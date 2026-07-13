"""Replay-safe claim and finding reconciliation for self-improvement cycles."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .adapters import FindingRecord, FindingsAdapter, PublicationState
from .errors import PolicyViolationError
from .projects import _require_slug, _require_text

_CYCLE_ID = re.compile(r"^cycle-[0-9a-f]{64}$")


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
