from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from wingstaff.errors import PolicyViolationError
from wingstaff.state import SkillDigest, StageProfile, WorkflowLedger, WorkflowStage
from wingstaff.workflow import (
    approve_plan,
    new_workflow,
    record_artifact,
    record_card,
    record_verification,
    record_worktree,
    release_worktree,
    replace_plan,
)

NOW = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)
PROFILES = tuple(
    StageProfile(stage=stage, profile=f"{stage.value}-profile")
    for stage in WorkflowStage
    if stage is not WorkflowStage.APPROVAL
)
TARGET = "/tmp/wingstaff-target"
WORKTREE = "/tmp/wingstaff-worktrees/workflow-1"


def make_ledger() -> WorkflowLedger:
    return new_workflow(
        workflow_id="workflow-1",
        board_slug="wingstaff-test",
        target_repository=TARGET,
        baseline_commit="abcdef123456",
        requested_goal="Fix the deliberately failing test",
        pack_name="addyosmani",
        pack_source_revision="source@0123456789abcdef",
        skill_digests=(SkillDigest(name="interview-me", digest="digest-1"),),
        stage_profiles=PROFILES,
        created_at=NOW,
    )


def make_planned() -> WorkflowLedger:
    ledger = record_artifact(
        make_ledger(),
        stage=WorkflowStage.DEFINE,
        path="artifacts/define.md",
        digest="define-v1",
        recorded_at=NOW + timedelta(minutes=1),
    )
    return record_artifact(
        ledger,
        stage=WorkflowStage.PLAN,
        path="artifacts/plan.md",
        digest="plan-v1",
        recorded_at=NOW + timedelta(minutes=2),
    )


def make_implementing() -> WorkflowLedger:
    ledger = approve_plan(
        make_planned(),
        plan_digest="plan-v1",
        decided_at=NOW + timedelta(minutes=3),
    )
    return record_worktree(
        ledger,
        worktree_path=WORKTREE,
        recorded_at=NOW + timedelta(minutes=4),
    )


def test_new_ledger_contains_policy_facts_but_no_operational_status() -> None:
    ledger = make_ledger()
    payload = ledger.to_dict()

    assert ledger.board_slug == "wingstaff-test"
    assert ledger.baseline_commit == "abcdef123456"
    assert ledger.plan_revision == 0
    assert ledger.committed is ledger.pushed is False
    assert ledger.created_at == ledger.updated_at == NOW
    assert {"status", "current_stage", "failure_reason"}.isdisjoint(payload)


@pytest.mark.parametrize(
    "target",
    ["owner/repository", "https://example.invalid/repository.git", "git@example.invalid:repo.git"],
)
def test_new_ledger_rejects_nonlocal_targets(target: str) -> None:
    with pytest.raises(PolicyViolationError, match="absolute local path"):
        replace(make_ledger(), target_repository=target)


def test_serialization_round_trip_preserves_complete_ledger() -> None:
    ledger = record_card(
        make_planned(),
        stage=WorkflowStage.APPROVAL,
        task_id="t_approval",
        idempotency_key="wingstaff:workflow-1:0:approval",
        recorded_at=NOW + timedelta(minutes=3),
    )

    assert WorkflowLedger.from_dict(ledger.to_dict()) == ledger


def test_approval_is_exact_and_plan_replacement_invalidates_it() -> None:
    planned = make_planned()
    with pytest.raises(PolicyViolationError, match="current plan digest"):
        approve_plan(
            planned,
            plan_digest="stale-plan",
            decided_at=NOW + timedelta(minutes=3),
        )

    approved = approve_plan(
        planned,
        plan_digest="plan-v1",
        decided_at=NOW + timedelta(minutes=3),
    )
    replacement = replace_plan(
        approved,
        path="artifacts/plan-v2.md",
        digest="plan-v2",
        replaced_at=NOW + timedelta(minutes=4),
    )

    assert replacement.plan_revision == 1
    assert replacement.current_plan_digest == "plan-v2"
    assert replacement.approval is None
    assert replacement.verification_evidence == ()


