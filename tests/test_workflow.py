from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from wingstaff.errors import PolicyViolationError
from wingstaff.packs import SkillActivationMode, validate_pack
from wingstaff.state import (
    ActivationCategory,
    ActivationDecision,
    ActivationManifest,
    ActivationManifestReference,
    ActivationReferenceState,
    SkillDigest,
    StageProfile,
    WorkflowConstraintsArtifact,
    WorkflowConstraintsIdentity,
    WorkflowLedger,
    WorkflowStage,
)
from wingstaff.workflow import (
    approve_plan,
    new_workflow,
    record_artifact,
    record_card,
    record_constraints,
    record_skill_activation,
    record_verification,
    record_worktree,
    release_worktree,
    replace_plan,
)

NOW = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)
PROFILES = tuple(
    StageProfile(stage=stage, profile=f"{stage.value}-profile")
    for stage in WorkflowStage
    if stage is not WorkflowStage.APPROVAL
)
TARGET = "/tmp/wingstaff-target"
WORKTREE = "/tmp/wingstaff-worktrees/workflow-1"
ACTIVATION_DIGEST = "b" * 64


def activation_pack():
    return validate_pack(
        {
            "schema_version": 1,
            "name": "activation-pack",
            "source": "https://github.com/owner/repository",
            "source_revision": "a" * 40,
            "lifecycle": {
                "human_gate_after": "plan",
                "stages": [
                    {
                        "id": stage.value,
                        "skills": [
                            {
                                "name": "activation-skill",
                                "activation": "required",
                                "install": "owner/repository/activation-skill",
                                "content_digest": ACTIVATION_DIGEST,
                            }
                        ],
                    }
                    for stage in WorkflowStage
                    if stage is not WorkflowStage.APPROVAL
                ],
            },
        }
    )


def activation_ledger() -> WorkflowLedger:
    return replace(
        make_ledger(),
        pack_name="activation-pack",
        pack_source_revision="a" * 40,
        skill_digests=(
            SkillDigest(name="activation-skill", digest=ACTIVATION_DIGEST),
        ),
    )


def activation_manifest(
    *,
    stage: WorkflowStage = WorkflowStage.DEFINE,
    revision: int = 0,
    sequence: int = 1,
    supersedes_digest: str | None = None,
    category: ActivationCategory = ActivationCategory.APPLICABLE,
) -> ActivationManifest:
    return ActivationManifest(
        schema="wingstaff.skill-activation/v1",
        workflow_id="workflow-1",
        stage=stage,
        plan_revision=revision,
        pack="activation-pack",
        pack_source_revision="a" * 40,
        sequence=sequence,
        supersedes_digest=supersedes_digest,
        decisions=(
            ActivationDecision(
                name="activation-skill",
                skill_digest=ACTIVATION_DIGEST,
                activation_mode=SkillActivationMode.REQUIRED,
                category=category,
                rank=1 if category is ActivationCategory.APPLICABLE else None,
                matched_criteria=("The pack requires this stage adapter.",),
                evidence=("The selected pack declares the adapter.",),
                rationale="Apply the required stage adapter.",
                condition=None,
            ),
        ),
    )


def make_ledger() -> WorkflowLedger:
    return new_workflow(
        workflow_id="workflow-1",
        board_slug="wingstaff-test",
        target_repository=TARGET,
        baseline_commit="abcdef123456",
        requested_goal="Fix the deliberately failing test",
        pack_name="addyosmani",
        pack_source_revision="source@0123456789abcdef",
        skill_digests=(SkillDigest(name="interview-me", digest="digest-1"),),
        stage_profiles=PROFILES,
        created_at=NOW,
    )


