from __future__ import annotations

import fcntl
import hashlib
import json
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from daidala import cli
from daidala.artifact_curator import CuratorPolicy
from daidala.curator_cron import (
    CuratorCronDocument,
    CuratorCronError,
    CuratorCronManager,
    CuratorCronRecord,
    CuratorCronStore,
)
from daidala.service import WorkflowService
from daidala.state import ArtifactReference, SkillDigest, StageProfile, WorkflowStage
from daidala.store import WorkflowStore
from daidala.workflow import new_workflow

NOW = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)


class RecordingRunner:
    def __init__(self) -> None:
        self.commands: list[tuple[str, ...]] = []

    def __call__(self, command: tuple[str, ...]) -> tuple[int, str]:
        self.commands.append(command)
        if command[:3] == ("hermes", "cron", "create"):
            return 0, "Created job: abcdef123456\n"
        if command[:3] == ("hermes", "cron", "edit"):
            return 0, "Updated job: abcdef123456\n"
        if command[:3] == ("hermes", "cron", "remove"):
            return 0, "Removed job: daidala-artifact-curator (abcdef123456)\n"
        return 1, "unsupported"


def _root(tmp_path: Path) -> Path:
    root = (tmp_path / "profiles" / "controller" / "daidala").resolve()
    root.mkdir(parents=True)
    return root


def _terminal_ledger(store: WorkflowStore, workflow_id: str):
    artifact_root = store.data_root / "workflows" / workflow_id / "artifacts"
    plan_path = artifact_root / "policy-0000/plan-0000/plan.md"
    delivery_path = artifact_root / "policy-0000/plan-0000/delivery.json"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text("# Plan\n", encoding="utf-8")
    delivery_path.write_text('{"committed":false,"pushed":false}\n', encoding="utf-8")

    def reference(path: Path, stage: WorkflowStage) -> ArtifactReference:
        content = path.read_bytes()
        return ArtifactReference(
            stage=stage,
            plan_revision=0,
            path=str(path.resolve()),
            digest=hashlib.sha256(content).hexdigest(),
            recorded_at=NOW,
            policy_revision=0,
        )

    profiles = tuple(
        StageProfile(stage=stage, profile="worker")
        for stage in WorkflowStage
        if stage is not WorkflowStage.APPROVAL
    )
    ledger = new_workflow(
        workflow_id=workflow_id,
        board_slug="daidala-test",
        target_repository=str((store.data_root / "target").resolve()),
        baseline_commit="a" * 40,
        requested_goal="Exercise scheduled artifact curation",
        pack_name="addyosmani",
        pack_source_revision="b" * 40,
        skill_digests=(SkillDigest(name="interview-me", digest="c" * 64),),
        stage_profiles=profiles,
        created_at=NOW,
    )
    return replace(
        ledger,
        artifacts=(
            reference(plan_path, WorkflowStage.PLAN),
            reference(delivery_path, WorkflowStage.DELIVER),
        ),
        updated_at=NOW,
    )


def test_cron_state_is_private_strict_and_compare_and_swap(tmp_path: Path) -> None:
    store = CuratorCronStore(_root(tmp_path))
    initial = store.read()
    record = CuratorCronRecord(
        job_id="abcdef123456",
        controller_profile="controller",
        interval="every 1d",
        policy_digest="a" * 64,
    )
    updated = store.replace(
        CuratorCronDocument(record=record),
        expected_digest=initial.digest,
    )

    assert store.path.stat().st_mode & 0o777 == 0o600
    assert store.read() == updated
    with pytest.raises(CuratorCronError, match="concurrently"):
        store.replace(CuratorCronDocument(), expected_digest=initial.digest)

    payload = updated.to_dict()
    payload["unexpected"] = True
    store.path.write_text(json.dumps(payload), encoding="utf-8")
    os.chmod(store.path, 0o600)
    with pytest.raises(CuratorCronError, match="schema"):
        store.read()


