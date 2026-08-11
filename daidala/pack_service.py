"""Typed pack validation, readiness, content, and confirmed installation service."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import StrEnum
from importlib import resources
from pathlib import Path
from typing import Any, Protocol

import yaml

from .locations import resolve_data_root
from .packs import SkillRef, WorkflowPack, load_pack
from .profile_files import ProfileFileError, atomic_write_private_text, read_private_text
from .skills import (
    InstallAction,
    ProfileSkillContentRegistry,
    SkillContentRegistry,
    SkillInventory,
    pack_skill_digests,
    plan_pack_install,
)

MAX_SKILL_DOCUMENT_BYTES = 1024 * 1024
MAX_PROFILE_CONFIG_BYTES = 1024 * 1024
BUNDLED_SKILL_NAMESPACE = "daidala"
BUNDLED_SKILL_SOURCE_BASE = "https://github.com/forgegod/daidala/tree/main/daidala/skills"
CommandRunner = Callable[[tuple[str, ...]], tuple[int, str]]
RevisionResolver = Callable[[WorkflowPack], str]
VersionResolver = Callable[[], str]


class PackServiceError(RuntimeError):
    """Base error for bounded pack operations."""


class UnknownPackSkillError(PackServiceError):
    """Raised when a content request does not name a declared pack skill."""


class PackConfirmationError(PackServiceError):
    """Raised when an installation request lacks literal confirmation."""


class StalePackPreviewError(PackServiceError):
    """Raised when current pack readiness no longer matches the reviewed preview."""


class PackInstallError(PackServiceError):
    """Raised when a confirmed installation cannot complete and verify."""


class PackActionError(PackServiceError):
    """Raised when a confirmed pack skill action cannot complete and verify."""


class SkillAction(StrEnum):
    """Closed pack-skill mutations exposed to the dashboard."""

    INSTALL = "install"
    ENABLE = "enable"
    DISABLE = "disable"


class SkillAvailabilityState(Protocol):
    """Profile-global enabled state using Hermes' skills.disabled contract."""

    def disabled_names(self) -> frozenset[str]: ...

    def set_enabled(self, names: tuple[str, ...], *, enabled: bool) -> None: ...


class ProfileSkillAvailabilityState:
    """Bounded profile-config adapter matching the Hermes Skills dashboard toggle."""

    def __init__(self, config_path: Path) -> None:
        self._config_path = config_path

    def disabled_names(self) -> frozenset[str]:
        return self._disabled_from(self._read_config())

    @staticmethod
    def _disabled_from(config: dict[str, Any]) -> frozenset[str]:
        skills = config.get("skills") or {}
        if not isinstance(skills, dict):
            raise PackServiceError("Hermes skills config must be a mapping")
        values = skills.get("disabled")
        if values is None:
            return frozenset()
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, list) or any(
            not isinstance(name, str) or not name.strip() for name in values
        ):
            raise PackServiceError("Hermes disabled skill state must be a string list")
        return frozenset(name.strip() for name in values)

    def set_enabled(self, names: tuple[str, ...], *, enabled: bool) -> None:
        config = self._read_config()
        skills = config.setdefault("skills", {})
        if not isinstance(skills, dict):
            raise PackActionError("Hermes skills config must be a mapping")
        disabled = set(self._disabled_from(config))
        if enabled:
            disabled.difference_update(names)
        else:
            disabled.update(names)
        skills["disabled"] = sorted(disabled)
        try:
            atomic_write_private_text(
                self._config_path,
                yaml.safe_dump(config, sort_keys=False),
                label="Hermes profile config",
            )
        except ProfileFileError as error:
            raise PackActionError("Hermes disabled skill state cannot be saved") from error
        observed = self.disabled_names()
        if any((name in observed) != (not enabled) for name in names):
            raise PackActionError("Hermes disabled skill update failed post-verification")

    def _read_config(self) -> dict[str, Any]:
        try:
            content = read_private_text(
                self._config_path,
                maximum_bytes=MAX_PROFILE_CONFIG_BYTES,
                label="Hermes profile config",
            )
        except FileNotFoundError:
            return {}
        except ProfileFileError as error:
            raise PackServiceError("Hermes profile config cannot be read") from error
        try:
            config = yaml.safe_load(content) or {}
        except yaml.YAMLError as error:
            raise PackServiceError("Hermes profile config is not valid YAML") from error
        if not isinstance(config, dict):
            raise PackServiceError("Hermes profile config must be a mapping")
        return config


