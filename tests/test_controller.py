from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from daidala.adapters import (
    ClaimIdentity,
    IntakeAdapter,
    IntakeCategory,
    IntakeRecord,
    NotificationAdapter,
    NotificationReceipt,
)
from daidala.controller import AdmissionCoordinator, CycleArtifactStore
from daidala.cycles import CycleIdentity, CycleMode
from daidala.errors import PolicyViolationError
from daidala.projects import ProjectManifest, parse_project_manifest
from daidala.registrations import ControllerRegistration, parse_controller_registration
from daidala.state import SkillDigest, StageProfile, WorkflowLedger, WorkflowStage
from daidala.workflow import new_workflow

ROOT = Path(__file__).parents[1]
NOW = datetime(2026, 7, 13, 12, 0, tzinfo=UTC)
BASELINE = "b" * 40


def manifest() -> ProjectManifest:
    return parse_project_manifest((ROOT / ".daidala/project.yaml").read_text())


def registration() -> ControllerRegistration:
    return parse_controller_registration(
        """schema: daidala.controller-registration/v2
project_id: forgegod-daidala
checkout: /srv/daidala
controller_profile: daidala-self-improvement
board: daidala-forgegod-daidala
repository_identity:
  canonical: forgegod/daidala
  verified_remote: git@github.com:forgegod/daidala.git
credentials:
  intake: github-daidala-read-issues
  findings: github-daidala-write-issues
approval:
  maintainers: [forgegod]
notifications:
  adapter: hermes-gateway
  target: attended-daidala
  destination: telegram:-1001234567890:17585
evaluator:
  backend: restricted-container
  network: denied-by-default
limits:
  active_cycles: 1
  goal_turns: 12
  delegated_workers: 3
  research_query_batches: 3
  extracted_sources: 3
  wall_clock_seconds: 3600
"""
    )


def intake() -> IntakeRecord:
    return IntakeRecord(
        adapter="github-issues",
        item_id="42",
        source_url="https://github.com/forgegod/daidala/issues/42",
        category=IntakeCategory.REGRESSION,
        priority=1,
        goal="Prove deterministic admission",
        acceptance_criteria=("Duplicate admission converges.",),
        evidence_digests=("a" * 64,),
        dependencies=(),
        risk="Fixture only.",
        admission_actor="forgegod",
        ready=True,
    )


def stage_profiles() -> dict[str, str]:
    return {
        stage.value: "daidala-self-improvement"
        for stage in WorkflowStage
        if stage is not WorkflowStage.APPROVAL
    }


def expected_cycle_id() -> str:
    project = manifest()
    pack = project.allowed_packs[0]
    record = intake()
    return CycleIdentity(
        project_id=project.project_id,
        mode=CycleMode.IMPROVE,
        intake_adapter=record.adapter,
        intake_item_id=record.item_id,
        manifest_digest=project.digest,
        baseline_revision=BASELINE,
        pack_name=pack.name,
        pack_source_revision=pack.source_revision,
        pack_content_digest=pack.content_digest,
    ).cycle_id


class FakeIntake(IntakeAdapter):
    def __init__(
        self,
        record: IntakeRecord,
        *,
        mutate_goal: bool = False,
        returned_lease_seconds: int | None = None,
    ) -> None:
        self.record = record
        self.mutate_goal = mutate_goal
        self.returned_lease_seconds = returned_lease_seconds
        self.claim_calls = 0

    def fetch_ready(self, *, limit: int) -> tuple[IntakeRecord, ...]:
        return (self.record,)[:limit]

    def claim(self, item_id: str, claim: ClaimIdentity) -> IntakeRecord:
        self.claim_calls += 1
        assert item_id == self.record.item_id
        goal = "Changed by adapter" if self.mutate_goal else self.record.goal
        returned_claim = claim
        if self.returned_lease_seconds is not None:
            returned_claim = replace(
                claim,
                lease_expires_at=claim.claimed_at
                + timedelta(seconds=self.returned_lease_seconds),
            )
        return replace(self.record, goal=goal, claim=returned_claim)


