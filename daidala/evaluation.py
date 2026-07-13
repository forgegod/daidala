"""Fresh evaluator workspaces and deterministic evidence comparison."""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import statistics
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .cycles import (
    ComparisonVerdict,
    CycleMode,
    LessonReuseEvidence,
    MetricDefinition,
    MetricKind,
)
from .errors import PolicyViolationError
from .projects import (
    _as_list,
    _require_digest,
    _require_exact_fields,
    _require_int,
    _require_revision,
    _require_slug,
    _require_text,
)
from .registrations import ControllerRegistration

EVALUATION_SCHEMA = "daidala.evaluation-evidence/v1"
EVALUATOR_SCHEMA = "daidala.evaluator-identity/v1"
COMPARISON_SCHEMA = "daidala.comparison-report/v1"
_CYCLE_PREFIX = "cycle-"
_ALLOWED_INHERITED_ENV = frozenset({"LANG", "LC_ALL", "PATH", "TZ"})


@dataclass(frozen=True)
class GraphEvidence:
    repository_revision: str
    files: int
    nodes: int
    digest: str

    def __post_init__(self) -> None:
        _require_revision(self.repository_revision, "graph repository revision")
        _require_int(self.files, "graph files", 0, 10_000_000)
        _require_int(self.nodes, "graph nodes", 0, 100_000_000)
        _require_digest(self.digest, "graph evidence digest")

    def to_dict(self) -> dict[str, Any]:
        return {
            "repository_revision": self.repository_revision,
            "files": self.files,
            "nodes": self.nodes,
            "digest": self.digest,
        }

    @classmethod
    def from_dict(cls, raw: Any) -> GraphEvidence:
        _require_exact_fields(
            raw,
            {"repository_revision", "files", "nodes", "digest"},
            "graph evidence",
        )
        return cls(**raw)


@dataclass(frozen=True)
class MetricEvidence:
    definition: MetricDefinition
    test_case_id: str
    fixture_digest: str
    environment_class: str
    limits_digest: str
    repository_revision: str
    passes: tuple[bool, ...] = ()
    values: tuple[float, ...] = ()
    observation_digest: str | None = None
    graph: GraphEvidence | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.definition, MetricDefinition):
            raise PolicyViolationError("metric evidence definition is invalid")
        _require_text(self.test_case_id, "metric test-case ID", 128)
        _require_digest(self.fixture_digest, "metric fixture digest")
        _require_slug(self.environment_class, "metric environment class")
        _require_digest(self.limits_digest, "metric limits digest")
        _require_revision(self.repository_revision, "metric repository revision")
        if not isinstance(self.passes, tuple) or any(
            type(value) is not bool for value in self.passes
        ):
            raise PolicyViolationError("metric pass samples must be booleans")
        if not isinstance(self.values, tuple) or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            for value in self.values
        ):
            raise PolicyViolationError("metric numeric samples must be finite numbers")
        if self.graph is not None and not isinstance(self.graph, GraphEvidence):
            raise PolicyViolationError("metric graph evidence is invalid")

        if self.definition.kind is MetricKind.DETERMINISTIC:
            if len(self.passes) != 1 or self.values or self.observation_digest is not None:
                raise PolicyViolationError(
                    "deterministic metric evidence requires one pass sample and no derived values"
                )
        elif self.definition.kind is MetricKind.REPEATED:
            repetitions = self.definition.repetitions or 0
            if len(self.passes) != repetitions:
                raise PolicyViolationError("repeated metric evidence is incomplete")
            if self.definition.aggregation in {"mean", "median"}:
                if len(self.values) != repetitions:
                    raise PolicyViolationError("numeric repeated metric evidence is incomplete")
            elif self.values:
                raise PolicyViolationError(
                    "all-pass metric evidence cannot contain numeric samples"
                )
            if self.observation_digest is not None:
                raise PolicyViolationError("repeated metric evidence cannot be observational")
        else:
            if self.passes or self.values:
                raise PolicyViolationError(
                    "observational metric evidence cannot authorize retention"
                )
            _require_digest(self.observation_digest, "metric observation digest")

    @property
    def comparison_identity(self) -> tuple[Any, ...]:
        return (
            self.definition,
            self.test_case_id,
            self.fixture_digest,
            self.environment_class,
            self.limits_digest,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "definition": self.definition.to_dict(),
            "test_case_id": self.test_case_id,
            "fixture_digest": self.fixture_digest,
            "environment_class": self.environment_class,
            "limits_digest": self.limits_digest,
            "repository_revision": self.repository_revision,
            "passes": list(self.passes),
            "values": list(self.values),
            "observation_digest": self.observation_digest,
            "graph": self.graph.to_dict() if self.graph else None,
        }

    @classmethod
    def from_dict(cls, raw: Any) -> MetricEvidence:
        _require_exact_fields(
            raw,
            {
                "definition",
                "test_case_id",
                "fixture_digest",
                "environment_class",
                "limits_digest",
                "repository_revision",
                "passes",
                "values",
                "observation_digest",
                "graph",
            },
            "metric evidence",
        )
        return cls(
            definition=MetricDefinition.from_dict(raw["definition"]),
            test_case_id=raw["test_case_id"],
            fixture_digest=raw["fixture_digest"],
            environment_class=raw["environment_class"],
            limits_digest=raw["limits_digest"],
            repository_revision=raw["repository_revision"],
            passes=tuple(_as_list(raw["passes"], "metric pass samples")),
            values=tuple(_as_list(raw["values"], "metric numeric samples")),
            observation_digest=raw["observation_digest"],
            graph=GraphEvidence.from_dict(raw["graph"]) if raw["graph"] is not None else None,
        )