@dataclass(frozen=True)
class PackSkillProjection:
    name: str
    activation: str
    bundled: bool
    external: bool
    install_target: str | None
    source_url: str
    expected_digest: str
    observed_digest: str | None
    installed: bool
    enabled: bool | None
    ready: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "activation": self.activation,
            "bundled": self.bundled,
            "external": self.external,
            "install_target": self.install_target,
            "source_url": self.source_url,
            "expected_digest": self.expected_digest,
            "observed_digest": self.observed_digest,
            "installed": self.installed,
            "enabled": self.enabled,
            "ready": self.ready,
        }


@dataclass(frozen=True)
class PackStageProjection:
    id: str
    skills: tuple[PackSkillProjection, ...]

    def to_dict(self) -> dict[str, object]:
        return {"id": self.id, "skills": [skill.to_dict() for skill in self.skills]}


@dataclass(frozen=True)
class PackValidation:
    name: str
    source: str
    source_revision: str
    hermes_version_constraint: str | None
    lifecycle: tuple[str, ...]
    human_gate_after: str
    stages: tuple[PackStageProjection, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "source": self.source,
            "source_revision": self.source_revision,
            "hermes_version_constraint": self.hermes_version_constraint,
            "lifecycle": list(self.lifecycle),
            "human_gate_after": self.human_gate_after,
            "stages": [stage.to_dict() for stage in self.stages],
        }


@dataclass(frozen=True)
class PackCheck:
    validation: PackValidation
    resolved_revision: str
    hermes_version: str
    actions: tuple[InstallAction, ...]
    revision_mismatches: tuple[str, ...]
    blockers: tuple[str, ...]
    activation_blockers: tuple[str, ...]
    installable: bool
    ready: bool
    preview_digest: str

    def identity_dict(self) -> dict[str, object]:
        return {
            **self.validation.to_dict(),
            "resolved_revision": self.resolved_revision,
            "hermes_version": self.hermes_version,
            "actions": [action.to_dict() for action in self.actions],
            "revision_mismatches": list(self.revision_mismatches),
            "blockers": list(self.blockers),
            "activation_blockers": list(self.activation_blockers),
            "installable": self.installable,
            "ready": self.ready,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self.identity_dict(), "preview_digest": self.preview_digest}


@dataclass(frozen=True)
class PackSkillDocument:
    pack: str
    skill: str
    source_revision: str
    stages: tuple[str, ...]
    activations: tuple[str, ...]
    bundled: bool
    external: bool
    install_target: str | None
    source_url: str
    expected_digest: str
    observed_digest: str | None
    installed: bool
    enabled: bool | None
    ready: bool
    available: bool
    content_origin: str | None
    byte_size: int | None
    content: str | None
    unavailable_reason: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "pack": self.pack,
            "skill": self.skill,
            "source_revision": self.source_revision,
            "stages": list(self.stages),
            "activation": list(self.activations),
            "bundled": self.bundled,
            "external": self.external,
            "install_target": self.install_target,
            "source_url": self.source_url,
            "expected_digest": self.expected_digest,
            "observed_digest": self.observed_digest,
            "installed": self.installed,
            "enabled": self.enabled,
            "ready": self.ready,
            "available": self.available,
            "content_origin": self.content_origin,
            "byte_size": self.byte_size,
            "content": self.content,
            "unavailable_reason": self.unavailable_reason,
        }


@dataclass(frozen=True)
class ExecutedInstall:
    name: str
    command: tuple[str, ...]
    exit_code: int

    def to_dict(self) -> dict[str, object]:
        return {"name": self.name, "command": list(self.command), "exit_code": self.exit_code}


