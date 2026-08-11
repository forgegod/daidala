"""Typed pack validation, readiness, content, and confirmed installation service."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, replace
from importlib import resources
from typing import Any

from .locations import resolve_data_root
from .packs import SkillRef, WorkflowPack, load_pack
from .skills import (
    InstallAction,
    ProfileSkillContentRegistry,
    SkillContentRegistry,
    SkillInventory,
    pack_skill_digests,
    plan_pack_install,
)

MAX_SKILL_DOCUMENT_BYTES = 1024 * 1024
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


@dataclass(frozen=True)
class PackSkillProjection:
    name: str
    activation: str
    bundled: bool
    external: bool
    install_target: str | None
    expected_digest: str
    observed_digest: str | None
    installed: bool
    ready: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "activation": self.activation,
            "bundled": self.bundled,
            "external": self.external,
            "install_target": self.install_target,
            "expected_digest": self.expected_digest,
            "observed_digest": self.observed_digest,
            "installed": self.installed,
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
    expected_digest: str
    observed_digest: str | None
    installed: bool
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
            "expected_digest": self.expected_digest,
            "observed_digest": self.observed_digest,
            "installed": self.installed,
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


class PackService:
    """Share one deterministic pack boundary across CLI and dashboard adapters."""

    def __init__(
        self,
        *,
        inventory: SkillInventory,
        registry: SkillContentRegistry,
        revision_resolver: RevisionResolver,
        hermes_version_resolver: VersionResolver,
        command_runner: CommandRunner,
    ) -> None:
        self._inventory = inventory
        self._registry = registry
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
        stages = tuple(
            PackStageProjection(
                id=stage.id,
                skills=tuple(
                    _observed_skill(skill, expected, installed, self._registry)
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
        check = PackCheck(
            validation=validation,
            resolved_revision=resolved_revision,
            hermes_version=hermes_version,
            actions=plan.actions,
            revision_mismatches=plan.revision_mismatches,
            blockers=plan.blockers,
            installable=plan.ready_to_apply,
            ready=plan.ready_to_apply and not plan.actions,
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
        observed_digest = (
            expected_digest
            if first.bundled is not None
            else self._registry.content_digest(skill_name) if installed else None
        )
        content: str | None
        content_origin: str | None = None
        unavailable_reason: str | None = None
        if first.bundled is not None:
            resource = resources.files(__package__).joinpath(
                "skills", first.bundled, "SKILL.md"
            )
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
            unavailable_reason = (
                f"skill document exceeds {MAX_SKILL_DOCUMENT_BYTES} bytes"
            )
        return PackSkillDocument(
            pack=pack.name,
            skill=skill_name,
            source_revision=pack.source_revision,
            stages=tuple(stage for stage, _skill in declarations),
            activations=tuple(skill.activation.value for _stage, skill in declarations),
            bundled=first.bundled is not None,
            external=first.is_external,
            install_target=first.install,
            expected_digest=expected_digest,
            observed_digest=observed_digest,
            installed=installed,
            ready=installed and observed_digest == expected_digest,
            available=content is not None,
            content_origin=content_origin,
            byte_size=byte_size,
            content=content,
            unavailable_reason=unavailable_reason,
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
                    expected_digest=digests[skill.name],
                    observed_digest=(digests[skill.name] if skill.bundled is not None else None),
                    installed=skill.bundled is not None,
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
    registry: SkillContentRegistry,
) -> PackSkillProjection:
    if skill.bundled is not None:
        return expected
    installed = skill.name in installed_names
    observed = registry.content_digest(skill.name) if installed else None
    return replace(
        expected,
        observed_digest=observed,
        installed=installed,
        ready=installed and observed == expected.expected_digest,
    )


def _digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
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
