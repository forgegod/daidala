"""Exact skill inventory, revision checks, and install planning."""

from __future__ import annotations

import hashlib
import importlib
import json
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Protocol

from .errors import WorkflowError
from .packs import SkillRef, WorkflowPack


class SkillInventoryError(WorkflowError):
    """Raised when the host skill inventory cannot satisfy its contract."""


class MissingSkillsError(SkillInventoryError):
    """Raised when one or more exact pack skills are unavailable."""

    def __init__(self, missing: tuple[SkillRef, ...]) -> None:
        self.missing = missing
        details = "; ".join(
            f"{skill.name} (install: hermes skills install {skill.install} --yes)"
            for skill in missing
        )
        super().__init__(f"missing required skills: {details}")


class SkillRevisionError(SkillInventoryError):
    """Raised when installed skill content does not match the pinned pack."""


class SkillInventory(Protocol):
    """Host boundary for exact installed skill names."""

    def installed_names(self) -> frozenset[str]: ...


class SkillContentRegistry(Protocol):
    """Resolve deterministic content digests for installed external skills."""

    def content_digest(self, name: str) -> str | None: ...

    def skill_markdown(self, name: str) -> str | None: ...


@dataclass(frozen=True)
class HermesSkillInventory:
    """Read the active Hermes profile's skill inventory without mutation."""

    list_skills: Callable[[], str] | None = None

    def installed_names(self) -> frozenset[str]:
        list_skills = self.list_skills or _host_skills_list
        try:
            payload = json.loads(list_skills())
        except (TypeError, json.JSONDecodeError) as error:
            raise SkillInventoryError("Hermes skill inventory returned invalid JSON") from error
        if not isinstance(payload, dict) or payload.get("success") is not True:
            message = payload.get("error") if isinstance(payload, dict) else None
            raise SkillInventoryError(
                f"Hermes skill inventory failed: {message or 'unknown error'}"
            )
        rows = payload.get("skills")
        if not isinstance(rows, list):
            raise SkillInventoryError("Hermes skill inventory omitted the skills list")

        names: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                raise SkillInventoryError("Hermes skill inventory contains an invalid row")
            name = row.get("name")
            if not isinstance(name, str) or not name.strip():
                raise SkillInventoryError("Hermes skill inventory contains an invalid name")
            names.add(name.strip())
        return frozenset(names)


@dataclass(frozen=True)
class ProfileSkillContentRegistry:
    """Hash exact skill directories under one Hermes profile."""

    skills_root: Path

    def installed_names(self) -> frozenset[str]:
        return frozenset(path.parent.name for path in self.skills_root.rglob("SKILL.md"))

    def content_digest(self, name: str) -> str | None:
        candidates = self._candidates(name)
        if not candidates:
            return None
        return hash_skill_directory(candidates[0].parent)

    def skill_markdown(self, name: str) -> str | None:
        candidates = self._candidates(name)
        if not candidates:
            return None
        try:
            return candidates[0].read_text(encoding="utf-8")
        except OSError as error:
            raise SkillRevisionError(f"cannot read installed skill {name!r}") from error

    def _candidates(self, name: str) -> tuple[Path, ...]:
        candidates = tuple(self.skills_root.rglob(f"{name}/SKILL.md"))
        if len(candidates) > 1:
            raise SkillRevisionError(f"multiple installed directories provide {name!r}")
        return candidates


@dataclass(frozen=True)
class InstallAction:
    name: str
    install_target: str

    @property
    def command(self) -> tuple[str, ...]:
        return ("hermes", "skills", "install", self.install_target, "--yes")

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "install_target": self.install_target,
            "command": list(self.command),
        }


