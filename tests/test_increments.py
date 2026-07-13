from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from daidala.errors import PolicyViolationError
from daidala.increments import (
    DocumentClass,
    IncrementEntry,
    IncrementManifest,
    ProducerIdentity,
    RedactionState,
    RetentionDisposition,
    increment_manifest_path,
    reconcile_increment_manifest,
)
from daidala.packs import SkillActivationMode
from daidala.projects import parse_project_manifest
from daidala.state import (
    ActivationCategory,
    ActivationDecision,
    ActivationManifest,
    WorkflowStage,
)

NOW = datetime(2026, 7, 13, 12, 0, tzinfo=UTC)


def entry(**changes: object) -> IncrementEntry:
    values: dict[str, object] = {
        "entry_id": "architecture-doc",
        "document_class": DocumentClass.REPOSITORY_INCREMENT,
        "media_type": "text/markdown",
        "purpose": "Describe the approved architecture increment.",
        "repository_path": "docs/15-self-improvement.md",
        "artifact_reference": None,
        "content_digest": "a" * 64,
        "byte_size": 1024,
        "cycle_id": "cycle-" + "b" * 64,
        "workflow_id": "workflow-1",
        "stage": WorkflowStage.IMPLEMENT,
        "plan_revision": 1,
        "policy_revision": 1,
        "project_manifest_digest": "c" * 64,
        "pack_identity_digest": "d" * 64,
        "constraints_digest": "e" * 64,
        "activation_manifest_digest": "f" * 64,
        "producers": (ProducerIdentity("documentation-and-adrs", "1" * 64),),
        "created_at": NOW,
        "supersedes_entry_id": None,
        "redaction_state": RedactionState.NOT_REQUIRED,
        "disposition": RetentionDisposition.RETAIN,
        "dox_scope": "docs/AGENTS.md",
    }
    values.update(changes)
    return IncrementEntry(**values)  # type: ignore[arg-type]


def test_increment_manifest_round_trip_digest_and_canonical_order() -> None:
    manifest = IncrementManifest(
        cycle_id="cycle-" + "b" * 64,
        workflow_id="workflow-1",
        entries=(entry(),),
    )

    assert IncrementManifest.from_dict(manifest.to_dict()) == manifest
    assert len(manifest.digest) == 64
    assert manifest.canonical_bytes().startswith(b'{"cycle_id":')


def test_increment_manifest_uses_profile_local_content_addressed_storage() -> None:
    cycle_id = "cycle-" + "b" * 64
    assert increment_manifest_path(Path("/profile/data"), "forgegod-daidala", cycle_id) == Path(
        f"/profile/data/projects/forgegod-daidala/cycles/{cycle_id}/increment-manifest.json"
    )
    with pytest.raises(PolicyViolationError, match="absolute resolved"):
        increment_manifest_path(Path("relative"), "forgegod-daidala", cycle_id)
    with pytest.raises(PolicyViolationError, match="absolute resolved"):
        increment_manifest_path(Path("/profile/../other"), "forgegod-daidala", cycle_id)
    with pytest.raises(PolicyViolationError, match="cycle- plus"):
        increment_manifest_path(Path("/profile/data"), "forgegod-daidala", "../escape")


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"document_class": DocumentClass.EPHEMERAL_WORK_PRODUCT}, "cannot enter"),
        ({"producers": ()}, "1-8 identities"),
        ({"repository_path": "../escape.md"}, "repository-relative"),
        ({"repository_path": "."}, "repository-relative"),
        ({"repository_path": None}, "non-empty"),
        ({"media_type": "text/markdown; charset=utf-8"}, "canonical type/subtype"),
        ({"byte_size": 1_048_577}, "0 to 1048576"),
        ({"activation_manifest_digest": "stale"}, "SHA-256"),
        ({"disposition": RetentionDisposition.PUBLISH_PENDING}, "retained or rejected"),
    ],
)
def test_increment_repository_document_fail_closed_cases(
    changes: dict[str, object], message: str
) -> None:
    with pytest.raises(PolicyViolationError, match=message):
        entry(**changes)


def test_increment_unknown_producer_without_digest_fails_closed() -> None:
    with pytest.raises(PolicyViolationError, match="SHA-256"):
        ProducerIdentity("unknown", None)


def test_workflow_and_external_documents_require_content_addressed_artifacts() -> None:
    workflow = entry(
        entry_id="plan-artifact",
        document_class=DocumentClass.WORKFLOW_ARTIFACT,
        repository_path=None,
        artifact_reference="artifacts/cycles/cycle-1/plan.json",
        dox_scope=None,
        disposition=RetentionDisposition.RETAIN,
        producers=(ProducerIdentity("deterministic-engine", None),),
    )
    finding = replace(
        workflow,
        entry_id="finding",
        document_class=DocumentClass.EXTERNAL_FINDING,
        disposition=RetentionDisposition.PUBLISH_PENDING,
    )

    assert workflow.artifact_reference is not None
    assert finding.disposition is RetentionDisposition.PUBLISH_PENDING
    with pytest.raises(PolicyViolationError, match="under artifacts"):
        replace(workflow, artifact_reference="tmp/plan.json")


def test_manifest_rejects_duplicate_identity_and_cross_cycle_entry() -> None:
    one = entry()
    with pytest.raises(PolicyViolationError, match="duplicate entry IDs"):
        IncrementManifest(one.cycle_id, one.workflow_id, (one, one))
    with pytest.raises(PolicyViolationError, match="does not match"):
        IncrementManifest("cycle-" + "9" * 64, one.workflow_id, (one,))


