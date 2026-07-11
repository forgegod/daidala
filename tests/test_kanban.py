from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from wingstaff.kanban import KanbanCoordinator, KanbanError
from wingstaff.packs import load_pack
from wingstaff.state import SkillDigest, WorkflowStage
from wingstaff.workflow import (
    approve_plan,
    new_workflow,
    record_artifact,
    record_worktree,
)

NOW = datetime(2026, 7, 10, 14, 0, tzinfo=UTC)


def make_approved_worktree():
    ledger = new_workflow(
        workflow_id="workflow-1",
        board_slug="wingstaff-test",
        target_repository="/tmp/wingstaff-target",
        baseline_commit="deadbeef",
        requested_goal="Change VALUE to 2",
        pack_name="addyosmani",
        pack_source_revision="source@revision",
        skill_digests=(SkillDigest(name="interview-me", digest="digest-1"),),
        created_at=NOW,
    )
    ledger = record_artifact(
        ledger,
        stage=WorkflowStage.DEFINE,
        path="artifacts/define.md",
        digest="define-v1",
        recorded_at=NOW + timedelta(minutes=1),
    )
    ledger = record_artifact(
        ledger,
        stage=WorkflowStage.PLAN,
        path="artifacts/plan.md",
        digest="plan-v1",
        recorded_at=NOW + timedelta(minutes=2),
    )
    ledger = approve_plan(
        ledger,
        plan_digest="plan-v1",
        decided_at=NOW + timedelta(minutes=3),
    )
    return record_worktree(
        ledger,
        worktree_path="/tmp/wingstaff-worktrees/workflow-1",
        recorded_at=NOW + timedelta(minutes=4),
    )


def test_implementation_adapter_uses_policy_facts_not_mirrored_status() -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def dispatch(name: str, args: dict[str, object]) -> str:
        calls.append((name, args))
        return json.dumps({"ok": True, "task_id": "t_impl", "status": "ready"})

    task = KanbanCoordinator(dispatch).ensure_implementation_task(
        make_approved_worktree(),
        load_pack("addyosmani"),
        assignee="engineer",
    )

    assert task.task_id == "t_impl"
    assert task.status == "ready"
    name, args = calls[0]
    assert name == "kanban_create"
    assert args["idempotency_key"] == "wingstaff:workflow-1:0:implement"
    assert args["workspace_path"] == "/tmp/wingstaff-worktrees/workflow-1"
    assert "Hermes Kanban remains authoritative" in str(args["body"])


def test_implementation_adapter_requires_approval_and_owned_worktree() -> None:
    ledger = make_approved_worktree()
    unowned = ledger.__class__.from_dict(
        {
            **ledger.to_dict(),
            "worktree_path": None,
            "worktree_owned": False,
        }
    )

    with pytest.raises(KanbanError, match="approved Wingstaff-owned worktree"):
        KanbanCoordinator(lambda name, args: "{}").ensure_implementation_task(
            unowned,
            load_pack("addyosmani"),
            assignee="engineer",
        )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ("not-json", "invalid JSON"),
        (json.dumps({"ok": False, "error": "interrupted"}), "interrupted"),
        (json.dumps({"ok": True, "status": "ready"}), "omitted task_id"),
    ],
)
def test_implementation_adapter_fails_closed_on_invalid_host_output(
    payload: str,
    message: str,
) -> None:
    coordinator = KanbanCoordinator(lambda name, args: payload)

    with pytest.raises(KanbanError, match=message):
        coordinator.ensure_implementation_task(
            make_approved_worktree(),
            load_pack("addyosmani"),
            assignee="engineer",
        )