def with_activation(
    ledger: WorkflowLedger,
    stage: WorkflowStage,
    *,
    state: ActivationReferenceState = ActivationReferenceState.FINALIZED,
    blocked: bool = False,
) -> WorkflowLedger:
    identity = (
        f"{stage.value}:{ledger.activation_revision_for(stage)}:"
        f"{len(ledger.activation_manifests)}"
    )
    return replace(
        ledger,
        activation_manifests=(
            *ledger.activation_manifests,
            ActivationManifestReference(
                stage=stage,
                plan_revision=ledger.activation_revision_for(stage),
                sequence=1,
                path=f"/tmp/{stage.value}-activation.json",
                digest=hashlib.sha256(identity.encode()).hexdigest(),
                state=state,
                blocked=blocked,
                supersedes_digest=None,
            ),
        ),
    )


def make_planned() -> WorkflowLedger:
    ledger = record_artifact(
        with_activation(make_ledger(), WorkflowStage.DEFINE),
        stage=WorkflowStage.DEFINE,
        path="artifacts/define.md",
        digest="define-v1",
        recorded_at=NOW + timedelta(minutes=1),
    )
    return record_artifact(
        with_activation(ledger, WorkflowStage.PLAN),
        stage=WorkflowStage.PLAN,
        path="artifacts/plan.md",
        digest="plan-v1",
        recorded_at=NOW + timedelta(minutes=2),
    )


def make_implementing() -> WorkflowLedger:
    ledger = approve_plan(
        make_planned(),
        plan_digest="plan-v1",
        decided_at=NOW + timedelta(minutes=3),
    )
    return record_worktree(
        ledger,
        worktree_path=WORKTREE,
        recorded_at=NOW + timedelta(minutes=4),
    )


def test_new_ledger_contains_policy_facts_but_no_operational_status() -> None:
    ledger = make_ledger()
    payload = ledger.to_dict()

    assert ledger.board_slug == "wingstaff-test"
    assert ledger.baseline_commit == "abcdef123456"
    assert ledger.plan_revision == 0
    assert ledger.committed is ledger.pushed is False
    assert ledger.created_at == ledger.updated_at == NOW
    assert {"status", "current_stage", "failure_reason"}.isdisjoint(payload)


@pytest.mark.parametrize(
    "target",
    ["owner/repository", "https://example.invalid/repository.git", "git@example.invalid:repo.git"],
)
def test_new_ledger_rejects_nonlocal_targets(target: str) -> None:
    with pytest.raises(PolicyViolationError, match="absolute local path"):
        replace(make_ledger(), target_repository=target)


def test_serialization_round_trip_preserves_complete_ledger() -> None:
    ledger = record_card(
        make_planned(),
        stage=WorkflowStage.APPROVAL,
        task_id="t_approval",
        idempotency_key="wingstaff:workflow-1:0:approval",
        recorded_at=NOW + timedelta(minutes=3),
    )

    assert WorkflowLedger.from_dict(ledger.to_dict()) == ledger


def test_constraint_recording_is_idempotent_and_invalidates_approval() -> None:
    from wingstaff.constraints import parse_workflow_constraints

    constraints = parse_workflow_constraints(
        "schema: wingstaff.workflow-constraints/v1\nglobal: [Never commit.]\n"
    )
    artifact = WorkflowConstraintsArtifact(
        "wingstaff.workflow-constraints-artifact/v1",
        "workflow-1",
        WorkflowConstraintsIdentity(1, 1, constraints.digest),
        constraints.canonical_bytes().decode(),
    )
    approved = approve_plan(
        make_planned(), plan_digest="plan-v1", decided_at=NOW + timedelta(minutes=3)
    )
    recorded = record_constraints(
        approved,
        artifact=artifact,
        path="/tmp/constraints-1.json",
        expected_current_digest=None,
        recorded_at=NOW + timedelta(minutes=4),
    )
    assert recorded.policy_revision == 1
    assert recorded.approval is None
    assert record_constraints(
        recorded,
        artifact=artifact,
        path="/tmp/constraints-1.json",
        expected_current_digest=constraints.digest,
        recorded_at=NOW + timedelta(minutes=5),
    ) is recorded
    with pytest.raises(PolicyViolationError, match="expected current"):
        record_constraints(
            recorded,
            artifact=artifact,
            path="/tmp/constraints-1.json",
            expected_current_digest=None,
            recorded_at=NOW + timedelta(minutes=5),
        )


