from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from daidala.recommendations import (
    ACTION_KINDS,
    KanbanSnapshot,
    Recommendation,
    derive_recommendations,
)
from daidala.state import (
    ArtifactReference,
    CardReference,
    SkillDigest,
    StageProfile,
    WorkflowStage,
)
from daidala.workflow import new_workflow

NOW = datetime(2026, 7, 12, tzinfo=UTC)


def ledger():
    profiles = tuple(
        StageProfile(stage=stage, profile="default")
        for stage in WorkflowStage
        if stage is not WorkflowStage.APPROVAL
    )
    return new_workflow(
        workflow_id="wf-1",
        board_slug="board",
        target_repository="/repo",
        baseline_commit="a" * 40,
        requested_goal="goal",
        pack_name="aidlc",
        pack_source_revision="b" * 40,
        skill_digests=(SkillDigest(name="skill", digest="c" * 64),),
        stage_profiles=profiles,
        created_at=NOW,
    )


def test_action_vocabulary_is_complete_and_closed() -> None:
    assert ACTION_KINDS == (
        "approve_current_tuple",
        "reapprove_current_tuple",
        "resolve_blocked_card",
        "restore_capability",
        "resolve_verification_failure",
        "replace_rejected_plan",
        "wait_for_dispatch",
        "deliver_reviewed_diff",
    )
    for action in ACTION_KINDS:
        assert Recommendation(action, "wf-1", "reason").action_kind == action
    with pytest.raises(ValueError, match="action_kind"):
        Recommendation("invented", "wf-1", "reason")


def test_empty_host_snapshot_produces_no_fabricated_decision() -> None:
    state = ledger()
    assert derive_recommendations(state, ()) == ()
    assert state == ledger()


def test_current_unapproved_plan_produces_exact_approval_action() -> None:
    state = ledger()
    plan = ArtifactReference(WorkflowStage.PLAN, 0, "/plan", "plan-digest", NOW)
    state = replace(state, artifacts=(plan,))

    result = derive_recommendations(state, ())

    approval = next(row for row in result if row.action_kind == "approve_current_tuple")
    assert approval.workflow_id == "wf-1"
    assert approval.plan_digest == "plan-digest"
    assert approval.card_id is None


def test_historical_approval_card_is_inert_for_current_recommendations() -> None:
    state = ledger()
    plan = ArtifactReference(WorkflowStage.PLAN, 0, "/plan", "plan-digest", NOW)
    gate = CardReference(
        WorkflowStage.APPROVAL,
        0,
        "historical-gate",
        "daidala:wf-1:0:0:none:approval",
        board_slug="board",
    )
    state = replace(state, artifacts=(plan,), card_references=(gate,))
    snapshot = KanbanSnapshot(
        WorkflowStage.APPROVAL,
        "historical-gate",
        "blocked",
        "default",
        block_kind="needs_input",
    )

    result = derive_recommendations(state, (snapshot,))

    assert [row.action_kind for row in result] == ["approve_current_tuple"]
    assert result[0].card_id is None


def test_blocked_snapshot_is_not_stored_in_ledger() -> None:
    state = ledger()
    snapshot = KanbanSnapshot(
        WorkflowStage.DEFINE,
        "task-1",
        "blocked",
        "default",
        block_kind="capability",
    )
    assert snapshot.to_dict()["status"] == "blocked"
    assert "status" not in state.to_dict()
