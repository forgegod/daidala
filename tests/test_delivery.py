from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from daidala.credentials import (
    CredentialBinding,
    CredentialBindings,
    credential_bindings_path,
)
from daidala.delivery import BranchDeliveryService, DeliveryError
from daidala.kanban import KanbanGraphAdapter
from daidala.profile_files import atomic_write_private_text
from daidala.registrations import (
    ControllerRegistration,
    RegistrationLimits,
    registration_path,
)
from daidala.service import ServiceError, WorkflowService
from daidala.skills import (
    content_registry_from_digests,
    inventory_from_names,
    required_skills,
)
from daidala.state import ActivationCategory, WorkflowStage
from daidala.store import WorkflowStore

NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)
WORKFLOW_ID = "delivery-fixture"
PROJECT_ID = "forgegod-delivery-fixture"
REPOSITORY = "forgegod/delivery-fixture"
DELIVERY_TOKEN = "test-delivery-token"
STAGE_PROFILES = {
    "define": "architect",
    "plan": "architect",
    "implement": "engineer",
    "verify": "engineer",
    "review": "reviewer",
    "deliver": "engineer",
}
PLAN_SUMMARY = {
    "headline": "Correct the fixture implementation.",
    "changes": ["Return the expected calculator result."],
    "affected_areas": ["calculator.py"],
    "risks": [],
    "verification": ["Run the focused test."],
}


class TickClock:
    def __init__(self) -> None:
        self.tick = 0

    def __call__(self) -> datetime:
        self.tick += 1
        return NOW + timedelta(minutes=self.tick)


class FixtureWorkflowService(WorkflowService):
    fixture_pack: Any

    def _context(self, workflow_id: str, stage: WorkflowStage) -> dict[str, str]:
        ledger = self.status(workflow_id)
        card = ledger.card_for(stage)
        assert card is not None
        return {"board_slug": ledger.board_slug, "task_id": card.task_id}

    def submit_artifact(self, workflow_id: str, *, stage: WorkflowStage, **kwargs):
        return super().submit_artifact(
            workflow_id,
            stage=stage,
            **self._context(workflow_id, stage),
            **kwargs,
        )

    def capture_implementation(self, workflow_id: str, **kwargs):
        return super().capture_implementation(
            workflow_id,
            **self._context(workflow_id, WorkflowStage.IMPLEMENT),
            **kwargs,
        )

    def record_verification(self, workflow_id: str, **kwargs):
        return super().record_verification(
            workflow_id,
            **self._context(workflow_id, WorkflowStage.VERIFY),
            **kwargs,
        )

    def submit_review(self, workflow_id: str, **kwargs):
        return super().submit_review(
            workflow_id,
            **self._context(workflow_id, WorkflowStage.REVIEW),
            **kwargs,
        )


def _run(command: tuple[str, ...], *, cwd: Path | None = None) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _manifest() -> str:
    source = (Path(__file__).parents[1] / ".daidala" / "project.yaml").read_text(
        encoding="utf-8"
    )
    return (
        source.replace("forgegod-daidala", PROJECT_ID)
        .replace("forgegod/daidala", REPOSITORY)
        .replace("allow_commit: false", "allow_commit: true")
        .replace("allow_push: false", "allow_push: true")
    )


def _activate(service: FixtureWorkflowService, workflow_id: str, stage: WorkflowStage) -> None:
    ledger = service.status(workflow_id)
    card = ledger.card_for(stage)
    assert card is not None
    pack = service.fixture_pack
    selected = next(row for row in pack.stages if row.id == stage.value)
    decisions = []
    rank = 0
    for skill in selected.skills:
        category = (
            ActivationCategory.APPLICABLE
            if skill.activation.value == "required"
            else ActivationCategory.NOT_APPLICABLE
        )
        if category is ActivationCategory.APPLICABLE:
            rank += 1
        decisions.append(
            {
                "name": skill.name,
                "category": category.value,
                "rank": rank if category is ActivationCategory.APPLICABLE else None,
                "matched_criteria": ["Fixture evaluates the pinned delivery-stage skill."],
                "evidence": ["The current workflow card and policy tuple were inspected."],
                "rationale": "Use required guidance and retain a deterministic fixture.",
                "condition": None,
            }
        )
    service.record_skill_activation(
        workflow_id,
        stage=stage,
        supersedes_digest=None,
        decisions=decisions,
        board_slug=ledger.board_slug,
        task_id=card.task_id,
    )


