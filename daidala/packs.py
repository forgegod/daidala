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
_LOWERCASE_SLUG_RE = re.compile(r"[a-z0-9][a-z0-9-]*")


class PackError(ValueError):
    """Raised when a workflow pack violates the Daidala pack contract."""


class SkillActivationMode(StrEnum):
    """Pack-owned obligation for applying one stage skill."""

    REQUIRED = "required"
    CONDITIONAL = "conditional"


@dataclass(frozen=True)
class CatalogSkill:
    name: str
    install: str | None = None
    content_digest: str | None = None
    bundled: str | None = None

    @property
    def is_external(self) -> bool:
        return self.install is not None


@dataclass(frozen=True)
class StageSkill:
    name: str
    activation: SkillActivationMode


@dataclass(frozen=True)
class Stage:
    id: str
    skills: tuple[StageSkill, ...]


@dataclass(frozen=True)
class WorkflowPack:
    name: str
    source: str
    source_revision: str
    hermes_version_constraint: str | None
    skills: tuple[CatalogSkill, ...]
    stages: tuple[Stage, ...]
    human_gate_after: str

    @property
    def lifecycle(self) -> tuple[str, ...]:
        return tuple(stage.id for stage in self.stages)

    def catalog_skill(self, name: str) -> CatalogSkill:
        """Resolve one validated stage binding to its catalog provider."""
        for skill in self.skills:
            if skill.name == name:
                return skill
        raise PackError(f"skill {name!r} is not declared by pack {self.name!r}")


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


def external_skill_install_target(pack: WorkflowPack, skill: CatalogSkill) -> str:
    """Resolve one external skill to its immutable Hermes install URL."""
    if skill.install is None:
        raise PackError(f"skill {skill.name!r} is not external")
    owner_repo = _github_owner_repo(pack.source)
    prefix = f"{owner_repo}/"
    if not skill.install.startswith(prefix):
        raise PackError(
            f"skill {skill.name!r} install target is outside pack source {owner_repo!r}"
        )
    relative_path = skill.install.removeprefix(prefix)
    if any(_LOWERCASE_SLUG_RE.fullmatch(part) is None for part in relative_path.split("/")):
        raise PackError(
            f"skill {skill.name!r} install target must use lowercase slug path segments"
        )
    return (
        f"https://raw.githubusercontent.com/{owner_repo}/"
        f"{pack.source_revision}/{relative_path}/SKILL.md"
    )


def validate_pack(raw: Any) -> WorkflowPack:
    """Validate raw YAML data and return the immutable runtime view."""
    if not isinstance(raw, dict):
        raise PackError("pack root must be a mapping")
    _reject_unknown(
        raw,
        {
            "schema_version",
            "name",
            "source",
            "source_revision",
            "hermes_version_constraint",
            "skills",
            "lifecycle",
        },
        "pack",
    )
    if raw.get("schema_version") != 2:
        raise PackError("schema_version must be 2")

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

    catalog_rows = raw.get("skills")
    if not isinstance(catalog_rows, list) or not catalog_rows:
        raise PackError("skills must be a non-empty list")
    catalog: list[CatalogSkill] = []
    catalog_by_name: dict[str, CatalogSkill] = {}
    for row in catalog_rows:
        skill = _validate_catalog_skill(row, source_owner_repo)
        if skill.name in catalog_by_name:
            raise PackError(f"duplicate catalog skill name: {skill.name}")
        catalog_by_name[skill.name] = skill
        catalog.append(skill)

    lifecycle = raw.get("lifecycle")
    if not isinstance(lifecycle, dict):
        raise PackError("lifecycle must be a mapping")
    _reject_unknown(lifecycle, {"human_gate_after", "stages"}, "lifecycle")

    human_gate_after = _required_text(lifecycle, "human_gate_after")
    stage_rows = lifecycle.get("stages")
    if not isinstance(stage_rows, list) or not stage_rows:
        raise PackError("lifecycle.stages must be a non-empty list")

    stages: list[Stage] = []
    seen: set[str] = set()
    for row in stage_rows:
        if not isinstance(row, dict):
            raise PackError("each stage must be a mapping")
        _reject_unknown(row, {"id", "skills"}, "stage")
        stage_id = _required_text(row, "id")
        if stage_id in seen:
            raise PackError(f"duplicate stage id: {stage_id}")
        seen.add(stage_id)

        skill_rows = row.get("skills")
        if not isinstance(skill_rows, list) or not skill_rows:
            raise PackError(f"stage {stage_id!r} must declare at least one skill")
        if len(skill_rows) > 32:
            raise PackError(f"stage {stage_id!r} cannot declare more than 32 skills")
        skills = tuple(_validate_stage_skill(stage_id, skill) for skill in skill_rows)
        skill_names = [skill.name for skill in skills]
        if len(set(skill_names)) != len(skill_names):
            raise PackError(f"stage {stage_id!r} contains duplicate skill bindings")
        unknown = [name for name in skill_names if name not in catalog_by_name]
        if unknown:
            raise PackError(
                f"stage {stage_id!r} references unknown catalog skill {unknown[0]!r}"
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
        skills=tuple(catalog),
        stages=tuple(stages),
        human_gate_after=human_gate_after,
    )


def _validate_catalog_skill(raw: Any, source_owner_repo: str) -> CatalogSkill:
    if not isinstance(raw, dict):
        raise PackError("catalog contains a non-mapping skill")
    _reject_unknown(raw, {"name", "install", "content_digest", "bundled"}, "catalog skill")
    name = _required_text(raw, "name")
    if _LOWERCASE_SLUG_RE.fullmatch(name) is None:
        raise PackError(f"catalog skill name must be a lowercase slug: {name!r}")
    install = raw.get("install")
    bundled = raw.get("bundled")
    if (install is None) == (bundled is None):
        raise PackError(
            f"catalog skill {name!r} must declare exactly one of install or bundled"
        )
    if bundled is not None:
        bundled = _required_text(raw, "bundled")
        if bundled != name:
            raise PackError(
                f"catalog skill {name!r} does not match bundled skill {bundled!r}"
            )
        if "content_digest" in raw:
            raise PackError(
                f"bundled catalog skill {name!r} must not declare content_digest"
            )
        return CatalogSkill(name=name, bundled=bundled)

    install = _required_text(raw, "install")
    content_digest = _required_sha256(raw, "content_digest")
    if not install.startswith(f"{source_owner_repo}/"):
        raise PackError(
            f"catalog skill {name!r} install target must start with {source_owner_repo!r}"
        )
    relative_path = install.removeprefix(f"{source_owner_repo}/")
    if any(_LOWERCASE_SLUG_RE.fullmatch(part) is None for part in relative_path.split("/")):
        raise PackError(
            f"catalog skill {name!r} install target must use "
            "lowercase slug path segments"
        )
    if install.rsplit("/", 1)[-1] != name:
        raise PackError(
            f"catalog skill {name!r} does not match install target {install!r}"
        )
    return CatalogSkill(
        name=name,
        install=install,
        content_digest=content_digest,
    )


def _validate_stage_skill(stage_id: str, raw: Any) -> StageSkill:
    if not isinstance(raw, dict):
        raise PackError(f"stage {stage_id!r} contains a non-mapping skill")
    _reject_unknown(raw, {"name", "activation"}, f"stage {stage_id!r} skill")
    name = _required_text(raw, "name")
    if _LOWERCASE_SLUG_RE.fullmatch(name) is None:
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
    return StageSkill(name=name, activation=activation)


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


def _reject_unknown(mapping: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(mapping) - allowed)
    if unknown:
        raise PackError(f"{label} contains unknown field: {unknown[0]}")
