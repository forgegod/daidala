from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from daidala.cycles import (
    ComparisonVerdict,
    CycleMode,
    LessonReuseEvidence,
    MetricDefinition,
    MetricKind,
)
from daidala.errors import PolicyViolationError
from daidala.evaluation import (
    ComparisonReport,
    EvaluationEvidence,
    EvaluatorIdentity,
    EvaluatorIsolationEvidence,
    EvaluatorWorkspace,
    GraphEvidence,
    MetricEvidence,
    compare_evaluations,
)
from daidala.registrations import ControllerRegistration, RegistrationLimits

CYCLE_ID = "cycle-" + "a" * 64
FIXTURE_DIGEST = "b" * 64
LIMITS_DIGEST = "c" * 64
BASELINE_REVISION = "d" * 40
CANDIDATE_REVISION = "e" * 40
CONTROLLER_ARTIFACT = "f" * 64
CANDIDATE_ARTIFACT = "1" * 64


def metric_evidence(
    *,
    revision: str,
    repeated_values: tuple[float, ...] = (1.0, 1.0, 1.0),
    deterministic_passed: bool = True,
    graph_revision: str | None = None,
) -> tuple[MetricEvidence, ...]:
    deterministic = MetricDefinition("repository", MetricKind.DETERMINISTIC, True)
    repeated = MetricDefinition(
        "stability",
        MetricKind.REPEATED,
        True,
        repetitions=3,
        maximum_failures=0,
        aggregation="mean",
        maximum_variance=0.25,
        direction="higher-is-better",
    )
    observational = MetricDefinition("ambiguity", MetricKind.OBSERVATIONAL, False)
    common = {
        "test_case_id": "TC-F17-01",
        "fixture_digest": FIXTURE_DIGEST,
        "environment_class": "restricted-container",
        "limits_digest": LIMITS_DIGEST,
        "repository_revision": revision,
    }
    return (
        MetricEvidence(
            definition=observational,
            observation_digest="2" * 64,
            graph=GraphEvidence(
                repository_revision=graph_revision or revision,
                files=12,
                nodes=50,
                digest="3" * 64,
            ),
            **common,
        ),
        MetricEvidence(
            definition=deterministic,
            passes=(deterministic_passed,),
            **common,
        ),
        MetricEvidence(
            definition=repeated,
            passes=(True, True, True),
            values=repeated_values,
            **common,
        ),
    )


def evaluation(
    mode: CycleMode,
    *,
    evaluator_id: str,
    subject_identity: str,
    revision: str,
    repeated_values: tuple[float, ...] = (1.0, 1.0, 1.0),
    deterministic_passed: bool = True,
    graph_revision: str | None = None,
    lesson_reuse: tuple[LessonReuseEvidence, ...] = (),
) -> EvaluationEvidence:
    return EvaluationEvidence(
        cycle_id=CYCLE_ID,
        workflow_id=CYCLE_ID,
        mode=mode,
        evaluator_id=evaluator_id,
        subject_identity=subject_identity,
        metrics=metric_evidence(
            revision=revision,
            repeated_values=repeated_values,
            deterministic_passed=deterministic_passed,
            graph_revision=graph_revision,
        ),
        lesson_reuse=lesson_reuse,
    )


@pytest.mark.parametrize("mode", tuple(CycleMode))
def test_complete_fixture_compares_in_all_cycle_modes(mode: CycleMode) -> None:
    baseline = evaluation(
        mode,
        evaluator_id=f"{mode.value}-baseline",
        subject_identity="baseline",
        revision=BASELINE_REVISION,
    )
    candidate = evaluation(
        mode,
        evaluator_id=f"{mode.value}-candidate",
        subject_identity="candidate",
        revision=CANDIDATE_REVISION,
        repeated_values=(2.0, 2.0, 2.0),
    )

    report = compare_evaluations(baseline, candidate)

    assert report.candidate_improved is True
    assert report.retention_eligible is (mode is CycleMode.IMPROVE)
    assert report.verdict is ComparisonVerdict.IMPROVED
    assert EvaluationEvidence.from_dict(candidate.to_dict()) == candidate
    assert report.digest == compare_evaluations(baseline, candidate).digest


