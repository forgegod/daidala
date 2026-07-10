from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from wingstaff import schemas, tools
from wingstaff.packs import load_pack
from wingstaff.service import WorkflowService
from wingstaff.skills import inventory_from_names, required_skills
from wingstaff.state import WorkflowStage, WorkflowStatus
from wingstaff.store import WorkflowStore
from wingstaff.workflow import record_artifact

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
    instance = WorkflowService(
        WorkflowStore(tmp_path / "data"),
        clock=TickClock(),
        id_factory=lambda: "workflow-generated",
        skill_inventory=inventory_from_names(
            skill.name for skill in required_skills(pack)
        ),
    )
    monkeypatch.setattr(tools, "_service_factory", lambda: instance)
    return instance


def call(handler, args: object) -> dict:
    raw = handler(args, task_id="test")
    assert isinstance(raw, str)
    return json.loads(raw)


def seed_awaiting_approval(
    service: WorkflowService, target_repository: Path
) -> str:
    state = service.start(
        target_repository=str(target_repository),
        goal="Fix the failing fixture",
        workflow_id="workflow-plan",
    )
    state = service.validate(state.workflow_id)
    state = record_artifact(
        state,
        stage=WorkflowStage.DEFINE,
        path="artifacts/define.md",
        digest="define-v1",
        recorded_at=state.updated_at,
    )
    state = record_artifact(
        state,
        stage=WorkflowStage.PLAN,
        path="artifacts/plan.md",
        digest="plan-v1",
        recorded_at=state.updated_at,
    )
    service.store.update(state)
    return state.workflow_id


def test_start_and_status_return_durable_json_state(
    service: WorkflowService, target_repository: Path
) -> None:
    started = call(
        tools.start,
        {
            "target_repository": str(target_repository),
            "goal": "Add one deterministic behavior",
        },
    )

    assert started["success"] is True
    workflow = started["workflow"]
    assert workflow["workflow_id"] == "workflow-generated"
    assert workflow["status"] == "draft"
    assert workflow["pack_source_revision"].startswith("wingstaff@")

    status = call(tools.status, {"workflow_id": workflow["workflow_id"]})
    assert status == started


def test_validate_records_clean_baseline(
    service: WorkflowService, target_repository: Path
) -> None:
    workflow_id = service.start(
        target_repository=str(target_repository),
        goal="Validate target",
    ).workflow_id

    result = call(tools.validate, {"workflow_id": workflow_id})

    assert result["success"] is True
    state = result["workflow"]
    assert state["status"] == "running"
    assert state["target_is_clean"] is True
    assert state["baseline_commit"]


def test_validate_dirty_target_blocks_workflow(
    service: WorkflowService, target_repository: Path
) -> None:
    workflow_id = service.start(
        target_repository=str(target_repository),
        goal="Reject dirty target",
    ).workflow_id
    (target_repository / "dirty.txt").write_text("dirty\n", encoding="utf-8")

    result = call(tools.validate, {"workflow_id": workflow_id})

    assert result["success"] is True
    assert result["workflow"]["status"] == "blocked"
    assert result["workflow"]["failure_reason"] == "target repository is dirty"


def test_approve_and_modify_bind_and_invalidate_exact_plan(
    service: WorkflowService, target_repository: Path
) -> None:
    workflow_id = seed_awaiting_approval(service, target_repository)

    approved = call(
        tools.approve,
        {"workflow_id": workflow_id, "plan_digest": "plan-v1"},
    )
    assert approved["success"] is True
    assert approved["workflow"]["status"] == "approved"
    assert approved["workflow"]["approval"]["plan_digest"] == "plan-v1"

    modified = call(
        tools.modify,
        {
            "workflow_id": workflow_id,
            "path": "artifacts/plan.md",
            "digest": "plan-v2",
        },
    )
    assert modified["success"] is True
    assert modified["workflow"]["status"] == "awaiting_approval"
    assert modified["workflow"]["approval"] is None
    plan = next(
        artifact
        for artifact in modified["workflow"]["artifacts"]
        if artifact["stage"] == "plan"
    )
    assert plan["digest"] == "plan-v2"


def test_cancel_records_terminal_reason(
    service: WorkflowService, target_repository: Path
) -> None:
    workflow_id = service.start(
        target_repository=str(target_repository),
        goal="Cancel me",
    ).workflow_id

    result = call(
        tools.cancel,
        {"workflow_id": workflow_id, "reason": "operator stopped workflow"},
    )

    assert result["success"] is True
    assert result["workflow"]["status"] == "cancelled"
    assert result["workflow"]["failure_reason"] == "operator stopped workflow"


def test_handlers_return_json_errors_instead_of_raising(
    service: WorkflowService, target_repository: Path
) -> None:
    workflow_id = seed_awaiting_approval(service, target_repository)

    wrong_digest = call(
        tools.approve,
        {"workflow_id": workflow_id, "plan_digest": "wrong"},
    )
    assert wrong_digest["success"] is False
    assert wrong_digest["error"] == "InvalidTransitionError"
    assert "current plan digest" in wrong_digest["message"]

    unknown = call(tools.status, {"workflow_id": workflow_id, "extra": True})
    assert unknown == {
        "success": False,
        "error": "ValueError",
        "message": "unknown arguments: extra",
    }

    missing = call(tools.cancel, {"workflow_id": workflow_id})
    assert missing["success"] is False
    assert "missing required arguments: reason" == missing["message"]


def test_start_rejects_remote_and_relative_targets(service: WorkflowService) -> None:
    for target in ("owner/repo", "https://example.invalid/repo.git"):
        result = call(
            tools.start,
            {"target_repository": target, "goal": "invalid target"},
        )
        assert result["success"] is False
        assert result["error"] == "ServiceError"
        assert "absolute local path" in result["message"]


def test_pack_info_is_strict_and_still_reports_valid_pack() -> None:
    result = call(tools.pack_info, {"pack": "addyosmani"})
    assert result["success"] is True
    assert result["pack"] == "addyosmani"

    invalid = call(tools.pack_info, {"pack": "addyosmani", "extra": 1})
    assert invalid["success"] is False
    assert invalid["message"] == "unknown arguments: extra"


def test_all_schemas_reject_unknown_fields() -> None:
    assert {schema["name"] for schema in schemas.ALL_TOOLS} == {
        "wingstaff_pack_info",
        "wingstaff_start",
        "wingstaff_status",
        "wingstaff_validate",
        "wingstaff_approve",
        "wingstaff_modify",
        "wingstaff_cancel",
    }
    for schema in schemas.ALL_TOOLS:
        assert schema["parameters"]["additionalProperties"] is False


def test_service_rejects_repository_subdirectory(
    service: WorkflowService, target_repository: Path
) -> None:
    child = target_repository / "child"
    child.mkdir()
    workflow_id = service.start(
        target_repository=str(child),
        goal="Reject repository subdirectory",
    ).workflow_id

    result = call(tools.validate, {"workflow_id": workflow_id})
    assert result["success"] is False
    assert result["error"] == "ServiceError"
    assert "repository root" in result["message"]
    assert service.status(workflow_id).status is WorkflowStatus.DRAFT