@dataclass(frozen=True)
class EvaluationEvidence:
    cycle_id: str
    workflow_id: str
    mode: CycleMode
    evaluator_id: str
    subject_identity: str
    metrics: tuple[MetricEvidence, ...]
    lesson_reuse: tuple[LessonReuseEvidence, ...] = ()
    schema: str = EVALUATION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != EVALUATION_SCHEMA:
            raise PolicyViolationError(f"evaluation schema must be {EVALUATION_SCHEMA!r}")
        _require_cycle_id(self.cycle_id, "evaluation cycle ID")
        if self.workflow_id != self.cycle_id:
            raise PolicyViolationError("evaluation workflow ID must equal the cycle ID")
        if not isinstance(self.mode, CycleMode):
            raise PolicyViolationError("evaluation cycle mode is invalid")
        _require_slug(self.evaluator_id, "evaluation evaluator ID")
        _require_text(self.subject_identity, "evaluation subject identity", 512)
        if not isinstance(self.metrics, tuple) or not 1 <= len(self.metrics) <= 64:
            raise PolicyViolationError("evaluation must contain 1-64 metric records")
        metric_ids = [row.definition.id for row in self.metrics]
        if metric_ids != sorted(metric_ids) or len(metric_ids) != len(set(metric_ids)):
            raise PolicyViolationError(
                "evaluation metrics must use unique canonical metric-ID order"
            )
        if not isinstance(self.lesson_reuse, tuple) or len(self.lesson_reuse) > 32:
            raise PolicyViolationError("evaluation lesson reuse must contain at most 32 records")
        lesson_ids = [row.lesson_digest for row in self.lesson_reuse]
        if lesson_ids != sorted(lesson_ids) or len(lesson_ids) != len(set(lesson_ids)):
            raise PolicyViolationError(
                "evaluation lessons must use unique canonical digest order"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "cycle_id": self.cycle_id,
            "workflow_id": self.workflow_id,
            "mode": self.mode.value,
            "evaluator_id": self.evaluator_id,
            "subject_identity": self.subject_identity,
            "metrics": [row.to_dict() for row in self.metrics],
            "lesson_reuse": [row.to_dict() for row in self.lesson_reuse],
        }

    def canonical_bytes(self) -> bytes:
        return _canonical_json(self.to_dict())

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    @classmethod
    def from_dict(cls, raw: Any) -> EvaluationEvidence:
        _require_exact_fields(
            raw,
            {
                "schema",
                "cycle_id",
                "workflow_id",
                "mode",
                "evaluator_id",
                "subject_identity",
                "metrics",
                "lesson_reuse",
            },
            "evaluation evidence",
        )
        try:
            mode = CycleMode(raw["mode"])
        except (TypeError, ValueError) as error:
            raise PolicyViolationError("evaluation cycle mode is invalid") from error
        return cls(
            schema=raw["schema"],
            cycle_id=raw["cycle_id"],
            workflow_id=raw["workflow_id"],
            mode=mode,
            evaluator_id=raw["evaluator_id"],
            subject_identity=raw["subject_identity"],
            metrics=tuple(
                MetricEvidence.from_dict(row)
                for row in _as_list(raw["metrics"], "evaluation metrics")
            ),
            lesson_reuse=tuple(
                LessonReuseEvidence.from_dict(row)
                for row in _as_list(raw["lesson_reuse"], "evaluation lesson reuse")
            ),
        )


