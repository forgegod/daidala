from __future__ import annotations

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
)
from daidala.state import WorkflowStage

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
