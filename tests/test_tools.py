from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from wingstaff import schemas, tools
from wingstaff.packs import load_pack
from wingstaff.service import WorkflowService
from wingstaff.skills import (
    content_registry_from_digests,
    inventory_from_names,
    required_skills,
)
from wingstaff.state import WorkflowStage
from wingstaff.store import WorkflowStore

NOW = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)


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
def service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> WorkflowService:
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
    )
    monkeypatch.setattr(tools, "_service_factory", lambda: instance)
    return instance


def call(handler, args: object) -> dict:
    raw = handler(args, task_id="test")
    assert isinstance(raw, str)
    return json.loads(raw)


def seed_planned(service: WorkflowService, target: Path) -> str:
    ledger = service.start(
        board_slug="wingstaff-test",
        target_repository=str(target),
        goal="Fix the failing fixture",
        workflow_id="workflow-plan",
    )
    ledger = service.submit_artifact(
        ledger.workflow_id,
        stage=WorkflowStage.DEFINE,
        content="# Definition\n",
    )
    ledger = service.submit_artifact(
        ledger.workflow_id,
        stage=WorkflowStage.PLAN,
        content="# Plan\n",
    )
    return ledger.workflow_id


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
        },
    )

    assert started["success"] is True
    ledger = started["workflow"]
    assert ledger["workflow_id"] == "workflow-generated"
    assert ledger["board_slug"] == "wingstaff-test"
    assert ledger["baseline_commit"]
    assert ledger["skill_digests"]
    assert {"status", "current_stage", "failure_reason"}.isdisjoint(ledger)
    assert call(tools.status, {"workflow_id": "workflow-generated"}) == started


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
        },
    )

    assert result["success"] is False
    assert result["error"] == "ServiceError"
    assert "dirty" in result["message"]
    assert service.store.list_all() == ()


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


def test_cancel_without_owned_worktree_does_not_create_lifecycle_state(
    service: WorkflowService,
    target_repository: Path,
) -> None:
    workflow_id = service.start(
        board_slug="wingstaff-test",
        target_repository=str(target_repository),
        goal="Cancel me",
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


def test_start_requires_explicit_board_and_local_repository(
    service: WorkflowService,
) -> None:
    missing_board = call(
        tools.start,
        {"target_repository": "/tmp/repo", "goal": "missing board"},
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
            },
        )
        assert result["success"] is False
        assert result["error"] == "ServiceError"
        assert "absolute local path" in result["message"]


def test_pack_info_is_strict_and_reports_valid_pack() -> None:
    result = call(tools.pack_info, {"pack": "addyosmani"})
    assert result["success"] is True
    assert result["pack"] == "addyosmani"

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
        "wingstaff_approve",
        "wingstaff_cancel",
        "wingstaff_submit_artifact",
        "wingstaff_prepare_implementation",
        "wingstaff_capture_implementation",
        "wingstaff_record_verification",
        "wingstaff_deliver",
    }
    for schema in schemas.ALL_TOOLS:
        assert schema["parameters"]["additionalProperties"] is False


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
        },
    )

    assert result["success"] is False
    assert result["error"] == "ServiceError"
    assert "repository root" in result["message"]