def test_approval_is_exact_and_plan_replacement_invalidates_it() -> None:
    planned = make_planned()
    with pytest.raises(PolicyViolationError, match="current plan digest"):
        approve_plan(
            planned,
            plan_digest="stale-plan",
            decided_at=NOW + timedelta(minutes=3),
        )

    approved = approve_plan(
        planned,
        plan_digest="plan-v1",
        decided_at=NOW + timedelta(minutes=3),
    )
    replacement = replace_plan(
        approved,
        path="artifacts/plan-v2.md",
        digest="plan-v2",
        replaced_at=NOW + timedelta(minutes=4),
    )

    assert replacement.plan_revision == 1
    assert replacement.current_plan_digest == "plan-v2"
    assert replacement.approval is None
    assert replacement.verification_evidence == ()


def test_card_mapping_is_idempotent_and_rejects_conflicts() -> None:
    planned = make_planned()
    recorded = record_card(
        planned,
        stage=WorkflowStage.APPROVAL,
        task_id="t_approval",
        idempotency_key="wingstaff:workflow-1:0:approval",
        recorded_at=NOW + timedelta(minutes=3),
    )
    assert (
        record_card(
            recorded,
            stage=WorkflowStage.APPROVAL,
            task_id="t_approval",
            idempotency_key="wingstaff:workflow-1:0:approval",
            recorded_at=NOW + timedelta(minutes=3),
        )
        is recorded
    )
    with pytest.raises(PolicyViolationError, match="different Kanban card"):
        record_card(
            recorded,
            stage=WorkflowStage.APPROVAL,
            task_id="t_other",
            idempotency_key="wingstaff:workflow-1:0:approval",
            recorded_at=NOW + timedelta(minutes=4),
        )
    with pytest.raises(PolicyViolationError, match="idempotency key"):
        record_card(
            planned,
            stage=WorkflowStage.APPROVAL,
            task_id="t_bad",
            idempotency_key="wingstaff:workflow-1:approval",
            recorded_at=NOW + timedelta(minutes=3),
        )


def test_post_gate_facts_require_approval_and_owned_worktree() -> None:
    with pytest.raises(PolicyViolationError, match="approval"):
        record_worktree(
            make_planned(),
            worktree_path=WORKTREE,
            recorded_at=NOW + timedelta(minutes=3),
        )

    implementing = make_implementing()
    with pytest.raises(PolicyViolationError, match="implement artifact"):
        record_verification(
            with_activation(implementing, WorkflowStage.VERIFY),
            command="pytest",
            exit_code=0,
            output_reference="artifacts/pytest.txt",
            output_digest="verify-v1",
            recorded_at=NOW + timedelta(minutes=5),
        )


def test_verification_evidence_does_not_create_a_blocked_status() -> None:
    ledger = record_artifact(
        with_activation(make_implementing(), WorkflowStage.IMPLEMENT),
        stage=WorkflowStage.IMPLEMENT,
        path="artifacts/implementation.diff",
        digest="diff-v1",
        recorded_at=NOW + timedelta(minutes=5),
    )
    failed = record_verification(
        with_activation(ledger, WorkflowStage.VERIFY),
        command="pytest",
        exit_code=1,
        output_reference="artifacts/pytest-1.txt",
        output_digest="verify-failed",
        recorded_at=NOW + timedelta(minutes=6),
    )

    assert failed.verification_evidence[-1].exit_code == 1
    assert "status" not in failed.to_dict()
    repeated = record_verification(
        failed,
        command="pytest",
        exit_code=1,
        output_reference="artifacts/pytest-1.txt",
        output_digest="verify-failed",
        recorded_at=NOW + timedelta(minutes=7),
    )
    assert repeated is failed
    with pytest.raises(PolicyViolationError, match="successful verification"):
        record_artifact(
            with_activation(failed, WorkflowStage.REVIEW),
            stage=WorkflowStage.REVIEW,
            path="artifacts/review.md",
            digest="review-v1",
            recorded_at=NOW + timedelta(minutes=7),
        )

    passed = record_verification(
        failed,
        command="pytest",
        exit_code=0,
        output_reference="artifacts/pytest-2.txt",
        output_digest="verify-passed",
        recorded_at=NOW + timedelta(minutes=7),
    )
    reviewed = record_artifact(
        with_activation(passed, WorkflowStage.REVIEW),
        stage=WorkflowStage.REVIEW,
        path="artifacts/review.md",
        digest="review-v1",
        recorded_at=NOW + timedelta(minutes=8),
    )
    delivered = record_artifact(
        with_activation(reviewed, WorkflowStage.DELIVER),
        stage=WorkflowStage.DELIVER,
        path="artifacts/delivery.json",
        digest="delivery-v1",
        recorded_at=NOW + timedelta(minutes=9),
    )

    assert delivered.committed is delivered.pushed is False