@pytest.mark.parametrize("mode", tuple(CycleMode))
def test_controlled_lesson_reuse_comparison_records_bounded_deltas(mode: CycleMode) -> None:
    baseline_lesson = LessonReuseEvidence(
        lesson_digest="7" * 64,
        applicable=True,
        failed_actions_avoided=0,
        recovery_outcome="not-needed",
        turns=6,
        wall_clock_milliseconds=600,
        irrelevant_matches=0,
        unsafe_uses=0,
    )
    candidate_lesson = replace(
        baseline_lesson,
        failed_actions_avoided=1,
        turns=4,
        wall_clock_milliseconds=400,
    )
    baseline = evaluation(
        mode,
        evaluator_id=f"{mode.value}-lesson-baseline",
        subject_identity="without-lesson",
        revision=BASELINE_REVISION,
        lesson_reuse=(baseline_lesson,),
    )
    candidate = evaluation(
        mode,
        evaluator_id=f"{mode.value}-lesson-candidate",
        subject_identity="with-lesson",
        revision=CANDIDATE_REVISION,
        lesson_reuse=(candidate_lesson,),
    )

    report = compare_evaluations(baseline, candidate)

    assert report.verdict is ComparisonVerdict.EQUIVALENT
    assert report.retention_eligible is False
    assert report.lesson_reuse[0].failed_actions_avoided_delta == 1
    assert report.lesson_reuse[0].turns_delta == -2
    assert report.lesson_reuse[0].wall_clock_milliseconds_delta == -200
    assert EvaluationEvidence.from_dict(candidate.to_dict()) == candidate

    with pytest.raises(PolicyViolationError, match="lesson reuse comparison identities"):
        compare_evaluations(baseline, replace(candidate, lesson_reuse=()))


def test_comparison_rejects_regression_and_marks_missing_or_stale_evidence_incomparable() -> None:
    baseline = evaluation(
        CycleMode.IMPROVE,
        evaluator_id="baseline",
        subject_identity="baseline",
        revision=BASELINE_REVISION,
    )
    failed = evaluation(
        CycleMode.IMPROVE,
        evaluator_id="failed",
        subject_identity="candidate",
        revision=CANDIDATE_REVISION,
        deterministic_passed=False,
    )
    stale_graph = evaluation(
        CycleMode.IMPROVE,
        evaluator_id="stale-graph",
        subject_identity="candidate",
        revision=CANDIDATE_REVISION,
        graph_revision=BASELINE_REVISION,
    )
    missing = replace(
        stale_graph,
        evaluator_id="missing",
        metrics=stale_graph.metrics[:-1],
    )

    assert compare_evaluations(baseline, failed).verdict is ComparisonVerdict.REGRESSED
    stale_report = compare_evaluations(baseline, stale_graph)
    assert stale_report.verdict is ComparisonVerdict.EQUIVALENT
    assert stale_report.metrics[0].status == "incomparable"
    assert compare_evaluations(baseline, missing).verdict is ComparisonVerdict.INCOMPARABLE


def test_required_deterministic_failure_blocks_other_metric_improvement() -> None:
    baseline = evaluation(
        CycleMode.IMPROVE,
        evaluator_id="failed-baseline",
        subject_identity="baseline",
        revision=BASELINE_REVISION,
        deterministic_passed=False,
    )
    candidate = evaluation(
        CycleMode.IMPROVE,
        evaluator_id="failed-candidate",
        subject_identity="candidate",
        revision=CANDIDATE_REVISION,
        repeated_values=(2.0, 2.0, 2.0),
        deterministic_passed=False,
    )

    report = compare_evaluations(baseline, candidate)

    assert report.verdict is ComparisonVerdict.REGRESSED
    assert report.retention_eligible is False


