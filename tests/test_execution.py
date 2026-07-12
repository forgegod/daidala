from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from wingstaff.errors import PolicyViolationError
from wingstaff.execution import ExecutionError, ExecutionWorkspace
from wingstaff.kanban import KanbanError, KanbanGraphAdapter
from wingstaff.packs import SkillActivationMode, load_pack
from wingstaff.service import ServiceError, WorkflowService
from wingstaff.skills import (
    content_registry_from_digests,
    inventory_from_names,
    required_skills,
)
from wingstaff.state import (
    ActivationCategory,
    ActivationDecision,
    ActivationManifest,
    ActivationManifestReference,
    WorkflowConstraintsArtifact,
    WorkflowConstraintsIdentity,
    WorkflowStage,
)
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

    def _current_context(self, workflow_id: str, stage: WorkflowStage) -> dict[str, str]:
        ledger = self.status(workflow_id)
        card = ledger.card_for(stage)
        assert card is not None
        return {"board_slug": ledger.board_slug, "task_id": card.task_id}

    def submit_artifact(self, workflow_id: str, *, stage: WorkflowStage, **kwargs):
        return super().submit_artifact(
            workflow_id, stage=stage, **self._current_context(workflow_id, stage), **kwargs
        )

    def capture_implementation(self, workflow_id: str, **kwargs):
        return super().capture_implementation(
            workflow_id,
            **self._current_context(workflow_id, WorkflowStage.IMPLEMENT),
            **kwargs,
        )

    def record_verification(self, workflow_id: str, **kwargs):
        return super().record_verification(
            workflow_id,
            **self._current_context(workflow_id, WorkflowStage.VERIFY),
            **kwargs,
        )

    def deliver(self, workflow_id: str, **kwargs):
        return super().deliver(
            workflow_id,
            **self._current_context(workflow_id, WorkflowStage.DELIVER),
            **kwargs,
        )


def record_stage_activation(
    service: FixtureWorkflowService,
    workflow_id: str,
    stage: WorkflowStage,
    *,
    overrides: dict[str, ActivationCategory] | None = None,
) -> ActivationManifestReference:
    ledger = service.status(workflow_id)
    card = ledger.card_for(stage)
    assert card is not None
    pack = load_pack(ledger.pack_name)
    pack_stage = next(row for row in pack.stages if row.id == stage.value)
    conditional_categories = (
        ActivationCategory.APPLICABLE,
        ActivationCategory.DEFERRED,
        ActivationCategory.NOT_APPLICABLE,
    )
    applicable_rank = 0
    conditional_index = 0
    decisions = []
    for skill in pack_stage.skills:
        if overrides and skill.name in overrides:
            category = overrides[skill.name]
        elif skill.activation is SkillActivationMode.REQUIRED:
            category = ActivationCategory.APPLICABLE
        else:
            category = conditional_categories[conditional_index % len(conditional_categories)]
            conditional_index += 1
        rank = None
        if category is ActivationCategory.APPLICABLE:
            applicable_rank += 1
            rank = applicable_rank
        decisions.append(
            {
                "name": skill.name,
                "category": category.value,
                "rank": rank,
                "matched_criteria": [f"Pinned criteria were assessed for {skill.name}."],
                "evidence": [f"The {stage.value} card and parent handoffs were inspected."],
                "rationale": f"Classify {skill.name} as {category.value} for this fixture.",
                "condition": (
                    "Apply if the stage exposes the matching specialist condition."
                    if category is ActivationCategory.DEFERRED
                    else None
                ),
            }
        )
    reference, _ = service.record_skill_activation(
        workflow_id,
        stage=stage,
        supersedes_digest=None,
        decisions=decisions,
        board_slug=ledger.board_slug,
        task_id=card.task_id,
    )
    return reference