def _complete_stage(
    service: FixtureWorkflowService,
    host,
    workflow_id: str,
    stage: WorkflowStage,
    artifact_digest: str,
) -> None:
    ledger = service.status(workflow_id)
    card = ledger.card_for(stage)
    activation = ledger.activation_for(stage)
    assert card is not None and activation is not None
    host.dispatch(
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
                "skill_activation_digest": activation.digest,
                "active_skills": [],
            },
        },
    )


def _write_delivery_registration(profile_root: Path, target: Path) -> None:
    project_root = profile_root / "projects" / PROJECT_ID
    project_root.mkdir(parents=True)
    registration = ControllerRegistration(
        project_id=PROJECT_ID,
        checkout=str(target),
        controller_profile="controller",
        board="delivery-board",
        repository_canonical=REPOSITORY,
        verified_remote=f"git@github.com:{REPOSITORY}.git",
        intake_credential="github-read",
        findings_credential="github-write",
        maintainers=("forgegod",),
        notification_adapter="hermes-gateway",
        notification_target="attended",
        notification_destination="telegram:delivery",
        evaluator_backend="restricted-container",
        evaluator_network="denied-by-default",
        limits=RegistrationLimits(1, 1, 0, 0, 0, 60),
    )
    bindings = CredentialBindings(
        project_id=PROJECT_ID,
        bindings=(
            CredentialBinding("github-read", "environment", "DAIDALA_GITHUB_READ_TOKEN"),
            CredentialBinding("github-write", "environment", "DAIDALA_GITHUB_WRITE_TOKEN"),
            CredentialBinding(
                "github-repository-delivery",
                "environment",
                "DAIDALA_GITHUB_DELIVERY_TOKEN",
            ),
        ),
    )
    registration_file = registration_path(profile_root, PROJECT_ID)
    atomic_write_private_text(
        registration_file,
        yaml.safe_dump(registration.to_dict(), sort_keys=False),
        label="controller registration",
    )
    atomic_write_private_text(
        credential_bindings_path(registration_file),
        yaml.safe_dump(bindings.to_dict(), sort_keys=False),
        label="credential bindings",
    )


