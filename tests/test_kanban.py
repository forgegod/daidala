from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from daidala.constraints import parse_workflow_constraints
from daidala.kanban import KanbanError, KanbanGraphAdapter
from daidala.packs import load_pack
from daidala.state import (
    ActivationManifestReference,
    ActivationReferenceState,
    CardReference,
    SkillDigest,
    StageProfile,
    WorkflowConstraintsIdentity,
    WorkflowConstraintsReference,
    WorkflowStage,
)
from daidala.workflow import (
    approve_plan,
    new_workflow,
    record_artifact,
    record_card,
    record_worktree,
)

NOW = datetime(2026, 7, 10, 14, 0, tzinfo=UTC)


class FakeHost:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.cards: dict[str, dict[str, object]] = {}
        self.by_key: dict[str, str] = {}
        self.archived: list[str] = []
        self.profiles = {"architect", "engineer", "reviewer"}

    def dispatch(self, name: str, args: dict[str, object]) -> str:
        self.calls.append((name, args))
        if name == "terminal":
            command = str(args["command"])
            if " assignees --json" in command:
                rows = [
                    {"name": profile, "on_disk": True, "counts": {}}
                    for profile in sorted(self.profiles)
                ]
                return json.dumps({"exit_code": 0, "output": json.dumps(rows)})
            if " archive " in command:
                self.archived.extend(command.split(" archive ", 1)[1].split())
                return json.dumps({"exit_code": 0, "output": ""})
        if name == "kanban_create":
            key = str(args["idempotency_key"])
            task_id = self.by_key.setdefault(key, f"t_{len(self.by_key) + 1}")
            self.cards.setdefault(
                task_id,
                {
                    "id": task_id,
                    "status": "blocked" if args.get("initial_status") == "blocked" else "ready",
                    "assignee": args["assignee"],
                    "args": dict(args),
                },
            )
            return json.dumps(
                {"ok": True, "task_id": task_id, "status": self.cards[task_id]["status"]}
            )
        if name == "kanban_show":
            task_id = str(args["task_id"])
            return json.dumps({"ok": True, "task": self.cards[task_id]})
        if name == "kanban_complete":
            task_id = str(args["task_id"])
            self.cards[task_id]["status"] = "done"
            return json.dumps({"ok": True, "task_id": task_id, "status": "done"})
        if name == "kanban_comment":
            return json.dumps({"ok": True, "task_id": args["task_id"]})
        raise AssertionError(f"unexpected host call: {name}")


def profiles() -> tuple[StageProfile, ...]:
    mapping = {
        WorkflowStage.DEFINE: "architect",
        WorkflowStage.PLAN: "architect",
        WorkflowStage.IMPLEMENT: "engineer",
        WorkflowStage.VERIFY: "engineer",
        WorkflowStage.REVIEW: "reviewer",
        WorkflowStage.DELIVER: "engineer",
    }
    return tuple(StageProfile(stage=stage, profile=profile) for stage, profile in mapping.items())


def make_ledger():
    return new_workflow(
        workflow_id="workflow-1",
        board_slug="daidala-test",
        target_repository="/tmp/daidala-target",
        baseline_commit="deadbeef",
        requested_goal="Change VALUE to 2",
        pack_name="addyosmani",
        pack_source_revision="source@revision",
        skill_digests=(SkillDigest(name="interview-me", digest="digest-1"),),
        stage_profiles=profiles(),
        created_at=NOW,
    )


