from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from wingstaff.errors import PolicyViolationError
from wingstaff.execution import ExecutionError
from wingstaff.kanban import KanbanGraphAdapter
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
        self.tick = 0

    def __call__(self) -> datetime:
        self.tick += 1
        return NOW + timedelta(minutes=self.tick)


class FixtureWorkflowService(WorkflowService):
    fixture_pack_name: str


@pytest.fixture
def target_repository(tmp_path: Path) -> Path:
    target = tmp_path / "target"
    target.mkdir()
    (target / "calculator.py").write_text(
        "def answer():\n    return 1\n", encoding="utf-8"
    )
    (target / "test_calculator.py").write_text(
        "from calculator import answer\n\n\ndef test_answer():\n    assert answer() == 2\n",
        encoding="utf-8",
    )
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
            "failing fixture",
        ],
        check=True,
    )
    return target.resolve()


@pytest.fixture(params=("addyosmani", "aidlc"))
def service(
    tmp_path: Path,
    request: pytest.FixtureRequest,
    kanban_adapter: KanbanGraphAdapter,
) -> FixtureWorkflowService:
    pack = load_pack(request.param)
    inventory = inventory_from_names(skill.name for skill in required_skills(pack))
    result = FixtureWorkflowService(
        WorkflowStore(tmp_path / "data"),
        clock=TickClock(),
        skill_inventory=inventory,
        skill_content_registry=content_registry_from_digests(
            {skill.name: skill.content_digest for skill in required_skills(pack)}
        ),
        kanban=kanban_adapter,
    )
    result.fixture_pack_name = pack.name
    return result


def prepare_planned_workflow(
    service: FixtureWorkflowService,
    target: Path,
    workflow_id: str,
) -> tuple[str, str]:
    state = service.start(
        board_slug="wingstaff-test",
        target_repository=str(target),
        goal="Make the deliberately failing test pass",
        stage_profiles=STAGE_PROFILES,
        pack_name=service.fixture_pack_name,
        workflow_id=workflow_id,
    )
    state = service.submit_artifact(
        state.workflow_id,
        stage=WorkflowStage.DEFINE,
        content="# Definition\n\n`answer()` must return 2.\n",
    )
    state = service.submit_artifact(
        state.workflow_id,
        stage=WorkflowStage.PLAN,
        content="# Plan\n\nChange `calculator.py`, run pytest, review the diff.\n",
    )
    plan = state.artifact_for(WorkflowStage.PLAN)
    assert plan is not None
    return state.workflow_id, plan.digest


def run_fixture_tests(worktree: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=worktree,
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )


def test_thin_workflow_delivers_verified_uncommitted_diff(
    service: FixtureWorkflowService,
    target_repository: Path,
) -> None:
    baseline = subprocess.run(
        ["git", "-C", str(target_repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    workflow_id, plan_digest = prepare_planned_workflow(
        service, target_repository, "workflow-success"
    )

    with pytest.raises(PolicyViolationError, match="approval"):
        service.prepare_implementation(workflow_id)

    service.approve(workflow_id, plan_digest)
    implementing = service.prepare_implementation(workflow_id)
    assert implementing.worktree_path is not None
    worktree = Path(implementing.worktree_path)
    assert worktree != target_repository
    assert worktree.is_dir()

    (worktree / "calculator.py").write_text(
        "def answer():\n    return 2\n", encoding="utf-8"
    )
    (worktree / "notes.txt").write_text("verified fixture\n", encoding="utf-8")
    verifying = service.capture_implementation(workflow_id)
    implementation = verifying.artifact_for(WorkflowStage.IMPLEMENT)
    assert implementation is not None
    diff = Path(implementation.path).read_text(encoding="utf-8")
    assert "return 2" in diff
    assert "notes.txt" in diff

    verification = run_fixture_tests(worktree)
    assert verification.returncode == 0, verification.stdout + verification.stderr
    reviewing = service.record_verification(
        workflow_id,
        command=f"{sys.executable} -m pytest -q",
        exit_code=verification.returncode,
        output=verification.stdout + verification.stderr,
    )
    assert reviewing.verification_evidence[-1].exit_code == 0

    service.submit_artifact(
        workflow_id,
        stage=WorkflowStage.REVIEW,
        content="# Review\n\nThe diff is scoped and pytest passes.\n",
    )
    worktree_head = subprocess.run(
        ["git", "-C", str(worktree), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    completed = service.deliver(workflow_id)

    delivery = completed.artifact_for(WorkflowStage.DELIVER)
    assert delivery is not None
    payload = json.loads(Path(delivery.path).read_text(encoding="utf-8"))
    assert payload["changed_paths"] == ["calculator.py", "notes.txt"]
    assert payload["verification"][0]["exit_code"] == 0
    assert payload["committed"] is False
    assert payload["pushed"] is False
    assert not worktree.exists()

    assert "return 1" in (target_repository / "calculator.py").read_text(encoding="utf-8")
    target_head = subprocess.run(
        ["git", "-C", str(target_repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert target_head == worktree_head == baseline


def test_cancel_rolls_back_owned_implementation_worktree(
    service: FixtureWorkflowService,
    target_repository: Path,
) -> None:
    workflow_id, plan_digest = prepare_planned_workflow(
        service, target_repository, "workflow-cancelled"
    )
    service.approve(workflow_id, plan_digest)
    implementing = service.prepare_implementation(workflow_id)
    assert implementing.worktree_path is not None
    worktree = Path(implementing.worktree_path)
    (worktree / "calculator.py").write_text("def answer():\n    return 9\n", encoding="utf-8")

    cancelled = service.cancel(workflow_id, "Operator requested rollback")

    assert cancelled.worktree_path is None
    assert cancelled.worktree_owned is False
    assert not worktree.exists()
    assert "return 1" in (target_repository / "calculator.py").read_text(encoding="utf-8")


def test_failed_verification_blocks_delivery(
    service: FixtureWorkflowService,
    target_repository: Path,
) -> None:
    workflow_id, plan_digest = prepare_planned_workflow(
        service, target_repository, "workflow-failure"
    )
    service.approve(workflow_id, plan_digest)
    implementing = service.prepare_implementation(workflow_id)
    assert implementing.worktree_path is not None
    worktree = Path(implementing.worktree_path)
    (worktree / "calculator.py").write_text(
        "def answer():\n    return 0\n", encoding="utf-8"
    )
    service.capture_implementation(workflow_id)

    verification = run_fixture_tests(worktree)
    assert verification.returncode != 0
    blocked = service.record_verification(
        workflow_id,
        command=f"{sys.executable} -m pytest -q",
        exit_code=verification.returncode,
        output=verification.stdout + verification.stderr,
    )

    assert blocked.verification_evidence[-1].exit_code != 0
    assert "status" not in blocked.to_dict()
    with pytest.raises(PolicyViolationError, match="successful verification"):
        service.deliver(workflow_id)


def test_capture_requires_real_diff_and_safe_workflow_id(
    service: FixtureWorkflowService,
    target_repository: Path,
) -> None:
    with pytest.raises(ExecutionError, match="workflow_id"):
        service.start(
            board_slug="wingstaff-test",
            target_repository=str(target_repository),
            goal="unsafe id",
            stage_profiles=STAGE_PROFILES,
            pack_name=service.fixture_pack_name,
            workflow_id="../escape",
        )

    workflow_id, plan_digest = prepare_planned_workflow(
        service, target_repository, "workflow-empty"
    )
    service.approve(workflow_id, plan_digest)
    service.prepare_implementation(workflow_id)

    with pytest.raises(ExecutionError, match="no working-tree diff"):
        service.capture_implementation(workflow_id)
