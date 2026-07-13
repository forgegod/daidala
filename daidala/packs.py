"""Workflow-pack loading and deterministic validation."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import StrEnum
from importlib.resources import files
from typing import Any
from urllib.parse import urlparse

import yaml

__version__ = "0.2.0"
_REQUIRED_LIFECYCLE = ("define", "plan", "implement", "verify", "review", "deliver")


class PackError(ValueError):
    """Raised when a workflow pack violates the Daidala pack contract."""


class SkillActivationMode(StrEnum):
    """Pack-owned obligation for applying one stage skill."""

    REQUIRED = "required"
    CONDITIONAL = "conditional"


@dataclass(frozen=True)
class SkillRef:
    name: str
    activation: SkillActivationMode
    install: str | None = None
    content_digest: str | None = None
    bundled: str | None = None

    @property
    def is_external(self) -> bool:
        return self.install is not None


@dataclass(frozen=True)
class Stage:
    id: str
    skills: tuple[SkillRef, ...]


@dataclass(frozen=True)
class WorkflowPack:
    name: str
    source: str
    source_revision: str
    hermes_version_constraint: str | None
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


def pack_content_digest(name: str) -> str:
    """Return the SHA-256 digest of the exact bundled pack resource bytes."""
    if not name or not name.replace("-", "").isalnum():
        raise PackError(f"invalid pack name: {name!r}")
    resource = files(__package__).joinpath("packs", f"{name}.yaml")
    if not resource.is_file():
        raise PackError(f"unknown bundled pack: {name!r}")
    return hashlib.sha256(resource.read_bytes()).hexdigest()


def validate_pack(raw: Any) -> WorkflowPack:
    """Validate raw YAML data and return the immutable runtime view."""
    if not isinstance(raw, dict):
        raise PackError("pack root must be a mapping")
    if raw.get("schema_version") != 1:
        raise PackError("schema_version must be 1")

    name = _required_text(raw, "name")
    source = _required_text(raw, "source")
    source_owner_repo = _github_owner_repo(source)
    source_revision = _required_sha256(raw, "source_revision", length=40)
    hermes_version_constraint = raw.get("hermes_version_constraint")
    if hermes_version_constraint is not None:
        if not isinstance(hermes_version_constraint, str) or not re.fullmatch(
            r">=\d+\.\d+\.\d+,<\d+\.\d+\.\d+", hermes_version_constraint
        ):
            raise PackError(
                "hermes_version_constraint must use >=X.Y.Z,<X.Y.Z format"
            )
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
        if len(skill_rows) > 32:
            raise PackError(f"stage {stage_id!r} cannot declare more than 32 skills")
        skills = tuple(
            _validate_skill(stage_id, skill, source_owner_repo) for skill in skill_rows
        )
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
        source_revision=source_revision,
        hermes_version_constraint=hermes_version_constraint,
        stages=tuple(stages),
        human_gate_after=human_gate_after,
    )


def _validate_skill(stage_id: str, raw: Any, source_owner_repo: str) -> SkillRef:
    if not isinstance(raw, dict):
        raise PackError(f"stage {stage_id!r} contains a non-mapping skill")
    name = _required_text(raw, "name")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
        raise PackError(
            f"stage {stage_id!r} skill name must be a lowercase slug: {name!r}"
        )
    activation_raw = _required_text(raw, "activation")
    try:
        activation = SkillActivationMode(activation_raw)
    except ValueError as error:
        raise PackError(
            f"stage {stage_id!r} skill {name!r} activation must be required or conditional"
        ) from error
    install = raw.get("install")
    bundled = raw.get("bundled")
    if (install is None) == (bundled is None):
        raise PackError(
            f"stage {stage_id!r} skill {name!r} must declare exactly one of "
            "install or bundled"
        )
    if bundled is not None:
        bundled = _required_text(raw, "bundled")
        if bundled != name:
            raise PackError(
                f"stage {stage_id!r} skill {name!r} does not match bundled skill "
                f"{bundled!r}"
            )
        if "content_digest" in raw:
            raise PackError(
                f"stage {stage_id!r} bundled skill {name!r} must not declare "
                "content_digest"
            )
        return SkillRef(name=name, activation=activation, bundled=bundled)

    install = _required_text(raw, "install")
    content_digest = _required_sha256(raw, "content_digest")
    if not install.startswith(f"{source_owner_repo}/"):
        raise PackError(
            f"stage {stage_id!r} skill {name!r} install target must start with "
            f"{source_owner_repo!r}"
        )
    if install.rsplit("/", 1)[-1] != name:
        raise PackError(
            f"stage {stage_id!r} skill {name!r} does not match install target {install!r}"
        )
    return SkillRef(
        name=name,
        activation=activation,
        install=install,
        content_digest=content_digest,
    )


def _github_owner_repo(source: str) -> str:
    parsed = urlparse(source)
    parts = [part for part in parsed.path.removesuffix(".git").split("/") if part]
    if (
        parsed.scheme != "https"
        or parsed.netloc.lower() != "github.com"
        or len(parts) != 2
        or parsed.query
        or parsed.fragment
    ):
        raise PackError("source must be an HTTPS GitHub owner/repository URL")
    return "/".join(parts)


def _required_sha256(
    mapping: dict[str, Any], key: str, *, length: int = 64
) -> str:
    value = _required_text(mapping, key)
    if not re.fullmatch(rf"[0-9a-f]{{{length}}}", value):
        raise PackError(f"{key} must be a {length}-character lowercase hex digest")
    return value


def _required_text(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PackError(f"{key} must be a non-empty string")
    return value.strip()
