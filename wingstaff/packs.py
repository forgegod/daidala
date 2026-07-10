"""Workflow-pack loading and deterministic validation."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from typing import Any

import yaml

__version__ = "0.1.0"
_REQUIRED_LIFECYCLE = ("define", "plan", "implement", "verify", "review", "deliver")


class PackError(ValueError):
    """Raised when a workflow pack violates the Wingstaff pack contract."""


@dataclass(frozen=True)
class SkillRef:
    name: str
    install: str


@dataclass(frozen=True)
class Stage:
    id: str
    skills: tuple[SkillRef, ...]


@dataclass(frozen=True)
class WorkflowPack:
    name: str
    source: str
    stages: tuple[Stage, ...]
    human_gate_after: str

    @property
    def lifecycle(self) -> tuple[str, ...]:
        return tuple(stage.id for stage in self.stages)


def load_pack(name: str) -> WorkflowPack:
    """Load a bundled pack by a conservative slug, then validate it."""
    if not name or not name.replace("-", "").isalnum():
        raise PackError(f"invalid pack name: {name!r}")

    resource = files(__package__).joinpath("packs", f"{name}.yaml")
    if not resource.is_file():
        raise PackError(f"unknown bundled pack: {name!r}")

    raw = yaml.safe_load(resource.read_text(encoding="utf-8"))
    return validate_pack(raw)


def validate_pack(raw: Any) -> WorkflowPack:
    """Validate raw YAML data and return the immutable runtime view."""
    if not isinstance(raw, dict):
        raise PackError("pack root must be a mapping")
    if raw.get("schema_version") != 1:
        raise PackError("schema_version must be 1")

    name = _required_text(raw, "name")
    source = _required_text(raw, "source")
    lifecycle = raw.get("lifecycle")
    if not isinstance(lifecycle, dict):
        raise PackError("lifecycle must be a mapping")

    human_gate_after = _required_text(lifecycle, "human_gate_after")
    stage_rows = lifecycle.get("stages")
    if not isinstance(stage_rows, list) or not stage_rows:
        raise PackError("lifecycle.stages must be a non-empty list")

    stages: list[Stage] = []
    seen: set[str] = set()
    for row in stage_rows:
        if not isinstance(row, dict):
            raise PackError("each stage must be a mapping")
        stage_id = _required_text(row, "id")
        if stage_id in seen:
            raise PackError(f"duplicate stage id: {stage_id}")
        seen.add(stage_id)

        skill_rows = row.get("skills")
        if not isinstance(skill_rows, list) or not skill_rows:
            raise PackError(f"stage {stage_id!r} must declare at least one skill")
        skills = tuple(_validate_skill(stage_id, skill) for skill in skill_rows)
        stages.append(Stage(id=stage_id, skills=skills))

    lifecycle_ids = tuple(stage.id for stage in stages)
    if lifecycle_ids != _REQUIRED_LIFECYCLE:
        raise PackError(
            "bootstrap lifecycle must be " + " -> ".join(_REQUIRED_LIFECYCLE)
        )
    if human_gate_after not in seen:
        raise PackError("human_gate_after must name a declared stage")
    if lifecycle_ids.index(human_gate_after) >= lifecycle_ids.index("implement"):
        raise PackError("human gate must occur before implementation")

    return WorkflowPack(
        name=name,
        source=source,
        stages=tuple(stages),
        human_gate_after=human_gate_after,
    )


def _validate_skill(stage_id: str, raw: Any) -> SkillRef:
    if not isinstance(raw, dict):
        raise PackError(f"stage {stage_id!r} contains a non-mapping skill")
    name = _required_text(raw, "name")
    install = _required_text(raw, "install")
    if install.rsplit("/", 1)[-1] != name:
        raise PackError(
            f"stage {stage_id!r} skill {name!r} does not match install target {install!r}"
        )
    return SkillRef(name=name, install=install)


def _required_text(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PackError(f"{key} must be a non-empty string")
    return value.strip()
