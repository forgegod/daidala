"""Immutable Daidala policy and artifact ledger types."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any

from .errors import PolicyViolationError
from .packs import SkillActivationMode

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_REVISION = re.compile(r"^[0-9a-f]{40}$")
_SKILL_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,127}$")
_ACTIVATION_SCHEMA = "daidala.skill-activation/v1"
_PLAN_SOURCE_REFERENCE_SCHEMA = "daidala.plan-source-reference/v1"
_PLAN_SOURCE_PACKET_SCHEMA = "daidala.plan-source-packet/v1"
_PLAN_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,127}$")
_EXECUTION_SLOT = re.compile(r"^P[0-9]{4}$")
_GIT_OBJECT_ID = re.compile(r"^[0-9a-f]{40,64}$")
_PLAN_DOCUMENT_BYTES = 1_048_576


@dataclass(frozen=True)
class PlanSourceReference:
    """Exact immutable Git-object identity for one repository plan document."""

    schema: str
    repository: str
    source_revision: str
    baseline_commit: str
    plan_path: str
    plan_blob_id: str
    plan_digest: str
    byte_size: int

    def __post_init__(self) -> None:
        if self.schema != _PLAN_SOURCE_REFERENCE_SCHEMA:
            raise PolicyViolationError(
                f"plan source schema must be {_PLAN_SOURCE_REFERENCE_SCHEMA!r}"
            )
        _require_absolute_local_path(self.repository, "plan source repository")
        if "." in Path(self.repository).parts or ".." in Path(self.repository).parts:
            raise PolicyViolationError("plan source repository must be normalized")
        if not isinstance(self.source_revision, str) or not _REVISION.fullmatch(
            self.source_revision
        ):
            raise PolicyViolationError("plan source revision must be 40 lowercase hex")
        if self.baseline_commit != self.source_revision:
            raise PolicyViolationError("plan source baseline must equal source revision")
        _require_repository_path(self.plan_path, "plan source path")
        if not self.plan_path.endswith(".md"):
            raise PolicyViolationError("plan source path must name a Markdown document")
        if not isinstance(self.plan_blob_id, str) or not _GIT_OBJECT_ID.fullmatch(
            self.plan_blob_id
        ):
            raise PolicyViolationError("plan source blob ID must be a lowercase Git object ID")
        _require_digest(self.plan_digest, "plan source digest")
        if (
            isinstance(self.byte_size, bool)
            or not isinstance(self.byte_size, int)
            or not 1 <= self.byte_size <= _PLAN_DOCUMENT_BYTES
        ):
            raise PolicyViolationError(
                f"plan source byte size must be 1-{_PLAN_DOCUMENT_BYTES}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "repository": self.repository,
            "source_revision": self.source_revision,
            "baseline_commit": self.baseline_commit,
            "plan_path": self.plan_path,
            "plan_blob_id": self.plan_blob_id,
            "plan_digest": self.plan_digest,
            "byte_size": self.byte_size,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> PlanSourceReference:
        _require_exact_fields(
            raw,
            {
                "schema",
                "repository",
                "source_revision",
                "baseline_commit",
                "plan_path",
                "plan_blob_id",
                "plan_digest",
                "byte_size",
            },
            "plan source reference",
        )
        try:
            return cls(**raw)
        except TypeError as error:
            raise PolicyViolationError(f"invalid plan source reference: {error}") from error


@dataclass(frozen=True)
class PlanSourcePacket:
    """Canonical pending-phase authority derived only from a Git plan object."""

    schema: str
    reference: PlanSourceReference
    plan_id: str
    execution_slot: str
    phase_number: int
    phase_title: str
    verification_gate: str
    direct_dependencies: tuple[str, ...]
    predecessor_workflow_id: str | None

    def __post_init__(self) -> None:
        if self.schema != _PLAN_SOURCE_PACKET_SCHEMA:
            raise PolicyViolationError(
                f"plan source packet schema must be {_PLAN_SOURCE_PACKET_SCHEMA!r}"
            )
        if not isinstance(self.reference, PlanSourceReference):
            raise PolicyViolationError("plan source packet reference is invalid")
        _require_plan_id(self.plan_id, "plan source Plan ID")
        if not isinstance(self.execution_slot, str) or not _EXECUTION_SLOT.fullmatch(
            self.execution_slot
        ):
            raise PolicyViolationError("plan source execution slot must be P plus four digits")
        if not self.reference.plan_path.rsplit("/", 1)[-1].startswith(
            f"{self.execution_slot}-"
        ):
            raise PolicyViolationError("plan source filename slot does not match execution slot")
        if (
            isinstance(self.phase_number, bool)
            or not isinstance(self.phase_number, int)
            or self.phase_number < 0
        ):
            raise PolicyViolationError("plan source phase number must be non-negative")
        _require_plain_text(self.phase_title, "plan source phase title", 500)
        _require_plain_text(self.verification_gate, "plan source verification gate", 4_096)
        if (
            not isinstance(self.direct_dependencies, tuple)
            or len(self.direct_dependencies) > 32
            or len(set(self.direct_dependencies)) != len(self.direct_dependencies)
        ):
            raise PolicyViolationError(
                "plan source dependencies must be a duplicate-free tuple of at most 32"
            )
        for dependency in self.direct_dependencies:
            _require_plan_id(dependency, "plan source dependency")
        if self.predecessor_workflow_id is not None:
            _require_plain_text(
                self.predecessor_workflow_id,
                "plan source predecessor workflow ID",
                128,
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "reference": self.reference.to_dict(),
            "plan_id": self.plan_id,
            "execution_slot": self.execution_slot,
            "phase_number": self.phase_number,
            "phase_title": self.phase_title,
            "verification_gate": self.verification_gate,
            "direct_dependencies": list(self.direct_dependencies),
            "predecessor_workflow_id": self.predecessor_workflow_id,
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> PlanSourcePacket:
        _require_exact_fields(
            raw,
            {
                "schema",
                "reference",
                "plan_id",
                "execution_slot",
                "phase_number",
                "phase_title",
                "verification_gate",
                "direct_dependencies",
                "predecessor_workflow_id",
            },
            "plan source packet",
        )
        try:
            return cls(
                schema=raw["schema"],
                reference=PlanSourceReference.from_dict(raw["reference"]),
                plan_id=raw["plan_id"],
                execution_slot=raw["execution_slot"],
                phase_number=raw["phase_number"],
                phase_title=raw["phase_title"],
                verification_gate=raw["verification_gate"],
                direct_dependencies=tuple(raw["direct_dependencies"]),
                predecessor_workflow_id=raw["predecessor_workflow_id"],
            )
        except (KeyError, TypeError) as error:
            raise PolicyViolationError(f"invalid plan source packet: {error}") from error


class WorkflowStage(StrEnum):
    DEFINE = "define"
    PLAN = "plan"
    APPROVAL = "approval"
    IMPLEMENT = "implement"
    VERIFY = "verify"
    REVIEW = "review"
    DELIVER = "deliver"


class ActivationCategory(StrEnum):
    APPLICABLE = "applicable"
    DEFERRED = "deferred"
    NOT_APPLICABLE = "not_applicable"
    BLOCKED = "blocked"


class ActivationReferenceState(StrEnum):
    PENDING = "pending"
    FINALIZED = "finalized"


@dataclass(frozen=True)
class ActivationDecision:
    name: str
    skill_digest: str
    activation_mode: SkillActivationMode
    category: ActivationCategory
    rank: int | None
    matched_criteria: tuple[str, ...]
    evidence: tuple[str, ...]
    rationale: str
    condition: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.activation_mode, SkillActivationMode):
            raise PolicyViolationError("activation mode must be required or conditional")
        if not isinstance(self.category, ActivationCategory):
            raise PolicyViolationError("activation category is invalid")
        if not isinstance(self.name, str) or not _SKILL_NAME.fullmatch(self.name):
            raise PolicyViolationError("activation decision name must be a canonical skill slug")
        _require_digest(self.skill_digest, "activation skill digest")
        _require_bounded_strings(self.matched_criteria, "matched_criteria")
        _require_bounded_strings(self.evidence, "evidence")
        _require_bounded_text(self.rationale, "rationale", 1000)
        if self.category is ActivationCategory.APPLICABLE:
            if isinstance(self.rank, bool) or not isinstance(self.rank, int) or self.rank < 1:
                raise PolicyViolationError(
                    "applicable activation decisions require a positive rank"
                )
        elif self.rank is not None:
            raise PolicyViolationError("only applicable activation decisions may declare rank")
        if self.category is ActivationCategory.DEFERRED:
            _require_bounded_text(self.condition, "deferred condition", 500)
        elif self.condition is not None:
            raise PolicyViolationError("only deferred activation decisions may declare condition")
        if (
            self.activation_mode is SkillActivationMode.REQUIRED
            and self.category not in {ActivationCategory.APPLICABLE, ActivationCategory.BLOCKED}
        ):
            raise PolicyViolationError("required skills must be applicable or blocked")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "skill_digest": self.skill_digest,
            "activation_mode": self.activation_mode.value,
            "category": self.category.value,
            "rank": self.rank,
            "matched_criteria": list(self.matched_criteria),
            "evidence": list(self.evidence),
            "rationale": self.rationale,
            "condition": self.condition,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ActivationDecision:
        _require_exact_fields(
            raw,
            {
                "name", "skill_digest", "activation_mode", "category", "rank",
                "matched_criteria", "evidence", "rationale", "condition",
            },
            "activation decision",
        )
        try:
            return cls(
                name=raw["name"],
                skill_digest=raw["skill_digest"],
                activation_mode=SkillActivationMode(raw["activation_mode"]),
                category=ActivationCategory(raw["category"]),
                rank=raw["rank"],
                matched_criteria=tuple(raw["matched_criteria"]),
                evidence=tuple(raw["evidence"]),
                rationale=raw["rationale"],
                condition=raw["condition"],
            )
        except (KeyError, TypeError, ValueError) as error:
            raise PolicyViolationError(f"invalid activation decision: {error}") from error


@dataclass(frozen=True)
class ActivationManifest:
    schema: str
    workflow_id: str
    stage: WorkflowStage
    plan_revision: int
    pack: str
    pack_source_revision: str
    sequence: int
    supersedes_digest: str | None
    decisions: tuple[ActivationDecision, ...]
    policy_revision: int = 0
    constraints_digest: str | None = None

    def __post_init__(self) -> None:
        if self.schema != _ACTIVATION_SCHEMA:
            raise PolicyViolationError(f"activation schema must be {_ACTIVATION_SCHEMA!r}")
        _require_text(self.workflow_id, "activation workflow ID")
        if not isinstance(self.stage, WorkflowStage) or self.stage is WorkflowStage.APPROVAL:
            raise PolicyViolationError("approval has no skill activation manifest")
        _require_revision(self.plan_revision)
        _require_revision(self.policy_revision)
        if self.constraints_digest is not None:
            _require_digest(self.constraints_digest, "activation constraint digest")
        _require_text(self.pack, "activation pack")
        if not isinstance(self.pack_source_revision, str) or not _REVISION.fullmatch(
            self.pack_source_revision
        ):
            raise PolicyViolationError("activation pack source revision must be 40 lowercase hex")
        if (
            isinstance(self.sequence, bool)
            or not isinstance(self.sequence, int)
            or self.sequence < 1
        ):
            raise PolicyViolationError("activation sequence must be a positive integer")
        if self.supersedes_digest is not None:
            _require_digest(self.supersedes_digest, "superseded activation digest")
        if not isinstance(self.decisions, tuple) or not 1 <= len(self.decisions) <= 32:
            raise PolicyViolationError("activation manifest requires 1-32 decisions")
        names = [decision.name for decision in self.decisions]
        if len(names) != len(set(names)):
            raise PolicyViolationError("activation manifest cannot contain duplicate skills")
        ranks = [
            _applicable_rank(decision)
            for decision in self.decisions
            if decision.category is ActivationCategory.APPLICABLE
        ]
        if sorted(ranks) != list(range(1, len(ranks) + 1)):
            raise PolicyViolationError("applicable activation ranks must be unique and contiguous")

    @property
    def blocked(self) -> bool:
        return any(decision.category is ActivationCategory.BLOCKED for decision in self.decisions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "workflow_id": self.workflow_id,
            "stage": self.stage.value,
            "plan_revision": self.plan_revision,
            "policy_revision": self.policy_revision,
            "constraints_digest": self.constraints_digest,
            "pack": self.pack,
            "pack_source_revision": self.pack_source_revision,
            "sequence": self.sequence,
            "supersedes_digest": self.supersedes_digest,
            "decisions": [decision.to_dict() for decision in self.decisions],
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ActivationManifest:
        _require_exact_fields(
            raw,
            {
                "schema", "workflow_id", "stage", "plan_revision", "pack",
                "pack_source_revision", "sequence", "supersedes_digest", "decisions",
                "policy_revision", "constraints_digest",
            },
            "activation manifest",
        )
        try:
            return cls(
                schema=raw["schema"],
                workflow_id=raw["workflow_id"],
                stage=WorkflowStage(raw["stage"]),
                plan_revision=raw["plan_revision"],
                pack=raw["pack"],
                pack_source_revision=raw["pack_source_revision"],
                sequence=raw["sequence"],
                supersedes_digest=raw["supersedes_digest"],
                decisions=tuple(ActivationDecision.from_dict(row) for row in raw["decisions"]),
                policy_revision=raw["policy_revision"],
                constraints_digest=raw["constraints_digest"],
            )
        except (KeyError, TypeError, ValueError) as error:
            raise PolicyViolationError(f"invalid activation manifest: {error}") from error


@dataclass(frozen=True)
class ActivationManifestReference:
    stage: WorkflowStage
    plan_revision: int
    sequence: int
    path: str
    digest: str
    state: ActivationReferenceState
    blocked: bool
    supersedes_digest: str | None
    policy_revision: int = 0
    constraints_digest: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.stage, WorkflowStage) or self.stage is WorkflowStage.APPROVAL:
            raise PolicyViolationError("approval has no skill activation reference")
        if not isinstance(self.state, ActivationReferenceState):
            raise PolicyViolationError("activation reference state must be pending or finalized")
        _require_revision(self.plan_revision)
        _require_revision(self.policy_revision)
        if self.constraints_digest is not None:
            _require_digest(self.constraints_digest, "activation constraint digest")
        if (
            isinstance(self.sequence, bool)
            or not isinstance(self.sequence, int)
            or self.sequence < 1
        ):
            raise PolicyViolationError("activation sequence must be a positive integer")
        _require_text(self.path, "activation artifact path")
        _require_digest(self.digest, "activation artifact digest")
        if not isinstance(self.blocked, bool):
            raise PolicyViolationError("activation blocked must be a boolean")
        if self.supersedes_digest is not None:
            _require_digest(self.supersedes_digest, "superseded activation digest")

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage.value,
            "plan_revision": self.plan_revision,
            "policy_revision": self.policy_revision,
            "constraints_digest": self.constraints_digest,
            "sequence": self.sequence,
            "path": self.path,
            "digest": self.digest,
            "state": self.state.value,
            "blocked": self.blocked,
            "supersedes_digest": self.supersedes_digest,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ActivationManifestReference:
        _require_exact_fields(
            raw,
            {
                "stage", "plan_revision", "sequence", "path", "digest", "state",
                "blocked", "supersedes_digest", "policy_revision", "constraints_digest",
            },
            "activation reference",
        )
        try:
            return cls(
                stage=WorkflowStage(raw["stage"]),
                plan_revision=raw["plan_revision"],
                sequence=raw["sequence"],
                path=raw["path"],
                digest=raw["digest"],
                state=ActivationReferenceState(raw["state"]),
                blocked=raw["blocked"],
                supersedes_digest=raw["supersedes_digest"],
                policy_revision=raw["policy_revision"],
                constraints_digest=raw["constraints_digest"],
            )
        except (KeyError, TypeError, ValueError) as error:
            raise PolicyViolationError(f"invalid activation reference: {error}") from error


@dataclass(frozen=True)
class SkillDigest:
    name: str
    digest: str

    def __post_init__(self) -> None:
        _require_text(self.name, "skill name")
        _require_text(self.digest, "skill digest")

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "digest": self.digest}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> SkillDigest:
        return cls(name=raw["name"], digest=raw["digest"])


@dataclass(frozen=True)
class StageProfile:
    stage: WorkflowStage
    profile: str

    def __post_init__(self) -> None:
        if self.stage is WorkflowStage.APPROVAL:
            raise PolicyViolationError("approval uses the plan-stage profile")
        _require_text(self.profile, "stage profile")

    def to_dict(self) -> dict[str, str]:
        return {"stage": self.stage.value, "profile": self.profile}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> StageProfile:
        return cls(stage=WorkflowStage(raw["stage"]), profile=raw["profile"])


@dataclass(frozen=True)
class ApprovalSummary:
    headline: str
    changes: tuple[str, ...]
    affected_areas: tuple[str, ...]
    risks: tuple[str, ...]
    verification: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_plain_text(self.headline, "approval summary headline", 200)
        _require_plain_text_items(
            self.changes, "approval summary changes", minimum=1, maximum=12
        )
        _require_plain_text_items(
            self.affected_areas,
            "approval summary affected_areas",
            minimum=0,
            maximum=12,
        )
        _require_plain_text_items(
            self.risks, "approval summary risks", minimum=0, maximum=12
        )
        _require_plain_text_items(
            self.verification,
            "approval summary verification",
            minimum=1,
            maximum=12,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "headline": self.headline,
            "changes": list(self.changes),
            "affected_areas": list(self.affected_areas),
            "risks": list(self.risks),
            "verification": list(self.verification),
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ApprovalSummary:
        _require_exact_fields(
            raw,
            {"headline", "changes", "affected_areas", "risks", "verification"},
            "approval summary",
        )
        try:
            for field in ("changes", "affected_areas", "risks", "verification"):
                if not isinstance(raw[field], list):
                    raise PolicyViolationError(
                        f"approval summary {field} must be an array"
                    )
            return cls(
                headline=raw["headline"],
                changes=tuple(raw["changes"]),
                affected_areas=tuple(raw["affected_areas"]),
                risks=tuple(raw["risks"]),
                verification=tuple(raw["verification"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            if isinstance(error, PolicyViolationError):
                raise
            raise PolicyViolationError(f"invalid approval summary: {error}") from error

    def digest_for(self, source_digest: str) -> str:
        _require_text(source_digest, "approval summary source digest")
        payload = {"source_digest": source_digest, "summary": self.to_dict()}
        canonical = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()


@dataclass(frozen=True)
class ArtifactReference:
    stage: WorkflowStage
    plan_revision: int
    path: str
    digest: str
    recorded_at: datetime
    policy_revision: int = 0
    approval_summary: ApprovalSummary | None = None
    approval_summary_digest: str | None = None

    def __post_init__(self) -> None:
        _require_revision(self.plan_revision)
        _require_revision(self.policy_revision)
        _require_text(self.path, "artifact path")
        _require_text(self.digest, "artifact digest")
        _require_aware(self.recorded_at, "artifact recorded_at")
        if (self.approval_summary is None) != (self.approval_summary_digest is None):
            raise PolicyViolationError(
                "artifact approval summary and digest must both be present or absent"
            )
        if self.approval_summary is not None:
            if self.stage is not WorkflowStage.PLAN:
                raise PolicyViolationError("only plan artifacts may carry an approval summary")
            expected = self.approval_summary.digest_for(self.digest)
            if self.approval_summary_digest != expected:
                raise PolicyViolationError(
                    "artifact approval summary digest does not match the plan digest"
                )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "stage": self.stage.value,
            "plan_revision": self.plan_revision,
            "path": self.path,
            "digest": self.digest,
            "recorded_at": self.recorded_at.isoformat(),
            "policy_revision": self.policy_revision,
        }
        if self.approval_summary is not None:
            payload["approval_summary"] = self.approval_summary.to_dict()
            payload["approval_summary_digest"] = self.approval_summary_digest
        return payload

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ArtifactReference:
        required = {
            "stage", "plan_revision", "path", "digest", "recorded_at",
        }
        allowed = required | {
            "policy_revision", "approval_summary", "approval_summary_digest",
        }
        if not isinstance(raw, dict) or required - set(raw) or set(raw) - allowed:
            raise PolicyViolationError("artifact reference fields are invalid")
        return cls(
            stage=WorkflowStage(raw["stage"]),
            plan_revision=raw["plan_revision"],
            path=raw["path"],
            digest=raw["digest"],
            recorded_at=datetime.fromisoformat(raw["recorded_at"]),
            policy_revision=raw.get("policy_revision", 0),
            approval_summary=(
                ApprovalSummary.from_dict(raw["approval_summary"])
                if raw.get("approval_summary") is not None
                else None
            ),
            approval_summary_digest=raw.get("approval_summary_digest"),
        )


@dataclass(frozen=True)
class ConstraintSourceProvenance:
    name: str
    digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not _SKILL_NAME.fullmatch(self.name):
            raise PolicyViolationError("constraint source name must be a canonical skill slug")
        _require_digest(self.digest, "constraint source digest")

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "digest": self.digest}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ConstraintSourceProvenance:
        _require_exact_fields(raw, {"name", "digest"}, "constraint source provenance")
        return cls(name=raw["name"], digest=raw["digest"])


@dataclass(frozen=True)
class WorkflowConstraintsIdentity:
    policy_revision: int
    constraints_revision: int
    digest: str

    def __post_init__(self) -> None:
        _require_positive_revision(self.policy_revision, "policy revision")
        _require_positive_revision(self.constraints_revision, "constraint revision")
        _require_digest(self.digest, "constraint digest")

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_revision": self.policy_revision,
            "constraints_revision": self.constraints_revision,
            "digest": self.digest,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> WorkflowConstraintsIdentity:
        _require_exact_fields(
            raw,
            {"policy_revision", "constraints_revision", "digest"},
            "workflow constraint identity",
        )
        return cls(**raw)


@dataclass(frozen=True)
class WorkflowConstraintsArtifact:
    schema: str
    workflow_id: str
    identity: WorkflowConstraintsIdentity
    canonical_content: str
    source: ConstraintSourceProvenance | None = None

    def __post_init__(self) -> None:
        if self.schema != "daidala.workflow-constraints-artifact/v1":
            raise PolicyViolationError(
                "constraint artifact schema must be "
                "'daidala.workflow-constraints-artifact/v1'"
            )
        _require_text(self.workflow_id, "constraint artifact workflow ID")
        if not isinstance(self.identity, WorkflowConstraintsIdentity):
            raise PolicyViolationError("constraint artifact identity is invalid")
        _require_text(self.canonical_content, "canonical constraint content")
        try:
            parsed = json.loads(self.canonical_content)
        except json.JSONDecodeError as error:
            raise PolicyViolationError("canonical constraint content must be valid JSON") from error
        from .constraints import WorkflowConstraints

        constraints = WorkflowConstraints.from_dict(parsed)
        if self.canonical_content.encode("utf-8") != constraints.canonical_bytes():
            raise PolicyViolationError("constraint artifact content must be canonical JSON")
        content_digest = hashlib.sha256(self.canonical_content.encode("utf-8")).hexdigest()
        if self.identity.digest != content_digest:
            raise PolicyViolationError(
                "constraint artifact digest does not match canonical content"
            )
        if self.source is not None and not isinstance(self.source, ConstraintSourceProvenance):
            raise PolicyViolationError("constraint artifact source provenance is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "workflow_id": self.workflow_id,
            "identity": self.identity.to_dict(),
            "canonical_content": self.canonical_content,
            "source": self.source.to_dict() if self.source else None,
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> WorkflowConstraintsArtifact:
        _require_exact_fields(
            raw,
            {"schema", "workflow_id", "identity", "canonical_content", "source"},
            "workflow constraint artifact",
        )
        try:
            return cls(
                schema=raw["schema"],
                workflow_id=raw["workflow_id"],
                identity=WorkflowConstraintsIdentity.from_dict(raw["identity"]),
                canonical_content=raw["canonical_content"],
                source=(
                    ConstraintSourceProvenance.from_dict(raw["source"])
                    if raw["source"] is not None
                    else None
                ),
            )
        except (KeyError, TypeError, ValueError) as error:
            if isinstance(error, PolicyViolationError):
                raise
            raise PolicyViolationError(f"invalid constraint artifact: {error}") from error


@dataclass(frozen=True)
class WorkflowConstraintsReference:
    identity: WorkflowConstraintsIdentity
    path: str
    recorded_at: datetime
    source: ConstraintSourceProvenance | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.identity, WorkflowConstraintsIdentity):
            raise PolicyViolationError("constraint reference identity is invalid")
        _require_text(self.path, "constraint artifact path")
        _require_aware(self.recorded_at, "constraint recorded_at")
        if self.source is not None and not isinstance(self.source, ConstraintSourceProvenance):
            raise PolicyViolationError("constraint reference source provenance is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity.to_dict(),
            "path": self.path,
            "recorded_at": self.recorded_at.isoformat(),
            "source": self.source.to_dict() if self.source else None,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> WorkflowConstraintsReference:
        _require_exact_fields(
            raw,
            {"identity", "path", "recorded_at", "source"},
            "workflow constraint reference",
        )
        try:
            return cls(
                identity=WorkflowConstraintsIdentity.from_dict(raw["identity"]),
                path=raw["path"],
                recorded_at=datetime.fromisoformat(raw["recorded_at"]),
                source=(
                    ConstraintSourceProvenance.from_dict(raw["source"])
                    if raw["source"] is not None
                    else None
                ),
            )
        except (KeyError, TypeError, ValueError) as error:
            if isinstance(error, PolicyViolationError):
                raise
            raise PolicyViolationError(f"invalid constraint reference: {error}") from error


@dataclass(frozen=True)
class ApprovalRecord:
    plan_digest: str
    plan_revision: int
    decided_at: datetime
    constraints_revision: int | None = None
    constraints_digest: str | None = None
    plan_source_packet_digest: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.plan_digest, "approved plan digest")
        _require_revision(self.plan_revision)
        if (self.constraints_revision is None) != (self.constraints_digest is None):
            raise PolicyViolationError(
                "approved constraint revision and digest must both be present or absent"
            )
        if self.constraints_revision is not None:
            _require_positive_revision(
                self.constraints_revision, "approved constraint revision"
            )
        if self.constraints_digest is not None:
            _require_digest(self.constraints_digest, "approved constraint digest")
        if self.plan_source_packet_digest is not None:
            _require_digest(
                self.plan_source_packet_digest, "approved plan source packet digest"
            )
        _require_aware(self.decided_at, "approval decided_at")

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_digest": self.plan_digest,
            "plan_revision": self.plan_revision,
            "decided_at": self.decided_at.isoformat(),
            "constraints_revision": self.constraints_revision,
            "constraints_digest": self.constraints_digest,
            "plan_source_packet_digest": self.plan_source_packet_digest,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ApprovalRecord:
        return cls(
            plan_digest=raw["plan_digest"],
            plan_revision=raw["plan_revision"],
            decided_at=datetime.fromisoformat(raw["decided_at"]),
            constraints_revision=raw.get("constraints_revision"),
            constraints_digest=raw.get("constraints_digest"),
            plan_source_packet_digest=raw.get("plan_source_packet_digest"),
        )


@dataclass(frozen=True)
class VerificationEvidence:
    command: str
    exit_code: int
    output_reference: str
    output_digest: str
    plan_revision: int
    recorded_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.command, "verification command")
        if isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int):
            raise PolicyViolationError("verification exit_code must be an integer")
        _require_text(self.output_reference, "verification output reference")
        _require_text(self.output_digest, "verification output digest")
        _require_revision(self.plan_revision)
        _require_aware(self.recorded_at, "verification recorded_at")

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "exit_code": self.exit_code,
            "output_reference": self.output_reference,
            "output_digest": self.output_digest,
            "plan_revision": self.plan_revision,
            "recorded_at": self.recorded_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> VerificationEvidence:
        return cls(
            command=raw["command"],
            exit_code=raw["exit_code"],
            output_reference=raw["output_reference"],
            output_digest=raw["output_digest"],
            plan_revision=raw["plan_revision"],
            recorded_at=datetime.fromisoformat(raw["recorded_at"]),
        )


class ReviewOutcome(StrEnum):
    ACCEPTED = "accepted"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"


class ReviewDispositionAction(StrEnum):
    ACCEPT_DELIVERY = "accept_delivery"
    REQUEST_REVISION = "request_revision"
    REJECT_WORKFLOW = "reject_workflow"


@dataclass(frozen=True)
class ReviewFinding:
    finding_id: str
    severity: str
    blocking: bool
    title: str
    rationale: str
    evidence_digests: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.finding_id, str) or not re.fullmatch(
            r"[a-z][a-z0-9-]{0,63}", self.finding_id
        ):
            raise PolicyViolationError("review finding ID must be a canonical slug")
        if self.severity not in {"low", "medium", "high", "critical"}:
            raise PolicyViolationError("review finding severity is invalid")
        if not isinstance(self.blocking, bool):
            raise PolicyViolationError("review finding blocking must be a boolean")
        _require_bounded_text(self.title, "review finding title", 200)
        _require_bounded_text(self.rationale, "review finding rationale", 2000)
        if not isinstance(self.evidence_digests, tuple) or not 1 <= len(self.evidence_digests) <= 8:
            raise PolicyViolationError("review finding evidence must contain 1-8 digests")
        for digest in self.evidence_digests:
            _require_digest(digest, "review finding evidence digest")
        if tuple(sorted(set(self.evidence_digests))) != self.evidence_digests:
            raise PolicyViolationError(
                "review finding evidence digests must be sorted and unique"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.finding_id,
            "severity": self.severity,
            "blocking": self.blocking,
            "title": self.title,
            "rationale": self.rationale,
            "evidence_digests": list(self.evidence_digests),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ReviewFinding:
        _require_exact_fields(
            raw,
            {"id", "severity", "blocking", "title", "rationale", "evidence_digests"},
            "review finding",
        )
        return cls(
            finding_id=raw["id"],
            severity=raw["severity"],
            blocking=raw["blocking"],
            title=raw["title"],
            rationale=raw["rationale"],
            evidence_digests=tuple(raw["evidence_digests"]),
        )


@dataclass(frozen=True)
class ReviewRecord:
    workflow_id: str
    plan_digest: str
    plan_revision: int
    policy_revision: int
    constraints_revision: int | None
    constraints_digest: str | None
    implementation_digest: str
    verification_digests: tuple[str, ...]
    activation_digest: str
    outcome: ReviewOutcome
    summary: ApprovalSummary
    summary_digest: str
    findings: tuple[ReviewFinding, ...]
    recorded_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.workflow_id, "review workflow ID")
        _require_digest(self.plan_digest, "review plan digest")
        _require_revision(self.plan_revision)
        _require_revision(self.policy_revision)
        if (self.constraints_revision is None) != (self.constraints_digest is None):
            raise PolicyViolationError(
                "review constraint revision and digest must both be present or absent"
            )
        if self.constraints_revision is not None:
            _require_positive_revision(self.constraints_revision, "review constraint revision")
        if self.constraints_digest is not None:
            _require_digest(self.constraints_digest, "review constraint digest")
        _require_digest(self.implementation_digest, "review implementation digest")
        if not isinstance(self.verification_digests, tuple) or not self.verification_digests:
            raise PolicyViolationError("review requires passing verification digests")
        for digest in self.verification_digests:
            _require_digest(digest, "review verification digest")
        if tuple(sorted(set(self.verification_digests))) != self.verification_digests:
            raise PolicyViolationError("review verification digests must be sorted and unique")
        _require_digest(self.activation_digest, "review activation digest")
        if not isinstance(self.outcome, ReviewOutcome):
            raise PolicyViolationError("review outcome is invalid")
        if not isinstance(self.summary, ApprovalSummary):
            raise PolicyViolationError("review summary is invalid")
        _require_digest(self.summary_digest, "review summary digest")
        if self.summary_digest != self.summary.digest_for(self.implementation_digest):
            raise PolicyViolationError(
                "review summary digest does not match the implementation digest"
            )
        if not isinstance(self.findings, tuple) or len(self.findings) > 32:
            raise PolicyViolationError("review findings must contain at most 32 records")
        if any(not isinstance(finding, ReviewFinding) for finding in self.findings):
            raise PolicyViolationError("review findings must contain review finding records")
        finding_ids = [finding.finding_id for finding in self.findings]
        if finding_ids != sorted(set(finding_ids)):
            raise PolicyViolationError("review findings must have sorted unique IDs")
        if self.outcome is ReviewOutcome.ACCEPTED and any(
            finding.blocking for finding in self.findings
        ):
            raise PolicyViolationError("accepted review cannot contain blocking findings")
        _require_aware(self.recorded_at, "review recorded_at")

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "plan_digest": self.plan_digest,
            "plan_revision": self.plan_revision,
            "policy_revision": self.policy_revision,
            "constraints_revision": self.constraints_revision,
            "constraints_digest": self.constraints_digest,
            "implementation_digest": self.implementation_digest,
            "verification_digests": list(self.verification_digests),
            "activation_digest": self.activation_digest,
            "outcome": self.outcome.value,
            "summary": self.summary.to_dict(),
            "summary_digest": self.summary_digest,
            "findings": [finding.to_dict() for finding in self.findings],
            "recorded_at": self.recorded_at.isoformat(),
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ReviewRecord:
        _require_exact_fields(
            raw,
            {
                "workflow_id", "plan_digest", "plan_revision", "policy_revision",
                "constraints_revision", "constraints_digest", "implementation_digest",
                "verification_digests", "activation_digest", "outcome", "summary",
                "summary_digest", "findings", "recorded_at",
            },
            "review record",
        )
        return cls(
            workflow_id=raw["workflow_id"],
            plan_digest=raw["plan_digest"],
            plan_revision=raw["plan_revision"],
            policy_revision=raw["policy_revision"],
            constraints_revision=raw["constraints_revision"],
            constraints_digest=raw["constraints_digest"],
            implementation_digest=raw["implementation_digest"],
            verification_digests=tuple(raw["verification_digests"]),
            activation_digest=raw["activation_digest"],
            outcome=ReviewOutcome(raw["outcome"]),
            summary=ApprovalSummary.from_dict(raw["summary"]),
            summary_digest=raw["summary_digest"],
            findings=tuple(ReviewFinding.from_dict(row) for row in raw["findings"]),
            recorded_at=datetime.fromisoformat(raw["recorded_at"]),
        )


@dataclass(frozen=True)
class ReviewDisposition:
    review_digest: str
    implementation_digest: str
    verification_digests: tuple[str, ...]
    plan_digest: str
    plan_revision: int
    policy_revision: int
    constraints_revision: int | None
    constraints_digest: str | None
    action: ReviewDispositionAction
    actor: str
    rationale: str
    decided_at: datetime

    def __post_init__(self) -> None:
        for digest, label in (
            (self.review_digest, "disposition review digest"),
            (self.implementation_digest, "disposition implementation digest"),
            (self.plan_digest, "disposition plan digest"),
        ):
            _require_digest(digest, label)
        if not isinstance(self.verification_digests, tuple) or not self.verification_digests:
            raise PolicyViolationError("disposition requires verification digests")
        for digest in self.verification_digests:
            _require_digest(digest, "disposition verification digest")
        if tuple(sorted(set(self.verification_digests))) != self.verification_digests:
            raise PolicyViolationError("disposition verification digests must be sorted and unique")
        _require_revision(self.plan_revision)
        _require_revision(self.policy_revision)
        if (self.constraints_revision is None) != (self.constraints_digest is None):
            raise PolicyViolationError(
                "disposition constraint revision and digest must both be present or absent"
            )
        if self.constraints_revision is not None:
            _require_positive_revision(self.constraints_revision, "disposition constraint revision")
        if self.constraints_digest is not None:
            _require_digest(self.constraints_digest, "disposition constraint digest")
        if not isinstance(self.action, ReviewDispositionAction):
            raise PolicyViolationError("review disposition action is invalid")
        _require_bounded_text(self.actor, "review disposition actor", 200)
        _require_bounded_text(self.rationale, "review disposition rationale", 2000)
        _require_aware(self.decided_at, "review disposition decided_at")

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_digest": self.review_digest,
            "implementation_digest": self.implementation_digest,
            "verification_digests": list(self.verification_digests),
            "plan_digest": self.plan_digest,
            "plan_revision": self.plan_revision,
            "policy_revision": self.policy_revision,
            "constraints_revision": self.constraints_revision,
            "constraints_digest": self.constraints_digest,
            "action": self.action.value,
            "actor": self.actor,
            "rationale": self.rationale,
            "decided_at": self.decided_at.isoformat(),
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ReviewDisposition:
        _require_exact_fields(
            raw,
            {
                "review_digest", "implementation_digest", "verification_digests", "plan_digest",
                "plan_revision", "policy_revision", "constraints_revision", "constraints_digest",
                "action", "actor", "rationale", "decided_at",
            },
            "review disposition",
        )
        return cls(
            review_digest=raw["review_digest"],
            implementation_digest=raw["implementation_digest"],
            verification_digests=tuple(raw["verification_digests"]),
            plan_digest=raw["plan_digest"],
            plan_revision=raw["plan_revision"],
            policy_revision=raw["policy_revision"],
            constraints_revision=raw["constraints_revision"],
            constraints_digest=raw["constraints_digest"],
            action=ReviewDispositionAction(raw["action"]),
            actor=raw["actor"],
            rationale=raw["rationale"],
            decided_at=datetime.fromisoformat(raw["decided_at"]),
        )


@dataclass(frozen=True)
class PlanRevisionRequestReference:
    """Durable intent for one review-driven successor Plan revision."""

    workflow_id: str
    source_review_digest: str
    source_disposition_digest: str
    source_plan_digest: str
    source_plan_revision: int
    source_policy_revision: int
    source_constraints_revision: int | None
    source_constraints_digest: str | None
    implementation_digest: str
    verification_digests: tuple[str, ...]
    target_plan_revision: int
    preview_digest: str
    request_path: str
    request_digest: str
    successor_packet_path: str
    successor_packet_digest: str
    source_review_card_id: str
    source_card_ids: tuple[str, ...]
    actor: str
    normalized_feedback: str
    requested_at: datetime
    cards_archived_at: datetime | None = None
    worktree_released_at: datetime | None = None
    resolved_at: datetime | None = None

    def __post_init__(self) -> None:
        _require_text(self.workflow_id, "revision request workflow ID")
        for digest, label in (
            (self.source_review_digest, "revision request review digest"),
            (self.source_disposition_digest, "revision request disposition digest"),
            (self.source_plan_digest, "revision request plan digest"),
            (self.implementation_digest, "revision request implementation digest"),
            (self.preview_digest, "revision request preview digest"),
            (self.request_digest, "revision request artifact digest"),
            (self.successor_packet_digest, "successor packet digest"),
        ):
            _require_digest(digest, label)
        _require_revision(self.source_plan_revision)
        _require_revision(self.source_policy_revision)
        if self.target_plan_revision != self.source_plan_revision + 1:
            raise PolicyViolationError("revision request target must follow its source plan")
        if (self.source_constraints_revision is None) != (
            self.source_constraints_digest is None
        ):
            raise PolicyViolationError(
                "revision request constraint revision and digest must both be present or absent"
            )
        if self.source_constraints_revision is not None:
            _require_positive_revision(
                self.source_constraints_revision, "revision request constraint revision"
            )
        if self.source_constraints_digest is not None:
            _require_digest(
                self.source_constraints_digest, "revision request constraint digest"
            )
        if not isinstance(self.verification_digests, tuple) or not self.verification_digests:
            raise PolicyViolationError("revision request requires verification digests")
        for digest in self.verification_digests:
            _require_digest(digest, "revision request verification digest")
        if tuple(sorted(set(self.verification_digests))) != self.verification_digests:
            raise PolicyViolationError(
                "revision request verification digests must be sorted and unique"
            )
        _require_absolute_local_path(self.request_path, "revision request artifact path")
        _require_absolute_local_path(self.successor_packet_path, "successor packet path")
        if self.request_path == self.successor_packet_path:
            raise PolicyViolationError("revision request artifacts must use distinct paths")
        _require_bounded_text(self.source_review_card_id, "source review card ID", 500)
        if not isinstance(self.source_card_ids, tuple) or not self.source_card_ids:
            raise PolicyViolationError("revision request requires source card IDs")
        if len(self.source_card_ids) != len(set(self.source_card_ids)):
            raise PolicyViolationError("revision request source card IDs must be unique")
        for task_id in self.source_card_ids:
            _require_bounded_text(task_id, "revision request source card ID", 500)
        if self.source_review_card_id not in self.source_card_ids:
            raise PolicyViolationError("revision request source cards must include the review card")
        _require_bounded_text(self.actor, "revision request actor", 200)
        _require_bounded_text(self.normalized_feedback, "revision request feedback", 4096)
        _require_aware(self.requested_at, "revision request requested_at")
        for value, label in (
            (self.cards_archived_at, "revision request cards_archived_at"),
            (self.worktree_released_at, "revision request worktree_released_at"),
            (self.resolved_at, "revision request resolved_at"),
        ):
            if value is not None:
                _require_aware(value, label)
                if value < self.requested_at:
                    raise PolicyViolationError(f"{label} cannot precede the request")
        if self.worktree_released_at is not None and self.cards_archived_at is None:
            raise PolicyViolationError("worktree release requires archived source cards")
        if (
            self.worktree_released_at is not None
            and self.cards_archived_at is not None
            and self.worktree_released_at < self.cards_archived_at
        ):
            raise PolicyViolationError("worktree release cannot precede card archival")
        if self.resolved_at is not None and self.worktree_released_at is None:
            raise PolicyViolationError("resolved revision request requires worktree release")
        if (
            self.resolved_at is not None
            and self.worktree_released_at is not None
            and self.resolved_at < self.worktree_released_at
        ):
            raise PolicyViolationError("revision resolution cannot precede worktree release")

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "source_review_digest": self.source_review_digest,
            "source_disposition_digest": self.source_disposition_digest,
            "source_plan_digest": self.source_plan_digest,
            "source_plan_revision": self.source_plan_revision,
            "source_policy_revision": self.source_policy_revision,
            "source_constraints_revision": self.source_constraints_revision,
            "source_constraints_digest": self.source_constraints_digest,
            "implementation_digest": self.implementation_digest,
            "verification_digests": list(self.verification_digests),
            "target_plan_revision": self.target_plan_revision,
            "preview_digest": self.preview_digest,
            "request_path": self.request_path,
            "request_digest": self.request_digest,
            "successor_packet_path": self.successor_packet_path,
            "successor_packet_digest": self.successor_packet_digest,
            "source_review_card_id": self.source_review_card_id,
            "source_card_ids": list(self.source_card_ids),
            "actor": self.actor,
            "normalized_feedback": self.normalized_feedback,
            "requested_at": self.requested_at.isoformat(),
            "cards_archived_at": (
                self.cards_archived_at.isoformat() if self.cards_archived_at else None
            ),
            "worktree_released_at": (
                self.worktree_released_at.isoformat() if self.worktree_released_at else None
            ),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> PlanRevisionRequestReference:
        _require_exact_fields(
            raw,
            {
                "workflow_id", "source_review_digest", "source_disposition_digest",
                "source_plan_digest", "source_plan_revision", "source_policy_revision",
                "source_constraints_revision", "source_constraints_digest",
                "implementation_digest", "verification_digests", "target_plan_revision",
                "preview_digest", "request_path", "request_digest", "successor_packet_path",
                "successor_packet_digest", "source_review_card_id", "requested_at", "resolved_at",
                "source_card_ids", "actor", "normalized_feedback", "cards_archived_at",
                "worktree_released_at",
            },
            "plan revision request reference",
        )
        return cls(
            workflow_id=raw["workflow_id"],
            source_review_digest=raw["source_review_digest"],
            source_disposition_digest=raw["source_disposition_digest"],
            source_plan_digest=raw["source_plan_digest"],
            source_plan_revision=raw["source_plan_revision"],
            source_policy_revision=raw["source_policy_revision"],
            source_constraints_revision=raw["source_constraints_revision"],
            source_constraints_digest=raw["source_constraints_digest"],
            implementation_digest=raw["implementation_digest"],
            verification_digests=tuple(raw["verification_digests"]),
            target_plan_revision=raw["target_plan_revision"],
            preview_digest=raw["preview_digest"],
            request_path=raw["request_path"],
            request_digest=raw["request_digest"],
            successor_packet_path=raw["successor_packet_path"],
            successor_packet_digest=raw["successor_packet_digest"],
            source_review_card_id=raw["source_review_card_id"],
            source_card_ids=tuple(raw["source_card_ids"]),
            actor=raw["actor"],
            normalized_feedback=raw["normalized_feedback"],
            requested_at=datetime.fromisoformat(raw["requested_at"]),
            cards_archived_at=(
                datetime.fromisoformat(raw["cards_archived_at"])
                if raw["cards_archived_at"]
                else None
            ),
            worktree_released_at=(
                datetime.fromisoformat(raw["worktree_released_at"])
                if raw["worktree_released_at"]
                else None
            ),
            resolved_at=(
                datetime.fromisoformat(raw["resolved_at"]) if raw["resolved_at"] else None
            ),
        )


@dataclass(frozen=True)
class CardReference:
    stage: WorkflowStage
    plan_revision: int
    task_id: str
    idempotency_key: str
    board_slug: str = ""
    policy_revision: int = 0
    constraints_revision: int | None = None
    constraints_digest: str | None = None

    def __post_init__(self) -> None:
        _require_revision(self.plan_revision)
        _require_text(self.board_slug, "card board slug")
        _require_revision(self.policy_revision)
        if self.constraints_revision is not None:
            _require_positive_revision(self.constraints_revision, "card constraint revision")
        if (self.constraints_revision is None) != (self.constraints_digest is None):
            raise PolicyViolationError(
                "card constraint revision and digest must both be present or absent"
            )
        if self.constraints_digest is not None:
            _require_digest(self.constraints_digest, "card constraint digest")
        _require_text(self.task_id, "Kanban task ID")
        _require_text(self.idempotency_key, "Kanban idempotency key")

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage.value,
            "plan_revision": self.plan_revision,
            "board_slug": self.board_slug,
            "policy_revision": self.policy_revision,
            "constraints_revision": self.constraints_revision,
            "constraints_digest": self.constraints_digest,
            "task_id": self.task_id,
            "idempotency_key": self.idempotency_key,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> CardReference:
        return cls(
            stage=WorkflowStage(raw["stage"]),
            plan_revision=raw["plan_revision"],
            task_id=raw["task_id"],
            idempotency_key=raw["idempotency_key"],
            board_slug=raw["board_slug"],
            policy_revision=raw["policy_revision"],
            constraints_revision=raw["constraints_revision"],
            constraints_digest=raw["constraints_digest"],
        )


@dataclass(frozen=True)
class WorkflowLedger:
    workflow_id: str
    board_slug: str
    target_repository: str
    baseline_commit: str
    requested_goal: str
    pack_name: str
    pack_source_revision: str
    skill_digests: tuple[SkillDigest, ...]
    stage_profiles: tuple[StageProfile, ...]
    created_at: datetime
    updated_at: datetime
    policy_revision: int = 0
    constraint_references: tuple[WorkflowConstraintsReference, ...] = ()
    plan_revision: int = 0
    card_references: tuple[CardReference, ...] = ()
    worktree_path: str | None = None
    worktree_owned: bool = False
    artifacts: tuple[ArtifactReference, ...] = ()
    plan_source_packet: PlanSourcePacket | None = None
    approval: ApprovalRecord | None = None
    verification_evidence: tuple[VerificationEvidence, ...] = ()
    review: ReviewRecord | None = None
    review_disposition: ReviewDisposition | None = None
    verification_history: tuple[VerificationEvidence, ...] = ()
    review_history: tuple[ReviewRecord, ...] = ()
    review_disposition_history: tuple[ReviewDisposition, ...] = ()
    revision_requests: tuple[PlanRevisionRequestReference, ...] = ()
    activation_manifests: tuple[ActivationManifestReference, ...] = ()
    committed: bool = False
    pushed: bool = False

    def __post_init__(self) -> None:
        for value, label in (
            (self.workflow_id, "workflow ID"),
            (self.board_slug, "board slug"),
            (self.baseline_commit, "baseline commit"),
            (self.requested_goal, "requested goal"),
            (self.pack_name, "pack name"),
            (self.pack_source_revision, "pack source revision"),
        ):
            _require_text(value, label)
        _require_absolute_local_path(self.target_repository, "target repository")
        _require_aware(self.created_at, "created_at")
        _require_aware(self.updated_at, "updated_at")
        _require_revision(self.plan_revision)
        _require_revision(self.policy_revision)
        if self.updated_at < self.created_at:
            raise PolicyViolationError("updated_at cannot be before created_at")
        if self.committed or self.pushed:
            raise PolicyViolationError("Daidala delivery cannot commit or push")
        if self.plan_source_packet is not None:
            if not isinstance(self.plan_source_packet, PlanSourcePacket):
                raise PolicyViolationError("plan source packet must be a plan source packet")
            reference = self.plan_source_packet.reference
            if reference.repository != self.target_repository:
                raise PolicyViolationError(
                    "plan source repository must match the workflow target repository"
                )
            if reference.baseline_commit != self.baseline_commit:
                raise PolicyViolationError(
                    "plan source baseline must match the workflow baseline commit"
                )
            if self.card_for(WorkflowStage.DEFINE) is not None or self.card_for(
                WorkflowStage.PLAN
            ) is not None:
                raise PolicyViolationError(
                    "imported plan workflows cannot create define or plan cards"
                )

        if self.constraint_references:
            expected_revisions = list(range(1, len(self.constraint_references) + 1))
            constraint_revisions = [
                row.identity.constraints_revision for row in self.constraint_references
            ]
            policy_revisions = [
                row.identity.policy_revision for row in self.constraint_references
            ]
            if constraint_revisions != expected_revisions:
                raise PolicyViolationError("constraint references must have contiguous revisions")
            if policy_revisions != expected_revisions:
                raise PolicyViolationError("constraint policy revisions must be contiguous")
            if self.policy_revision != policy_revisions[-1]:
                raise PolicyViolationError(
                    "policy revision must match the current constraint reference"
                )
            paths = [row.path for row in self.constraint_references]
            if len(paths) != len(set(paths)):
                raise PolicyViolationError("constraint references must use immutable paths")
        elif self.policy_revision != 0:
            raise PolicyViolationError("policy revision requires a constraint reference")

        skill_names = [skill.name for skill in self.skill_digests]
        if not skill_names:
            raise PolicyViolationError("workflow requires exact skill digests")
        if len(skill_names) != len(set(skill_names)):
            raise PolicyViolationError("workflow cannot contain duplicate skill digests")

        profile_stages = [row.stage for row in self.stage_profiles]
        expected_profile_stages = set(WorkflowStage) - {WorkflowStage.APPROVAL}
        if set(profile_stages) != expected_profile_stages or len(profile_stages) != len(
            expected_profile_stages
        ):
            raise PolicyViolationError("workflow requires exactly one profile per executable stage")

        card_keys = [
            (card.stage, card.plan_revision, card.policy_revision)
            for card in self.card_references
        ]
        if len(card_keys) != len(set(card_keys)):
            raise PolicyViolationError("workflow cannot contain duplicate stage card references")
        task_ids = [card.task_id for card in self.card_references]
        if len(task_ids) != len(set(task_ids)):
            raise PolicyViolationError("workflow cannot reuse a Kanban task ID")
        idempotency_keys = [card.idempotency_key for card in self.card_references]
        if len(idempotency_keys) != len(set(idempotency_keys)):
            raise PolicyViolationError("workflow cannot reuse a Kanban idempotency key")

        artifact_keys = [
            (row.stage, row.plan_revision, row.policy_revision) for row in self.artifacts
        ]
        if len(artifact_keys) != len(set(artifact_keys)):
            raise PolicyViolationError("workflow cannot contain duplicate stage artifacts")

        if self.worktree_path is None:
            if self.worktree_owned:
                raise PolicyViolationError("owned worktree requires a path")
        else:
            _require_absolute_local_path(self.worktree_path, "worktree path")
            if Path(self.worktree_path) == Path(self.target_repository):
                raise PolicyViolationError("worktree path must differ from target repository")
            if not self.worktree_owned:
                raise PolicyViolationError("worktree path requires Daidala ownership")

        plan = self.artifact_for(WorkflowStage.PLAN)
        if self.approval is not None:
            if (
                plan is None
                or self.approval.plan_digest != plan.digest
                or self.approval.plan_revision != self.plan_revision
                or self.approval.constraints_revision != self.current_constraints_revision
                or self.approval.constraints_digest != self.current_constraints_digest
            ):
                raise PolicyViolationError(
                    "approval must match the current plan revision and digest"
                )
            if self.plan_source_packet is not None and (
                self.approval.plan_source_packet_digest != self.plan_source_packet.digest
            ):
                raise PolicyViolationError(
                    "imported plan approval must match the admitted plan source packet"
                )
            if (
                self.plan_source_packet is None
                and self.approval.plan_source_packet_digest is not None
            ):
                raise PolicyViolationError(
                    "generated plan approval cannot name a plan source packet"
                )

        for evidence in self.verification_evidence:
            if evidence.plan_revision != self.plan_revision:
                raise PolicyViolationError(
                    "verification evidence must match the current plan revision"
                )

        if self.review is not None:
            implementation = self.artifact_for(WorkflowStage.IMPLEMENT)
            plan = self.artifact_for(WorkflowStage.PLAN)
            activation = self.activation_for(WorkflowStage.REVIEW)
            passing = tuple(
                sorted(
                    {row.output_digest for row in self.verification_evidence if row.exit_code == 0}
                )
            )
            review = self.review
            if (
                implementation is None or plan is None or activation is None
                or review.workflow_id != self.workflow_id
                or review.plan_digest != plan.digest
                or review.plan_revision != self.plan_revision
                or review.policy_revision != self.policy_revision
                or review.constraints_revision != self.current_constraints_revision
                or review.constraints_digest != self.current_constraints_digest
                or review.implementation_digest != implementation.digest
                or review.verification_digests != passing
                or review.activation_digest != activation.digest
            ):
                raise PolicyViolationError("review must match the current evidence tuple")
            allowed_evidence = {review.implementation_digest, *review.verification_digests}
            if any(
                not set(finding.evidence_digests) <= allowed_evidence
                for finding in review.findings
            ):
                raise PolicyViolationError("review finding evidence is not ledger-bound")
        if self.review_disposition is not None:
            review = self.review
            disposition = self.review_disposition
            if review is None or (
                disposition.review_digest != review.digest
                or disposition.implementation_digest != review.implementation_digest
                or disposition.verification_digests != review.verification_digests
                or disposition.plan_digest != review.plan_digest
                or disposition.plan_revision != review.plan_revision
                or disposition.policy_revision != review.policy_revision
                or disposition.constraints_revision != review.constraints_revision
                or disposition.constraints_digest != review.constraints_digest
            ):
                raise PolicyViolationError("review disposition must match the current review tuple")

        historical_reviews = [row.digest for row in self.review_history]
        if len(historical_reviews) != len(set(historical_reviews)):
            raise PolicyViolationError("workflow cannot contain duplicate historical reviews")
        historical_dispositions = [row.digest for row in self.review_disposition_history]
        if len(historical_dispositions) != len(set(historical_dispositions)):
            raise PolicyViolationError("workflow cannot contain duplicate historical dispositions")
        if self.review is not None and self.review.digest in set(historical_reviews):
            raise PolicyViolationError("current review cannot also be historical")
        if (
            self.review_disposition is not None
            and self.review_disposition.digest in set(historical_dispositions)
        ):
            raise PolicyViolationError("current disposition cannot also be historical")
        known_reviews = {row.digest for row in self.review_history}
        if self.review is not None:
            known_reviews.add(self.review.digest)
        if any(
            row.review_digest not in known_reviews for row in self.review_disposition_history
        ):
            raise PolicyViolationError("historical disposition has no ledger review")
        verification_keys = [
            (row.plan_revision, row.output_digest, row.recorded_at)
            for row in (*self.verification_history, *self.verification_evidence)
        ]
        if len(verification_keys) != len(set(verification_keys)):
            raise PolicyViolationError("workflow cannot contain duplicate verification history")
        request_targets = [row.target_plan_revision for row in self.revision_requests]
        if len(request_targets) != len(set(request_targets)):
            raise PolicyViolationError("workflow cannot contain duplicate plan revision requests")
        if any(row.workflow_id != self.workflow_id for row in self.revision_requests):
            raise PolicyViolationError("plan revision request workflow ID does not match")
        if any(row.target_plan_revision > self.plan_revision + 1 for row in self.revision_requests):
            raise PolicyViolationError("plan revision request targets an unreachable revision")
        pending = [row for row in self.revision_requests if row.resolved_at is None]
        if len(pending) > 1:
            raise PolicyViolationError("workflow cannot contain multiple pending revision requests")

        activation_groups: dict[
            tuple[WorkflowStage, int, int, str | None],
            list[ActivationManifestReference],
        ] = {}
        for reference in self.activation_manifests:
            if reference.plan_revision > self.plan_revision or (
                reference.stage is WorkflowStage.DEFINE and reference.plan_revision != 0
            ):
                raise PolicyViolationError("activation reference has an invalid stage revision")
            activation_groups.setdefault(
                (
                    reference.stage,
                    reference.plan_revision,
                    reference.policy_revision,
                    reference.constraints_digest,
                ),
                [],
            ).append(reference)
        digests = [reference.digest for reference in self.activation_manifests]
        if len(digests) != len(set(digests)):
            raise PolicyViolationError("workflow cannot contain duplicate activation digests")
        for references in activation_groups.values():
            for index, reference in enumerate(references, start=1):
                if reference.sequence != index:
                    raise PolicyViolationError(
                        "activation references must have contiguous sequences"
                    )
                expected = None if index == 1 else references[index - 2].digest
                if reference.supersedes_digest != expected:
                    raise PolicyViolationError("activation references must form a linear chain")

    @property
    def current_plan_digest(self) -> str | None:
        plan = self.artifact_for(WorkflowStage.PLAN)
        return plan.digest if plan else None

    @property
    def current_constraints(self) -> WorkflowConstraintsReference | None:
        return self.constraint_references[-1] if self.constraint_references else None

    @property
    def current_constraints_digest(self) -> str | None:
        current = self.current_constraints
        return current.identity.digest if current else None

    @property
    def current_constraints_revision(self) -> int | None:
        current = self.current_constraints
        return current.identity.constraints_revision if current else None

    def artifact_for(self, stage: WorkflowStage) -> ArtifactReference | None:
        revision = 0 if stage is WorkflowStage.DEFINE else self.plan_revision
        return next(
            (
                artifact
                for artifact in self.artifacts
                if artifact.stage is stage and artifact.plan_revision == revision
                and artifact.policy_revision == self.policy_revision
            ),
            None,
        )

    def card_for(self, stage: WorkflowStage) -> CardReference | None:
        revision = 0 if stage is WorkflowStage.DEFINE else self.plan_revision
        return next(
            (
                card
                for card in self.card_references
                if card.stage is stage
                and card.plan_revision == revision
                and card.board_slug == self.board_slug
                and card.policy_revision == self.policy_revision
                and card.constraints_revision == self.current_constraints_revision
                and card.constraints_digest == self.current_constraints_digest
            ),
            None,
        )

    def profile_for(self, stage: WorkflowStage) -> str:
        selected = WorkflowStage.PLAN if stage is WorkflowStage.APPROVAL else stage
        return next(row.profile for row in self.stage_profiles if row.stage is selected)

    def activation_revision_for(self, stage: WorkflowStage) -> int:
        if stage is WorkflowStage.APPROVAL:
            raise PolicyViolationError("approval has no skill activation revision")
        return 0 if stage is WorkflowStage.DEFINE else self.plan_revision

    @property
    def pending_revision_request(self) -> PlanRevisionRequestReference | None:
        return next(
            (row for row in reversed(self.revision_requests) if row.resolved_at is None),
            None,
        )

    def activation_for(self, stage: WorkflowStage) -> ActivationManifestReference | None:
        revision = self.activation_revision_for(stage)
        references = [
            reference
            for reference in self.activation_manifests
            if reference.stage is stage
            and reference.plan_revision == revision
            and reference.policy_revision == self.policy_revision
            and reference.constraints_digest == self.current_constraints_digest
        ]
        if not references or references[-1].state is not ActivationReferenceState.FINALIZED:
            return None
        return references[-1]

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "workflow_id": self.workflow_id,
            "board_slug": self.board_slug,
            "target_repository": self.target_repository,
            "baseline_commit": self.baseline_commit,
            "requested_goal": self.requested_goal,
            "pack_name": self.pack_name,
            "pack_source_revision": self.pack_source_revision,
            "skill_digests": [row.to_dict() for row in self.skill_digests],
            "stage_profiles": [row.to_dict() for row in self.stage_profiles],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "policy_revision": self.policy_revision,
            "constraint_references": [
                row.to_dict() for row in self.constraint_references
            ],
            "plan_revision": self.plan_revision,
            "card_references": [row.to_dict() for row in self.card_references],
            "worktree_path": self.worktree_path,
            "worktree_owned": self.worktree_owned,
            "artifacts": [row.to_dict() for row in self.artifacts],
            "approval": self.approval.to_dict() if self.approval else None,
            "verification_evidence": [
                row.to_dict() for row in self.verification_evidence
            ],
            "review": self.review.to_dict() if self.review else None,
            "review_disposition": (
                self.review_disposition.to_dict() if self.review_disposition else None
            ),
            "verification_history": [row.to_dict() for row in self.verification_history],
            "review_history": [row.to_dict() for row in self.review_history],
            "review_disposition_history": [
                row.to_dict() for row in self.review_disposition_history
            ],
            "revision_requests": [row.to_dict() for row in self.revision_requests],
            "activation_manifests": [
                row.to_dict() for row in self.activation_manifests
            ],
            "committed": self.committed,
            "pushed": self.pushed,
        }
        if self.plan_source_packet is not None:
            payload["plan_source_packet"] = self.plan_source_packet.to_dict()
        return payload

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> WorkflowLedger:
        try:
            expected = {
                "workflow_id",
                "board_slug",
                "target_repository",
                "baseline_commit",
                "requested_goal",
                "pack_name",
                "pack_source_revision",
                "skill_digests",
                "stage_profiles",
                "created_at",
                "updated_at",
                "policy_revision",
                "constraint_references",
                "plan_revision",
                "card_references",
                "worktree_path",
                "worktree_owned",
                "artifacts",
                "plan_source_packet",
                "approval",
                "verification_evidence",
                "review",
                "review_disposition",
                "verification_history",
                "review_history",
                "review_disposition_history",
                "revision_requests",
                "activation_manifests",
                "committed",
                "pushed",
            }
            unknown = sorted(set(raw) - expected)
            if unknown:
                raise PolicyViolationError(
                    f"unknown serialized workflow ledger fields: {', '.join(unknown)}"
                )
            return cls(
                workflow_id=raw["workflow_id"],
                board_slug=raw["board_slug"],
                target_repository=raw["target_repository"],
                baseline_commit=raw["baseline_commit"],
                requested_goal=raw["requested_goal"],
                pack_name=raw["pack_name"],
                pack_source_revision=raw["pack_source_revision"],
                skill_digests=tuple(
                    SkillDigest.from_dict(row) for row in raw["skill_digests"]
                ),
                stage_profiles=tuple(
                    StageProfile.from_dict(row) for row in raw["stage_profiles"]
                ),
                created_at=datetime.fromisoformat(raw["created_at"]),
                updated_at=datetime.fromisoformat(raw["updated_at"]),
                policy_revision=raw.get("policy_revision", 0),
                constraint_references=tuple(
                    WorkflowConstraintsReference.from_dict(row)
                    for row in raw.get("constraint_references", [])
                ),
                plan_revision=raw["plan_revision"],
                card_references=tuple(
                    CardReference.from_dict(row) for row in raw["card_references"]
                ),
                worktree_path=raw.get("worktree_path"),
                worktree_owned=raw["worktree_owned"],
                artifacts=tuple(
                    ArtifactReference.from_dict(row) for row in raw["artifacts"]
                ),
                plan_source_packet=(
                    PlanSourcePacket.from_dict(raw["plan_source_packet"])
                    if raw.get("plan_source_packet")
                    else None
                ),
                approval=(
                    ApprovalRecord.from_dict(raw["approval"])
                    if raw.get("approval")
                    else None
                ),
                verification_evidence=tuple(
                    VerificationEvidence.from_dict(row)
                    for row in raw["verification_evidence"]
                ),
                review=ReviewRecord.from_dict(raw["review"]) if raw.get("review") else None,
                review_disposition=(
                    ReviewDisposition.from_dict(raw["review_disposition"])
                    if raw.get("review_disposition")
                    else None
                ),
                verification_history=tuple(
                    VerificationEvidence.from_dict(row)
                    for row in raw.get("verification_history", [])
                ),
                review_history=tuple(
                    ReviewRecord.from_dict(row) for row in raw.get("review_history", [])
                ),
                review_disposition_history=tuple(
                    ReviewDisposition.from_dict(row)
                    for row in raw.get("review_disposition_history", [])
                ),
                revision_requests=tuple(
                    PlanRevisionRequestReference.from_dict(row)
                    for row in raw.get("revision_requests", [])
                ),
                activation_manifests=tuple(
                    ActivationManifestReference.from_dict(row)
                    for row in raw["activation_manifests"]
                ),
                committed=raw["committed"],
                pushed=raw["pushed"],
            )
        except (KeyError, TypeError, ValueError) as error:
            if isinstance(error, PolicyViolationError):
                raise
            raise PolicyViolationError(f"invalid serialized workflow ledger: {error}") from error


def _require_text(value: str | None, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise PolicyViolationError(f"{label} must be a non-empty string")


def _require_bounded_text(value: str | None, label: str, maximum: int) -> None:
    _require_text(value, label)
    if not isinstance(value, str):
        raise PolicyViolationError(f"{label} must be a non-empty string")
    if len(value) > maximum:
        raise PolicyViolationError(f"{label} must be at most {maximum} characters")


def _require_bounded_strings(values: tuple[str, ...], label: str) -> None:
    if not isinstance(values, tuple) or not 1 <= len(values) <= 8:
        raise PolicyViolationError(f"{label} must contain 1-8 strings")
    for value in values:
        _require_bounded_text(value, label, 500)


def _require_plain_text(value: str, label: str, maximum_bytes: int) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise PolicyViolationError(f"{label} must be trimmed non-empty plain text")
    if any(ord(character) < 32 or 127 <= ord(character) < 160 for character in value):
        raise PolicyViolationError(f"{label} must be trimmed non-empty plain text")
    if len(value.encode("utf-8")) > maximum_bytes:
        raise PolicyViolationError(f"{label} must be at most {maximum_bytes} UTF-8 bytes")


def _require_plain_text_items(
    values: tuple[str, ...],
    label: str,
    *,
    minimum: int,
    maximum: int,
) -> None:
    if not isinstance(values, tuple) or not minimum <= len(values) <= maximum:
        raise PolicyViolationError(f"{label} must contain {minimum}-{maximum} items")
    for value in values:
        _require_plain_text(value, label, 500)


def _require_digest(value: str, label: str) -> None:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise PolicyViolationError(f"{label} must be a lowercase SHA-256 digest")


def _require_exact_fields(raw: Any, expected: set[str], label: str) -> None:
    if not isinstance(raw, dict):
        raise PolicyViolationError(f"{label} must be an object")
    missing = sorted(expected - set(raw))
    unknown = sorted(set(raw) - expected)
    if missing or unknown:
        detail = []
        if missing:
            detail.append(f"missing: {', '.join(missing)}")
        if unknown:
            detail.append(f"unknown: {', '.join(unknown)}")
        raise PolicyViolationError(f"{label} fields are invalid ({'; '.join(detail)})")


def _applicable_rank(decision: ActivationDecision) -> int:
    if decision.rank is None:
        raise PolicyViolationError("applicable activation decisions require a rank")
    return decision.rank


def _require_revision(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PolicyViolationError("plan revision must be a non-negative integer")


def _require_positive_revision(value: int, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise PolicyViolationError(f"{label} must be a positive integer")


def _require_aware(value: datetime, label: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise PolicyViolationError(f"{label} must be timezone-aware")


def _require_absolute_local_path(value: str, label: str) -> None:
    _require_text(value, label)
    if "://" in value or value.startswith("git@") or not Path(value).is_absolute():
        raise PolicyViolationError(f"{label} must be an absolute local path")


def _require_repository_path(value: Any, label: str) -> None:
    _require_text(value, label)
    if not isinstance(value, str):
        raise PolicyViolationError(f"{label} must be a string")
    path = PurePosixPath(value)
    if (
        not path.parts
        or path.is_absolute()
        or "." in path.parts
        or ".." in path.parts
        or path.as_posix() != value
    ):
        raise PolicyViolationError(f"{label} must be a normalized repository-relative path")


def _require_plan_id(value: Any, label: str) -> None:
    if not isinstance(value, str) or not _PLAN_ID.fullmatch(value):
        raise PolicyViolationError(f"{label} must be a canonical plan ID")