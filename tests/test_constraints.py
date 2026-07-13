from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from daidala.constraints import extract_policy_skill_constraints, parse_workflow_constraints
from daidala.errors import PolicyViolationError
from daidala.state import (
    ConstraintSourceProvenance,
    WorkflowConstraintsArtifact,
    WorkflowConstraintsIdentity,
    WorkflowConstraintsReference,
    WorkflowStage,
)

NOW = datetime(2026, 7, 12, 12, 0, tzinfo=UTC)
VALID = """\
schema: daidala.workflow-constraints/v1
global:
  - Never commit or push.
  - "Do not add dependencies without approval."
phases:
  review:
    - Unresolved critical findings block delivery.
  deliver:
    - |-
      Documentation must match changed contracts.
      Describe required operator action.
"""


def test_policy_skill_extracts_only_the_fenced_yaml_document() -> None:
    markdown = f"""---
name: no-push-policy
description: Reusable delivery constraints.
---
```yaml
{VALID.rstrip()}
```
"""

    content = extract_policy_skill_constraints(markdown)

    assert content == VALID.rstrip()
    assert parse_workflow_constraints(content).global_constraints[0] == "Never commit or push."


@pytest.mark.parametrize(
    "body",
    (
        VALID,
        f"Prose before.\n```yaml\n{VALID.rstrip()}\n```",
        f"```yml\n{VALID.rstrip()}\n```",
        f"```yaml\n{VALID.rstrip()}\n```\n```yaml\n{VALID.rstrip()}\n```",
    ),
)
def test_policy_skill_rejects_any_body_other_than_one_yaml_fence(body: str) -> None:
    markdown = f"---\nname: no-push-policy\n---\n{body}\n"

    with pytest.raises(PolicyViolationError, match="exactly one fenced yaml"):
        extract_policy_skill_constraints(markdown)


def test_plain_quoted_literal_and_folded_scalars_canonicalize() -> None:
    constraints = parse_workflow_constraints(
        """\
schema: daidala.workflow-constraints/v1
global:
  - Plain policy.
  - "Quoted policy."
  - |-
    First line.
    Second line.
phases:
  verify:
    - >-
      Folded policy
      stays one line.
"""
    )

    assert constraints.global_constraints == (
        "Plain policy.",
        "Quoted policy.",
        "First line.\nSecond line.",
    )
    assert constraints.constraints_for(WorkflowStage.VERIFY) == (
        *constraints.global_constraints,
        "Folded policy stays one line.",
    )
    assert constraints.canonical_bytes().decode() == (
        '{"global":["Plain policy.","Quoted policy.",'
        '"First line.\\nSecond line."],"phases":{"verify":'
        '["Folded policy stays one line."]},'
        '"schema":"daidala.workflow-constraints/v1"}'
    )


def test_mapping_and_scalar_style_do_not_change_identity() -> None:
    first = parse_workflow_constraints(VALID)
    second = parse_workflow_constraints(
        """\
phases:
  deliver: ["Documentation must match changed contracts.\\nDescribe required operator action."]
  review: [Unresolved critical findings block delivery.]
global: [Never commit or push., Do not add dependencies without approval.]
schema: daidala.workflow-constraints/v1
"""
    )

    assert second == first
    assert second.digest == first.digest


def test_legacy_constraint_schema_is_rejected() -> None:
    legacy = "wing" + "staff"
    with pytest.raises(PolicyViolationError, match="constraint schema"):
        parse_workflow_constraints(
            f"schema: {legacy}.workflow-constraints/v1\nglobal: [Never push.]\n"
        )


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (
            "schema: daidala.workflow-constraints/v1\n"
            "global: [ok]\nglobal: [again]\n",
            "duplicate key",
        ),
        ("schema: daidala.workflow-constraints/v1\nglobal: &rows [ok]\n", "anchors"),
        ("schema: daidala.workflow-constraints/v1\nglobal: [!!str ok]\n", "tags"),
        ("schema: daidala.workflow-constraints/v1\nglobal: [ok]\nextra: true\n", "unknown"),
        ("schema: wrong\nglobal: [ok]\n", "schema"),
        ("schema: daidala.workflow-constraints/v1\nglobal: []\n", "1-16"),
        ("schema: daidala.workflow-constraints/v1\nglobal: [true]\n", "non-empty strings"),
        (
            "schema: daidala.workflow-constraints/v1\nglobal: [ok]\nphases:\n  approval: [no]\n",
            "not an executable",
        ),
        (
            "schema: daidala.workflow-constraints/v1\nglobal: [ok]\nphases:\n  build: [no]\n",
            "unknown constraint phase",
        ),
    ],
)
def test_invalid_yaml_structures_fail_closed(content: str, message: str) -> None:
    with pytest.raises(PolicyViolationError, match=message):
        parse_workflow_constraints(content)


