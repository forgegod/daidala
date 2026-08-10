from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from daidala.errors import PolicyViolationError
from daidala.execution import ExecutionError, ExecutionWorkspace
from daidala.kanban import KanbanError, KanbanGraphAdapter
from daidala.packs import SkillActivationMode, load_pack
from daidala.plan_admission import admit_plan_source
from daidala.recommendations import KanbanSnapshot, derive_recommendations
from daidala.service import ServiceError, WorkflowService
from daidala.skills import (
    content_registry_from_digests,
    inventory_from_names,
    required_skills,
)
from daidala.state import (
    ActivationCategory,
    ActivationDecision,
    ActivationManifest,
    ActivationManifestReference,
    WorkflowConstraintsArtifact,
    WorkflowConstraintsIdentity,
    WorkflowStage,
)
from daidala.store import WorkflowStore

NOW = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)
STAGE_PROFILES = {
    "define": "architect",
    "plan": "architect",
    "implement": "engineer",
    "verify": "engineer",
    "review": "reviewer",
    "deliver": "engineer",
}
PLAN_SUMMARY = {
    "headline": "Plan the fixture implementation.",
    "changes": ["Update calculator behavior."],
    "affected_areas": ["calculator.py"],
    "risks": [],
    "verification": ["Run pytest."],
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

    def submit_review(self, workflow_id: str, **kwargs):
        return super().submit_review(
            workflow_id,
            **self._current_context(workflow_id, WorkflowStage.REVIEW),
            **kwargs,
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
            "user.name=Daidala Tests",
            "-c",
            "user.email=daidala@example.invalid",
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
        board_slug="daidala-test",
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
        approval_summary=PLAN_SUMMARY,
    )
    plan = state.artifact_for(WorkflowStage.PLAN)
    assert plan is not None
    return state.workflow_id, plan.digest


def complete_fixture_stage(
    service: FixtureWorkflowService,
    fake_kanban_host,
    workflow_id: str,
    stage: WorkflowStage,
    artifact_digest: str,
) -> None:
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
                "schema": "daidala.handoff/v1",
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


def prepare_reviewed_workflow(
    service: FixtureWorkflowService,
    target: Path,
    fake_kanban_host,
    workflow_id: str,
) -> tuple[str, str]:
    workflow_id, plan_digest = prepare_planned_workflow(service, target, workflow_id)
    planned = service.status(workflow_id)
    definition = planned.artifact_for(WorkflowStage.DEFINE)
    plan = planned.artifact_for(WorkflowStage.PLAN)
    assert definition is not None and plan is not None
    complete_fixture_stage(
        service, fake_kanban_host, workflow_id, WorkflowStage.DEFINE, definition.digest
    )
    complete_fixture_stage(
        service, fake_kanban_host, workflow_id, WorkflowStage.PLAN, plan.digest
    )
    implementing = service.approve(workflow_id, plan_digest)
    assert implementing.worktree_path is not None
    worktree = Path(implementing.worktree_path)
    (worktree / "calculator.py").write_text(
        "def answer():\n    return 2\n", encoding="utf-8"
    )
    record_stage_activation(service, workflow_id, WorkflowStage.IMPLEMENT)
    implemented = service.capture_implementation(workflow_id)
    implementation = implemented.artifact_for(WorkflowStage.IMPLEMENT)
    assert implementation is not None
    complete_fixture_stage(
        service,
        fake_kanban_host,
        workflow_id,
        WorkflowStage.IMPLEMENT,
        implementation.digest,
    )
    record_stage_activation(service, workflow_id, WorkflowStage.VERIFY)
    verified = service.record_verification(
        workflow_id,
        command="python -m pytest -q",
        exit_code=0,
        output="1 passed\n",
    )
    evidence = verified.verification_evidence[-1]
    complete_fixture_stage(
        service,
        fake_kanban_host,
        workflow_id,
        WorkflowStage.VERIFY,
        evidence.output_digest,
    )
    record_stage_activation(service, workflow_id, WorkflowStage.REVIEW)
    reviewed = service.submit_review(
        workflow_id,
        outcome="changes_requested",
        summary={
            "headline": "The behavior works but the plan omitted a boundary case.",
            "changes": ["Update calculator behavior."],
            "affected_areas": ["calculator.py"],
            "risks": ["The boundary case is not represented in the plan."],
            "verification": ["The current focused test passes."],
        },
        findings=[
            {
                "id": "plan-boundary-gap",
                "severity": "high",
                "title": "The plan omits the boundary case.",
                "rationale": "Revise the plan to cover the boundary case.",
                "blocking": True,
                "evidence_digests": [implementation.digest, evidence.output_digest],
            }
        ],
    )
    assert reviewed.review is not None
    return workflow_id, reviewed.review.digest


def run_fixture_tests(worktree: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=worktree,
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )


def artifact_relative_path(service: WorkflowService, workflow_id: str, path: str) -> str:
    root = service.store.data_root / "workflows" / workflow_id
    return Path(path).relative_to(root).as_posix()


def test_imported_plan_preview_and_apply_skip_authoring_cards(
    service: FixtureWorkflowService,
    target_repository: Path,
    fake_kanban_host,
) -> None:
    plan_path = target_repository / "docs" / "plans" / "P0200-imported.md"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text(
        "\n".join(
            (
                "# Imported fixture",
                "",
                "**Plan ID:** imported-fixture",
                "",
                "**Execution slot:** P0200",
                "",
                "**Created:** 2026-08-10",
                "",
                "**Depends on:** none",
                "",
                "**Status:** pending",
                "",
                "## Phase table",
                "",
                "| # | Phase | Status | Verification gate |",
                "|---|---|---|---|",
                "| 0 | Fix calculator | pending | `python -m pytest -q` exits 0 |",
                "",
                "## Phase 0 — Fix calculator",
                "",
                "Verification gate: `python -m pytest -q` exits 0",
                "",
            )
        ),
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(target_repository), "add", "docs/plans"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(target_repository),
            "-c",
            "user.name=Daidala Tests",
            "-c",
            "user.email=daidala@example.invalid",
            "commit",
            "-qm",
            "add imported plan",
        ],
        check=True,
    )
    revision = subprocess.run(
        ["git", "-C", str(target_repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    packet = admit_plan_source(
        repository=target_repository,
        plan_path="docs/plans/P0200-imported.md",
        source_revision=revision,
        baseline_commit=revision,
        phase_number=0,
    )

    preview = service.preview_start_from_plan(
        packet=packet,
        board_slug="daidala-test",
        stage_profiles=STAGE_PROFILES,
        pack_name=service.fixture_pack_name,
        workflow_id="workflow-imported",
    )

    assert service.store.list_all() == ()
    assert not fake_kanban_host.cards
    with pytest.raises(ServiceError, match="stale"):
        service.preview_start_from_plan(
            packet=replace(packet, phase_title="Stale phase title"),
            board_slug="daidala-test",
            stage_profiles=STAGE_PROFILES,
            pack_name=service.fixture_pack_name,
            workflow_id="workflow-stale",
        )
    assert service.store.list_all() == ()
    with pytest.raises(ServiceError, match="changed after preview"):
        service.start_from_plan(
            packet=packet,
            board_slug="daidala-test",
            stage_profiles=STAGE_PROFILES,
            pack_name=service.fixture_pack_name,
            workflow_id="workflow-imported",
            expected_preview_digest="0" * 64,
        )

    started = service.start_from_plan(
        packet=packet,
        board_slug="daidala-test",
        stage_profiles=STAGE_PROFILES,
        pack_name=service.fixture_pack_name,
        workflow_id="workflow-imported",
        expected_preview_digest=preview.digest,
    )

    plan = started.artifact_for(WorkflowStage.PLAN)
    assert plan is not None
    assert started.plan_source_packet == packet
    assert started.card_for(WorkflowStage.DEFINE) is None
    assert started.card_for(WorkflowStage.PLAN) is None
    assert Path(plan.path).read_bytes() == plan_path.read_bytes()
    assert not fake_kanban_host.cards
    restarted_preview = service.preview_start_from_plan(
        packet=packet,
        board_slug="daidala-test",
        stage_profiles=STAGE_PROFILES,
        pack_name=service.fixture_pack_name,
        workflow_id="workflow-imported",
    )
    assert service.start_from_plan(
        packet=packet,
        board_slug="daidala-test",
        stage_profiles=STAGE_PROFILES,
        pack_name=service.fixture_pack_name,
        workflow_id="workflow-imported",
        expected_preview_digest=restarted_preview.digest,
    ) == started
    with pytest.raises(PolicyViolationError, match="plan source packet"):
        service.approve(started.workflow_id, plan.digest)

    approved = service.approve(
        started.workflow_id,
        plan.digest,
        plan_source_packet_digest=packet.digest,
    )

    implement = approved.card_for(WorkflowStage.IMPLEMENT)
    assert implement is not None
    assert approved.card_for(WorkflowStage.VERIFY) is not None
    assert approved.card_for(WorkflowStage.REVIEW) is not None
    assert fake_kanban_host.cards[implement.task_id]["args"]["parents"] == []
    with pytest.raises(ServiceError, match="cannot be replaced"):
        service.replace_plan(
            started.workflow_id,
            path=plan.path,
            digest=plan.digest,
            approval_summary=PLAN_SUMMARY,
        )


def test_thin_workflow_delivers_verified_uncommitted_diff(
    service: FixtureWorkflowService,
    target_repository: Path,
    fake_kanban_host,
    monkeypatch: pytest.MonkeyPatch,
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
                    "schema": "daidala.handoff/v1",
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
    assert artifact_relative_path(service, workflow_id, definition.path) == (
        "artifacts/policy-0000/define.md"
    )
    assert artifact_relative_path(service, workflow_id, plan.path) == (
        "artifacts/policy-0000/plan-0000/plan.md"
    )
    assert planned.card_for(WorkflowStage.APPROVAL) is None
    assert len(fake_kanban_host.cards) == 2
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
    assert artifact_relative_path(service, workflow_id, implementation.path) == (
        "artifacts/policy-0000/plan-0000/implementation.diff"
    )
    assert implementation.path.endswith("/implementation.diff")
    assert Path(implementation.path).with_name("implementation-paths.json").is_file()
    artifact_root = service.store.data_root / "workflows" / workflow_id / "artifacts"
    (artifact_root / "implementation-paths.json").write_text(
        '{"changed_paths": ["stale-root.py"]}\n',
        encoding="utf-8",
    )
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
    assert artifact_relative_path(
        service,
        workflow_id,
        reviewing.verification_evidence[-1].output_reference,
    ).startswith("artifacts/policy-0000/plan-0000/verification-")
    complete_stage(
        WorkflowStage.VERIFY,
        reviewing.verification_evidence[-1].output_digest,
    )

    record_stage_activation(service, workflow_id, WorkflowStage.REVIEW)
    review_request = {
        "outcome": "accepted",
        "summary": {
            "headline": "The diff is scoped and pytest passes.",
            "changes": ["Update calculator behavior."],
            "affected_areas": ["calculator.py", "notes.txt"],
            "risks": [],
            "verification": ["pytest passes."],
        },
        "findings": [],
    }
    review_completion_failed = False

    def fail_first_review_completion(name: str, args: dict[str, object]) -> str:
        nonlocal review_completion_failed
        if name == "kanban_complete" and not review_completion_failed:
            review_completion_failed = True
            raise KanbanError("transient review completion failure")
        return fake_kanban_host.dispatch(name, args)

    monkeypatch.setattr(
        service,
        "_kanban",
        KanbanGraphAdapter(fail_first_review_completion),
    )
    with pytest.raises(KanbanError, match="transient review completion failure"):
        service.submit_review(workflow_id, **review_request)
    persisted_after_review_failure = service.status(workflow_id)
    assert persisted_after_review_failure.review is not None
    assert persisted_after_review_failure.card_for(WorkflowStage.DELIVER) is None
    monkeypatch.setattr(
        service,
        "_kanban",
        KanbanGraphAdapter(fake_kanban_host.dispatch),
    )
    reviewed = service.submit_review(workflow_id, **review_request)
    review = reviewed.review
    assert review is not None
    assert review.summary_digest == review.summary.digest_for(implementation.digest)
    assert service.current_implementation_changed_paths(workflow_id) == (
        "calculator.py",
        "notes.txt",
    )
    assert reviewed.card_for(WorkflowStage.DELIVER) is None
    replayed_review = service.submit_review(workflow_id, **review_request)
    assert replayed_review.review == review
    complete_stage(WorkflowStage.REVIEW, review.digest)
    with pytest.raises(ServiceError, match="exact current review digest"):
        service.decide_review(
            workflow_id,
            review_digest="f" * 64,
            action="accept_delivery",
            actor="fixture operator",
            rationale="The exact review evidence is accepted for delivery.",
        )
    delivery_creation_failed = False

    def fail_first_delivery_creation(name: str, args: dict[str, object]) -> str:
        nonlocal delivery_creation_failed
        if (
            name == "kanban_create"
            and str(args.get("title", "")).endswith(": deliver")
            and not delivery_creation_failed
        ):
            delivery_creation_failed = True
            raise KanbanError("transient delivery creation failure")
        return fake_kanban_host.dispatch(name, args)

    monkeypatch.setattr(
        service,
        "_kanban",
        KanbanGraphAdapter(fail_first_delivery_creation),
    )
    with pytest.raises(KanbanError, match="transient delivery creation failure"):
        service.decide_review(
            workflow_id,
            review_digest=review.digest,
            action="accept_delivery",
            actor="fixture operator",
            rationale="The exact review evidence is accepted for delivery.",
        )
    persisted_after_delivery_failure = service.status(workflow_id)
    assert persisted_after_delivery_failure.review_disposition is not None
    assert persisted_after_delivery_failure.card_for(WorkflowStage.DELIVER) is None
    monkeypatch.setattr(
        service,
        "_kanban",
        KanbanGraphAdapter(fake_kanban_host.dispatch),
    )
    reviewed = service.decide_review(
        workflow_id,
        review_digest=review.digest,
        action="accept_delivery",
        actor="fixture operator",
        rationale="The exact review evidence is accepted for delivery.",
    )
    assert reviewed.review_disposition is not None
    deliver_card = reviewed.card_for(WorkflowStage.DELIVER)
    assert deliver_card is not None
    replayed_disposition = service.decide_review(
        workflow_id,
        review_digest=review.digest,
        action="accept_delivery",
        actor="fixture operator",
        rationale="The exact review evidence is accepted for delivery.",
    )
    assert replayed_disposition.review_disposition == reviewed.review_disposition
    assert replayed_disposition.card_for(WorkflowStage.DELIVER) == deliver_card
    snapshots = tuple(
        KanbanSnapshot(
            card.stage,
            card.task_id,
            str(fake_kanban_host.cards[card.task_id]["status"]),
            str(fake_kanban_host.cards[card.task_id]["assignee"]),
        )
        for card in replayed_disposition.card_references
    )
    delivery_recommendation = next(
        row
        for row in derive_recommendations(replayed_disposition, snapshots)
        if row.action_kind == "deliver_reviewed_diff"
    )
    assert delivery_recommendation.evidence_ref == review.digest
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
    assert artifact_relative_path(service, workflow_id, delivery.path) == (
        "artifacts/policy-0000/plan-0000/delivery.json"
    )
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

    assert len(fake_kanban_host.cards) == 6
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
            "daidala.handoff/v1"
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


def test_review_revision_preview_apply_retries_and_preserves_rejected_evidence(
    service: FixtureWorkflowService,
    target_repository: Path,
    fake_kanban_host,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow_id, review_digest = prepare_reviewed_workflow(
        service,
        target_repository,
        fake_kanban_host,
        "workflow-plan-revision",
    )
    before = service.status(workflow_id)
    old_plan = before.artifact_for(WorkflowStage.PLAN)
    old_implementation = before.artifact_for(WorkflowStage.IMPLEMENT)
    assert old_plan is not None and old_implementation is not None
    old_verification = before.verification_evidence
    old_worktree = before.worktree_path
    rationale = "Cover the blocking boundary case, then rerun the exact verification."
    preview = service.preview_review_decision(
        workflow_id,
        action="request_revision",
        actor="fixture operator",
        rationale=rationale,
    )

    assert service.status(workflow_id) == before
    assert preview.review_digest == review_digest
    assert preview.next_plan_revision == 1
    assert preview.next_assignee == "architect"
    assert preview.worktree_to_release == old_worktree
    assert preview.revision_request_digest is not None
    assert preview.successor_packet_digest is not None
    assert preview.successor_packet is not None
    assert preview.successor_packet["source_review"]["digest"] == review_digest
    assert preview.successor_packet["source_disposition_preview"]["digest"]
    current_implementation = service.status(workflow_id).artifact_for(
        WorkflowStage.IMPLEMENT
    )
    assert current_implementation is not None
    assert preview.successor_packet["source_implementation"]["digest"] == (
        current_implementation.digest
    )
    assert preview.successor_packet["source_verification"]
    with pytest.raises(ServiceError, match="changed after preview"):
        service.apply_review_decision(
            workflow_id,
            action="request_revision",
            actor="fixture operator",
            rationale=rationale,
            expected_review_digest=review_digest,
            expected_preview_digest="f" * 64,
            confirm=True,
        )
    assert service.status(workflow_id) == before

    real_write_artifact = service._workspace.write_artifact
    artifact_write_failed = False

    def fail_first_artifact_write(
        workflow_id: str,
        relative_path: str,
        content: str,
    ):
        nonlocal artifact_write_failed
        if not artifact_write_failed:
            artifact_write_failed = True
            raise ExecutionError("transient revision artifact failure")
        return real_write_artifact(workflow_id, relative_path, content)

    monkeypatch.setattr(service._workspace, "write_artifact", fail_first_artifact_write)
    with pytest.raises(ExecutionError, match="transient revision artifact failure"):
        service.apply_review_decision(
            workflow_id,
            action="request_revision",
            actor="fixture operator",
            rationale=rationale,
            expected_review_digest=review_digest,
            expected_preview_digest=preview.digest,
            confirm=True,
        )
    after_artifact_failure = service.status(workflow_id)
    assert after_artifact_failure.pending_revision_request is None
    assert after_artifact_failure.review_disposition is not None
    assert (
        service.preview_review_decision(
            workflow_id,
            action="request_revision",
            actor="fixture operator",
            rationale=rationale,
        ).digest
        == preview.digest
    )
    monkeypatch.setattr(service._workspace, "write_artifact", real_write_artifact)

    archive_failed = False

    def fail_first_archive(name: str, args: dict[str, object]) -> str:
        nonlocal archive_failed
        if (
            name == "terminal"
            and " archive " in str(args.get("command", ""))
            and not archive_failed
        ):
            archive_failed = True
            raise KanbanError("transient archive failure")
        return fake_kanban_host.dispatch(name, args)

    monkeypatch.setattr(service, "_kanban", KanbanGraphAdapter(fail_first_archive))
    with pytest.raises(KanbanError, match="transient archive failure"):
        service.apply_review_decision(
            workflow_id,
            action="request_revision",
            actor="fixture operator",
            rationale=rationale,
            expected_review_digest=review_digest,
            expected_preview_digest=preview.digest,
            confirm=True,
        )
    after_archive_failure = service.status(workflow_id)
    request = after_archive_failure.pending_revision_request
    assert request is not None
    assert request.cards_archived_at is None
    assert after_archive_failure.plan_revision == 0
    assert after_archive_failure.review_disposition is not None
    partial_packet = service.review_packet(workflow_id)["pending_revision_request"]
    assert isinstance(partial_packet, dict)
    assert "request_path" not in partial_packet
    assert "successor_packet_path" not in partial_packet
    comment_count_after_archive_failure = sum(
        len(rows) for rows in fake_kanban_host.comments.values()
    )

    monkeypatch.setattr(
        service,
        "_kanban",
        KanbanGraphAdapter(fake_kanban_host.dispatch),
    )
    real_remove = service._workspace.remove_worktree
    cleanup_failed = False

    def fail_first_cleanup(target_repository: str, worktree_path: str) -> None:
        nonlocal cleanup_failed
        if not cleanup_failed:
            cleanup_failed = True
            raise ExecutionError("transient worktree cleanup failure")
        real_remove(target_repository, worktree_path)

    monkeypatch.setattr(service._workspace, "remove_worktree", fail_first_cleanup)
    with pytest.raises(ExecutionError, match="transient worktree cleanup failure"):
        service.apply_review_decision(
            workflow_id,
            action="request_revision",
            actor="fixture operator",
            rationale=rationale,
            expected_review_digest=review_digest,
            expected_preview_digest=preview.digest,
            confirm=True,
        )
    after_cleanup_failure = service.status(workflow_id)
    request = after_cleanup_failure.pending_revision_request
    assert request is not None
    assert request.cards_archived_at is not None
    assert request.worktree_released_at is None
    comment_count = sum(len(rows) for rows in fake_kanban_host.comments.values())
    assert comment_count == comment_count_after_archive_failure

    monkeypatch.setattr(service._workspace, "remove_worktree", real_remove)
    plan_create_failed = False

    def fail_first_plan_create(name: str, args: dict[str, object]) -> str:
        nonlocal plan_create_failed
        if (
            name == "kanban_create"
            and str(args.get("title", "")).endswith(": plan")
            and not plan_create_failed
        ):
            plan_create_failed = True
            raise KanbanError("transient successor Plan card failure")
        return fake_kanban_host.dispatch(name, args)

    monkeypatch.setattr(service, "_kanban", KanbanGraphAdapter(fail_first_plan_create))
    with pytest.raises(KanbanError, match="transient successor Plan card failure"):
        service.apply_review_decision(
            workflow_id,
            action="request_revision",
            actor="fixture operator",
            rationale=rationale,
            expected_review_digest=review_digest,
            expected_preview_digest=preview.digest,
            confirm=True,
        )
    after_plan_card_failure = service.status(workflow_id)
    assert after_plan_card_failure.plan_revision == 1
    assert after_plan_card_failure.pending_revision_request is not None
    assert after_plan_card_failure.card_for(WorkflowStage.PLAN) is None

    monkeypatch.setattr(
        service,
        "_kanban",
        KanbanGraphAdapter(fake_kanban_host.dispatch),
    )
    result = service.apply_review_decision(
        workflow_id,
        action="request_revision",
        actor="fixture operator",
        rationale=rationale,
        expected_review_digest=review_digest,
        expected_preview_digest=preview.digest,
        confirm=True,
    )
    revised = service.status(workflow_id)
    plan_card = revised.card_for(WorkflowStage.PLAN)
    assert plan_card is not None
    assert result["replayed"] is True
    assert result["workflow"] == {
        "workflow_id": workflow_id,
        "plan_revision": 1,
        "plan_card_id": plan_card.task_id,
    }
    assert revised.plan_revision == 1
    assert revised.current_plan_digest is None
    assert revised.approval is None
    assert revised.review is None
    assert revised.review_disposition is None
    assert revised.verification_evidence == ()
    assert revised.review_history[-1].digest == review_digest
    assert revised.review_disposition_history[-1].action.value == "request_revision"
    assert revised.verification_history[-1] == old_verification[-1]
    assert old_plan in revised.artifacts
    assert old_implementation in revised.artifacts
    assert revised.worktree_owned is False
    assert old_worktree is not None and not Path(old_worktree).exists()
    assert sum(len(rows) for rows in fake_kanban_host.comments.values()) == comment_count
    request = revised.pending_revision_request
    assert request is not None
    review_packet = service.review_packet(workflow_id)
    pending_packet = review_packet["pending_revision_request"]
    assert isinstance(pending_packet, dict)
    assert "request_path" not in pending_packet
    assert "successor_packet_path" not in pending_packet
    assert Path(request.request_path).is_file()
    assert Path(request.successor_packet_path).is_file()
    assert hashlib.sha256(Path(request.request_path).read_bytes()).hexdigest() == (
        preview.revision_request_digest
    )
    assert hashlib.sha256(Path(request.successor_packet_path).read_bytes()).hexdigest() == (
        preview.successor_packet_digest
    )
    assert plan_card.plan_revision == 1
    assert fake_kanban_host.cards[plan_card.task_id]["args"]["parents"] == [
        request.source_review_card_id
    ]
    assert revised.card_for(WorkflowStage.IMPLEMENT) is None
    with pytest.raises(PolicyViolationError, match="current plan"):
        service.approve(workflow_id, plan_digest=old_plan.digest)

    record_stage_activation(service, workflow_id, WorkflowStage.PLAN)
    planned = service.submit_artifact(
        workflow_id,
        stage=WorkflowStage.PLAN,
        content=(
            "# Revised plan\n\nCover the blocking boundary case and rerun verification.\n"
        ),
        approval_summary={
            **PLAN_SUMMARY,
            "headline": "Cover the blocking boundary case before implementation.",
        },
    )
    new_plan = planned.artifact_for(WorkflowStage.PLAN)
    assert new_plan is not None and new_plan.digest != old_plan.digest
    assert planned.pending_revision_request is None
    assert planned.revision_requests[-1].resolved_at is not None
    approved = service.approve(workflow_id, plan_digest=new_plan.digest)
    assert approved.approval is not None
    assert approved.worktree_owned is True
    implementation_card = approved.card_for(WorkflowStage.IMPLEMENT)
    assert implementation_card is not None
    assert implementation_card.plan_revision == 1


def test_blocked_activation_denies_stage_evidence_without_completion_handoff(
    service: FixtureWorkflowService,
    target_repository: Path,
    fake_kanban_host,
) -> None:
    ledger = service.start(
        board_slug="daidala-test",
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
        board_slug="daidala-test",
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
    record_stage_activation(service, workflow_id, WorkflowStage.IMPLEMENT)
    captured = service.capture_implementation(workflow_id)
    implementation = captured.artifact_for(WorkflowStage.IMPLEMENT)
    assert implementation is not None
    implementation_path = Path(implementation.path)
    implementation_hash = hashlib.sha256(implementation_path.read_bytes()).hexdigest()

    cancelled = service.cancel(workflow_id, "Operator requested rollback")

    assert cancelled.worktree_path is None
    assert cancelled.worktree_owned is False
    assert not worktree.exists()
    assert "return 1" in (target_repository / "calculator.py").read_text(encoding="utf-8")
    assert cancelled.artifact_for(WorkflowStage.IMPLEMENT) == implementation
    assert hashlib.sha256(implementation_path.read_bytes()).hexdigest() == implementation_hash

    restarted = service.start(
        board_slug="daidala-test",
        target_repository=str(target_repository),
        goal="Make the deliberately failing test pass",
        stage_profiles=STAGE_PROFILES,
        pack_name=service.fixture_pack_name,
        workflow_id=workflow_id,
    )
    assert restarted.artifact_for(WorkflowStage.IMPLEMENT) == implementation
    assert hashlib.sha256(implementation_path.read_bytes()).hexdigest() == implementation_hash


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
    old_artifact_bytes = {
        artifact.path: Path(artifact.path).read_bytes() for artifact in old_artifacts
    }
    old_artifact_hashes = {
        path: hashlib.sha256(content).hexdigest()
        for path, content in old_artifact_bytes.items()
    }
    assert approved.worktree_path is not None
    old_worktree = Path(approved.worktree_path)

    content = (
        "schema: daidala.workflow-constraints/v1\n"
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
        approval_summary=PLAN_SUMMARY,
    )
    plan = planned.artifact_for(WorkflowStage.PLAN)
    definition = planned.artifact_for(WorkflowStage.DEFINE)
    assert definition is not None and plan is not None
    assert artifact_relative_path(service, workflow_id, definition.path) == (
        "artifacts/policy-0001/define.md"
    )
    assert artifact_relative_path(service, workflow_id, plan.path) == (
        "artifacts/policy-0001/plan-0000/plan.md"
    )
    assert all(
        Path(path).read_bytes() == content
        for path, content in old_artifact_bytes.items()
    )
    assert {
        path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
        for path in old_artifact_hashes
    } == old_artifact_hashes
    artifact_root = service.store.data_root / "workflows" / workflow_id / "artifacts"
    assert not (artifact_root / "define.md").exists()
    assert not (artifact_root / "plan.md").exists()
    assert not any(path.is_symlink() for path in artifact_root.rglob("*"))
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
    content = "schema: daidala.workflow-constraints/v1\nglobal: [Never push.]\n"
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
    assert blocked.card_for(WorkflowStage.DELIVER) is None


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
        board_slug="daidala-test",
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
    assert len(fake_kanban_host.cards) == 5

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
                "schema": "daidala.handoff/v1",
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
            board_slug="daidala-test",
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
        schema="daidala.skill-activation/v1",
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
    from daidala.constraints import parse_workflow_constraints

    constraints = parse_workflow_constraints(
        "schema: daidala.workflow-constraints/v1\nglobal: [Never commit.]\n"
    )
    artifact = WorkflowConstraintsArtifact(
        "daidala.workflow-constraints-artifact/v1",
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


def test_revision_artifact_paths_are_validated_immutable_and_replay_safe(
    tmp_path: Path,
) -> None:
    workspace = ExecutionWorkspace(tmp_path / "data")
    relative = workspace.stage_artifact_relative_path(
        stage=WorkflowStage.PLAN,
        policy_revision=2,
        plan_revision=3,
        filename="plan.md",
    )

    assert relative == "policy-0002/plan-0003/plan.md"
    with pytest.raises(ExecutionError, match="not executable"):
        workspace.stage_artifact_relative_path(
            stage=WorkflowStage.APPROVAL,
            policy_revision=2,
            plan_revision=3,
            filename="approval.md",
        )
    with pytest.raises(ExecutionError, match="non-negative"):
        workspace.stage_artifact_relative_path(
            stage=WorkflowStage.PLAN,
            policy_revision=-1,
            plan_revision=3,
            filename="plan.md",
        )
    with pytest.raises(ExecutionError, match="one relative path segment"):
        workspace.stage_artifact_relative_path(
            stage=WorkflowStage.PLAN,
            policy_revision=2,
            plan_revision=3,
            filename="nested/plan.md",
        )
    first = workspace.write_artifact("workflow-artifacts", relative, "# Plan\n")
    replayed = workspace.write_artifact("workflow-artifacts", relative, "# Plan\n")

    assert replayed == first
    assert Path(first.path).read_text(encoding="utf-8") == "# Plan\n"
    assert not tuple(Path(first.path).parent.glob(".daidala-artifact-*"))
    with pytest.raises(ExecutionError, match="content conflicts"):
        workspace.write_artifact("workflow-artifacts", relative, "# Changed\n")
    assert Path(first.path).read_text(encoding="utf-8") == "# Plan\n"

    json_relative = workspace.stage_artifact_relative_path(
        stage=WorkflowStage.DELIVER,
        policy_revision=2,
        plan_revision=3,
        filename="delivery.json",
    )
    json_first = workspace.write_json_artifact(
        "workflow-artifacts", json_relative, {"committed": False}
    )
    assert workspace.read_json_artifact("workflow-artifacts", json_first.path) == {
        "committed": False
    }
    with pytest.raises(ExecutionError, match="absolute path"):
        workspace.read_json_artifact("workflow-artifacts", json_relative)
    with pytest.raises(ExecutionError, match="outside"):
        workspace.read_json_artifact("workflow-artifacts", str(tmp_path / "outside.json"))
    assert workspace.write_json_artifact(
        "workflow-artifacts", json_relative, {"committed": False}
    ) == json_first
    with pytest.raises(ExecutionError, match="content conflicts"):
        workspace.write_json_artifact(
            "workflow-artifacts", json_relative, {"committed": True}
        )

    linked = Path(workspace.artifact_path("workflow-artifacts", "linked.md"))
    linked.parent.mkdir(parents=True, exist_ok=True)
    linked.symlink_to(first.path)
    with pytest.raises(ExecutionError, match="symlink"):
        workspace.write_artifact("workflow-artifacts", "linked.md", "# Plan\n")

    outside = tmp_path / "outside"
    outside.mkdir()
    workflow_link = tmp_path / "data" / "workflows" / "workflow-symlink"
    workflow_link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ExecutionError, match="root contains a symlink"):
        workspace.write_artifact("workflow-symlink", "blocked.md", "blocked")

    for malformed in (
        "",
        "/absolute.md",
        "../escape.md",
        "a/../../escape.md",
        "a" * 513,
    ):
        with pytest.raises(ExecutionError, match="relative path"):
            workspace.write_artifact("workflow-artifacts", malformed, "blocked")