@dataclass(frozen=True)
class MetricComparison:
    metric_id: str
    status: str
    reason: str
    baseline_value: float | None
    candidate_value: float | None

    def __post_init__(self) -> None:
        _require_slug(self.metric_id, "metric comparison ID")
        if self.status not in {
            "improved",
            "equivalent",
            "regressed",
            "incomparable",
            "observational",
        }:
            raise PolicyViolationError("metric comparison status is invalid")
        _require_text(self.reason, "metric comparison reason", 512)
        for value in (self.baseline_value, self.candidate_value):
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                raise PolicyViolationError("metric comparison values must be finite numbers")

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "status": self.status,
            "reason": self.reason,
            "baseline_value": self.baseline_value,
            "candidate_value": self.candidate_value,
        }

    @classmethod
    def from_dict(cls, raw: Any) -> MetricComparison:
        _require_exact_fields(raw, set(cls.__dataclass_fields__), "metric comparison")
        return cls(**raw)


@dataclass(frozen=True)
class LessonReuseComparison:
    lesson_digest: str
    failed_actions_avoided_delta: int
    turns_delta: int
    wall_clock_milliseconds_delta: int
    irrelevant_matches_delta: int
    unsafe_uses_delta: int

    def __post_init__(self) -> None:
        _require_digest(self.lesson_digest, "lesson comparison digest")
        for value in (
            self.failed_actions_avoided_delta,
            self.turns_delta,
            self.wall_clock_milliseconds_delta,
            self.irrelevant_matches_delta,
            self.unsafe_uses_delta,
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise PolicyViolationError("lesson comparison deltas must be integers")

    def to_dict(self) -> dict[str, Any]:
        return {
            "lesson_digest": self.lesson_digest,
            "failed_actions_avoided_delta": self.failed_actions_avoided_delta,
            "turns_delta": self.turns_delta,
            "wall_clock_milliseconds_delta": self.wall_clock_milliseconds_delta,
            "irrelevant_matches_delta": self.irrelevant_matches_delta,
            "unsafe_uses_delta": self.unsafe_uses_delta,
        }

    @classmethod
    def from_dict(cls, raw: Any) -> LessonReuseComparison:
        _require_exact_fields(raw, set(cls.__dataclass_fields__), "lesson comparison")
        return cls(**raw)


@dataclass(frozen=True)
class ComparisonReport:
    cycle_id: str
    mode: CycleMode
    baseline_digest: str
    candidate_digest: str
    metrics: tuple[MetricComparison, ...]
    lesson_reuse: tuple[LessonReuseComparison, ...]
    verdict: ComparisonVerdict
    candidate_improved: bool
    retention_eligible: bool
    schema: str = COMPARISON_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != COMPARISON_SCHEMA:
            raise PolicyViolationError(f"comparison schema must be {COMPARISON_SCHEMA!r}")
        _require_cycle_id(self.cycle_id, "comparison cycle ID")
        if not isinstance(self.mode, CycleMode):
            raise PolicyViolationError("comparison cycle mode is invalid")
        _require_digest(self.baseline_digest, "comparison baseline digest")
        _require_digest(self.candidate_digest, "comparison candidate digest")
        if not isinstance(self.metrics, tuple) or not 1 <= len(self.metrics) <= 64:
            raise PolicyViolationError("comparison must contain 1-64 metric records")
        metric_ids = [row.metric_id for row in self.metrics]
        if metric_ids != sorted(metric_ids) or len(metric_ids) != len(set(metric_ids)):
            raise PolicyViolationError("comparison metrics must use canonical unique order")
        if not isinstance(self.lesson_reuse, tuple) or len(self.lesson_reuse) > 32:
            raise PolicyViolationError("comparison must contain at most 32 lesson records")
        lesson_ids = [row.lesson_digest for row in self.lesson_reuse]
        if lesson_ids != sorted(lesson_ids) or len(lesson_ids) != len(set(lesson_ids)):
            raise PolicyViolationError("comparison lessons must use canonical unique order")
        if not isinstance(self.verdict, ComparisonVerdict):
            raise PolicyViolationError("comparison verdict is invalid")
        if not isinstance(self.candidate_improved, bool) or not isinstance(
            self.retention_eligible, bool
        ):
            raise PolicyViolationError("comparison decision flags must be booleans")
        if self.retention_eligible and (
            self.mode is not CycleMode.IMPROVE
            or self.verdict is not ComparisonVerdict.IMPROVED
        ):
            raise PolicyViolationError("comparison retention eligibility is inconsistent")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "cycle_id": self.cycle_id,
            "mode": self.mode.value,
            "baseline_digest": self.baseline_digest,
            "candidate_digest": self.candidate_digest,
            "metrics": [row.to_dict() for row in self.metrics],
            "lesson_reuse": [row.to_dict() for row in self.lesson_reuse],
            "verdict": self.verdict.value,
            "candidate_improved": self.candidate_improved,
            "retention_eligible": self.retention_eligible,
        }

    @property
    def digest(self) -> str:
        return hashlib.sha256(_canonical_json(self.to_dict())).hexdigest()

    @classmethod
    def from_dict(cls, raw: Any) -> ComparisonReport:
        _require_exact_fields(
            raw,
            {
                "schema",
                "cycle_id",
                "mode",
                "baseline_digest",
                "candidate_digest",
                "metrics",
                "lesson_reuse",
                "verdict",
                "candidate_improved",
                "retention_eligible",
            },
            "comparison report",
        )
        try:
            mode = CycleMode(raw["mode"])
            verdict = ComparisonVerdict(raw["verdict"])
        except (TypeError, ValueError) as error:
            raise PolicyViolationError("comparison mode or verdict is invalid") from error
        return cls(
            schema=raw["schema"],
            cycle_id=raw["cycle_id"],
            mode=mode,
            baseline_digest=raw["baseline_digest"],
            candidate_digest=raw["candidate_digest"],
            metrics=tuple(
                MetricComparison.from_dict(row)
                for row in _as_list(raw["metrics"], "comparison metrics")
            ),
            lesson_reuse=tuple(
                LessonReuseComparison.from_dict(row)
                for row in _as_list(raw["lesson_reuse"], "comparison lessons")
            ),
            verdict=verdict,
            candidate_improved=raw["candidate_improved"],
            retention_eligible=raw["retention_eligible"],
        )