@dataclass(frozen=True)
class PackInstallResult:
    applied_preview_digest: str
    executed: tuple[ExecutedInstall, ...]
    pack: PackCheck

    def to_dict(self) -> dict[str, object]:
        return {
            "success": True,
            "applied_preview_digest": self.applied_preview_digest,
            "executed": [row.to_dict() for row in self.executed],
            "pack": self.pack.to_dict(),
        }


@dataclass(frozen=True)
class PackSkillActionPreview:
    action: SkillAction
    pack_name: str
    skill_name: str | None
    skills: tuple[str, ...]
    blockers: tuple[str, ...]
    pack: PackCheck
    preview_digest: str

    def identity_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "action": self.action.value,
            "pack_name": self.pack_name,
            "skill_name": self.skill_name,
            "skills": list(self.skills),
            "blockers": list(self.blockers),
            "pack": self.pack.identity_dict(),
        }

    def to_dict(self) -> dict[str, object]:
        return {
            **self.identity_dict(),
            "applicable": bool(self.skills) and not self.blockers,
            "preview_digest": self.preview_digest,
        }


@dataclass(frozen=True)
class PackSkillActionResult:
    action: SkillAction
    applied_preview_digest: str
    affected: tuple[str, ...]
    executed: tuple[ExecutedInstall, ...]
    pack: PackCheck

    def to_dict(self) -> dict[str, object]:
        return {
            "success": True,
            "action": self.action.value,
            "applied_preview_digest": self.applied_preview_digest,
            "affected": list(self.affected),
            "executed": [row.to_dict() for row in self.executed],
            "pack": self.pack.to_dict(),
        }