@dataclass(frozen=True)
class PackInstallPlan:
    pack: str
    source: str
    pinned_revision: str
    resolved_revision: str
    hermes_version: str
    hermes_version_constraint: str | None
    actions: tuple[InstallAction, ...]
    revision_mismatches: tuple[str, ...]
    blockers: tuple[str, ...]

    @property
    def ready_to_apply(self) -> bool:
        return not self.blockers and not self.revision_mismatches

    def to_dict(self) -> dict[str, object]:
        return {
            "pack": self.pack,
            "source": self.source,
            "pinned_revision": self.pinned_revision,
            "resolved_revision": self.resolved_revision,
            "hermes_version": self.hermes_version,
            "hermes_version_constraint": self.hermes_version_constraint,
            "actions": [action.to_dict() for action in self.actions],
            "revision_mismatches": list(self.revision_mismatches),
            "blockers": list(self.blockers),
            "ready_to_apply": self.ready_to_apply,
        }


def required_skills(pack: WorkflowPack) -> tuple[SkillRef, ...]:
    """Return exact external requirements once, preserving lifecycle order."""
    ordered: list[SkillRef] = []
    targets_by_name: dict[str, tuple[str, str]] = {}
    for stage in pack.stages:
        for skill in stage.skills:
            if not skill.is_external:
                continue
            assert skill.install is not None
            assert skill.content_digest is not None
            previous = targets_by_name.get(skill.name)
            current = (skill.install, skill.content_digest)
            if previous is None:
                targets_by_name[skill.name] = current
                ordered.append(skill)
            elif previous != current:
                raise SkillInventoryError(
                    f"skill {skill.name!r} has conflicting install targets or digests"
                )
    return tuple(ordered)


def pack_skill_digests(pack: WorkflowPack) -> tuple[tuple[str, str], ...]:
    """Return exact external and bundled skill digests in lifecycle order."""
    ordered: list[tuple[str, str]] = []
    observed: dict[str, str] = {}
    bundled_root = files(__package__).joinpath("skills")
    for stage in pack.stages:
        for skill in stage.skills:
            digest = skill.content_digest
            if skill.bundled is not None:
                digest = hash_resource_directory(bundled_root.joinpath(skill.bundled))
            if digest is None:
                raise SkillRevisionError(
                    f"skill {skill.name!r} has no deterministic content digest"
                )
            previous = observed.get(skill.name)
            if previous is None:
                observed[skill.name] = digest
                ordered.append((skill.name, digest))
            elif previous != digest:
                raise SkillRevisionError(
                    f"skill {skill.name!r} has conflicting content digests"
                )
    return tuple(ordered)


def require_pack_skills(
    pack: WorkflowPack,
    inventory: SkillInventory,
) -> tuple[SkillRef, ...]:
    """Require every exact pack skill without installing or updating anything."""
    requirements = required_skills(pack)
    installed = inventory.installed_names()
    missing = tuple(skill for skill in requirements if skill.name not in installed)
    if missing:
        raise MissingSkillsError(missing)
    return requirements


def require_pack_skill_revisions(
    pack: WorkflowPack,
    registry: SkillContentRegistry,
) -> tuple[SkillRef, ...]:
    """Require installed content to match every pinned directory digest."""
    mismatches: list[str] = []
    requirements = required_skills(pack)
    for skill in requirements:
        observed = registry.content_digest(skill.name)
        if observed != skill.content_digest:
            mismatches.append(
                f"{skill.name} (expected {skill.content_digest}, "
                f"observed {observed or 'missing'})"
            )
    if mismatches:
        raise SkillRevisionError(
            "skill revision mismatch: "
            + "; ".join(mismatches)
            + f". Plan a controlled update: wingstaff packs update-plan {pack.name}"
        )
    return requirements