def compare_evaluations(
    baseline: EvaluationEvidence,
    candidate: EvaluationEvidence,
) -> ComparisonReport:
    """Compare immutable evidence without performing retention or any other mutation."""
    identity_matches = (
        baseline.cycle_id == candidate.cycle_id
        and baseline.workflow_id == candidate.workflow_id
        and baseline.mode is candidate.mode
    )
    baseline_by_id = {row.definition.id: row for row in baseline.metrics}
    candidate_by_id = {row.definition.id: row for row in candidate.metrics}
    comparisons: list[MetricComparison] = []
    all_ids = sorted(set(baseline_by_id) | set(candidate_by_id))
    for metric_id in all_ids:
        before = baseline_by_id.get(metric_id)
        after = candidate_by_id.get(metric_id)
        if not identity_matches or before is None or after is None:
            comparisons.append(
                MetricComparison(
                    metric_id,
                    "incomparable",
                    "missing or mismatched evidence",
                    None,
                    None,
                )
            )
            continue
        comparisons.append(_compare_metric(before, after))

    required_ids = {
        row.definition.id
        for row in (*baseline.metrics, *candidate.metrics)
        if row.definition.required
    }
    required = [row for row in comparisons if row.metric_id in required_ids]
    has_incomparable = any(row.status == "incomparable" for row in required)
    has_regression = any(row.status == "regressed" for row in required)
    improved = any(row.status == "improved" for row in comparisons)
    if has_incomparable:
        verdict = ComparisonVerdict.INCOMPARABLE
    elif has_regression:
        verdict = ComparisonVerdict.REGRESSED
    elif improved:
        verdict = ComparisonVerdict.IMPROVED
    else:
        verdict = ComparisonVerdict.EQUIVALENT
    eligible = baseline.mode is CycleMode.IMPROVE and verdict is ComparisonVerdict.IMPROVED
    return ComparisonReport(
        cycle_id=baseline.cycle_id,
        mode=baseline.mode,
        baseline_digest=baseline.digest,
        candidate_digest=candidate.digest,
        metrics=tuple(comparisons),
        lesson_reuse=_compare_lesson_reuse(baseline.lesson_reuse, candidate.lesson_reuse),
        verdict=verdict,
        candidate_improved=improved,
        retention_eligible=eligible,
    )


def _compare_lesson_reuse(
    baseline: tuple[LessonReuseEvidence, ...],
    candidate: tuple[LessonReuseEvidence, ...],
) -> tuple[LessonReuseComparison, ...]:
    before = {row.lesson_digest: row for row in baseline}
    after = {row.lesson_digest: row for row in candidate}
    if set(before) != set(after):
        raise PolicyViolationError("lesson reuse comparison identities differ")
    return tuple(
        LessonReuseComparison(
            lesson_digest=digest,
            failed_actions_avoided_delta=(
                after[digest].failed_actions_avoided
                - before[digest].failed_actions_avoided
            ),
            turns_delta=after[digest].turns - before[digest].turns,
            wall_clock_milliseconds_delta=(
                after[digest].wall_clock_milliseconds
                - before[digest].wall_clock_milliseconds
            ),
            irrelevant_matches_delta=(
                after[digest].irrelevant_matches - before[digest].irrelevant_matches
            ),
            unsafe_uses_delta=after[digest].unsafe_uses - before[digest].unsafe_uses,
        )
        for digest in sorted(before)
    )