class FakeNotifications(NotificationAdapter):
    def __init__(
        self,
        target: str = "attended-daidala",
        event_id: str | None = None,
    ) -> None:
        self.target = target
        self.event_id = event_id
        self.calls: list[dict[str, object]] = []

    def deliver(self, payload: dict[str, object]) -> NotificationReceipt:
        self.calls.append(payload)
        return NotificationReceipt(
            self.event_id or str(payload["event_id"]),
            "hermes-gateway",
            self.target,
            f"receipt-{payload['event_id']}",
            NOW,
        )


class FakeWorkflow:
    def __init__(self) -> None:
        self.calls = 0
        self.expected_baselines: list[object] = []
        self.ledgers: dict[str, WorkflowLedger] = {}

    def start(self, **kwargs: object) -> WorkflowLedger:
        self.calls += 1
        self.expected_baselines.append(kwargs.get("expected_baseline_commit"))
        workflow_id = str(kwargs["workflow_id"])
        if workflow_id not in self.ledgers:
            self.ledgers[workflow_id] = new_workflow(
                workflow_id=workflow_id,
                board_slug=str(kwargs["board_slug"]),
                target_repository=str(kwargs["target_repository"]),
                baseline_commit=BASELINE,
                requested_goal=str(kwargs["goal"]),
                pack_name=str(kwargs["pack_name"]),
                pack_source_revision=manifest().allowed_packs[0].source_revision,
                skill_digests=(SkillDigest("fixture-skill", "c" * 64),),
                stage_profiles=tuple(
                    StageProfile(stage, "daidala-self-improvement")
                    for stage in WorkflowStage
                    if stage is not WorkflowStage.APPROVAL
                ),
                created_at=NOW,
            )
        return self.ledgers[workflow_id]


def coordinator(
    tmp_path: Path,
    intake_adapter: FakeIntake,
    notifications: FakeNotifications,
    workflow: FakeWorkflow,
    *,
    clock: datetime = NOW,
) -> AdmissionCoordinator:
    return AdmissionCoordinator(
        store=CycleArtifactStore(tmp_path),
        workflow=workflow,
        intake_adapter=intake_adapter,
        notification_adapter=notifications,
        clock=lambda: clock,
    )


def admit(
    coordinator: AdmissionCoordinator,
    *,
    intake_record: IntakeRecord | None = None,
):  # type: ignore[no-untyped-def]
    return coordinator.admit(
        manifest=manifest(),
        registration=registration(),
        intake=intake_record or intake(),
        baseline_revision=BASELINE,
        stage_profiles=stage_profiles(),
        constraints_content=(ROOT / ".daidala/constraints.yaml").read_text(),
    )


def test_duplicate_admission_converges_on_cycle_workflow_and_receipt(tmp_path: Path) -> None:
    intake_adapter = FakeIntake(intake())
    notifications = FakeNotifications()
    workflow = FakeWorkflow()
    subject = coordinator(tmp_path, intake_adapter, notifications, workflow)

    first = admit(subject)
    second = admit(subject)

    assert first == second
    assert first[0].workflow_id == first[0].cycle.cycle_id
    assert first[1].workflow_id == first[0].cycle.cycle_id
    assert intake_adapter.claim_calls == 1
    assert workflow.calls == 2
    assert workflow.expected_baselines == [BASELINE, BASELINE]
    assert len(notifications.calls) == 1
    snapshot = (
        tmp_path
        / "projects"
        / "forgegod-daidala"
        / "cycles"
        / first[0].cycle.cycle_id
        / "manifest-snapshot.json"
    )
    assert snapshot.is_file()
    with pytest.raises(PolicyViolationError, match="stage profiles must be a tuple"):
        replace(first[0], stage_profiles=("invalid",))  # type: ignore[arg-type]


def test_preview_validates_exact_admission_without_mutating_adapters_or_artifacts(
    tmp_path: Path,
) -> None:
    intake_adapter = FakeIntake(intake())
    notifications = FakeNotifications()
    workflow = FakeWorkflow()
    subject = coordinator(tmp_path, intake_adapter, notifications, workflow)

    preview = subject.preview(
        manifest=manifest(),
        registration=registration(),
        intake=intake(),
        baseline_revision=BASELINE,
        stage_profiles=stage_profiles(),
        constraints_content=(ROOT / ".daidala/constraints.yaml").read_text(),
    )

    assert preview.cycle.cycle_id == expected_cycle_id()
    assert preview.workflow_id == expected_cycle_id()
    assert preview.intake_digest == intake().digest
    assert preview.to_dict()["dry_run"] is True
    assert intake_adapter.claim_calls == 0
    assert notifications.calls == []
    assert workflow.calls == 0
    assert not (tmp_path / "projects").exists()


