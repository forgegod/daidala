from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from wingstaff import schemas, tools
from wingstaff.errors import PolicyViolationError
from wingstaff.kanban import KanbanGraphAdapter
from wingstaff.packs import load_pack
from wingstaff.service import WorkflowService
from wingstaff.skills import (
    content_registry_from_digests,
    inventory_from_names,
    required_skills,
)
from wingstaff.state import WorkflowStage
from wingstaff.store import StoreError, WorkflowStore

NOW = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)
STAGE_PROFILES = {
    "define": "architect",
    "plan": "architect",
    "implement": "engineer",
    "verify": "engineer",
    "review": "reviewer",
    "deliver": "engineer",
}


class TickClock:
    def __init__(self) -> None:
        self._tick = 0

    def __call__(self) -> datetime:
        self._tick += 1
        return NOW + timedelta(minutes=self._tick)


@pytest.fixture
def target_repository(tmp_path: Path) -> Path:
    target = tmp_path / "target"
    target.mkdir()
    subprocess.run(["git", "init", "-q", str(target)], check=True)
    (target / "README.md").write_text("fixture\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(target), "add", "README.md"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(target),
            "-c",
            "user.name=Wingstaff Tests",
            "-c",
            "user.email=wingstaff@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        check=True,
    )
    return target.resolve()


@pytest.fixture
def service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kanban_adapter: KanbanGraphAdapter,
) -> WorkflowService:
    pack = load_pack("addyosmani")
    skills = required_skills(pack)
    instance = WorkflowService(
        WorkflowStore(tmp_path / "data"),
        clock=TickClock(),
        id_factory=lambda: "workflow-generated",
        skill_inventory=inventory_from_names(skill.name for skill in skills),
        skill_content_registry=content_registry_from_digests(
            {skill.name: skill.content_digest for skill in skills}
        ),
        kanban=kanban_adapter,
    )
    monkeypatch.setattr(tools, "_service_factory", lambda: instance)
    return instance


def call(handler, args: object) -> dict:
    raw = handler(args, task_id="test")
    assert isinstance(raw, str)
    return json.loads(raw)


def worker_context(
    service: WorkflowService, workflow_id: str, stage: WorkflowStage
) -> dict[str, str]:
    ledger = service.status(workflow_id)
    card = ledger.card_for(stage)
    assert card is not None
    return {"board_slug": ledger.board_slug, "task_id": card.task_id}


def seed_planned(service: WorkflowService, target: Path) -> str:
    ledger = service.start(
        board_slug="wingstaff-test",
        target_repository=str(target),
        goal="Fix the failing fixture",
        stage_profiles=STAGE_PROFILES,
        workflow_id="workflow-plan",
    )
    record_activation(service, ledger.workflow_id, WorkflowStage.DEFINE)
    ledger = service.submit_artifact(
        ledger.workflow_id,
        stage=WorkflowStage.DEFINE,
        content="# Definition\n",
        **worker_context(service, ledger.workflow_id, WorkflowStage.DEFINE),
    )
    record_activation(service, ledger.workflow_id, WorkflowStage.PLAN)
    ledger = service.submit_artifact(
        ledger.workflow_id,
        stage=WorkflowStage.PLAN,
        content="# Plan\n",
        **worker_context(service, ledger.workflow_id, WorkflowStage.PLAN),
    )
    return ledger.workflow_id


def activation_decisions(
    service: WorkflowService,
    workflow_id: str,
    stage: WorkflowStage = WorkflowStage.DEFINE,
) -> list[dict]:
    ledger = service.status(workflow_id)
    pack = load_pack(ledger.pack_name)
    pack_stage = next(row for row in pack.stages if row.id == stage.value)
    return [
        {
            "name": skill.name,
            "category": "applicable" if skill.activation.value == "required" else "not_applicable",
            "rank": 1 if skill.activation.value == "required" else None,
            "matched_criteria": ["The pinned skill criteria were assessed."],
            "evidence": ["The current definition card was inspected."],
            "rationale": "Apply required guidance; omit conditional guidance for this fixture.",
            "condition": None,
        }
        for skill in pack_stage.skills
    ]


def record_activation(
    service: WorkflowService,
    workflow_id: str,
    stage: WorkflowStage,
) -> None:
    ledger = service.status(workflow_id)
    card = ledger.card_for(stage)
    assert card is not None
    service.record_skill_activation(
        workflow_id,
        stage=stage,
        supersedes_digest=None,
        decisions=activation_decisions(service, workflow_id, stage),
        board_slug=ledger.board_slug,
        task_id=card.task_id,
    )