def _compare_metric(before: MetricEvidence, after: MetricEvidence) -> MetricComparison:
    metric_id = before.definition.id
    if before.comparison_identity != after.comparison_identity:
        return MetricComparison(
            metric_id, "incomparable", "comparison identity differs", None, None
        )
    for row in (before, after):
        if row.graph is not None and (
            row.graph.repository_revision != row.repository_revision
            or row.graph.files == 0
            or row.graph.nodes == 0
        ):
            return MetricComparison(
                metric_id,
                "incomparable",
                "structural graph evidence is stale or empty",
                None,
                None,
            )
    if (before.graph is None) != (after.graph is None):
        return MetricComparison(metric_id, "incomparable", "graph evidence is missing", None, None)

    definition = before.definition
    if definition.kind is MetricKind.OBSERVATIONAL:
        return MetricComparison(
            metric_id,
            "observational",
            "observation has no retention authority",
            None,
            None,
        )
    if definition.kind is MetricKind.DETERMINISTIC:
        baseline_value = float(before.passes[0])
        candidate_value = float(after.passes[0])
        if not after.passes[0]:
            return MetricComparison(
                metric_id,
                "regressed",
                "candidate fails a required deterministic metric",
                baseline_value,
                candidate_value,
            )
        if not before.passes[0]:
            return MetricComparison(
                metric_id,
                "improved",
                "candidate repairs a required deterministic metric",
                baseline_value,
                candidate_value,
            )
        return MetricComparison(
            metric_id,
            "equivalent",
            "candidate and baseline pass the required deterministic metric",
            baseline_value,
            candidate_value,
        )
    else:
        maximum_failures = definition.maximum_failures or 0
        before_failures = sum(not value for value in before.passes)
        after_failures = sum(not value for value in after.passes)
        if definition.aggregation == "all-pass":
            baseline_value = 1.0 - before_failures / len(before.passes)
            candidate_value = 1.0 - after_failures / len(after.passes)
        else:
            variance_limit = float(definition.maximum_variance or 0)
            if (
                statistics.pvariance(before.values) > variance_limit
                or statistics.pvariance(after.values) > variance_limit
            ):
                return MetricComparison(
                    metric_id,
                    "incomparable",
                    "repeated metric variance exceeds its declared policy",
                    None,
                    None,
                )
            aggregate = statistics.mean if definition.aggregation == "mean" else statistics.median
            baseline_value = float(aggregate(before.values))
            candidate_value = float(aggregate(after.values))
        if after_failures > maximum_failures:
            return MetricComparison(
                metric_id,
                "regressed",
                "candidate exceeds the maximum failure count",
                baseline_value,
                candidate_value,
            )
    lower_is_better = definition.direction == "lower-is-better"
    if (candidate_value < baseline_value and not lower_is_better) or (
        candidate_value > baseline_value and lower_is_better
    ):
        status = "regressed"
        reason = "candidate value regresses the declared comparison direction"
    elif (candidate_value > baseline_value and not lower_is_better) or (
        candidate_value < baseline_value and lower_is_better
    ):
        status = "improved"
        reason = "candidate value improves the declared comparison direction"
    else:
        status = "equivalent"
        reason = "candidate and baseline are equivalent"
    return MetricComparison(metric_id, status, reason, baseline_value, candidate_value)


