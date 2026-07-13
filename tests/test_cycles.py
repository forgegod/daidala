from __future__ import annotations

from dataclasses import replace

import pytest

from daidala.cycles import (
    ComparisonOutcome,
    CycleIdentity,
    CycleMode,
    DelegationEvidence,
    LessonReuseEvidence,
    MetricDefinition,
    MetricKind,
)
from daidala.errors import PolicyViolationError


def identity(mode: CycleMode = CycleMode.IMPROVE) -> CycleIdentity:
    return CycleIdentity(
        project_id="forgegod-daidala",
        mode=mode,
        intake_adapter="github-issues",
        intake_item_id="issue-42",
        manifest_digest="a" * 64,
        baseline_revision="b" * 40,
        pack_name="addyosmani",
        pack_source_revision="c" * 40,
        pack_content_digest="d" * 64,
        candidate_identity=None if mode is CycleMode.IMPROVE else "candidate-v1",
    )


def test_cycle_identity_is_stable_path_safe_and_collision_sensitive() -> None:
    cycle = identity()

    assert CycleIdentity.from_dict(cycle.to_dict()) == cycle
    assert cycle.cycle_id == identity().cycle_id
    assert cycle.cycle_id.startswith("cycle-")
    assert len(cycle.cycle_id) == 70
    assert replace(cycle, intake_item_id="issue-43").cycle_id != cycle.cycle_id
    assert replace(cycle, manifest_digest="e" * 64).cycle_id != cycle.cycle_id


@pytest.mark.parametrize("mode", [CycleMode.REGRESS, CycleMode.EVALUATE_PACK])
def test_comparison_modes_require_explicit_candidate_identity(mode: CycleMode) -> None:
    with pytest.raises(PolicyViolationError, match="require a candidate"):
        replace(identity(mode), candidate_identity=None)


def test_metric_kinds_encode_retention_authority() -> None:
    deterministic = MetricDefinition("repository", MetricKind.DETERMINISTIC, True)
    repeated = MetricDefinition("stability", MetricKind.REPEATED, True, 3, 0, "all-pass")
    observational = MetricDefinition("ambiguity", MetricKind.OBSERVATIONAL, False)

    assert MetricDefinition.from_dict(deterministic.to_dict()) == deterministic
    assert MetricDefinition.from_dict(repeated.to_dict()) == repeated
    assert MetricDefinition.from_dict(observational.to_dict()) == observational
    assert ComparisonOutcome.INCOMPARABLE.value == "incomparable"
    with pytest.raises(PolicyViolationError, match="cannot define retention thresholds"):
        MetricDefinition("observation", MetricKind.OBSERVATIONAL, False, 3, 0, "mean")
    with pytest.raises(PolicyViolationError, match="cannot allow failures"):
        MetricDefinition("stability", MetricKind.REPEATED, True, 3, 1, "all-pass")


def test_delegation_and_lesson_reuse_evidence_are_bounded_and_round_trip() -> None:
    delegation = DelegationEvidence(
        parent_run_id="run:parent",
        child_run_id="run:child",
        delegated_goal="Inspect the schema",
        role="leaf",
        toolsets=("file",),
        model_route="configured-default",
        input_artifact_digests=("a" * 64,),
        output_digest="b" * 64,
        turns=3,
        wall_clock_milliseconds=250,
        terminal_state="completed",
    )
    lesson = LessonReuseEvidence(
        lesson_digest="c" * 64,
        applicable=True,
        failed_actions_avoided=1,
        recovery_outcome="not-needed",
        turns=2,
        wall_clock_milliseconds=100,
        irrelevant_matches=0,
        unsafe_uses=0,
    )

    assert DelegationEvidence.from_dict(delegation.to_dict()) == delegation
    assert LessonReuseEvidence.from_dict(lesson.to_dict()) == lesson

    with pytest.raises(PolicyViolationError, match="output digest"):
        replace(delegation, output_digest=None)
    with pytest.raises(PolicyViolationError, match="cannot contain duplicates"):
        replace(delegation, input_artifact_digests=("a" * 64, "a" * 64))
    with pytest.raises(PolicyViolationError, match="cannot claim"):
        replace(lesson, applicable=False)