def test_start_and_status_return_policy_ledger_without_status(
    service: WorkflowService,
    target_repository: Path,
) -> None:
    started = call(
        tools.start,
        {
            "board_slug": "wingstaff-test",
            "target_repository": str(target_repository),
            "goal": "Add one deterministic behavior",
            "stage_profiles": STAGE_PROFILES,
            "workflow_id": "workflow-generated",
        },
    )

    assert started["success"] is True
    ledger = started["workflow"]
    assert ledger["workflow_id"] == "workflow-generated"
    assert ledger["board_slug"] == "wingstaff-test"
    assert ledger["baseline_commit"]
    assert ledger["skill_digests"]
    assert {"status", "current_stage", "failure_reason"}.isdisjoint(ledger)
    status = call(tools.status, {"workflow_id": "workflow-generated"})
    assert status["workflow"] == started["workflow"]
    assert [row["stage"] for row in status["kanban"]] == ["define", "plan"]


def test_start_restart_and_approval_create_one_idempotent_graph(
    service: WorkflowService,
    target_repository: Path,
    fake_kanban_host,
) -> None:
    arguments = {
        "board_slug": "wingstaff-test",
        "target_repository": str(target_repository),
        "goal": "Build one graph",
        "stage_profiles": STAGE_PROFILES,
        "workflow_id": "workflow-restart",
    }
    first = service.start(**arguments)
    second = service.start(**arguments)

    assert first.card_references == second.card_references
    assert len(fake_kanban_host.cards) == 2
    assert {card.stage for card in second.card_references} == {
        WorkflowStage.DEFINE,
        WorkflowStage.PLAN,
    }

    record_activation(service, second.workflow_id, WorkflowStage.DEFINE)
    service.submit_artifact(
        second.workflow_id,
        stage=WorkflowStage.DEFINE,
        content="# Definition\n",
        **worker_context(service, second.workflow_id, WorkflowStage.DEFINE),
    )
    record_activation(service, second.workflow_id, WorkflowStage.PLAN)
    planned = service.submit_artifact(
        second.workflow_id,
        stage=WorkflowStage.PLAN,
        content="# Plan\n",
        **worker_context(service, second.workflow_id, WorkflowStage.PLAN),
    )
    plan = planned.artifact_for(WorkflowStage.PLAN)
    assert plan is not None
    approved = service.approve(second.workflow_id, plan_digest=plan.digest)

    assert len(fake_kanban_host.cards) == 7
    assert [card.stage for card in approved.card_references] == list(WorkflowStage)
    for parent, child in zip(
        (
            WorkflowStage.APPROVAL,
            WorkflowStage.IMPLEMENT,
            WorkflowStage.VERIFY,
            WorkflowStage.REVIEW,
        ),
        (
            WorkflowStage.IMPLEMENT,
            WorkflowStage.VERIFY,
            WorkflowStage.REVIEW,
            WorkflowStage.DELIVER,
        ),
        strict=True,
    ):
        parent_card = approved.card_for(parent)
        child_card = approved.card_for(child)
        assert parent_card is not None and child_card is not None
        child_args = fake_kanban_host.cards[child_card.task_id]["args"]
        assert child_args["parents"] == [parent_card.task_id]


def test_start_rejects_dirty_target_without_persisting_status(
    service: WorkflowService,
    target_repository: Path,
) -> None:
    (target_repository / "dirty.txt").write_text("dirty\n", encoding="utf-8")

    result = call(
        tools.start,
        {
            "board_slug": "wingstaff-test",
            "target_repository": str(target_repository),
            "goal": "Reject dirty target",
            "stage_profiles": STAGE_PROFILES,
            "workflow_id": "workflow-dirty",
        },
    )

    assert result["success"] is False
    assert result["error"] == "ServiceError"
    assert "dirty" in result["message"]
    assert service.store.list_all() == ()