def test_pack_content_digest_mismatch_fails_before_adapters_or_artifacts(
    tmp_path: Path,
) -> None:
    project = manifest()
    tampered_pack = replace(project.allowed_packs[0], content_digest="0" * 64)
    tampered_manifest = replace(
        project,
        allowed_packs=(tampered_pack, *project.allowed_packs[1:]),
    )
    intake_adapter = FakeIntake(intake())
    notifications = FakeNotifications()
    workflow = FakeWorkflow()
    subject = coordinator(tmp_path, intake_adapter, notifications, workflow)

    with pytest.raises(PolicyViolationError, match="pack identity does not match"):
        subject.admit(
            manifest=tampered_manifest,
            registration=registration(),
            intake=intake(),
            baseline_revision=BASELINE,
            stage_profiles=stage_profiles(),
            constraints_content=(ROOT / ".daidala/constraints.yaml").read_text(),
        )

    assert intake_adapter.claim_calls == 0
    assert notifications.calls == []
    assert workflow.calls == 0
    assert not (tmp_path / "projects").exists()


def test_malformed_adapter_output_fails_before_workflow_or_notification(tmp_path: Path) -> None:
    intake_adapter = FakeIntake(intake(), mutate_goal=True)
    notifications = FakeNotifications()
    workflow = FakeWorkflow()

    with pytest.raises(PolicyViolationError, match="immutable admission fields"):
        admit(coordinator(tmp_path, intake_adapter, notifications, workflow))

    assert workflow.calls == 0
    assert notifications.calls == []


def test_unauthorized_actor_and_malformed_constraints_fail_before_adapters(
    tmp_path: Path,
) -> None:
    intake_adapter = FakeIntake(intake())
    notifications = FakeNotifications()
    workflow = FakeWorkflow()
    subject = coordinator(tmp_path, intake_adapter, notifications, workflow)

    with pytest.raises(PolicyViolationError, match="authorized maintainer"):
        subject.admit(
            manifest=manifest(),
            registration=registration(),
            intake=replace(intake(), admission_actor="unknown"),
            baseline_revision=BASELINE,
            stage_profiles=stage_profiles(),
            constraints_content=(ROOT / ".daidala/constraints.yaml").read_text(),
        )
    with pytest.raises(PolicyViolationError, match="missing: global"):
        subject.admit(
            manifest=manifest(),
            registration=registration(),
            intake=intake(),
            baseline_revision=BASELINE,
            stage_profiles=stage_profiles(),
            constraints_content="schema: wrong\n",
        )

    assert intake_adapter.claim_calls == 0
    assert workflow.calls == 0
    assert notifications.calls == []


def test_notification_receipt_must_match_trusted_registration(tmp_path: Path) -> None:
    notifications = FakeNotifications(target="wrong-target")
    workflow = FakeWorkflow()
    with pytest.raises(PolicyViolationError, match="target does not match"):
        admit(coordinator(tmp_path, FakeIntake(intake()), notifications, workflow))

    assert workflow.calls == 0

    wrong_event = FakeNotifications(event_id="cycle-wrong:admitted")
    with pytest.raises(PolicyViolationError, match="event does not match"):
        admit(coordinator(tmp_path / "wrong-event", FakeIntake(intake()), wrong_event, workflow))

    assert workflow.calls == 0