def test_numeric_comparison_honors_explicit_lower_is_better_direction() -> None:
    before = metric_evidence(revision=BASELINE_REVISION)[-1]
    after = metric_evidence(
        revision=CANDIDATE_REVISION,
        repeated_values=(0.5, 0.5, 0.5),
    )[-1]
    before = replace(
        before,
        definition=replace(before.definition, direction="lower-is-better"),
    )
    after = replace(
        after,
        definition=replace(after.definition, direction="lower-is-better"),
    )
    baseline = evaluation(
        CycleMode.IMPROVE,
        evaluator_id="lower-baseline",
        subject_identity="baseline",
        revision=BASELINE_REVISION,
    )
    candidate = evaluation(
        CycleMode.IMPROVE,
        evaluator_id="lower-candidate",
        subject_identity="candidate",
        revision=CANDIDATE_REVISION,
    )

    report = compare_evaluations(
        replace(baseline, metrics=(*baseline.metrics[:-1], before)),
        replace(candidate, metrics=(*candidate.metrics[:-1], after)),
    )

    assert report.verdict is ComparisonVerdict.IMPROVED


def registration(checkout: Path) -> ControllerRegistration:
    return ControllerRegistration(
        project_id="forgegod-daidala",
        checkout=str(checkout),
        controller_profile="daidala-self-improvement",
        board="daidala-forgegod-daidala",
        repository_canonical="forgegod/daidala",
        verified_remote="https://github.com/forgegod/daidala.git",
        intake_credential="github-read",
        findings_credential="github-findings",
        maintainers=("operator",),
        notification_adapter="hermes-gateway",
        notification_target="attended-daidala",
        evaluator_backend="restricted-container",
        evaluator_network="denied-by-default",
        limits=RegistrationLimits(1, 12, 3, 3, 3, 3600),
    )


def isolation_evidence() -> EvaluatorIsolationEvidence:
    return EvaluatorIsolationEvidence(
        backend="restricted-container",
        network="denied-by-default",
        image_identity="sha256:" + "6" * 64,
        fresh_home=True,
        network_denied=True,
        controller_credentials_absent=True,
        bounded_mounts=True,
        receipt_id="isolation-receipt-1",
    )


def init_repository(path: Path) -> Path:
    path.mkdir()
    (path / "value.py").write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(path),
            "-c",
            "user.name=Daidala Tests",
            "-c",
            "user.email=daidala@example.invalid",
            "commit",
            "-qm",
            "baseline",
        ],
        check=True,
    )
    return path.resolve()


def evaluator_identity(
    role: str,
    revision: str,
    mode: CycleMode = CycleMode.IMPROVE,
) -> EvaluatorIdentity:
    return EvaluatorIdentity(
        project_id="forgegod-daidala",
        cycle_id=CYCLE_ID,
        evaluator_id=f"uc01-{role}",
        mode=mode,
        role=role,
        subject_identity=role,
        repository_revision=revision,
        limits_digest=LIMITS_DIGEST,
        isolation_digest=isolation_evidence().digest,
        controller_artifact_identity=CONTROLLER_ARTIFACT,
        candidate_artifact_identity=CANDIDATE_ARTIFACT if role == "candidate" else None,
        backend="restricted-container",
        network="denied-by-default",
    )


