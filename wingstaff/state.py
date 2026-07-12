"""Immutable Wingstaff policy and artifact ledger types."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import PolicyViolationError
from .packs import SkillActivationMode

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_REVISION = re.compile(r"^[0-9a-f]{40}$")
_SKILL_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,127}$")
_ACTIVATION_SCHEMA = "wingstaff.skill-activation/v1"


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
class ArtifactReference:
    stage: WorkflowStage
    plan_revision: int
    path: str
    digest: str
    recorded_at: datetime

    def __post_init__(self) -> None:
        _require_revision(self.plan_revision)
        _require_text(self.path, "artifact path")
        _require_text(self.digest, "artifact digest")
        _require_aware(self.recorded_at, "artifact recorded_at")

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage.value,
            "plan_revision": self.plan_revision,
            "path": self.path,
            "digest": self.digest,
            "recorded_at": self.recorded_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ArtifactReference:
        return cls(
            stage=WorkflowStage(raw["stage"]),
            plan_revision=raw["plan_revision"],
            path=raw["path"],
            digest=raw["digest"],
            recorded_at=datetime.fromisoformat(raw["recorded_at"]),
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
        if self.schema != "wingstaff.workflow-constraints-artifact/v1":
            raise PolicyViolationError(
                "constraint artifact schema must be "
                "'wingstaff.workflow-constraints-artifact/v1'"
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

    def __post_init__(self) -> None:
        _require_text(self.plan_digest, "approved plan digest")
        _require_revision(self.plan_revision)
        _require_aware(self.decided_at, "approval decided_at")

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_digest": self.plan_digest,
            "plan_revision": self.plan_revision,
            "decided_at": self.decided_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ApprovalRecord:
        return cls(
            plan_digest=raw["plan_digest"],
            plan_revision=raw["plan_revision"],
            decided_at=datetime.fromisoformat(raw["decided_at"]),
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
    approval: ApprovalRecord | None = None
    verification_evidence: tuple[VerificationEvidence, ...] = ()
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
            raise PolicyViolationError("Wingstaff delivery cannot commit or push")

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

        artifact_keys = [(row.stage, row.plan_revision) for row in self.artifacts]
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
                raise PolicyViolationError("worktree path requires Wingstaff ownership")

        plan = self.artifact_for(WorkflowStage.PLAN)
        if self.approval is not None:
            if (
                plan is None
                or self.approval.plan_digest != plan.digest
                or self.approval.plan_revision != self.plan_revision
            ):
                raise PolicyViolationError(
                    "approval must match the current plan revision and digest"
                )

        for evidence in self.verification_evidence:
            if evidence.plan_revision != self.plan_revision:
                raise PolicyViolationError(
                    "verification evidence must match the current plan revision"
                )

        activation_groups: dict[
            tuple[WorkflowStage, int], list[ActivationManifestReference]
        ] = {}
        for reference in self.activation_manifests:
            if reference.plan_revision > self.plan_revision or (
                reference.stage in {WorkflowStage.DEFINE, WorkflowStage.PLAN}
                and reference.plan_revision != 0
            ):
                raise PolicyViolationError("activation reference has an invalid stage revision")
            activation_groups.setdefault(
                (reference.stage, reference.plan_revision), []
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
            ),
            None,
        )

    def card_for(self, stage: WorkflowStage) -> CardReference | None:
        revision = 0 if stage in {WorkflowStage.DEFINE, WorkflowStage.PLAN} else self.plan_revision
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
        return 0 if stage in {WorkflowStage.DEFINE, WorkflowStage.PLAN} else self.plan_revision

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
        return {
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
            "activation_manifests": [
                row.to_dict() for row in self.activation_manifests
            ],
            "committed": self.committed,
            "pushed": self.pushed,
        }

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
                "approval",
                "verification_evidence",
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
                approval=(
                    ApprovalRecord.from_dict(raw["approval"])
                    if raw.get("approval")
                    else None
                ),
                verification_evidence=tuple(
                    VerificationEvidence.from_dict(row)
                    for row in raw["verification_evidence"]
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