def test_card_mapping_is_idempotent_and_rejects_conflicts() -> None:
    planned = make_planned()
    recorded = record_card(
        planned,
        stage=WorkflowStage.APPROVAL,
        task_id="t_approval",
        idempotency_key="wingstaff:workflow-1:0:approval",
        recorded_at=NOW + timedelta(minutes=3),
    )
    assert (
        record_card(
            recorded,
            stage=WorkflowStage.APPROVAL,
            task_id="t_approval",
            idempotency_key="wingstaff:workflow-1:0:approval",
            recorded_at=NOW + timedelta(minutes=3),
        )
        is recorded
    )
    with pytest.raises(PolicyViolationError, match="different Kanban card"):
        record_card(
            recorded,
            stage=WorkflowStage.APPROVAL,
            task_id="t_other",
            idempotency_key="wingstaff:workflow-1:0:approval",
            recorded_at=NOW + timedelta(minutes=4),
        )
    with pytest.raises(PolicyViolationError, match="idempotency key"):
        record_card(
            planned,
            stage=WorkflowStage.APPROVAL,
            task_id="t_bad",
            idempotency_key="wingstaff:workflow-1:approval",
            recorded_at=NOW + timedelta(minutes=3),
        )


def test_post_gate_facts_require_approval_and_owned_worktree() -> None:
    with pytest.raises(PolicyViolationError, match="approval"):
        record_worktree(
            make_planned(),
            worktree_path=WORKTREE,
            recorded_at=NOW + timedelta(minutes=3),
        )

    implementing = make_implementing()
    with pytest.raises(PolicyViolationError, match="implement artifact"):
        record_verification(
            implementing,
            command="pytest",
            exit_code=0,
            output_reference="artifacts/pytest.txt",
            output_digest="verify-v1",
            recorded_at=NOW + timedelta(minutes=5),
        )


def test_verification_evidence_does_not_create_a_blocked_status() -> None:
    ledger = record_artifact(
        make_implementing(),
        stage=WorkflowStage.IMPLEMENT,
        path="artifacts/implementation.diff",
        digest="diff-v1",
        recorded_at=NOW + timedelta(minutes=5),
    )
    failed = record_verification(
        ledger,
        command="pytest",
        exit_code=1,
        output_reference="artifacts/pytest-1.txt",
        output_digest="verify-failed",
        recorded_at=NOW + timedelta(minutes=6),
    )

    assert failed.verification_evidence[-1].exit_code == 1
    assert "status" not in failed.to_dict()
    repeated = record_verification(
        failed,
        command="pytest",
        exit_code=1,
        output_reference="artifacts/pytest-1.txt",
        output_digest="verify-failed",
        recorded_at=NOW + timedelta(minutes=7),
    )
    assert repeated is failed
    with pytest.raises(PolicyViolationError, match="successful verification"):
        record_artifact(
            failed,
            stage=WorkflowStage.REVIEW,
            path="artifacts/review.md",
            digest="review-v1",
            recorded_at=NOW + timedelta(minutes=7),
        )

    passed = record_verification(
        failed,
        command="pytest",
        exit_code=0,
        output_reference="artifacts/pytest-2.txt",
        output_digest="verify-passed",
        recorded_at=NOW + timedelta(minutes=7),
    )
    reviewed = record_artifact(
        passed,
        stage=WorkflowStage.REVIEW,
        path="artifacts/review.md",
        digest="review-v1",
        recorded_at=NOW + timedelta(minutes=8),
    )
    delivered = record_artifact(
        reviewed,
        stage=WorkflowStage.DELIVER,
        path="artifacts/delivery.json",
        digest="delivery-v1",
        recorded_at=NOW + timedelta(minutes=9),
    )

    assert delivered.committed is delivered.pushed is False


def test_worktree_release_clears_only_ownership_facts() -> None:
    ledger = make_implementing()
    released = release_worktree(
        ledger,
        released_at=NOW + timedelta(minutes=5),
    )

    assert released.worktree_path is None
    assert released.worktree_owned is False
    assert released.approval == ledger.approval


def test_timestamps_are_timezone_aware_and_monotonic() -> None:
    with pytest.raises(PolicyViolationError, match="timezone-aware"):
        replace(make_ledger(), updated_at=datetime(2026, 7, 10, 12, 1))
    with pytest.raises(PolicyViolationError, match="before created_at"):
        replace(make_ledger(), updated_at=NOW - timedelta(seconds=1))
    with pytest.raises(PolicyViolationError, match="before updated_at"):
        record_artifact(
            make_planned(),
            stage=WorkflowStage.IMPLEMENT,
            path="artifacts/implementation.diff",
            digest="diff-v1",
            recorded_at=NOW,
        )


def test_deserialization_rejects_operational_status_payload() -> None:
    raw = make_ledger().to_dict()
    raw["status"] = "running"

    with pytest.raises(PolicyViolationError, match="unknown serialized"):
        WorkflowLedger.from_dict(raw)