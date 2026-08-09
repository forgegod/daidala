"""Deterministic profile-local artifact curation and crash-convergent recovery."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import stat
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any

from .archive_io import ArchiveError, create_archive, restore_archive, verify_archive
from .artifact_access import (
    ArchivedArtifactSource,
    ArtifactAccessError,
    ArtifactAccessService,
    ArtifactId,
)
from .errors import PolicyViolationError
from .kanban import KanbanCardStatus
from .profile_files import ProfileFileError, atomic_write_private_text, read_private_text
from .state import WorkflowLedger, WorkflowStage
from .store import StoreError, WorkflowStore

_STATE_SCHEMA = "daidala.artifact-curator/v1"
_ARCHIVE_SCHEMA = "daidala.artifact-curator-archive/v1"
_ARCHIVE_ID_SCHEMA = "daidala.artifact-curator-archive-id/v1"
_STATE_FILENAME = "artifact-curator.json"
_MAX_STATE_BYTES = 1024 * 1024
_MAX_ARCHIVE_MANIFEST_BYTES = 1024 * 1024
_MAX_ROWS = 4096
_MAX_ARCHIVES_PER_WORKFLOW = 32
_MAX_MEMBER_PATH_BYTES = 512
_TERMINAL_CARD_STATES = frozenset({"done", "archived"})
_WORKFLOW_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

StatusProvider = Callable[[WorkflowLedger], tuple[KanbanCardStatus, ...]]
FaultInjector = Callable[[str], None]


class CuratorError(PolicyViolationError):
    """Raised when curator policy, state, or recovery cannot be verified."""


class CurationState(StrEnum):
    ACTIVE = "active"
    STALE = "stale"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class CuratorPolicy:
    enabled: bool = False
    stale_after_days: int = 30
    archive_after_days: int = 90

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise CuratorError("artifact curator policy is invalid")
        for value in (self.stale_after_days, self.archive_after_days):
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 3650:
                raise CuratorError("artifact curator policy is invalid")
        if self.archive_after_days <= self.stale_after_days:
            raise CuratorError("artifact curator archive age must exceed stale age")

    def to_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "stale_after_days": self.stale_after_days,
            "archive_after_days": self.archive_after_days,
        }

    @classmethod
    def from_dict(cls, raw: object) -> CuratorPolicy:
        if not isinstance(raw, dict) or set(raw) != {
            "enabled",
            "stale_after_days",
            "archive_after_days",
        }:
            raise CuratorError("artifact curator policy schema is invalid")
        try:
            return cls(**raw)
        except TypeError as error:
            raise CuratorError("artifact curator policy schema is invalid") from error


@dataclass(frozen=True)
class CurationRow:
    workflow_id: str
    state: CurationState
    first_terminal_observed_at: datetime | None
    last_transition_at: datetime
    pinned: bool
    archive_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _workflow_id(self.workflow_id)
        if not isinstance(self.state, CurationState) or not isinstance(self.pinned, bool):
            raise CuratorError("artifact curator row is invalid")
        _aware(self.last_transition_at, "last transition")
        if self.first_terminal_observed_at is not None:
            _aware(self.first_terminal_observed_at, "first terminal observation")
            if self.first_terminal_observed_at > self.last_transition_at:
                raise CuratorError("artifact curator row timestamps are invalid")
        if (
            not isinstance(self.archive_ids, tuple)
            or len(self.archive_ids) > _MAX_ARCHIVES_PER_WORKFLOW
        ):
            raise CuratorError("artifact curator archive IDs are invalid")
        if tuple(sorted(set(self.archive_ids))) != self.archive_ids:
            raise CuratorError("artifact curator archive IDs are not canonical")
        for archive_id in self.archive_ids:
            _digest_value(archive_id, "archive ID")
        if self.state is CurationState.ARCHIVED and not self.archive_ids:
            raise CuratorError("archived curator row requires an archive ID")

    def to_dict(self) -> dict[str, object]:
        return {
            "workflow_id": self.workflow_id,
            "state": self.state.value,
            "first_terminal_observed_at": (
                self.first_terminal_observed_at.isoformat()
                if self.first_terminal_observed_at
                else None
            ),
            "last_transition_at": self.last_transition_at.isoformat(),
            "pinned": self.pinned,
            "archive_ids": list(self.archive_ids),
        }

    @classmethod
    def from_dict(cls, raw: object) -> CurationRow:
        if not isinstance(raw, dict) or set(raw) != {
            "workflow_id",
            "state",
            "first_terminal_observed_at",
            "last_transition_at",
            "pinned",
            "archive_ids",
        }:
            raise CuratorError("artifact curator row schema is invalid")
        try:
            observed = raw["first_terminal_observed_at"]
            archive_ids = raw["archive_ids"]
            if not isinstance(archive_ids, list):
                raise TypeError
            return cls(
                workflow_id=raw["workflow_id"],
                state=CurationState(raw["state"]),
                first_terminal_observed_at=(
                    datetime.fromisoformat(observed) if observed is not None else None
                ),
                last_transition_at=datetime.fromisoformat(raw["last_transition_at"]),
                pinned=raw["pinned"],
                archive_ids=tuple(archive_ids),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise CuratorError("artifact curator row schema is invalid") from error


@dataclass(frozen=True)
class CuratorDocument:
    policy: CuratorPolicy = CuratorPolicy()
    rows: tuple[CurationRow, ...] = ()
    schema: str = _STATE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != _STATE_SCHEMA or not isinstance(self.rows, tuple):
            raise CuratorError("artifact curator state schema is invalid")
        if len(self.rows) > _MAX_ROWS or any(not isinstance(row, CurationRow) for row in self.rows):
            raise CuratorError("artifact curator state rows are invalid")
        workflow_ids = tuple(row.workflow_id for row in self.rows)
        if workflow_ids != tuple(sorted(workflow_ids)) or len(set(workflow_ids)) != len(
            workflow_ids
        ):
            raise CuratorError("artifact curator state rows are not canonical")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "policy": self.policy.to_dict(),
            "rows": [row.to_dict() for row in self.rows],
        }

    def canonical_bytes(self) -> bytes:
        content = _canonical(self.to_dict()) + b"\n"
        if len(content) > _MAX_STATE_BYTES:
            raise CuratorError("artifact curator state exceeds its document bound")
        return content

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    @classmethod
    def from_dict(cls, raw: object) -> CuratorDocument:
        if (
            not isinstance(raw, dict)
            or set(raw) != {"schema", "policy", "rows"}
            or raw["schema"] != _STATE_SCHEMA
            or not isinstance(raw["rows"], list)
        ):
            raise CuratorError("artifact curator state schema is invalid")
        return cls(
            schema=raw["schema"],
            policy=CuratorPolicy.from_dict(raw["policy"]),
            rows=tuple(CurationRow.from_dict(row) for row in raw["rows"]),
        )


class ArtifactCuratorStore:
    """Strict mode-0600 compare-and-swap state document."""

    def __init__(self, data_root: Path) -> None:
        root = Path(data_root)
        if not root.is_absolute() or root.resolve() != root:
            raise CuratorError("artifact curator root must be absolute and resolved")
        self.path = root / _STATE_FILENAME

    def read(self) -> CuratorDocument:
        try:
            content = read_private_text(
                self.path,
                maximum_bytes=_MAX_STATE_BYTES,
                label="artifact curator state",
            )
        except FileNotFoundError:
            return CuratorDocument()
        except ProfileFileError as error:
            raise CuratorError("artifact curator state is unavailable") from error
        try:
            raw = json.loads(content, object_pairs_hook=_reject_duplicate_keys)
            return CuratorDocument.from_dict(raw)
        except (json.JSONDecodeError, CuratorError) as error:
            raise CuratorError("artifact curator state schema is invalid") from error

    def replace(self, document: CuratorDocument, *, expected_digest: str) -> CuratorDocument:
        if not isinstance(document, CuratorDocument):
            raise CuratorError("artifact curator state is invalid")
        _digest_value(expected_digest, "state digest")
        current = self.read()
        if current.digest != expected_digest:
            raise CuratorError("artifact curator state was modified concurrently")
        content = document.canonical_bytes().decode("utf-8")
        if document == current:
            return current
        try:
            atomic_write_private_text(
                self.path,
                content,
                label="artifact curator state",
            )
        except ProfileFileError as error:
            raise CuratorError("artifact curator state cannot be replaced") from error
        return document


@dataclass(frozen=True, order=True)
class CuratedArchiveMember:
    path: str
    size: int
    sha256: str
    artifact_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _member_path(self.path)
        if isinstance(self.size, bool) or not isinstance(self.size, int) or self.size < 0:
            raise CuratorError("artifact archive member is invalid")
        _digest_value(self.sha256, "artifact archive member digest")
        if not isinstance(self.artifact_ids, tuple):
            raise CuratorError("artifact archive member identities are invalid")
        if self.artifact_ids != tuple(sorted(set(self.artifact_ids))):
            raise CuratorError("artifact archive member identities are not canonical")
        for artifact_id in self.artifact_ids:
            _digest_value(artifact_id, "artifact ID")

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "size": self.size,
            "sha256": self.sha256,
            "artifact_ids": list(self.artifact_ids),
            "ledger_evidence": bool(self.artifact_ids),
        }

    @classmethod
    def from_dict(cls, raw: object) -> CuratedArchiveMember:
        if not isinstance(raw, dict) or set(raw) != {
            "path",
            "size",
            "sha256",
            "artifact_ids",
            "ledger_evidence",
        }:
            raise CuratorError("artifact archive member schema is invalid")
        artifact_ids = raw["artifact_ids"]
        if not isinstance(artifact_ids, list) or raw["ledger_evidence"] is not bool(artifact_ids):
            raise CuratorError("artifact archive member schema is invalid")
        try:
            return cls(
                path=raw["path"],
                size=raw["size"],
                sha256=raw["sha256"],
                artifact_ids=tuple(artifact_ids),
            )
        except TypeError as error:
            raise CuratorError("artifact archive member schema is invalid") from error


@dataclass(frozen=True)
class CuratedArchiveManifest:
    archive_id: str
    workflow_id: str
    ledger_token: str
    created_at: datetime
    archive_sha256: str
    archive_size: int
    integrity_manifest_sha256: str
    members: tuple[CuratedArchiveMember, ...]
    schema: str = _ARCHIVE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != _ARCHIVE_SCHEMA:
            raise CuratorError("artifact archive manifest schema is invalid")
        _digest_value(self.archive_id, "archive ID")
        _workflow_id(self.workflow_id)
        _text(self.ledger_token, "ledger update token")
        _aware(self.created_at, "archive creation time")
        _digest_value(self.archive_sha256, "archive digest")
        _digest_value(self.integrity_manifest_sha256, "archive manifest digest")
        if (
            isinstance(self.archive_size, bool)
            or not isinstance(self.archive_size, int)
            or self.archive_size < 0
            or not isinstance(self.members, tuple)
            or not self.members
        ):
            raise CuratorError("artifact archive manifest is invalid")
        if self.members != tuple(sorted(self.members)):
            raise CuratorError("artifact archive manifest members are not canonical")
        paths = tuple(member.path for member in self.members)
        if len(paths) != len(set(paths)):
            raise CuratorError("artifact archive manifest members are duplicated")
        if self.archive_id != _archive_identity(
            self.workflow_id, self.ledger_token, self.members
        ):
            raise CuratorError("artifact archive manifest identity is invalid")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "archive_id": self.archive_id,
            "workflow_id": self.workflow_id,
            "ledger_token": self.ledger_token,
            "created_at": self.created_at.isoformat(),
            "archive_sha256": self.archive_sha256,
            "archive_size": self.archive_size,
            "integrity_manifest_sha256": self.integrity_manifest_sha256,
            "members": [member.to_dict() for member in self.members],
        }

    @classmethod
    def from_dict(cls, raw: object) -> CuratedArchiveManifest:
        expected = {
            "schema",
            "archive_id",
            "workflow_id",
            "ledger_token",
            "created_at",
            "archive_sha256",
            "archive_size",
            "integrity_manifest_sha256",
            "members",
        }
        if not isinstance(raw, dict) or set(raw) != expected or not isinstance(
            raw["members"], list
        ):
            raise CuratorError("artifact archive manifest schema is invalid")
        try:
            return cls(
                schema=raw["schema"],
                archive_id=raw["archive_id"],
                workflow_id=raw["workflow_id"],
                ledger_token=raw["ledger_token"],
                created_at=datetime.fromisoformat(raw["created_at"]),
                archive_sha256=raw["archive_sha256"],
                archive_size=raw["archive_size"],
                integrity_manifest_sha256=raw["integrity_manifest_sha256"],
                members=tuple(CuratedArchiveMember.from_dict(row) for row in raw["members"]),
            )
        except (TypeError, ValueError) as error:
            raise CuratorError("artifact archive manifest schema is invalid") from error


@dataclass(frozen=True)
class CurationAction:
    workflow_id: str
    action: str
    ledger_token: str
    from_state: CurationState | None
    to_state: CurationState
    archive_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "workflow_id": self.workflow_id,
            "action": self.action,
            "ledger_token": self.ledger_token,
            "from_state": self.from_state.value if self.from_state else None,
            "to_state": self.to_state.value,
            "archive_id": self.archive_id,
        }


@dataclass(frozen=True)
class CuratorPreview:
    operation: str
    state_digest: str
    actions: tuple[CurationAction, ...]
    workflow_id: str | None = None
    archive_id: str | None = None

    def _identity(self) -> dict[str, object]:
        return {
            "schema": "daidala.artifact-curator-preview/v1",
            "operation": self.operation,
            "state_digest": self.state_digest,
            "workflow_id": self.workflow_id,
            "archive_id": self.archive_id,
            "actions": [action.to_dict() for action in self.actions],
        }

    @property
    def digest(self) -> str:
        return hashlib.sha256(_canonical(self._identity())).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return {**self._identity(), "preview_digest": self.digest}


@dataclass(frozen=True)
class CuratorResult:
    operation: str
    workflow_id: str | None
    archive_id: str | None
    transitioned: int = 0
    archived_files: int = 0
    restored_files: int = 0
    replayed: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "operation": self.operation,
            "workflow_id": self.workflow_id,
            "archive_id": self.archive_id,
            "transitioned": self.transitioned,
            "archived_files": self.archived_files,
            "restored_files": self.restored_files,
            "replayed": self.replayed,
        }


@dataclass(frozen=True)
class CuratorStatus:
    policy: CuratorPolicy
    rows: tuple[CurationRow, ...]
    state_digest: str

    def to_dict(self) -> dict[str, object]:
        counts = {state.value: 0 for state in CurationState}
        for row in self.rows:
            counts[row.state.value] += 1
        return {
            "policy": self.policy.to_dict(),
            "state_digest": self.state_digest,
            "counts": counts,
            "pinned": sum(row.pinned for row in self.rows),
            "rows": [row.to_dict() for row in self.rows],
        }


@dataclass(frozen=True)
class _ArchivePlan:
    archive_id: str
    workflow_id: str
    ledger_token: str
    members: tuple[CuratedArchiveMember, ...]


class ArtifactCurator:
    """Classify, archive, restore, and recover workflow artifacts deterministically."""

    def __init__(
        self,
        store: WorkflowStore,
        *,
        clock: Callable[[], datetime] | None = None,
        status_provider: StatusProvider | None = None,
        fault_injector: FaultInjector | None = None,
    ) -> None:
        self.store = store
        self.data_root = store.data_root.resolve()
        self.state_store = ArtifactCuratorStore(self.data_root)
        self.clock = clock or (lambda: datetime.now(UTC))
        self.status_provider = status_provider
        self.fault_injector = fault_injector or (lambda _boundary: None)
        self._active_access = ArtifactAccessService(store)
        self._manifest_cache: dict[
            tuple[str, str],
            tuple[tuple[tuple[int, ...], ...], CuratedArchiveManifest],
        ] = {}
        self.lock_path = self.data_root / ".artifact-curator.lock"

    def status(self) -> CuratorStatus:
        document = self.state_store.read()
        return CuratorStatus(document.policy, document.rows, document.digest)

    def configure(
        self, policy: CuratorPolicy, *, expected_state_digest: str
    ) -> CuratorStatus:
        with _exclusive_lock(self.lock_path):
            current = self.state_store.read()
            updated = self.state_store.replace(
                replace(current, policy=policy),
                expected_digest=expected_state_digest,
            )
        return CuratorStatus(updated.policy, updated.rows, updated.digest)

    def preview_run(self) -> CuratorPreview:
        document = self.state_store.read()
        rows = {row.workflow_id: row for row in document.rows}
        actions: list[CurationAction] = []
        for ledger in self.store.list_all():
            _workflow_id(ledger.workflow_id)
            observed = self.store.get_with_token(ledger.workflow_id)
            ledger = observed.ledger
            row = rows.get(ledger.workflow_id)
            if not self._terminal_eligible(ledger):
                continue
            if row is not None and row.state is CurationState.ARCHIVED:
                manifest = self._latest_archive(row)
                if self._has_active_sources(ledger.workflow_id, manifest):
                    if manifest.ledger_token != observed.updated_at:
                        try:
                            archive_plan = self._archive_plan(ledger, observed.updated_at)
                        except CuratorError:
                            continue
                        actions.append(
                            CurationAction(
                                ledger.workflow_id,
                                "archive",
                                observed.updated_at,
                                row.state,
                                CurationState.ARCHIVED,
                                archive_plan.archive_id,
                            )
                        )
                        continue
                    actions.append(
                        CurationAction(
                            ledger.workflow_id,
                            "recover",
                            observed.updated_at,
                            row.state,
                            CurationState.ARCHIVED,
                            manifest.archive_id,
                        )
                    )
                continue
            if not document.policy.enabled or (row is not None and row.pinned):
                continue
            try:
                archive_plan = self._archive_plan(ledger, observed.updated_at)
            except CuratorError:
                continue
            if row is None or row.first_terminal_observed_at is None:
                actions.append(
                    CurationAction(
                        ledger.workflow_id,
                        "observe",
                        observed.updated_at,
                        row.state if row else None,
                        CurationState.ACTIVE,
                    )
                )
                continue
            age = self.clock() - row.first_terminal_observed_at
            if age >= timedelta(days=document.policy.archive_after_days):
                actions.append(
                    CurationAction(
                        ledger.workflow_id,
                        "archive",
                        observed.updated_at,
                        row.state,
                        CurationState.ARCHIVED,
                        archive_plan.archive_id,
                    )
                )
            elif (
                age >= timedelta(days=document.policy.stale_after_days)
                and row.state is CurationState.ACTIVE
            ):
                actions.append(
                    CurationAction(
                        ledger.workflow_id,
                        "mark-stale",
                        observed.updated_at,
                        row.state,
                        CurationState.STALE,
                    )
                )
        return CuratorPreview("run", document.digest, tuple(actions))

    def apply_run(self, *, expected_preview_digest: str) -> CuratorResult:
        with _exclusive_lock(self.lock_path):
            preview = self.preview_run()
            self._require_preview(preview, expected_preview_digest)
            transitioned = 0
            archived_files = 0
            for action in preview.actions:
                with _exclusive_lock(self._workflow_lock(action.workflow_id)):
                    if action.action in {"observe", "mark-stale"}:
                        self._apply_transition(action)
                        transitioned += 1
                    else:
                        result = self._apply_archive_action(action)
                        transitioned += result.transitioned
                        archived_files += result.archived_files
            return CuratorResult(
                operation="run",
                workflow_id=None,
                archive_id=None,
                transitioned=transitioned,
                archived_files=archived_files,
                replayed=not preview.actions,
            )

    def preview_pin(self, workflow_id: str, *, pinned: bool) -> CuratorPreview:
        if not isinstance(pinned, bool):
            raise CuratorError("artifact curator pin value is invalid")
        observed = self._observed(workflow_id)
        document = self.state_store.read()
        row = self._row(document, workflow_id)
        operation = "pin" if pinned else "unpin"
        actions = ()
        if row is None or row.pinned is not pinned:
            actions = (
                CurationAction(
                    workflow_id,
                    operation,
                    observed.updated_at,
                    row.state if row else None,
                    row.state if row else CurationState.ACTIVE,
                ),
            )
        return CuratorPreview(operation, document.digest, actions, workflow_id=workflow_id)

    def apply_pin(
        self,
        workflow_id: str,
        *,
        pinned: bool,
        expected_preview_digest: str,
    ) -> CuratorResult:
        with _exclusive_lock(self.lock_path):
            with _exclusive_lock(self._workflow_lock(workflow_id)):
                preview = self.preview_pin(workflow_id, pinned=pinned)
                self._require_preview(preview, expected_preview_digest)
                if not preview.actions:
                    return CuratorResult(preview.operation, workflow_id, None, replayed=True)
                action = preview.actions[0]
                observed = self._observed(workflow_id)
                if observed.updated_at != action.ledger_token:
                    raise CuratorError("workflow ledger changed after curator preview")
                document = self.state_store.read()
                row = self._row(document, workflow_id)
                now = self.clock()
                updated = (
                    replace(row, pinned=pinned, last_transition_at=now)
                    if row is not None
                    else CurationRow(
                        workflow_id=workflow_id,
                        state=CurationState.ACTIVE,
                        first_terminal_observed_at=None,
                        last_transition_at=now,
                        pinned=pinned,
                    )
                )
                self._replace_row(document, updated)
                return CuratorResult(preview.operation, workflow_id, None, transitioned=1)

    def preview_archive(self, workflow_id: str) -> CuratorPreview:
        observed = self._observed(workflow_id)
        if not self._terminal_eligible(observed.ledger):
            raise CuratorError("workflow is not safely terminal for artifact curation")
        document = self.state_store.read()
        row = self._row(document, workflow_id)
        if row is not None and row.state is CurationState.ARCHIVED:
            manifest = self._latest_archive(row)
            if (
                manifest.ledger_token != observed.updated_at
                and self._has_active_sources(workflow_id, manifest)
            ):
                plan = self._archive_plan(observed.ledger, observed.updated_at)
                action = CurationAction(
                    workflow_id,
                    "archive",
                    observed.updated_at,
                    row.state,
                    CurationState.ARCHIVED,
                    plan.archive_id,
                )
                return CuratorPreview(
                    "archive",
                    document.digest,
                    (action,),
                    workflow_id=workflow_id,
                    archive_id=plan.archive_id,
                )
            archive_id = manifest.archive_id
            actions = ()
            if self._has_active_sources(workflow_id, manifest):
                actions = (
                    CurationAction(
                        workflow_id,
                        "recover",
                        observed.updated_at,
                        row.state,
                        CurationState.ARCHIVED,
                        archive_id,
                    ),
                )
            return CuratorPreview(
                "archive",
                document.digest,
                actions,
                workflow_id=workflow_id,
                archive_id=archive_id,
            )
        plan = self._archive_plan(observed.ledger, observed.updated_at)
        action = CurationAction(
            workflow_id,
            "archive",
            observed.updated_at,
            row.state if row else None,
            CurationState.ARCHIVED,
            plan.archive_id,
        )
        return CuratorPreview(
            "archive",
            document.digest,
            (action,),
            workflow_id=workflow_id,
            archive_id=plan.archive_id,
        )

    def apply_archive(
        self, workflow_id: str, *, expected_preview_digest: str
    ) -> CuratorResult:
        with _exclusive_lock(self.lock_path):
            preview = self.preview_archive(workflow_id)
            self._require_preview(preview, expected_preview_digest)
            if not preview.actions:
                return CuratorResult(
                    "archive", workflow_id, preview.archive_id, replayed=True
                )
            with _exclusive_lock(self._workflow_lock(workflow_id)):
                return self._apply_archive_action(preview.actions[0])

    def list_archived(self) -> tuple[dict[str, object], ...]:
        document = self.state_store.read()
        results = []
        for row in document.rows:
            for archive_id in row.archive_ids:
                manifest = self._read_archive_manifest(row.workflow_id, archive_id)
                results.append(
                    {
                        "workflow_id": row.workflow_id,
                        "archive_id": archive_id,
                        "created_at": manifest.created_at.isoformat(),
                        "archive_digest": manifest.archive_sha256,
                        "member_count": len(manifest.members),
                        "ledger_evidence_count": sum(
                            bool(member.artifact_ids) for member in manifest.members
                        ),
                    }
                )
        return tuple(results)

    def preview_restore(self, workflow_id: str, archive_id: str) -> CuratorPreview:
        _digest_value(archive_id, "archive ID")
        document = self.state_store.read()
        row = self._row(document, workflow_id)
        if row is None or archive_id not in row.archive_ids:
            raise CuratorError("artifact archive is not bound to this workflow")
        observed = self._observed(workflow_id)
        self._read_archive_manifest(workflow_id, archive_id)
        action = CurationAction(
            workflow_id,
            "restore",
            observed.updated_at,
            row.state,
            CurationState.ACTIVE,
            archive_id,
        )
        return CuratorPreview(
            "restore",
            document.digest,
            (action,),
            workflow_id=workflow_id,
            archive_id=archive_id,
        )

    def apply_restore(
        self,
        workflow_id: str,
        archive_id: str,
        *,
        expected_preview_digest: str,
    ) -> CuratorResult:
        with _exclusive_lock(self.lock_path):
            preview = self.preview_restore(workflow_id, archive_id)
            self._require_preview(preview, expected_preview_digest)
            with _exclusive_lock(self._workflow_lock(workflow_id)):
                manifest = self._read_archive_manifest(workflow_id, archive_id)
                archive, integrity, _curation = self._archive_paths(workflow_id, archive_id)
                destination = self.data_root / "artifact-restores" / workflow_id / archive_id
                try:
                    restored = restore_archive(archive, integrity, destination)
                except ArchiveError as error:
                    raise CuratorError("artifact archive restore failed") from error
                if len(restored.members) != len(manifest.members):
                    raise CuratorError("artifact archive restore failed")
                reobserved = self._observed(workflow_id)
                if reobserved.updated_at != preview.actions[0].ledger_token:
                    raise CuratorError("workflow changed during artifact restore")
                document = self.state_store.read()
                row = self._row(document, workflow_id)
                if row is None or archive_id not in row.archive_ids:
                    raise CuratorError("artifact archive state changed during restore")
                updated = replace(
                    row,
                    state=CurationState.ACTIVE,
                    pinned=True,
                    last_transition_at=self.clock(),
                )
                self._replace_row(document, updated)
                return CuratorResult(
                    "restore",
                    workflow_id,
                    archive_id,
                    transitioned=1,
                    restored_files=len(manifest.members),
                )

    def archive_lookup(
        self, workflow_id: str, artifact_id: ArtifactId
    ) -> ArchivedArtifactSource | None:
        if not isinstance(artifact_id, ArtifactId):
            raise CuratorError("artifact archive lookup identity is invalid")
        row = self._row(self.state_store.read(), workflow_id)
        if row is None:
            return None
        matches: list[
            tuple[datetime, str, str, ArchivedArtifactSource]
        ] = []
        for archive_id in row.archive_ids:
            manifest = self._read_archive_manifest(workflow_id, archive_id)
            for member in manifest.members:
                if str(artifact_id) in member.artifact_ids:
                    archive, integrity, _curation = self._archive_paths(
                        workflow_id, archive_id
                    )
                    matches.append(
                        (
                            manifest.created_at,
                            archive_id,
                            member.sha256,
                            ArchivedArtifactSource(archive, integrity, member.path),
                        )
                    )
        if len({digest for _created, _archive, digest, _source in matches}) > 1:
            raise CuratorError("artifact archive lookup is ambiguous")
        if not matches:
            return None
        return max(matches, key=lambda match: (match[0], match[1]))[3]

    def _apply_transition(self, action: CurationAction) -> None:
        observed = self._observed(action.workflow_id)
        if observed.updated_at != action.ledger_token or not self._terminal_eligible(
            observed.ledger
        ):
            raise CuratorError("workflow changed after curator preview")
        self._archive_plan(observed.ledger, observed.updated_at)
        document = self.state_store.read()
        row = self._row(document, action.workflow_id)
        now = self.clock()
        if action.action == "observe":
            updated = (
                CurationRow(
                    workflow_id=action.workflow_id,
                    state=CurationState.ACTIVE,
                    first_terminal_observed_at=now,
                    last_transition_at=now,
                    pinned=False,
                )
                if row is None
                else replace(
                    row,
                    state=CurationState.ACTIVE,
                    first_terminal_observed_at=now,
                    last_transition_at=now,
                )
            )
        elif action.action == "mark-stale" and row is not None:
            updated = replace(row, state=CurationState.STALE, last_transition_at=now)
        else:
            raise CuratorError("artifact curator transition is stale")
        self._replace_row(document, updated)

    def _apply_archive_action(self, action: CurationAction) -> CuratorResult:
        archive_id = action.archive_id
        if archive_id is None:
            raise CuratorError("artifact archive preview omitted its identity")
        if action.action == "recover":
            manifest = self._read_archive_manifest(action.workflow_id, archive_id)
            removed = self._finish_cleanup(manifest)
            return CuratorResult(
                "archive",
                action.workflow_id,
                archive_id,
                archived_files=len(manifest.members),
                replayed=removed == 0,
            )
        observed = self._observed(action.workflow_id)
        if observed.updated_at != action.ledger_token or not self._terminal_eligible(
            observed.ledger
        ):
            raise CuratorError("workflow changed after curator preview")
        plan = self._archive_plan(observed.ledger, observed.updated_at)
        if plan.archive_id != archive_id:
            raise CuratorError("artifact archive preview is stale")
        archive, integrity, curation = self._archive_paths(action.workflow_id, archive_id)
        try:
            created = create_archive(
                self._artifact_root(action.workflow_id),
                (member.path for member in plan.members),
                archive,
                integrity,
            )
        except ArchiveError as error:
            raise CuratorError("artifact archive creation failed") from error
        self.fault_injector("after-archive-publish")
        manifest = CuratedArchiveManifest(
            archive_id=archive_id,
            workflow_id=action.workflow_id,
            ledger_token=action.ledger_token,
            created_at=self._existing_archive_time(curation) or self.clock(),
            archive_sha256=created.manifest.archive_sha256,
            archive_size=created.manifest.archive_size,
            integrity_manifest_sha256=_file_digest(integrity)[0],
            members=plan.members,
        )
        self._write_archive_manifest(curation, manifest)
        self.fault_injector("after-manifest-publish")
        reobserved = self._observed(action.workflow_id)
        if reobserved.updated_at != action.ledger_token or not self._terminal_eligible(
            reobserved.ledger
        ):
            raise CuratorError("workflow changed before archive publication")
        document = self.state_store.read()
        row = self._row(document, action.workflow_id)
        now = self.clock()
        archive_ids = tuple(sorted({*(row.archive_ids if row else ()), archive_id}))
        updated = CurationRow(
            workflow_id=action.workflow_id,
            state=CurationState.ARCHIVED,
            first_terminal_observed_at=(
                row.first_terminal_observed_at if row and row.first_terminal_observed_at else now
            ),
            last_transition_at=now,
            pinned=row.pinned if row else False,
            archive_ids=archive_ids,
        )
        self._replace_row(document, updated)
        self.fault_injector("after-state-publish")
        self._finish_cleanup(manifest)
        return CuratorResult(
            "archive",
            action.workflow_id,
            archive_id,
            transitioned=1,
            archived_files=len(manifest.members),
        )

    def _finish_cleanup(self, manifest: CuratedArchiveManifest) -> int:
        verified = self._read_archive_manifest(manifest.workflow_id, manifest.archive_id)
        observed = self._observed(manifest.workflow_id)
        if observed.updated_at != manifest.ledger_token or not self._terminal_eligible(
            observed.ledger
        ):
            raise CuratorError("workflow changed before artifact cleanup")
        root = self._artifact_root(manifest.workflow_id)
        removed = 0
        for member in verified.members:
            path = root / member.path
            try:
                metadata = path.lstat()
            except FileNotFoundError:
                continue
            except OSError as error:
                raise CuratorError("artifact archive cleanup failed") from error
            if (
                stat.S_ISLNK(metadata.st_mode)
                or not stat.S_ISREG(metadata.st_mode)
                or metadata.st_nlink != 1
            ):
                raise CuratorError("artifact archive cleanup blocked by source drift")
            digest, size = _file_digest(path, expected=metadata)
            if digest != member.sha256 or size != member.size:
                raise CuratorError("artifact archive cleanup blocked by source drift")
            try:
                current = path.lstat()
                if _file_identity(current) != _file_identity(metadata):
                    raise CuratorError("artifact archive cleanup blocked by source drift")
                path.unlink()
            except CuratorError:
                raise
            except OSError as error:
                raise CuratorError("artifact archive cleanup failed") from error
            removed += 1
            self.fault_injector("after-source-remove")
        self._remove_empty_directories(root)
        return removed

    def _archive_plan(self, ledger: WorkflowLedger, ledger_token: str) -> _ArchivePlan:
        root = self._artifact_root(ledger.workflow_id)
        inventory = _source_inventory(root)
        try:
            bindings = self._active_access.archive_bindings(
                ledger.workflow_id, ledger=ledger
            )
        except (ArtifactAccessError, StoreError) as error:
            raise CuratorError("ledger artifact inventory is unavailable") from error
        ids_by_path: dict[str, list[str]] = {}
        for binding in bindings:
            source = inventory.get(binding.member_path)
            if source is None or source[1] != binding.digest:
                raise CuratorError("ledger artifact inventory is incomplete")
            ids_by_path.setdefault(binding.member_path, []).append(str(binding.artifact_id))
        members = tuple(
            CuratedArchiveMember(
                path=path,
                size=size,
                sha256=digest,
                artifact_ids=tuple(sorted(ids_by_path.get(path, ()))),
            )
            for path, (size, digest) in sorted(inventory.items())
        )
        archive_id = _archive_identity(ledger.workflow_id, ledger_token, members)
        return _ArchivePlan(archive_id, ledger.workflow_id, ledger_token, members)

    def _read_archive_manifest(
        self, workflow_id: str, archive_id: str
    ) -> CuratedArchiveManifest:
        archive, integrity, curation = self._archive_paths(workflow_id, archive_id)
        try:
            fingerprint = tuple(
                _path_fingerprint(path) for path in (archive, integrity, curation)
            )
            cached = self._manifest_cache.get((workflow_id, archive_id))
            if cached is not None and cached[0] == fingerprint:
                return cached[1]
            content = read_private_text(
                curation,
                maximum_bytes=_MAX_ARCHIVE_MANIFEST_BYTES,
                label="artifact archive manifest",
            )
            raw = json.loads(content, object_pairs_hook=_reject_duplicate_keys)
            manifest = CuratedArchiveManifest.from_dict(raw)
            verified = verify_archive(archive, integrity)
            integrity_digest, _size = _file_digest(integrity)
            if fingerprint != tuple(
                _path_fingerprint(path) for path in (archive, integrity, curation)
            ):
                raise CuratorError("artifact archive changed during verification")
        except (
            FileNotFoundError,
            ProfileFileError,
            json.JSONDecodeError,
            CuratorError,
            ArchiveError,
            OSError,
        ) as error:
            raise CuratorError("artifact archive manifest cannot be verified") from error
        if manifest.workflow_id != workflow_id or manifest.archive_id != archive_id:
            raise CuratorError("artifact archive manifest identity is invalid")
        if (
            manifest.archive_sha256 != verified.archive_sha256
            or manifest.archive_size != verified.archive_size
            or manifest.integrity_manifest_sha256 != integrity_digest
            or tuple((row.path, row.size, row.sha256) for row in manifest.members)
            != tuple((row.path, row.size, row.sha256) for row in verified.members)
        ):
            raise CuratorError("artifact archive manifest cannot be verified")
        if len(self._manifest_cache) >= 32:
            self._manifest_cache.pop(next(iter(self._manifest_cache)))
        self._manifest_cache[(workflow_id, archive_id)] = (fingerprint, manifest)
        return manifest

    def _write_archive_manifest(
        self, path: Path, manifest: CuratedArchiveManifest
    ) -> None:
        content = (_canonical(manifest.to_dict()) + b"\n").decode("utf-8")
        if len(content.encode("utf-8")) > _MAX_ARCHIVE_MANIFEST_BYTES:
            raise CuratorError("artifact archive manifest exceeds its document bound")
        try:
            existing = read_private_text(
                path,
                maximum_bytes=_MAX_ARCHIVE_MANIFEST_BYTES,
                label="artifact archive manifest",
            )
        except FileNotFoundError:
            existing = None
        except ProfileFileError as error:
            raise CuratorError("artifact archive manifest is unavailable") from error
        if existing is not None and existing != content:
            raise CuratorError("artifact archive manifest conflicts with published state")
        if existing is None:
            try:
                atomic_write_private_text(path, content, label="artifact archive manifest")
            except ProfileFileError as error:
                raise CuratorError("artifact archive manifest cannot be published") from error

    def _existing_archive_time(self, path: Path) -> datetime | None:
        if not path.exists():
            return None
        try:
            content = read_private_text(
                path,
                maximum_bytes=_MAX_ARCHIVE_MANIFEST_BYTES,
                label="artifact archive manifest",
            )
            raw = json.loads(content, object_pairs_hook=_reject_duplicate_keys)
            return CuratedArchiveManifest.from_dict(raw).created_at
        except (
            ProfileFileError,
            json.JSONDecodeError,
            CuratorError,
            OSError,
        ) as error:
            raise CuratorError("artifact archive manifest is unavailable") from error

    def _terminal_eligible(self, ledger: WorkflowLedger) -> bool:
        if ledger.worktree_owned or ledger.worktree_path is not None:
            return False
        if ledger.pending_revision_request is not None:
            return False
        if ledger.artifact_for(WorkflowStage.DELIVER) is not None:
            return True
        if not ledger.card_references or self.status_provider is None:
            return False
        try:
            statuses = self.status_provider(ledger)
        except Exception:  # noqa: BLE001 - unavailable host state fails closed
            return False
        if not isinstance(statuses, tuple) or any(
            not isinstance(status, KanbanCardStatus) for status in statuses
        ):
            return False
        expected = {card.task_id for card in ledger.card_references}
        actual = {status.task_id for status in statuses}
        if actual != expected or any(
            status.status not in _TERMINAL_CARD_STATES for status in statuses
        ):
            return False
        return ledger.approval is not None or all(
            status.status == "archived" for status in statuses
        )

    def _replace_row(self, document: CuratorDocument, row: CurationRow) -> CuratorDocument:
        rows = {current.workflow_id: current for current in document.rows}
        rows[row.workflow_id] = row
        updated = replace(document, rows=tuple(rows[key] for key in sorted(rows)))
        return self.state_store.replace(updated, expected_digest=document.digest)

    @staticmethod
    def _row(document: CuratorDocument, workflow_id: str) -> CurationRow | None:
        return next((row for row in document.rows if row.workflow_id == workflow_id), None)

    def _latest_archive(self, row: CurationRow) -> CuratedArchiveManifest:
        manifests = tuple(
            self._read_archive_manifest(row.workflow_id, archive_id)
            for archive_id in row.archive_ids
        )
        if not manifests:
            raise CuratorError("archived workflow has no published artifact archive")
        return max(manifests, key=lambda manifest: (manifest.created_at, manifest.archive_id))

    def _observed(self, workflow_id: str):
        _workflow_id(workflow_id)
        try:
            return self.store.get_with_token(workflow_id)
        except StoreError as error:
            raise CuratorError("workflow is unavailable") from error

    @staticmethod
    def _require_preview(preview: CuratorPreview, expected_digest: str) -> None:
        _digest_value(expected_digest, "curator preview digest")
        if preview.digest != expected_digest:
            raise CuratorError("artifact curator preview is stale")

    def _artifact_root(self, workflow_id: str) -> Path:
        _workflow_id(workflow_id)
        return self.data_root / "workflows" / workflow_id / "artifacts"

    def _archive_paths(self, workflow_id: str, archive_id: str) -> tuple[Path, Path, Path]:
        _workflow_id(workflow_id)
        _digest_value(archive_id, "archive ID")
        directory = self.data_root / "artifact-archives" / workflow_id
        return (
            directory / f"{archive_id}.tar.gz",
            directory / f"{archive_id}.archive-manifest.json",
            directory / f"{archive_id}.manifest.json",
        )

    def _workflow_lock(self, workflow_id: str) -> Path:
        _workflow_id(workflow_id)
        identity = hashlib.sha256(workflow_id.encode("utf-8")).hexdigest()
        return self.data_root / f".artifact-curator-{identity}.lock"

    def _has_active_sources(
        self, workflow_id: str, manifest: CuratedArchiveManifest
    ) -> bool:
        root = self._artifact_root(workflow_id)
        return any((root / member.path).exists() for member in manifest.members)

    @staticmethod
    def _remove_empty_directories(root: Path) -> None:
        if not root.is_dir():
            return
        directories = sorted(
            (path for path in root.rglob("*") if path.is_dir()),
            key=lambda path: len(path.parts),
            reverse=True,
        )
        for directory in directories:
            try:
                directory.rmdir()
            except OSError:
                pass


@contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(
            path,
            os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
    except OSError as error:
        raise CuratorError("artifact curator lock is unsafe") from error
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise CuratorError("artifact curator lock is unsafe")
        os.fchmod(descriptor, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise CuratorError("artifact curator lock contention") from error
        yield
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def _source_inventory(root: Path) -> dict[str, tuple[int, str]]:
    try:
        metadata = root.lstat()
    except OSError as error:
        raise CuratorError("workflow artifact inventory is unavailable") from error
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise CuratorError("workflow artifact inventory is unsafe")
    inventory: dict[str, tuple[int, str]] = {}
    try:
        for directory, names, filenames in os.walk(root, topdown=True, followlinks=False):
            current = Path(directory)
            for name in names:
                child = current / name
                details = child.lstat()
                if stat.S_ISLNK(details.st_mode) or not stat.S_ISDIR(details.st_mode):
                    raise CuratorError("workflow artifact inventory is unsafe")
            for name in filenames:
                child = current / name
                details = child.lstat()
                if (
                    stat.S_ISLNK(details.st_mode)
                    or not stat.S_ISREG(details.st_mode)
                    or details.st_nlink != 1
                ):
                    raise CuratorError("workflow artifact inventory is unsafe")
                relative = child.relative_to(root).as_posix()
                _member_path(relative)
                digest, size = _file_digest(child)
                inventory[relative] = (size, digest)
    except CuratorError:
        raise
    except OSError as error:
        raise CuratorError("workflow artifact inventory is unavailable") from error
    if not inventory:
        raise CuratorError("workflow artifact inventory is empty")
    return inventory


def _file_digest(
    path: Path, *, expected: os.stat_result | None = None
) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as stream:
            initial = os.fstat(stream.fileno())
            if not stat.S_ISREG(initial.st_mode) or initial.st_nlink != 1:
                raise CuratorError("private file is unsafe")
            if expected is not None and _file_identity(initial) != _file_identity(expected):
                raise CuratorError("private file changed during verification")
            while chunk := stream.read(64 * 1024):
                size += len(chunk)
                digest.update(chunk)
            final = os.fstat(stream.fileno())
            if _file_identity(initial) != _file_identity(final) or final.st_size != size:
                raise CuratorError("private file changed during verification")
    except CuratorError:
        raise
    except OSError as error:
        raise CuratorError("private file cannot be verified") from error
    return digest.hexdigest(), size


def _file_identity(metadata: os.stat_result) -> tuple[int, int, int, int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _path_fingerprint(path: Path) -> tuple[int, ...]:
    metadata = path.lstat()
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
    ):
        raise CuratorError("artifact archive private file is unsafe")
    return _file_identity(metadata)


def _member_path(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or "\x00" in value
        or "\\" in value
        or len(value.encode("utf-8")) > _MAX_MEMBER_PATH_BYTES
    ):
        raise CuratorError("artifact archive member path is invalid")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value or any(
        part in {"", ".", ".."} for part in path.parts
    ):
        raise CuratorError("artifact archive member path is invalid")
    return value


def _canonical(value: Mapping[str, object]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _archive_identity(
    workflow_id: str,
    ledger_token: str,
    members: tuple[CuratedArchiveMember, ...],
) -> str:
    identity = {
        "schema": _ARCHIVE_ID_SCHEMA,
        "workflow_id": workflow_id,
        "ledger_token": ledger_token,
        "members": [member.to_dict() for member in members],
    }
    return hashlib.sha256(_canonical(identity)).hexdigest()


def _reject_duplicate_keys(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CuratorError("duplicate artifact curator field")
        result[key] = value
    return result


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value or len(value) > 200:
        raise CuratorError(f"artifact curator {label} is invalid")
    return value


def _workflow_id(value: object) -> str:
    if not isinstance(value, str) or _WORKFLOW_ID.fullmatch(value) is None:
        raise CuratorError("artifact curator workflow ID is invalid")
    return value


def _digest_value(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise CuratorError(f"artifact curator {label} is invalid")
    return value


def _aware(value: object, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise CuratorError(f"artifact curator {label} must be timezone-aware")
    return value


__all__ = [
    "ArtifactCurator",
    "ArtifactCuratorStore",
    "CurationAction",
    "CurationRow",
    "CurationState",
    "CuratorDocument",
    "CuratorError",
    "CuratorPolicy",
    "CuratorPreview",
    "CuratorResult",
    "CuratorStatus",
]