@pytest.fixture
def prepared_delivery(tmp_path: Path, fake_kanban_host, request) -> tuple[
    FixtureWorkflowService, Path, Path, Path, list[tuple[str, ...]]
]:
    target = tmp_path / "target"
    target.mkdir()
    (target / "calculator.py").write_text(
        "def answer():\n    return 1\n", encoding="utf-8"
    )
    (target / ".daidala").mkdir()
    (target / ".daidala" / "project.yaml").write_text(_manifest(), encoding="utf-8")
    _run(("git", "init", "-q", str(target)))
    _run(("git", "-C", str(target), "config", "user.name", "Daidala Tests"))
    _run(("git", "-C", str(target), "config", "user.email", "daidala@example.invalid"))
    _run(("git", "-C", str(target), "add", "."))
    _run(("git", "-C", str(target), "commit", "-qm", "delivery fixture"))
    _run(("git", "-C", str(target), "remote", "add", "origin", f"git@github.com:{REPOSITORY}.git"))

    remote = tmp_path / "remote.git"
    _run(("git", "init", "--bare", "-q", str(remote)))
    profile_root = tmp_path / "profile"
    profile_root.mkdir()
    _write_delivery_registration(profile_root, target.resolve())

    from daidala.packs import load_pack

    pack = load_pack("aidlc")
    skills = required_skills(pack)
    service = FixtureWorkflowService(
        WorkflowStore(tmp_path / "data"),
        clock=TickClock(),
        skill_inventory=inventory_from_names(skill.name for skill in skills),
        skill_content_registry=content_registry_from_digests(
            cast(dict[str, str], {skill.name: skill.content_digest for skill in skills})
        ),
        kanban=KanbanGraphAdapter(fake_kanban_host.dispatch),
    )
    service.fixture_pack = pack
    started = service.start(
        board_slug="delivery-board",
        target_repository=str(target.resolve()),
        goal="Make the calculator answer two",
        stage_profiles=STAGE_PROFILES,
        pack_name=pack.name,
        workflow_id=WORKFLOW_ID,
    )
    _activate(service, started.workflow_id, WorkflowStage.DEFINE)
    defined = service.submit_artifact(
        started.workflow_id,
        stage=WorkflowStage.DEFINE,
        content="# Definition\n",
    )
    definition = defined.artifact_for(WorkflowStage.DEFINE)
    assert definition is not None
    _complete_stage(service, fake_kanban_host, WORKFLOW_ID, WorkflowStage.DEFINE, definition.digest)
    _activate(service, WORKFLOW_ID, WorkflowStage.PLAN)
    planned = service.submit_artifact(
        WORKFLOW_ID,
        stage=WorkflowStage.PLAN,
        content="# Plan\n\nUpdate calculator.py and run the focused test.\n",
        approval_summary=PLAN_SUMMARY,
    )
    plan = planned.artifact_for(WorkflowStage.PLAN)
    assert plan is not None
    _complete_stage(service, fake_kanban_host, WORKFLOW_ID, WorkflowStage.PLAN, plan.digest)
    implementing = service.approve(WORKFLOW_ID, plan.digest)
    assert implementing.worktree_path is not None
    worktree = Path(implementing.worktree_path)
    implementation = "def answer():\n    return 2"
    if not getattr(request, "param", False):
        implementation += "\n"
    (worktree / "calculator.py").write_text(implementation, encoding="utf-8")
    _activate(service, WORKFLOW_ID, WorkflowStage.IMPLEMENT)
    implemented = service.capture_implementation(WORKFLOW_ID)
    implementation = implemented.artifact_for(WorkflowStage.IMPLEMENT)
    assert implementation is not None
    _complete_stage(
        service, fake_kanban_host, WORKFLOW_ID, WorkflowStage.IMPLEMENT, implementation.digest
    )
    _activate(service, WORKFLOW_ID, WorkflowStage.VERIFY)
    verified = service.record_verification(
        WORKFLOW_ID,
        command="python -m pytest -q",
        exit_code=0,
        output="1 passed\n",
    )
    evidence = verified.verification_evidence[-1]
    _complete_stage(
        service,
        fake_kanban_host,
        WORKFLOW_ID,
        WorkflowStage.VERIFY,
        evidence.output_digest,
    )
    _activate(service, WORKFLOW_ID, WorkflowStage.REVIEW)
    reviewed = service.submit_review(
        WORKFLOW_ID,
        outcome="accepted",
        summary=PLAN_SUMMARY,
        findings=[],
    )
    assert reviewed.review is not None
    _complete_stage(
        service,
        fake_kanban_host,
        WORKFLOW_ID,
        WorkflowStage.REVIEW,
        reviewed.review.digest,
    )
    ready = service.decide_review(
        WORKFLOW_ID,
        review_digest=reviewed.review.digest,
        action="accept_delivery",
        actor="fixture-operator",
        rationale="The exact reviewed diff is accepted for branch delivery.",
    )
    assert ready.card_for(WorkflowStage.DELIVER) is not None
    _activate(service, WORKFLOW_ID, WorkflowStage.DELIVER)
    commands: list[tuple[str, ...]] = []
    return service, target.resolve(), remote.resolve(), profile_root.resolve(), commands


def _delivery_runner(
    remote: Path,
    commands: list[tuple[str, ...],],
):
    remote_url = f"https://github.com/{REPOSITORY}.git"

    def run(command: tuple[str, ...], environment: Mapping[str, str]) -> tuple[int, str]:
        commands.append(command)
        translated = tuple(str(remote) if value == remote_url else value for value in command)
        completed = subprocess.run(
            translated,
            check=False,
            capture_output=True,
            text=True,
            env=dict(environment),
        )
        return completed.returncode, completed.stdout + completed.stderr

    return run


