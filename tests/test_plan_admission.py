from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import FrozenInstanceError, dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from daidala.errors import PolicyViolationError
from daidala.execution import ExecutionError, ExecutionWorkspace
from daidala.plan_admission import (
    admit_plan_source,
    parse_plan_document,
    parse_plan_inventory,
    select_pending_phase,
    validate_plan_checkpoint,
)
from daidala.state import (
    ActivationManifestReference,
    ActivationReferenceState,
    ApprovalSummary,
    ArtifactReference,
    PlanSourcePacket,
    ReviewDisposition,
    ReviewDispositionAction,
    ReviewOutcome,
    ReviewRecord,
    SkillDigest,
    StageProfile,
    VerificationEvidence,
    WorkflowLedger,
    WorkflowStage,
)
from daidala.store import WorkflowStore
from daidala.workflow import new_workflow, record_plan_source

DONE_DIGEST = "a" * 64


def plan_document(
    *,
    plan_id: str,
    slot: str,
    status: str = "pending",
    dependencies: str = "none",
    phases: tuple[tuple[str, str], ...] = (("Admit the committed source", "pending"),),
) -> str:
    rows = "\n".join(
        f"| {number} | {title} | {phase_status} | `pytest -q tests/test_{number}.py` exits 0 |"
        for number, (title, phase_status) in enumerate(phases)
    )
    sections = "\n".join(
        "\n".join(
            (
                f"## Phase {number} — {title}",
                "",
                "Goal: keep the admission fixture deterministic.",
                "",
                f"Verification gate: `pytest -q tests/test_{number}.py` exits 0",
            )
        )
        for number, (title, _phase_status) in enumerate(phases)
    )
    return "\n".join(
        (
            f"# {plan_id}",
            "",
            f"**Plan ID:** {plan_id}",
            "",
            f"**Execution slot:** {slot}",
            "",
            "**Created:** 2026-08-10",
            "",
            f"**Depends on:** {dependencies}",
            "",
            f"**Status:** {status}",
            "",
            "## Phase table",
            "",
            "| # | Phase | Status | Verification gate |",
            "|---|---|---|---|",
            rows,
            "",
            sections,
            "",
        )
    )


def git(repository: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def commit(repository: Path, message: str) -> str:
    git(repository, "add", ".")
    subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "-c",
            "user.name=Daidala Tests",
            "-c",
            "user.email=daidala@example.invalid",
            "commit",
            "-qm",
            message,
        ],
        check=True,
    )
    return git(repository, "rev-parse", "HEAD")


def repository_with_plans(tmp_path: Path) -> tuple[Path, str]:
    repository = tmp_path / "target"
    plans = repository / "docs" / "plans"
    plans.mkdir(parents=True)
    (plans / "P0100-complete.md").write_text(
        plan_document(
            plan_id="completed-policy",
            slot="P0100",
            status="complete",
            phases=(("Record completed policy", f"done (daidala:workflow-1:{DONE_DIGEST})"),),
        ),
        encoding="utf-8",
    )
    (plans / "P0200-active.md").write_text(
        plan_document(
            plan_id="active-policy",
            slot="P0200",
            dependencies="completed-policy",
        ),
        encoding="utf-8",
    )
    (plans / "P0099-legacy.md").write_text(
        "\n".join(
            (
                "# Legacy plan",
                "",
                "**Plan ID:** legacy-plan",
                "",
                "**Execution slot:** P0099",
                "",
                "**Status:** complete — historic format",
                "",
                "No new-shape phase metadata exists here.",
                "",
            )
        ),
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    return repository, commit(repository, "plan fixture")


NOW = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)


@dataclass(frozen=True)
class CheckpointFixture:
    repository: Path
    revision: str
    packet: PlanSourcePacket
    ledger: WorkflowLedger
    workspace: ExecutionWorkspace
    store: WorkflowStore
    delivered_feature: bytes


def git_bytes(repository: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        capture_output=True,
    ).stdout


