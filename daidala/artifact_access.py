"""Ledger-bound, digest-verifying access to active workflow artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from .archive_io import ArchiveError, ArchiveMember, inventory_archive, read_archive_member
from .errors import WorkflowError
from .state import ApprovalSummary, WorkflowLedger, WorkflowStage
from .store import StoreError, WorkflowStore

_MAX_ARTIFACT_BYTES = 1024 * 1024
_MAX_EXPORT_BYTES = 64 * 1024 * 1024
_ALLOWED_KINDS = frozenset({"stage", "verification", "constraint", "activation"})


class ArtifactFailureReason(StrEnum):
    INVALID_REQUEST = "invalid_request"
    WORKFLOW_UNAVAILABLE = "workflow_unavailable"
    ARTIFACT_NOT_FOUND = "artifact_not_found"
    MISSING_PLAN = "missing_plan"
    STALE_IDENTITY = "stale_identity"
    MISSING_SUMMARY = "missing_summary"
    INVALID_SUMMARY = "invalid_summary"
    BINARY = "binary"
    OVERSIZED = "oversized"
    DIGEST_MISMATCH = "digest_mismatch"
    UNSAFE_PATH = "unsafe_path"
    EXPORT_COLLISION = "export_collision"
    EXPORT_FAILED = "export_failed"
    ARCHIVE_INVALID = "archive_invalid"


class ArtifactAccessError(WorkflowError):
    """Raised when ledger identity cannot authorize verified artifact bytes."""

    def __init__(
        self,
        message: str,
        *,
        reason: ArtifactFailureReason = ArtifactFailureReason.INVALID_REQUEST,
    ) -> None:
        super().__init__(message)
        self.reason = reason


class ArtifactAvailability(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    ACTIVE_AND_ARCHIVED = "active-and-archived"
    MISSING = "missing"


@dataclass(frozen=True)
class ArtifactId:
    value: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.value, str)
            or len(self.value) != 64
            or any(character not in "0123456789abcdef" for character in self.value)
        ):
            raise ArtifactAccessError("artifact ID must be an opaque SHA-256 identity")

    def __str__(self) -> str:
        return self.value

    def __len__(self) -> int:
        return len(self.value)


@dataclass(frozen=True)
class ArchivedArtifactSource:
    archive_path: Path
    manifest_path: Path
    member_path: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.archive_path, Path)
            or not self.archive_path.is_absolute()
            or not isinstance(self.manifest_path, Path)
            or not self.manifest_path.is_absolute()
            or not isinstance(self.member_path, str)
            or not self.member_path
        ):
            raise ArtifactAccessError(
                "archived artifact source is malformed",
                reason=ArtifactFailureReason.ARCHIVE_INVALID,
            )


ArtifactArchiveLookup = Callable[[str, ArtifactId], ArchivedArtifactSource | None]


@dataclass(frozen=True)
class ArtifactCatalogEntry:
    artifact_id: ArtifactId
    workflow_id: str
    kind: str
    stage: str | None
    policy_revision: int
    plan_revision: int
    digest: str
    recorded_at: datetime | None
    size: int | None
    availability: ArtifactAvailability
    approval_summary_digest: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact_id": str(self.artifact_id),
            "workflow_id": self.workflow_id,
            "kind": self.kind,
            "stage": self.stage,
            "policy_revision": self.policy_revision,
            "plan_revision": self.plan_revision,
            "digest": self.digest,
            "recorded_at": self.recorded_at.isoformat() if self.recorded_at else None,
            "size": self.size,
            "availability": self.availability.value,
            "approval_summary_digest": self.approval_summary_digest,
        }


@dataclass(frozen=True)
class ArtifactText:
    entry: ArtifactCatalogEntry
    content: str
    approval_summary: ApprovalSummary | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            **self.entry.to_dict(),
            "content": self.content,
            "approval_summary": (
                self.approval_summary.to_dict() if self.approval_summary else None
            ),
        }


@dataclass(frozen=True)
class CurrentPlanEvidence:
    workflow_id: str
    artifact_id: ArtifactId
    policy_revision: int
    plan_revision: int
    plan_digest: str
    approval_summary: ApprovalSummary
    approval_summary_digest: str
    content: str

    def to_dict(self) -> dict[str, object]:
        return {
            "workflow_id": self.workflow_id,
            "artifact_id": str(self.artifact_id),
            "policy_revision": self.policy_revision,
            "plan_revision": self.plan_revision,
            "plan_digest": self.plan_digest,
            "approval_summary": self.approval_summary.to_dict(),
            "approval_summary_digest": self.approval_summary_digest,
            "content": self.content,
        }


@dataclass(frozen=True)
class ArtifactExport:
    artifact_id: ArtifactId
    digest: str
    size: int
    output: str

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact_id": str(self.artifact_id),
            "digest": self.digest,
            "size": self.size,
            "output": self.output,
        }


@dataclass(frozen=True)
class _ArtifactRecord:
    entry: ArtifactCatalogEntry
    path: str
    evidence_key: str
    approval_summary: ApprovalSummary | None = None
    archive_source: ArchivedArtifactSource | None = None


class ArtifactAccessService:
    """Resolve active or archived bytes exclusively through immutable ledger facts."""

    def __init__(
        self,
        store: WorkflowStore,
        *,
        archive_lookup: ArtifactArchiveLookup | None = None,
    ) -> None:
        self._store = store
        self._data_root = store.data_root.resolve()
        self._archive_lookup = archive_lookup

    def list(
        self,
        workflow_id: str,
        kinds: Iterable[str] | None = None,
        revisions: Iterable[int] | None = None,
        *,
        ledger: WorkflowLedger | None = None,
    ) -> tuple[ArtifactCatalogEntry, ...]:
        selected_kinds = self._selected_kinds(kinds)
        selected_revisions = self._selected_revisions(revisions)
        records = self._records(workflow_id, selected_kinds, ledger=ledger)
        if selected_revisions is not None:
            records = tuple(
                record
                for record in records
                if record.entry.plan_revision in selected_revisions
            )
        return tuple(record.entry for record in records)

    def read_text(
        self,
        workflow_id: str,
        artifact_id: str | ArtifactId,
        *,
        ledger: WorkflowLedger | None = None,
    ) -> ArtifactText:
        record = self._resolve_record(workflow_id, artifact_id, ledger=ledger)
        try:
            content = self._verified_bytes(record, maximum=_MAX_ARTIFACT_BYTES).decode(
                "utf-8", errors="strict"
            )
        except UnicodeDecodeError as error:
            raise ArtifactAccessError(
                "artifact content is binary; use verified export",
                reason=ArtifactFailureReason.BINARY,
            ) from error
        if "\x00" in content:
            raise ArtifactAccessError(
                "artifact content is binary; use verified export",
                reason=ArtifactFailureReason.BINARY,
            )
        return ArtifactText(
            entry=record.entry,
            content=content,
            approval_summary=record.approval_summary,
        )

    def export(
        self,
        workflow_id: str,
        artifact_id: str | ArtifactId,
        output: str | Path,
        *,
        overwrite: bool = False,
    ) -> ArtifactExport:
        record = self._resolve_record(workflow_id, artifact_id)
        content = self._verified_bytes(record, maximum=_MAX_EXPORT_BYTES)
        destination = self._validated_destination(output, overwrite=overwrite)
        temporary: Path | None = None
        try:
            descriptor, temporary_name = tempfile.mkstemp(
                dir=destination.parent,
                prefix=".daidala-artifact-export-",
            )
            temporary = Path(temporary_name)
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            if hashlib.sha256(temporary.read_bytes()).hexdigest() != record.entry.digest:
                raise ArtifactAccessError("exported artifact digest verification failed")
            if overwrite:
                os.replace(temporary, destination)
            else:
                try:
                    os.link(temporary, destination)
                except FileExistsError as error:
                    raise ArtifactAccessError(
                        "artifact export destination already exists",
                        reason=ArtifactFailureReason.EXPORT_COLLISION,
                    ) from error
                temporary.unlink()
            os.chmod(destination, 0o600)
        except ArtifactAccessError:
            raise
        except OSError as error:
            raise ArtifactAccessError("artifact export failed") from error
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        if hashlib.sha256(destination.read_bytes()).hexdigest() != record.entry.digest:
            raise ArtifactAccessError("exported artifact digest verification failed")
        return ArtifactExport(
            artifact_id=record.entry.artifact_id,
            digest=record.entry.digest,
            size=len(content),
            output=str(destination),
        )

    def current_plan(
        self, workflow_id: str, *, ledger: WorkflowLedger | None = None
    ) -> CurrentPlanEvidence:
        ledger = self._snapshot_ledger(workflow_id, ledger)
        current = ledger.artifact_for(WorkflowStage.PLAN)
        if current is None:
            raise ArtifactAccessError(
                "current plan is not available",
                reason=ArtifactFailureReason.MISSING_PLAN,
            )
        record = next(
            (
                candidate
                for candidate in self._records(
                    ledger.workflow_id, frozenset({"stage"}), ledger=ledger
                )
                if candidate.entry.stage == WorkflowStage.PLAN.value
                and candidate.entry.policy_revision == ledger.policy_revision
                and candidate.entry.plan_revision == ledger.plan_revision
                and candidate.entry.digest == current.digest
            ),
            None,
        )
        if record is None:
            raise ArtifactAccessError(
                "current plan identity is not available",
                reason=ArtifactFailureReason.STALE_IDENTITY,
            )
        summary = current.approval_summary
        summary_digest = current.approval_summary_digest
        if summary is None or summary_digest is None:
            raise ArtifactAccessError(
                "current plan is not approvable without a bound summary",
                reason=ArtifactFailureReason.MISSING_SUMMARY,
            )
        if summary.digest_for(current.digest) != summary_digest:
            raise ArtifactAccessError(
                "current plan approval summary identity is invalid",
                reason=ArtifactFailureReason.INVALID_SUMMARY,
            )
        text = self.read_text(workflow_id, record.entry.artifact_id, ledger=ledger)
        return CurrentPlanEvidence(
            workflow_id=workflow_id,
            artifact_id=record.entry.artifact_id,
            policy_revision=current.policy_revision,
            plan_revision=current.plan_revision,
            plan_digest=current.digest,
            approval_summary=summary,
            approval_summary_digest=summary_digest,
            content=text.content,
        )

    def _resolve_record(
        self,
        workflow_id: str,
        artifact_id: str | ArtifactId,
        *,
        ledger: WorkflowLedger | None = None,
    ) -> _ArtifactRecord:
        identity = (
            artifact_id if isinstance(artifact_id, ArtifactId) else ArtifactId(artifact_id)
        )
        record = next(
            (
                candidate
                for candidate in self._records(
                    workflow_id, _ALLOWED_KINDS, ledger=ledger
                )
                if candidate.entry.artifact_id == identity
            ),
            None,
        )
        if record is None:
            raise ArtifactAccessError(
                "artifact ID is not bound to this workflow",
                reason=ArtifactFailureReason.ARTIFACT_NOT_FOUND,
            )
        return record

    def _records(
        self,
        workflow_id: str,
        selected_kinds: frozenset[str],
        *,
        ledger: WorkflowLedger | None = None,
    ) -> tuple[_ArtifactRecord, ...]:
        ledger = self._snapshot_ledger(workflow_id, ledger)
        records: list[_ArtifactRecord] = []
        if "stage" in selected_kinds:
            for reference in ledger.artifacts:
                records.append(
                    self._record(
                        ledger,
                        kind="stage",
                        stage=reference.stage.value,
                        policy_revision=reference.policy_revision,
                        plan_revision=reference.plan_revision,
                        evidence_key=reference.stage.value,
                        digest=reference.digest,
                        recorded_at=reference.recorded_at,
                        path=reference.path,
                        approval_summary=reference.approval_summary,
                        approval_summary_digest=reference.approval_summary_digest,
                    )
                )
        if "verification" in selected_kinds:
            for evidence in ledger.verification_evidence:
                command_identity = hashlib.sha256(evidence.command.encode("utf-8")).hexdigest()
                records.append(
                    self._record(
                        ledger,
                        kind="verification",
                        stage=WorkflowStage.VERIFY.value,
                        policy_revision=ledger.policy_revision,
                        plan_revision=evidence.plan_revision,
                        evidence_key=f"command:{command_identity}:exit:{evidence.exit_code}",
                        digest=evidence.output_digest,
                        recorded_at=evidence.recorded_at,
                        path=evidence.output_reference,
                    )
                )
        if "constraint" in selected_kinds:
            for reference in ledger.constraint_references:
                records.append(
                    self._record(
                        ledger,
                        kind="constraint",
                        stage=None,
                        policy_revision=reference.identity.policy_revision,
                        plan_revision=0,
                        evidence_key=(
                            f"constraint:{reference.identity.constraints_revision}"
                        ),
                        digest=reference.identity.digest,
                        recorded_at=reference.recorded_at,
                        path=reference.path,
                    )
                )
        if "activation" in selected_kinds:
            for reference in ledger.activation_manifests:
                records.append(
                    self._record(
                        ledger,
                        kind="activation",
                        stage=reference.stage.value,
                        policy_revision=reference.policy_revision,
                        plan_revision=reference.plan_revision,
                        evidence_key=(
                            f"activation:{reference.stage.value}:{reference.sequence}:"
                            f"{reference.state.value}"
                        ),
                        digest=reference.digest,
                        recorded_at=None,
                        path=reference.path,
                    )
                )
        return tuple(
            sorted(
                records,
                key=lambda record: (
                    record.entry.policy_revision,
                    record.entry.plan_revision,
                    record.entry.kind,
                    record.entry.stage or "",
                    record.evidence_key,
                    record.entry.digest,
                ),
            )
        )

    def _snapshot_ledger(
        self, workflow_id: str, ledger: WorkflowLedger | None
    ) -> WorkflowLedger:
        if ledger is None:
            return self._ledger(workflow_id)
        if ledger.workflow_id != workflow_id:
            raise ArtifactAccessError(
                "artifact snapshot workflow identity does not match request"
            )
        return ledger

    def _record(
        self,
        ledger: WorkflowLedger,
        *,
        kind: str,
        stage: str | None,
        policy_revision: int,
        plan_revision: int,
        evidence_key: str,
        digest: str,
        recorded_at: datetime | None,
        path: str,
        approval_summary: ApprovalSummary | None = None,
        approval_summary_digest: str | None = None,
    ) -> _ArtifactRecord:
        identity = {
            "schema": "daidala.artifact-id/v1",
            "workflow_id": ledger.workflow_id,
            "kind": kind,
            "stage": stage,
            "policy_revision": policy_revision,
            "plan_revision": plan_revision,
            "evidence_key": evidence_key,
            "digest": digest,
        }
        canonical = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
        artifact_id = ArtifactId(hashlib.sha256(canonical).hexdigest())
        archive_source = self._archive_source(ledger.workflow_id, artifact_id)
        availability, size = self._availability(
            ledger.workflow_id,
            path,
            digest=digest,
            archive_source=archive_source,
        )
        entry = ArtifactCatalogEntry(
            artifact_id=artifact_id,
            workflow_id=ledger.workflow_id,
            kind=kind,
            stage=stage,
            policy_revision=policy_revision,
            plan_revision=plan_revision,
            digest=digest,
            recorded_at=recorded_at,
            size=size,
            availability=availability,
            approval_summary_digest=approval_summary_digest,
        )
        return _ArtifactRecord(
            entry=entry,
            path=path,
            evidence_key=evidence_key,
            approval_summary=approval_summary,
            archive_source=archive_source,
        )

    def _archive_source(
        self, workflow_id: str, artifact_id: ArtifactId
    ) -> ArchivedArtifactSource | None:
        if self._archive_lookup is None:
            return None
        try:
            source = self._archive_lookup(workflow_id, artifact_id)
        except Exception as error:  # noqa: BLE001 - injected profile-state boundary
            raise ArtifactAccessError(
                "artifact archive lookup failed",
                reason=ArtifactFailureReason.ARCHIVE_INVALID,
            ) from error
        if source is not None and not isinstance(source, ArchivedArtifactSource):
            raise ArtifactAccessError(
                "artifact archive lookup returned an invalid source",
                reason=ArtifactFailureReason.ARCHIVE_INVALID,
            )
        return source

    def _availability(
        self,
        workflow_id: str,
        recorded_path: str,
        *,
        digest: str,
        archive_source: ArchivedArtifactSource | None,
    ) -> tuple[ArtifactAvailability, int | None]:
        active_size: int | None = None
        try:
            path = self._validated_source_path(workflow_id, recorded_path)
            details = path.stat(follow_symlinks=False)
        except (ArtifactAccessError, OSError):
            pass
        else:
            if stat.S_ISREG(details.st_mode):
                active_size = details.st_size
        archived_member = self._archived_member(archive_source, digest=digest)
        if active_size is not None and archived_member is not None:
            if active_size != archived_member.size:
                raise ArtifactAccessError(
                    "active and archived artifact sizes do not match",
                    reason=ArtifactFailureReason.DIGEST_MISMATCH,
                )
            return ArtifactAvailability.ACTIVE_AND_ARCHIVED, active_size
        if active_size is not None:
            return ArtifactAvailability.ACTIVE, active_size
        if archived_member is not None:
            return ArtifactAvailability.ARCHIVED, archived_member.size
        return ArtifactAvailability.MISSING, None

    def _archived_member(
        self,
        source: ArchivedArtifactSource | None,
        *,
        digest: str,
    ) -> ArchiveMember | None:
        if source is None:
            return None
        try:
            manifest = inventory_archive(source.archive_path, source.manifest_path)
        except ArchiveError as error:
            raise ArtifactAccessError(
                "archived artifact cannot be verified",
                reason=ArtifactFailureReason.ARCHIVE_INVALID,
            ) from error
        member = next(
            (candidate for candidate in manifest.members if candidate.path == source.member_path),
            None,
        )
        if member is None or member.sha256 != digest:
            raise ArtifactAccessError(
                "archived artifact does not match the policy ledger",
                reason=ArtifactFailureReason.DIGEST_MISMATCH,
            )
        return member

    def _verified_bytes(self, record: _ArtifactRecord, *, maximum: int) -> bytes:
        if record.entry.availability is ArtifactAvailability.ARCHIVED:
            return self._verified_archived_bytes(record, maximum=maximum)
        return self._verified_active_bytes(record, maximum=maximum)

    def _verified_active_bytes(self, record: _ArtifactRecord, *, maximum: int) -> bytes:
        path = self._validated_source_path(record.entry.workflow_id, record.path)
        try:
            details = path.stat(follow_symlinks=False)
        except OSError as error:
            raise ArtifactAccessError("artifact bytes are not available") from error
        if not stat.S_ISREG(details.st_mode):
            raise ArtifactAccessError("artifact reference is not a direct regular file")
        if details.st_size > maximum:
            raise ArtifactAccessError(
                self._bound_message(maximum),
                reason=ArtifactFailureReason.OVERSIZED,
            )
        try:
            content = path.read_bytes()
        except OSError as error:
            raise ArtifactAccessError("artifact bytes cannot be read") from error
        if len(content) > maximum:
            raise ArtifactAccessError(
                self._bound_message(maximum),
                reason=ArtifactFailureReason.OVERSIZED,
            )
        if hashlib.sha256(content).hexdigest() != record.entry.digest:
            raise ArtifactAccessError(
                "artifact digest does not match the policy ledger",
                reason=ArtifactFailureReason.DIGEST_MISMATCH,
            )
        return content

    def _verified_archived_bytes(self, record: _ArtifactRecord, *, maximum: int) -> bytes:
        source = record.archive_source
        if source is None:
            raise ArtifactAccessError("artifact bytes are not available")
        try:
            content = read_archive_member(
                source.archive_path,
                source.manifest_path,
                source.member_path,
                max_bytes=maximum,
            )
        except ArchiveError as error:
            reason = (
                ArtifactFailureReason.OVERSIZED
                if str(error).endswith("bounds")
                else ArtifactFailureReason.ARCHIVE_INVALID
            )
            message = (
                self._bound_message(maximum)
                if reason is ArtifactFailureReason.OVERSIZED
                else "archived artifact cannot be verified"
            )
            raise ArtifactAccessError(message, reason=reason) from error
        if hashlib.sha256(content).hexdigest() != record.entry.digest:
            raise ArtifactAccessError(
                "archived artifact does not match the policy ledger",
                reason=ArtifactFailureReason.DIGEST_MISMATCH,
            )
        return content

    @staticmethod
    def _bound_message(maximum: int) -> str:
        if maximum == _MAX_ARTIFACT_BYTES:
            return "artifact exceeds the 1 MiB document bound; use verified export"
        return "artifact exceeds the 64 MiB export bound"

    def _validated_source_path(self, workflow_id: str, recorded_path: str) -> Path:
        if not isinstance(recorded_path, str) or not recorded_path:
            raise ArtifactAccessError("artifact reference is malformed")
        candidate = Path(recorded_path)
        if not candidate.is_absolute():
            raise ArtifactAccessError("artifact reference is not an absolute ledger path")
        root = self._data_root / "workflows" / workflow_id / "artifacts"
        try:
            candidate.relative_to(root)
        except ValueError as error:
            raise ArtifactAccessError(
                "artifact reference is outside its workflow artifact root",
                reason=ArtifactFailureReason.UNSAFE_PATH,
            ) from error
        current = candidate
        while current != root:
            if current.is_symlink():
                raise ArtifactAccessError("artifact reference contains a symlink")
            if current == current.parent:
                raise ArtifactAccessError(
                    "artifact reference is outside its workflow artifact root",
                    reason=ArtifactFailureReason.UNSAFE_PATH,
                )
            current = current.parent
        current = root
        while current != self._data_root:
            if current.is_symlink():
                raise ArtifactAccessError("workflow artifact root contains a symlink")
            if current == current.parent:
                raise ArtifactAccessError("workflow artifact root is invalid")
            current = current.parent
        if candidate.resolve(strict=False) != candidate:
            raise ArtifactAccessError("artifact reference is not normalized")
        return candidate

    @staticmethod
    def _validated_destination(output: str | Path, *, overwrite: bool) -> Path:
        if not isinstance(output, (str, Path)) or not str(output):
            raise ArtifactAccessError("artifact export destination is required")
        destination = Path(output).absolute()
        parent = destination.parent
        if not parent.is_dir() or parent.is_symlink():
            raise ArtifactAccessError("artifact export parent must be an existing real directory")
        if destination.is_symlink():
            raise ArtifactAccessError("artifact export destination cannot be a symlink")
        if destination.exists():
            if not overwrite:
                raise ArtifactAccessError(
                    "artifact export destination already exists",
                    reason=ArtifactFailureReason.EXPORT_COLLISION,
                )
            try:
                details = destination.stat(follow_symlinks=False)
            except OSError as error:
                raise ArtifactAccessError(
                    "artifact export destination cannot be inspected"
                ) from error
            if not stat.S_ISREG(details.st_mode):
                raise ArtifactAccessError("artifact export destination must be a regular file")
        return destination

    @staticmethod
    def _selected_kinds(kinds: Iterable[str] | None) -> frozenset[str]:
        if kinds is None:
            return frozenset({"stage", "verification"})
        try:
            selected = frozenset(kinds)
        except TypeError as error:
            raise ArtifactAccessError("artifact kinds must be an iterable of strings") from error
        unknown = selected - _ALLOWED_KINDS
        if unknown or any(not isinstance(kind, str) for kind in selected):
            raise ArtifactAccessError("artifact kinds contain an unknown value")
        return selected

    @staticmethod
    def _selected_revisions(revisions: Iterable[int] | None) -> frozenset[int] | None:
        if revisions is None:
            return None
        try:
            selected = frozenset(revisions)
        except TypeError as error:
            raise ArtifactAccessError("artifact revisions must be non-negative integers") from error
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in selected
        ):
            raise ArtifactAccessError("artifact revisions must be non-negative integers")
        return selected

    def _ledger(self, workflow_id: str) -> WorkflowLedger:
        if not isinstance(workflow_id, str) or not workflow_id:
            raise ArtifactAccessError("workflow ID is required")
        try:
            return self._store.get(workflow_id)
        except StoreError as error:
            raise ArtifactAccessError(
                "workflow is not available",
                reason=ArtifactFailureReason.WORKFLOW_UNAVAILABLE,
            ) from error


__all__ = [
    "ArchivedArtifactSource",
    "ArtifactAccessError",
    "ArtifactAccessService",
    "ArtifactArchiveLookup",
    "ArtifactAvailability",
    "ArtifactCatalogEntry",
    "ArtifactExport",
    "ArtifactFailureReason",
    "ArtifactId",
    "ArtifactText",
    "CurrentPlanEvidence",
]
