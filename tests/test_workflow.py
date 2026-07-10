from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from wingstaff.errors import InvalidTransitionError, InvalidWorkflowError
from wingstaff.state import DeliveryMode, WorkflowStage, WorkflowState, WorkflowStatus
from wingstaff.workflow import (
    approve_plan,
    cancel_workflow,
    fail_workflow,
    modify_plan,
    new_workflow,
    record_artifact,
    record_verification,
    start_implementation,
    validate_target,
)

NOW = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)
TARGET = "/tmp/wingstaff-target"
WORKTREE = "/tmp/wingstaff-worktrees/workflow-1"


def make_draft() -> WorkflowState:
    return new_workflow(
        workflow_id="workflow-1",
        target_repository=TARGET,
        requested_goal="Fix the deliberately failing test",
        pack_name="addyosmani",
        pack_source_revision="0123456789abcdef",
        created_at=NOW,
    )


def make_awaiting_approval() -> WorkflowState:
    state = validate_target(
        make_draft(),
        target_is_clean=True,
        baseline_commit="abcdef123456",
        validated_at=NOW + timedelta(minutes=1),
    )
    state = record_artifact(
        state,
        stage=WorkflowStage.DEFINE,
        path="artifacts/define.md",
        digest="define-v1",
        recorded_at=NOW + timedelta(minutes=2),
    )
    return record_artifact(
        state,
        stage=WorkflowStage.PLAN,
        path="artifacts/plan.md",
        digest="plan-v1",
        recorded_at=NOW + timedelta(minutes=3),
    )


def test_new_workflow_has_fixed_local_delivery_contract() -> None:
    state = make_draft()

    assert state.status is WorkflowStatus.DRAFT
    assert state.current_stage is WorkflowStage.DEFINE
    assert state.target_repository == TARGET
    assert state.delivery_mode is DeliveryMode.REVIEWED_DIFF_ONLY
    assert state.created_at == state.updated_at == NOW


@pytest.mark.parametrize(
    "target",
    ["owner/repository", "https://example.invalid/repository.git", "git@example.invalid:repo.git"],
)
def test_new_workflow_rejects_nonlocal_or_noncanonical_targets(target: str) -> None:
    with pytest.raises(InvalidWorkflowError, match="absolute local path"):
        new_workflow(
            workflow_id="workflow-1",
            target_repository=target,
            requested_goal="goal",
            pack_name="addyosmani",
            pack_source_revision="revision",
            created_at=NOW,
        )


def test_dirty_target_blocks_forward_progress() -> None:
    state = validate_target(
        make_draft(),
        target_is_clean=False,
        baseline_commit=None,
        validated_at=NOW + timedelta(minutes=1),
    )

    assert state.status is WorkflowStatus.BLOCKED
    assert state.target_is_clean is False
    assert state.failure_reason == "target repository is dirty"
    with pytest.raises(InvalidTransitionError):
        record_artifact(
            state,
            stage=WorkflowStage.DEFINE,
            path="artifacts/define.md",
            digest="define-v1",
            recorded_at=NOW + timedelta(minutes=2),
        )
    # BLOCKED is terminal; a blocked workflow cannot be cancelled. The operator
    # must create a new workflow to retry against the now-cleaned target.