@pytest.mark.parametrize("mode", tuple(CycleMode))
def test_complete_local_evaluator_fixture_runs_in_every_mode(
    tmp_path: Path,
    mode: CycleMode,
) -> None:
    checkout = init_repository(tmp_path / "checkout")
    revision = subprocess.run(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    workspace = EvaluatorWorkspace(
        (tmp_path / "data").resolve(), registration(checkout), isolation_evidence()
    )
    baseline_identity = evaluator_identity("baseline", revision, mode)
    candidate_identity = evaluator_identity("candidate", revision, mode)
    baseline_paths = workspace.create(baseline_identity)
    candidate_paths = workspace.create(candidate_identity)

    environment = workspace.environment(
        candidate_identity,
        {"PATH": "/usr/bin", "GH_TOKEN": "must-not-cross", "HERMES_HOME": "/controller"},
    )

    assert Path(environment["HERMES_HOME"]) == candidate_paths.home
    assert environment["DAIDALA_CANDIDATE_ARTIFACT"] == CANDIDATE_ARTIFACT
    assert "GH_TOKEN" not in environment
    assert baseline_paths.home != candidate_paths.home
    with pytest.raises(PolicyViolationError, match="network denied"):
        replace(isolation_evidence(), network_denied=False)
    with pytest.raises(PolicyViolationError, match="durable baseline"):
        workspace.create_worktree(candidate_identity)

    baseline = evaluation(
        mode,
        evaluator_id=baseline_identity.evaluator_id,
        subject_identity="baseline",
        revision=revision,
    )
    workspace.record_evidence(baseline_identity, baseline, baseline=True)
    worktree = workspace.create_worktree(candidate_identity)
    candidate = evaluation(
        mode,
        evaluator_id=candidate_identity.evaluator_id,
        subject_identity="candidate",
        revision=revision,
        repeated_values=(2.0, 2.0, 2.0),
    )
    workspace.record_evidence(candidate_identity, candidate)
    report = compare_evaluations(baseline, candidate)

    assert worktree.is_dir()
    assert worktree != checkout
    assert report.verdict is ComparisonVerdict.IMPROVED
    assert report.retention_eligible is (mode is CycleMode.IMPROVE)
    assert ComparisonReport.from_dict(report.to_dict()) == report
    assert workspace.record_evidence(baseline_identity, baseline, baseline=True).exists()
    assert EvaluatorIdentity.from_dict(candidate_identity.to_dict()) == candidate_identity
    with pytest.raises(PolicyViolationError, match="controller artifact"):
        replace(
            candidate_identity,
            candidate_artifact_identity=candidate_identity.controller_artifact_identity,
        )

    stale_identity = replace(
        candidate_identity,
        evaluator_id="stale-candidate",
        limits_digest="9" * 64,
    )
    workspace.create(stale_identity)
    with pytest.raises(PolicyViolationError, match="baseline evidence identity is stale"):
        workspace.create_worktree(stale_identity)

    stale_revision_identity = replace(
        candidate_identity,
        evaluator_id="stale-revision-candidate",
        repository_revision="8" * 40,
    )
    workspace.create(stale_revision_identity)
    with pytest.raises(PolicyViolationError, match="baseline evidence identity is stale"):
        workspace.create_worktree(stale_revision_identity)

    assert workspace.finalize(candidate_identity, terminal_state="completed") is None
    assert not candidate_paths.scratch.exists()
    assert not candidate_paths.home.exists()
    assert not worktree.exists()


def test_evaluator_rejects_stale_evidence_and_quarantines_failed_mutation(tmp_path: Path) -> None:
    checkout = init_repository(tmp_path / "checkout")
    revision = subprocess.run(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    workspace = EvaluatorWorkspace(
        (tmp_path / "data").resolve(), registration(checkout), isolation_evidence()
    )
    baseline_identity = evaluator_identity("baseline", revision)
    workspace.create(baseline_identity)
    workspace.record_evidence(
        baseline_identity,
        evaluation(
            CycleMode.IMPROVE,
            evaluator_id=baseline_identity.evaluator_id,
            subject_identity="baseline",
            revision=revision,
        ),
        baseline=True,
    )
    identity = evaluator_identity("candidate", revision)
    paths = workspace.create(identity)
    worktree = workspace.create_worktree(identity)
    (worktree / "value.py").write_text("VALUE = 2\n", encoding="utf-8")
    (paths.scratch / "worker.log").write_text("bounded failure\n", encoding="utf-8")
    stale = evaluation(
        CycleMode.IMPROVE,
        evaluator_id="other-evaluator",
        subject_identity="candidate",
        revision=revision,
    )

    with pytest.raises(PolicyViolationError, match="evaluator identity"):
        workspace.record_evidence(identity, stale)

    quarantine = workspace.finalize(identity, terminal_state="completed")
    assert quarantine is not None
    assert quarantine.is_dir()
    assert not paths.scratch.exists()
    assert worktree.is_dir()
    assert (quarantine / "recovery.json").is_file()