def test_worktree_release_clears_only_ownership_facts() -> None:
    ledger = make_implementing()
    released = release_worktree(
        ledger,
        released_at=NOW + timedelta(minutes=5),
    )

    assert released.worktree_path is None
    assert released.worktree_owned is False
    assert released.approval == ledger.approval


def test_timestamps_are_timezone_aware_and_monotonic() -> None:
    with pytest.raises(PolicyViolationError, match="timezone-aware"):
        replace(make_ledger(), updated_at=datetime(2026, 7, 10, 12, 1))
    with pytest.raises(PolicyViolationError, match="before created_at"):
        replace(make_ledger(), updated_at=NOW - timedelta(seconds=1))
    with pytest.raises(PolicyViolationError, match="before updated_at"):
        record_artifact(
            with_activation(make_planned(), WorkflowStage.IMPLEMENT),
            stage=WorkflowStage.IMPLEMENT,
            path="artifacts/implementation.diff",
            digest="diff-v1",
            recorded_at=NOW,
        )


def test_deserialization_rejects_operational_status_payload() -> None:
    raw = make_ledger().to_dict()
    raw["status"] = "running"

    with pytest.raises(PolicyViolationError, match="unknown serialized"):
        WorkflowLedger.from_dict(raw)


@pytest.mark.parametrize(
    ("ledger", "message"),
    (
        (make_ledger(), "requires a finalized define"),
        (
            with_activation(
                make_ledger(),
                WorkflowStage.DEFINE,
                state=ActivationReferenceState.PENDING,
            ),
            "requires a finalized define",
        ),
        (
            with_activation(make_ledger(), WorkflowStage.DEFINE, blocked=True),
            "define skill activation is blocked",
        ),
    ),
)
def test_stage_artifact_rejects_missing_pending_or_blocked_activation(
    ledger: WorkflowLedger,
    message: str,
) -> None:
    with pytest.raises(PolicyViolationError, match=message):
        record_artifact(
            ledger,
            stage=WorkflowStage.DEFINE,
            path="artifacts/define.md",
            digest="define-v1",
            recorded_at=NOW + timedelta(minutes=1),
        )


def test_activation_manifest_is_strict_canonical_and_round_trips() -> None:
    manifest = activation_manifest()

    assert ActivationManifest.from_dict(manifest.to_dict()) == manifest
    assert manifest.canonical_bytes().startswith(b'{"decisions":')
    raw = manifest.to_dict()
    raw["unknown"] = True
    with pytest.raises(PolicyViolationError, match="fields are invalid"):
        ActivationManifest.from_dict(raw)
    with pytest.raises(PolicyViolationError, match="required skills"):
        replace(
            manifest.decisions[0],
            category=ActivationCategory.NOT_APPLICABLE,
            rank=None,
        )


