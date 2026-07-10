"""Deterministic workflow creation and state transitions."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path

from .errors import InvalidTransitionError, InvalidWorkflowError
from .state import (
    ApprovalRecord,
    ArtifactReference,
    VerificationEvidence,
    WorkflowStage,
    WorkflowState,
    WorkflowStatus,
)


def new_workflow(
    *,
    workflow_id: str,
    target_repository: str,
    requested_goal: str,
    pack_name: str,
    pack_source_revision: str,
    created_at: datetime,
) -> WorkflowState:
    """Create an immutable draft without touching the target repository."""
    return WorkflowState(
        workflow_id=workflow_id,
        target_repository=target_repository,
        requested_goal=requested_goal,
        pack_name=pack_name,
        pack_source_revision=pack_source_revision,
        current_stage=WorkflowStage.DEFINE,
        status=WorkflowStatus.DRAFT,
        created_at=created_at,
        updated_at=created_at,
    )


def validate_target(
    state: WorkflowState,
    *,
    target_is_clean: bool,
    baseline_commit: str | None,
    validated_at: datetime,
) -> WorkflowState:
    """Record deterministic target validation and block dirty targets."""
    if (
        state.target_is_clean is target_is_clean
        and state.baseline_commit == baseline_commit
        and state.target_validated_at == validated_at
    ):
        return state
    _require_state(
        state,
        status=WorkflowStatus.DRAFT,
        stage=WorkflowStage.DEFINE,
        recorded_at=validated_at,
    )
    if not isinstance(target_is_clean, bool):
        raise InvalidWorkflowError("target_is_clean must be a boolean")

    if not target_is_clean:
        return replace(
            state,
            status=WorkflowStatus.BLOCKED,
            target_is_clean=False,
            target_validated_at=validated_at,
            updated_at=validated_at,
            failure_reason="target repository is dirty",
        )
    if not isinstance(baseline_commit, str) or not baseline_commit.strip():
        raise InvalidWorkflowError("baseline commit must be a non-empty string")
    return replace(
        state,
        status=WorkflowStatus.RUNNING,
        target_is_clean=True,
        baseline_commit=baseline_commit.strip(),
        target_validated_at=validated_at,
        updated_at=validated_at,
    )


def record_artifact(
    state: WorkflowState,
    *,
    stage: WorkflowStage,
    path: str,
    digest: str,
    recorded_at: datetime,
) -> WorkflowState:
    """Record the current stage artifact and advance without skipping the gate."""
    candidate = ArtifactReference(stage=stage, path=path, digest=digest, recorded_at=recorded_at)
    existing = state.artifact_for(stage)
    if existing == candidate:
        return state
    if existing is not None:
        raise InvalidTransitionError(f"stage {stage.value!r} already has a different artifact")
    _require_state(
        state,
        status=WorkflowStatus.RUNNING,
        stage=stage,
        recorded_at=recorded_at,
    )

    next_stage: WorkflowStage
    next_status = WorkflowStatus.RUNNING
    if stage is WorkflowStage.DEFINE:
        next_stage = WorkflowStage.PLAN
    elif stage is WorkflowStage.PLAN:
        next_stage = WorkflowStage.PLAN
        next_status = WorkflowStatus.AWAITING_APPROVAL
    elif stage is WorkflowStage.IMPLEMENT:
        next_stage = WorkflowStage.VERIFY
    elif stage is WorkflowStage.REVIEW:
        next_stage = WorkflowStage.DELIVER
    elif stage is WorkflowStage.DELIVER:
        next_stage = WorkflowStage.DELIVER
        next_status = WorkflowStatus.COMPLETED
    else:
        raise InvalidTransitionError("verification requires structured verification evidence")

    return replace(
        state,
        artifacts=(*state.artifacts, candidate),
        current_stage=next_stage,
        status=next_status,
        updated_at=recorded_at,
    )


def approve_plan(
    state: WorkflowState,
    *,
    plan_digest: str,
    decided_at: datetime,
) -> WorkflowState:
    """Bind approval to the exact current plan digest."""
    if state.approval is not None and state.approval.plan_digest == plan_digest:
        return state
    if state.status is not WorkflowStatus.AWAITING_APPROVAL:
        raise InvalidTransitionError("plan approval requires awaiting_approval status")
    _require_not_before(state, decided_at)
    plan = state.artifact_for(WorkflowStage.PLAN)
    if plan is None or plan.digest != plan_digest:
        raise InvalidTransitionError("approval must match the current plan digest")
    return replace(
        state,
        status=WorkflowStatus.APPROVED,
        current_stage=WorkflowStage.IMPLEMENT,
        approval=ApprovalRecord(plan_digest=plan_digest, decided_at=decided_at),
        updated_at=decided_at,
    )


def modify_plan(
    state: WorkflowState,
    *,
    path: str,
    digest: str,
    modified_at: datetime,
) -> WorkflowState:
    """Replace the plan artifact and invalidate any existing approval."""
    if state.status not in {WorkflowStatus.AWAITING_APPROVAL, WorkflowStatus.APPROVED}:
        raise InvalidTransitionError("plan modification requires a planned workflow")
    _require_not_before(state, modified_at)
    replacement = ArtifactReference(
        stage=WorkflowStage.PLAN,
        path=path,
        digest=digest,
        recorded_at=modified_at,
    )
    artifacts = tuple(
        replacement if artifact.stage is WorkflowStage.PLAN else artifact
        for artifact in state.artifacts
    )
    if not any(artifact.stage is WorkflowStage.PLAN for artifact in state.artifacts):
        raise InvalidTransitionError("plan modification requires a plan artifact")
    if state.artifact_for(WorkflowStage.PLAN) == replacement and state.approval is None:
        return state
    return replace(
        state,
        artifacts=artifacts,
        approval=None,
        status=WorkflowStatus.AWAITING_APPROVAL,
        current_stage=WorkflowStage.PLAN,
        worktree_path=None,
        updated_at=modified_at,
    )


def start_implementation(
    state: WorkflowState,
    *,
    worktree_path: str,
    started_at: datetime,
) -> WorkflowState:
    """Start implementation only after approval in a distinct local worktree."""
    if (
        state.status is WorkflowStatus.RUNNING
        and state.current_stage is WorkflowStage.IMPLEMENT
        and state.worktree_path == worktree_path
    ):
        return state
    if state.status is not WorkflowStatus.APPROVED:
        raise InvalidTransitionError("implementation requires approval")
    _require_not_before(state, started_at)
    if not isinstance(worktree_path, str) or not Path(worktree_path).is_absolute():
        raise InvalidWorkflowError("worktree path must be an absolute local path")
    if Path(worktree_path) == Path(state.target_repository):
        raise InvalidWorkflowError("worktree path must differ from target repository")
    return replace(
        state,
        status=WorkflowStatus.RUNNING,
        worktree_path=worktree_path,
        updated_at=started_at,
    )


def record_verification(
    state: WorkflowState,
    *,
    command: str,
    exit_code: int,
    output_reference: str,
    recorded_at: datetime,
) -> WorkflowState:
    """Record real verification evidence and block on failure."""
    evidence = VerificationEvidence(
        command=command,
        exit_code=exit_code,
        output_reference=output_reference,
        recorded_at=recorded_at,
    )
    if evidence in state.verification_evidence:
        return state
    _require_state(
        state,
        status=WorkflowStatus.RUNNING,
        stage=WorkflowStage.VERIFY,
        recorded_at=recorded_at,
    )
    evidence_rows = (*state.verification_evidence, evidence)
    if exit_code != 0:
        return replace(
            state,
            verification_evidence=evidence_rows,
            status=WorkflowStatus.BLOCKED,
            updated_at=recorded_at,
            failure_reason=f"verification failed with exit code {exit_code}",
        )
    return replace(
        state,
        verification_evidence=evidence_rows,
        current_stage=WorkflowStage.REVIEW,
        updated_at=recorded_at,
    )


def fail_workflow(
    state: WorkflowState,
    *,
    reason: str,
    failed_at: datetime,
) -> WorkflowState:
    """Record a terminal runtime failure."""
    if state.status is WorkflowStatus.FAILED and state.failure_reason == reason:
        return state
    _require_nonterminal(state)
    _require_not_before(state, failed_at)
    return replace(
        state,
        status=WorkflowStatus.FAILED,
        failure_reason=reason,
        updated_at=failed_at,
    )


def cancel_workflow(
    state: WorkflowState,
    *,
    reason: str,
    cancelled_at: datetime,
) -> WorkflowState:
    """Record terminal operator cancellation."""
    if state.status is WorkflowStatus.CANCELLED and state.failure_reason == reason:
        return state
    _require_nonterminal(state)
    _require_not_before(state, cancelled_at)
    return replace(
        state,
        status=WorkflowStatus.CANCELLED,
        failure_reason=reason,
        updated_at=cancelled_at,
    )


def _require_state(
    state: WorkflowState,
    *,
    status: WorkflowStatus,
    stage: WorkflowStage,
    recorded_at: datetime,
) -> None:
    if state.status is not status or state.current_stage is not stage:
        raise InvalidTransitionError(
            f"transition requires {status.value}/{stage.value}; "
            f"workflow is {state.status.value}/{state.current_stage.value}"
        )
    if recorded_at < state.updated_at:
        raise InvalidTransitionError(
            f"recorded_at cannot be before updated_at {state.updated_at.isoformat()}"
        )


def _require_nonterminal(state: WorkflowState) -> None:
    if state.status in {
        WorkflowStatus.BLOCKED,
        WorkflowStatus.FAILED,
        WorkflowStatus.COMPLETED,
        WorkflowStatus.CANCELLED,
    }:
        raise InvalidTransitionError(f"workflow is terminal: {state.status.value}")


def _require_not_before(state: WorkflowState, recorded_at: datetime) -> None:
    if recorded_at < state.updated_at:
        raise InvalidTransitionError(
            f"recorded_at cannot be before updated_at {state.updated_at.isoformat()}"
        )