def activation_handoff(ledger, stage: WorkflowStage) -> tuple[str, list[str]]:
    reference = ledger.activation_for(stage)
    assert reference is not None
    manifest = json.loads(Path(reference.path).read_text(encoding="utf-8"))
    active = [
        decision["name"]
        for decision in manifest["decisions"]
        if decision["category"] == ActivationCategory.APPLICABLE.value
    ]
    return reference.digest, active


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
    record_stage_activation(service, workflow_id, WorkflowStage.DEFINE)
    state = service.submit_artifact(
        state.workflow_id,
        stage=WorkflowStage.DEFINE,
        content="# Definition\n\n`answer()` must return 2.\n",
    )
    record_stage_activation(service, workflow_id, WorkflowStage.PLAN)
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
    fake_kanban_host,
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

    def complete_stage(stage: WorkflowStage, artifact_digest: str) -> None:
        ledger = service.status(workflow_id)
        card = ledger.card_for(stage)
        assert card is not None
        activation_digest, active_skills = activation_handoff(ledger, stage)
        fake_kanban_host.dispatch(
            "kanban_complete",
            {
                "task_id": card.task_id,
                "summary": f"{stage.value} evidence recorded",
                "metadata": {
                    "schema": "wingstaff.handoff/v1",
                    "workflow_id": workflow_id,
                    "plan_revision": ledger.activation_revision_for(stage),
                    "stage": stage.value,
                    "pack": ledger.pack_name,
                    "pack_revision": ledger.pack_source_revision,
                    "outcome": "completed",
                    "artifact_refs": [artifact_digest],
                    "artifact_digest": artifact_digest,
                    "skill_activation_digest": activation_digest,
                    "active_skills": active_skills,
                },
            },
        )

    planned = service.status(workflow_id)
    definition = planned.artifact_for(WorkflowStage.DEFINE)
    plan = planned.artifact_for(WorkflowStage.PLAN)
    assert definition is not None and plan is not None
    complete_stage(WorkflowStage.DEFINE, definition.digest)
    complete_stage(WorkflowStage.PLAN, plan.digest)

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
    record_stage_activation(service, workflow_id, WorkflowStage.IMPLEMENT)
    verifying = service.capture_implementation(workflow_id)
    implementation = verifying.artifact_for(WorkflowStage.IMPLEMENT)
    assert implementation is not None
    complete_stage(WorkflowStage.IMPLEMENT, implementation.digest)
    diff = Path(implementation.path).read_text(encoding="utf-8")
    assert "return 2" in diff
    assert "notes.txt" in diff

    verification = run_fixture_tests(worktree)
    assert verification.returncode == 0, verification.stdout + verification.stderr
    record_stage_activation(service, workflow_id, WorkflowStage.VERIFY)
    reviewing = service.record_verification(
        workflow_id,
        command=f"{sys.executable} -m pytest -q",
        exit_code=verification.returncode,
        output=verification.stdout + verification.stderr,
    )
    assert reviewing.verification_evidence[-1].exit_code == 0
    complete_stage(
        WorkflowStage.VERIFY,
        reviewing.verification_evidence[-1].output_digest,
    )

    record_stage_activation(service, workflow_id, WorkflowStage.REVIEW)
    reviewed = service.submit_artifact(
        workflow_id,
        stage=WorkflowStage.REVIEW,
        content="# Review\n\nThe diff is scoped and pytest passes.\n",
    )
    review = reviewed.artifact_for(WorkflowStage.REVIEW)
    assert review is not None
    complete_stage(WorkflowStage.REVIEW, review.digest)
    worktree_head = subprocess.run(
        ["git", "-C", str(worktree), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    record_stage_activation(service, workflow_id, WorkflowStage.DELIVER)
    completed = service.deliver(workflow_id)

    delivery = completed.artifact_for(WorkflowStage.DELIVER)
    assert delivery is not None
    complete_stage(WorkflowStage.DELIVER, delivery.digest)
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

    assert len(fake_kanban_host.cards) == 7
    assert all(card["status"] == "done" for card in fake_kanban_host.cards.values())
    for stage in (
        WorkflowStage.DEFINE,
        WorkflowStage.PLAN,
        WorkflowStage.IMPLEMENT,
        WorkflowStage.VERIFY,
        WorkflowStage.REVIEW,
        WorkflowStage.DELIVER,
    ):
        card = completed.card_for(stage)
        assert card is not None
        assert fake_kanban_host.cards[card.task_id]["completion_metadata"]["schema"] == (
            "wingstaff.handoff/v1"
        )

    categories = {
        decision["category"]
        for reference in completed.activation_manifests
        for decision in json.loads(Path(reference.path).read_text(encoding="utf-8"))[
            "decisions"
        ]
    }
    if service.fixture_pack_name == "addyosmani":
        assert {
            ActivationCategory.APPLICABLE.value,
            ActivationCategory.DEFERRED.value,
            ActivationCategory.NOT_APPLICABLE.value,
        } <= categories
    else:
        assert categories == {ActivationCategory.APPLICABLE.value}


def test_blocked_activation_denies_stage_evidence_without_completion_handoff(
    service: FixtureWorkflowService,
    target_repository: Path,
    fake_kanban_host,
) -> None:
    ledger = service.start(
        board_slug="wingstaff-test",
        target_repository=str(target_repository),
        goal="Prove blocked activation fails closed",
        stage_profiles=STAGE_PROFILES,
        pack_name=service.fixture_pack_name,
        workflow_id="workflow-blocked-activation",
    )
    pack = load_pack(ledger.pack_name)
    define = next(row for row in pack.stages if row.id == WorkflowStage.DEFINE.value)
    blocked_skill = define.skills[0]
    reference = record_stage_activation(
        service,
        ledger.workflow_id,
        WorkflowStage.DEFINE,
        overrides={blocked_skill.name: ActivationCategory.BLOCKED},
    )

    assert reference.blocked is True
    with pytest.raises(PolicyViolationError, match="define skill activation is blocked"):
        service.submit_artifact(
            ledger.workflow_id,
            stage=WorkflowStage.DEFINE,
            content="# Definition\n",
        )
    card = service.status(ledger.workflow_id).card_for(WorkflowStage.DEFINE)
    assert card is not None
    assert "completion_metadata" not in fake_kanban_host.cards[card.task_id]


def test_evidence_rejects_wrong_board_and_stale_card_context(
    service: FixtureWorkflowService,
    target_repository: Path,
) -> None:
    ledger = service.start(
        board_slug="wingstaff-test",
        target_repository=str(target_repository),
        goal="Reject stale worker evidence",
        stage_profiles=STAGE_PROFILES,
        pack_name=service.fixture_pack_name,
        workflow_id="workflow-stale-evidence",
    )
    record_stage_activation(service, ledger.workflow_id, WorkflowStage.DEFINE)
    card = ledger.card_for(WorkflowStage.DEFINE)
    assert card is not None

    with pytest.raises(ServiceError, match="board"):
        WorkflowService.submit_artifact(
            service,
            ledger.workflow_id,
            stage=WorkflowStage.DEFINE,
            content="# Definition\n",
            board_slug="wrong-board",
            task_id=card.task_id,
        )
    with pytest.raises(ServiceError, match="task"):
        WorkflowService.submit_artifact(
            service,
            ledger.workflow_id,
            stage=WorkflowStage.DEFINE,
            content="# Definition\n",
            board_slug=ledger.board_slug,
            task_id="stale-card",
        )


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


def test_constraint_replacement_invalidates_and_recreates_graph_recoverably(
    service: FixtureWorkflowService,
    target_repository: Path,
    fake_kanban_host,
) -> None:
    workflow_id, plan_digest = prepare_planned_workflow(
        service, target_repository, "workflow-policy-replacement"
    )
    approved = service.approve(workflow_id, plan_digest)
    old_cards = {card.task_id for card in approved.card_references}
    old_artifacts = approved.artifacts
    assert approved.worktree_path is not None
    old_worktree = Path(approved.worktree_path)

    content = (
        "schema: wingstaff.workflow-constraints/v1\n"
        "global:\n"
        "  - Never commit or push.\n"
    )
    replaced = service.replace_constraints(
        workflow_id,
        content=content,
        expected_current_digest=None,
    )

    assert replaced.policy_revision == 1
    assert replaced.current_constraints_revision == 1
    assert replaced.approval is None
    assert replaced.worktree_path is None
    assert not old_worktree.exists()
    assert replaced.artifacts == old_artifacts
    assert replaced.artifact_for(WorkflowStage.DEFINE) is None
    assert replaced.artifact_for(WorkflowStage.PLAN) is None
    assert old_cards.issubset(set(fake_kanban_host.archived))
    define_card = replaced.card_for(WorkflowStage.DEFINE)
    plan_card = replaced.card_for(WorkflowStage.PLAN)
    assert define_card is not None and define_card.task_id not in old_cards
    assert plan_card is not None and plan_card.task_id not in old_cards

    digest = replaced.current_constraints_digest
    retried = service.replace_constraints(
        workflow_id,
        content=content,
        expected_current_digest=digest,
    )
    assert retried.constraint_references == replaced.constraint_references
    assert retried.card_references == replaced.card_references

    record_stage_activation(service, workflow_id, WorkflowStage.DEFINE)
    service.submit_artifact(
        workflow_id,
        stage=WorkflowStage.DEFINE,
        content="# Revised definition\n",
    )
    record_stage_activation(service, workflow_id, WorkflowStage.PLAN)
    planned = service.submit_artifact(
        workflow_id,
        stage=WorkflowStage.PLAN,
        content="# Revised plan\n",
    )
    plan = planned.artifact_for(WorkflowStage.PLAN)
    assert plan is not None
    reapproved = service.approve(workflow_id, plan.digest)
    assert reapproved.approval is not None
    assert reapproved.approval.constraints_revision == 1
    assert reapproved.approval.constraints_digest == digest


def test_constraint_replacement_persists_invalidation_before_failed_archival(
    service: FixtureWorkflowService,
    target_repository: Path,
    fake_kanban_host,
) -> None:
    workflow_id, plan_digest = prepare_planned_workflow(
        service, target_repository, "workflow-policy-archive-recovery"
    )
    approved = service.approve(workflow_id, plan_digest)
    assert approved.approval is not None

    def fail_archive(name: str, args: dict[str, object]) -> str:
        if name == "terminal" and " archive " in str(args["command"]):
            return json.dumps({"exit_code": 1, "output": "interrupted"})
        return fake_kanban_host.dispatch(name, args)

    service._kanban = KanbanGraphAdapter(fail_archive)
    content = "schema: wingstaff.workflow-constraints/v1\nglobal: [Never push.]\n"
    with pytest.raises(KanbanError, match="exit code 1"):
        service.replace_constraints(
            workflow_id,
            content=content,
            expected_current_digest=None,
        )

    interrupted = service.status(workflow_id)
    assert interrupted.policy_revision == 1
    assert interrupted.approval is None
    assert interrupted.worktree_owned is True

    service._kanban = KanbanGraphAdapter(fake_kanban_host.dispatch)
    recovered = service.replace_constraints(
        workflow_id,
        content=content,
        expected_current_digest=interrupted.current_constraints_digest,
    )
    assert recovered.worktree_owned is False
    assert recovered.card_for(WorkflowStage.DEFINE) is not None
    assert recovered.card_for(WorkflowStage.PLAN) is not None


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
    record_stage_activation(service, workflow_id, WorkflowStage.IMPLEMENT)
    service.capture_implementation(workflow_id)

    verification = run_fixture_tests(worktree)
    assert verification.returncode != 0
    record_stage_activation(service, workflow_id, WorkflowStage.VERIFY)
    blocked = service.record_verification(
        workflow_id,
        command=f"{sys.executable} -m pytest -q",
        exit_code=verification.returncode,
        output=verification.stdout + verification.stderr,
    )

    assert blocked.verification_evidence[-1].exit_code != 0
    assert "status" not in blocked.to_dict()
    record_stage_activation(service, workflow_id, WorkflowStage.DELIVER)
    with pytest.raises(PolicyViolationError, match="successful verification"):
        service.deliver(workflow_id)


def test_verification_worker_blocks_and_resumes_same_card_and_workspace(
    service: FixtureWorkflowService,
    target_repository: Path,
    fake_kanban_host,
) -> None:
    workflow_id, plan_digest = prepare_planned_workflow(
        service, target_repository, "workflow-worker-recovery"
    )
    service.approve(workflow_id, plan_digest)
    implementing = service.prepare_implementation(workflow_id)
    assert implementing.worktree_path is not None
    worktree = Path(implementing.worktree_path)
    (worktree / "calculator.py").write_text(
        "def answer():\n    return 2\n", encoding="utf-8"
    )
    record_stage_activation(service, workflow_id, WorkflowStage.IMPLEMENT)
    captured = service.capture_implementation(workflow_id)
    verify_card = captured.card_for(WorkflowStage.VERIFY)
    assert verify_card is not None

    first_show = json.loads(
        fake_kanban_host.dispatch("kanban_show", {"task_id": verify_card.task_id})
    )
    verification_activation = record_stage_activation(
        service, workflow_id, WorkflowStage.VERIFY
    )
    failed = service.record_verification(
        workflow_id,
        command="pytest -q",
        exit_code=1,
        output="one failed\n",
    )
    failure = failed.verification_evidence[-1]
    comment = (
        f"workflow_id={workflow_id} stage=verify revision={failed.plan_revision} "
        f"output={failure.output_reference}; rerun after operator remediation"
    )
    fake_kanban_host.dispatch(
        "kanban_comment", {"task_id": verify_card.task_id, "body": comment}
    )
    fake_kanban_host.dispatch(
        "kanban_block",
        {
            "task_id": verify_card.task_id,
            "kind": "needs_input",
            "reason": "verification-failed: pytest -q exited 1",
        },
    )
    assert fake_kanban_host.cards[verify_card.task_id]["status"] == "blocked"

    restarted = service.start(
        board_slug="wingstaff-test",
        target_repository=str(target_repository),
        goal="Make the deliberately failing test pass",
        stage_profiles=STAGE_PROFILES,
        pack_name=service.fixture_pack_name,
        workflow_id=workflow_id,
    )
    restarted_verify = restarted.card_for(WorkflowStage.VERIFY)
    assert restarted_verify is not None
    assert restarted_verify.task_id == verify_card.task_id
    assert restarted.worktree_path == str(worktree)
    assert len(fake_kanban_host.cards) == 7

    fake_kanban_host.dispatch("kanban_unblock", {"task_id": verify_card.task_id})
    retry_show = json.loads(
        fake_kanban_host.dispatch("kanban_show", {"task_id": verify_card.task_id})
    )
    assert retry_show["task"]["id"] == first_show["task"]["id"]
    assert retry_show["task"]["args"]["workspace_path"] == str(worktree)
    assert retry_show["task"]["comments"] == [comment]

    passed = service.record_verification(
        workflow_id,
        command="pytest -q",
        exit_code=0,
        output="one passed\n",
    )
    fake_kanban_host.dispatch(
        "kanban_complete",
        {
            "task_id": verify_card.task_id,
            "summary": "verification passed after unblock",
            "metadata": {
                "schema": "wingstaff.handoff/v1",
                "workflow_id": workflow_id,
                "plan_revision": passed.plan_revision,
                "stage": "verify",
                "pack": passed.pack_name,
                "pack_revision": passed.pack_source_revision,
                "outcome": "completed",
                "artifact_refs": [
                    row.to_dict() for row in passed.verification_evidence
                ],
                "skill_activation_digest": verification_activation.digest,
                "active_skills": activation_handoff(
                    passed, WorkflowStage.VERIFY
                )[1],
                "workspace_path": str(worktree),
                "baseline_commit": passed.baseline_commit,
            },
        },
    )
    assert fake_kanban_host.cards[verify_card.task_id]["status"] == "done"


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
    record_stage_activation(service, workflow_id, WorkflowStage.IMPLEMENT)

    with pytest.raises(ExecutionError, match="no working-tree diff"):
        service.capture_implementation(workflow_id)


def test_verification_retries_keep_immutable_output_artifacts(
    service: FixtureWorkflowService,
    target_repository: Path,
) -> None:
    workflow_id, plan_digest = prepare_planned_workflow(
        service, target_repository, "workflow-verification-retry"
    )
    service.approve(workflow_id, plan_digest)
    implementing = service.prepare_implementation(workflow_id)
    assert implementing.worktree_path is not None
    worktree = Path(implementing.worktree_path)
    (worktree / "calculator.py").write_text(
        "def answer():\n    return 2\n", encoding="utf-8"
    )
    record_stage_activation(service, workflow_id, WorkflowStage.IMPLEMENT)
    service.capture_implementation(workflow_id)

    record_stage_activation(service, workflow_id, WorkflowStage.VERIFY)
    failed = service.record_verification(
        workflow_id,
        command="pytest -q",
        exit_code=1,
        output="one failed\n",
    )
    first = failed.verification_evidence[-1]
    first_path = Path(first.output_reference)
    assert first_path.read_text(encoding="utf-8") == "one failed\n"

    repeated = service.record_verification(
        workflow_id,
        command="pytest -q",
        exit_code=1,
        output="one failed\n",
    )
    assert repeated.verification_evidence == failed.verification_evidence

    passed = service.record_verification(
        workflow_id,
        command="pytest -q",
        exit_code=0,
        output="one passed\n",
    )
    second = passed.verification_evidence[-1]
    assert second.output_reference != first.output_reference
    assert first_path.read_text(encoding="utf-8") == "one failed\n"
    assert Path(second.output_reference).read_text(encoding="utf-8") == "one passed\n"


def test_activation_artifact_creation_is_canonical_and_exclusive(tmp_path: Path) -> None:
    manifest = ActivationManifest(
        schema="wingstaff.skill-activation/v1",
        workflow_id="workflow-activation",
        stage=WorkflowStage.DEFINE,
        plan_revision=0,
        pack="test-pack",
        pack_source_revision="a" * 40,
        sequence=1,
        supersedes_digest=None,
        decisions=(
            ActivationDecision(
                name="test-skill",
                skill_digest="b" * 64,
                activation_mode=SkillActivationMode.REQUIRED,
                category=ActivationCategory.APPLICABLE,
                rank=1,
                matched_criteria=("The pack requires this skill.",),
                evidence=("The stage declares this skill.",),
                rationale="Apply the required skill.",
                condition=None,
            ),
        ),
    )
    workspace = ExecutionWorkspace(tmp_path / "data")

    with pytest.raises(ExecutionError, match="does not match"):
        workspace.write_activation_manifest("different-workflow", manifest)
    stored = workspace.write_activation_manifest("workflow-activation", manifest)

    assert Path(stored.path).name == "skill-activation-define-r0-p0-1.json"
    assert Path(stored.path).read_bytes() == manifest.canonical_bytes()
    with pytest.raises(ExecutionError, match="already exists"):
        workspace.write_activation_manifest("workflow-activation", manifest)
    assert Path(stored.path).read_bytes() == manifest.canonical_bytes()


def test_constraint_artifact_creation_is_exclusive_and_verified(tmp_path: Path) -> None:
    from wingstaff.constraints import parse_workflow_constraints

    constraints = parse_workflow_constraints(
        "schema: wingstaff.workflow-constraints/v1\nglobal: [Never commit.]\n"
    )
    artifact = WorkflowConstraintsArtifact(
        "wingstaff.workflow-constraints-artifact/v1",
        "workflow-constraints",
        WorkflowConstraintsIdentity(1, 1, constraints.digest),
        constraints.canonical_bytes().decode(),
    )
    workspace = ExecutionWorkspace(tmp_path / "data")
    stored = workspace.write_constraints_artifact("workflow-constraints", artifact)

    assert stored.digest == constraints.digest
    assert workspace.read_constraints_artifact("workflow-constraints", stored.path) == artifact
    with pytest.raises(ExecutionError, match="already exists"):
        workspace.write_constraints_artifact("workflow-constraints", artifact)