def test_activation_reference_reservation_finalization_and_serialization() -> None:
    manifest = activation_manifest()
    pending = record_skill_activation(
        activation_ledger(),
        manifest=manifest,
        pack=activation_pack(),
        path="/tmp/activation-1.json",
        state=ActivationReferenceState.PENDING,
        recorded_at=NOW + timedelta(minutes=1),
    )

    assert pending.activation_for(WorkflowStage.DEFINE) is None
    assert pending.activation_manifests[-1].state is ActivationReferenceState.PENDING
    assert WorkflowLedger.from_dict(pending.to_dict()) == pending
    finalized = record_skill_activation(
        pending,
        manifest=manifest,
        pack=activation_pack(),
        path="/tmp/activation-1.json",
        state=ActivationReferenceState.FINALIZED,
        recorded_at=NOW + timedelta(minutes=2),
    )

    assert finalized.activation_for(WorkflowStage.DEFINE) == finalized.activation_manifests[-1]
    assert finalized.activation_manifests[-1].state is ActivationReferenceState.FINALIZED
    assert (
        record_skill_activation(
            finalized,
            manifest=manifest,
            pack=activation_pack(),
            path="/tmp/activation-1.json",
            state=ActivationReferenceState.FINALIZED,
            recorded_at=NOW + timedelta(minutes=3),
        )
        is finalized
    )


def test_activation_supersession_is_linear_and_blocked_is_preserved() -> None:
    first_manifest = activation_manifest()
    pending = record_skill_activation(
        activation_ledger(),
        manifest=first_manifest,
        pack=activation_pack(),
        path="/tmp/activation-1.json",
        state=ActivationReferenceState.PENDING,
        recorded_at=NOW + timedelta(minutes=1),
    )
    first = record_skill_activation(
        pending,
        manifest=first_manifest,
        pack=activation_pack(),
        path="/tmp/activation-1.json",
        state=ActivationReferenceState.FINALIZED,
        recorded_at=NOW + timedelta(minutes=2),
    )
    first_digest = first.activation_manifests[-1].digest
    blocked_manifest = activation_manifest(
        sequence=2,
        supersedes_digest=first_digest,
        category=ActivationCategory.BLOCKED,
    )
    blocked_pending = record_skill_activation(
        first,
        manifest=blocked_manifest,
        pack=activation_pack(),
        path="/tmp/activation-2.json",
        state=ActivationReferenceState.PENDING,
        recorded_at=NOW + timedelta(minutes=3),
    )
    blocked = record_skill_activation(
        blocked_pending,
        manifest=blocked_manifest,
        pack=activation_pack(),
        path="/tmp/activation-2.json",
        state=ActivationReferenceState.FINALIZED,
        recorded_at=NOW + timedelta(minutes=4),
    )

    assert [row.sequence for row in blocked.activation_manifests] == [1, 2]
    reference = blocked.activation_for(WorkflowStage.DEFINE)
    assert reference is not None and reference.blocked is True
    stale = replace(blocked_manifest, sequence=3, supersedes_digest="c" * 64)
    with pytest.raises(PolicyViolationError, match="latest effective digest"):
        record_skill_activation(
            blocked,
            manifest=stale,
            pack=activation_pack(),
            path="/tmp/activation-3.json",
            state=ActivationReferenceState.PENDING,
            recorded_at=NOW + timedelta(minutes=5),
        )


def test_activation_rejects_wrong_pack_contract_and_obsolete_revision() -> None:
    manifest = activation_manifest()
    wrong_digest = replace(
        manifest,
        decisions=(replace(manifest.decisions[0], skill_digest="c" * 64),),
    )
    with pytest.raises(PolicyViolationError, match="skill digest"):
        record_skill_activation(
            activation_ledger(),
            manifest=wrong_digest,
            pack=activation_pack(),
            path="/tmp/activation.json",
            state=ActivationReferenceState.PENDING,
            recorded_at=NOW + timedelta(minutes=1),
        )

    implementing = replace(activation_ledger(), plan_revision=1)
    with pytest.raises(PolicyViolationError, match="plan revision"):
        record_skill_activation(
            implementing,
            manifest=activation_manifest(stage=WorkflowStage.IMPLEMENT, revision=0),
            pack=activation_pack(),
            path="/tmp/activation.json",
            state=ActivationReferenceState.PENDING,
            recorded_at=NOW + timedelta(minutes=1),
        )