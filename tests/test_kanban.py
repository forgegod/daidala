from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from wingstaff.kanban import KanbanCoordinator, KanbanError
from wingstaff.packs import load_pack
from wingstaff.service import ServiceError, WorkflowService
from wingstaff.skills import (
    content_registry_from_digests,
    inventory_from_names,
    required_skills,
)
from wingstaff.state import WorkflowStage, WorkflowStatus
from wingstaff.store import WorkflowStore

NOW = datetime(2026, 7, 10, 14, 0, tzinfo=UTC)


class TickClock:
    def __init__(self) -> None:
        self.tick = 0

    def __call__(self) -> datetime:
        self.tick += 1
        return NOW + timedelta(minutes=self.tick)


class FakeKanbanHost:
    def __init__(self, *, fail_once: bool = False) -> None:
        self.fail_once = fail_once
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.tasks: dict[str, str] = {}

    def dispatch_tool(self, name: str, args: dict[str, object]) -> str:
        self.calls.append((name, args))
        if self.fail_once:
            self.fail_once = False
            return json.dumps({"ok": False, "error": "interrupted"})
        key = str(args["idempotency_key"])
        task_id = self.tasks.setdefault(key, f"t_{len(self.tasks) + 1:012x}")
        return json.dumps({"ok": True, "task_id": task_id, "status": "ready"})


@pytest.fixture
def target_repository(tmp_path: Path) -> Path:
    target = tmp_path / "target"
    target.mkdir()
    (target / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(target)], check=True)
    subprocess.run(["git", "-C", str(target), "add", "."], check=True)
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


def make_service(data_root: Path, host: FakeKanbanHost) -> WorkflowService:
    pack = load_pack("addyosmani")
    skills = required_skills(pack)
    return WorkflowService(
        WorkflowStore(data_root),
        clock=TickClock(),
        skill_inventory=inventory_from_names(skill.name for skill in skills),
        skill_content_registry=content_registry_from_digests(
            {skill.name: skill.content_digest for skill in skills}
        ),
        kanban=KanbanCoordinator(host.dispatch_tool),
    )


def prepare_approved(
    service: WorkflowService, target: Path, workflow_id: str
) -> tuple[str, str]:
    service.start(
        target_repository=str(target), goal="Change VALUE to 2", workflow_id=workflow_id
    )
    service.validate(workflow_id)
    service.submit_artifact(
        workflow_id, stage=WorkflowStage.DEFINE, content="# Definition\n"
    )
    planned = service.submit_artifact(
        workflow_id, stage=WorkflowStage.PLAN, content="# Plan\n"
    )
    plan = planned.artifact_for(WorkflowStage.PLAN)
    assert plan is not None
    service.approve(workflow_id, plan.digest)
    return workflow_id, plan.digest


def test_implementation_card_is_never_created_before_approval(
    tmp_path: Path, target_repository: Path
) -> None:
    host = FakeKanbanHost()
    service = make_service(tmp_path / "data", host)
    state = service.start(
        target_repository=str(target_repository),
        goal="Change VALUE to 2",
        workflow_id="not-approved",
    )

    with pytest.raises(ServiceError, match="approved"):
        service.prepare_implementation(state.workflow_id, assignee="engineer")

    assert host.calls == []


def test_restart_reuses_idempotent_card_and_persistent_worktree(
    tmp_path: Path, target_repository: Path
) -> None:
    host = FakeKanbanHost(fail_once=True)
    data_root = tmp_path / "data"
    service = make_service(data_root, host)
    workflow_id, _ = prepare_approved(service, target_repository, "restart-safe")

    with pytest.raises(KanbanError, match="interrupted"):
        service.prepare_implementation(workflow_id, assignee="engineer")

    persisted = service.status(workflow_id)
    assert persisted.status is WorkflowStatus.RUNNING
    assert persisted.current_stage is WorkflowStage.IMPLEMENT
    assert persisted.worktree_path is not None

    restarted = make_service(data_root, host)
    resumed = restarted.prepare_implementation(workflow_id, assignee="engineer")
    repeated = restarted.prepare_implementation(workflow_id, assignee="engineer")

    assert resumed.worktree_path == repeated.worktree_path == persisted.worktree_path
    assert len(host.calls) == 3
    assert len(host.tasks) == 1
    assert {call[1]["idempotency_key"] for call in host.calls} == {
        "wingstaff:restart-safe:implement"
    }
    _, args = host.calls[-1]
    assert args["assignee"] == "engineer"
    assert args["workspace_kind"] == "worktree"
    assert args["workspace_path"] == persisted.worktree_path
    assert args["skills"] == [
        "incremental-implementation",
        "test-driven-development",
        "source-driven-development",
        "doubt-driven-development",
    ]
    assert "Wingstaff workflow: restart-safe" in str(args["body"])
    assert "Stage: implement" in str(args["body"])