def checkpoint_fixture(tmp_path: Path, *, binary_diff: bool = False) -> CheckpointFixture:
    repository, _ = repository_with_plans(tmp_path)
    plan_path = repository / "docs" / "plans" / "P0200-active.md"
    plan_path.write_text(
        plan_document(
            plan_id="active-policy",
            slot="P0200",
            dependencies="completed-policy",
            phases=(("Implement fixture", "pending"), ("Verify fixture", "pending")),
        ),
        encoding="utf-8",
    )
    (repository / "feature.txt").write_bytes(b"before\n")
    revision = commit(repository, "checkpoint baseline")
    packet = admit_plan_source(
        repository=repository,
        plan_path="docs/plans/P0200-active.md",
        source_revision=revision,
        baseline_commit=revision,
        phase_number=0,
    )
    plan_markdown = git_bytes(
        repository,
        "show",
        f"{revision}:docs/plans/P0200-active.md",
    ).decode("utf-8")
    workspace = ExecutionWorkspace(tmp_path / "daidala-data")
    stored = workspace.write_plan_source(
        "workflow-0",
        packet=packet,
        plan_markdown=plan_markdown,
        policy_revision=0,
        plan_revision=0,
    )
    assert workspace.write_plan_source(
        "workflow-0",
        packet=packet,
        plan_markdown=plan_markdown,
        policy_revision=0,
        plan_revision=0,
    ) == stored
    assert workspace.read_artifact_bytes(
        "workflow-0",
        stored.plan.path,
        expected_digest=packet.reference.plan_digest,
    ) == plan_markdown.encode("utf-8")
    assert workspace.read_artifact_bytes(
        "workflow-0",
        stored.packet.path,
        expected_digest=packet.digest,
    ) == packet.canonical_bytes()
    assert json.loads(
        workspace.read_artifact_bytes(
            "workflow-0",
            stored.packet.path,
            expected_digest=packet.digest,
        )
    ) == packet.to_dict()

    plan_relative = workspace.stage_artifact_relative_path(
        stage=WorkflowStage.PLAN,
        policy_revision=0,
        plan_revision=0,
        filename="plan.md",
    )
    workspace.write_artifact("conflicting-source", plan_relative, "conflict\n")
    with pytest.raises(ExecutionError, match="content conflicts"):
        workspace.write_plan_source(
            "conflicting-source",
            packet=packet,
            plan_markdown=plan_markdown,
            policy_revision=0,
            plan_revision=0,
        )

    delivered_feature = b"\x00binary checkpoint\xff" if binary_diff else b"after\n"
    (repository / "feature.txt").write_bytes(delivered_feature)
    implementation_diff = git_bytes(
        repository,
        "diff",
        "--binary",
        "--no-ext-diff",
        "HEAD",
    )
    git(repository, "checkout", "--", "feature.txt")
    implementation_path = workspace.stage_artifact_relative_path(
        stage=WorkflowStage.IMPLEMENT,
        policy_revision=0,
        plan_revision=0,
        filename="implementation.patch",
    )
    implementation = workspace.write_artifact(
        "workflow-0",
        implementation_path,
        implementation_diff.decode("utf-8"),
    )
    verification = VerificationEvidence(
        command="pytest -q",
        exit_code=0,
        output_reference="verification.log",
        output_digest="b" * 64,
        plan_revision=0,
        recorded_at=NOW,
    )
    delivery_payload = {
        "workflow_id": "workflow-0",
        "baseline_commit": revision,
        "changed_paths": ["feature.txt"],
        "verification": [verification.to_dict()],
        "committed": False,
        "pushed": False,
    }
    delivery_path = workspace.stage_artifact_relative_path(
        stage=WorkflowStage.DELIVER,
        policy_revision=0,
        plan_revision=0,
        filename="delivery.json",
    )
    delivery = workspace.write_json_artifact("workflow-0", delivery_path, delivery_payload)
    ledger = record_plan_source(
        new_workflow(
            workflow_id="workflow-0",
            board_slug="daidala-test",
            target_repository=str(repository.resolve()),
            baseline_commit=revision,
            requested_goal="Implement the admitted fixture phase.",
            pack_name="fixture-pack",
            pack_source_revision="a" * 40,
            skill_digests=(SkillDigest(name="fixture-skill", digest="fixture-digest"),),
            stage_profiles=tuple(
                StageProfile(stage=stage, profile=f"{stage.value}-profile")
                for stage in WorkflowStage
                if stage is not WorkflowStage.APPROVAL
            ),
            created_at=NOW,
        ),
        packet=packet,
        recorded_at=NOW,
    )
    summary = ApprovalSummary(
        headline="Accept the fixture delivery.",
        changes=("Update feature.txt.",),
        affected_areas=("fixture",),
        risks=(),
        verification=("pytest -q",),
    )
    activation_digest = hashlib.sha256(b"review activation").hexdigest()
    review = ReviewRecord(
        workflow_id=ledger.workflow_id,
        plan_digest=stored.plan.digest,
        plan_revision=0,
        policy_revision=0,
        constraints_revision=None,
        constraints_digest=None,
        implementation_digest=implementation.digest,
        verification_digests=(verification.output_digest,),
        activation_digest=activation_digest,
        outcome=ReviewOutcome.ACCEPTED,
        summary=summary,
        summary_digest=summary.digest_for(implementation.digest),
        findings=(),
        recorded_at=NOW + timedelta(minutes=1),
    )
    disposition = ReviewDisposition(
        review_digest=review.digest,
        implementation_digest=review.implementation_digest,
        verification_digests=review.verification_digests,
        plan_digest=review.plan_digest,
        plan_revision=review.plan_revision,
        policy_revision=review.policy_revision,
        constraints_revision=review.constraints_revision,
        constraints_digest=review.constraints_digest,
        action=ReviewDispositionAction.ACCEPT_DELIVERY,
        actor="fixture operator",
        rationale="Accept the exact fixture evidence.",
        decided_at=NOW + timedelta(minutes=2),
    )
    ledger = replace(
        ledger,
        artifacts=(
            ArtifactReference(
                stage=WorkflowStage.PLAN,
                plan_revision=0,
                path=stored.plan.path,
                digest=stored.plan.digest,
                recorded_at=NOW,
            ),
            ArtifactReference(
                stage=WorkflowStage.IMPLEMENT,
                plan_revision=0,
                path=implementation.path,
                digest=implementation.digest,
                recorded_at=NOW,
            ),
            ArtifactReference(
                stage=WorkflowStage.DELIVER,
                plan_revision=0,
                path=delivery.path,
                digest=delivery.digest,
                recorded_at=NOW + timedelta(minutes=2),
            ),
        ),
        verification_evidence=(verification,),
        review=review,
        review_disposition=disposition,
        activation_manifests=(
            ActivationManifestReference(
                stage=WorkflowStage.REVIEW,
                plan_revision=0,
                sequence=1,
                path="/tmp/review-activation.json",
                digest=activation_digest,
                state=ActivationReferenceState.FINALIZED,
                blocked=False,
                supersedes_digest=None,
            ),
        ),
        updated_at=NOW + timedelta(minutes=2),
    )
    store = WorkflowStore(tmp_path / "ledger-data")
    assert store.create(ledger) == ledger
    assert WorkflowLedger.from_dict(ledger.to_dict()) == ledger
    return CheckpointFixture(
        repository,
        revision,
        packet,
        ledger,
        workspace,
        store,
        delivered_feature,
    )


