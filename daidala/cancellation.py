"""Deterministic project-cycle cancellation records and coordination."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from .adapters import (
    IntakeAdapter,
    IntakeCancellationReceipt,
    NotificationAdapter,
    NotificationReceipt,
)
from .controller import CycleAdmission, validate_notification_receipt
from .errors import PolicyViolationError
from .projects import _require_digest, _require_slug, _require_text
from .registrations import ControllerRegistration
from .state import WorkflowLedger

CANCELLATION_PREVIEW_SCHEMA = "daidala.cycle-cancellation-preview/v1"
CANCELLATION_SCHEMA = "daidala.cycle-cancellation/v1"
CANCELLATION_WORKFLOW_RECEIPT_SCHEMA = "daidala.cycle-cancellation-workflow/v1"


class WorkflowCanceller(Protocol):
    def cancel(self, workflow_id: str, reason: str) -> WorkflowLedger: ...


@dataclass(frozen=True)
class CycleCancellationPreview:
    project_id: str
    cycle_id: str
    workflow_id: str
    board: str
    controller_profile: str
    intake_item_id: str
    admission_digest: str
    manifest_digest: str
    registration_digest: str
    workflow_digest: str
    reason: str
    schema: str = CANCELLATION_PREVIEW_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != CANCELLATION_PREVIEW_SCHEMA:
            raise PolicyViolationError(
                f"cancellation preview schema must be {CANCELLATION_PREVIEW_SCHEMA!r}"
            )
        _require_slug(self.project_id, "cancellation project ID")
        _require_text(self.cycle_id, "cancellation cycle ID", 256)
        if self.workflow_id != self.cycle_id:
            raise PolicyViolationError("cancellation workflow ID must equal the cycle ID")
        _require_slug(self.board, "cancellation board")
        _require_slug(self.controller_profile, "cancellation controller profile")
        _require_text(self.intake_item_id, "cancellation intake item ID", 256)
        for value, label in (
            (self.admission_digest, "cancellation admission digest"),
            (self.manifest_digest, "cancellation manifest digest"),
            (self.registration_digest, "cancellation registration digest"),
            (self.workflow_digest, "cancellation workflow digest"),
        ):
            _require_digest(value, label)
        _require_text(self.reason, "cancellation reason", 1_000)
        if self.reason != self.reason.strip():
            raise PolicyViolationError("cancellation reason must be stripped")

    @property
    def reason_digest(self) -> str:
        return hashlib.sha256(self.reason.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "project_id": self.project_id,
            "cycle_id": self.cycle_id,
            "workflow_id": self.workflow_id,
            "board": self.board,
            "controller_profile": self.controller_profile,
            "intake_item_id": self.intake_item_id,
            "admission_digest": self.admission_digest,
            "manifest_digest": self.manifest_digest,
            "registration_digest": self.registration_digest,
            "workflow_digest": self.workflow_digest,
            "reason": self.reason,
            "reason_digest": self.reason_digest,
        }

    def canonical_bytes(self) -> bytes:
        return _canonical_json(self.to_dict())

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    @classmethod
    def from_dict(cls, raw: Any) -> CycleCancellationPreview:
        _require_fields(
            raw,
            {
                "schema",
                "project_id",
                "cycle_id",
                "workflow_id",
                "board",
                "controller_profile",
                "intake_item_id",
                "admission_digest",
                "manifest_digest",
                "registration_digest",
                "workflow_digest",
                "reason",
                "reason_digest",
            },
            "cycle cancellation preview",
        )
        expected_reason_digest = raw["reason_digest"]
        preview = cls(**{key: value for key, value in raw.items() if key != "reason_digest"})
        if preview.reason_digest != expected_reason_digest:
            raise PolicyViolationError("cancellation reason digest does not match reason")
        return preview


@dataclass(frozen=True)
class CycleCancellation:
    preview: CycleCancellationPreview
    remote_receipt: IntakeCancellationReceipt
    notification_receipt: NotificationReceipt
    canceled_at: datetime
    schema: str = CANCELLATION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != CANCELLATION_SCHEMA:
            raise PolicyViolationError(
                f"cycle cancellation schema must be {CANCELLATION_SCHEMA!r}"
            )
        if self.remote_receipt.item_id != self.preview.intake_item_id:
            raise PolicyViolationError("cancellation receipt intake item does not match preview")
        if self.remote_receipt.cycle_id != self.preview.cycle_id:
            raise PolicyViolationError("cancellation receipt cycle does not match preview")
        if self.remote_receipt.reason_digest != self.preview.reason_digest:
            raise PolicyViolationError("cancellation receipt reason does not match preview")
        if self.notification_receipt.event_id != f"{self.preview.cycle_id}:cancelled":
            raise PolicyViolationError("cancellation notification event does not match preview")
        if not isinstance(self.canceled_at, datetime) or self.canceled_at.tzinfo is None:
            raise PolicyViolationError("cycle cancellation timestamp must be timezone-aware")
        if self.canceled_at < self.remote_receipt.canceled_at:
            raise PolicyViolationError("cycle cancellation precedes remote cancellation")
        if self.canceled_at < self.notification_receipt.delivered_at:
            raise PolicyViolationError("cycle cancellation precedes its notification")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "preview": self.preview.to_dict(),
            "remote_receipt": self.remote_receipt.to_dict(),
            "notification_receipt": self.notification_receipt.to_dict(),
            "canceled_at": self.canceled_at.isoformat(),
        }

    def canonical_bytes(self) -> bytes:
        return _canonical_json(self.to_dict())

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    @classmethod
    def from_dict(cls, raw: Any) -> CycleCancellation:
        _require_fields(
            raw,
            {
                "schema",
                "preview",
                "remote_receipt",
                "notification_receipt",
                "canceled_at",
            },
            "cycle cancellation",
        )
        try:
            canceled_at = datetime.fromisoformat(raw["canceled_at"])
        except (TypeError, ValueError) as error:
            raise PolicyViolationError(
                "cycle cancellation timestamp must be ISO-8601"
            ) from error
        return cls(
            schema=raw["schema"],
            preview=CycleCancellationPreview.from_dict(dict(raw["preview"])),
            remote_receipt=IntakeCancellationReceipt.from_dict(raw["remote_receipt"]),
            notification_receipt=NotificationReceipt.from_dict(
                raw["notification_receipt"]
            ),
            canceled_at=canceled_at,
        )


class CancellationArtifactStore:
    """Persist replay-safe cancellation receipts beside immutable cycle evidence."""

    def __init__(self, data_root: Path, project_id: str, cycle_id: str) -> None:
        self.root = (
            Path(data_root).resolve()
            / "projects"
            / project_id
            / "cycles"
            / cycle_id
        )

    def load_remote_receipt(self) -> IntakeCancellationReceipt | None:
        raw = self._load(self.root / "cancellation-remote.json", "remote cancellation")
        return None if raw is None else IntakeCancellationReceipt.from_dict(raw)

    def save_remote_receipt(self, receipt: IntakeCancellationReceipt) -> None:
        self._write_once(
            self.root / "cancellation-remote.json", receipt.canonical_bytes()
        )

    def load_notification_receipt(self) -> NotificationReceipt | None:
        raw = self._load(
            self.root / "cancellation-notification.json",
            "cancellation notification",
        )
        return None if raw is None else NotificationReceipt.from_dict(raw)

    def load_workflow_receipt(
        self, preview: CycleCancellationPreview
    ) -> dict[str, object] | None:
        raw = self._load(
            self.root / "cancellation-workflow.json",
            "workflow cancellation",
        )
        if raw is None:
            return None
        expected = {
            "schema": CANCELLATION_WORKFLOW_RECEIPT_SCHEMA,
            "cycle_id": preview.cycle_id,
            "workflow_id": preview.workflow_id,
            "preview_digest": preview.digest,
            "worktree_released": True,
        }
        if raw != expected:
            raise PolicyViolationError("stored workflow cancellation conflicts with preview")
        return expected

    def save_workflow_receipt(self, preview: CycleCancellationPreview) -> None:
        self._write_once(
            self.root / "cancellation-workflow.json",
            _canonical_json(
                {
                    "schema": CANCELLATION_WORKFLOW_RECEIPT_SCHEMA,
                    "cycle_id": preview.cycle_id,
                    "workflow_id": preview.workflow_id,
                    "preview_digest": preview.digest,
                    "worktree_released": True,
                }
            ),
        )

    def save_notification_receipt(self, receipt: NotificationReceipt) -> None:
        self._write_once(
            self.root / "cancellation-notification.json",
            _canonical_json(receipt.to_dict()),
        )

    def load_cancellation(self) -> CycleCancellation | None:
        raw = self._load(self.root / "cancellation.json", "cycle cancellation")
        return None if raw is None else CycleCancellation.from_dict(raw)

    def save_cancellation(self, cancellation: CycleCancellation) -> None:
        self._write_once(
            self.root / "cancellation.json", cancellation.canonical_bytes()
        )

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
                    f"immutable cancellation artifact conflicts at {path.name!r}"
                )
            if path.stat().st_mode & 0o777 != 0o600:
                raise PolicyViolationError(
                    f"immutable cancellation artifact has unsafe mode at {path.name!r}"
                )
            return
        try:
            with path.open("xb") as handle:
                handle.write(content)
            os.chmod(path, 0o600)
        except FileExistsError as error:
            if path.read_bytes() != content:
                raise PolicyViolationError(
                    f"immutable cancellation artifact conflicts at {path.name!r}"
                ) from error


class CancellationCoordinator:
    """Converge remote closure, workflow archival, notification, and evidence."""

    def __init__(
        self,
        *,
        store: CancellationArtifactStore,
        intake_adapter: IntakeAdapter,
        notification_adapter: NotificationAdapter,
        workflow: WorkflowCanceller,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self.intake_adapter = intake_adapter
        self.notification_adapter = notification_adapter
        self.workflow = workflow
        self.clock = clock or (lambda: datetime.now(UTC))

    def cancel(
        self,
        preview: CycleCancellationPreview,
        registration: ControllerRegistration,
    ) -> CycleCancellation:
        stored = self.store.load_cancellation()
        if stored is not None:
            if stored.preview != preview:
                raise PolicyViolationError("stored cycle cancellation conflicts with preview")
            return stored
        remote = self.store.load_remote_receipt()
        if remote is None:
            remote = self.intake_adapter.cancel(
                preview.intake_item_id,
                preview.cycle_id,
                preview.reason_digest,
            )
            if not isinstance(remote, IntakeCancellationReceipt):
                raise PolicyViolationError(
                    "intake adapter returned an invalid cancellation receipt"
                )
            self.store.save_remote_receipt(remote)
        if (
            remote.item_id != preview.intake_item_id
            or remote.cycle_id != preview.cycle_id
            or remote.reason_digest != preview.reason_digest
        ):
            raise PolicyViolationError("remote cancellation receipt conflicts with preview")
        workflow_receipt = self.store.load_workflow_receipt(preview)
        if workflow_receipt is None:
            ledger = self.workflow.cancel(preview.workflow_id, preview.reason)
            if ledger.workflow_id != preview.workflow_id:
                raise PolicyViolationError("canceled workflow does not match preview")
            if ledger.worktree_owned or ledger.worktree_path is not None:
                raise PolicyViolationError("canceled workflow retains worktree ownership")
            self.store.save_workflow_receipt(preview)
        event_id = f"{preview.cycle_id}:cancelled"
        notification = self.store.load_notification_receipt()
        if notification is None:
            notification = self.notification_adapter.deliver(
                {
                    "event_id": event_id,
                    "event": "cycle-cancelled",
                    "cycle_id": preview.cycle_id,
                    "workflow_id": preview.workflow_id,
                    "intake_item_id": preview.intake_item_id,
                    "cancellation_preview_digest": preview.digest,
                    "remote_cancellation_digest": remote.digest,
                }
            )
            if not isinstance(notification, NotificationReceipt):
                raise PolicyViolationError(
                    "notification adapter returned an invalid cancellation receipt"
                )
            self.store.save_notification_receipt(notification)
        validate_notification_receipt(notification, registration, event_id)
        canceled_at = max(self.clock(), remote.canceled_at, notification.delivered_at)
        cancellation = CycleCancellation(preview, remote, notification, canceled_at)
        self.store.save_cancellation(cancellation)
        return cancellation


def build_cancellation_preview(
    *,
    project_id: str,
    manifest_digest: str,
    registration: ControllerRegistration,
    admission: CycleAdmission,
    ledger: WorkflowLedger,
    reason: str,
) -> CycleCancellationPreview:
    if ledger.workflow_id != admission.workflow_id:
        raise PolicyViolationError("cancellation workflow does not match admission")
    if ledger.board_slug != registration.board or admission.board != registration.board:
        raise PolicyViolationError("cancellation board does not match registration")
    if ledger.target_repository != admission.checkout:
        raise PolicyViolationError("cancellation checkout does not match admission")
    if ledger.requested_goal != admission.intake.goal:
        raise PolicyViolationError("cancellation goal does not match admission")
    if (
        ledger.baseline_commit != admission.cycle.baseline_revision
        or ledger.pack_name != admission.cycle.pack_name
        or ledger.pack_source_revision != admission.cycle.pack_source_revision
    ):
        raise PolicyViolationError("cancellation workflow identity does not match cycle")
    stable_workflow = ledger.to_dict()
    for mutable_cleanup_field in ("updated_at", "worktree_path", "worktree_owned"):
        stable_workflow.pop(mutable_cleanup_field)
    return CycleCancellationPreview(
        project_id=project_id,
        cycle_id=admission.cycle.cycle_id,
        workflow_id=admission.workflow_id,
        board=registration.board,
        controller_profile=registration.controller_profile,
        intake_item_id=admission.intake.item_id,
        admission_digest=hashlib.sha256(admission.canonical_bytes()).hexdigest(),
        manifest_digest=manifest_digest,
        registration_digest=registration.digest,
        workflow_digest=hashlib.sha256(_canonical_json(stable_workflow)).hexdigest(),
        reason=reason.strip(),
    )


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