@dataclass(frozen=True)
class EvaluatorIdentity:
    project_id: str
    cycle_id: str
    evaluator_id: str
    mode: CycleMode
    role: str
    subject_identity: str
    repository_revision: str
    limits_digest: str
    isolation_digest: str
    controller_artifact_identity: str
    candidate_artifact_identity: str | None
    backend: str
    network: str
    schema: str = EVALUATOR_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != EVALUATOR_SCHEMA:
            raise PolicyViolationError(f"evaluator schema must be {EVALUATOR_SCHEMA!r}")
        _require_slug(self.project_id, "evaluator project ID")
        _require_cycle_id(self.cycle_id, "evaluator cycle ID")
        _require_slug(self.evaluator_id, "evaluator ID")
        if not isinstance(self.mode, CycleMode):
            raise PolicyViolationError("evaluator cycle mode is invalid")
        if self.role not in {"baseline", "candidate"}:
            raise PolicyViolationError("evaluator role must be baseline or candidate")
        _require_text(self.subject_identity, "evaluator subject identity", 512)
        _require_revision(self.repository_revision, "evaluator repository revision")
        _require_digest(self.limits_digest, "evaluator limits digest")
        _require_digest(self.isolation_digest, "evaluator isolation digest")
        _require_digest(self.controller_artifact_identity, "controller artifact identity")
        if self.role == "baseline" and self.candidate_artifact_identity is not None:
            raise PolicyViolationError("baseline evaluator cannot load a candidate artifact")
        if self.role == "candidate":
            _require_digest(self.candidate_artifact_identity, "candidate artifact identity")
            if self.candidate_artifact_identity == self.controller_artifact_identity:
                raise PolicyViolationError(
                    "candidate artifact cannot replace the controller artifact"
                )
        if self.backend != "restricted-container" or self.network != "denied-by-default":
            raise PolicyViolationError("evaluator boundary is not approved for v1")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "project_id": self.project_id,
            "cycle_id": self.cycle_id,
            "evaluator_id": self.evaluator_id,
            "mode": self.mode.value,
            "role": self.role,
            "subject_identity": self.subject_identity,
            "repository_revision": self.repository_revision,
            "limits_digest": self.limits_digest,
            "isolation_digest": self.isolation_digest,
            "controller_artifact_identity": self.controller_artifact_identity,
            "candidate_artifact_identity": self.candidate_artifact_identity,
            "backend": self.backend,
            "network": self.network,
        }

    @property
    def digest(self) -> str:
        return hashlib.sha256(_canonical_json(self.to_dict())).hexdigest()

    @classmethod
    def from_dict(cls, raw: Any) -> EvaluatorIdentity:
        _require_exact_fields(
            raw,
            {
                "schema",
                "project_id",
                "cycle_id",
                "evaluator_id",
                "mode",
                "role",
                "subject_identity",
                "repository_revision",
                "limits_digest",
                "isolation_digest",
                "controller_artifact_identity",
                "candidate_artifact_identity",
                "backend",
                "network",
            },
            "evaluator identity",
        )
        try:
            mode = CycleMode(raw["mode"])
        except (TypeError, ValueError) as error:
            raise PolicyViolationError("evaluator cycle mode is invalid") from error
        return cls(**{**raw, "mode": mode})


@dataclass(frozen=True)
class EvaluatorPaths:
    root: Path
    home: Path
    scratch: Path


@dataclass(frozen=True)
class EvaluatorIsolationEvidence:
    backend: str
    network: str
    image_identity: str
    fresh_home: bool
    network_denied: bool
    controller_credentials_absent: bool
    bounded_mounts: bool
    receipt_id: str

    def __post_init__(self) -> None:
        if self.backend != "restricted-container" or self.network != "denied-by-default":
            raise PolicyViolationError("evaluator isolation boundary is not approved for v1")
        _require_text(self.image_identity, "evaluator image identity", 256)
        _require_text(self.receipt_id, "evaluator isolation receipt ID", 256)
        checks = {
            "fresh home": self.fresh_home,
            "network denied": self.network_denied,
            "controller credentials absent": self.controller_credentials_absent,
            "bounded mounts": self.bounded_mounts,
        }
        if any(type(value) is not bool for value in checks.values()):
            raise PolicyViolationError("evaluator isolation checks must be booleans")
        missing = [label for label, passed in checks.items() if not passed]
        if missing:
            raise PolicyViolationError(
                f"evaluator isolation evidence is incomplete: {', '.join(missing)}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "network": self.network,
            "image_identity": self.image_identity,
            "fresh_home": self.fresh_home,
            "network_denied": self.network_denied,
            "controller_credentials_absent": self.controller_credentials_absent,
            "bounded_mounts": self.bounded_mounts,
            "receipt_id": self.receipt_id,
        }

    @property
    def digest(self) -> str:
        return hashlib.sha256(_canonical_json(self.to_dict())).hexdigest()