def _delivery_service(
    service: FixtureWorkflowService,
    remote: Path,
    profile_root: Path,
    commands: list[tuple[str, ...]],
    *,
    credential: str | None = DELIVERY_TOKEN,
) -> BranchDeliveryService:
    environ = {"HOME": os.environ["HOME"], "PATH": os.environ["PATH"], "LANG": "C.UTF-8"}
    if credential is not None:
        environ["DAIDALA_GITHUB_DELIVERY_TOKEN"] = credential
    return BranchDeliveryService(
        service,
        profile_root=profile_root,
        runner=_delivery_runner(remote, commands),
        environ=environ,
        clock=lambda: NOW,
    )


def test_delivery_commits_and_pushes_only_the_reviewed_branch(
    prepared_delivery, fake_kanban_host
) -> None:
    service, target, remote, profile_root, commands = prepared_delivery
    delivery = _delivery_service(service, remote, profile_root, commands)

    preview = delivery.preview(WORKFLOW_ID)
    rendered_preview = json.dumps(preview.to_dict())
    assert preview.branch == f"daidala/{WORKFLOW_ID}"
    assert preview.credential_available is True
    assert DELIVERY_TOKEN not in rendered_preview
    assert "credential_alias" not in rendered_preview
    assert str(target) not in rendered_preview

    completed = delivery.apply(
        WORKFLOW_ID,
        expected_preview_digest=preview.digest,
        confirm=True,
    )

    authorization = completed.delivery_authorization
    assert authorization is not None and authorization.commit is not None
    assert completed.committed is True
    assert completed.pushed is True
    assert completed.worktree_owned is False
    assert completed.worktree_path is None
    remote_commit = _run(
        ("git", "--git-dir", str(remote), "rev-parse", f"refs/heads/{preview.branch}")
    )
    assert remote_commit == authorization.commit
    assert _run(("git", "-C", str(target), "rev-parse", "HEAD")) == completed.baseline_commit
    delivery_artifact = completed.artifact_for(WorkflowStage.DELIVER)
    assert delivery_artifact is not None
    receipt = json.loads(Path(delivery_artifact.path).read_text(encoding="utf-8"))
    assert receipt["branch"] == preview.branch
    assert receipt["commit"] == authorization.commit
    assert receipt["committed"] is True
    assert receipt["pushed"] is True
    card = completed.card_for(WorkflowStage.DELIVER)
    assert card is not None
    assert fake_kanban_host.cards[card.task_id]["status"] == "done"
    assert fake_kanban_host.cards[card.task_id]["completion_metadata"] == {
        "schema": "daidala.delivery/v1",
        "branch": preview.branch,
        "commit": authorization.commit,
    }
    assert all(DELIVERY_TOKEN not in " ".join(command) for command in commands)
    assert all(
        DELIVERY_TOKEN not in path.read_text(encoding="utf-8", errors="ignore")
        for path in profile_root.rglob("*")
        if path.is_file()
    )
    completed_call_count = sum(
        name == "kanban_complete" and args["task_id"] == card.task_id
        for name, args in fake_kanban_host.calls
    )

    replayed = delivery.apply(
        WORKFLOW_ID,
        expected_preview_digest=preview.digest,
        confirm=True,
    )
    assert replayed == completed
    assert (
        sum(
            name == "kanban_complete" and args["task_id"] == card.task_id
            for name, args in fake_kanban_host.calls
        )
        == completed_call_count
    )



@pytest.mark.parametrize("prepared_delivery", [True], indirect=True)
def test_delivery_commits_a_reviewed_diff_without_a_final_newline(
    prepared_delivery,
) -> None:
    service, _target, remote, profile_root, commands = prepared_delivery
    delivery = _delivery_service(service, remote, profile_root, commands)
    preview = delivery.preview(WORKFLOW_ID)

    completed = delivery.apply(
        WORKFLOW_ID,
        expected_preview_digest=preview.digest,
        confirm=True,
    )

    authorization = completed.delivery_authorization
    assert authorization is not None and authorization.commit is not None
    assert completed.committed is True
    assert completed.pushed is True
    assert _run(
        ("git", "--git-dir", str(remote), "rev-parse", f"refs/heads/{preview.branch}")
    ) == authorization.commit