def plan_pack_install(
    pack: WorkflowPack,
    inventory: SkillInventory,
    registry: SkillContentRegistry,
    *,
    resolved_revision: str,
    hermes_version: str,
    recursive: bool = False,
) -> PackInstallPlan:
    """Build a mutation-free installation plan for the pinned pack subset."""
    installed = inventory.installed_names()
    actions: list[InstallAction] = []
    mismatches: list[str] = []
    blockers: list[str] = []
    for skill in required_skills(pack):
        if skill.name not in installed:
            actions.append(InstallAction(skill.name, skill.install))
            continue
        if registry.content_digest(skill.name) != skill.content_digest:
            mismatches.append(skill.name)

    if resolved_revision != pack.source_revision:
        blockers.append(
            f"source revision mismatch: expected {pack.source_revision}, "
            f"resolved {resolved_revision}"
        )
    if pack.hermes_version_constraint and not version_satisfies(
        hermes_version, pack.hermes_version_constraint
    ):
        blockers.append(
            f"Hermes {hermes_version} does not satisfy "
            f"{pack.hermes_version_constraint}"
        )
    if recursive:
        blockers.append(
            "Hermes 0.18.2 has no recursive skill-install capability; "
            "install the required subset"
        )
    if mismatches:
        blockers.append("installed skill revisions require a controlled update plan")
    return PackInstallPlan(
        pack=pack.name,
        source=pack.source,
        pinned_revision=pack.source_revision,
        resolved_revision=resolved_revision,
        hermes_version=hermes_version,
        hermes_version_constraint=pack.hermes_version_constraint,
        actions=tuple(actions),
        revision_mismatches=tuple(mismatches),
        blockers=tuple(blockers),
    )


def hash_skill_directory(directory: Path) -> str:
    """Hash relative paths and bytes for one complete skill directory."""
    return hash_resource_directory(directory)


def hash_resource_directory(directory: Traversable) -> str:
    """Hash relative paths and bytes for a filesystem or packaged directory."""
    digest = hashlib.sha256()
    for relative, path in _walk_resource_files(directory):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _walk_resource_files(
    directory: Traversable,
    prefix: str = "",
) -> tuple[tuple[str, Traversable], ...]:
    rows: list[tuple[str, Traversable]] = []
    for child in sorted(directory.iterdir(), key=lambda item: item.name):
        relative = f"{prefix}/{child.name}" if prefix else child.name
        if child.is_file():
            rows.append((relative, child))
        elif child.is_dir():
            rows.extend(_walk_resource_files(child, relative))
    return tuple(rows)


def version_satisfies(version: str, constraint: str) -> bool:
    """Evaluate the pack's conservative >=lower,<upper host constraint."""
    match = re.fullmatch(
        r">=(\d+)\.(\d+)\.(\d+),<(\d+)\.(\d+)\.(\d+)", constraint
    )
    version_match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version)
    if match is None or version_match is None:
        return False
    current = tuple(int(part) for part in version_match.groups())
    lower = tuple(int(part) for part in match.groups()[:3])
    upper = tuple(int(part) for part in match.groups()[3:])
    return lower <= current < upper


def inventory_from_names(names: Iterable[str]) -> SkillInventory:
    """Build an immutable inventory for tests and host adapters."""
    installed = frozenset(names)

    @dataclass(frozen=True)
    class _Inventory:
        def installed_names(self) -> frozenset[str]:
            return installed

    return _Inventory()


def content_registry_from_digests(
    digests: dict[str, str],
) -> SkillContentRegistry:
    """Build an immutable content registry for deterministic tests."""
    installed = dict(digests)

    @dataclass(frozen=True)
    class _Registry:
        def content_digest(self, name: str) -> str | None:
            return installed.get(name)

        def skill_markdown(self, name: str) -> str | None:
            del name
            return None

    return _Registry()


def _host_skills_list() -> str:
    try:
        module = importlib.import_module("tools.skills_tool")
    except ImportError as error:
        raise SkillInventoryError("Hermes skill inventory is unavailable") from error
    skills_list = getattr(module, "skills_list", None)
    if not callable(skills_list):
        raise SkillInventoryError("Hermes skill inventory is unavailable")
    result = skills_list()
    if not isinstance(result, str):
        raise SkillInventoryError("Hermes skill inventory returned a non-string result")
    return result
