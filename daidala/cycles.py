"""Pure cycle identity and evidence schema models."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import PolicyViolationError
from .projects import (
    _as_tuple,
    _require_digest,
    _require_exact_fields,
    _require_int,
    _require_revision,
    _require_slug,
    _require_text,
)

CYCLE_SCHEMA = "daidala.cycle-identity/v1"
_DELEGATION_SCHEMA = "daidala.delegation-evidence/v1"
_LESSON_SCHEMA = "daidala.lesson-reuse-evidence/v1"
_RUN_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,255}$")


class CycleMode(StrEnum):
    IMPROVE = "improve"
    REGRESS = "regress"
    EVALUATE_PACK = "evaluate-pack"


class MetricKind(StrEnum):
    DETERMINISTIC = "deterministic"
    REPEATED = "repeated"
    OBSERVATIONAL = "observational"


class ComparisonOutcome(StrEnum):
    RETAINED = "retained"
    REVERTED = "reverted"
    REJECTED = "rejected"
    BLOCKED = "blocked"
    INCOMPARABLE = "incomparable"
    NO_CHANGE = "no-change"


@dataclass(frozen=True)
class CycleIdentity:
    project_id: str
    mode: CycleMode
    intake_adapter: str
    intake_item_id: str
    manifest_digest: str
    baseline_revision: str
    pack_name: str
    pack_source_revision: str
    pack_content_digest: str
    candidate_identity: str | None = None
    schema: str = CYCLE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != CYCLE_SCHEMA:
            raise PolicyViolationError(f"cycle schema must be {CYCLE_SCHEMA!r}")
        _require_slug(self.project_id, "cycle project ID")
        if not isinstance(self.mode, CycleMode):
            raise PolicyViolationError("cycle mode is invalid")
        _require_slug(self.intake_adapter, "cycle intake adapter")
        _require_text(self.intake_item_id, "cycle intake item ID", 512)
        _require_digest(self.manifest_digest, "cycle manifest digest")
        _require_revision(self.baseline_revision, "cycle baseline revision")
        _require_slug(self.pack_name, "cycle pack name")
        _require_revision(self.pack_source_revision, "cycle pack source revision")
        _require_digest(self.pack_content_digest, "cycle pack content digest")
        if self.candidate_identity is not None:
            _require_text(self.candidate_identity, "cycle candidate identity", 512)
        if self.mode is CycleMode.IMPROVE and self.candidate_identity is not None:
            raise PolicyViolationError("improve cycles derive the candidate after approval")
        if self.mode is not CycleMode.IMPROVE and self.candidate_identity is None:
            raise PolicyViolationError("comparison cycle modes require a candidate identity")

    @property
    def cycle_id(self) -> str:
        digest = hashlib.sha256(self.canonical_bytes()).hexdigest()
        return f"cycle-{digest}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "project_id": self.project_id,
            "mode": self.mode.value,
            "intake_adapter": self.intake_adapter,
            "intake_item_id": self.intake_item_id,
            "manifest_digest": self.manifest_digest,
            "baseline_revision": self.baseline_revision,
            "pack_name": self.pack_name,
            "pack_source_revision": self.pack_source_revision,
            "pack_content_digest": self.pack_content_digest,
            "candidate_identity": self.candidate_identity,
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")

    @classmethod
    def from_dict(cls, raw: Any) -> CycleIdentity:
        fields = {
            "schema",
            "project_id",
            "mode",
            "intake_adapter",
            "intake_item_id",
            "manifest_digest",
            "baseline_revision",
            "pack_name",
            "pack_source_revision",
            "pack_content_digest",
            "candidate_identity",
        }
        _require_exact_fields(raw, fields, "cycle identity")
        try:
            mode = CycleMode(raw["mode"])
        except (TypeError, ValueError) as error:
            raise PolicyViolationError("cycle mode is invalid") from error
        return cls(**{**raw, "mode": mode})


@dataclass(frozen=True)
class MetricDefinition:
    id: str
    kind: MetricKind
    required: bool
    repetitions: int | None = None
    maximum_failures: int | None = None
    aggregation: str | None = None

    def __post_init__(self) -> None:
        _require_slug(self.id, "metric ID")
        if not isinstance(self.kind, MetricKind):
            raise PolicyViolationError("metric kind is invalid")
        if not isinstance(self.required, bool):
            raise PolicyViolationError("metric required must be a boolean")
        if self.kind is MetricKind.DETERMINISTIC:
            repeated_values = (self.repetitions, self.maximum_failures, self.aggregation)
            if any(value is not None for value in repeated_values):
                raise PolicyViolationError("deterministic metrics do not aggregate repeated runs")
            if not self.required:
                raise PolicyViolationError("deterministic metrics must be required")
        elif self.kind is MetricKind.REPEATED:
            _require_int(self.repetitions, "metric repetitions", 2, 20)
            _require_int(self.maximum_failures, "metric maximum failures", 0, self.repetitions or 0)
            if self.aggregation not in {"all-pass", "mean", "median"}:
                raise PolicyViolationError(
                    "repeated metric aggregation must be all-pass, mean, or median"
                )
            if self.aggregation == "all-pass" and self.maximum_failures != 0:
                raise PolicyViolationError("all-pass metrics cannot allow failures")
        elif any(
            value is not None
            for value in (self.repetitions, self.maximum_failures, self.aggregation)
        ):
            raise PolicyViolationError("observational metrics cannot define retention thresholds")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "required": self.required,
            "repetitions": self.repetitions,
            "maximum_failures": self.maximum_failures,
            "aggregation": self.aggregation,
        }

    @classmethod
    def from_dict(cls, raw: Any) -> MetricDefinition:
        _require_exact_fields(
            raw,
            {"id", "kind", "required", "repetitions", "maximum_failures", "aggregation"},
            "metric definition",
        )
        try:
            kind = MetricKind(raw["kind"])
        except (TypeError, ValueError) as error:
            raise PolicyViolationError("metric kind is invalid") from error
        return cls(**{**raw, "kind": kind})


@dataclass(frozen=True)
class DelegationEvidence:
    parent_run_id: str
    child_run_id: str
    delegated_goal: str
    role: str
    toolsets: tuple[str, ...]
    model_route: str
    input_artifact_digests: tuple[str, ...]
    output_digest: str | None
    turns: int
    wall_clock_milliseconds: int
    terminal_state: str
    failure_reason: str | None = None
    schema: str = _DELEGATION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != _DELEGATION_SCHEMA:
            raise PolicyViolationError(f"delegation schema must be {_DELEGATION_SCHEMA!r}")
        for value, label in (
            (self.parent_run_id, "parent run ID"),
            (self.child_run_id, "child run ID"),
        ):
            if not isinstance(value, str) or not _RUN_ID.fullmatch(value):
                raise PolicyViolationError(f"delegation {label} is invalid")
        if self.parent_run_id == self.child_run_id:
            raise PolicyViolationError("delegation parent and child run IDs must differ")
        _require_text(self.delegated_goal, "delegated goal", 2_000)
        if self.role not in {"leaf", "orchestrator"}:
            raise PolicyViolationError("delegation role must be leaf or orchestrator")
        if not isinstance(self.toolsets, tuple) or len(self.toolsets) > 16:
            raise PolicyViolationError("delegation toolsets must contain at most 16 entries")
        if len(self.toolsets) != len(set(self.toolsets)):
            raise PolicyViolationError("delegation toolsets cannot contain duplicates")
        for toolset in self.toolsets:
            _require_slug(toolset, "delegation toolset")
        _require_text(self.model_route, "delegation model route", 512)
        if (
            not isinstance(self.input_artifact_digests, tuple)
            or len(self.input_artifact_digests) > 32
        ):
            raise PolicyViolationError("delegation inputs must contain at most 32 digests")
        if len(self.input_artifact_digests) != len(set(self.input_artifact_digests)):
            raise PolicyViolationError("delegation input artifacts cannot contain duplicates")
        for digest in self.input_artifact_digests:
            _require_digest(digest, "delegation input artifact digest")
        if self.output_digest is not None:
            _require_digest(self.output_digest, "delegation output digest")
        _require_int(self.turns, "delegation turns", 0, 1_000)
        _require_int(self.wall_clock_milliseconds, "delegation wall clock", 0, 86_400_000)
        if self.terminal_state not in {"completed", "failed", "cancelled", "budget-exhausted"}:
            raise PolicyViolationError("delegation terminal state is invalid")
        if self.terminal_state == "completed" and self.output_digest is None:
            raise PolicyViolationError("completed delegation requires an output digest")
        if self.terminal_state == "completed" and self.failure_reason is not None:
            raise PolicyViolationError("completed delegation cannot include a failure reason")
        if self.terminal_state != "completed":
            _require_text(self.failure_reason, "delegation failure reason", 1_000)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "parent_run_id": self.parent_run_id,
            "child_run_id": self.child_run_id,
            "delegated_goal": self.delegated_goal,
            "role": self.role,
            "toolsets": list(self.toolsets),
            "model_route": self.model_route,
            "input_artifact_digests": list(self.input_artifact_digests),
            "output_digest": self.output_digest,
            "turns": self.turns,
            "wall_clock_milliseconds": self.wall_clock_milliseconds,
            "terminal_state": self.terminal_state,
            "failure_reason": self.failure_reason,
        }

    @classmethod
    def from_dict(cls, raw: Any) -> DelegationEvidence:
        fields = {
            "schema",
            "parent_run_id",
            "child_run_id",
            "delegated_goal",
            "role",
            "toolsets",
            "model_route",
            "input_artifact_digests",
            "output_digest",
            "turns",
            "wall_clock_milliseconds",
            "terminal_state",
            "failure_reason",
        }
        _require_exact_fields(raw, fields, "delegation evidence")
        return cls(
            **{
                **raw,
                "toolsets": _as_tuple(raw["toolsets"], "delegation toolsets"),
                "input_artifact_digests": _as_tuple(
                    raw["input_artifact_digests"], "delegation input artifacts"
                ),
            }
        )


@dataclass(frozen=True)
class LessonReuseEvidence:
    lesson_digest: str
    applicable: bool
    failed_actions_avoided: int
    recovery_outcome: str
    turns: int
    wall_clock_milliseconds: int
    irrelevant_matches: int
    unsafe_uses: int
    schema: str = _LESSON_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != _LESSON_SCHEMA:
            raise PolicyViolationError(f"lesson schema must be {_LESSON_SCHEMA!r}")
        _require_digest(self.lesson_digest, "lesson digest")
        if not isinstance(self.applicable, bool):
            raise PolicyViolationError("lesson applicability must be a boolean")
        for value, label, maximum in (
            (self.failed_actions_avoided, "failed actions avoided", 1_000),
            (self.turns, "lesson turns", 1_000),
            (self.wall_clock_milliseconds, "lesson wall clock", 86_400_000),
            (self.irrelevant_matches, "irrelevant matches", 10_000),
            (self.unsafe_uses, "unsafe uses", 10_000),
        ):
            _require_int(value, label, 0, maximum)
        if self.recovery_outcome not in {"not-needed", "recovered", "failed", "blocked"}:
            raise PolicyViolationError("lesson recovery outcome is invalid")
        if not self.applicable and self.failed_actions_avoided:
            raise PolicyViolationError("an inapplicable lesson cannot claim avoided actions")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "lesson_digest": self.lesson_digest,
            "applicable": self.applicable,
            "failed_actions_avoided": self.failed_actions_avoided,
            "recovery_outcome": self.recovery_outcome,
            "turns": self.turns,
            "wall_clock_milliseconds": self.wall_clock_milliseconds,
            "irrelevant_matches": self.irrelevant_matches,
            "unsafe_uses": self.unsafe_uses,
        }

    @classmethod
    def from_dict(cls, raw: Any) -> LessonReuseEvidence:
        _require_exact_fields(raw, set(cls.__dataclass_fields__), "lesson reuse evidence")
        return cls(**raw)
