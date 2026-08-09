"""Tests for bounded dashboard supervision projections."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, cast

from daidala.constraints import DEFAULT_CONSTRAINT_TEMPLATE
from daidala.dashboard_backend import (
    DashboardBackend,
    _approval_review_packet,
    _workflow_timeline,
)
from daidala.recommendations import KanbanSnapshot
from daidala.state import WorkflowLedger, WorkflowStage


def _ledger(**overrides: object) -> WorkflowLedger:
    values: dict[str, object] = {
        "workflow_id": "workflow-1",
        "requested_goal": "Ship the bounded dashboard",
        "policy_revision": 2,
        "plan_revision": 3,
        "current_constraints_revision": 4,
        "current_constraints_digest": "d" * 64,
        "pack_name": "addyosmani",
        "pack_source_revision": "pack-v1",
        "approval": None,
        "review": None,
        "review_disposition": None,
        "baseline_commit": "f" * 40,
        "worktree_path": "/profile/workflows/workflow-1/worktree",
        "worktree_owned": True,
        "artifact_for": lambda _stage: None,
        "activation_for": lambda _stage: None,
    }
    values.update(overrides)
    return cast(WorkflowLedger, SimpleNamespace(**values))


def test_approval_review_packet_is_exact_bounded_and_path_free() -> None:
    packet = _approval_review_packet(
        _ledger(),
        {
            "artifact_id": "a" * 64,
            "policy_revision": 2,
            "plan_revision": 3,
            "plan_digest": "b" * 64,
            "approval_summary": {
                "headline": "Exact plan",
                "changes": ["Add approval"],
                "risks": [],
                "verification": ["Run pytest"],
            },
            "approval_summary_digest": "c" * 64,
            "content": "# Exact plan\n<script>literal</script>\n",
        },
    )

    assert packet["plan"]["verification_state"] == "verified"
    assert packet["plan"]["content"] == "# Exact plan\n<script>literal</script>\n"
    assert packet["tuple"] == {
        "workflow_id": "workflow-1",
        "policy_revision": 2,
        "plan_revision": 3,
        "plan_digest": "b" * 64,
        "constraints_revision": 4,
        "constraints_digest": "d" * 64,
    }
    assert packet["successor_packet"]["stage"] == "implement"
    assert packet["successor_packet"]["baseline_commit"] is None
    assert packet["successor_packet"]["worktree"] is None
    assert packet["consequences"]["next_cards"] == ["implement", "verify", "review"]
    assert "/profile/" not in json.dumps(packet)


def test_approval_review_resolves_plan_from_captured_ledger_snapshot() -> None:
    captured_ledger = _ledger()
    snapshots: list[WorkflowLedger] = []

    class Evidence:
        def to_dict(self) -> dict[str, object]:
            return {
                "artifact_id": "a" * 64,
                "policy_revision": 2,
                "plan_revision": 3,
                "plan_digest": "b" * 64,
                "approval_summary": {"headline": "Exact plan"},
                "approval_summary_digest": "c" * 64,
                "content": "# Exact plan\n",
            }

    class Service:
        def status(self, _workflow_id: str) -> WorkflowLedger:
            return captured_ledger

        def current_plan_evidence(
            self, _workflow_id: str, *, ledger: WorkflowLedger | None = None
        ) -> Evidence:
            assert ledger is captured_ledger
            assert ledger is not None
            snapshots.append(ledger)
            return Evidence()

    backend = DashboardBackend(service_factory=cast(Any, Service))

    packet = backend.approval_review("workflow-1")

    assert snapshots == [captured_ledger]
    assert packet["tuple"]["plan_digest"] == "b" * 64


def test_timeline_inserts_distinct_non_kanban_approval_gate() -> None:
    rows = _workflow_timeline(
        _ledger(),
        (
            KanbanSnapshot(
                stage=WorkflowStage.PLAN,
                task_id="t_plan",
                status="done",
                assignee="planner",
            ),
            KanbanSnapshot(
                stage=WorkflowStage.IMPLEMENT,
                task_id="t_implement",
                status="todo",
                assignee="implementer",
            ),
        ),
    )

    plan_index = next(index for index, row in enumerate(rows) if row["stage"] == "plan")
    gate = rows[plan_index + 1]
    assert gate == {
        "kind": "approval_gate",
        "stage": "approval",
        "label": "Human approval — Daidala policy gate",
        "status": "pending",
        "card_id": None,
        "assignee": None,
        "occurred_at": None,
        "approval": None,
    }
    assert rows[plan_index + 2]["stage"] == "implement"
    assert rows[plan_index]["card_id"] == "t_plan"


def test_prerequisites_project_the_exact_runtime_constraint_template() -> None:
    class Store:
        def list_all(self) -> list[object]:
            return []

    service = SimpleNamespace(store=Store())
    backend = DashboardBackend(service_factory=cast(Any, lambda: service))

    payload = backend.prerequisites()

    assert payload["constraint_template"] == {
        "kind": "yaml-template",
        "source": "docs/14-workflow-constraints.md#starter-template",
        "content": DEFAULT_CONSTRAINT_TEMPLATE,
    }
def test_timeline_inserts_distinct_non_kanban_review_gate() -> None:
    rows = _workflow_timeline(
        _ledger(review=SimpleNamespace(digest="a" * 64)),
        (),
    )

    review_index = next(index for index, row in enumerate(rows) if row["stage"] == "review")
    gate = rows[review_index + 1]
    assert gate == {
        "kind": "review_gate",
        "stage": "review_disposition",
        "label": "Human review disposition — Daidala policy gate",
        "status": "pending",
        "card_id": None,
        "assignee": None,
        "occurred_at": None,
        "review_digest": "a" * 64,
        "disposition": None,
    }