def test_invalid_local_inputs_fail_before_claim_artifact_or_notification(tmp_path: Path) -> None:
    intake_adapter = FakeIntake(intake())
    notifications = FakeNotifications()
    workflow = FakeWorkflow()
    subject = coordinator(tmp_path, intake_adapter, notifications, workflow)
    arguments = {
        "manifest": manifest(),
        "registration": registration(),
        "intake": intake(),
        "baseline_revision": BASELINE,
        "stage_profiles": stage_profiles(),
        "constraints_content": (ROOT / ".daidala/constraints.yaml").read_text(),
    }

    with pytest.raises(PolicyViolationError, match="claim lease"):
        subject.admit(**arguments, claim_lease_seconds=1)
    invalid_profiles = stage_profiles()
    invalid_profiles.pop("define")
    with pytest.raises(PolicyViolationError, match="map every executable stage"):
        subject.admit(**{**arguments, "stage_profiles": invalid_profiles})
    preclaimed = replace(
        intake(),
        claim=ClaimIdentity("another-cycle", NOW, NOW + timedelta(minutes=15)),
    )
    with pytest.raises(PolicyViolationError, match="another owner"):
        subject.admit(**{**arguments, "intake": preclaimed})
    expired = replace(
        intake(),
        claim=ClaimIdentity(
            expected_cycle_id(),
            NOW - timedelta(minutes=16),
            NOW - timedelta(minutes=1),
        ),
    )
    with pytest.raises(PolicyViolationError, match="two-authority reconciliation"):
        subject.admit(**{**arguments, "intake": expired})
    invalid_profiles_with_mixed_keys = {**stage_profiles(), 1: "invalid"}
    with pytest.raises(PolicyViolationError, match="map strings to strings"):
        subject.admit(
            **{**arguments, "stage_profiles": invalid_profiles_with_mixed_keys}  # type: ignore[dict-item]
        )

    assert intake_adapter.claim_calls == 0
    assert notifications.calls == []
    assert workflow.calls == 0
    assert not (tmp_path / "projects").exists()


def test_adapter_claim_lease_is_bounded_before_downstream_effects(tmp_path: Path) -> None:
    intake_adapter = FakeIntake(intake(), returned_lease_seconds=86_401)
    notifications = FakeNotifications()
    workflow = FakeWorkflow()

    with pytest.raises(PolicyViolationError, match="invalid claim lease"):
        admit(coordinator(tmp_path, intake_adapter, notifications, workflow))

    assert notifications.calls == []
    assert workflow.calls == 0


def test_replay_rejects_changed_constraints_and_stage_profiles(tmp_path: Path) -> None:
    intake_adapter = FakeIntake(intake())
    notifications = FakeNotifications()
    workflow = FakeWorkflow()
    subject = coordinator(tmp_path, intake_adapter, notifications, workflow)
    admit(subject)
    constraints = (ROOT / ".daidala/constraints.yaml").read_text()
    arguments = {
        "manifest": manifest(),
        "registration": registration(),
        "intake": intake(),
        "baseline_revision": BASELINE,
        "stage_profiles": stage_profiles(),
    }

    changed_constraints = constraints.replace(
        "Keep one active self-improvement cycle globally.",
        "Keep exactly one active self-improvement cycle globally.",
    )
    with pytest.raises(PolicyViolationError, match="constraints conflict"):
        subject.admit(**arguments, constraints_content=changed_constraints)
    changed_profiles = stage_profiles()
    changed_profiles["define"] = "different-profile"
    with pytest.raises(PolicyViolationError, match="stage profiles conflict"):
        subject.admit(
            **{**arguments, "stage_profiles": changed_profiles},
            constraints_content=constraints,
        )

    assert intake_adapter.claim_calls == 1
    assert len(notifications.calls) == 1
    assert workflow.calls == 1


def test_expired_stored_claim_resumes_same_admission_owner(tmp_path: Path) -> None:
    intake_adapter = FakeIntake(intake())
    notifications = FakeNotifications()
    workflow = FakeWorkflow()
    admit(coordinator(tmp_path, intake_adapter, notifications, workflow))

    replay = admit(
        coordinator(
            tmp_path,
            intake_adapter,
            notifications,
            workflow,
            clock=NOW + timedelta(minutes=16),
        )
    )

    assert replay[0].cycle.cycle_id == expected_cycle_id()
    assert intake_adapter.claim_calls == 1
    assert len(notifications.calls) == 1
    assert workflow.calls == 2


def test_expired_claim_without_stored_admission_requires_reconciliation(
    tmp_path: Path,
) -> None:
    expired = replace(
        intake(),
        claim=ClaimIdentity(
            claimant=expected_cycle_id(),
            claimed_at=NOW - timedelta(minutes=16),
            lease_expires_at=NOW - timedelta(minutes=1),
        ),
    )
    subject = coordinator(
        tmp_path,
        FakeIntake(expired),
        FakeNotifications(),
        FakeWorkflow(),
    )

    with pytest.raises(PolicyViolationError, match="two-authority reconciliation"):
        admit(subject, intake_record=expired)
