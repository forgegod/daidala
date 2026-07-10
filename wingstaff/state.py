"""Immutable workflow state and serialization types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import InvalidWorkflowError


class WorkflowStatus(StrEnum):
    DRAFT = "draft"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    BLOCKED = "blocked"
    FAILED = "failed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class WorkflowStage(StrEnum):
    DEFINE = "define"
    PLAN = "plan"
    IMPLEMENT = "implement"
    VERIFY = "verify"
    REVIEW = "review"
    DELIVER = "deliver"


class DeliveryMode(StrEnum):
    REVIEWED_DIFF_ONLY = "reviewed_diff_only"


@dataclass(frozen=True)
class ArtifactReference:
    stage: WorkflowStage
    path: str
    digest: str
    recorded_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.path, "artifact path")
        _require_text(self.digest, "artifact digest")
        _require_aware(self.recorded_at, "artifact recorded_at")

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage.value,
            "path": self.path,
            "digest": self.digest,
            "recorded_at": self.recorded_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ArtifactReference:
        return cls(
            stage=WorkflowStage(raw["stage"]),
            path=raw["path"],
            digest=raw["digest"],
            recorded_at=datetime.fromisoformat(raw["recorded_at"]),
        )


@dataclass(frozen=True)
class ApprovalRecord:
    plan_digest: str
    decided_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.plan_digest, "approved plan digest")
        _require_aware(self.decided_at, "approval decided_at")

    def to_dict(self) -> dict[str, str]:
        return {
            "plan_digest": self.plan_digest,
            "decided_at": self.decided_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ApprovalRecord:
        return cls(
            plan_digest=raw["plan_digest"],
            decided_at=datetime.fromisoformat(raw["decided_at"]),
        )


@dataclass(frozen=True)
class VerificationEvidence:
    command: str
    exit_code: int
    output_reference: str
    recorded_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.command, "verification command")
        if isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int):
            raise InvalidWorkflowError("verification exit_code must be an integer")
        _require_text(self.output_reference, "verification output reference")
        _require_aware(self.recorded_at, "verification recorded_at")

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "exit_code": self.exit_code,
            "output_reference": self.output_reference,
            "recorded_at": self.recorded_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> VerificationEvidence:
        return cls(
            command=raw["command"],
            exit_code=raw["exit_code"],
            output_reference=raw["output_reference"],
            recorded_at=datetime.fromisoformat(raw["recorded_at"]),
        )


@dataclass(frozen=True)
class WorkflowState:
    workflow_id: str
    target_repository: str
    requested_goal: str
    pack_name: str
    pack_source_revision: str
    current_stage: WorkflowStage
    status: WorkflowStatus
    created_at: datetime
    updated_at: datetime
    baseline_commit: str | None = None
    target_is_clean: bool | None = None
    target_validated_at: datetime | None = None
    worktree_path: str | None = None
    delivery_mode: DeliveryMode = DeliveryMode.REVIEWED_DIFF_ONLY
    artifacts: tuple[ArtifactReference, ...] = ()
    approval: ApprovalRecord | None = None
    verification_evidence: tuple[VerificationEvidence, ...] = ()
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        for value, label in (
            (self.workflow_id, "workflow ID"),
            (self.requested_goal, "requested goal"),
            (self.pack_name, "pack name"),
            (self.pack_source_revision, "pack source revision"),
        ):
            _require_text(value, label)
        _require_absolute_local_path(self.target_repository, "target repository")
        _require_aware(self.created_at, "created_at")
        _require_aware(self.updated_at, "updated_at")
        if self.updated_at < self.created_at:
            raise InvalidWorkflowError("updated_at cannot be before created_at")
        if self.delivery_mode is not DeliveryMode.REVIEWED_DIFF_ONLY:
            raise InvalidWorkflowError("delivery mode must be reviewed_diff_only")

        if self.target_validated_at is not None:
            _require_aware(self.target_validated_at, "target_validated_at")
        if self.target_is_clean is True:
            _require_text(self.baseline_commit, "baseline commit")
            if self.target_validated_at is None:
                raise InvalidWorkflowError("clean target requires target_validated_at")
        if self.target_is_clean is False and self.target_validated_at is None:
            raise InvalidWorkflowError("dirty target requires target_validated_at")

        if self.worktree_path is not None:
            _require_absolute_local_path(self.worktree_path, "worktree path")
            if Path(self.worktree_path) == Path(self.target_repository):
                raise InvalidWorkflowError("worktree path must differ from target repository")

        stages = [artifact.stage for artifact in self.artifacts]
        if len(stages) != len(set(stages)):
            raise InvalidWorkflowError("workflow cannot contain duplicate stage artifacts")

        plan = self.artifact_for(WorkflowStage.PLAN)
        if self.approval is not None:
            if plan is None or self.approval.plan_digest != plan.digest:
                raise InvalidWorkflowError("approval must match the current plan digest")

        if self.status is WorkflowStatus.AWAITING_APPROVAL:
            if self.current_stage is not WorkflowStage.PLAN or plan is None:
                raise InvalidWorkflowError("awaiting approval requires a plan artifact")
            if self.approval is not None:
                raise InvalidWorkflowError("awaiting approval cannot retain approval")
        if self.status is WorkflowStatus.APPROVED:
            if self.current_stage is not WorkflowStage.IMPLEMENT or self.approval is None:
                raise InvalidWorkflowError("approved workflow requires plan approval")
        if self.status is WorkflowStatus.RUNNING and self.current_stage in {
            WorkflowStage.IMPLEMENT,
            WorkflowStage.VERIFY,
            WorkflowStage.REVIEW,
            WorkflowStage.DELIVER,
        }:
            if self.approval is None or self.worktree_path is None:
                raise InvalidWorkflowError("post-gate execution requires approval and worktree")
        if self.status is WorkflowStatus.COMPLETED:
            if self.current_stage is not WorkflowStage.DELIVER:
                raise InvalidWorkflowError("completed workflow must be at deliver")

        needs_reason = self.status in {
            WorkflowStatus.BLOCKED,
            WorkflowStatus.FAILED,
            WorkflowStatus.CANCELLED,
        }
        if needs_reason:
            _require_text(self.failure_reason, "failure reason")
        elif self.failure_reason is not None:
            raise InvalidWorkflowError("active workflow cannot have a failure reason")

    def artifact_for(self, stage: WorkflowStage) -> ArtifactReference | None:
        return next((artifact for artifact in self.artifacts if artifact.stage is stage), None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "target_repository": self.target_repository,
            "requested_goal": self.requested_goal,
            "pack_name": self.pack_name,
            "pack_source_revision": self.pack_source_revision,
            "current_stage": self.current_stage.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "baseline_commit": self.baseline_commit,
            "target_is_clean": self.target_is_clean,
            "target_validated_at": (
                self.target_validated_at.isoformat() if self.target_validated_at else None
            ),
            "worktree_path": self.worktree_path,
            "delivery_mode": self.delivery_mode.value,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "approval": self.approval.to_dict() if self.approval else None,
            "verification_evidence": [
                evidence.to_dict() for evidence in self.verification_evidence
            ],
            "failure_reason": self.failure_reason,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> WorkflowState:
        try:
            return cls(
                workflow_id=raw["workflow_id"],
                target_repository=raw["target_repository"],
                requested_goal=raw["requested_goal"],
                pack_name=raw["pack_name"],
                pack_source_revision=raw["pack_source_revision"],
                current_stage=WorkflowStage(raw["current_stage"]),
                status=WorkflowStatus(raw["status"]),
                created_at=datetime.fromisoformat(raw["created_at"]),
                updated_at=datetime.fromisoformat(raw["updated_at"]),
                baseline_commit=raw.get("baseline_commit"),
                target_is_clean=raw.get("target_is_clean"),
                target_validated_at=(
                    datetime.fromisoformat(raw["target_validated_at"])
                    if raw.get("target_validated_at")
                    else None
                ),
                worktree_path=raw.get("worktree_path"),
                delivery_mode=DeliveryMode(raw["delivery_mode"]),
                artifacts=tuple(ArtifactReference.from_dict(row) for row in raw["artifacts"]),
                approval=(
                    ApprovalRecord.from_dict(raw["approval"])
                    if raw.get("approval")
                    else None
                ),
                verification_evidence=tuple(
                    VerificationEvidence.from_dict(row)
                    for row in raw["verification_evidence"]
                ),
                failure_reason=raw.get("failure_reason"),
            )
        except (KeyError, TypeError, ValueError) as error:
            if isinstance(error, InvalidWorkflowError):
                raise
            raise InvalidWorkflowError(f"invalid serialized workflow: {error}") from error


def _require_text(value: str | None, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise InvalidWorkflowError(f"{label} must be a non-empty string")


def _require_aware(value: datetime, label: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise InvalidWorkflowError(f"{label} must be timezone-aware")


def _require_absolute_local_path(value: str, label: str) -> None:
    _require_text(value, label)
    if "://" in value or not Path(value).is_absolute():
        raise InvalidWorkflowError(f"{label} must be an absolute local path")