def test_happy_path_cannot_skip_gate_and_completes_with_reviewed_diff() -> None:
    state = make_awaiting_approval()

    with pytest.raises(InvalidTransitionError, match="approval"):
        start_implementation(
            state,
            worktree_path=WORKTREE,
            started_at=NOW + timedelta(minutes=4),
        )

    state = approve_plan(
        state,
        plan_digest="plan-v1",
        decided_at=NOW + timedelta(minutes=4),
    )
    state = start_implementation(
        state,
        worktree_path=WORKTREE,
        started_at=NOW + timedelta(minutes=5),
    )
    state = record_artifact(
        state,
        stage=WorkflowStage.IMPLEMENT,
        path="artifacts/implementation.diff",
        digest="diff-v1",
        recorded_at=NOW + timedelta(minutes=6),
    )
    state = record_verification(
        state,
        command="pytest",
        exit_code=0,
        output_reference="artifacts/pytest.txt",
        recorded_at=NOW + timedelta(minutes=7),
    )
    state = record_artifact(
        state,
        stage=WorkflowStage.REVIEW,
        path="artifacts/review.md",
        digest="review-v1",
        recorded_at=NOW + timedelta(minutes=8),
    )
    state = record_artifact(
        state,
        stage=WorkflowStage.DELIVER,
        path="artifacts/delivery.md",
        digest="delivery-v1",
        recorded_at=NOW + timedelta(minutes=9),
    )

    assert state.status is WorkflowStatus.COMPLETED
    assert state.current_stage is WorkflowStage.DELIVER
    assert state.delivery_mode is DeliveryMode.REVIEWED_DIFF_ONLY
    assert [artifact.stage for artifact in state.artifacts] == [
        WorkflowStage.DEFINE,
        WorkflowStage.PLAN,
        WorkflowStage.IMPLEMENT,
        WorkflowStage.REVIEW,
        WorkflowStage.DELIVER,
    ]
    assert state.verification_evidence[0].exit_code == 0


def test_approval_must_match_current_plan_and_is_invalidated_by_modification() -> None:
    state = make_awaiting_approval()

    with pytest.raises(InvalidTransitionError, match="current plan digest"):
        approve_plan(
            state,
            plan_digest="stale-plan",
            decided_at=NOW + timedelta(minutes=4),
        )

    approved = approve_plan(
        state,
        plan_digest="plan-v1",
        decided_at=NOW + timedelta(minutes=4),
    )
    modified = modify_plan(
        approved,
        path="artifacts/plan.md",
        digest="plan-v2",
        modified_at=NOW + timedelta(minutes=5),
    )

    assert modified.status is WorkflowStatus.AWAITING_APPROVAL
    assert modified.current_stage is WorkflowStage.PLAN
    assert modified.approval is None
    assert modified.artifact_for(WorkflowStage.PLAN).digest == "plan-v2"


def test_implementation_requires_fresh_absolute_worktree() -> None:
    state = approve_plan(
        make_awaiting_approval(),
        plan_digest="plan-v1",
        decided_at=NOW + timedelta(minutes=4),
    )

    for path in (TARGET, "relative-worktree"):
        with pytest.raises(InvalidWorkflowError, match="worktree"):
            start_implementation(
                state,
                worktree_path=path,
                started_at=NOW + timedelta(minutes=5),
            )


def test_failed_verification_blocks_completion() -> None:
    state = approve_plan(
        make_awaiting_approval(),
        plan_digest="plan-v1",
        decided_at=NOW + timedelta(minutes=4),
    )
    state = start_implementation(
        state,
        worktree_path=WORKTREE,
        started_at=NOW + timedelta(minutes=5),
    )
    state = record_artifact(
        state,
        stage=WorkflowStage.IMPLEMENT,
        path="artifacts/implementation.diff",
        digest="diff-v1",
        recorded_at=NOW + timedelta(minutes=6),
    )
    state = record_verification(
        state,
        command="pytest",
        exit_code=1,
        output_reference="artifacts/pytest.txt",
        recorded_at=NOW + timedelta(minutes=7),
    )

    assert state.status is WorkflowStatus.BLOCKED
    assert state.failure_reason == "verification failed with exit code 1"
    with pytest.raises(InvalidTransitionError):
        record_artifact(
            state,
            stage=WorkflowStage.REVIEW,
            path="artifacts/review.md",
            digest="review-v1",
            recorded_at=NOW + timedelta(minutes=8),
        )


def test_repeated_completed_transitions_are_idempotent() -> None:
    draft = make_draft()
    validated = validate_target(
        draft,
        target_is_clean=True,
        baseline_commit="abcdef123456",
        validated_at=NOW + timedelta(minutes=1),
    )
    assert (
        validate_target(
            validated,
            target_is_clean=True,
            baseline_commit="abcdef123456",
            validated_at=NOW + timedelta(minutes=1),
        )
        is validated
    )

    defined = record_artifact(
        validated,
        stage=WorkflowStage.DEFINE,
        path="artifacts/define.md",
        digest="define-v1",
        recorded_at=NOW + timedelta(minutes=2),
    )
    assert (
        record_artifact(
            defined,
            stage=WorkflowStage.DEFINE,
            path="artifacts/define.md",
            digest="define-v1",
            recorded_at=NOW + timedelta(minutes=2),
        )
        is defined
    )


