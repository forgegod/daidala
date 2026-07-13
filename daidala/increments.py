"""Immutable increment-document classification and provenance models."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath
from typing import Any

from .errors import PolicyViolationError
from .projects import (
    ProjectManifest,
    _as_list,
    _require_digest,
    _require_exact_fields,
    _require_int,
    _require_slug,
    _require_text,
)
from .state import ActivationCategory, ActivationManifest, WorkflowStage

INCREMENT_SCHEMA = "daidala.increment-manifest/v1"
MAX_DOCUMENT_BYTES = 1_048_576
MAX_INCREMENT_ENTRIES = 256
MAX_INCREMENT_MANIFEST_BYTES = 1_048_576
_CYCLE_ID = re.compile(r"^cycle-[0-9a-f]{64}$")
_MEDIA_TYPE = re.compile(
    r"^[a-z0-9][a-z0-9!#$&^_.+-]{0,63}/[a-z0-9][a-z0-9!#$&^_.+-]{0,127}$"
)


class DocumentClass(StrEnum):
    REPOSITORY_INCREMENT = "repository-increment"
    WORKFLOW_ARTIFACT = "workflow-artifact"
    EXTERNAL_FINDING = "external-finding"
    EPHEMERAL_WORK_PRODUCT = "ephemeral-work-product"


class RedactionState(StrEnum):
    NOT_REQUIRED = "not-required"
    REDACTED = "redacted"


class RetentionDisposition(StrEnum):
    RETAIN = "retain"
    REJECT = "reject"
    PUBLISH_PENDING = "publish-pending"
    DISCARD = "discard"
    QUARANTINE = "quarantine"


@dataclass(frozen=True)
class ProducerIdentity:
    name: str
    content_digest: str | None

    def __post_init__(self) -> None:
        if self.name == "deterministic-engine":
            if self.content_digest is not None:
                raise PolicyViolationError("deterministic engine producer has no skill digest")
            return
        _require_slug(self.name, "increment producer name")
        _require_digest(self.content_digest, "increment producer content digest")

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "content_digest": self.content_digest}

    @classmethod
    def from_dict(cls, raw: Any) -> ProducerIdentity:
        _require_exact_fields(raw, {"name", "content_digest"}, "increment producer")
        return cls(raw["name"], raw["content_digest"])


@dataclass(frozen=True)
class IncrementEntry:
    entry_id: str
    document_class: DocumentClass
    media_type: str
    purpose: str
    repository_path: str | None
    artifact_reference: str | None
    content_digest: str
    byte_size: int
    cycle_id: str
    workflow_id: str
    stage: WorkflowStage
    plan_revision: int
    policy_revision: int
    project_manifest_digest: str
    pack_identity_digest: str
    constraints_digest: str | None
    activation_manifest_digest: str
    producers: tuple[ProducerIdentity, ...]
    created_at: datetime
    supersedes_entry_id: str | None
    redaction_state: RedactionState
    disposition: RetentionDisposition
    dox_scope: str | None

    def __post_init__(self) -> None:
        _require_slug(self.entry_id, "increment entry ID")
        if not isinstance(self.document_class, DocumentClass):
            raise PolicyViolationError("increment document class is invalid")
        if self.document_class is DocumentClass.EPHEMERAL_WORK_PRODUCT:
            raise PolicyViolationError(
                "ephemeral work products cannot enter the increment manifest"
            )
        _require_media_type(self.media_type)
        _require_text(self.purpose, "increment purpose", 1_000)
        _require_digest(self.content_digest, "increment content digest")
        _require_int(self.byte_size, "increment byte size", 0, MAX_DOCUMENT_BYTES)
        _require_cycle_id(self.cycle_id)
        _require_slug(self.workflow_id, "increment workflow ID")
        if not isinstance(self.stage, WorkflowStage) or self.stage is WorkflowStage.APPROVAL:
            raise PolicyViolationError("increment stage must be executable")
        _require_int(self.plan_revision, "increment plan revision", 0, 1_000_000)
        _require_int(self.policy_revision, "increment policy revision", 0, 1_000_000)
        _require_digest(self.project_manifest_digest, "project manifest digest")
        _require_digest(self.pack_identity_digest, "pack identity digest")
        if self.constraints_digest is not None:
            _require_digest(self.constraints_digest, "increment constraints digest")
        _require_digest(self.activation_manifest_digest, "activation manifest digest")
        if not isinstance(self.producers, tuple) or not 1 <= len(self.producers) <= 8:
            raise PolicyViolationError("increment producers must contain 1-8 identities")
        names = [producer.name for producer in self.producers]
        if len(names) != len(set(names)):
            raise PolicyViolationError("increment producers cannot contain duplicates")
        if not isinstance(self.created_at, datetime) or self.created_at.tzinfo is None:
            raise PolicyViolationError("increment creation time must be timezone-aware")
        if self.supersedes_entry_id is not None:
            _require_slug(self.supersedes_entry_id, "superseded increment entry ID")
            if self.supersedes_entry_id == self.entry_id:
                raise PolicyViolationError("increment entry cannot supersede itself")
        if not isinstance(self.redaction_state, RedactionState):
            raise PolicyViolationError("increment redaction state is invalid")
        if not isinstance(self.disposition, RetentionDisposition):
            raise PolicyViolationError("increment disposition is invalid")
        self._validate_location_and_disposition()

    def _validate_location_and_disposition(self) -> None:
        if self.document_class is DocumentClass.REPOSITORY_INCREMENT:
            _require_repository_path(self.repository_path, "repository increment path")
            if self.artifact_reference is not None:
                raise PolicyViolationError("repository increments cannot use artifact references")
            _require_repository_path(self.dox_scope, "repository increment DOX scope")
            if self.disposition not in {RetentionDisposition.RETAIN, RetentionDisposition.REJECT}:
                raise PolicyViolationError("repository increments must be retained or rejected")
        else:
            if self.repository_path is not None or self.dox_scope is not None:
                raise PolicyViolationError(
                    "non-repository documents cannot declare repository paths"
                )
            _require_artifact_reference(self.artifact_reference)
            if self.document_class is DocumentClass.WORKFLOW_ARTIFACT and self.disposition not in {
                RetentionDisposition.RETAIN,
                RetentionDisposition.REJECT,
                RetentionDisposition.QUARANTINE,
            }:
                raise PolicyViolationError("workflow artifact disposition is invalid")
            if self.document_class is DocumentClass.EXTERNAL_FINDING and self.disposition not in {
                RetentionDisposition.PUBLISH_PENDING,
                RetentionDisposition.RETAIN,
                RetentionDisposition.REJECT,
            }:
                raise PolicyViolationError("external finding disposition is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "document_class": self.document_class.value,
            "media_type": self.media_type,
            "purpose": self.purpose,
            "repository_path": self.repository_path,
            "artifact_reference": self.artifact_reference,
            "content_digest": self.content_digest,
            "byte_size": self.byte_size,
            "cycle_id": self.cycle_id,
            "workflow_id": self.workflow_id,
            "stage": self.stage.value,
            "plan_revision": self.plan_revision,
            "policy_revision": self.policy_revision,
            "project_manifest_digest": self.project_manifest_digest,
            "pack_identity_digest": self.pack_identity_digest,
            "constraints_digest": self.constraints_digest,
            "activation_manifest_digest": self.activation_manifest_digest,
            "producers": [producer.to_dict() for producer in self.producers],
            "created_at": self.created_at.isoformat(),
            "supersedes_entry_id": self.supersedes_entry_id,
            "redaction_state": self.redaction_state.value,
            "disposition": self.disposition.value,
            "dox_scope": self.dox_scope,
        }

    @classmethod
    def from_dict(cls, raw: Any) -> IncrementEntry:
        fields = {
            "entry_id",
            "document_class",
            "media_type",
            "purpose",
            "repository_path",
            "artifact_reference",
            "content_digest",
            "byte_size",
            "cycle_id",
            "workflow_id",
            "stage",
            "plan_revision",
            "policy_revision",
            "project_manifest_digest",
            "pack_identity_digest",
            "constraints_digest",
            "activation_manifest_digest",
            "producers",
            "created_at",
            "supersedes_entry_id",
            "redaction_state",
            "disposition",
            "dox_scope",
        }
        _require_exact_fields(raw, fields, "increment entry")
        try:
            return cls(
                **{
                    **raw,
                    "document_class": DocumentClass(raw["document_class"]),
                    "stage": WorkflowStage(raw["stage"]),
                    "producers": tuple(
                        ProducerIdentity.from_dict(row)
                        for row in _as_list(raw["producers"], "increment producers")
                    ),
                    "created_at": datetime.fromisoformat(raw["created_at"]),
                    "redaction_state": RedactionState(raw["redaction_state"]),
                    "disposition": RetentionDisposition(raw["disposition"]),
                }
            )
        except (TypeError, ValueError) as error:
            if isinstance(error, PolicyViolationError):
                raise
            raise PolicyViolationError(f"invalid increment entry: {error}") from error


@dataclass(frozen=True)
class IncrementManifest:
    cycle_id: str
    workflow_id: str
    entries: tuple[IncrementEntry, ...]
    schema: str = INCREMENT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != INCREMENT_SCHEMA:
            raise PolicyViolationError(f"increment schema must be {INCREMENT_SCHEMA!r}")
        _require_cycle_id(self.cycle_id)
        _require_slug(self.workflow_id, "increment manifest workflow ID")
        if (
            not isinstance(self.entries, tuple)
            or not 1 <= len(self.entries) <= MAX_INCREMENT_ENTRIES
        ):
            raise PolicyViolationError(
                f"increment manifest must contain 1-{MAX_INCREMENT_ENTRIES} entries"
            )
        entry_ids = [entry.entry_id for entry in self.entries]
        if len(entry_ids) != len(set(entry_ids)):
            raise PolicyViolationError("increment manifest cannot contain duplicate entry IDs")
        if entry_ids != sorted(entry_ids):
            raise PolicyViolationError("increment entries must use canonical entry-ID order")
        for entry in self.entries:
            if entry.cycle_id != self.cycle_id or entry.workflow_id != self.workflow_id:
                raise PolicyViolationError("increment entry identity does not match its manifest")
        if len(self.canonical_bytes()) > MAX_INCREMENT_MANIFEST_BYTES:
            raise PolicyViolationError("increment manifest exceeds its canonical byte bound")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "cycle_id": self.cycle_id,
            "workflow_id": self.workflow_id,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    @classmethod
    def from_dict(cls, raw: Any) -> IncrementManifest:
        _require_exact_fields(
            raw,
            {"schema", "cycle_id", "workflow_id", "entries"},
            "increment manifest",
        )
        return cls(
            schema=raw["schema"],
            cycle_id=raw["cycle_id"],
            workflow_id=raw["workflow_id"],
            entries=tuple(
                IncrementEntry.from_dict(row)
                for row in _as_list(raw["entries"], "increment entries")
            ),
        )


@dataclass(frozen=True)
class IncrementReconciliation:
    manifest_digest: str
    repository_paths: tuple[str, ...]
    artifact_references: tuple[str, ...]
    activation_digests: tuple[str, ...]


def reconcile_increment_manifest(
    manifest: IncrementManifest,
    *,
    project_manifest: ProjectManifest,
    repository_root: Path,
    approved_repository_paths: tuple[str, ...],
    frozen_changed_paths: tuple[str, ...],
    artifact_ledger: Mapping[str, tuple[str, int]],
    activation_manifests: tuple[ActivationManifest, ...],
    expected_pack_identity_digest: str,
    expected_constraints_digest: str | None,
) -> IncrementReconciliation:
    """Reconcile durable documents against immutable policy and observed content."""
    if not isinstance(manifest, IncrementManifest):
        raise PolicyViolationError("increment reconciliation manifest is invalid")
    if not isinstance(project_manifest, ProjectManifest):
        raise PolicyViolationError("increment reconciliation project manifest is invalid")
    root = Path(repository_root)
    if not root.is_absolute() or root != root.resolve() or not root.is_dir():
        raise PolicyViolationError("increment repository root must be an existing resolved path")
    _require_digest(expected_pack_identity_digest, "expected pack identity digest")
    if expected_constraints_digest is not None:
        _require_digest(expected_constraints_digest, "expected constraints digest")
    approved = _canonical_path_set(approved_repository_paths, "approved plan paths")
    changed = _canonical_path_set(frozen_changed_paths, "frozen changed paths")
    if len(changed) > project_manifest.maximum_changed_files:
        raise PolicyViolationError("frozen diff exceeds the project changed-file limit")
    for path in changed:
        _require_mutable_path(project_manifest, path)

    activations = {
        hashlib.sha256(row.canonical_bytes()).hexdigest(): row
        for row in activation_manifests
    }
    if len(activations) != len(activation_manifests):
        raise PolicyViolationError("increment activation manifests contain duplicate identity")
    repository_paths: list[str] = []
    artifact_references: list[str] = []
    used_activations: set[str] = set()
    for entry in manifest.entries:
        if entry.project_manifest_digest != project_manifest.digest:
            raise PolicyViolationError("increment project manifest identity is stale")
        if entry.pack_identity_digest != expected_pack_identity_digest:
            raise PolicyViolationError("increment pack identity is stale")
        if entry.constraints_digest != expected_constraints_digest:
            raise PolicyViolationError("increment constraints identity is stale")
        activation = activations.get(entry.activation_manifest_digest)
        if activation is None:
            raise PolicyViolationError("increment activation identity is stale or missing")
        _validate_entry_activation(
            entry, activation, project_manifest, expected_pack_identity_digest
        )
        used_activations.add(entry.activation_manifest_digest)

        if entry.document_class is DocumentClass.REPOSITORY_INCREMENT:
            path = entry.repository_path or ""
            if path not in approved:
                raise PolicyViolationError(
                    "repository increment is not declared by the approved plan"
                )
            if path not in changed:
                raise PolicyViolationError("repository increment is absent from the frozen diff")
            _require_mutable_path(project_manifest, path)
            content = _read_repository_document(root, path)
            if hashlib.sha256(content).hexdigest() != entry.content_digest:
                raise PolicyViolationError("repository increment content digest does not match")
            if len(content) != entry.byte_size:
                raise PolicyViolationError("repository increment byte size does not match")
            _require_nearest_dox(root, path, entry.dox_scope or "")
            repository_paths.append(path)
        else:
            reference = entry.artifact_reference or ""
            ledger_row = artifact_ledger.get(reference)
            if ledger_row is None:
                raise PolicyViolationError("increment artifact is missing from the artifact ledger")
            if ledger_row != (entry.content_digest, entry.byte_size):
                raise PolicyViolationError("increment artifact ledger identity does not match")
            artifact_references.append(reference)

    return IncrementReconciliation(
        manifest_digest=manifest.digest,
        repository_paths=tuple(sorted(repository_paths)),
        artifact_references=tuple(sorted(artifact_references)),
        activation_digests=tuple(sorted(used_activations)),
    )


def _validate_entry_activation(
    entry: IncrementEntry,
    activation: ActivationManifest,
    project_manifest: ProjectManifest,
    expected_pack_identity_digest: str,
) -> None:
    if activation.blocked:
        raise PolicyViolationError("blocked activation cannot produce an increment document")
    if (
        activation.workflow_id != entry.workflow_id
        or activation.stage is not entry.stage
        or activation.plan_revision != entry.plan_revision
        or activation.policy_revision != entry.policy_revision
        or activation.constraints_digest != entry.constraints_digest
    ):
        raise PolicyViolationError("increment activation identity does not match the entry")
    selected_pack = next(
        (
            pack
            for pack in project_manifest.allowed_packs
            if pack.name == activation.pack
            and pack.source_revision == activation.pack_source_revision
        ),
        None,
    )
    if selected_pack is None:
        raise PolicyViolationError("increment activation pack is not allowed by the project")
    selected_digest = hashlib.sha256(
        json.dumps(
            selected_pack.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()
    if selected_digest != expected_pack_identity_digest:
        raise PolicyViolationError("approved pack identity does not match the activation")
    applicable = {
        (decision.name, decision.skill_digest)
        for decision in activation.decisions
        if decision.category is ActivationCategory.APPLICABLE
    }
    for producer in entry.producers:
        if (producer.name, producer.content_digest) not in applicable:
            raise PolicyViolationError(
                "increment producer is not active in the finalized activation"
            )


def _canonical_path_set(values: tuple[str, ...], label: str) -> set[str]:
    if not isinstance(values, tuple) or len(values) != len(set(values)):
        raise PolicyViolationError(f"{label} must be a duplicate-free tuple")
    for value in values:
        _require_repository_path(value, label)
    return set(values)


def _require_mutable_path(manifest: ProjectManifest, path: str) -> None:
    if any(fnmatchcase(path, pattern) for pattern in manifest.protected_paths):
        raise PolicyViolationError("frozen diff touches a protected project path")
    if not any(fnmatchcase(path, pattern) for pattern in manifest.mutable_paths):
        raise PolicyViolationError("frozen diff touches a path outside mutable project policy")


def _read_repository_document(root: Path, relative: str) -> bytes:
    target = root / relative
    try:
        resolved = target.resolve(strict=True)
    except OSError as error:
        raise PolicyViolationError("repository increment document is missing") from error
    if not resolved.is_file() or root not in resolved.parents:
        raise PolicyViolationError("repository increment document escapes its repository")
    if target.is_symlink():
        raise PolicyViolationError("repository increment document cannot be a symlink")
    try:
        return resolved.read_bytes()
    except OSError as error:
        raise PolicyViolationError("repository increment document is unreadable") from error


def _require_nearest_dox(root: Path, relative: str, declared_scope: str) -> None:
    _require_repository_path(declared_scope, "repository increment DOX scope")
    cursor = (root / relative).parent
    nearest: Path | None = None
    while cursor == root or root in cursor.parents:
        candidate = cursor / "AGENTS.md"
        if candidate.is_file():
            nearest = candidate
            break
        if cursor == root:
            break
        cursor = cursor.parent
    if nearest is None or nearest.relative_to(root).as_posix() != declared_scope:
        raise PolicyViolationError(
            "repository increment does not name its nearest owning DOX scope"
        )


def increment_manifest_path(data_root: Path, project_id: str, cycle_id: str) -> Path:
    if not isinstance(data_root, Path) or not data_root.is_absolute():
        raise PolicyViolationError("increment data root must be an absolute resolved path")
    if ".." in data_root.parts or "." in data_root.parts:
        raise PolicyViolationError("increment data root must be an absolute resolved path")
    _require_slug(project_id, "increment project ID")
    _require_cycle_id(cycle_id)
    return data_root / "projects" / project_id / "cycles" / cycle_id / "increment-manifest.json"


def _require_cycle_id(value: Any) -> None:
    if not isinstance(value, str) or not _CYCLE_ID.fullmatch(value):
        raise PolicyViolationError("increment cycle ID must be cycle- plus a SHA-256 digest")


def _require_media_type(value: Any) -> None:
    _require_text(value, "increment media type", 127)
    if not isinstance(value, str) or not _MEDIA_TYPE.fullmatch(value):
        raise PolicyViolationError("increment media type must be a canonical type/subtype")


def _require_repository_path(value: Any, label: str) -> None:
    _require_text(value, label, 512)
    if not isinstance(value, str):
        raise PolicyViolationError(f"{label} must be a string")
    path = PurePosixPath(value)
    if not path.parts or path.is_absolute() or ".." in path.parts or str(path) != value:
        raise PolicyViolationError(f"{label} must be a normalized repository-relative path")


def _require_artifact_reference(value: Any) -> None:
    _require_text(value, "artifact reference", 512)
    if not isinstance(value, str) or not value.startswith("artifacts/"):
        raise PolicyViolationError("artifact reference must be profile-local under artifacts/")
    _require_repository_path(value, "artifact reference")
