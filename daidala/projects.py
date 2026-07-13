"""Strict committed project-manifest parsing and identity."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

import yaml
from yaml.constructor import ConstructorError
from yaml.events import AliasEvent
from yaml.tokens import AliasToken, AnchorToken, TagToken

from .errors import PolicyViolationError

PROJECT_SCHEMA = "daidala.project/v1"
MAX_MANIFEST_BYTES = 65_536
MAX_TEXT_CHARS = 512
MAX_COMMAND_CHARS = 2_048
MAX_LIST_ITEMS = 64
MAX_TIMEOUT_SECONDS = 3_600
MAX_REPETITIONS = 20

_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,127}$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_REVISION = re.compile(r"^[0-9a-f]{40}$")
_GLOB_META = re.compile(r"[*?[]")


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(
    loader: _UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in result
        except TypeError as error:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "mapping keys must be scalar strings",
                key_node.start_mark,
            ) from error
        if duplicate:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"duplicate key: {key!r}",
                key_node.start_mark,
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


@dataclass(frozen=True)
class PackIdentity:
    name: str
    source_revision: str
    content_digest: str

    def __post_init__(self) -> None:
        _require_slug(self.name, "pack name")
        _require_revision(self.source_revision, "pack source revision")
        _require_digest(self.content_digest, "pack content digest")

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "source_revision": self.source_revision,
            "content_digest": self.content_digest,
        }

    @classmethod
    def from_dict(cls, raw: Any) -> PackIdentity:
        _require_exact_fields(raw, {"name", "source_revision", "content_digest"}, "pack")
        return cls(raw["name"], raw["source_revision"], raw["content_digest"])


@dataclass(frozen=True)
class RepositorySpec:
    forge: str
    canonical: str
    allowed_remote_urls: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.forge != "github":
            raise PolicyViolationError("repository forge must be 'github'")
        if not isinstance(self.canonical, str) or not _REPOSITORY.fullmatch(self.canonical):
            raise PolicyViolationError("repository canonical identity must be owner/repository")
        _require_unique_tuple(self.allowed_remote_urls, "allowed remote URLs", maximum=8)
        allowed = {
            f"https://github.com/{self.canonical}.git",
            f"git@github.com:{self.canonical}.git",
        }
        if any(url not in allowed for url in self.allowed_remote_urls):
            raise PolicyViolationError(
                "allowed remote URLs must exactly identify the canonical GitHub repository"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "forge": self.forge,
            "canonical": self.canonical,
            "allowed_remote_urls": list(self.allowed_remote_urls),
        }

    @classmethod
    def from_dict(cls, raw: Any) -> RepositorySpec:
        _require_exact_fields(raw, {"forge", "canonical", "allowed_remote_urls"}, "repository")
        return cls(raw["forge"], raw["canonical"], _as_tuple(raw["allowed_remote_urls"], "URLs"))


@dataclass(frozen=True)
class VerificationSuite:
    id: str
    kind: str
    commands: tuple[str, ...] = ()
    timeout_seconds: int | None = None
    repetitions: int | None = None
    maximum_failures: int | None = None
    fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_slug(self.id, "verification suite ID")
        if self.kind not in {"deterministic", "repeated", "observational"}:
            raise PolicyViolationError("verification kind is invalid")
        if self.kind == "deterministic":
            _require_commands(self.commands)
            _require_int(self.timeout_seconds, "verification timeout", 1, MAX_TIMEOUT_SECONDS)
            repeated_values = (self.repetitions, self.maximum_failures)
            if any(value is not None for value in repeated_values) or self.fields:
                raise PolicyViolationError(
                    "deterministic suites cannot declare repeated or observational fields"
                )
        elif self.kind == "repeated":
            if len(self.commands) != 1:
                raise PolicyViolationError("repeated suites require exactly one command")
            _require_commands(self.commands)
            _require_int(self.timeout_seconds, "verification timeout", 1, MAX_TIMEOUT_SECONDS)
            _require_int(self.repetitions, "verification repetitions", 2, MAX_REPETITIONS)
            _require_int(self.maximum_failures, "maximum failures", 0, self.repetitions or 0)
            if self.fields:
                raise PolicyViolationError("repeated suites cannot declare observational fields")
        else:
            _require_unique_tuple(self.fields, "observational fields", maximum=32, slug=True)
            if self.commands or any(
                value is not None
                for value in (self.timeout_seconds, self.repetitions, self.maximum_failures)
            ):
                raise PolicyViolationError("observational suites cannot execute commands")

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"id": self.id, "kind": self.kind}
        if self.commands:
            if self.kind == "repeated":
                result["command"] = self.commands[0]
            else:
                result["commands"] = list(self.commands)
        if self.timeout_seconds is not None:
            result["timeout_seconds"] = self.timeout_seconds
        if self.repetitions is not None:
            result["repetitions"] = self.repetitions
        if self.maximum_failures is not None:
            result["acceptance"] = {"maximum_failures": self.maximum_failures}
        if self.fields:
            result["fields"] = list(self.fields)
        return result

    @classmethod
    def from_dict(cls, raw: Any) -> VerificationSuite:
        if not isinstance(raw, dict):
            raise PolicyViolationError("verification suite must be an object")
        kind = raw.get("kind")
        expected = {"id", "kind"}
        if kind == "deterministic":
            expected |= {"commands", "timeout_seconds"}
        elif kind == "repeated":
            expected |= {"command", "timeout_seconds", "repetitions", "acceptance"}
        elif kind == "observational":
            expected |= {"fields"}
        _require_exact_fields(raw, expected, "verification suite")
        acceptance = raw.get("acceptance")
        if kind == "repeated":
            _require_exact_fields(acceptance, {"maximum_failures"}, "verification acceptance")
        if not isinstance(kind, str):
            raise PolicyViolationError("verification kind is invalid")
        commands = (
            (raw["command"],)
            if kind == "repeated"
            else _as_tuple(raw.get("commands", []), "commands")
        )
        return cls(
            id=raw["id"],
            kind=kind,
            commands=commands,
            timeout_seconds=raw.get("timeout_seconds"),
            repetitions=raw.get("repetitions"),
            maximum_failures=acceptance["maximum_failures"] if acceptance else None,
            fields=_as_tuple(raw.get("fields", []), "fields"),
        )


@dataclass(frozen=True)
class ProjectManifest:
    project_id: str
    repository: RepositorySpec
    allowed_packs: tuple[PackIdentity, ...]
    default_pack: str
    default_constraints_source: str
    verification_suites: tuple[VerificationSuite, ...]
    mutable_paths: tuple[str, ...]
    protected_paths: tuple[str, ...]
    maximum_changed_files: int
    approval_roles: tuple[str, ...]
    intake_adapter: str
    eligible_categories: tuple[str, ...]
    allow_commit: bool
    allow_push: bool
    allow_publish: bool
    schema: str = PROJECT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != PROJECT_SCHEMA:
            raise PolicyViolationError(f"project schema must be {PROJECT_SCHEMA!r}")
        _require_slug(self.project_id, "project ID")
        _require_unique_objects(
            self.allowed_packs,
            "allowed packs",
            key=lambda pack: pack.name,
            maximum=16,
        )
        if self.default_pack not in {pack.name for pack in self.allowed_packs}:
            raise PolicyViolationError("default pack must name an allowed pack")
        _require_relative_path(
            self.default_constraints_source,
            "default constraints source",
            glob=False,
        )
        _require_unique_objects(
            self.verification_suites,
            "verification suites",
            key=lambda suite: suite.id,
            maximum=16,
        )
        _require_path_patterns(self.mutable_paths, "mutable paths")
        _require_path_patterns(self.protected_paths, "protected paths")
        _require_int(self.maximum_changed_files, "maximum changed files", 1, 100)
        _require_unique_tuple(self.approval_roles, "approval roles", maximum=16, slug=True)
        _require_slug(self.intake_adapter, "intake adapter")
        _require_unique_tuple(
            self.eligible_categories,
            "eligible categories",
            maximum=32,
            slug=True,
        )
        for label, value in (
            ("allow commit", self.allow_commit),
            ("allow push", self.allow_push),
            ("allow publish", self.allow_publish),
        ):
            if not isinstance(value, bool):
                raise PolicyViolationError(f"{label} must be a boolean")
        if self.allow_push and not self.allow_commit:
            raise PolicyViolationError("push cannot be allowed when commit is disabled")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "project_id": self.project_id,
            "repository": self.repository.to_dict(),
            "workflow": {
                "allowed_packs": [pack.to_dict() for pack in self.allowed_packs],
                "default_pack": self.default_pack,
                "default_constraints": {"source": self.default_constraints_source},
            },
            "verification": {"suites": [suite.to_dict() for suite in self.verification_suites]},
            "improvement": {
                "mutable_paths": list(self.mutable_paths),
                "protected_paths": list(self.protected_paths),
                "maximum_changed_files": self.maximum_changed_files,
                "approval_roles": list(self.approval_roles),
            },
            "intake": {
                "adapter": self.intake_adapter,
                "eligible_categories": list(self.eligible_categories),
            },
            "release": {
                "allow_commit": self.allow_commit,
                "allow_push": self.allow_push,
                "allow_publish": self.allow_publish,
            },
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    @classmethod
    def from_dict(cls, raw: Any) -> ProjectManifest:
        _require_exact_fields(
            raw,
            {
                "schema",
                "project_id",
                "repository",
                "workflow",
                "verification",
                "improvement",
                "intake",
                "release",
            },
            "project manifest",
        )
        workflow = raw["workflow"]
        verification = raw["verification"]
        improvement = raw["improvement"]
        intake = raw["intake"]
        release = raw["release"]
        _require_exact_fields(
            workflow,
            {"allowed_packs", "default_pack", "default_constraints"},
            "workflow",
        )
        _require_exact_fields(
            workflow["default_constraints"], {"source"}, "default constraints"
        )
        _require_exact_fields(verification, {"suites"}, "verification")
        _require_exact_fields(
            improvement,
            {"mutable_paths", "protected_paths", "maximum_changed_files", "approval_roles"},
            "improvement",
        )
        _require_exact_fields(intake, {"adapter", "eligible_categories"}, "intake")
        _require_exact_fields(release, {"allow_commit", "allow_push", "allow_publish"}, "release")
        return cls(
            schema=raw["schema"],
            project_id=raw["project_id"],
            repository=RepositorySpec.from_dict(raw["repository"]),
            allowed_packs=tuple(
                PackIdentity.from_dict(row)
                for row in _as_list(workflow["allowed_packs"], "allowed packs")
            ),
            default_pack=workflow["default_pack"],
            default_constraints_source=workflow["default_constraints"]["source"],
            verification_suites=tuple(
                VerificationSuite.from_dict(row)
                for row in _as_list(
                    verification["suites"], "verification suites"
                )
            ),
            mutable_paths=_as_tuple(improvement["mutable_paths"], "mutable paths"),
            protected_paths=_as_tuple(improvement["protected_paths"], "protected paths"),
            maximum_changed_files=improvement["maximum_changed_files"],
            approval_roles=_as_tuple(improvement["approval_roles"], "approval roles"),
            intake_adapter=intake["adapter"],
            eligible_categories=_as_tuple(intake["eligible_categories"], "eligible categories"),
            allow_commit=release["allow_commit"],
            allow_push=release["allow_push"],
            allow_publish=release["allow_publish"],
        )


def parse_project_manifest(content: str) -> ProjectManifest:
    raw = parse_strict_yaml(content, label="project manifest", maximum_bytes=MAX_MANIFEST_BYTES)
    return ProjectManifest.from_dict(raw)


def parse_strict_yaml(content: str, *, label: str, maximum_bytes: int) -> Any:
    if not isinstance(content, str) or not content.strip():
        raise PolicyViolationError(f"{label} content must be a non-empty string")
    if len(content.encode("utf-8")) > maximum_bytes:
        raise PolicyViolationError(f"{label} content must be at most {maximum_bytes} UTF-8 bytes")
    if _contains_control_character(content):
        raise PolicyViolationError(f"{label} content contains control characters")
    try:
        tokens = tuple(yaml.scan(content))
        if any(isinstance(token, (AnchorToken, AliasToken, TagToken)) for token in tokens):
            raise PolicyViolationError(f"{label} cannot use anchors, aliases, or tags")
        if any(isinstance(event, AliasEvent) for event in yaml.parse(content)):
            raise PolicyViolationError(f"{label} cannot use aliases")
        return yaml.load(content, Loader=_UniqueKeyLoader)
    except PolicyViolationError:
        raise
    except yaml.YAMLError as error:
        raise PolicyViolationError(f"invalid {label} YAML: {error}") from error


def _require_exact_fields(raw: Any, expected: set[str], label: str) -> None:
    if not isinstance(raw, dict):
        raise PolicyViolationError(f"{label} must be an object")
    missing = sorted(expected - set(raw))
    unknown = sorted(set(raw) - expected)
    if missing or unknown:
        details = []
        if missing:
            details.append(f"missing: {', '.join(missing)}")
        if unknown:
            details.append(f"unknown: {', '.join(unknown)}")
        raise PolicyViolationError(f"{label} fields are invalid ({'; '.join(details)})")


def _as_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise PolicyViolationError(f"{label} must be a list")
    return value


def _as_tuple(value: Any, label: str) -> tuple[str, ...]:
    rows = _as_list(value, label)
    if any(not isinstance(row, str) for row in rows):
        raise PolicyViolationError(f"{label} must contain strings")
    return tuple(rows)


def _require_slug(value: Any, label: str) -> None:
    if not isinstance(value, str) or not _SLUG.fullmatch(value):
        raise PolicyViolationError(f"{label} must be a lowercase path-safe slug")


def _require_digest(value: Any, label: str) -> None:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise PolicyViolationError(f"{label} must be a lowercase SHA-256 digest")


def _require_revision(value: Any, label: str) -> None:
    if not isinstance(value, str) or not _REVISION.fullmatch(value):
        raise PolicyViolationError(f"{label} must be 40 lowercase hex characters")


def _require_text(value: Any, label: str, maximum: int = MAX_TEXT_CHARS) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise PolicyViolationError(
            f"{label} must be a non-empty string of at most {maximum} characters"
        )
    if _contains_control_character(value):
        raise PolicyViolationError(f"{label} contains control characters")


def _require_unique_tuple(
    values: tuple[str, ...], label: str, *, maximum: int, slug: bool = False
) -> None:
    if not isinstance(values, tuple) or not 1 <= len(values) <= maximum:
        raise PolicyViolationError(f"{label} must contain 1-{maximum} values")
    if len(values) != len(set(values)):
        raise PolicyViolationError(f"{label} cannot contain duplicates")
    for value in values:
        if slug:
            _require_slug(value, label)
        else:
            _require_text(value, label)


def _require_unique_objects(values: tuple[Any, ...], label: str, *, key: Any, maximum: int) -> None:
    if not isinstance(values, tuple) or not 1 <= len(values) <= maximum:
        raise PolicyViolationError(f"{label} must contain 1-{maximum} entries")
    keys = [key(value) for value in values]
    if len(keys) != len(set(keys)):
        raise PolicyViolationError(f"{label} cannot contain duplicate identities")


def _require_int(value: Any, label: str, minimum: int, maximum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise PolicyViolationError(f"{label} must be an integer from {minimum} to {maximum}")


def _require_commands(commands: tuple[str, ...]) -> None:
    if not isinstance(commands, tuple) or not 1 <= len(commands) <= 32:
        raise PolicyViolationError("commands must contain 1-32 entries")
    for command in commands:
        _require_text(command, "command", MAX_COMMAND_CHARS)


def _require_path_patterns(values: tuple[str, ...], label: str) -> None:
    _require_unique_tuple(values, label, maximum=MAX_LIST_ITEMS)
    for value in values:
        _require_relative_path(value, label, glob=True)


def _require_relative_path(value: Any, label: str, *, glob: bool) -> None:
    _require_text(value, label, 512)
    if not isinstance(value, str):
        raise PolicyViolationError(f"{label} must be a string")
    if value.startswith(("/", "~")) or "\\" in value or "//" in value:
        raise PolicyViolationError(f"{label} must use a relative POSIX path")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise PolicyViolationError(f"{label} cannot escape or normalize its root")
    if not glob and _GLOB_META.search(value):
        raise PolicyViolationError(f"{label} cannot contain glob syntax")


def _contains_control_character(value: str) -> bool:
    return any(
        character not in {"\n", "\t"} and unicodedata.category(character) == "Cc"
        for character in value
    )