def test_delivery_fails_closed_without_a_resolved_credential(prepared_delivery) -> None:
    service, _target, remote, profile_root, commands = prepared_delivery
    delivery = _delivery_service(service, remote, profile_root, commands, credential=None)

    preview = delivery.preview(WORKFLOW_ID)
    assert preview.credential_available is False
    with pytest.raises(DeliveryError, match="credential unavailable"):
        delivery.apply(WORKFLOW_ID, expected_preview_digest=preview.digest, confirm=True)

    assert not any(command[:2] == ("git", "ls-remote") for command in commands)
    assert service.status(WORKFLOW_ID).delivery_authorization is None


def test_delivery_rejects_a_conflicting_remote_branch(prepared_delivery) -> None:
    service, target, remote, profile_root, commands = prepared_delivery
    delivery = _delivery_service(service, remote, profile_root, commands)
    preview = delivery.preview(WORKFLOW_ID)
    _run(
        (
            "git",
            "-C",
            str(target),
            "push",
            str(remote),
            f"HEAD:refs/heads/{preview.branch}",
        )
    )

    with pytest.raises(DeliveryError, match="already exists on the remote"):
        delivery.apply(WORKFLOW_ID, expected_preview_digest=preview.digest, confirm=True)

    assert service.status(WORKFLOW_ID).delivery_authorization is None


def test_delivery_retries_after_commit_failure_on_its_owned_baseline_branch(
    prepared_delivery,
) -> None:
    service, _target, remote, profile_root, commands = prepared_delivery
    delivery = _delivery_service(service, remote, profile_root, commands)
    preview = delivery.preview(WORKFLOW_ID)
    original_runner = delivery.runner
    failed_once = False

    def fail_first_commit(
        command: tuple[str, ...], environment: Mapping[str, str]
    ) -> tuple[int, str]:
        nonlocal failed_once
        if "commit" in command and not failed_once:
            failed_once = True
            return 1, "injected commit failure"
        return original_runner(command, environment)

    delivery.runner = fail_first_commit
    with pytest.raises(DeliveryError, match="reviewed delivery commit failed"):
        delivery.apply(
            WORKFLOW_ID,
            expected_preview_digest=preview.digest,
            confirm=True,
        )

    pending = service.status(WORKFLOW_ID)
    assert pending.delivery_authorization is not None
    assert pending.delivery_authorization.commit is None
    assert pending.worktree_path is not None
    assert (
        _run(("git", "-C", pending.worktree_path, "branch", "--show-current"))
        == preview.branch
    )
    assert (
        _run(("git", "-C", pending.worktree_path, "rev-parse", "HEAD"))
        == preview.baseline_commit
    )
    assert "return 2" in (Path(pending.worktree_path) / "calculator.py").read_text(
        encoding="utf-8"
    )

    completed = delivery.apply(
        WORKFLOW_ID,
        expected_preview_digest=preview.digest,
        confirm=True,
    )
    assert completed.committed is True
    assert completed.pushed is True