def checkpoint_commit(
    fixture: CheckpointFixture,
    *,
    done_status: str | None = None,
    extra_path: bool = False,
) -> str:
    source_path = fixture.repository / fixture.packet.reference.plan_path
    source = source_path.read_text(encoding="utf-8")
    expected = "| 0 | Implement fixture | pending | `pytest -q tests/test_0.py` exits 0 |"
    delivery = fixture.ledger.artifact_for(WorkflowStage.DELIVER)
    assert delivery is not None
    status = done_status or (
        f"done (daidala:{fixture.ledger.workflow_id}:"
        f"{delivery.digest})"
    )
    assert expected in source
    checkpoint = expected.replace("pending", status)
    source_path.write_text(source.replace(expected, checkpoint), encoding="utf-8")
    (fixture.repository / "feature.txt").write_bytes(fixture.delivered_feature)
    if extra_path:
        (fixture.repository / "unexpected.txt").write_text("unexpected\n", encoding="utf-8")
    return commit(fixture.repository, "checkpoint phase zero")


def checkpoint_packet(fixture: CheckpointFixture, revision: str) -> PlanSourcePacket:
    return admit_plan_source(
        repository=fixture.repository,
        plan_path=fixture.packet.reference.plan_path,
        source_revision=revision,
        baseline_commit=revision,
        phase_number=1,
        predecessor_workflow_id=fixture.ledger.workflow_id,
    )