class PackService:
    """Share one deterministic pack boundary across CLI and dashboard adapters."""

    def __init__(
        self,
        *,
        inventory: SkillInventory,
        registry: SkillContentRegistry,
        skill_state: SkillAvailabilityState | None = None,
        revision_resolver: RevisionResolver,
        hermes_version_resolver: VersionResolver,
        command_runner: CommandRunner,
    ) -> None:
        self._inventory = inventory
        self._registry = registry
        self._skill_state = skill_state or ProfileSkillAvailabilityState(
            resolve_data_root() / "config.yaml"
        )
        self._revision_resolver = revision_resolver
        self._hermes_version_resolver = hermes_version_resolver
        self._command_runner = command_runner

    @classmethod
    def from_default_profile(cls) -> PackService:
        registry = ProfileSkillContentRegistry(resolve_data_root() / "skills")
        return cls(
            inventory=registry,
            registry=registry,
            revision_resolver=_resolve_revision,
            hermes_version_resolver=lambda: _resolve_hermes_version(_run_command),
            command_runner=_run_command,
        )

    @staticmethod
    def bundled_names() -> tuple[str, ...]:
        root = resources.files(__package__).joinpath("packs")
        return tuple(
            sorted(
                item.name.removesuffix(".yaml")
                for item in root.iterdir()
                if item.name.endswith(".yaml")
            )
        )

    @staticmethod
    def validate(name: str) -> PackValidation:
        return _validation(load_pack(name))

    def check(self, name: str, *, recursive: bool = False) -> PackCheck:
        pack = load_pack(name)
        validation = _validation(pack)
        installed = self._inventory.installed_names()
        disabled = self._skill_state.disabled_names()
        stages = tuple(
            PackStageProjection(
                id=stage.id,
                skills=tuple(
                    _observed_skill(skill, expected, installed, disabled, self._registry)
                    for skill, expected in zip(
                        stage.skills, validation.stages[index].skills, strict=True
                    )
                ),
            )
            for index, stage in enumerate(pack.stages)
        )
        validation = replace(validation, stages=stages)
        resolved_revision = self._revision_resolver(pack)
        hermes_version = self._hermes_version_resolver()
        plan = plan_pack_install(
            pack,
            self._inventory,
            self._registry,
            resolved_revision=resolved_revision,
            hermes_version=hermes_version,
            recursive=recursive,
        )
        activation_blockers = _activation_blockers(pack, installed, disabled)
        check = PackCheck(
            validation=validation,
            resolved_revision=resolved_revision,
            hermes_version=hermes_version,
            actions=plan.actions,
            revision_mismatches=plan.revision_mismatches,
            blockers=(*plan.blockers, *activation_blockers),
            activation_blockers=activation_blockers,
            installable=plan.ready_to_apply,
            ready=plan.ready_to_apply and not plan.actions and not activation_blockers,
            preview_digest="",
        )
        return replace(check, preview_digest=_digest(check.identity_dict()))

    def skill_content(self, pack_name: str, skill_name: str) -> PackSkillDocument:
        pack = load_pack(pack_name)
        declarations = tuple(
            (stage.id, skill)
            for stage in pack.stages
            for skill in stage.skills
            if skill.name == skill_name
        )
        if not declarations:
            raise UnknownPackSkillError(
                f"skill {skill_name!r} is not declared by pack {pack_name!r}"
            )
        first = declarations[0][1]
        expected_digest = dict(pack_skill_digests(pack))[skill_name]
        installed_names = self._inventory.installed_names()
        installed = first.bundled is not None or skill_name in installed_names
        availability_name = _availability_name(first)
        enabled = installed and availability_name not in self._skill_state.disabled_names()
        observed_digest = (
            expected_digest
            if first.bundled is not None
            else self._registry.content_digest(skill_name)
            if installed
            else None
        )
        content: str | None
        content_origin: str | None = None
        unavailable_reason: str | None = None
        if first.bundled is not None:
            resource = resources.files(__package__).joinpath("skills", first.bundled, "SKILL.md")
            content = resource.read_text(encoding="utf-8")
            content_origin = "bundled"
        elif installed:
            content = self._registry.skill_markdown(skill_name)
            if content is not None:
                content_origin = "installed"
        else:
            content = None
        if content is None and first.is_external:
            unavailable_reason = (
                "skill document is unavailable" if installed else "skill is not installed"
            )
        byte_size = len(content.encode("utf-8")) if content is not None else None
        if byte_size is not None and byte_size > MAX_SKILL_DOCUMENT_BYTES:
            content = None
            unavailable_reason = f"skill document exceeds {MAX_SKILL_DOCUMENT_BYTES} bytes"
        return PackSkillDocument(
            pack=pack.name,
            skill=skill_name,
            source_revision=pack.source_revision,
            stages=tuple(stage for stage, _skill in declarations),
            activations=tuple(skill.activation.value for _stage, skill in declarations),
            bundled=first.bundled is not None,
            external=first.is_external,
            install_target=first.install,
            source_url=_skill_source_url(pack, first),
            expected_digest=expected_digest,
            observed_digest=observed_digest,
            installed=installed,
            enabled=enabled if installed else None,
            ready=installed and enabled and observed_digest == expected_digest,
            available=content is not None,
            content_origin=content_origin,
            byte_size=byte_size,
            content=content,
            unavailable_reason=unavailable_reason,
        )

    def preview_action(
        self,
        name: str,
        action: SkillAction,
        *,
        skill_name: str | None = None,
    ) -> PackSkillActionPreview:
        pack = load_pack(name)
        declared = _declared_skills(pack)
        if skill_name is not None and skill_name not in declared:
            raise UnknownPackSkillError(f"skill {skill_name!r} is not declared by pack {name!r}")
        current = self.check(name)
        projections = _skill_projections(current)
        blockers: list[str] = []

        if action is SkillAction.INSTALL:
            install_actions = {row.name: row for row in current.actions}
            names = tuple(
                skill
                for skill in declared
                if skill in install_actions and (skill_name is None or skill == skill_name)
            )
            blockers.extend(
                blocker
                for blocker in current.blockers
                if blocker not in current.activation_blockers
            )
            if skill_name is not None and declared[skill_name].bundled is not None:
                blockers.append(f"bundled skill {skill_name!r} has no install action")
        elif action is SkillAction.ENABLE:
            names = tuple(
                skill
                for skill in declared
                if projections[skill].installed
                and projections[skill].enabled is False
                and (skill_name is None or skill == skill_name)
            )
            if skill_name is not None and not projections[skill_name].installed:
                blockers.append(f"skill {skill_name!r} is not installed")
        elif action is SkillAction.DISABLE:
            names = tuple(
                skill
                for skill in declared
                if projections[skill].installed
                and projections[skill].enabled is True
                and (skill_name is None or skill == skill_name)
            )
            if skill_name is not None and not projections[skill_name].installed:
                blockers.append(f"skill {skill_name!r} is not installed")
        else:  # pragma: no cover - SkillAction is closed, defensive for Python callers.
            raise PackActionError(f"unsupported pack skill action: {action!r}")

        preview = PackSkillActionPreview(
            action=action,
            pack_name=name,
            skill_name=skill_name,
            skills=names,
            blockers=tuple(blockers),
            pack=current,
            preview_digest="",
        )
        return replace(preview, preview_digest=_digest(preview.identity_dict()))

    def apply_action(
        self,
        name: str,
        action: SkillAction,
        *,
        expected_preview_digest: str,
        confirm: bool,
        skill_name: str | None = None,
    ) -> PackSkillActionResult:
        if confirm is not True:
            raise PackConfirmationError("explicit pack skill action confirmation is required")
        preview = self.preview_action(name, action, skill_name=skill_name)
        if preview.preview_digest != expected_preview_digest:
            raise StalePackPreviewError("pack skill action inputs changed after preview")
        if preview.blockers:
            raise PackActionError("pack skill action preview is blocked")
        if not preview.skills:
            raise PackActionError("pack skill action has no applicable skills")

        executed: list[ExecutedInstall] = []
        if action is SkillAction.INSTALL:
            actions = {row.name: row for row in preview.pack.actions}
            for skill in preview.skills:
                install = actions[skill]
                exit_code, _output = self._command_runner(install.command)
                executed.append(ExecutedInstall(skill, install.command, exit_code))
                if exit_code != 0:
                    raise PackActionError(
                        f"skill installation failed for {skill!r} with exit {exit_code}"
                    )
        else:
            declared = _declared_skills(load_pack(name))
            self._skill_state.set_enabled(
                tuple(_availability_name(declared[skill]) for skill in preview.skills),
                enabled=action is SkillAction.ENABLE,
            )

        verified = self.check(name)
        projections = _skill_projections(verified)
        if action is SkillAction.INSTALL:
            converged = all(
                projections[skill].installed
                and projections[skill].observed_digest == projections[skill].expected_digest
                for skill in preview.skills
            )
        else:
            expected_enabled = action is SkillAction.ENABLE
            converged = all(
                projections[skill].enabled is expected_enabled for skill in preview.skills
            )
        if not converged:
            raise PackActionError("pack skill action failed post-verification")
        return PackSkillActionResult(
            action=action,
            applied_preview_digest=expected_preview_digest,
            affected=preview.skills,
            executed=tuple(executed),
            pack=verified,
        )

    def install(
        self,
        name: str,
        *,
        expected_preview_digest: str,
        confirm: bool,
    ) -> PackInstallResult:
        if confirm is not True:
            raise PackConfirmationError("explicit installation confirmation is required")
        current = self.check(name)
        if current.preview_digest != expected_preview_digest:
            raise StalePackPreviewError("pack installation inputs changed after preview")
        if not current.actions:
            raise PackInstallError("pack has no external skill installation actions")
        if not current.installable:
            raise PackInstallError("pack installation preview is blocked")

        executed: list[ExecutedInstall] = []
        for action in current.actions:
            exit_code, _output = self._command_runner(action.command)
            row = ExecutedInstall(action.name, action.command, exit_code)
            executed.append(row)
            if exit_code != 0:
                raise PackInstallError(
                    f"skill installation failed for {action.name!r} with exit {exit_code}"
                )
        verified = self.check(name)
        if not verified.ready:
            raise PackInstallError("pack installation did not pass post-install verification")
        return PackInstallResult(
            applied_preview_digest=expected_preview_digest,
            executed=tuple(executed),
            pack=verified,
        )