def test_delivery_recovers_when_commit_persistence_fails_after_git_commit(
    prepared_delivery,
) -> None:
    service, _target, remote, profile_root, commands = prepared_delivery
    delivery = _delivery_service(service, remote, profile_root, commands)
    preview = delivery.preview(WORKFLOW_ID)
    original_record = service.record_delivery_authorization
    failed_once = False

    def fail_recorded_commit(workflow_id: str, *, authorization):
        nonlocal failed_once
        if authorization.commit is not None and not failed_once:
            failed_once = True
            raise RuntimeError("injected authorization persistence failure")
        return original_record(workflow_id, authorization=authorization)

    service.record_delivery_authorization = fail_recorded_commit  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="authorization persistence failure"):
        delivery.apply(
            WORKFLOW_ID,
            expected_preview_digest=preview.digest,
            confirm=True,
        )

    pending = service.status(WORKFLOW_ID)
    assert pending.delivery_authorization is not None
    assert pending.delivery_authorization.commit is None
    assert pending.worktree_path is not None
    head = _run(("git", "-C", pending.worktree_path, "rev-parse", "HEAD"))
    assert head != preview.baseline_commit

    service.record_delivery_authorization = original_record  # type: ignore[method-assign]
    completed = delivery.apply(
        WORKFLOW_ID,
        expected_preview_digest=preview.digest,
        confirm=True,
    )

    assert completed.committed is True
    assert completed.pushed is True



def test_delivery_replay_releases_worktree_without_repeating_kanban_completion(
    prepared_delivery, fake_kanban_host, monkeypatch
) -> None:
    service, _target, remote, profile_root, commands = prepared_delivery
    delivery = _delivery_service(service, remote, profile_root, commands)
    preview = delivery.preview(WORKFLOW_ID)
    original_remove = service._workspace.remove_worktree
    failed_once = False

    def fail_first_release(target_repository: str, worktree_path: str) -> None:
        nonlocal failed_once
        if not failed_once:
            failed_once = True
            raise RuntimeError("injected worktree release failure")
        original_remove(target_repository, worktree_path)

    monkeypatch.setattr(service._workspace, "remove_worktree", fail_first_release)
    with pytest.raises(RuntimeError, match="injected worktree release failure"):
        delivery.apply(
            WORKFLOW_ID,
            expected_preview_digest=preview.digest,
            confirm=True,
        )

    pending = service.status(WORKFLOW_ID)
    card = pending.card_for(WorkflowStage.DELIVER)
    assert card is not None
    assert pending.committed is True
    assert pending.pushed is True
    assert pending.worktree_owned is True
    completed_call_count = sum(
        name == "kanban_complete" and args["task_id"] == card.task_id
        for name, args in fake_kanban_host.calls
    )
    assert completed_call_count == 1

    replayed = delivery.apply(
        WORKFLOW_ID,
        expected_preview_digest=preview.digest,
        confirm=True,
    )

    assert replayed.worktree_owned is False
    assert replayed.worktree_path is None
    assert (
        sum(
            name == "kanban_complete" and args["task_id"] == card.task_id
            for name, args in fake_kanban_host.calls
        )
        == completed_call_count
    )


def test_delivery_replay_rejects_done_card_without_matching_run_receipt(
    prepared_delivery, fake_kanban_host, monkeypatch
) -> None:
    service, _target, remote, profile_root, commands = prepared_delivery
    delivery = _delivery_service(service, remote, profile_root, commands)
    preview = delivery.preview(WORKFLOW_ID)
    original_remove = service._workspace.remove_worktree
    failed_once = False

    def fail_first_release(target_repository: str, worktree_path: str) -> None:
        nonlocal failed_once
        if not failed_once:
            failed_once = True
            raise RuntimeError("injected worktree release failure")
        original_remove(target_repository, worktree_path)

    monkeypatch.setattr(service._workspace, "remove_worktree", fail_first_release)
    with pytest.raises(RuntimeError, match="injected worktree release failure"):
        delivery.apply(
            WORKFLOW_ID,
            expected_preview_digest=preview.digest,
            confirm=True,
        )

    pending = service.status(WORKFLOW_ID)
    card = pending.card_for(WorkflowStage.DELIVER)
    assert card is not None
    fake_kanban_host.cards[card.task_id]["runs"] = [
        {"outcome": "completed", "metadata": {"schema": "unrelated/v1"}}
    ]

    with pytest.raises(ServiceError, match="exact branch-delivery receipt"):
        delivery.apply(
            WORKFLOW_ID,
            expected_preview_digest=preview.digest,
            confirm=True,
        )

    blocked = service.status(WORKFLOW_ID)
    assert blocked.worktree_owned is True
    assert blocked.worktree_path == pending.worktree_path