def test_setup_replays_updates_exact_job_and_removes_only_recorded_id(tmp_path: Path) -> None:
    runner = RecordingRunner()
    manager = CuratorCronManager(_root(tmp_path), command_runner=runner)
    policy = CuratorPolicy(enabled=False, stale_after_days=30, archive_after_days=90)

    preview = manager.preview_setup("every 1d", policy)
    assert preview.action == "create"
    assert preview.controller_profile == "controller"
    assert preview.policy_digest == policy.digest
    assert preview.script_name == "daidala-artifact-curator.sh"
    assert preview.script_entrypoint == "daidala curator tick"

    result = manager.apply_setup(
        "every 1d",
        policy,
        expected_preview_digest=preview.digest,
        confirmed_controller_profile="controller",
    )
    assert result.record is not None
    assert result.record.job_id == "abcdef123456"
    assert runner.commands == [
        (
            "hermes",
            "cron",
            "create",
            "every 1d",
            "--no-agent",
            "--script",
            "daidala-artifact-curator.sh",
            "--deliver",
            "local",
            "--name",
            "daidala-artifact-curator",
        )
    ]
    script = manager.script_path.read_text(encoding="utf-8")
    assert "exec daidala curator tick" in script
    assert "password" not in script.lower()
    assert manager.script_path.stat().st_mode & 0o777 == 0o600

    replay = manager.preview_setup("every 1d", policy)
    assert replay.action == "none"
    assert manager.apply_setup(
        "every 1d",
        policy,
        expected_preview_digest=replay.digest,
        confirmed_controller_profile="controller",
    ).replayed is True
    assert len(runner.commands) == 1

    changed_policy = replace(policy, enabled=True)
    update = manager.preview_setup("every 2d", changed_policy)
    assert update.action == "update"
    assert update.digest != replay.digest
    manager.apply_setup(
        "every 2d",
        changed_policy,
        expected_preview_digest=update.digest,
        confirmed_controller_profile="controller",
    )
    assert runner.commands[-1] == (
        "hermes",
        "cron",
        "edit",
        "abcdef123456",
        "--schedule",
        "every 2d",
        "--script",
        "daidala-artifact-curator.sh",
        "--no-agent",
        "--deliver",
        "local",
        "--name",
        "daidala-artifact-curator",
    )

    remove = manager.preview_remove(changed_policy)
    assert remove.job_id == "abcdef123456"
    manager.apply_remove(
        changed_policy,
        expected_preview_digest=remove.digest,
        confirmed_controller_profile="controller",
    )
    assert runner.commands[-1] == (
        "hermes",
        "cron",
        "remove",
        "abcdef123456",
    )
    assert manager.status().record is None


def test_setup_requires_fresh_digest_and_literal_controller_confirmation(tmp_path: Path) -> None:
    manager = CuratorCronManager(_root(tmp_path), command_runner=RecordingRunner())
    policy = CuratorPolicy()
    preview = manager.preview_setup("every 1d", policy)

    with pytest.raises(CuratorCronError, match="preview digest"):
        manager.apply_setup(
            "every 2d",
            policy,
            expected_preview_digest=preview.digest,
            confirmed_controller_profile="controller",
        )
    with pytest.raises(CuratorCronError, match="not confirmed"):
        manager.apply_setup(
            "every 1d",
            policy,
            expected_preview_digest=preview.digest,
            confirmed_controller_profile="worker",
        )
    assert manager.status().record is None


def test_failed_public_cli_call_never_records_unverified_job_id(tmp_path: Path) -> None:
    commands: list[tuple[str, ...]] = []

    def fail(command: tuple[str, ...]) -> tuple[int, str]:
        commands.append(command)
        return 1, "host failure with private details"

    manager = CuratorCronManager(_root(tmp_path), command_runner=fail)
    policy = CuratorPolicy()
    preview = manager.preview_setup("every 1d", policy)

    with pytest.raises(CuratorCronError, match="creation failed") as raised:
        manager.apply_setup(
            "every 1d",
            policy,
            expected_preview_digest=preview.digest,
            confirmed_controller_profile="controller",
        )
    assert "private details" not in str(raised.value)
    assert manager.status().record is None
    assert commands[0][:3] == ("hermes", "cron", "create")


def test_setup_rejects_noncanonical_output_and_compensates_failed_state_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)

    def prefixed_output(command: tuple[str, ...]) -> tuple[int, str]:
        return 0, "warning\nCreated job: abcdef123456\n"

    malformed = CuratorCronManager(root, command_runner=prefixed_output)
    policy = CuratorPolicy()
    preview = malformed.preview_setup("every 1d", policy)
    with pytest.raises(CuratorCronError, match="creation failed"):
        malformed.apply_setup(
            "every 1d",
            policy,
            expected_preview_digest=preview.digest,
            confirmed_controller_profile="controller",
        )

    runner = RecordingRunner()
    manager = CuratorCronManager(root, command_runner=runner)
    preview = manager.preview_setup("every 1d", policy)

    def fail_replace(*args, **kwargs):
        raise CuratorCronError("state cannot be replaced")

    monkeypatch.setattr(manager.store, "replace", fail_replace)
    with pytest.raises(CuratorCronError, match="cannot be replaced"):
        manager.apply_setup(
            "every 1d",
            policy,
            expected_preview_digest=preview.digest,
            confirmed_controller_profile="controller",
        )
    assert runner.commands[-1] == (
        "hermes",
        "cron",
        "remove",
        "abcdef123456",
    )