def test_admits_one_exact_committed_pending_phase(tmp_path: Path) -> None:
    repository, revision = repository_with_plans(tmp_path)

    packet = admit_plan_source(
        repository=repository,
        plan_path="docs/plans/P0200-active.md",
        source_revision=revision,
        baseline_commit=revision,
        phase_number=0,
    )

    assert packet.plan_id == "active-policy"
    assert packet.execution_slot == "P0200"
    assert packet.reference.source_revision == revision
    assert packet.reference.baseline_commit == revision
    assert packet.reference.plan_path == "docs/plans/P0200-active.md"
    assert len(packet.reference.plan_blob_id) == 40
    assert len(packet.reference.plan_digest) == len(packet.digest) == 64
    assert PlanSourcePacket.from_dict(packet.to_dict()) == packet
    assert packet.canonical_bytes().startswith(b'{"direct_dependencies":[')
    with pytest.raises(FrozenInstanceError):
        packet.phase_title = "changed"  # type: ignore[misc]
    assert git(repository, "status", "--porcelain") == ""


def test_admission_uses_the_injected_git_boundary(tmp_path: Path) -> None:
    repository, revision = repository_with_plans(tmp_path)
    calls: list[tuple[str, ...]] = []

    def runner(root: Path, args: tuple[str, ...]) -> bytes:
        calls.append(args)
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
        ).stdout

    packet = admit_plan_source(
        repository=repository,
        plan_path="docs/plans/P0200-active.md",
        source_revision=revision,
        baseline_commit=revision,
        phase_number=0,
        git_runner=runner,
    )

    assert packet.reference.plan_blob_id
    assert ("rev-parse", "--show-toplevel") in calls
    assert ("status", "--porcelain=v1", "--untracked-files=normal") in calls
    assert any(call[:2] == ("cat-file", "-p") for call in calls)


def test_packet_rejects_unknown_fields_and_stale_reference_identity(tmp_path: Path) -> None:
    repository, revision = repository_with_plans(tmp_path)
    packet = admit_plan_source(
        repository=repository,
        plan_path="docs/plans/P0200-active.md",
        source_revision=revision,
        baseline_commit=revision,
        phase_number=0,
    )

    unknown = packet.to_dict() | {"unexpected": "field"}
    with pytest.raises(PolicyViolationError, match="unknown"):
        PlanSourcePacket.from_dict(unknown)

    stale = packet.to_dict()
    stale["reference"]["baseline_commit"] = "b" * 40
    with pytest.raises(PolicyViolationError, match="baseline"):
        PlanSourcePacket.from_dict(stale)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (
            plan_document(plan_id="policy", slot="P0200").replace(
                "**Plan ID:** policy",
                "**Plan ID:** policy\n**Plan ID:** duplicate-policy",
            ),
            "duplicate",
        ),
        (
            plan_document(plan_id="policy", slot="P0200").replace(
                "## Phase 0 — Admit the committed source",
                "## Phase 0 — Different heading",
            ),
            "does not match",
        ),
        (
            plan_document(
                plan_id="policy",
                slot="P0200",
                phases=(
                    ("Completed", "done ()"),
                    ("Pending", "pending"),
                ),
            ),
            "status",
        ),
        (
            plan_document(plan_id="policy", slot="P0200").replace(
                "`pytest -q tests/test_0.py` exits 0",
                "a prose test gate",
                1,
            ),
            "executable command",
        ),
        (
            plan_document(plan_id="policy", slot="P0200", status="complete"),
            "complete plan documents",
        ),
    ],
)
def test_plan_parser_rejects_ambiguous_or_malformed_markdown(
    content: str, message: str
) -> None:
    with pytest.raises(PolicyViolationError, match=message):
        parse_plan_document("docs/plans/P0200-policy.md", content)


def test_inventory_rejects_duplicate_unknown_and_cyclic_dependencies() -> None:
    first = plan_document(plan_id="first", slot="P0100", dependencies="second")
    second = plan_document(plan_id="second", slot="P0200", dependencies="first")
    with pytest.raises(PolicyViolationError, match="cycle"):
        parse_plan_inventory(
            {
                "docs/plans/P0100-first.md": first,
                "docs/plans/P0200-second.md": second,
            }
        )

    with pytest.raises(PolicyViolationError, match="unknown"):
        parse_plan_inventory(
            {
                "docs/plans/P0100-first.md": plan_document(
                    plan_id="first", slot="P0100", dependencies="missing"
                )
            }
        )

    with pytest.raises(PolicyViolationError, match="duplicate"):
        parse_plan_inventory(
            {
                "docs/plans/P0100-first.md": plan_document(plan_id="same", slot="P0100"),
                "docs/plans/P0200-second.md": plan_document(plan_id="same", slot="P0200"),
            }
        )