def activation_manifest() -> ActivationManifest:
    return ActivationManifest(
        schema="daidala.skill-activation/v1",
        workflow_id="workflow-1",
        stage=WorkflowStage.IMPLEMENT,
        plan_revision=1,
        policy_revision=1,
        constraints_digest="e" * 64,
        pack="addyosmani",
        pack_source_revision="7ce442de03ddc1b72480c3b48d55c62880ea2a90",
        sequence=1,
        supersedes_digest=None,
        decisions=(
            ActivationDecision(
                name="documentation-and-adrs",
                skill_digest="1" * 64,
                activation_mode=SkillActivationMode.CONDITIONAL,
                category=ActivationCategory.APPLICABLE,
                rank=1,
                matched_criteria=("The approved plan declares a document.",),
                evidence=("The implementation card owns the document.",),
                rationale="The skill produced the repository increment.",
                condition=None,
            ),
        ),
    )


def pack_identity_digest(project) -> str:
    pack = next(row for row in project.allowed_packs if row.name == "addyosmani")
    content = json.dumps(
        pack.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def test_increment_reconciliation_binds_plan_diff_content_activation_and_nearest_dox(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    docs = repository / "docs"
    docs.mkdir(parents=True)
    (repository / "AGENTS.md").write_text("# root\n", encoding="utf-8")
    (docs / "AGENTS.md").write_text("# docs\n", encoding="utf-8")
    content = b"# Approved architecture\n"
    (docs / "architecture.md").write_bytes(content)
    project = parse_project_manifest(
        (Path(__file__).parents[1] / ".daidala/project.yaml").read_text(encoding="utf-8")
    )
    activation = activation_manifest()
    activation_digest = hashlib.sha256(activation.canonical_bytes()).hexdigest()
    pack_digest = pack_identity_digest(project)
    document = entry(
        repository_path="docs/architecture.md",
        content_digest=hashlib.sha256(content).hexdigest(),
        byte_size=len(content),
        project_manifest_digest=project.digest,
        pack_identity_digest=pack_digest,
        activation_manifest_digest=activation_digest,
        dox_scope="docs/AGENTS.md",
    )
    manifest = IncrementManifest(document.cycle_id, document.workflow_id, (document,))

    result = reconcile_increment_manifest(
        manifest,
        project_manifest=project,
        repository_root=repository,
        approved_repository_paths=("docs/architecture.md",),
        frozen_changed_paths=("docs/architecture.md",),
        artifact_ledger={},
        activation_manifests=(activation,),
        expected_pack_identity_digest=pack_digest,
        expected_constraints_digest="e" * 64,
    )

    assert result.manifest_digest == manifest.digest
    assert result.repository_paths == ("docs/architecture.md",)
    assert result.activation_digests == (activation_digest,)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ("undeclared", "approved plan"),
        ("stale-activation", "activation"),
        ("duplicate-activation", "duplicate identity"),
        ("unknown-producer", "not active"),
        ("wrong-dox", "nearest owning DOX"),
        ("content-drift", "content digest"),
    ],
)
def test_increment_reconciliation_fails_closed(
    tmp_path: Path,
    change: str,
    message: str,
) -> None:
    repository = tmp_path / "repository"
    docs = repository / "docs"
    docs.mkdir(parents=True)
    (repository / "AGENTS.md").write_text("# root\n", encoding="utf-8")
    (docs / "AGENTS.md").write_text("# docs\n", encoding="utf-8")
    content = b"# Approved architecture\n"
    target = docs / "architecture.md"
    target.write_bytes(content)
    project = parse_project_manifest(
        (Path(__file__).parents[1] / ".daidala/project.yaml").read_text(encoding="utf-8")
    )
    activation = activation_manifest()
    activation_digest = hashlib.sha256(activation.canonical_bytes()).hexdigest()
    pack_digest = pack_identity_digest(project)
    document = entry(
        repository_path="docs/architecture.md",
        content_digest=hashlib.sha256(content).hexdigest(),
        byte_size=len(content),
        project_manifest_digest=project.digest,
        pack_identity_digest=pack_digest,
        activation_manifest_digest=(
            "9" * 64 if change == "stale-activation" else activation_digest
        ),
        dox_scope=("AGENTS.md" if change == "wrong-dox" else "docs/AGENTS.md"),
        producers=(
            ProducerIdentity("unknown-producer", "8" * 64),
        )
        if change == "unknown-producer"
        else (ProducerIdentity("documentation-and-adrs", "1" * 64),),
    )
    if change == "content-drift":
        target.write_text("changed after capture\n", encoding="utf-8")
    approved = () if change == "undeclared" else ("docs/architecture.md",)

    with pytest.raises(PolicyViolationError, match=message):
        reconcile_increment_manifest(
            IncrementManifest(document.cycle_id, document.workflow_id, (document,)),
            project_manifest=project,
            repository_root=repository,
            approved_repository_paths=approved,
            frozen_changed_paths=("docs/architecture.md",),
            artifact_ledger={},
            activation_manifests=(
                (activation, activation)
                if change == "duplicate-activation"
                else (activation,)
            ),
            expected_pack_identity_digest=pack_digest,
            expected_constraints_digest="e" * 64,
        )
