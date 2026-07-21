"""Deterministic delivered-cycle completion records and coordination."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .adapters import (
    IntakeAdapter,
    IntakeCompletionReceipt,
    NotificationAdapter,
    NotificationReceipt,
)
from .controller import CycleAdmission, validate_notification_receipt
from .errors import PolicyViolationError
from .projects import _require_digest, _require_text
from .registrations import ControllerRegistration
from .state import WorkflowLedger, WorkflowStage

COMPLETION_PREVIEW_SCHEMA = "daidala.cycle-completion-preview/v1"
COMPLETION_SCHEMA = "daidala.cycle-completion/v1"


@dataclass(frozen=True)
class CycleCompletionPreview:
    cycle_id: str
    workflow_id: str
    intake_item_id: str
    admission_digest: str
    plan_revision: int
    plan_digest: str
    review_digest: str
    delivery_digest: str
    verification_digests: tuple[str, ...]
    schema: str = COMPLETION_PREVIEW_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != COMPLETION_PREVIEW_SCHEMA:
            raise PolicyViolationError(
                f"completion preview schema must be {COMPLETION_PREVIEW_SCHEMA!r}"
            )
        _require_text(self.cycle_id, "completion cycle ID", 256)
        if self.workflow_id != self.cycle_id:
            raise PolicyViolationError("completion workflow ID must equal the cycle ID")
        _require_text(self.intake_item_id, "completion intake item ID", 256)
        for value, label in (
            (self.admission_digest, "completion admission digest"),
            (self.plan_digest, "completion plan digest"),
            (self.review_digest, "completion review digest"),
            (self.delivery_digest, "completion delivery digest"),
        ):
            _require_digest(value, label)
        if (
            isinstance(self.plan_revision, bool)
            or not isinstance(self.plan_revision, int)
            or self.plan_revision < 0
        ):
            raise PolicyViolationError(
                "completion plan revision must be a non-negative integer"
            )
        if not isinstance(self.verification_digests, tuple) or not self.verification_digests:
            raise PolicyViolationError("completion requires verification evidence")
        for digest in self.verification_digests:
            _require_digest(digest, "completion verification digest")
        if tuple(sorted(set(self.verification_digests))) != self.verification_digests:
            raise PolicyViolationError("completion verification digests must be unique and sorted")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "cycle_id": self.cycle_id,
            "workflow_id": self.workflow_id,
            "intake_item_id": self.intake_item_id,
            "admission_digest": self.admission_digest,
            "plan_revision": self.plan_revision,
            "plan_digest": self.plan_digest,
            "review_digest": self.review_digest,
            "delivery_digest": self.delivery_digest,
            "verification_digests": list(self.verification_digests),
        }

    def canonical_bytes(self) -> bytes:
        return _canonical_json(self.to_dict())

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    @classmethod
    def from_dict(cls, raw: Any) -> CycleCompletionPreview:
        _require_fields(
            raw,
            {
                "schema",
                "cycle_id",
                "workflow_id",
                "intake_item_id",
                "admission_digest",
                "plan_revision",
                "plan_digest",
                "review_digest",
                "delivery_digest",
                "verification_digests",
            },
            "cycle completion preview",
        )
        digests = raw["verification_digests"]
        if not isinstance(digests, list) or any(not isinstance(row, str) for row in digests):
            raise PolicyViolationError("completion verification digests must be strings")
        return cls(**{**raw, "verification_digests": tuple(digests)})


@dataclass(frozen=True)
class CycleCompletion:
    preview: CycleCompletionPreview
    remote_receipt: IntakeCompletionReceipt
    notification_receipt: NotificationReceipt
    completed_at: datetime
    schema: str = COMPLETION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != COMPLETION_SCHEMA:
            raise PolicyViolationError(f"cycle completion schema must be {COMPLETION_SCHEMA!r}")
        if self.remote_receipt.item_id != self.preview.intake_item_id:
            raise PolicyViolationError("completion receipt intake item does not match preview")
        if self.remote_receipt.cycle_id != self.preview.cycle_id:
            raise PolicyViolationError("completion receipt cycle does not match preview")
        expected_event = f"{self.preview.cycle_id}:completed"
        if self.notification_receipt.event_id != expected_event:
            raise PolicyViolationError("completion notification event does not match preview")
        if not isinstance(self.completed_at, datetime) or self.completed_at.tzinfo is None:
            raise PolicyViolationError("cycle completion timestamp must be timezone-aware")
        if self.completed_at < self.remote_receipt.completed_at:
            raise PolicyViolationError("cycle completion precedes remote completion")
        if self.completed_at < self.notification_receipt.delivered_at:
            raise PolicyViolationError("cycle completion precedes its notification")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "preview": self.preview.to_dict(),
            "remote_receipt": self.remote_receipt.to_dict(),
            "notification_receipt": self.notification_receipt.to_dict(),
            "completed_at": self.completed_at.isoformat(),
        }

    def canonical_bytes(self) -> bytes:
        return _canonical_json(self.to_dict())

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    @classmethod
    def from_dict(cls, raw: Any) -> CycleCompletion:
        _require_fields(
            raw,
            {
                "schema",
                "preview",
                "remote_receipt",
                "notification_receipt",
                "completed_at",
            },
            "cycle completion",
        )
        try:
            completed_at = datetime.fromisoformat(raw["completed_at"])
        except (TypeError, ValueError) as error:
            raise PolicyViolationError("cycle completion timestamp must be ISO-8601") from error
        return cls(
            schema=raw["schema"],
            preview=CycleCompletionPreview.from_dict(raw["preview"]),
            remote_receipt=IntakeCompletionReceipt.from_dict(raw["remote_receipt"]),
            notification_receipt=NotificationReceipt.from_dict(raw["notification_receipt"]),
            completed_at=completed_at,
        )


class CompletionArtifactStore:
    """Persist replay-safe completion receipts without altering admission history."""

    def __init__(self, data_root: Path) -> None:
        self.data_root = Path(data_root).resolve()

    def load_remote_receipt(
        self, preview: CycleCompletionPreview
    ) -> IntakeCompletionReceipt | None:
        raw = self._load(self._root(preview) / "completion-remote.json", "remote completion")
        return None if raw is None else IntakeCompletionReceipt.from_dict(raw)

    def save_remote_receipt(
        self, preview: CycleCompletionPreview, receipt: IntakeCompletionReceipt
    ) -> None:
        self._write_once(self._root(preview) / "completion-remote.json", receipt.canonical_bytes())

    def load_notification_receipt(
        self, preview: CycleCompletionPreview
    ) -> NotificationReceipt | None:
        raw = self._load(
            self._root(preview) / "completion-notification.json",
            "completion notification",
        )
        return None if raw is None else NotificationReceipt.from_dict(raw)

    def save_notification_receipt(
        self, preview: CycleCompletionPreview, receipt: NotificationReceipt
    ) -> None:
        self._write_once(
            self._root(preview) / "completion-notification.json",
            _canonical_json(receipt.to_dict()),
        )

    def load_completion(self, preview: CycleCompletionPreview) -> CycleCompletion | None:
        raw = self._load(self._root(preview) / "completion.json", "cycle completion")
        return None if raw is None else CycleCompletion.from_dict(raw)

    def save_completion(self, completion: CycleCompletion) -> None:
        self._write_once(
            self._root(completion.preview) / "completion.json", completion.canonical_bytes()
        )

    def _root(self, preview: CycleCompletionPreview) -> Path:
        project_id = _project_id_from_admission(self.data_root, preview)
        return self.data_root / "projects" / project_id / "cycles" / preview.cycle_id

    @staticmethod
    def _load(path: Path, label: str) -> Any | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise PolicyViolationError(f"stored {label} is unreadable") from error

    @staticmethod
    def _write_once(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_bytes() != content:
                raise PolicyViolationError(
                    f"immutable cycle artifact conflicts at {path.name!r}"
                )
            if path.stat().st_mode & 0o777 != 0o600:
                raise PolicyViolationError(
                    f"immutable cycle artifact has unsafe mode at {path.name!r}"
                )
            return
        try:
            with path.open("xb") as handle:
                handle.write(content)
            os.chmod(path, 0o600)
        except FileExistsError as error:
            if path.read_bytes() != content:
                raise PolicyViolationError(
                    f"immutable cycle artifact conflicts at {path.name!r}"
                ) from error


class CompletionCoordinator:
    """Converge remote completion, attended notification, and immutable state."""

    def __init__(
        self,
        *,
        store: CompletionArtifactStore,
        intake_adapter: IntakeAdapter,
        notification_adapter: NotificationAdapter,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self.intake_adapter = intake_adapter
        self.notification_adapter = notification_adapter
        self.clock = clock or (lambda: datetime.now(UTC))

    def complete(
        self,
        preview: CycleCompletionPreview,
        registration: ControllerRegistration,
    ) -> CycleCompletion:
        stored = self.store.load_completion(preview)
        if stored is not None:
            if stored.preview != preview:
                raise PolicyViolationError("stored cycle completion conflicts with preview")
            return stored
        remote = self.store.load_remote_receipt(preview)
        if remote is None:
            remote = self.intake_adapter.complete(preview.intake_item_id, preview.cycle_id)
            if not isinstance(remote, IntakeCompletionReceipt):
                raise PolicyViolationError("intake adapter returned an invalid completion receipt")
            self.store.save_remote_receipt(preview, remote)
        if remote.item_id != preview.intake_item_id or remote.cycle_id != preview.cycle_id:
            raise PolicyViolationError("remote completion receipt conflicts with preview")
        event_id = f"{preview.cycle_id}:completed"
        receipt = self.store.load_notification_receipt(preview)
        if receipt is None:
            receipt = self.notification_adapter.deliver(
                {
                    "event_id": event_id,
                    "event": "cycle-completed",
                    "cycle_id": preview.cycle_id,
                    "workflow_id": preview.workflow_id,
                    "intake_item_id": preview.intake_item_id,
                    "completion_preview_digest": preview.digest,
                    "remote_completion_digest": remote.digest,
                }
            )
            if not isinstance(receipt, NotificationReceipt):
                raise PolicyViolationError(
                    "notification adapter returned an invalid completion receipt"
                )
            self.store.save_notification_receipt(preview, receipt)
        validate_notification_receipt(receipt, registration, event_id)
        completed_at = max(self.clock(), remote.completed_at, receipt.delivered_at)
        completion = CycleCompletion(preview, remote, receipt, completed_at)
        self.store.save_completion(completion)
        return completion


def build_completion_preview(
    admission: CycleAdmission,
    ledger: WorkflowLedger,
) -> CycleCompletionPreview:
    if (
        ledger.workflow_id != admission.workflow_id
        or ledger.workflow_id != admission.cycle.cycle_id
    ):
        raise PolicyViolationError("completion workflow does not match admission")
    if ledger.approval is None or ledger.current_plan_digest is None:
        raise PolicyViolationError("completion requires an approved current plan")
    if ledger.worktree_owned or ledger.worktree_path is not None:
        raise PolicyViolationError("completion requires released worktree ownership")
    if ledger.committed or ledger.pushed:
        raise PolicyViolationError("completion cannot represent committed or pushed work")
    review = ledger.artifact_for(WorkflowStage.REVIEW)
    delivery = ledger.artifact_for(WorkflowStage.DELIVER)
    if review is None or delivery is None:
        raise PolicyViolationError("completion requires review and delivery artifacts")
    verification = tuple(
        sorted(
            {
                row.output_digest
                for row in ledger.verification_evidence
                if row.plan_revision == ledger.plan_revision and row.exit_code == 0
            }
        )
    )
    if not verification:
        raise PolicyViolationError("completion requires passing verification evidence")
    admission_digest = hashlib.sha256(admission.canonical_bytes()).hexdigest()
    return CycleCompletionPreview(
        cycle_id=admission.cycle.cycle_id,
        workflow_id=admission.workflow_id,
        intake_item_id=admission.intake.item_id,
        admission_digest=admission_digest,
        plan_revision=ledger.plan_revision,
        plan_digest=ledger.current_plan_digest,
        review_digest=review.digest,
        delivery_digest=delivery.digest,
        verification_digests=verification,
    )


def _project_id_from_admission(data_root: Path, preview: CycleCompletionPreview) -> str:
    projects = data_root / "projects"
    matches = [
        path.parent.parent.parent.name
        for path in projects.glob(f"*/cycles/{preview.cycle_id}/admission.json")
    ]
    if len(matches) != 1:
        raise PolicyViolationError("completion cycle admission ownership is ambiguous")
    return matches[0]


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _require_fields(raw: Any, expected: set[str], label: str) -> None:
    if not isinstance(raw, dict):
        raise PolicyViolationError(f"{label} must be an object")
    actual = set(raw)
    if actual != expected:
        raise PolicyViolationError(
            f"{label} fields mismatch; missing={sorted(expected - actual)!r}, "
            f"unknown={sorted(actual - expected)!r}"
        )