def with_constraints(ledger):
    constraints = parse_workflow_constraints(
        """schema: daidala.workflow-constraints/v1
global:
  - Never commit or push.
phases:
  review:
    - Critical findings block delivery.
"""
    )
    reference = WorkflowConstraintsReference(
        identity=WorkflowConstraintsIdentity(
            policy_revision=1,
            constraints_revision=1,
            digest=constraints.digest,
        ),
        path="/tmp/constraints/workflow-constraints-1.json",
        recorded_at=ledger.updated_at + timedelta(seconds=1),
    )
    return replace(
        ledger,
        policy_revision=1,
        constraint_references=(reference,),
        artifacts=tuple(replace(row, policy_revision=1) for row in ledger.artifacts),
        approval=(
            replace(
                ledger.approval,
                constraints_revision=1,
                constraints_digest=constraints.digest,
            )
            if ledger.approval is not None
            else None
        ),
        activation_manifests=tuple(
            replace(
                row,
                policy_revision=1,
                constraints_digest=constraints.digest,
            )
            for row in ledger.activation_manifests
        ),
        updated_at=reference.recorded_at,
    ), constraints


def with_activation(ledger, stage: WorkflowStage):
    return replace(
        ledger,
        activation_manifests=(
            *ledger.activation_manifests,
            ActivationManifestReference(
                stage=stage,
                plan_revision=ledger.activation_revision_for(stage),
                sequence=1,
                path=f"/tmp/{stage.value}-activation.json",
                digest=hashlib.sha256(stage.value.encode()).hexdigest(),
                state=ActivationReferenceState.FINALIZED,
                blocked=False,
                supersedes_digest=None,
            ),
        ),
    )


def make_approved_worktree():
    ledger = with_activation(make_ledger(), WorkflowStage.DEFINE)
    ledger = record_artifact(
        ledger,
        stage=WorkflowStage.DEFINE,
        path="artifacts/define.md",
        digest="define-v1",
        recorded_at=NOW + timedelta(minutes=1),
    )
    ledger = record_artifact(
        with_activation(ledger, WorkflowStage.PLAN),
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
        worktree_path="/tmp/daidala-worktrees/workflow-1",
        recorded_at=NOW + timedelta(minutes=4),
    )


def record_host_card(ledger, stage: WorkflowStage, task_id: str, minute: int):
    revision = 0 if stage in {WorkflowStage.DEFINE, WorkflowStage.PLAN} else ledger.plan_revision
    constraint_key = ledger.current_constraints_digest or "none"
    return record_card(
        ledger,
        stage=stage,
        task_id=task_id,
        idempotency_key=(
            f"daidala:{ledger.workflow_id}:{revision}:{ledger.policy_revision}:"
            f"{constraint_key}:{stage.value}"
        ),
        recorded_at=NOW + timedelta(minutes=minute),
    )


def test_initial_graph_pins_board_profiles_skills_and_parent() -> None:
    host = FakeHost()
    adapter = KanbanGraphAdapter(host.dispatch)
    ledger = make_ledger()

    adapter.validate_assignees(ledger.board_slug, [row.profile for row in ledger.stage_profiles])
    define = adapter.ensure_card(ledger, load_pack("addyosmani"), stage=WorkflowStage.DEFINE)
    plan = adapter.ensure_card(
        ledger,
        load_pack("addyosmani"),
        stage=WorkflowStage.PLAN,
        parents=(define.task_id,),
    )

    define_args = host.cards[define.task_id]["args"]
    plan_args = host.cards[plan.task_id]["args"]
    assert define_args["board"] == "daidala-test"
    assert define_args["assignee"] == "architect"
    assert define_args["skills"] == [
        "daidala:orchestrate",
        *(
            skill.name
            for skill in next(
                stage for stage in load_pack("addyosmani").stages if stage.id == "define"
            ).skills
        ),
    ]
    assert plan_args["parents"] == [define.task_id]
    assert plan_args["idempotency_key"] == "daidala:workflow-1:0:0:none:plan"
    assert "Policy revision: 0" in str(define_args["body"])
    assert "Constraint revision: none" in str(define_args["body"])
    assert "Constraint digest: none" in str(define_args["body"])


def test_restart_reuses_idempotent_cards() -> None:
    host = FakeHost()
    adapter = KanbanGraphAdapter(host.dispatch)
    ledger = make_ledger()

    first = adapter.ensure_card(ledger, load_pack("addyosmani"), stage=WorkflowStage.DEFINE)
    second = adapter.ensure_card(ledger, load_pack("addyosmani"), stage=WorkflowStage.DEFINE)

    assert first.task_id == second.task_id
    assert len(host.cards) == 1


