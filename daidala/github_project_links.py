"""Strict, credential-minimal GitHub Projects v2 link configuration."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from .credentials import credential_bindings_path, parse_credential_bindings
from .errors import PolicyViolationError
from .prerequisites import (
    PrerequisiteEvidence,
    parse_prerequisite_evidence,
    prerequisite_evidence_path,
    require_credential_capability,
)
from .profile_files import ProfileFileError, atomic_write_private_text, read_private_text
from .projects import _require_slug, parse_strict_yaml
from .registrations import ControllerRegistration

GITHUB_PROJECT_LINKS_SCHEMA = "daidala.github-project-links/v1"
GITHUB_PROJECT_LINKS_FILENAME = "github-project-links.yaml"
MAX_GITHUB_PROJECT_LINKS_BYTES = 256 * 1024
MAX_GITHUB_PROJECT_LINKS = 1024
MAX_GITHUB_OUTPUT_BYTES = 64 * 1024
GITHUB_TIMEOUT_SECONDS = 30
_INTAKE_ALLOWED = {"read-organization", "read-project", "read-public-repository"}
_OWNER = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
_GH_VERSION = re.compile(r"gh version (\d+)\.(\d+)\.(\d+)")


class GitHubProjectLinkError(PolicyViolationError):
    """Raised when a GitHub Project link cannot be safely read or changed."""


@dataclass(frozen=True)
class GitHubProjectLink:
    project_id: str
    owner: str
    project_number: int
    project_node_id: str

    def __post_init__(self) -> None:
        _require_slug(self.project_id, "GitHub Project link project ID")
        if not isinstance(self.owner, str) or not _OWNER.fullmatch(self.owner):
            raise GitHubProjectLinkError("GitHub Project owner is invalid")
        if (
            isinstance(self.project_number, bool)
            or not isinstance(self.project_number, int)
            or not 1 <= self.project_number <= 2_147_483_647
        ):
            raise GitHubProjectLinkError("GitHub Project number is invalid")
        _require_non_control_text(self.project_node_id, "GitHub Project node ID", 256)

    def to_dict(self) -> dict[str, object]:
        return {
            "project_id": self.project_id,
            "owner": self.owner,
            "project_number": self.project_number,
            "project_node_id": self.project_node_id,
        }

    @classmethod
    def from_dict(cls, raw: Any) -> GitHubProjectLink:
        if not isinstance(raw, dict) or set(raw) != {
            "project_id",
            "owner",
            "project_number",
            "project_node_id",
        }:
            raise GitHubProjectLinkError("GitHub Project link fields are invalid")
        return cls(**raw)


class GitHubProjectLinksStore:
    """The one mode-0600 link document for a controller profile."""

    def __init__(self, data_root: Path) -> None:
        if (
            not isinstance(data_root, Path)
            or not data_root.is_absolute()
            or data_root.resolve() != data_root
        ):
            raise GitHubProjectLinkError("GitHub Project links root must be absolute and resolved")
        self.path = data_root / GITHUB_PROJECT_LINKS_FILENAME

    def read(
        self, registrations: tuple[ControllerRegistration, ...]
    ) -> tuple[GitHubProjectLink, ...]:
        try:
            content = read_private_text(
                self.path,
                maximum_bytes=MAX_GITHUB_PROJECT_LINKS_BYTES,
                label="GitHub Project links",
            )
        except FileNotFoundError:
            return ()
        except ProfileFileError as error:
            raise GitHubProjectLinkError(str(error)) from error
        links = parse_github_project_links(content)
        known = {registration.project_id for registration in registrations}
        unknown = [link.project_id for link in links if link.project_id not in known]
        if unknown:
            raise GitHubProjectLinkError("GitHub Project links contain an unregistered project")
        return links

    def replace(
        self,
        links: tuple[GitHubProjectLink, ...],
        registrations: tuple[ControllerRegistration, ...],
    ) -> bool:
        _validate_links(links, registrations)
        canonical = yaml.safe_dump(
            {
                "schema": GITHUB_PROJECT_LINKS_SCHEMA,
                "links": [link.to_dict() for link in links],
            },
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )
        try:
            current = self.path.read_text(encoding="utf-8") if self.path.exists() else None
        except OSError as error:
            raise GitHubProjectLinkError("cannot read GitHub Project links") from error
        if current == canonical:
            return False
        try:
            atomic_write_private_text(self.path, canonical, label="GitHub Project links")
        except ProfileFileError as error:
            raise GitHubProjectLinkError(str(error)) from error
        return True

    def digest(self, registrations: tuple[ControllerRegistration, ...]) -> str:
        links = self.read(registrations)
        canonical = json.dumps(
            [link.to_dict() for link in links], separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()


def parse_github_project_links(content: str) -> tuple[GitHubProjectLink, ...]:
    raw = parse_strict_yaml(
        content,
        label="GitHub Project links",
        maximum_bytes=MAX_GITHUB_PROJECT_LINKS_BYTES,
    )
    if not isinstance(raw, dict) or set(raw) != {"schema", "links"}:
        raise GitHubProjectLinkError("GitHub Project links schema is invalid")
    if raw["schema"] != GITHUB_PROJECT_LINKS_SCHEMA:
        raise GitHubProjectLinkError("GitHub Project links schema is invalid")
    rows = raw["links"]
    if not isinstance(rows, list) or len(rows) > MAX_GITHUB_PROJECT_LINKS:
        raise GitHubProjectLinkError("GitHub Project links must contain at most 1024 rows")
    links = tuple(GitHubProjectLink.from_dict(row) for row in rows)
    if len({link.project_id for link in links}) != len(links):
        raise GitHubProjectLinkError("GitHub Project links cannot contain duplicate project IDs")
    return links


def _validate_links(
    links: tuple[GitHubProjectLink, ...], registrations: tuple[ControllerRegistration, ...]
) -> None:
    if len(links) > MAX_GITHUB_PROJECT_LINKS:
        raise GitHubProjectLinkError("GitHub Project links must contain at most 1024 rows")
    if len({link.project_id for link in links}) != len(links):
        raise GitHubProjectLinkError("GitHub Project links cannot contain duplicate project IDs")
    known = {registration.project_id for registration in registrations}
    if any(link.project_id not in known for link in links):
        raise GitHubProjectLinkError("GitHub Project link project is not registered")


RuntimeRunner = Callable[[tuple[str, ...], Mapping[str, str]], tuple[int, str]]


class GitHubProjectVerifier:
    """Verify only one Project v2 read with the registered intake capability."""

    def __init__(
        self,
        *,
        runner: RuntimeRunner | None = None,
        environ: Mapping[str, str] | None = None,
        current_date: date | None = None,
    ) -> None:
        self.runner = runner or _run_bounded
        self.environ = dict(os.environ if environ is None else environ)
        self.current_date = current_date or date.today()

    def preflight(self) -> None:
        code, version = self.runner(("gh", "--version"), _preflight_environment(self.environ))
        if code != 0 or not _is_supported_gh(version):
            raise GitHubProjectLinkError("GitHub CLI 2.40.0 or newer is required")
        code, help_text = self.runner(
            ("gh", "project", "view", "--help"), _preflight_environment(self.environ)
        )
        required = ("<number>", "--owner", "--format", "json")
        if code != 0 or any(token not in help_text for token in required):
            raise GitHubProjectLinkError("GitHub CLI project view command shape is unsupported")

    def verify(
        self,
        *,
        registration: ControllerRegistration,
        registration_file: Path,
        owner: str,
        project_number: int,
    ) -> tuple[GitHubProjectLink, dict[str, str]]:
        if owner != "@me" and (not isinstance(owner, str) or not _OWNER.fullmatch(owner)):
            raise GitHubProjectLinkError("GitHub Project owner is invalid")
        GitHubProjectLink(registration.project_id, "valid", project_number, "pending")
        self.preflight()
        bindings = _load_bindings(registration, registration_file)
        evidence = _load_evidence(registration, registration_file)
        require_credential_capability(
            evidence,
            alias=registration.intake_credential,
            capability="github-intake",
            allowed=_INTAKE_ALLOWED,
            current_date=self.current_date,
        )
        token = bindings.resolve(registration.intake_credential, self.environ)
        canonical_owner = self._canonical_owner(owner, token)
        environment = _github_environment(self.environ, token)
        code, output = self.runner(
            (
                "gh",
                "project",
                "view",
                str(project_number),
                "--owner",
                canonical_owner,
                "--format",
                "json",
            ),
            environment,
        )
        if code != 0 or len(output.encode("utf-8")) > MAX_GITHUB_OUTPUT_BYTES:
            raise GitHubProjectLinkError("bounded GitHub Project read failed")
        node_id, returned_number, returned_owner, url, title = _parse_project_view(output)
        if (
            returned_number != project_number
            or returned_owner.casefold() != canonical_owner.casefold()
        ):
            raise GitHubProjectLinkError("GitHub Project identity changed during verification")
        link = GitHubProjectLink(
            registration.project_id,
            returned_owner,
            returned_number,
            node_id,
        )
        return link, {"title": title, "url": url}

    def _canonical_owner(self, owner: str, token: str) -> str:
        if owner != "@me":
            return owner
        code, output = self.runner(
            ("gh", "api", "user", "--jq", ".login"),
            _github_environment(self.environ, token),
        )
        resolved = output.strip()
        if code != 0 or not _OWNER.fullmatch(resolved):
            raise GitHubProjectLinkError("cannot resolve the authenticated GitHub owner")
        return resolved


def _load_bindings(registration: ControllerRegistration, registration_file: Path):
    try:
        bindings = parse_credential_bindings(
            read_private_text(
                credential_bindings_path(registration_file),
                maximum_bytes=16_384,
                label="credential bindings",
            )
        )
    except (ProfileFileError, PolicyViolationError) as error:
        raise GitHubProjectLinkError("GitHub intake credential bindings are unavailable") from error
    if bindings.project_id != registration.project_id:
        raise GitHubProjectLinkError("GitHub intake credential bindings project does not match")
    return bindings


def _load_evidence(
    registration: ControllerRegistration, registration_file: Path
) -> PrerequisiteEvidence:
    try:
        evidence = parse_prerequisite_evidence(
            read_private_text(
                prerequisite_evidence_path(registration_file),
                maximum_bytes=64 * 1024,
                label="prerequisite evidence",
            )
        )
    except (ProfileFileError, PolicyViolationError) as error:
        raise GitHubProjectLinkError(
            "GitHub intake prerequisite evidence is unavailable"
        ) from error
    if evidence.project_id != registration.project_id:
        raise GitHubProjectLinkError("GitHub intake prerequisite evidence project does not match")
    return evidence


def _run_bounded(command: tuple[str, ...], environment: Mapping[str, str]) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            env=dict(environment),
            timeout=GITHUB_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise GitHubProjectLinkError("bounded GitHub Project command is unavailable") from error
    output = (completed.stdout + completed.stderr).strip()
    if len(output.encode("utf-8")) > MAX_GITHUB_OUTPUT_BYTES:
        raise GitHubProjectLinkError("bounded GitHub Project output exceeds 64 KiB")
    return completed.returncode, output


def _preflight_environment(environ: Mapping[str, str]) -> dict[str, str]:
    return {"PATH": environ.get("PATH", ""), "LANG": "C.UTF-8", "GIT_LOCALE": "C"}


def _github_environment(environ: Mapping[str, str], token: str) -> dict[str, str]:
    allowed = {"PATH", "HOME", "HTTPS_PROXY", "NO_PROXY"}
    result = {name: environ[name] for name in allowed if name in environ}
    result.update(
        {
            "GH_TOKEN": token,
            "GH_PROMPT_DISABLED": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "NO_COLOR": "1",
            "LANG": "C.UTF-8",
            "GIT_LOCALE": "C",
        }
    )
    return result


def _is_supported_gh(output: str) -> bool:
    match = _GH_VERSION.search(output)
    return match is not None and tuple(int(group) for group in match.groups()) >= (2, 40, 0)


def _parse_project_view(content: str) -> tuple[str, int, str, str, str]:
    try:
        raw = json.loads(content)
    except json.JSONDecodeError as error:
        raise GitHubProjectLinkError("GitHub Project returned invalid JSON") from error
    if not isinstance(raw, dict) or set(raw) != {"id", "number", "url", "title", "owner"}:
        raise GitHubProjectLinkError("GitHub Project returned an unexpected JSON shape")
    owner = raw["owner"]
    if (
        not isinstance(owner, dict)
        or set(owner) != {"login"}
        or not isinstance(owner["login"], str)
    ):
        raise GitHubProjectLinkError("GitHub Project owner is invalid")
    candidate = GitHubProjectLink("valid-project", owner["login"], raw["number"], raw["id"])
    url, title = raw["url"], raw["title"]
    if (
        not isinstance(url, str)
        or not url.startswith("https://")
        or len(url.encode("utf-8")) > 4096
    ):
        raise GitHubProjectLinkError("GitHub Project URL is invalid")
    _require_non_control_text(title, "GitHub Project title", 1024)
    return candidate.project_node_id, candidate.project_number, candidate.owner, url, title


def _require_non_control_text(value: object, label: str, maximum_bytes: int) -> None:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > maximum_bytes
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise GitHubProjectLinkError(f"{label} must be bounded non-control text")