class EvaluatorWorkspace:
    """Own evaluator paths and immutable evidence below one approved registration."""

    def __init__(
        self,
        data_root: Path,
        registration: ControllerRegistration,
        isolation: EvaluatorIsolationEvidence,
    ) -> None:
        if (
            not isinstance(data_root, Path)
            or not data_root.is_absolute()
            or data_root != data_root.resolve()
        ):
            raise PolicyViolationError("evaluator data root must be an absolute resolved path")
        if not isinstance(registration, ControllerRegistration):
            raise PolicyViolationError("evaluator registration is invalid")
        if not isinstance(isolation, EvaluatorIsolationEvidence):
            raise PolicyViolationError("evaluator isolation evidence is invalid")
        if (
            isolation.backend != registration.evaluator_backend
            or isolation.network != registration.evaluator_network
        ):
            raise PolicyViolationError("evaluator isolation evidence does not match registration")
        self.data_root = data_root
        self.registration = registration
        self.isolation = isolation

    def create(self, identity: EvaluatorIdentity) -> EvaluatorPaths:
        self._validate_identity(identity)
        paths = self._paths(identity)
        paths.root.mkdir(parents=True, exist_ok=True)
        identity_path = paths.root / "identity.json"
        _write_once(identity_path, _canonical_json(identity.to_dict()), "evaluator identity")
        paths.home.mkdir(exist_ok=True)
        paths.scratch.mkdir(exist_ok=True)
        return paths

    def environment(
        self,
        identity: EvaluatorIdentity,
        inherited: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        self._validate_identity(identity)
        paths = self.create(identity)
        environment = {
            key: value
            for key, value in (inherited or {}).items()
            if key in _ALLOWED_INHERITED_ENV and isinstance(value, str)
        }
        environment.update({"HOME": str(paths.home), "HERMES_HOME": str(paths.home)})
        if identity.candidate_artifact_identity is not None:
            environment["DAIDALA_CANDIDATE_ARTIFACT"] = identity.candidate_artifact_identity
        return environment

    def record_evidence(
        self,
        identity: EvaluatorIdentity,
        evidence: EvaluationEvidence,
        *,
        baseline: bool = False,
    ) -> Path:
        self._validate_identity(identity)
        if (
            evidence.cycle_id != identity.cycle_id
            or evidence.evaluator_id != identity.evaluator_id
            or evidence.mode is not identity.mode
            or evidence.subject_identity != identity.subject_identity
        ):
            raise PolicyViolationError("evaluation evidence does not match evaluator identity")
        if any(
            row.repository_revision != identity.repository_revision
            or row.limits_digest != identity.limits_digest
            or row.environment_class != identity.backend
            for row in evidence.metrics
        ):
            raise PolicyViolationError("evaluation evidence execution identity is stale")
        paths = self.create(identity)
        evidence_path = paths.root / "evidence.json"
        _write_once(evidence_path, evidence.canonical_bytes(), "evaluation evidence")
        if baseline:
            if identity.role != "baseline":
                raise PolicyViolationError(
                    "only a baseline evaluator can record durable baseline evidence"
                )
            _write_once(
                self._cycle_root(identity) / "baseline-evidence.json",
                evidence.canonical_bytes(),
                "baseline evidence",
            )
        return evidence_path

    def create_worktree(self, identity: EvaluatorIdentity) -> Path:
        self._validate_identity(identity)
        if identity.role != "candidate":
            raise PolicyViolationError("only a candidate evaluator can own a mutation worktree")
        baseline_path = self._cycle_root(identity) / "baseline-evidence.json"
        if not baseline_path.is_file():
            raise PolicyViolationError("durable baseline evidence is required before mutation")
        baseline = _read_evaluation_evidence(baseline_path)
        baseline_identity = _read_evaluator_identity(
            self._cycle_root(identity)
            / "evaluators"
            / baseline.evaluator_id
            / "identity.json"
        )
        if (
            baseline_identity.project_id != identity.project_id
            or baseline_identity.cycle_id != identity.cycle_id
            or baseline_identity.mode is not identity.mode
            or baseline_identity.repository_revision != identity.repository_revision
            or baseline_identity.limits_digest != identity.limits_digest
            or baseline_identity.isolation_digest != identity.isolation_digest
            or baseline_identity.controller_artifact_identity
            != identity.controller_artifact_identity
            or baseline_identity.backend != identity.backend
            or baseline_identity.network != identity.network
        ):
            raise PolicyViolationError("durable baseline evidence identity is stale")
        paths = self.create(identity)
        worktree = paths.root / "worktree"
        if worktree.exists():
            head = _git(worktree, "rev-parse", "HEAD")
            status = _git(worktree, "status", "--porcelain=v1")
            if head == identity.repository_revision and not status:
                return worktree
            raise PolicyViolationError("candidate evaluator worktree is stale or dirty")
        _git(
            Path(self.registration.checkout),
            "worktree",
            "add",
            "--detach",
            str(worktree),
            identity.repository_revision,
        )
        return worktree

    def finalize(
        self,
        identity: EvaluatorIdentity,
        *,
        terminal_state: str,
        mutated: bool = False,
        ownership_ambiguous: bool = False,
    ) -> Path | None:
        self._validate_identity(identity)
        if terminal_state not in {"completed", "failed", "cancelled", "budget-exhausted"}:
            raise PolicyViolationError("evaluator terminal state is invalid")
        paths = self.create(identity)
        worktree = paths.root / "worktree"
        observed_mutation = mutated
        if worktree.exists():
            try:
                observed_mutation = observed_mutation or bool(
                    _git(worktree, "status", "--porcelain=v1")
                )
            except PolicyViolationError:
                ownership_ambiguous = True
        if terminal_state == "completed" and not observed_mutation and not ownership_ambiguous:
            if worktree.exists():
                try:
                    _git(
                        Path(self.registration.checkout),
                        "worktree",
                        "remove",
                        str(worktree),
                    )
                except PolicyViolationError:
                    ownership_ambiguous = True
            if ownership_ambiguous:
                return self._quarantine(
                    identity,
                    paths,
                    terminal_state,
                    observed_mutation,
                    ownership_ambiguous,
                )
            shutil.rmtree(paths.scratch)
            shutil.rmtree(paths.home)
            return None
        return self._quarantine(
            identity,
            paths,
            terminal_state,
            observed_mutation,
            ownership_ambiguous,
        )

    def _quarantine(
        self,
        identity: EvaluatorIdentity,
        paths: EvaluatorPaths,
        terminal_state: str,
        mutated: bool,
        ownership_ambiguous: bool,
    ) -> Path:
        quarantine = paths.root / "quarantine"
        if quarantine.exists():
            raise PolicyViolationError("evaluator quarantine already exists")
        paths.scratch.rename(quarantine)
        recovery = {
            "schema": "daidala.evaluator-recovery/v1",
            "evaluator_identity_digest": identity.digest,
            "terminal_state": terminal_state,
            "mutated": mutated,
            "ownership_ambiguous": ownership_ambiguous,
            "worktree_preserved": (paths.root / "worktree").exists(),
        }
        _write_once(quarantine / "recovery.json", _canonical_json(recovery), "recovery evidence")
        return quarantine

    def _validate_identity(self, identity: EvaluatorIdentity) -> None:
        if not isinstance(identity, EvaluatorIdentity):
            raise PolicyViolationError("evaluator identity is invalid")
        if identity.project_id != self.registration.project_id:
            raise PolicyViolationError("evaluator project does not match registration")
        if identity.isolation_digest != self.isolation.digest:
            raise PolicyViolationError("evaluator isolation receipt identity is stale")
        if (
            identity.backend != self.registration.evaluator_backend
            or identity.network != self.registration.evaluator_network
        ):
            raise PolicyViolationError("evaluator boundary does not match registration")

    def _cycle_root(self, identity: EvaluatorIdentity) -> Path:
        return self.data_root / "projects" / identity.project_id / "cycles" / identity.cycle_id

    def _paths(self, identity: EvaluatorIdentity) -> EvaluatorPaths:
        root = self._cycle_root(identity) / "evaluators" / identity.evaluator_id
        return EvaluatorPaths(root=root, home=root / "home", scratch=root / "scratch")


def _write_once(path: Path, content: bytes, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content:
            raise PolicyViolationError(f"immutable {label} conflicts at {path.name!r}")
        return
    try:
        with path.open("xb") as handle:
            handle.write(content)
    except FileExistsError as error:
        if path.read_bytes() != content:
            raise PolicyViolationError(f"immutable {label} conflicts at {path.name!r}") from error


def _read_evaluation_evidence(path: Path) -> EvaluationEvidence:
    return EvaluationEvidence.from_dict(_read_json(path, "durable baseline evidence"))


def _read_evaluator_identity(path: Path) -> EvaluatorIdentity:
    return EvaluatorIdentity.from_dict(_read_json(path, "baseline evaluator identity"))


def _read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PolicyViolationError(f"{label} is unreadable") from error


def _git(target: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(target), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise PolicyViolationError(f"evaluator Git operation failed: {error}") from error
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "Git operation failed"
        raise PolicyViolationError(f"evaluator Git operation failed: {message}")
    return result.stdout.strip()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _require_cycle_id(value: Any, label: str) -> None:
    if (
        not isinstance(value, str)
        or not value.startswith(_CYCLE_PREFIX)
        or len(value) != len(_CYCLE_PREFIX) + 64
    ):
        raise PolicyViolationError(f"{label} must be cycle- plus a SHA-256 digest")
    _require_digest(value[len(_CYCLE_PREFIX) :], label)