def test_alias_merge_and_control_characters_fail_closed() -> None:
    with pytest.raises(PolicyViolationError, match="anchors, aliases"):
        parse_workflow_constraints(
            "schema: daidala.workflow-constraints/v1\n"
            "global: &rows [ok]\n"
            "phases: {review: *rows}\n"
        )
    with pytest.raises(PolicyViolationError, match="control characters"):
        parse_workflow_constraints(
            "schema: daidala.workflow-constraints/v1\nglobal: [bad\x07value]\n"
        )


def test_item_and_canonical_utf8_bounds_fail_closed() -> None:
    oversized_item = "é" * 513
    with pytest.raises(PolicyViolationError, match="1024 UTF-8 bytes"):
        parse_workflow_constraints(
            f"schema: daidala.workflow-constraints/v1\nglobal: [{oversized_item!r}]\n"
        )

    rows = "\n".join(f"  - {'x' * 250}{index}" for index in range(16))
    with pytest.raises(PolicyViolationError, match="4096 UTF-8 bytes"):
        parse_workflow_constraints(
            f"schema: daidala.workflow-constraints/v1\nglobal:\n{rows}\n"
        )


def test_artifact_identity_provenance_and_reference_are_strict_and_immutable() -> None:
    constraints = parse_workflow_constraints(VALID)
    identity = WorkflowConstraintsIdentity(
        policy_revision=1,
        constraints_revision=1,
        digest=constraints.digest,
    )
    source = ConstraintSourceProvenance(name="release-policy", digest="a" * 64)
    artifact = WorkflowConstraintsArtifact(
        schema="daidala.workflow-constraints-artifact/v1",
        workflow_id="workflow-1",
        identity=identity,
        canonical_content=constraints.canonical_bytes().decode(),
        source=source,
    )
    reference = WorkflowConstraintsReference(
        identity=identity,
        path="artifacts/constraints/1.json",
        recorded_at=NOW,
        source=source,
    )

    assert WorkflowConstraintsArtifact.from_dict(artifact.to_dict()) == artifact
    assert WorkflowConstraintsReference.from_dict(reference.to_dict()) == reference
    assert artifact.canonical_bytes().startswith(b'{"canonical_content":')
    with pytest.raises(FrozenInstanceError):
        artifact.workflow_id = "changed"  # type: ignore[misc]


def test_artifact_rejects_noncanonical_or_mismatched_content() -> None:
    constraints = parse_workflow_constraints(VALID)
    identity = WorkflowConstraintsIdentity(1, 1, constraints.digest)

    with pytest.raises(PolicyViolationError, match="canonical JSON"):
        WorkflowConstraintsArtifact(
            "daidala.workflow-constraints-artifact/v1",
            "workflow-1",
            identity,
            json.dumps(constraints.to_dict(), ensure_ascii=False),
        )
    with pytest.raises(PolicyViolationError, match="digest does not match"):
        WorkflowConstraintsArtifact(
            "daidala.workflow-constraints-artifact/v1",
            "workflow-1",
            WorkflowConstraintsIdentity(1, 1, "b" * 64),
            constraints.canonical_bytes().decode(),
        )


@pytest.mark.parametrize("revision", [0, -1, True])
def test_constraint_identity_requires_positive_integer_revisions(revision: object) -> None:
    with pytest.raises(PolicyViolationError, match="positive integer"):
        WorkflowConstraintsIdentity(revision, 1, "a" * 64)  # type: ignore[arg-type]
