from __future__ import annotations

import hashlib
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from daidala.artifact_access import (
    ArtifactAccessError,
    ArtifactAccessService,
    ArtifactFailureReason,
    ArtifactId,
)
from daidala.errors import PolicyViolationError
from daidala.state import (
    ActivationManifestReference,
    ActivationReferenceState,
    ApprovalSummary,
    ArtifactReference,
    SkillDigest,
    StageProfile,
    VerificationEvidence,
    WorkflowConstraintsIdentity,
    WorkflowConstraintsReference,
    WorkflowStage,
)
from daidala.store import WorkflowStore
from daidala.workflow import new_workflow

NOW = datetime(2026, 7, 27, 8, 0, tzinfo=UTC)
SUMMARY_PAYLOAD = {
    "headline": "Implement exact ledger-bound artifact access.",
    "changes": ["Add an opaque artifact catalog.", "Verify bytes before reads."],
    "affected_areas": ["policy ledger", "artifact storage"],
    "risks": ["Artifact content may contain private data."],
    "verification": ["Run focused artifact-access tests."],
}


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _profiles() -> tuple[StageProfile, ...]:
    return tuple(
        StageProfile(stage=stage, profile="worker")
        for stage in WorkflowStage
        if stage is not WorkflowStage.APPROVAL
    )


def _write(root: Path, relative: str, content: bytes) -> tuple[str, str]:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return str(path.resolve()), _digest(content)


@pytest.fixture
def artifact_fixture(tmp_path: Path) -> tuple[WorkflowStore, ArtifactAccessService, str]:
    store = WorkflowStore(tmp_path / "data")
    workflow_id = "workflow-artifacts"
    artifact_root = store.data_root / "workflows" / workflow_id / "artifacts"
    definition_path, definition_digest = _write(
        artifact_root, "policy-0001/define.md", b"# Definition\n"
    )
    plan_bytes = b"# Plan\n\nImplement the resolver.\n"
    plan_path, plan_digest = _write(
        artifact_root, "policy-0001/plan-0000/plan.md", plan_bytes
    )
    verification_path, verification_digest = _write(
        artifact_root, "policy-0001/plan-0000/verification.txt", b"3 passed\n"
    )
    implementation_path, implementation_digest = _write(
        artifact_root, "policy-0001/plan-0000/implementation.diff", b"diff --git a/a b/a\n"
    )
    review_path, review_digest = _write(
        artifact_root, "policy-0001/plan-0000/review.md", b"# Review\n\nAccepted.\n"
    )
    delivery_path, delivery_digest = _write(
        artifact_root, "policy-0001/plan-0000/delivery.json", b'{"committed":false}\n'
    )
    constraint_path, constraint_digest = _write(
        artifact_root, "policy-0001/constraints.yaml", b"schema_version: 1\n"
    )
    activation_path, activation_digest = _write(
        artifact_root, "policy-0001/activation.json", b'{"schema":"activation"}\n'
    )
    summary = ApprovalSummary.from_dict(SUMMARY_PAYLOAD)
    ledger = new_workflow(
        workflow_id=workflow_id,
        board_slug="daidala-test",
        target_repository=str((tmp_path / "target").resolve()),
        baseline_commit="a" * 40,
        requested_goal="Test artifact access",
        pack_name="addyosmani",
        pack_source_revision="b" * 40,
        skill_digests=(SkillDigest(name="interview-me", digest="c" * 64),),
        stage_profiles=_profiles(),
        created_at=NOW,
    )
    ledger = replace(
        ledger,
        policy_revision=1,
        constraint_references=(
            WorkflowConstraintsReference(
                identity=WorkflowConstraintsIdentity(
                    policy_revision=1,
                    constraints_revision=1,
                    digest=constraint_digest,
                ),
                path=constraint_path,
                recorded_at=NOW + timedelta(minutes=1),
            ),
        ),
        artifacts=(
            ArtifactReference(
                stage=WorkflowStage.DEFINE,
                plan_revision=0,
                path=definition_path,
                digest=definition_digest,
                recorded_at=NOW + timedelta(minutes=2),
                policy_revision=1,
            ),
            ArtifactReference(
                stage=WorkflowStage.PLAN,
                plan_revision=0,
                path=plan_path,
                digest=plan_digest,
                recorded_at=NOW + timedelta(minutes=3),
                policy_revision=1,
                approval_summary=summary,
                approval_summary_digest=summary.digest_for(plan_digest),
            ),
            ArtifactReference(
                stage=WorkflowStage.IMPLEMENT,
                plan_revision=0,
                path=implementation_path,
                digest=implementation_digest,
                recorded_at=NOW + timedelta(minutes=5),
                policy_revision=1,
            ),
            ArtifactReference(
                stage=WorkflowStage.REVIEW,
                plan_revision=0,
                path=review_path,
                digest=review_digest,
                recorded_at=NOW + timedelta(minutes=6),
                policy_revision=1,
            ),
            ArtifactReference(
                stage=WorkflowStage.DELIVER,
                plan_revision=0,
                path=delivery_path,
                digest=delivery_digest,
                recorded_at=NOW + timedelta(minutes=7),
                policy_revision=1,
            ),
        ),
        verification_evidence=(
            VerificationEvidence(
                command="pytest -q",
                exit_code=0,
                output_reference=verification_path,
                output_digest=verification_digest,
                plan_revision=0,
                recorded_at=NOW + timedelta(minutes=4),
            ),
        ),
        activation_manifests=(
            ActivationManifestReference(
                stage=WorkflowStage.PLAN,
                plan_revision=0,
                sequence=1,
                path=activation_path,
                digest=activation_digest,
                state=ActivationReferenceState.FINALIZED,
                blocked=False,
                supersedes_digest=None,
                policy_revision=1,
                constraints_digest=constraint_digest,
            ),
        ),
        updated_at=NOW + timedelta(minutes=7),
    )
    store.create(ledger)
    return store, ArtifactAccessService(store), workflow_id


