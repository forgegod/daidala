"""Strict profile-local credential alias bindings.

Bindings contain resolver metadata only. Secret values are resolved from the
process environment immediately before a bounded adapter call.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import PolicyViolationError
from .projects import (
    _as_list,
    _require_exact_fields,
    _require_slug,
    parse_strict_yaml,
)

CREDENTIAL_BINDINGS_SCHEMA = "daidala.credential-bindings/v1"
MAX_CREDENTIAL_BINDINGS_BYTES = 16_384
_ENVIRONMENT_VARIABLE = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")


@dataclass(frozen=True)
class CredentialBinding:
    alias: str
    resolver: str
    environment_variable: str

    def __post_init__(self) -> None:
        _require_slug(self.alias, "credential alias")
        if self.resolver != "environment":
            raise PolicyViolationError("credential binding resolver must be 'environment'")
        if (
            not isinstance(self.environment_variable, str)
            or not _ENVIRONMENT_VARIABLE.fullmatch(self.environment_variable)
        ):
            raise PolicyViolationError(
                "credential binding environment variable must be an explicit uppercase name"
            )
        if self.environment_variable == "GH_TOKEN":
            raise PolicyViolationError(
                "credential bindings must use an alias-specific environment variable, not GH_TOKEN"
            )

    def to_dict(self) -> dict[str, str]:
        return {
            "alias": self.alias,
            "resolver": self.resolver,
            "environment_variable": self.environment_variable,
        }

    @classmethod
    def from_dict(cls, raw: Any) -> CredentialBinding:
        _require_exact_fields(
            raw,
            {"alias", "resolver", "environment_variable"},
            "credential binding",
        )
        return cls(
            alias=raw["alias"],
            resolver=raw["resolver"],
            environment_variable=raw["environment_variable"],
        )


@dataclass(frozen=True)
class CredentialBindings:
    project_id: str
    bindings: tuple[CredentialBinding, ...]
    schema: str = CREDENTIAL_BINDINGS_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != CREDENTIAL_BINDINGS_SCHEMA:
            raise PolicyViolationError(
                f"credential bindings schema must be {CREDENTIAL_BINDINGS_SCHEMA!r}"
            )
        _require_slug(self.project_id, "credential bindings project ID")
        if not isinstance(self.bindings, tuple) or not 1 <= len(self.bindings) <= 32:
            raise PolicyViolationError("credential bindings must contain 1-32 entries")
        aliases = [binding.alias for binding in self.bindings]
        variables = [binding.environment_variable for binding in self.bindings]
        if len(aliases) != len(set(aliases)):
            raise PolicyViolationError("credential bindings cannot contain duplicate aliases")
        if len(variables) != len(set(variables)):
            raise PolicyViolationError(
                "credential bindings cannot reuse an environment variable"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "project_id": self.project_id,
            "bindings": [binding.to_dict() for binding in self.bindings],
        }

    def binding_for(self, alias: str) -> CredentialBinding:
        matches = [binding for binding in self.bindings if binding.alias == alias]
        if len(matches) != 1:
            raise PolicyViolationError(f"credential alias {alias!r} has no explicit binding")
        return matches[0]

    def resolve(self, alias: str, environ: Mapping[str, str]) -> str:
        binding = self.binding_for(alias)
        value = environ.get(binding.environment_variable)
        if not isinstance(value, str) or not value or len(value) > 16_384:
            raise PolicyViolationError(
                f"credential environment variable {binding.environment_variable!r} is unavailable"
            )
        if any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise PolicyViolationError(
                "credential environment variable contains control characters"
            )
        return value

    @classmethod
    def from_dict(cls, raw: Any) -> CredentialBindings:
        _require_exact_fields(raw, {"schema", "project_id", "bindings"}, "credential bindings")
        rows = _as_list(raw["bindings"], "credential bindings")
        return cls(
            schema=raw["schema"],
            project_id=raw["project_id"],
            bindings=tuple(CredentialBinding.from_dict(row) for row in rows),
        )


def parse_credential_bindings(content: str) -> CredentialBindings:
    raw = parse_strict_yaml(
        content,
        label="credential bindings",
        maximum_bytes=MAX_CREDENTIAL_BINDINGS_BYTES,
    )
    return CredentialBindings.from_dict(raw)


def credential_bindings_path(registration_file: Path) -> Path:
    if not registration_file.is_absolute() or registration_file.name != "registration.yaml":
        raise PolicyViolationError("registration file must be an absolute registration.yaml path")
    return registration_file.parent / "credential-bindings.yaml"
