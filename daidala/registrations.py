"""Trusted profile-local project registration model."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .errors import PolicyViolationError
from .projects import (
    MAX_TEXT_CHARS,
    ProjectManifest,
    _as_list,
    _as_tuple,
    _require_exact_fields,
    _require_int,
    _require_slug,
    _require_text,
    parse_strict_yaml,
)

REGISTRATION_SCHEMA = "daidala.controller-registration/v2"
MAX_REGISTRATION_BYTES = 32_768
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
_HERMES_DESTINATION = re.compile(
    r"^[a-z][a-z0-9_-]{0,63}:[^\s\x00-\x1f\x7f]{1,447}$"
)


@dataclass(frozen=True)
class RegistrationLimits:
    active_cycles: int
    goal_turns: int
    delegated_workers: int
    research_query_batches: int
    extracted_sources: int
    wall_clock_seconds: int

    def __post_init__(self) -> None:
        _require_int(self.active_cycles, "active cycles", 1, 1)
        _require_int(self.goal_turns, "goal turns", 1, 100)
        _require_int(self.delegated_workers, "delegated workers", 0, 9)
        _require_int(self.research_query_batches, "research query batches", 0, 10)
        _require_int(self.extracted_sources, "extracted sources", 0, 20)
        _require_int(self.wall_clock_seconds, "wall-clock seconds", 60, 86_400)

    def to_dict(self) -> dict[str, int]:
        return {
            "active_cycles": self.active_cycles,
            "goal_turns": self.goal_turns,
            "delegated_workers": self.delegated_workers,
            "research_query_batches": self.research_query_batches,
            "extracted_sources": self.extracted_sources,
            "wall_clock_seconds": self.wall_clock_seconds,
        }

    @classmethod
    def from_dict(cls, raw: Any) -> RegistrationLimits:
        fields = {
            "active_cycles",
            "goal_turns",
            "delegated_workers",
            "research_query_batches",
            "extracted_sources",
            "wall_clock_seconds",
        }
        _require_exact_fields(raw, fields, "registration limits")
        return cls(**{field: raw[field] for field in fields})


@dataclass(frozen=True)
class ControllerRegistration:
    project_id: str
    checkout: str
    controller_profile: str
    board: str
    repository_canonical: str
    verified_remote: str
    intake_credential: str
    findings_credential: str
    maintainers: tuple[str, ...]
    notification_adapter: str
    notification_target: str
    notification_destination: str
    evaluator_backend: str
    evaluator_network: str
    limits: RegistrationLimits
    schema: str = REGISTRATION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != REGISTRATION_SCHEMA:
            raise PolicyViolationError(f"registration schema must be {REGISTRATION_SCHEMA!r}")
        _require_slug(self.project_id, "registration project ID")
        _require_absolute_checkout(self.checkout)
        _require_slug(self.controller_profile, "controller profile")
        _require_slug(self.board, "board")
        if (
            not isinstance(self.repository_canonical, str)
            or not _REPOSITORY.fullmatch(self.repository_canonical)
        ):
            raise PolicyViolationError(
                "registration repository canonical identity must be owner/repository"
            )
        _require_text(self.verified_remote, "verified remote", 512)
        _require_slug(self.intake_credential, "intake credential alias")
        _require_slug(self.findings_credential, "findings credential alias")
        if self.intake_credential == self.findings_credential:
            raise PolicyViolationError("intake and findings credentials must use distinct aliases")
        if not isinstance(self.maintainers, tuple) or not 1 <= len(self.maintainers) <= 32:
            raise PolicyViolationError("registration maintainers must contain 1-32 identities")
        if len(self.maintainers) != len(set(self.maintainers)):
            raise PolicyViolationError("registration maintainers cannot contain duplicates")
        for maintainer in self.maintainers:
            _require_text(maintainer, "registration maintainer", MAX_TEXT_CHARS)
        if self.notification_adapter != "hermes-gateway":
            raise PolicyViolationError("notification adapter must be 'hermes-gateway'")
        _require_slug(self.notification_target, "notification target alias")
        if (
            not isinstance(self.notification_destination, str)
            or not _HERMES_DESTINATION.fullmatch(self.notification_destination)
        ):
            raise PolicyViolationError(
                "notification destination must be an explicit non-home Hermes send target"
            )
        if self.evaluator_backend != "restricted-container":
            raise PolicyViolationError("v1 evaluator backend must be 'restricted-container'")
        if self.evaluator_network != "denied-by-default":
            raise PolicyViolationError("v1 evaluator network must be 'denied-by-default'")

    def validate_manifest(self, manifest: ProjectManifest) -> None:
        if manifest.project_id != self.project_id:
            raise PolicyViolationError("registration project ID does not match manifest")
        if manifest.repository.canonical != self.repository_canonical:
            raise PolicyViolationError("registration repository identity does not match manifest")
        if self.verified_remote not in manifest.repository.allowed_remote_urls:
            raise PolicyViolationError("verified remote is not allowed by the manifest")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "project_id": self.project_id,
            "checkout": self.checkout,
            "controller_profile": self.controller_profile,
            "board": self.board,
            "repository_identity": {
                "canonical": self.repository_canonical,
                "verified_remote": self.verified_remote,
            },
            "credentials": {
                "intake": self.intake_credential,
                "findings": self.findings_credential,
            },
            "approval": {"maintainers": list(self.maintainers)},
            "notifications": {
                "adapter": self.notification_adapter,
                "target": self.notification_target,
                "destination": self.notification_destination,
            },
            "evaluator": {
                "backend": self.evaluator_backend,
                "network": self.evaluator_network,
            },
            "limits": self.limits.to_dict(),
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    @classmethod
    def from_dict(cls, raw: Any) -> ControllerRegistration:
        _require_exact_fields(
            raw,
            {
                "schema",
                "project_id",
                "checkout",
                "controller_profile",
                "board",
                "repository_identity",
                "credentials",
                "approval",
                "notifications",
                "evaluator",
                "limits",
            },
            "controller registration",
        )
        repository = raw["repository_identity"]
        credentials = raw["credentials"]
        approval = raw["approval"]
        notifications = raw["notifications"]
        evaluator = raw["evaluator"]
        _require_exact_fields(repository, {"canonical", "verified_remote"}, "repository identity")
        _require_exact_fields(credentials, {"intake", "findings"}, "credentials")
        _require_exact_fields(approval, {"maintainers"}, "approval")
        _require_exact_fields(
            notifications, {"adapter", "target", "destination"}, "notifications"
        )
        _require_exact_fields(evaluator, {"backend", "network"}, "evaluator")
        _as_list(approval["maintainers"], "registration maintainers")
        return cls(
            schema=raw["schema"],
            project_id=raw["project_id"],
            checkout=raw["checkout"],
            controller_profile=raw["controller_profile"],
            board=raw["board"],
            repository_canonical=repository["canonical"],
            verified_remote=repository["verified_remote"],
            intake_credential=credentials["intake"],
            findings_credential=credentials["findings"],
            maintainers=_as_tuple(approval["maintainers"], "registration maintainers"),
            notification_adapter=notifications["adapter"],
            notification_target=notifications["target"],
            notification_destination=notifications["destination"],
            evaluator_backend=evaluator["backend"],
            evaluator_network=evaluator["network"],
            limits=RegistrationLimits.from_dict(raw["limits"]),
        )


def parse_controller_registration(content: str) -> ControllerRegistration:
    raw = parse_strict_yaml(
        content,
        label="controller registration",
        maximum_bytes=MAX_REGISTRATION_BYTES,
    )
    return ControllerRegistration.from_dict(raw)


def registration_path(data_root: Path, project_id: str) -> Path:
    if (
        not isinstance(data_root, Path)
        or not data_root.is_absolute()
        or ".." in data_root.parts
        or "." in data_root.parts
    ):
        raise PolicyViolationError("registration data root must be an absolute resolved path")
    _require_slug(project_id, "registration project ID")
    return data_root / "projects" / project_id / "registration.yaml"


def _require_absolute_checkout(value: Any) -> None:
    _require_text(value, "registration checkout", 4096)
    if not isinstance(value, str):
        raise PolicyViolationError("registration checkout must be a string")
    path = PurePosixPath(value)
    if not path.is_absolute() or ".." in path.parts or str(path) != value:
        raise PolicyViolationError("registration checkout must be a normalized absolute POSIX path")