def test_summary_is_strict_bounded_and_source_bound() -> None:
    summary = ApprovalSummary.from_dict(SUMMARY_PAYLOAD)
    assert ApprovalSummary.from_dict(summary.to_dict()) == summary
    assert summary.canonical_bytes() == ApprovalSummary.from_dict(
        SUMMARY_PAYLOAD
    ).canonical_bytes()
    assert summary.digest_for("a" * 64) != summary.digest_for("b" * 64)

    with pytest.raises(PolicyViolationError, match="approval summary fields"):
        ApprovalSummary.from_dict({**SUMMARY_PAYLOAD, "extra": "no"})
    with pytest.raises(PolicyViolationError, match="headline"):
        ApprovalSummary.from_dict({**SUMMARY_PAYLOAD, "headline": " padded "})
    with pytest.raises(PolicyViolationError, match="UTF-8 bytes"):
        ApprovalSummary.from_dict({**SUMMARY_PAYLOAD, "headline": "é" * 101})
    with pytest.raises(PolicyViolationError, match="changes"):
        ApprovalSummary.from_dict({**SUMMARY_PAYLOAD, "changes": []})
    with pytest.raises(PolicyViolationError, match="must be an array"):
        ApprovalSummary.from_dict({**SUMMARY_PAYLOAD, "changes": "not-an-array"})
    bounded = ApprovalSummary.from_dict(
        {
            **SUMMARY_PAYLOAD,
            "headline": "h" * 200,
            "changes": [f"change-{index}" for index in range(12)],
            "verification": [f"check-{index}" for index in range(12)],
        }
    )
    assert len(bounded.changes) == len(bounded.verification) == 12


def test_artifact_id_is_frozen_opaque_and_deterministic() -> None:
    value = "a" * 64
    assert str(ArtifactId(value)) == value
    assert ArtifactId(value) == ArtifactId(value)
    with pytest.raises(ArtifactAccessError, match="opaque SHA-256"):
        ArtifactId("latest")


def test_catalog_uses_opaque_ids_and_lists_only_ledger_references(
    artifact_fixture: tuple[WorkflowStore, ArtifactAccessService, str],
) -> None:
    store, access, workflow_id = artifact_fixture
    root = store.data_root / "workflows" / workflow_id / "artifacts"
    _write(root, "policy-0001/plan-0000/unreferenced.txt", b"not evidence\n")

    entries = access.list(workflow_id)
    assert {entry.kind for entry in entries} == {"stage", "verification"}
    assert {entry.stage for entry in entries} == {
        "define", "plan", "implement", "verify", "review", "deliver",
    }
    assert all(len(entry.artifact_id) == 64 for entry in entries)
    assert all("path" not in entry.to_dict() for entry in entries)
    assert all("unreferenced" not in str(entry.to_dict()) for entry in entries)

    explicit = access.list(workflow_id, kinds={"constraint", "activation"})
    assert {entry.kind for entry in explicit} == {"constraint", "activation"}


