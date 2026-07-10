"""Read-only exact skill inventory checks for workflow packs."""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
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
            f"{skill.name} (install: {skill.install})" for skill in missing
        )
        super().__init__(f"missing required skills: {details}")


class SkillInventory(Protocol):
    """Host boundary for exact installed skill names."""

    def installed_names(self) -> frozenset[str]: ...


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


def required_skills(pack: WorkflowPack) -> tuple[SkillRef, ...]:
    """Return exact requirements once, preserving first lifecycle order."""
    ordered: list[SkillRef] = []
    targets_by_name: dict[str, str] = {}
    for stage in pack.stages:
        for skill in stage.skills:
            previous = targets_by_name.get(skill.name)
            if previous is None:
                targets_by_name[skill.name] = skill.install
                ordered.append(skill)
            elif previous != skill.install:
                raise SkillInventoryError(
                    f"skill {skill.name!r} has conflicting install targets: "
                    f"{previous!r} and {skill.install!r}"
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


def inventory_from_names(names: Iterable[str]) -> SkillInventory:
    """Build an immutable inventory for tests and host adapters."""
    installed = frozenset(names)

    @dataclass(frozen=True)
    class _Inventory:
        def installed_names(self) -> frozenset[str]:
            return installed

    return _Inventory()


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
