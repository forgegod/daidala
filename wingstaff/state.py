"""Immutable Wingstaff policy and artifact ledger types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import PolicyViolationError


class WorkflowStage(StrEnum):
    DEFINE = "define"
    PLAN = "plan"
    APPROVAL = "approval"
    IMPLEMENT = "implement"
    VERIFY = "verify"
    REVIEW = "review"
    DELIVER = "deliver"


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

    def __post_init__(self) -> None:
        _require_revision(self.plan_revision)
        _require_text(self.task_id, "Kanban task ID")
        _require_text(self.idempotency_key, "Kanban idempotency key")

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage.value,
            "plan_revision": self.plan_revision,
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
    plan_revision: int = 0
    card_references: tuple[CardReference, ...] = ()
    worktree_path: str | None = None
    worktree_owned: bool = False
    artifacts: tuple[ArtifactReference, ...] = ()
    approval: ApprovalRecord | None = None
    verification_evidence: tuple[VerificationEvidence, ...] = ()
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
        if self.updated_at < self.created_at:
            raise PolicyViolationError("updated_at cannot be before created_at")
        if self.committed or self.pushed:
            raise PolicyViolationError("Wingstaff delivery cannot commit or push")

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
            (card.stage, card.plan_revision) for card in self.card_references
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

    @property
    def current_plan_digest(self) -> str | None:
        plan = self.artifact_for(WorkflowStage.PLAN)
        return plan.digest if plan else None

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
                if card.stage is stage and card.plan_revision == revision
            ),
            None,
        )

    def profile_for(self, stage: WorkflowStage) -> str:
        selected = WorkflowStage.PLAN if stage is WorkflowStage.APPROVAL else stage
        return next(row.profile for row in self.stage_profiles if row.stage is selected)

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
            "plan_revision": self.plan_revision,
            "card_references": [row.to_dict() for row in self.card_references],
            "worktree_path": self.worktree_path,
            "worktree_owned": self.worktree_owned,
            "artifacts": [row.to_dict() for row in self.artifacts],
            "approval": self.approval.to_dict() if self.approval else None,
            "verification_evidence": [
                row.to_dict() for row in self.verification_evidence
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
                "plan_revision",
                "card_references",
                "worktree_path",
                "worktree_owned",
                "artifacts",
                "approval",
                "verification_evidence",
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


def _require_revision(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PolicyViolationError("plan revision must be a non-negative integer")


def _require_aware(value: datetime, label: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise PolicyViolationError(f"{label} must be timezone-aware")


def _require_absolute_local_path(value: str, label: str) -> None:
    _require_text(value, label)
    if "://" in value or value.startswith("git@") or not Path(value).is_absolute():
        raise PolicyViolationError(f"{label} must be an absolute local path")