def test_tool_start_and_replacement_use_explicit_constraint_content(
    service: WorkflowService,
    target_repository: Path,
) -> None:
    first = "schema: wingstaff.workflow-constraints/v1\nglobal: [Never push.]\n"
    started = call(
        tools.start,
        {
            "board_slug": "wingstaff-test",
            "target_repository": str(target_repository),
            "goal": "Constrained workflow",
            "stage_profiles": STAGE_PROFILES,
            "workflow_id": "workflow-constraints",
            "constraints_content": first,
        },
    )

    assert started["success"] is True
    current = started["workflow"]["constraint_references"][-1]["identity"]["digest"]
    no_change = service.replace_constraint_input(
        "workflow-constraints",
        expected_current_digest=current,
        content=(
            "global:\n  - Never push.\n"
            "schema: wingstaff.workflow-constraints/v1\n"
        ),
    )
    assert no_change.policy_revision == 1
    assert len(no_change.constraint_references) == 1
    replaced = call(
        tools.replace_constraints,
        {
            "workflow_id": "workflow-constraints",
            "expected_current_digest": current,
            "constraints_content": (
                "schema: wingstaff.workflow-constraints/v1\n"
                "global: [Never push., Preserve audit history.]\n"
            ),
        },
    )

    assert replaced["success"] is True
    assert replaced["workflow"]["policy_revision"] == 2
    assert replaced["workflow"]["constraint_references"][-1]["identity"]["digest"] != current


def test_approve_binds_exact_digest_and_service_replacement_invalidates_it(
    service: WorkflowService,
    target_repository: Path,
) -> None:
    workflow_id = seed_planned(service, target_repository)
    plan = service.status(workflow_id).artifact_for(WorkflowStage.PLAN)
    assert plan is not None

    approved = call(
        tools.approve,
        {"workflow_id": workflow_id, "plan_digest": plan.digest},
    )
    assert approved["success"] is True
    assert approved["workflow"]["approval"]["plan_digest"] == plan.digest

    replacement = service.replace_plan(
        workflow_id,
        path="artifacts/plan-v2.md",
        digest="plan-v2",
    )
    assert replacement.plan_revision == 1
    assert replacement.approval is None
    with pytest.raises(PolicyViolationError, match="approval"):
        service.prepare_implementation(workflow_id)


def test_cancel_without_owned_worktree_does_not_create_lifecycle_state(
    service: WorkflowService,
    target_repository: Path,
) -> None:
    workflow_id = service.start(
        board_slug="wingstaff-test",
        target_repository=str(target_repository),
        goal="Cancel me",
        stage_profiles=STAGE_PROFILES,
        workflow_id="workflow-cancel",
    ).workflow_id

    result = call(
        tools.cancel,
        {"workflow_id": workflow_id, "reason": "operator stopped workflow"},
    )

    assert result["success"] is True
    assert {"status", "failure_reason"}.isdisjoint(result["workflow"])


def test_handlers_return_json_errors_instead_of_raising(
    service: WorkflowService,
    target_repository: Path,
) -> None:
    workflow_id = seed_planned(service, target_repository)

    wrong_digest = call(
        tools.approve,
        {"workflow_id": workflow_id, "plan_digest": "wrong"},
    )
    assert wrong_digest["success"] is False
    assert wrong_digest["error"] == "PolicyViolationError"
    assert "current plan digest" in wrong_digest["message"]

    unknown = call(tools.status, {"workflow_id": workflow_id, "extra": True})
    assert unknown == {
        "success": False,
        "error": "ValueError",
        "message": "unknown arguments: extra",
    }

    missing = call(tools.cancel, {"workflow_id": workflow_id})
    assert missing["success"] is False
    assert missing["message"] == "missing required arguments: reason"