def test_invalid_transition_and_guessed_artifact_are_rejected() -> None:
    with pytest.raises(InvalidTransitionError):
        approve_plan(make_draft(), plan_digest="plan-v1", decided_at=NOW)

    state = validate_target(
        make_draft(),
        target_is_clean=True,
        baseline_commit="abcdef123456",
        validated_at=NOW + timedelta(minutes=1),
    )
    with pytest.raises(InvalidWorkflowError, match="artifact path"):
        record_artifact(
            state,
            stage=WorkflowStage.DEFINE,
            path="",
            digest="define-v1",
            recorded_at=NOW + timedelta(minutes=2),
        )


def test_terminal_transitions_and_serialization_round_trip() -> None:
    cancelled = cancel_workflow(
        make_draft(),
        reason="operator cancelled",
        cancelled_at=NOW + timedelta(minutes=1),
    )
    assert cancel_workflow(
        cancelled,
        reason="operator cancelled",
        cancelled_at=NOW + timedelta(minutes=1),
    ) is cancelled
    with pytest.raises(InvalidTransitionError):
        fail_workflow(
            cancelled,
            reason="late failure",
            failed_at=NOW + timedelta(minutes=2),
        )

    failed = fail_workflow(
        make_draft(),
        reason="pack validation failed",
        failed_at=NOW + timedelta(minutes=1),
    )
    assert failed.status is WorkflowStatus.FAILED

    state = make_awaiting_approval()
    restored = WorkflowState.from_dict(state.to_dict())
    assert restored == state


def test_state_rejects_naive_or_reversed_timestamps() -> None:
    with pytest.raises(InvalidWorkflowError, match="timezone-aware"):
        replace(make_draft(), updated_at=datetime(2026, 7, 10, 12, 1))
    with pytest.raises(InvalidWorkflowError, match="before created_at"):
        replace(make_draft(), updated_at=NOW - timedelta(seconds=1))

    validated = validate_target(
        make_draft(),
        target_is_clean=True,
        baseline_commit="abcdef123456",
        validated_at=NOW + timedelta(minutes=2),
    )
    with pytest.raises(InvalidTransitionError, match="before updated_at"):
        record_artifact(
            validated,
            stage=WorkflowStage.DEFINE,
            path="artifacts/define.md",
            digest="define-v1",
            recorded_at=NOW + timedelta(minutes=1),
        )

    awaiting = make_awaiting_approval()
    with pytest.raises(InvalidTransitionError, match="before updated_at"):
        approve_plan(
            awaiting,
            plan_digest="plan-v1",
            decided_at=NOW + timedelta(minutes=2),
        )
    with pytest.raises(InvalidTransitionError, match="before updated_at"):
        modify_plan(
            awaiting,
            path="artifacts/plan.md",
            digest="plan-v2",
            modified_at=NOW + timedelta(minutes=2),
        )

    approved = approve_plan(
        awaiting,
        plan_digest="plan-v1",
        decided_at=NOW + timedelta(minutes=4),
    )
    with pytest.raises(InvalidTransitionError, match="before updated_at"):
        start_implementation(
            approved,
            worktree_path=WORKTREE,
            started_at=NOW + timedelta(minutes=3),
        )

    for transition in (
        lambda: fail_workflow(
            make_draft(), reason="failed", failed_at=NOW - timedelta(seconds=1)
        ),
        lambda: cancel_workflow(
            make_draft(), reason="cancelled", cancelled_at=NOW - timedelta(seconds=1)
        ),
    ):
        with pytest.raises(InvalidTransitionError, match="before updated_at"):
            transition()


def test_deserialization_rejects_unknown_status() -> None:
    raw = make_draft().to_dict()
    raw["status"] = "unknown"

    with pytest.raises(InvalidWorkflowError, match="invalid serialized workflow"):
        WorkflowState.from_dict(raw)
