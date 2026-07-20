"""Replay-safe claim and finding reconciliation for self-improvement cycles."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from .adapters import (
    FindingRecord,
    FindingsAdapter,
    NotificationReceipt,
    PublicationState,
)
from .errors import PolicyViolationError
from .projects import _require_digest, _require_slug, _require_text

_CYCLE_ID = re.compile(r"^cycle-[0-9a-f]{64}$")
RECONCILIATION_PREVIEW_SCHEMA = "daidala.reconciliation-preview/v1"
RECONCILIATION_RESULT_SCHEMA = "daidala.reconciliation-result/v1"


class ReconciliationOutcome(StrEnum):
    IDLE = "idle"
    ACTIVE_CYCLE = "active-cycle"
    BLOCKED = "blocked"
    ADMISSION_PREVIEW = "admission-preview"
    ADMITTED = "admitted"
    REPLAYED = "replayed"


@dataclass(frozen=True)
class ClaimRecoveryEvidence:
    cycle_id: str
    intake_item_id: str
    claimant: str
    observed_at: datetime
    lease_expires_at: datetime
    daidala_has_active_owner: bool
    board_has_active_owner: bool

    def __post_init__(self) -> None:
        if not isinstance(self.cycle_id, str) or not _CYCLE_ID.fullmatch(self.cycle_id):
            raise PolicyViolationError("claim recovery cycle ID is invalid")
        _require_text(self.intake_item_id, "claim recovery intake item ID", 256)
        _require_text(self.claimant, "claim recovery claimant", 256)
        if self.claimant != self.cycle_id:
            raise PolicyViolationError("claim recovery claimant must equal the cycle ID")
        for value, label in (
            (self.observed_at, "claim recovery observation time"),
            (self.lease_expires_at, "claim recovery lease expiry"),
        ):
            if not isinstance(value, datetime) or value.tzinfo is None:
                raise PolicyViolationError(f"{label} must be timezone-aware")
        for value, label in (
            (self.daidala_has_active_owner, "Daidala active owner"),
            (self.board_has_active_owner, "board active owner"),
        ):
            if not isinstance(value, bool):
                raise PolicyViolationError(f"{label} must be a boolean")

    @property
    def recoverable(self) -> bool:
        return (
            self.observed_at >= self.lease_expires_at
            and not self.daidala_has_active_owner
            and not self.board_has_active_owner
        )

    def require_recoverable(self) -> None:
        if self.observed_at < self.lease_expires_at:
            raise PolicyViolationError("claim lease has not expired")
        if self.daidala_has_active_owner or self.board_has_active_owner:
            raise PolicyViolationError("claim recovery requires proof of no active owner")

    def to_dict(self) -> dict[str, object]:
        return {
            "cycle_id": self.cycle_id,
            "intake_item_id": self.intake_item_id,
            "claimant": self.claimant,
            "observed_at": self.observed_at.isoformat(),
            "lease_expires_at": self.lease_expires_at.isoformat(),
            "daidala_has_active_owner": self.daidala_has_active_owner,
            "board_has_active_owner": self.board_has_active_owner,
        }

    @classmethod
    def from_dict(cls, raw: Any) -> ClaimRecoveryEvidence:
        _require_fields(
            raw,
            {
                "cycle_id",
                "intake_item_id",
                "claimant",
                "observed_at",
                "lease_expires_at",
                "daidala_has_active_owner",
                "board_has_active_owner",
            },
            "claim recovery evidence",
        )
        try:
            observed_at = datetime.fromisoformat(raw["observed_at"])
            lease_expires_at = datetime.fromisoformat(raw["lease_expires_at"])
        except (TypeError, ValueError) as error:
            raise PolicyViolationError(
                "claim recovery timestamps must be ISO-8601 strings"
            ) from error
        return cls(
            cycle_id=raw["cycle_id"],
            intake_item_id=raw["intake_item_id"],
            claimant=raw["claimant"],
            observed_at=observed_at,
            lease_expires_at=lease_expires_at,
            daidala_has_active_owner=raw["daidala_has_active_owner"],
            board_has_active_owner=raw["board_has_active_owner"],
        )


@dataclass(frozen=True)
class ReconciliationPreview:
    project_id: str
    manifest_digest: str
    registration_digest: str
    outcome: ReconciliationOutcome
    candidate_count: int
    cycle_id: str | None = None
    workflow_id: str | None = None
    intake_item_id: str | None = None
    intake_digest: str | None = None
    blocker: str | None = None
    recovery: ClaimRecoveryEvidence | None = None
    schema: str = RECONCILIATION_PREVIEW_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != RECONCILIATION_PREVIEW_SCHEMA:
            raise PolicyViolationError("reconciliation preview schema is invalid")
        _require_slug(self.project_id, "reconciliation project ID")
        _require_digest(self.manifest_digest, "reconciliation manifest digest")
        _require_digest(self.registration_digest, "reconciliation registration digest")
        if not isinstance(self.outcome, ReconciliationOutcome):
            raise PolicyViolationError("reconciliation outcome is invalid")
        if (
            isinstance(self.candidate_count, bool)
            or not isinstance(self.candidate_count, int)
            or not 0 <= self.candidate_count <= 100
        ):
            raise PolicyViolationError("reconciliation candidate count is invalid")
        if self.cycle_id is not None and not _CYCLE_ID.fullmatch(self.cycle_id):
            raise PolicyViolationError("reconciliation cycle ID is invalid")
        if self.workflow_id is not None and self.workflow_id != self.cycle_id:
            raise PolicyViolationError("reconciliation workflow ID must equal cycle ID")
        if self.intake_item_id is not None:
            _require_text(self.intake_item_id, "reconciliation intake item ID", 256)
        if self.intake_digest is not None:
            _require_digest(self.intake_digest, "reconciliation intake digest")
        if self.blocker is not None:
            _require_text(self.blocker, "reconciliation blocker", 512)
        has_identity = all(
            value is not None
            for value in (
                self.cycle_id,
                self.workflow_id,
                self.intake_item_id,
                self.intake_digest,
            )
        )
        if self.outcome in {
            ReconciliationOutcome.ACTIVE_CYCLE,
            ReconciliationOutcome.ADMISSION_PREVIEW,
        } and not has_identity:
            raise PolicyViolationError("reconciliation outcome requires exact cycle identity")
        if self.outcome is ReconciliationOutcome.BLOCKED and self.blocker is None:
            raise PolicyViolationError("blocked reconciliation requires a blocker")
        if self.outcome is not ReconciliationOutcome.BLOCKED and self.blocker is not None:
            raise PolicyViolationError("non-blocked reconciliation cannot contain a blocker")
        if self.recovery is not None:
            if self.outcome is not ReconciliationOutcome.ADMISSION_PREVIEW:
                raise PolicyViolationError("claim recovery requires an admission preview")
            if self.recovery.intake_item_id != self.intake_item_id:
                raise PolicyViolationError("claim recovery intake identity conflicts")
            self.recovery.require_recoverable()

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "project_id": self.project_id,
            "manifest_digest": self.manifest_digest,
            "registration_digest": self.registration_digest,
            "outcome": self.outcome.value,
            "candidate_count": self.candidate_count,
            "cycle_id": self.cycle_id,
            "workflow_id": self.workflow_id,
            "intake_item_id": self.intake_item_id,
            "intake_digest": self.intake_digest,
            "blocker": self.blocker,
            "recovery": None if self.recovery is None else self.recovery.to_dict(),
        }

    @property
    def digest(self) -> str:
        identity = self.to_dict()
        recovery = identity["recovery"]
        if isinstance(recovery, dict):
            recovery = dict(recovery)
            recovery.pop("observed_at")
            identity["recovery"] = recovery
        return hashlib.sha256(_canonical_json(identity)).hexdigest()

    @classmethod
    def from_dict(cls, raw: Any) -> ReconciliationPreview:
        _require_fields(
            raw,
            {
                "schema",
                "project_id",
                "manifest_digest",
                "registration_digest",
                "outcome",
                "candidate_count",
                "cycle_id",
                "workflow_id",
                "intake_item_id",
                "intake_digest",
                "blocker",
                "recovery",
            },
            "reconciliation preview",
        )
        try:
            outcome = ReconciliationOutcome(raw["outcome"])
        except (TypeError, ValueError) as error:
            raise PolicyViolationError("reconciliation outcome is invalid") from error
        return cls(
            schema=raw["schema"],
            project_id=raw["project_id"],
            manifest_digest=raw["manifest_digest"],
            registration_digest=raw["registration_digest"],
            outcome=outcome,
            candidate_count=raw["candidate_count"],
            cycle_id=raw["cycle_id"],
            workflow_id=raw["workflow_id"],
            intake_item_id=raw["intake_item_id"],
            intake_digest=raw["intake_digest"],
            blocker=raw["blocker"],
            recovery=(
                None
                if raw["recovery"] is None
                else ClaimRecoveryEvidence.from_dict(raw["recovery"])
            ),
        )


@dataclass(frozen=True)
class ReconciliationResult:
    preview: ReconciliationPreview
    outcome: ReconciliationOutcome
    notification_receipts: tuple[NotificationReceipt, ...] = ()
    schema: str = RECONCILIATION_RESULT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != RECONCILIATION_RESULT_SCHEMA:
            raise PolicyViolationError("reconciliation result schema is invalid")
        if self.outcome not in {
            ReconciliationOutcome.IDLE,
            ReconciliationOutcome.ACTIVE_CYCLE,
            ReconciliationOutcome.BLOCKED,
            ReconciliationOutcome.ADMITTED,
            ReconciliationOutcome.REPLAYED,
        }:
            raise PolicyViolationError("reconciliation result outcome is not terminal")
        allowed_previews = {
            ReconciliationOutcome.IDLE: {ReconciliationOutcome.IDLE},
            ReconciliationOutcome.ACTIVE_CYCLE: {ReconciliationOutcome.ACTIVE_CYCLE},
            ReconciliationOutcome.BLOCKED: {ReconciliationOutcome.BLOCKED},
            ReconciliationOutcome.ADMITTED: {ReconciliationOutcome.ADMISSION_PREVIEW},
            ReconciliationOutcome.REPLAYED: {ReconciliationOutcome.ACTIVE_CYCLE},
        }
        if self.preview.outcome not in allowed_previews[self.outcome]:
            raise PolicyViolationError("reconciliation result conflicts with preview outcome")
        if not isinstance(self.notification_receipts, tuple) or any(
            not isinstance(row, NotificationReceipt) for row in self.notification_receipts
        ):
            raise PolicyViolationError("reconciliation notification receipts are invalid")
        event_ids = tuple(row.event_id for row in self.notification_receipts)
        if len(set(event_ids)) != len(event_ids):
            raise PolicyViolationError("reconciliation notification receipts must be unique")
        if self.outcome is ReconciliationOutcome.BLOCKED:
            expected = f"reconciliation-{self.preview.digest}:blocked"
            if event_ids != (expected,):
                raise PolicyViolationError("blocked reconciliation receipt is not event-bound")
        elif self.outcome in {
            ReconciliationOutcome.ADMITTED,
            ReconciliationOutcome.REPLAYED,
        }:
            if not event_ids or event_ids[-1] != f"{self.preview.cycle_id}:admitted":
                raise PolicyViolationError("admission reconciliation receipt is not event-bound")
            if self.preview.recovery is not None and event_ids[0] != (
                f"{self.preview.cycle_id}:claim-recovered"
            ):
                raise PolicyViolationError("claim recovery receipt is not event-bound")
        elif event_ids:
            raise PolicyViolationError("non-notifying reconciliation contains receipts")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "preview": self.preview.to_dict(),
            "preview_digest": self.preview.digest,
            "outcome": self.outcome.value,
            "notification_receipts": [row.to_dict() for row in self.notification_receipts],
        }

    @property
    def digest(self) -> str:
        return hashlib.sha256(_canonical_json(self.to_dict())).hexdigest()

    @classmethod
    def from_dict(cls, raw: Any) -> ReconciliationResult:
        _require_fields(
            raw,
            {
                "schema",
                "preview",
                "preview_digest",
                "outcome",
                "notification_receipts",
            },
            "reconciliation result",
        )
        preview = ReconciliationPreview.from_dict(raw["preview"])
        if raw["preview_digest"] != preview.digest:
            raise PolicyViolationError("reconciliation preview digest conflicts")
        try:
            outcome = ReconciliationOutcome(raw["outcome"])
        except (TypeError, ValueError) as error:
            raise PolicyViolationError("reconciliation result outcome is invalid") from error
        receipts = raw["notification_receipts"]
        if not isinstance(receipts, list):
            raise PolicyViolationError("reconciliation notification receipts must be a list")
        return cls(
            schema=raw["schema"],
            preview=preview,
            outcome=outcome,
            notification_receipts=tuple(NotificationReceipt.from_dict(row) for row in receipts),
        )


class ReconciliationTickStore:
    """Persist one immutable result per content-addressed reconciliation preview."""

    def __init__(self, data_root: Path) -> None:
        if (
            not isinstance(data_root, Path)
            or not data_root.is_absolute()
            or ".." in data_root.parts
            or "." in data_root.parts
        ):
            raise PolicyViolationError("reconciliation data root must be absolute")
        self.data_root = data_root

    def load(self, preview: ReconciliationPreview) -> ReconciliationResult | None:
        path = self._path(preview)
        if not path.exists():
            return None
        try:
            result = ReconciliationResult.from_dict(json.loads(path.read_text("utf-8")))
        except (OSError, json.JSONDecodeError) as error:
            raise PolicyViolationError("stored reconciliation result is unreadable") from error
        if result.preview.digest != preview.digest:
            raise PolicyViolationError("stored reconciliation result conflicts with preview")
        if path.stat().st_mode & 0o777 != 0o600:
            raise PolicyViolationError("stored reconciliation result has unsafe mode")
        return result

    def save(self, result: ReconciliationResult) -> None:
        path = self._path(result.preview)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = _canonical_json(result.to_dict())
        if path.exists():
            if path.read_bytes() != content:
                raise PolicyViolationError("immutable reconciliation result conflicts")
            if path.stat().st_mode & 0o777 != 0o600:
                raise PolicyViolationError("stored reconciliation result has unsafe mode")
            return
        try:
            with path.open("xb") as handle:
                handle.write(content)
            os.chmod(path, 0o600)
        except FileExistsError as error:
            if path.read_bytes() != content:
                raise PolicyViolationError("immutable reconciliation result conflicts") from error

    def _path(self, preview: ReconciliationPreview) -> Path:
        return (
            self.data_root
            / "projects"
            / preview.project_id
            / "reconciliation"
            / "ticks"
            / f"{preview.digest}.json"
        )


class PendingFindingStore:
    """Persist local findings until an adapter returns a verified remote identity."""

    def __init__(self, data_root: Path) -> None:
        if (
            not isinstance(data_root, Path)
            or not data_root.is_absolute()
            or ".." in data_root.parts
            or "." in data_root.parts
        ):
            raise PolicyViolationError("finding data root must be an absolute resolved path")
        self.data_root = data_root

    def save_pending(self, finding: FindingRecord) -> FindingRecord:
        if finding.publication_state is not PublicationState.PENDING:
            raise PolicyViolationError("only pending findings can enter synchronization storage")
        self._write_once(self._pending_path(finding), _canonical_finding(finding))
        return finding

    def synchronize(
        self, finding_id: str, project_id: str, adapter: FindingsAdapter
    ) -> FindingRecord:
        _require_slug(finding_id, "finding ID")
        _require_slug(project_id, "finding project ID")
        published_path = self._published_path(project_id, finding_id)
        if published_path.exists():
            return _read_finding(published_path)
        pending = _read_finding(self._pending_path_for(project_id, finding_id))
        if pending.publication_state is not PublicationState.PENDING:
            raise PolicyViolationError("stored finding is not pending synchronization")
        published = adapter.synchronize(pending)
        if not isinstance(published, FindingRecord):
            raise PolicyViolationError("findings adapter returned an invalid record type")
        _validate_publication(pending, published)
        self._write_once(published_path, _canonical_finding(published))
        return published

    def _pending_path(self, finding: FindingRecord) -> Path:
        return self._pending_path_for(finding.project_id, finding.finding_id)

    def _pending_path_for(self, project_id: str, finding_id: str) -> Path:
        _require_slug(project_id, "finding project ID")
        _require_slug(finding_id, "finding ID")
        return (
            self.data_root
            / "projects"
            / project_id
            / "findings"
            / "pending"
            / f"{finding_id}.json"
        )

    def _published_path(self, project_id: str, finding_id: str) -> Path:
        _require_slug(project_id, "finding project ID")
        _require_slug(finding_id, "finding ID")
        return (
            self.data_root
            / "projects"
            / project_id
            / "findings"
            / "published"
            / f"{finding_id}.json"
        )

    @staticmethod
    def _write_once(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_bytes() != content:
                raise PolicyViolationError(f"immutable finding conflicts at {path.name!r}")
            return
        try:
            with path.open("xb") as handle:
                handle.write(content)
        except FileExistsError as error:
            if path.read_bytes() != content:
                raise PolicyViolationError(
                    f"immutable finding conflicts at {path.name!r}"
                ) from error


def _validate_publication(pending: FindingRecord, published: FindingRecord) -> None:
    if published.publication_state is not PublicationState.PUBLISHED:
        raise PolicyViolationError("findings adapter did not return published state")
    pending_identity = {
        **pending.to_dict(),
        "publication_state": PublicationState.PUBLISHED.value,
        "remote_identity": published.remote_identity,
        "remote_url": published.remote_url,
    }
    if published.to_dict() != pending_identity:
        raise PolicyViolationError("findings adapter changed immutable finding fields")


def _canonical_finding(finding: FindingRecord) -> bytes:
    return json.dumps(
        finding.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _read_finding(path: Path) -> FindingRecord:
    if not path.exists():
        raise PolicyViolationError("pending finding does not exist")
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PolicyViolationError("stored finding is unreadable") from error
    return FindingRecord.from_dict(raw)


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