def test_current_plan_returns_exact_text_and_bound_summary_without_mutation(
    artifact_fixture: tuple[WorkflowStore, ArtifactAccessService, str],
) -> None:
    store, access, workflow_id = artifact_fixture
    before = store.get_with_token(workflow_id)

    current = access.current_plan(workflow_id)

    assert current.content.startswith("# Plan")
    assert current.approval_summary == ApprovalSummary.from_dict(SUMMARY_PAYLOAD)
    assert current.approval_summary_digest == current.approval_summary.digest_for(
        current.plan_digest
    )
    assert store.get_with_token(workflow_id) == before


def test_artifact_reads_accept_only_the_matching_captured_ledger_snapshot(
    artifact_fixture: tuple[WorkflowStore, ArtifactAccessService, str],
) -> None:
    store, access, workflow_id = artifact_fixture
    captured_ledger = store.get(workflow_id)

    entries = access.list(workflow_id, kinds={"stage"}, ledger=captured_ledger)
    plan_entry = next(entry for entry in entries if entry.stage == "plan")
    text = access.read_text(
        workflow_id, plan_entry.artifact_id, ledger=captured_ledger
    )
    current = access.current_plan(workflow_id, ledger=captured_ledger)

    assert text.content == current.content
    mismatched = replace(captured_ledger, workflow_id="different-workflow")
    with pytest.raises(ArtifactAccessError, match="snapshot workflow identity"):
        access.list(workflow_id, ledger=mismatched)


def test_resolver_rejects_forged_corrupt_binary_oversized_and_cross_workflow_ids(
    artifact_fixture: tuple[WorkflowStore, ArtifactAccessService, str],
) -> None:
    store, access, workflow_id = artifact_fixture
    plan = next(entry for entry in access.list(workflow_id) if entry.stage == "plan")

    with pytest.raises(ArtifactAccessError, match="artifact ID") as forged_error:
        access.read_text(workflow_id, "0" * 64)
    assert forged_error.value.reason is ArtifactFailureReason.ARTIFACT_NOT_FOUND
    with pytest.raises(ArtifactAccessError, match="workflow"):
        access.read_text("other-workflow", plan.artifact_id)

    ledger = store.get(workflow_id)
    plan_reference = ledger.artifact_for(WorkflowStage.PLAN)
    assert plan_reference is not None
    Path(plan_reference.path).write_text("changed\n", encoding="utf-8")
    with pytest.raises(ArtifactAccessError, match="digest"):
        access.read_text(workflow_id, plan.artifact_id)

    Path(plan_reference.path).write_bytes(b"binary\x00content")
    forged = replace(
        plan_reference,
        digest=_digest(b"binary\x00content"),
        approval_summary_digest=plan_reference.approval_summary.digest_for(
            _digest(b"binary\x00content")
        )
        if plan_reference.approval_summary
        else None,
    )
    store.update(
        replace(
            ledger,
            artifacts=tuple(
                forged if row is plan_reference else row for row in ledger.artifacts
            ),
            updated_at=ledger.updated_at + timedelta(minutes=1),
        ),
        expected_updated_at=ledger.updated_at.isoformat(),
    )
    binary_id = next(
        entry.artifact_id for entry in access.list(workflow_id) if entry.stage == "plan"
    )
    with pytest.raises(ArtifactAccessError, match="binary"):
        access.read_text(workflow_id, binary_id)

    Path(forged.path).write_bytes(b"x" * (1024 * 1024 + 1))
    oversized_ledger = store.get(workflow_id)
    oversized_reference = oversized_ledger.artifact_for(WorkflowStage.PLAN)
    assert oversized_reference is not None
    oversized_digest = _digest(Path(forged.path).read_bytes())
    oversized_reference = replace(
        oversized_reference,
        digest=oversized_digest,
        approval_summary_digest=oversized_reference.approval_summary.digest_for(
            oversized_digest
        )
        if oversized_reference.approval_summary
        else None,
    )
    store.update(
        replace(
            oversized_ledger,
            artifacts=tuple(
                oversized_reference if row.stage is WorkflowStage.PLAN else row
                for row in oversized_ledger.artifacts
            ),
            updated_at=oversized_ledger.updated_at + timedelta(minutes=1),
        ),
        expected_updated_at=oversized_ledger.updated_at.isoformat(),
    )
    oversized_id = next(
        entry.artifact_id for entry in access.list(workflow_id) if entry.stage == "plan"
    )
    with pytest.raises(ArtifactAccessError, match="1 MiB"):
        access.read_text(workflow_id, oversized_id)