def test_card_projects_current_global_and_phase_constraints_with_identity() -> None:
    host = FakeHost()
    ledger, constraints = with_constraints(make_approved_worktree())

    card = KanbanGraphAdapter(host.dispatch).ensure_card(
        ledger,
        load_pack("addyosmani"),
        stage=WorkflowStage.REVIEW,
        constraints=constraints,
    )

    args = host.cards[card.task_id]["args"]
    body = str(args["body"])
    assert "Policy revision: 1" in body
    assert "Constraint revision: 1" in body
    assert f"Constraint digest: {constraints.digest}" in body
    assert "- Never commit or push." in body
    assert "- Critical findings block delivery." in body
    assert constraints.digest in str(args["idempotency_key"])


def test_card_reference_persists_board_and_complete_constraint_identity() -> None:
    ledger, _constraints = with_constraints(make_ledger())
    recorded = record_host_card(ledger, WorkflowStage.DEFINE, "t_define", 2)
    card = recorded.card_for(WorkflowStage.DEFINE)

    assert card is not None
    assert card.board_slug == ledger.board_slug
    assert card.constraints_revision == 1
    assert card.constraints_digest == ledger.current_constraints_digest
    assert CardReference.from_dict(card.to_dict()) == card


def test_approval_card_excludes_non_executable_constraint_projection() -> None:
    host = FakeHost()
    ledger, constraints = with_constraints(make_approved_worktree())

    card = KanbanGraphAdapter(host.dispatch).ensure_card(
        ledger,
        load_pack("addyosmani"),
        stage=WorkflowStage.APPROVAL,
        constraints=constraints,
    )

    args = host.cards[card.task_id]["args"]
    assert isinstance(args, dict)
    body = str(args["body"])
    assert "Workflow constraints" not in body
    assert "Never commit or push" not in body


def test_card_rejects_missing_current_constraint_content() -> None:
    ledger, _constraints = with_constraints(make_ledger())

    with pytest.raises(KanbanError, match="do not match"):
        KanbanGraphAdapter(FakeHost().dispatch).ensure_card(
            ledger,
            load_pack("addyosmani"),
            stage=WorkflowStage.DEFINE,
        )


def test_card_rejects_oversized_rendered_body_instead_of_truncating() -> None:
    ledger = replace(make_ledger(), requested_goal="x" * 8192)

    with pytest.raises(KanbanError, match="at most 8192"):
        KanbanGraphAdapter(FakeHost().dispatch).ensure_card(
            ledger, load_pack("addyosmani"), stage=WorkflowStage.DEFINE
        )


def test_unknown_assignee_stops_before_card_creation() -> None:
    host = FakeHost()
    adapter = KanbanGraphAdapter(host.dispatch)

    with pytest.raises(KanbanError, match="unknown Kanban assignee.*missing"):
        adapter.validate_assignees("daidala-test", ["architect", "missing"])

    assert not host.cards


def test_deleted_assignee_remains_visible_in_live_card_status() -> None:
    host = FakeHost()
    adapter = KanbanGraphAdapter(host.dispatch)
    ledger = make_ledger()
    define = adapter.ensure_card(ledger, load_pack("addyosmani"), stage=WorkflowStage.DEFINE)
    ledger = record_host_card(ledger, WorkflowStage.DEFINE, define.task_id, 1)

    host.profiles.remove("architect")
    status = adapter.combined_status(ledger)

    assert len(status) == 1
    assert status[0].stage is WorkflowStage.DEFINE
    assert status[0].assignee == "architect"
    assert status[0].status == "ready"