def _validation(pack: WorkflowPack) -> PackValidation:
    digests = dict(pack_skill_digests(pack))
    stages = tuple(
        PackStageProjection(
            id=stage.id,
            skills=tuple(
                PackSkillProjection(
                    name=skill.name,
                    activation=skill.activation.value,
                    bundled=skill.bundled is not None,
                    external=skill.is_external,
                    install_target=skill.install,
                    source_url=_skill_source_url(pack, skill),
                    expected_digest=digests[skill.name],
                    observed_digest=(digests[skill.name] if skill.bundled is not None else None),
                    installed=skill.bundled is not None,
                    enabled=True if skill.bundled is not None else None,
                    ready=skill.bundled is not None,
                )
                for skill in stage.skills
            ),
        )
        for stage in pack.stages
    )
    return PackValidation(
        name=pack.name,
        source=pack.source,
        source_revision=pack.source_revision,
        hermes_version_constraint=pack.hermes_version_constraint,
        lifecycle=pack.lifecycle,
        human_gate_after=pack.human_gate_after,
        stages=stages,
    )


def _observed_skill(
    skill: SkillRef,
    expected: PackSkillProjection,
    installed_names: frozenset[str],
    disabled_names: frozenset[str],
    registry: SkillContentRegistry,
) -> PackSkillProjection:
    availability_name = _availability_name(skill)
    if skill.bundled is not None:
        enabled = availability_name not in disabled_names
        return replace(expected, enabled=enabled, ready=enabled)
    installed = skill.name in installed_names
    enabled = installed and availability_name not in disabled_names
    observed = registry.content_digest(skill.name) if installed else None
    return replace(
        expected,
        observed_digest=observed,
        installed=installed,
        enabled=enabled if installed else None,
        ready=installed and enabled and observed == expected.expected_digest,
    )