def test_resolver_rejects_path_escape_and_symlink(
    artifact_fixture: tuple[WorkflowStore, ArtifactAccessService, str], tmp_path: Path
) -> None:
    store, access, workflow_id = artifact_fixture
    ledger = store.get(workflow_id)
    plan = ledger.artifact_for(WorkflowStage.PLAN)
    assert plan is not None
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n", encoding="utf-8")
    escaped = replace(
        plan,
        path=str(outside.resolve()),
        digest=_digest(outside.read_bytes()),
        approval_summary_digest=plan.approval_summary.digest_for(_digest(outside.read_bytes()))
        if plan.approval_summary
        else None,
    )
    escaped_ledger = replace(
        ledger,
        artifacts=tuple(escaped if row is plan else row for row in ledger.artifacts),
        updated_at=ledger.updated_at + timedelta(minutes=1),
    )
    store.update(escaped_ledger, expected_updated_at=ledger.updated_at.isoformat())
    escaped_id = next(
        entry.artifact_id for entry in access.list(workflow_id) if entry.stage == "plan"
    )
    with pytest.raises(ArtifactAccessError, match="workflow artifact root"):
        access.read_text(workflow_id, escaped_id)

    current = store.get(workflow_id)
    escaped = current.artifact_for(WorkflowStage.PLAN)
    assert escaped is not None
    symlink = (
        store.data_root
        / "workflows"
        / workflow_id
        / "artifacts"
        / "policy-0001"
        / "plan-0000"
        / "symlink.md"
    )
    symlink.symlink_to(outside)
    linked = replace(escaped, path=str(symlink.absolute()))
    store.update(
        replace(
            current,
            artifacts=tuple(
                linked if row.stage is WorkflowStage.PLAN else row
                for row in current.artifacts
            ),
            updated_at=current.updated_at + timedelta(minutes=1),
        ),
        expected_updated_at=current.updated_at.isoformat(),
    )
    linked_id = next(
        entry.artifact_id for entry in access.list(workflow_id) if entry.stage == "plan"
    )
    with pytest.raises(ArtifactAccessError, match="symlink"):
        access.read_text(workflow_id, linked_id)


def test_export_is_digest_verified_private_and_collision_safe(
    artifact_fixture: tuple[WorkflowStore, ArtifactAccessService, str], tmp_path: Path
) -> None:
    store, access, workflow_id = artifact_fixture
    before = store.get_with_token(workflow_id)
    plan = next(entry for entry in access.list(workflow_id) if entry.stage == "plan")
    output = tmp_path / "exported-plan.md"

    result = access.export(workflow_id, plan.artifact_id, output)

    assert result.output == str(output)
    assert _digest(output.read_bytes()) == plan.digest
    assert os.stat(output).st_mode & 0o777 == 0o600
    with pytest.raises(ArtifactAccessError, match="already exists"):
        access.export(workflow_id, plan.artifact_id, output)
    access.export(workflow_id, plan.artifact_id, output, overwrite=True)
    linked_output = tmp_path / "linked-output.md"
    linked_output.symlink_to(output)
    with pytest.raises(ArtifactAccessError, match="symlink"):
        access.export(
            workflow_id, plan.artifact_id, linked_output, overwrite=True
        )
    assert store.get_with_token(workflow_id) == before


def test_legacy_summaryless_plan_is_readable_but_not_approvable(
    artifact_fixture: tuple[WorkflowStore, ArtifactAccessService, str],
) -> None:
    store, access, workflow_id = artifact_fixture
    ledger = store.get(workflow_id)
    plan = ledger.artifact_for(WorkflowStage.PLAN)
    assert plan is not None
    legacy = replace(plan, approval_summary=None, approval_summary_digest=None)
    store.update(
        replace(
            ledger,
            artifacts=tuple(legacy if row is plan else row for row in ledger.artifacts),
            updated_at=ledger.updated_at + timedelta(minutes=1),
        ),
        expected_updated_at=ledger.updated_at.isoformat(),
    )
    entry = next(entry for entry in access.list(workflow_id) if entry.stage == "plan")
    assert access.read_text(workflow_id, entry.artifact_id).content.startswith("# Plan")
    with pytest.raises(ArtifactAccessError, match="not approvable") as summary_error:
        access.current_plan(workflow_id)
    assert summary_error.value.reason is ArtifactFailureReason.MISSING_SUMMARY