def test_record_skill_activation_requires_exact_kanban_worker_context(
    service: WorkflowService,
    target_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow_id = service.start(
        board_slug="wingstaff-test",
        target_repository=str(target_repository),
        goal="Assess definition skills",
        stage_profiles=STAGE_PROFILES,
        workflow_id="workflow-activation",
    ).workflow_id
    arguments = {
        "workflow_id": workflow_id,
        "stage": "define",
        "supersedes_digest": None,
        "decisions": activation_decisions(service, workflow_id),
    }

    absent = call(tools.record_skill_activation, arguments)
    assert absent["success"] is False
    assert "Kanban worker context" in absent["message"]

    ledger = service.status(workflow_id)
    card = ledger.card_for(WorkflowStage.DEFINE)
    assert card is not None
    monkeypatch.setenv("HERMES_KANBAN_BOARD", "wrong-board")
    monkeypatch.setenv("HERMES_KANBAN_TASK", card.task_id)
    wrong_board = call(tools.record_skill_activation, arguments)
    assert wrong_board["success"] is False
    assert "board" in wrong_board["message"]

    monkeypatch.setenv("HERMES_KANBAN_BOARD", ledger.board_slug)
    monkeypatch.setenv("HERMES_KANBAN_TASK", "wrong-card")
    wrong_card = call(tools.record_skill_activation, arguments)
    assert wrong_card["success"] is False
    assert "task" in wrong_card["message"]

    monkeypatch.setenv("HERMES_KANBAN_TASK", card.task_id)
    recorded = call(tools.record_skill_activation, arguments)
    assert recorded["success"] is True
    assert recorded["activation"]["state"] == "finalized"
    assert recorded["activation"]["sequence"] == 1
    assert recorded["workflow"]["pack_source_revision"] == load_pack(
        "addyosmani"
    ).source_revision

    repeated = call(tools.record_skill_activation, arguments)
    assert repeated["success"] is True
    assert repeated["activation"] == recorded["activation"]
    assert len(repeated["workflow"]["activation_manifests"]) == 1


def test_record_skill_activation_rejects_malformed_and_persists_blocked_supersession(
    service: WorkflowService,
    target_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow_id = service.start(
        board_slug="wingstaff-test",
        target_repository=str(target_repository),
        goal="Reassess definition skills",
        stage_profiles=STAGE_PROFILES,
        workflow_id="workflow-activation-supersession",
    ).workflow_id
    ledger = service.status(workflow_id)
    card = ledger.card_for(WorkflowStage.DEFINE)
    assert card is not None
    monkeypatch.setenv("HERMES_KANBAN_BOARD", ledger.board_slug)
    monkeypatch.setenv("HERMES_KANBAN_TASK", card.task_id)
    decisions = activation_decisions(service, workflow_id)
    first = call(
        tools.record_skill_activation,
        {
            "workflow_id": workflow_id,
            "stage": "define",
            "supersedes_digest": None,
            "decisions": decisions,
        },
    )
    digest = first["activation"]["digest"]

    malformed = [*decisions[:-1], {**decisions[-1], "unknown": True}]
    rejected = call(
        tools.record_skill_activation,
        {
            "workflow_id": workflow_id,
            "stage": "define",
            "supersedes_digest": digest,
            "decisions": malformed,
        },
    )
    assert rejected["success"] is False
    assert "fields" in rejected["message"]

    blocked = [*decisions]
    required_index = next(
        index for index, decision in enumerate(blocked) if decision["rank"] == 1
    )
    blocked[required_index] = {
        **blocked[required_index],
        "category": "blocked",
        "rank": None,
        "rationale": "The required capability is unavailable.",
    }
    superseded = call(
        tools.record_skill_activation,
        {
            "workflow_id": workflow_id,
            "stage": "define",
            "supersedes_digest": digest,
            "decisions": blocked,
        },
    )
    assert superseded["success"] is True
    assert superseded["activation"]["sequence"] == 2
    assert superseded["activation"]["blocked"] is True


def test_record_skill_activation_reloads_after_reservation_race(
    service: WorkflowService,
    target_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow_id = service.start(
        board_slug="wingstaff-test",
        target_repository=str(target_repository),
        goal="Retry activation reservation",
        stage_profiles=STAGE_PROFILES,
        workflow_id="workflow-activation-race",
    ).workflow_id
    ledger = service.status(workflow_id)
    card = ledger.card_for(WorkflowStage.DEFINE)
    assert card is not None
    monkeypatch.setenv("HERMES_KANBAN_BOARD", ledger.board_slug)
    monkeypatch.setenv("HERMES_KANBAN_TASK", card.task_id)
    original_update = service.store.update
    raced = False

    def update_with_one_race(updated, *, expected_updated_at=None):
        nonlocal raced
        if updated.activation_manifests and not raced:
            raced = True
            raise StoreError(f"workflow {workflow_id!r} was modified concurrently")
        return original_update(updated, expected_updated_at=expected_updated_at)

    monkeypatch.setattr(service.store, "update", update_with_one_race)
    result = call(
        tools.record_skill_activation,
        {
            "workflow_id": workflow_id,
            "stage": "define",
            "supersedes_digest": None,
            "decisions": activation_decisions(service, workflow_id),
        },
    )

    assert raced is True
    assert result["success"] is True
    assert result["activation"]["state"] == "finalized"


def test_start_requires_explicit_board_and_local_repository(
    service: WorkflowService,
) -> None:
    missing_board = call(
        tools.start,
        {
            "target_repository": "/tmp/repo",
            "goal": "missing board",
            "stage_profiles": STAGE_PROFILES,
            "workflow_id": "workflow-missing-board",
        },
    )
    assert missing_board["success"] is False
    assert missing_board["message"] == "missing required arguments: board_slug"

    for target in ("owner/repo", "https://example.invalid/repo.git"):
        result = call(
            tools.start,
            {
                "board_slug": "wingstaff-test",
                "target_repository": target,
                "goal": "invalid target",
                "stage_profiles": STAGE_PROFILES,
                "workflow_id": "workflow-invalid-target",
            },
        )
        assert result["success"] is False
        assert result["error"] == "ServiceError"
        assert "absolute local path" in result["message"]


def test_pack_info_is_strict_and_reports_valid_pack() -> None:
    result = call(tools.pack_info, {"pack": "addyosmani"})
    assert result["success"] is True
    assert result["pack"] == "addyosmani"
    assert result["source_revision"] == "7ce442de03ddc1b72480c3b48d55c62880ea2a90"
    assert result["skills"]["define"][0] == {
        "name": "interview-me",
        "provider": {
            "kind": "external",
            "reference": "addyosmani/agent-skills/skills/interview-me",
        },
        "content_digest": {
            "sha256": "f271a5931d374e3ab970c79e0461a30b741123271519e599b5b9a29b8db2ffaf",
            "source": "pack",
        },
        "activation": "conditional",
    }

    aidlc = call(tools.pack_info, {"pack": "aidlc"})
    aidlc_skill = aidlc["skills"]["define"][0]
    assert aidlc_skill["name"] == "aidlc-adapter"
    assert aidlc_skill["provider"] == {
        "kind": "bundled",
        "reference": "aidlc-adapter",
    }
    assert aidlc_skill["activation"] == "required"
    assert aidlc_skill["content_digest"]["source"] == "bundled-resource"
    assert len(aidlc_skill["content_digest"]["sha256"]) == 64

    invalid = call(tools.pack_info, {"pack": "addyosmani", "extra": 1})
    assert invalid["success"] is False
    assert invalid["message"] == "unknown arguments: extra"


def test_execution_handlers_keep_json_boundary() -> None:
    cases = [
        (tools.submit_artifact, {"workflow_id": "workflow", "stage": "define", "content": "x"}),
        (tools.prepare_implementation, {"workflow_id": "workflow"}),
        (tools.capture_implementation, {"workflow_id": "workflow"}),
        (
            tools.record_verification,
            {"workflow_id": "workflow", "command": "pytest", "exit_code": 0, "output": "ok"},
        ),
        (tools.deliver, {"workflow_id": "workflow"}),
    ]

    for handler, arguments in cases:
        result = call(handler, {**arguments, "extra": True})
        assert result == {
            "success": False,
            "error": "ValueError",
            "message": "unknown arguments: extra",
        }


def test_public_schemas_have_no_removed_lifecycle_aliases() -> None:
    assert {schema["name"] for schema in schemas.ALL_TOOLS} == {
        "wingstaff_pack_info",
        "wingstaff_start",
        "wingstaff_status",
        "wingstaff_replace_constraints",
        "wingstaff_approve",
        "wingstaff_cancel",
        "wingstaff_submit_artifact",
        "wingstaff_prepare_implementation",
        "wingstaff_capture_implementation",
        "wingstaff_record_skill_activation",
        "wingstaff_record_verification",
        "wingstaff_deliver",
    }
    for schema in schemas.ALL_TOOLS:
        assert schema["parameters"]["additionalProperties"] is False
    decision = schemas.RECORD_SKILL_ACTIVATION["parameters"]["properties"]["decisions"]
    assert decision["maxItems"] == 32
    assert decision["items"]["additionalProperties"] is False


def test_service_rejects_repository_subdirectory(
    service: WorkflowService,
    target_repository: Path,
) -> None:
    child = target_repository / "child"
    child.mkdir()

    result = call(
        tools.start,
        {
            "board_slug": "wingstaff-test",
            "target_repository": str(child),
            "goal": "Reject repository subdirectory",
            "stage_profiles": STAGE_PROFILES,
            "workflow_id": "workflow-subdirectory",
        },
    )

    assert result["success"] is False
    assert result["error"] == "ServiceError"
    assert "repository root" in result["message"]