def _activation_blockers(
    pack: WorkflowPack,
    installed_names: frozenset[str],
    disabled_names: frozenset[str],
) -> tuple[str, ...]:
    blockers: list[str] = []
    seen: set[str] = set()
    for stage in pack.stages:
        for skill in stage.skills:
            installed = skill.bundled is not None or skill.name in installed_names
            if (
                skill.name in seen
                or not installed
                or _availability_name(skill) not in disabled_names
            ):
                continue
            seen.add(skill.name)
            blockers.append(f"{skill.activation.value} skill {skill.name!r} is disabled")
    return tuple(blockers)


def _declared_skills(pack: WorkflowPack) -> dict[str, SkillRef]:
    declared: dict[str, SkillRef] = {}
    for stage in pack.stages:
        for skill in stage.skills:
            declared.setdefault(skill.name, skill)
    return declared


def _skill_projections(check: PackCheck) -> dict[str, PackSkillProjection]:
    projections: dict[str, PackSkillProjection] = {}
    for stage in check.validation.stages:
        for skill in stage.skills:
            projections.setdefault(skill.name, skill)
    return projections


def _availability_name(skill: SkillRef) -> str:
    if skill.bundled is not None:
        return f"{BUNDLED_SKILL_NAMESPACE}:{skill.name}"
    return skill.name


def _skill_source_url(pack: WorkflowPack, skill: SkillRef) -> str:
    if skill.bundled is not None:
        return f"{BUNDLED_SKILL_SOURCE_BASE}/{skill.bundled}"
    assert skill.install is not None
    path = "/".join(skill.install.split("/")[2:])
    source = pack.source.removesuffix(".git").rstrip("/")
    return f"{source}/tree/{pack.source_revision}/{path}"


def _digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _resolve_revision(pack: WorkflowPack) -> str:
    completed = subprocess.run(
        ("git", "ls-remote", pack.source, "HEAD"),
        check=False,
        capture_output=True,
        text=True,
    )
    revision = completed.stdout.strip().split("\t", 1)[0]
    if completed.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise PackServiceError(f"could not resolve source revision for pack {pack.name!r}")
    return revision


def _resolve_hermes_version(runner: CommandRunner) -> str:
    code, output = runner(("hermes", "--version"))
    match = re.search(r"Hermes Agent v(\d+\.\d+\.\d+)", output)
    if code != 0 or match is None:
        raise PackServiceError("could not resolve Hermes semantic version")
    return match.group(1)


def _run_command(command: tuple[str, ...]) -> tuple[int, str]:
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    output = completed.stdout
    if completed.stderr:
        output += completed.stderr
    return completed.returncode, output.strip()