def test_pending_selection_requires_complete_predecessors_and_pending_successors() -> None:
    plan = parse_plan_document(
        "docs/plans/P0200-policy.md",
        plan_document(
            plan_id="policy",
            slot="P0200",
            phases=(
                ("Completed", f"done (daidala:workflow-1:{DONE_DIGEST})"),
                ("Pending", "pending"),
                ("Later", "pending"),
            ),
        ),
    )

    assert select_pending_phase(plan, 1).title == "Pending"
    with pytest.raises(PolicyViolationError, match="must be pending"):
        select_pending_phase(plan, 0)
    with pytest.raises(PolicyViolationError, match="does not exist"):
        select_pending_phase(plan, 3)


def test_admission_rejects_dirty_drifted_and_traversal_inputs(tmp_path: Path) -> None:
    repository, revision = repository_with_plans(tmp_path)
    selected = repository / "docs" / "plans" / "P0200-active.md"
    selected.write_text("working-tree rewrite\n", encoding="utf-8")

    with pytest.raises(PolicyViolationError, match="clean"):
        admit_plan_source(
            repository=repository,
            plan_path="docs/plans/P0200-active.md",
            source_revision=revision,
            baseline_commit=revision,
            phase_number=0,
        )
    with pytest.raises(PolicyViolationError, match="normalized"):
        admit_plan_source(
            repository=repository,
            plan_path="../P0200-active.md",
            source_revision=revision,
            baseline_commit=revision,
            phase_number=0,
        )
    with pytest.raises(PolicyViolationError, match="full 40-character"):
        admit_plan_source(
            repository=repository,
            plan_path="docs/plans/P0200-active.md",
            source_revision=revision[:12],
            baseline_commit=revision[:12],
            phase_number=0,
        )


def test_admission_rejects_symlink_and_non_utf8_plan_objects(tmp_path: Path) -> None:
    repository, _revision = repository_with_plans(tmp_path)
    plans = repository / "docs" / "plans"
    (plans / "P0200-active.md").unlink()
    (plans / "P0200-active.md").symlink_to("P0100-complete.md")
    revision = commit(repository, "symlink plan")

    with pytest.raises(PolicyViolationError, match="regular non-symlinked"):
        admit_plan_source(
            repository=repository,
            plan_path="docs/plans/P0200-active.md",
            source_revision=revision,
            baseline_commit=revision,
            phase_number=0,
        )

    (plans / "P0200-active.md").unlink()
    (plans / "P0200-active.md").write_bytes(b"\xff\xfe")
    revision = commit(repository, "binary plan")
    with pytest.raises(PolicyViolationError, match="not UTF-8"):
        admit_plan_source(
            repository=repository,
            plan_path="docs/plans/P0200-active.md",
            source_revision=revision,
            baseline_commit=revision,
            phase_number=0,
        )


def test_checkpoint_validation_accepts_exact_delivered_direct_child(tmp_path: Path) -> None:
    fixture = checkpoint_fixture(tmp_path)

    assert validate_plan_checkpoint(
        packet=fixture.packet,
        store=WorkflowStore(tmp_path / "phase-zero"),
        workspace=fixture.workspace,
    ) is None
    revision = checkpoint_commit(fixture)
    packet = checkpoint_packet(fixture, revision)

    assert validate_plan_checkpoint(
        packet=packet,
        store=fixture.store,
        workspace=fixture.workspace,
    ) == fixture.ledger
    assert validate_plan_checkpoint(
        packet=packet,
        store=fixture.store,
        workspace=fixture.workspace,
    ) == fixture.ledger
    assert git(fixture.repository, "status", "--porcelain") == ""


def test_checkpoint_validation_matches_binary_delivery_diff(tmp_path: Path) -> None:
    fixture = checkpoint_fixture(tmp_path, binary_diff=True)
    packet = checkpoint_packet(fixture, checkpoint_commit(fixture))

    assert validate_plan_checkpoint(
        packet=packet,
        store=fixture.store,
        workspace=fixture.workspace,
    ) == fixture.ledger