def test_show_accepts_native_unwrapped_kanban_payload() -> None:
    host = FakeHost()
    adapter = KanbanGraphAdapter(host.dispatch)
    ledger = make_ledger()
    define = adapter.ensure_card(
        ledger,
        load_pack("addyosmani"),
        stage=WorkflowStage.DEFINE,
    )
    ledger = record_host_card(ledger, WorkflowStage.DEFINE, define.task_id, 1)

    def native_dispatch(name: str, args: dict[str, object]) -> str:
        assert name == "kanban_show"
        return json.dumps({"task": host.cards[str(args["task_id"])]})

    status = KanbanGraphAdapter(native_dispatch).show_card(
        ledger,
        WorkflowStage.DEFINE,
    )

    assert status.task_id == define.task_id
    assert status.status == "ready"


def test_approval_and_post_gate_graph_use_blocked_gate_and_shared_worktree() -> None:
    host = FakeHost()
    adapter = KanbanGraphAdapter(host.dispatch)
    ledger = make_approved_worktree()
    plan = adapter.ensure_card(ledger, load_pack("addyosmani"), stage=WorkflowStage.PLAN)
    ledger = record_host_card(ledger, WorkflowStage.PLAN, plan.task_id, 5)
    gate = adapter.ensure_card(
        ledger,
        load_pack("addyosmani"),
        stage=WorkflowStage.APPROVAL,
        parents=(plan.task_id,),
    )
    ledger = record_host_card(ledger, WorkflowStage.APPROVAL, gate.task_id, 6)

    assert host.cards[gate.task_id]["status"] == "blocked"
    adapter.complete_approval(ledger)
    assert host.cards[gate.task_id]["status"] == "done"

    implement = adapter.ensure_card(
        ledger,
        load_pack("addyosmani"),
        stage=WorkflowStage.IMPLEMENT,
        parents=(gate.task_id,),
    )
    args = host.cards[implement.task_id]["args"]
    assert args["parents"] == [gate.task_id]
    assert args["workspace_kind"] == "dir"
    assert args["workspace_path"] == ledger.worktree_path


def test_post_gate_card_is_rejected_before_approval() -> None:
    with pytest.raises(KanbanError, match="require approval"):
        KanbanGraphAdapter(FakeHost().dispatch).ensure_card(
            make_ledger(),
            load_pack("addyosmani"),
            stage=WorkflowStage.IMPLEMENT,
        )


def test_combined_status_reads_host_without_mutating_ledger() -> None:
    host = FakeHost()
    adapter = KanbanGraphAdapter(host.dispatch)
    ledger = make_ledger()
    card = adapter.ensure_card(ledger, load_pack("addyosmani"), stage=WorkflowStage.DEFINE)
    ledger = record_host_card(ledger, WorkflowStage.DEFINE, card.task_id, 1)

    combined = adapter.combined_status(ledger)

    assert [row.to_dict() for row in combined] == [
        {
            "stage": "define",
            "task_id": card.task_id,
            "status": "ready",
            "assignee": "architect",
        }
    ]
    assert "status" not in ledger.to_dict()


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ("not-json", "invalid JSON"),
        (json.dumps({"ok": False, "error": "interrupted"}), "interrupted"),
        (json.dumps({"ok": True, "status": "ready"}), "omitted task_id"),
    ],
)
def test_adapter_fails_closed_on_invalid_host_output(payload: str, message: str) -> None:
    adapter = KanbanGraphAdapter(lambda name, args: payload)

    with pytest.raises(KanbanError, match=message):
        adapter.ensure_card(make_ledger(), load_pack("addyosmani"), stage=WorkflowStage.DEFINE)


def test_archive_comments_and_archives_every_selected_card() -> None:
    host = FakeHost()
    adapter = KanbanGraphAdapter(host.dispatch)
    ledger = make_ledger()
    define = adapter.ensure_card(ledger, load_pack("addyosmani"), stage=WorkflowStage.DEFINE)
    ledger = record_host_card(ledger, WorkflowStage.DEFINE, define.task_id, 1)

    adapter.archive(ledger, "operator cancelled")

    assert host.archived == [define.task_id]
    assert any(name == "kanban_comment" for name, _ in host.calls)