def test_schedule_apply_fails_closed_on_lock_contention(tmp_path: Path) -> None:
    manager = CuratorCronManager(_root(tmp_path), command_runner=RecordingRunner())
    policy = CuratorPolicy()
    preview = manager.preview_setup("every 1d", policy)
    descriptor = os.open(manager.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        with pytest.raises(CuratorCronError, match="lock contention"):
            manager.apply_setup(
                "every 1d",
                policy,
                expected_preview_digest=preview.digest,
                confirmed_controller_profile="controller",
            )
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def test_tick_binding_rejects_policy_or_script_drift(tmp_path: Path) -> None:
    runner = RecordingRunner()
    manager = CuratorCronManager(_root(tmp_path), command_runner=runner)
    policy = CuratorPolicy()
    preview = manager.preview_setup("every 1d", policy)
    manager.apply_setup(
        "every 1d",
        policy,
        expected_preview_digest=preview.digest,
        confirmed_controller_profile="controller",
    )

    assert manager.require_current_policy(policy).job_id == "abcdef123456"
    with pytest.raises(CuratorCronError, match="policy changed"):
        manager.require_current_policy(replace(policy, enabled=True))

    manager.script_path.write_text("tampered\n", encoding="utf-8")
    os.chmod(manager.script_path, 0o600)
    with pytest.raises(CuratorCronError, match="script identity"):
        manager.require_current_policy(policy)


def test_schedule_cli_is_dry_run_first_and_tick_is_silent_without_work(
    tmp_path: Path, capsys
) -> None:
    runner = RecordingRunner()
    service = WorkflowService(
        WorkflowStore(_root(tmp_path)),
        cron_command_runner=runner,
    )

    def factory() -> WorkflowService:
        return service

    argv = ["curator", "schedule", "setup", "every 1d"]

    assert cli.main(argv, service_factory=factory) == 0
    preview = json.loads(capsys.readouterr().out)["schedule"]
    assert preview["action"] == "create"
    assert preview["controller_profile"] == "controller"
    assert runner.commands == []

    assert cli.main([*argv, "--apply"], service_factory=factory) == 1
    assert "--expected-preview-digest" in capsys.readouterr().out
    assert cli.main(
        [
            *argv,
            "--apply",
            "--expected-preview-digest",
            preview["preview_digest"],
            "--confirm-controller-profile",
            "controller",
        ],
        service_factory=factory,
    ) == 0
    applied = json.loads(capsys.readouterr().out)
    assert applied["dry_run"] is False
    assert applied["schedule"]["record"]["job_id"] == "abcdef123456"

    assert cli.main(["curator", "tick"], service_factory=factory) == 0
    assert capsys.readouterr().out == ""


def test_curator_policy_cli_requires_state_and_literal_policy_digests(
    tmp_path: Path, capsys
) -> None:
    service = WorkflowService(WorkflowStore(_root(tmp_path)))

    def factory() -> WorkflowService:
        return service

    argv = [
        "curator",
        "configure",
        "--enabled",
        "--stale-after-days",
        "10",
        "--archive-after-days",
        "20",
    ]
    assert cli.main(argv, service_factory=factory) == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview["dry_run"] is True
    assert preview["policy"]["enabled"] is True
    assert service.curator_status().policy.enabled is False

    assert cli.main(
        [
            *argv,
            "--apply",
            "--expected-state-digest",
            preview["state_digest"],
            "--confirm-policy-digest",
            "f" * 64,
        ],
        service_factory=factory,
    ) == 1
    assert "does not match" in capsys.readouterr().out
    assert service.curator_status().policy.enabled is False

    assert cli.main(
        [
            *argv,
            "--apply",
            "--expected-state-digest",
            preview["state_digest"],
            "--confirm-policy-digest",
            preview["policy_digest"],
        ],
        service_factory=factory,
    ) == 0
    applied = json.loads(capsys.readouterr().out)
    assert applied["dry_run"] is False
    assert applied["curator"]["policy"]["enabled"] is True


def test_registered_tick_archives_once_then_converges(tmp_path: Path) -> None:
    runner = RecordingRunner()
    store = WorkflowStore(_root(tmp_path))
    workflow_id = "wf-cron"
    ledger = _terminal_ledger(store, workflow_id)
    store.create(ledger)
    clock = [NOW]
    service = WorkflowService(
        store,
        clock=lambda: clock[0],
        cron_command_runner=runner,
    )
    initial = service.curator_status()
    configured = service.configure_curator(
        enabled=True,
        stale_after_days=1,
        archive_after_days=2,
        expected_state_digest=initial.state_digest,
    )
    schedule = service.preview_curator_cron_setup("every 1d")
    service.apply_curator_cron_setup(
        "every 1d",
        expected_preview_digest=schedule.digest,
        confirmed_controller_profile="controller",
    )

    observed = service.run_curator_cron_tick()
    assert observed is not None and observed.transitioned == 1
    clock[0] = NOW + timedelta(days=2)
    archived = service.run_curator_cron_tick()
    assert archived is not None and archived.archived_files == 2
    assert not Path(ledger.artifacts[0].path).exists()
    assert service.run_curator_cron_tick() is None
    assert service.curator_status().policy == configured.policy