def test_checkpoint_validation_fails_closed_for_lineage_delta_and_evidence(
    tmp_path: Path,
) -> None:
    fixture = checkpoint_fixture(tmp_path)
    revision = checkpoint_commit(fixture)
    valid_packet = checkpoint_packet(fixture, revision)
    with pytest.raises(PolicyViolationError, match="unambiguous predecessor"):
        validate_plan_checkpoint(
            packet=valid_packet,
            store=WorkflowStore(tmp_path / "no-predecessor"),
            workspace=fixture.workspace,
        )
    with pytest.raises(PolicyViolationError, match="workflow ID does not match"):
        validate_plan_checkpoint(
            packet=replace(valid_packet, predecessor_workflow_id="wrong-workflow"),
            store=fixture.store,
            workspace=fixture.workspace,
        )
    missing_evidence = WorkflowStore(tmp_path / "missing-evidence")
    missing_evidence.create(replace(fixture.ledger, review_disposition=None))
    with pytest.raises(PolicyViolationError, match="accepted review"):
        validate_plan_checkpoint(
            packet=valid_packet,
            store=missing_evidence,
            workspace=fixture.workspace,
        )
    missing_delivery = WorkflowStore(tmp_path / "missing-delivery")
    missing_delivery.create(
        replace(
            fixture.ledger,
            artifacts=tuple(
                artifact
                for artifact in fixture.ledger.artifacts
                if artifact.stage is not WorkflowStage.DELIVER
            ),
        )
    )
    with pytest.raises(PolicyViolationError, match="immutable delivery evidence"):
        validate_plan_checkpoint(
            packet=valid_packet,
            store=missing_delivery,
            workspace=fixture.workspace,
        )

    subprocess.run(
        [
            "git",
            "-C",
            str(fixture.repository),
            "-c",
            "user.name=Daidala Tests",
            "-c",
            "user.email=daidala@example.invalid",
            "commit",
            "--allow-empty",
            "-qm",
            "unrelated checkpoint parent",
        ],
        check=True,
    )
    wrong_parent = checkpoint_packet(fixture, git(fixture.repository, "rev-parse", "HEAD"))
    with pytest.raises(PolicyViolationError, match="direct child"):
        validate_plan_checkpoint(
            packet=wrong_parent,
            store=fixture.store,
            workspace=fixture.workspace,
        )

    git(fixture.repository, "reset", "--hard", fixture.revision)
    git(fixture.repository, "clean", "-fd")
    extra = checkpoint_packet(fixture, checkpoint_commit(fixture, extra_path=True))
    with pytest.raises(PolicyViolationError, match="unexpected paths"):
        validate_plan_checkpoint(
            packet=extra,
            store=fixture.store,
            workspace=fixture.workspace,
        )

    git(fixture.repository, "reset", "--hard", fixture.revision)
    git(fixture.repository, "clean", "-fd")
    forged_status = f"done (daidala:forged:{'c' * 64})"
    forged = checkpoint_packet(
        fixture,
        checkpoint_commit(fixture, done_status=forged_status),
    )
    with pytest.raises(PolicyViolationError, match="allowed status projection"):
        validate_plan_checkpoint(
            packet=forged,
            store=fixture.store,
            workspace=fixture.workspace,
        )

    git(fixture.repository, "reset", "--hard", fixture.revision)
    git(fixture.repository, "clean", "-fd")
    source_path = fixture.repository / fixture.packet.reference.plan_path
    source_path.write_text(
        source_path.read_text(encoding="utf-8") + "<!-- superseding rewrite -->\n",
        encoding="utf-8",
    )
    same_phase = admit_plan_source(
        repository=fixture.repository,
        plan_path=fixture.packet.reference.plan_path,
        source_revision=commit(fixture.repository, "plan-only same phase rewrite"),
        baseline_commit=git(fixture.repository, "rev-parse", "HEAD"),
        phase_number=0,
    )
    with pytest.raises(PolicyViolationError, match="cannot supersede"):
        validate_plan_checkpoint(
            packet=same_phase,
            store=fixture.store,
            workspace=fixture.workspace,
        )

    delivery = fixture.ledger.artifact_for(WorkflowStage.DELIVER)
    assert delivery is not None
    Path(delivery.path).write_text("{}\n", encoding="utf-8")
    with pytest.raises(PolicyViolationError, match="delivery evidence is unavailable"):
        validate_plan_checkpoint(
            packet=valid_packet,
            store=fixture.store,
            workspace=fixture.workspace,
        )
