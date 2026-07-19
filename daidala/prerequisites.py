"""Non-mutating self-improvement prerequisite diagnosis."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from .credentials import (
    MAX_CREDENTIAL_BINDINGS_BYTES,
    CredentialBindings,
    credential_bindings_path,
    parse_credential_bindings,
)
from .errors import PolicyViolationError
from .evaluation import validate_pinned_image_identity
from .packs import load_pack, pack_content_digest
from .projects import (
    MAX_MANIFEST_BYTES,
    ProjectManifest,
    _as_list,
    _as_tuple,
    _require_digest,
    _require_exact_fields,
    _require_revision,
    _require_slug,
    _require_text,
    parse_project_manifest,
)
from .registrations import (
    MAX_REGISTRATION_BYTES,
    ControllerRegistration,
    parse_controller_registration,
)

PREREQUISITE_REPORT_SCHEMA = "daidala.prerequisite-report/v1"
PREREQUISITE_EVIDENCE_SCHEMA = "daidala.prerequisite-evidence/v1"
MAX_INPUT_BYTES = 65_536
MAX_EVIDENCE_ITEMS = 16
GUIDE_PATH = "docs/16-self-improvement-setup.md"
_REQUIRED_PROJECT_FIELDS = {
    "category",
    "priority",
    "readiness",
    "claim-owner",
    "claim-lease-expiry",
    "cycle-id",
    "workflow-id",
    "terminal-comparison-outcome",
}
_INTAKE_ALLOWED = {
    "read-organization",
    "read-project",
    "read-public-repository",
}
_FINDINGS_ALLOWED = {"metadata-read", "issues-read-write"}
_REQUIRED_DENIED = {
    "contents-write",
    "administration",
    "merge",
    "release",
    "deployment",
}
_SAFE_ENVIRONMENT_NAMES = {
    "HOME",
    "LANG",
    "LANGUAGE",
    "LC_ALL",
    "LOGNAME",
    "PATH",
    "TERM",
    "TMPDIR",
    "USER",
    "XDG_CACHE_HOME",
    "XDG_CONFIG_HOME",
    "XDG_DATA_HOME",
    "XDG_RUNTIME_DIR",
}

DoctorRunner = Callable[[tuple[str, ...], Mapping[str, str]], tuple[int, str]]


@dataclass(frozen=True)
class CheckDefinition:
    check_id: str
    name: str
    guide: str

    def to_dict(self) -> dict[str, str]:
        return {"id": self.check_id, "name": self.name, "guide": self.guide}


CHECKS = (
    CheckDefinition("SI-PROFILE", "Profile", "Sections 4-5"),
    CheckDefinition("SI-BOARD", "Board", "Section 6"),
    CheckDefinition("SI-REPOSITORY", "Repository", "Sections 1 and 9"),
    CheckDefinition("SI-PACKS", "Packs", "Section 5"),
    CheckDefinition("SI-GITHUB-INTAKE", "GitHub intake", "Sections 3.2 and 3.4"),
    CheckDefinition("SI-GITHUB-FINDINGS", "GitHub findings", "Sections 3.3 and 3.4"),
    CheckDefinition("SI-GITHUB-PROJECT", "Project", "Sections 3.1 and 8"),
    CheckDefinition("SI-NOTIFICATION", "Notification", "Section 7"),
    CheckDefinition("SI-EVALUATOR", "Evaluator", "Section 2"),
    CheckDefinition("SI-REGISTRATION", "Registration", "Section 9"),
    CheckDefinition("SI-ACTIVE-CYCLE", "Active cycle", "Section 11"),
)
_CHECK_BY_ID = {definition.check_id: definition for definition in CHECKS}
CHECKLIST_DIGEST = hashlib.sha256(
    json.dumps(
        [definition.to_dict() for definition in CHECKS],
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
).hexdigest()


class CheckStatus(StrEnum):
    PASS = "pass"
    BLOCKED = "blocked"
    NOT_RUN = "not-run"
    ERROR = "error"


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    name: str
    status: CheckStatus
    guide: str
    evidence: tuple[str, ...] = ()
    blocker: str | None = None

    def __post_init__(self) -> None:
        definition = _CHECK_BY_ID.get(self.check_id)
        if definition is None or definition.name != self.name or definition.guide != self.guide:
            raise PolicyViolationError("prerequisite result does not match the checklist registry")
        if not isinstance(self.status, CheckStatus):
            raise PolicyViolationError("prerequisite result status is invalid")
        if not isinstance(self.evidence, tuple) or len(self.evidence) > MAX_EVIDENCE_ITEMS:
            raise PolicyViolationError("prerequisite evidence exceeds its item bound")
        for row in self.evidence:
            _require_text(row, "prerequisite evidence", 512)
        if self.status is CheckStatus.PASS:
            if self.blocker is not None:
                raise PolicyViolationError("passing prerequisite result cannot contain a blocker")
        else:
            _require_text(self.blocker, "prerequisite blocker", 512)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.check_id,
            "name": self.name,
            "status": self.status.value,
            "guide": self.guide,
            "evidence": list(self.evidence),
            "blocker": self.blocker,
        }

    @classmethod
    def from_dict(cls, raw: Any) -> CheckResult:
        _require_exact_fields(
            raw,
            {"id", "name", "status", "guide", "evidence", "blocker"},
            "prerequisite result",
        )
        try:
            status = CheckStatus(raw["status"])
        except (TypeError, ValueError) as error:
            raise PolicyViolationError("prerequisite result status is invalid") from error
        return cls(
            check_id=raw["id"],
            name=raw["name"],
            status=status,
            guide=raw["guide"],
            evidence=_as_tuple(raw["evidence"], "prerequisite evidence"),
            blocker=raw["blocker"],
        )


@dataclass(frozen=True)
class PrerequisiteReport:
    live: bool
    status: CheckStatus
    checks: tuple[CheckResult, ...]
    project_id: str | None
    manifest_digest: str | None
    error: str | None = None
    schema: str = PREREQUISITE_REPORT_SCHEMA
    checklist_digest: str = CHECKLIST_DIGEST
    guide: str = GUIDE_PATH

    def __post_init__(self) -> None:
        if self.schema != PREREQUISITE_REPORT_SCHEMA:
            raise PolicyViolationError(
                f"prerequisite report schema must be {PREREQUISITE_REPORT_SCHEMA!r}"
            )
        if self.checklist_digest != CHECKLIST_DIGEST or self.guide != GUIDE_PATH:
            raise PolicyViolationError("prerequisite report checklist identity is invalid")
        if not isinstance(self.live, bool) or not isinstance(self.status, CheckStatus):
            raise PolicyViolationError("prerequisite report state is invalid")
        if self.status is CheckStatus.ERROR and not self.checks:
            if self.project_id is not None or self.manifest_digest is not None:
                raise PolicyViolationError("invalid-input report cannot assert project identity")
            _require_text(self.error, "prerequisite report error", 512)
            return
        _require_slug(self.project_id, "prerequisite report project ID")
        _require_digest(self.manifest_digest, "prerequisite report manifest digest")
        if tuple(result.check_id for result in self.checks) != tuple(
            definition.check_id for definition in CHECKS
        ):
            raise PolicyViolationError("prerequisite report must contain every check exactly once")
        expected_status = _aggregate_status(self.checks)
        if self.status is not expected_status:
            raise PolicyViolationError("prerequisite report aggregate status is inconsistent")
        if self.error is not None:
            raise PolicyViolationError(
                "valid-input prerequisite report cannot contain a top-level error"
            )

    @property
    def exit_code(self) -> int:
        if self.status is CheckStatus.PASS:
            return 0
        if self.status is CheckStatus.ERROR:
            return 1
        return 2

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "project_id": self.project_id,
            "manifest_digest": self.manifest_digest,
            "checklist_digest": self.checklist_digest,
            "guide": self.guide,
            "live": self.live,
            "status": self.status.value,
            "checks": [result.to_dict() for result in self.checks],
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, raw: Any) -> PrerequisiteReport:
        _require_exact_fields(
            raw,
            {
                "schema",
                "project_id",
                "manifest_digest",
                "checklist_digest",
                "guide",
                "live",
                "status",
                "checks",
                "error",
            },
            "prerequisite report",
        )
        try:
            status = CheckStatus(raw["status"])
        except (TypeError, ValueError) as error:
            raise PolicyViolationError("prerequisite report status is invalid") from error
        return cls(
            schema=raw["schema"],
            project_id=raw["project_id"],
            manifest_digest=raw["manifest_digest"],
            checklist_digest=raw["checklist_digest"],
            guide=raw["guide"],
            live=raw["live"],
            status=status,
            checks=tuple(
                CheckResult.from_dict(row)
                for row in _as_list(raw["checks"], "prerequisite checks")
            ),
            error=raw["error"],
        )


@dataclass(frozen=True)
class CredentialCapability:
    alias: str
    capability: str
    allowed: tuple[str, ...]
    denied: tuple[str, ...]
    expires_on: str
    read_probe_receipt: str
    write_probe_identity: str | None = None

    def __post_init__(self) -> None:
        _require_slug(self.alias, "credential capability alias")
        if self.capability not in {"github-intake", "github-findings"}:
            raise PolicyViolationError("credential capability kind is invalid")
        _require_unique_strings(self.allowed, "allowed credential capabilities")
        _require_unique_strings(self.denied, "denied credential capabilities")
        _require_text(self.expires_on, "credential expiration", 32)
        _require_text(self.read_probe_receipt, "credential read-probe receipt", 256)
        if self.write_probe_identity is not None:
            _require_text(self.write_probe_identity, "credential write-probe identity", 256)

    def to_dict(self) -> dict[str, object]:
        return {
            "alias": self.alias,
            "capability": self.capability,
            "allowed": list(self.allowed),
            "denied": list(self.denied),
            "expires_on": self.expires_on,
            "read_probe_receipt": self.read_probe_receipt,
            "write_probe_identity": self.write_probe_identity,
        }

    @classmethod
    def from_dict(cls, raw: Any) -> CredentialCapability:
        _require_exact_fields(
            raw,
            {
                "alias",
                "capability",
                "allowed",
                "denied",
                "expires_on",
                "read_probe_receipt",
                "write_probe_identity",
            },
            "credential capability",
        )
        return cls(
            alias=raw["alias"],
            capability=raw["capability"],
            allowed=_as_tuple(raw["allowed"], "allowed credential capabilities"),
            denied=_as_tuple(raw["denied"], "denied credential capabilities"),
            expires_on=raw["expires_on"],
            read_probe_receipt=raw["read_probe_receipt"],
            write_probe_identity=raw["write_probe_identity"],
        )


@dataclass(frozen=True)
class PrerequisiteEvidence:
    project_id: str
    approved_controller_revision: str
    sticky_profile: str
    credential_capabilities: tuple[CredentialCapability, ...]
    github_project: dict[str, Any] | None
    notification: dict[str, Any] | None
    evaluator: dict[str, Any] | None
    schema: str = PREREQUISITE_EVIDENCE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != PREREQUISITE_EVIDENCE_SCHEMA:
            raise PolicyViolationError(
                f"prerequisite evidence schema must be {PREREQUISITE_EVIDENCE_SCHEMA!r}"
            )
        _require_slug(self.project_id, "prerequisite evidence project ID")
        _require_revision(self.approved_controller_revision, "approved controller revision")
        _require_slug(self.sticky_profile, "sticky profile")
        aliases = [row.alias for row in self.credential_capabilities]
        if len(aliases) != len(set(aliases)):
            raise PolicyViolationError("credential capability aliases cannot repeat")
        if len(self.credential_capabilities) > 32:
            raise PolicyViolationError("credential capabilities exceed their bound")
        if self.github_project is not None:
            _require_exact_fields(
                self.github_project,
                {"owner", "project_id", "url", "fields", "read_probe_receipt"},
                "GitHub Project evidence",
            )
            _require_slug(self.github_project["owner"], "GitHub Project owner")
            _require_text(self.github_project["project_id"], "GitHub Project ID", 256)
            _require_https_url(self.github_project["url"], "GitHub Project URL")
            _require_unique_strings(
                _as_tuple(self.github_project["fields"], "GitHub Project fields"),
                "GitHub Project fields",
            )
            _require_text(
                self.github_project["read_probe_receipt"],
                "GitHub Project read-probe receipt",
                256,
            )
        if self.notification is not None:
            _require_exact_fields(
                self.notification,
                {"adapter", "target_alias", "authorized_maintainer", "receipt_id"},
                "notification evidence",
            )
            for key in ("adapter", "target_alias"):
                _require_slug(self.notification[key], f"notification {key}")
            _require_text(
                self.notification["authorized_maintainer"],
                "authorized notification maintainer",
                256,
            )
            _require_text(self.notification["receipt_id"], "notification receipt ID", 256)
        if self.evaluator is not None:
            _require_exact_fields(
                self.evaluator,
                {
                    "backend",
                    "network",
                    "image_identity",
                    "fresh_home",
                    "network_denied",
                    "controller_credentials_absent",
                    "bounded_mounts",
                    "receipt_id",
                },
                "evaluator evidence",
            )
            for key in ("backend", "network"):
                _require_slug(self.evaluator[key], f"evaluator {key}")
            validate_pinned_image_identity(self.evaluator["image_identity"])
            for key in (
                "fresh_home",
                "network_denied",
                "controller_credentials_absent",
                "bounded_mounts",
            ):
                if not isinstance(self.evaluator[key], bool):
                    raise PolicyViolationError(f"evaluator {key} must be a boolean")
            _require_text(self.evaluator["receipt_id"], "evaluator receipt ID", 256)

    @classmethod
    def from_dict(cls, raw: Any) -> PrerequisiteEvidence:
        _require_exact_fields(
            raw,
            {
                "schema",
                "project_id",
                "approved_controller_revision",
                "sticky_profile",
                "credential_capabilities",
                "github_project",
                "notification",
                "evaluator",
            },
            "prerequisite evidence",
        )
        return cls(
            schema=raw["schema"],
            project_id=raw["project_id"],
            approved_controller_revision=raw["approved_controller_revision"],
            sticky_profile=raw["sticky_profile"],
            credential_capabilities=tuple(
                CredentialCapability.from_dict(row)
                for row in _as_list(
                    raw["credential_capabilities"], "credential capabilities"
                )
            ),
            github_project=raw["github_project"],
            notification=raw["notification"],
            evaluator=raw["evaluator"],
        )


def prerequisite_evidence_path(registration_file: Path) -> Path:
    if not registration_file.is_absolute() or registration_file.name != "registration.yaml":
        raise PolicyViolationError("registration file must be an absolute registration.yaml path")
    return registration_file.parent / "prerequisite-evidence.json"


def parse_prerequisite_evidence(content: str) -> PrerequisiteEvidence:
    raw = _parse_json_object(content, "prerequisite evidence")
    return PrerequisiteEvidence.from_dict(raw)


@dataclass
class _DiagnosisContext:
    manifest_path: Path
    repository_root: Path
    manifest: ProjectManifest
    registration_path: Path | None
    registration: ControllerRegistration | None
    bindings: CredentialBindings | None
    evidence: PrerequisiteEvidence | None
    live: bool
    runner: DoctorRunner
    environ: Mapping[str, str]
    safe_environment: Mapping[str, str]
    current_date: date
    board_payload: dict[str, Any] | None = None
    results: dict[str, CheckResult] = field(default_factory=dict)


def run_prerequisite_diagnosis(
    *,
    project_manifest: Path,
    registration: Path | None = None,
    live: bool = False,
    runner: DoctorRunner | None = None,
    environ: Mapping[str, str] | None = None,
    current_date: date | None = None,
) -> PrerequisiteReport:
    selected_runner = runner or _default_runner
    selected_environ = dict(os.environ if environ is None else environ)
    try:
        manifest_path = project_manifest.expanduser().resolve(strict=True)
        manifest = parse_project_manifest(
            _read_bounded(manifest_path, "project manifest", MAX_MANIFEST_BYTES)
        )
        repository_root = (
            manifest_path.parent.parent
            if manifest_path.parent.name == ".daidala"
            else manifest_path.parent
        )
        registration_path_value: Path | None = None
        registration_value: ControllerRegistration | None = None
        bindings: CredentialBindings | None = None
        evidence: PrerequisiteEvidence | None = None
        if registration is not None:
            registration_path_value = registration.expanduser().resolve(strict=True)
            registration_value = parse_controller_registration(
                _read_bounded(
                    registration_path_value,
                    "controller registration",
                    MAX_REGISTRATION_BYTES,
                )
            )
            registration_value.validate_manifest(manifest)
            binding_file = credential_bindings_path(registration_path_value)
            evidence_file = prerequisite_evidence_path(registration_path_value)
            if binding_file.is_file():
                bindings = parse_credential_bindings(
                    _read_bounded(
                        binding_file,
                        "credential bindings",
                        MAX_CREDENTIAL_BINDINGS_BYTES,
                    )
                )
            if evidence_file.is_file():
                evidence = parse_prerequisite_evidence(
                    _read_bounded(evidence_file, "prerequisite evidence", MAX_INPUT_BYTES)
                )
            for source, label in ((bindings, "credential bindings"), (evidence, "evidence")):
                if source is not None and source.project_id != manifest.project_id:
                    raise PolicyViolationError(
                        f"prerequisite {label} project ID does not match the manifest"
                    )
        context = _DiagnosisContext(
            manifest_path=manifest_path,
            repository_root=repository_root,
            manifest=manifest,
            registration_path=registration_path_value,
            registration=registration_value,
            bindings=bindings,
            evidence=evidence,
            live=live,
            runner=selected_runner,
            environ=selected_environ,
            safe_environment=_safe_environment(selected_environ),
            current_date=current_date or date.today(),
        )
        results_list: list[CheckResult] = []
        for checker in (
            _check_profile,
            _check_board,
            _check_repository,
            _check_packs,
            _check_github_intake,
            _check_github_findings,
            _check_github_project,
            _check_notification,
            _check_evaluator,
            _check_registration,
            _check_active_cycle,
        ):
            result = checker(context)
            context.results[result.check_id] = result
            results_list.append(result)
        results = tuple(results_list)
        return PrerequisiteReport(
            live=live,
            status=_aggregate_status(results),
            checks=results,
            project_id=manifest.project_id,
            manifest_digest=manifest.digest,
        )
    except Exception as error:  # noqa: BLE001 - diagnostic process boundary
        message = str(error).strip() or type(error).__name__
        return PrerequisiteReport(
            live=live,
            status=CheckStatus.ERROR,
            checks=(),
            project_id=None,
            manifest_digest=None,
            error=f"{type(error).__name__}: {message}"[:512],
        )


def _check_profile(context: _DiagnosisContext) -> CheckResult:
    definition = _CHECK_BY_ID["SI-PROFILE"]
    if context.registration is None or context.registration_path is None:
        return _blocked(definition, "trusted registration was not provided")
    if context.evidence is None:
        return _blocked(definition, "approved controller identity evidence is missing")
    profile = context.registration.controller_profile
    profile_root = context.registration_path.parents[2]
    code, listing = context.runner(
        ("hermes", "profile", "list"), context.safe_environment
    )
    if code != 0:
        return _blocked(definition, "Hermes profile inventory is unavailable")
    active = _active_profile(listing)
    if active != context.evidence.sticky_profile or active == profile:
        return _blocked(definition, "sticky Hermes profile does not match retained evidence")
    code, shown = context.runner(
        ("hermes", "profile", "show", profile), context.safe_environment
    )
    if code != 0 or f"Path:    {profile_root}" not in shown:
        return _blocked(definition, "controller profile path is unavailable or mismatched")
    code, plugin_output = context.runner(
        ("hermes", "-p", profile, "plugins", "list", "--no-bundled", "--json"),
        context.safe_environment,
    )
    if code != 0:
        return _blocked(definition, "controller plugin inventory is unavailable")
    try:
        plugins = _parse_json_list(plugin_output, "plugin inventory")
    except PolicyViolationError as error:
        return _error(definition, str(error))
    plugin = next((row for row in plugins if row.get("name") == "daidala"), None)
    if plugin is None or plugin.get("enabled") is not True or plugin.get("error") not in {None, ""}:
        return _blocked(definition, "Daidala plugin is not enabled and healthy")
    plugin_dir = profile_root / "plugins" / "daidala"
    code, revision = context.runner(
        ("git", "-C", str(plugin_dir), "rev-parse", "HEAD"),
        context.safe_environment,
    )
    if code != 0 or revision.strip() != context.evidence.approved_controller_revision:
        return _blocked(definition, "controller plugin revision does not match approved evidence")
    code, status = context.runner(
        ("git", "-C", str(plugin_dir), "status", "--short"),
        context.safe_environment,
    )
    if code != 0 or status.strip():
        return _blocked(definition, "controller plugin checkout is unavailable or dirty")
    return _passed(
        definition,
        "controller profile exists",
        "sticky profile unchanged",
        f"controller revision {revision.strip()}",
    )


def _check_board(context: _DiagnosisContext) -> CheckResult:
    definition = _CHECK_BY_ID["SI-BOARD"]
    registration = context.registration
    if registration is None:
        return _blocked(definition, "trusted registration was not provided")
    code, output = context.runner(
        ("hermes", "kanban", "boards", "list", "--json"),
        context.safe_environment,
    )
    if code != 0:
        return _blocked(definition, "Hermes board inventory is unavailable")
    try:
        boards = _parse_json_list(output, "board inventory")
    except PolicyViolationError as error:
        return _error(definition, str(error))
    board = next((row for row in boards if row.get("slug") == registration.board), None)
    if board is None or board.get("archived") is True:
        return _blocked(definition, "registered board does not exist or is archived")
    if board.get("default_workdir") != registration.checkout:
        return _blocked(definition, "registered board workdir does not match the checkout")
    code, stats_output = context.runner(
        ("hermes", "kanban", "--board", registration.board, "stats", "--json"),
        context.safe_environment,
    )
    if code != 0:
        return _blocked(definition, "registered board statistics are unavailable")
    try:
        context.board_payload = _parse_json_dict(stats_output, "board statistics")
    except PolicyViolationError as error:
        return _error(definition, str(error))
    return _passed(definition, "board slug and workdir match", "board inventory read")


def _check_repository(context: _DiagnosisContext) -> CheckResult:
    definition = _CHECK_BY_ID["SI-REPOSITORY"]
    root = str(context.repository_root)
    code, remote = context.runner(
        ("git", "-C", root, "remote", "get-url", "origin"),
        context.safe_environment,
    )
    allowed = set(context.manifest.repository.allowed_remote_urls)
    if code != 0 or remote.strip() not in allowed:
        return _blocked(definition, "repository origin does not match the committed manifest")
    if context.registration is not None and remote.strip() != context.registration.verified_remote:
        return _blocked(definition, "repository origin does not match trusted registration")
    code, revision = context.runner(
        ("git", "-C", root, "rev-parse", "HEAD"),
        context.safe_environment,
    )
    if code != 0 or not re.fullmatch(r"[0-9a-f]{40}", revision.strip()):
        return _blocked(definition, "repository baseline revision is unavailable")
    code, status = context.runner(
        ("git", "-C", root, "status", "--porcelain"),
        context.safe_environment,
    )
    if code != 0 or status.strip():
        return _blocked(definition, "repository checkout is not clean")
    if (
        context.registration is not None
        and Path(context.registration.checkout) != context.repository_root
    ):
        return _blocked(definition, "manifest path is outside the registered checkout")
    return _passed(
        definition,
        f"canonical repository {context.manifest.repository.canonical}",
        f"baseline revision {revision.strip()}",
        "checkout clean",
    )


def _check_packs(context: _DiagnosisContext) -> CheckResult:
    definition = _CHECK_BY_ID["SI-PACKS"]
    for expected in context.manifest.allowed_packs:
        try:
            pack = load_pack(expected.name)
            digest = pack_content_digest(expected.name)
        except Exception:  # noqa: BLE001 - packaged-resource boundary
            return _blocked(definition, f"pack {expected.name!r} is unavailable")
        if pack.source_revision != expected.source_revision or digest != expected.content_digest:
            return _blocked(definition, f"pack {expected.name!r} identity does not match manifest")
    if context.registration is None:
        return _blocked(
            definition,
            "controller registration is required for native pack validation",
        )
    for expected in context.manifest.allowed_packs:
        code, _ = context.runner(
            (
                "hermes",
                "-p",
                context.registration.controller_profile,
                "daidala",
                "packs",
                "validate",
                expected.name,
            ),
            context.safe_environment,
        )
        if code != 0:
            return _blocked(definition, f"controller failed pack validation for {expected.name!r}")
    return _passed(
        definition,
        *[
            f"pack {row.name} identity valid"
            for row in context.manifest.allowed_packs
        ],
    )


def _check_github_intake(context: _DiagnosisContext) -> CheckResult:
    definition = _CHECK_BY_ID["SI-GITHUB-INTAKE"]
    if not context.live:
        return _not_run(definition, "live GitHub checks require --live")
    registration = context.registration
    if registration is None:
        return _blocked(definition, "trusted registration was not provided")
    capability = _credential_capability(
        context, registration.intake_credential, "github-intake", _INTAKE_ALLOWED
    )
    if isinstance(capability, CheckResult):
        return capability
    token = _resolve_credential(context, registration.intake_credential, definition)
    if isinstance(token, CheckResult):
        return token
    owner = context.manifest.repository.canonical.split("/", 1)[0]
    probes = (
        (
            (
                "gh", "issue", "list", "--repo", context.manifest.repository.canonical,
                "--limit", "1", "--json", "number",
            ),
            _parse_github_issue_inventory,
        ),
        (
            (
                "gh", "project", "list", "--owner", owner,
                "--limit", "100", "--format", "json",
            ),
            _parse_github_project_inventory,
        ),
    )
    for command, parser in probes:
        code, output = context.runner(command, _github_environment(context.environ, token))
        if code != 0:
            return _blocked(definition, "bounded GitHub intake read probe failed")
        try:
            parser(output)
        except PolicyViolationError as error:
            return _error(definition, str(error))
    return _passed(definition, "explicit alias binding resolved", "bounded read probes passed")


def _check_github_findings(context: _DiagnosisContext) -> CheckResult:
    definition = _CHECK_BY_ID["SI-GITHUB-FINDINGS"]
    if not context.live:
        return _not_run(definition, "live GitHub checks require --live")
    registration = context.registration
    if registration is None:
        return _blocked(definition, "trusted registration was not provided")
    capability = _credential_capability(
        context, registration.findings_credential, "github-findings", _FINDINGS_ALLOWED
    )
    if isinstance(capability, CheckResult):
        return capability
    token = _resolve_credential(context, registration.findings_credential, definition)
    if isinstance(token, CheckResult):
        return token
    command = (
        "gh", "issue", "list", "--repo", context.manifest.repository.canonical,
        "--limit", "1", "--json", "number",
    )
    code, output = context.runner(command, _github_environment(context.environ, token))
    if code != 0:
        return _blocked(definition, "bounded GitHub findings read probe failed")
    try:
        _parse_github_issue_inventory(output)
    except PolicyViolationError as error:
        return _error(definition, str(error))
    return _passed(
        definition,
        "explicit alias binding resolved",
        "bounded issue read probe passed",
        "prior controlled write probe validated",
    )


def _check_github_project(context: _DiagnosisContext) -> CheckResult:
    definition = _CHECK_BY_ID["SI-GITHUB-PROJECT"]
    if not context.live:
        return _not_run(definition, "live GitHub checks require --live")
    registration = context.registration
    evidence = context.evidence
    if registration is None or evidence is None or evidence.github_project is None:
        return _blocked(definition, "retained GitHub Project evidence is missing")
    project = evidence.github_project
    owner = context.manifest.repository.canonical.split("/", 1)[0]
    if project["owner"] != owner or set(project["fields"]) != _REQUIRED_PROJECT_FIELDS:
        return _blocked(definition, "retained GitHub Project identity or fields are incomplete")
    token = _resolve_credential(context, registration.intake_credential, definition)
    if isinstance(token, CheckResult):
        return token
    code, output = context.runner(
        ("gh", "project", "list", "--owner", owner, "--limit", "100", "--format", "json"),
        _github_environment(context.environ, token),
    )
    if code != 0:
        return _blocked(definition, "bounded GitHub Project read probe failed")
    try:
        projects = _parse_github_project_inventory(output)
    except PolicyViolationError as error:
        return _error(definition, str(error))
    if not any(
        row.get("id") == project["project_id"] and row.get("url") == project["url"]
        for row in projects
    ):
        return _blocked(definition, "retained GitHub Project identity is not present")
    return _passed(definition, "GitHub Project identity and required fields verified")


def _check_notification(context: _DiagnosisContext) -> CheckResult:
    definition = _CHECK_BY_ID["SI-NOTIFICATION"]
    if not context.live:
        return _not_run(definition, "live gateway checks require --live")
    registration = context.registration
    evidence = context.evidence
    if registration is None or evidence is None or evidence.notification is None:
        return _blocked(definition, "approved attended notification receipt is missing")
    notification = evidence.notification
    if (
        notification["adapter"] != registration.notification_adapter
        or notification["target_alias"] != registration.notification_target
        or notification["authorized_maintainer"] not in registration.maintainers
    ):
        return _blocked(definition, "notification evidence does not match registration")
    code, output = context.runner(
        ("hermes", "-p", registration.controller_profile, "gateway", "status"),
        context.safe_environment,
    )
    normalized = output.lower()
    if code != 0 or "running" not in normalized or "stopped" in normalized:
        return _blocked(definition, "controller gateway is not running")
    return _passed(definition, "gateway running", "prior attended receipt validated")


def _check_evaluator(context: _DiagnosisContext) -> CheckResult:
    definition = _CHECK_BY_ID["SI-EVALUATOR"]
    if not context.live:
        return _not_run(definition, "live container checks require --live")
    registration = context.registration
    evidence = context.evidence
    if registration is None or evidence is None or evidence.evaluator is None:
        return _blocked(definition, "approved evaluator isolation evidence is missing")
    evaluator = evidence.evaluator
    if (
        evaluator["backend"] != registration.evaluator_backend
        or evaluator["network"] != registration.evaluator_network
    ):
        return _blocked(definition, "evaluator evidence does not match registration")
    required = (
        evaluator["fresh_home"],
        evaluator["network_denied"],
        evaluator["controller_credentials_absent"],
        evaluator["bounded_mounts"],
    )
    if not all(required):
        return _blocked(definition, "evaluator isolation evidence is incomplete")
    for command in (
        ("docker", "version", "--format", "{{.Client.Version}}|{{.Server.Version}}"),
        ("docker", "network", "inspect", "none", "--format", "{{.Name}}|{{.Driver}}"),
        (
            "docker",
            "image",
            "inspect",
            evaluator["image_identity"],
            "--format",
            "{{.Id}}",
        ),
    ):
        code, _ = context.runner(command, context.safe_environment)
        if code != 0:
            return _blocked(definition, "restricted-container boundary is unavailable")
    return _passed(definition, "container boundary available", "prior isolation receipt validated")


def _check_registration(context: _DiagnosisContext) -> CheckResult:
    definition = _CHECK_BY_ID["SI-REGISTRATION"]
    if context.registration is None or context.registration_path is None:
        return _blocked(definition, "trusted registration was not provided")
    expected_path = (
        context.registration_path.parents[2]
        / "projects"
        / context.registration.project_id
        / "registration.yaml"
    )
    if context.registration_path != expected_path:
        return _blocked(definition, "registration is outside the profile-local project path")
    if context.bindings is None:
        return _blocked(definition, "profile-local credential bindings are missing")
    if context.evidence is None:
        return _blocked(definition, "retained prerequisite evidence is missing")
    dependency_ids = tuple(definition.check_id for definition in CHECKS[:9])
    incomplete = [
        check_id
        for check_id in dependency_ids
        if context.results[check_id].status is not CheckStatus.PASS
    ]
    if incomplete:
        return _blocked(
            definition,
            "registration capability checks are incomplete: " + ", ".join(incomplete),
        )
    return _passed(
        definition,
        "strict registration and manifest binding valid",
        "capability checks passed",
    )


def _check_active_cycle(context: _DiagnosisContext) -> CheckResult:
    definition = _CHECK_BY_ID["SI-ACTIVE-CYCLE"]
    registration = context.registration
    if registration is None or context.registration_path is None:
        return _blocked(definition, "trusted registration was not provided")
    payload = context.board_payload
    if payload is None:
        board = context.results.get("SI-BOARD")
        if board is not None and board.status is CheckStatus.ERROR:
            return _error(definition, "board prerequisite failed during ownership check")
        return _blocked(definition, "board ownership cannot be established")
    counts = payload.get("counts", {})
    if not isinstance(counts, dict):
        return _error(definition, "board statistics counts are invalid")
    active_statuses = {"triage", "todo", "ready", "running", "blocked", "scheduled"}
    if any(
        isinstance(counts.get(status), int) and counts.get(status, 0) > 0
        for status in active_statuses
    ):
        return _blocked(definition, "registered board has active task ownership")
    project_root = context.registration_path.parent
    cycles_root = project_root / "cycles"
    if cycles_root.is_dir() and any(cycles_root.glob("cycle-*/admission.json")):
        return _blocked(definition, "Daidala cycle admission ownership exists")
    return _passed(definition, "no board, admission, worktree, evaluator, or claim owner found")


def _credential_capability(
    context: _DiagnosisContext,
    alias: str,
    capability: str,
    allowed: set[str],
) -> CredentialCapability | CheckResult:
    definition = _CHECK_BY_ID[
        "SI-GITHUB-INTAKE" if capability == "github-intake" else "SI-GITHUB-FINDINGS"
    ]
    if context.evidence is None:
        return _blocked(definition, "retained credential capability metadata is missing")
    matches = [row for row in context.evidence.credential_capabilities if row.alias == alias]
    if len(matches) != 1:
        return _blocked(definition, "credential capability metadata does not match its alias")
    row = matches[0]
    if row.capability != capability or set(row.allowed) != allowed:
        return _blocked(definition, "credential allowed capabilities are not exact")
    if not _REQUIRED_DENIED.issubset(row.denied):
        return _blocked(definition, "credential denied capabilities are incomplete")
    try:
        expires_on = date.fromisoformat(row.expires_on)
    except ValueError:
        return _blocked(definition, "credential expiration date is invalid")
    if expires_on < context.current_date:
        return _blocked(definition, "credential capability evidence is expired")
    if capability == "github-findings" and row.write_probe_identity is None:
        return _blocked(definition, "approved controlled findings write probe is missing")
    return row


def _resolve_credential(
    context: _DiagnosisContext, alias: str, definition: CheckDefinition
) -> str | CheckResult:
    if context.bindings is None:
        return _blocked(definition, "profile-local credential bindings are missing")
    try:
        return context.bindings.resolve(alias, context.environ)
    except PolicyViolationError as error:
        return _blocked(definition, str(error))


def _safe_environment(environ: Mapping[str, str]) -> dict[str, str]:
    return {
        name: value
        for name, value in environ.items()
        if name in _SAFE_ENVIRONMENT_NAMES
    }


def _github_environment(environ: Mapping[str, str], token: str) -> dict[str, str]:
    result = _safe_environment(environ)
    if "GH_HOST" in environ:
        result["GH_HOST"] = environ["GH_HOST"]
    result["GH_TOKEN"] = token
    return result


def _active_profile(output: str) -> str | None:
    for line in output.splitlines():
        match = re.search(r"◆\s*([a-z0-9][a-z0-9-]{0,127})", line)
        if match:
            return match.group(1)
    return None


def _passed(definition: CheckDefinition, *evidence: str) -> CheckResult:
    return CheckResult(
        definition.check_id,
        definition.name,
        CheckStatus.PASS,
        definition.guide,
        tuple(evidence),
    )


def _blocked(definition: CheckDefinition, blocker: str) -> CheckResult:
    return CheckResult(
        definition.check_id,
        definition.name,
        CheckStatus.BLOCKED,
        definition.guide,
        blocker=blocker,
    )


def _not_run(definition: CheckDefinition, blocker: str) -> CheckResult:
    return CheckResult(
        definition.check_id,
        definition.name,
        CheckStatus.NOT_RUN,
        definition.guide,
        blocker=blocker,
    )


def _error(definition: CheckDefinition, blocker: str) -> CheckResult:
    return CheckResult(
        definition.check_id,
        definition.name,
        CheckStatus.ERROR,
        definition.guide,
        blocker=blocker,
    )


def _aggregate_status(checks: tuple[CheckResult, ...]) -> CheckStatus:
    statuses = {result.status for result in checks}
    if CheckStatus.ERROR in statuses:
        return CheckStatus.ERROR
    if statuses == {CheckStatus.PASS}:
        return CheckStatus.PASS
    return CheckStatus.BLOCKED


def _read_bounded(path: Path, label: str, maximum_bytes: int) -> str:
    try:
        content = path.read_bytes()
    except OSError as error:
        raise PolicyViolationError(f"cannot read {label}") from error
    if len(content) > maximum_bytes:
        raise PolicyViolationError(f"{label} exceeds {maximum_bytes} bytes")
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise PolicyViolationError(f"{label} is not UTF-8") from error


def _parse_json_object(content: str, label: str) -> dict[str, Any]:
    if len(content.encode("utf-8")) > MAX_INPUT_BYTES:
        raise PolicyViolationError(f"{label} exceeds {MAX_INPUT_BYTES} bytes")
    try:
        raw = json.loads(content)
    except json.JSONDecodeError as error:
        raise PolicyViolationError(f"invalid {label} JSON") from error
    if not isinstance(raw, dict):
        raise PolicyViolationError(f"{label} must be an object")
    return cast(dict[str, Any], raw)


def _parse_json_dict(content: str, label: str) -> dict[str, Any]:
    return _parse_json_object(content, label)


def _parse_json_list(content: str, label: str) -> list[dict[str, Any]]:
    try:
        raw = json.loads(content)
    except json.JSONDecodeError as error:
        raise PolicyViolationError(f"{label} returned invalid JSON") from error
    if not isinstance(raw, list) or any(not isinstance(row, dict) for row in raw):
        raise PolicyViolationError(f"{label} must be a JSON list of objects")
    return cast(list[dict[str, Any]], raw)


def _parse_github_project_inventory(content: str) -> list[dict[str, Any]]:
    raw = _parse_json_object(content, "GitHub Project inventory")
    _require_exact_fields(raw, {"projects", "totalCount"}, "GitHub Project inventory")
    projects = raw["projects"]
    if not isinstance(projects, list) or any(not isinstance(row, dict) for row in projects):
        raise PolicyViolationError("GitHub Project inventory projects must be a list of objects")
    if not isinstance(raw["totalCount"], int) or raw["totalCount"] < len(projects):
        raise PolicyViolationError("GitHub Project inventory totalCount is invalid")
    return cast(list[dict[str, Any]], projects)


def _parse_github_issue_inventory(content: str) -> list[dict[str, Any]]:
    issues = _parse_json_list(content, "GitHub issue inventory")
    for issue in issues:
        _require_exact_fields(issue, {"number"}, "GitHub issue inventory row")
        if not isinstance(issue["number"], int) or issue["number"] < 1:
            raise PolicyViolationError("GitHub issue inventory number is invalid")
    return issues


def _require_unique_strings(values: tuple[str, ...], label: str) -> None:
    if not isinstance(values, tuple) or not values or len(values) > 32:
        raise PolicyViolationError(f"{label} must contain 1-32 entries")
    if len(values) != len(set(values)):
        raise PolicyViolationError(f"{label} cannot contain duplicates")
    for value in values:
        _require_slug(value, label)


def _require_https_url(value: Any, label: str) -> None:
    _require_text(value, label, 2048)
    if not isinstance(value, str) or not value.startswith("https://"):
        raise PolicyViolationError(f"{label} must use HTTPS")


def _default_runner(
    command: tuple[str, ...], environment: Mapping[str, str]
) -> tuple[int, str]:
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env=dict(environment),
    )
    output = completed.stdout
    if completed.stderr:
        output += completed.stderr
    return completed.returncode, output.strip()
