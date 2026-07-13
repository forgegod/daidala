"""Strict workflow-constraint parsing and canonicalization."""

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
from .state import WorkflowStage

CONSTRAINTS_SCHEMA = "daidala.workflow-constraints/v1"
MAX_CONSTRAINTS_PER_SCOPE = 16
MAX_CONSTRAINT_BYTES = 1024
MAX_CANONICAL_BYTES = 4096
_EXECUTABLE_STAGES = tuple(stage for stage in WorkflowStage if stage is not WorkflowStage.APPROVAL)



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
class WorkflowConstraints:
    """Validated constraint content with a deterministic JSON representation."""

    global_constraints: tuple[str, ...]
    phases: tuple[tuple[WorkflowStage, tuple[str, ...]], ...] = ()
    schema: str = CONSTRAINTS_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != CONSTRAINTS_SCHEMA:
            raise PolicyViolationError(f"constraint schema must be {CONSTRAINTS_SCHEMA!r}")
        _validate_constraints(self.global_constraints, "global")
        if not isinstance(self.phases, tuple):
            raise PolicyViolationError("constraint phases must be an ordered tuple")
        stages = [stage for stage, _constraints in self.phases]
        if len(stages) != len(set(stages)):
            raise PolicyViolationError("constraint phases cannot contain duplicate stages")
        if any(stage not in _EXECUTABLE_STAGES for stage in stages):
            raise PolicyViolationError("constraint phases contain an invalid executable stage")
        if stages != sorted(stages, key=lambda stage: stage.value):
            raise PolicyViolationError("constraint phases must use canonical stage order")
        for stage, constraints in self.phases:
            _validate_constraints(constraints, f"phase {stage.value}")
        if len(self.canonical_bytes()) > MAX_CANONICAL_BYTES:
            raise PolicyViolationError(
                f"canonical constraint content must be at most {MAX_CANONICAL_BYTES} UTF-8 bytes"
            )

    def constraints_for(self, stage: WorkflowStage) -> tuple[str, ...]:
        if stage is WorkflowStage.APPROVAL:
            raise PolicyViolationError("approval is not an executable constraint phase")
        specific = next((rows for candidate, rows in self.phases if candidate is stage), ())
        return (*self.global_constraints, *specific)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "schema": self.schema,
            "global": list(self.global_constraints),
        }
        if self.phases:
            result["phases"] = {
                stage.value: list(constraints) for stage, constraints in self.phases
            }
        return result

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> WorkflowConstraints:
        if not isinstance(raw, dict):
            raise PolicyViolationError("constraint document must be an object")
        expected = {"schema", "global", "phases"}
        unknown = sorted(set(raw) - expected)
        missing = sorted({"schema", "global"} - set(raw))
        if missing or unknown:
            details = []
            if missing:
                details.append(f"missing: {', '.join(missing)}")
            if unknown:
                details.append(f"unknown: {', '.join(unknown)}")
            raise PolicyViolationError(
                f"constraint document fields are invalid ({'; '.join(details)})"
            )
        phases_raw = raw.get("phases", {})
        if not isinstance(phases_raw, dict):
            raise PolicyViolationError("constraint phases must be an object")
        phases: list[tuple[WorkflowStage, tuple[str, ...]]] = []
        for name, constraints in phases_raw.items():
            try:
                stage = WorkflowStage(name)
            except (TypeError, ValueError) as error:
                raise PolicyViolationError(f"unknown constraint phase: {name!r}") from error
            if stage is WorkflowStage.APPROVAL:
                raise PolicyViolationError("approval is not an executable constraint phase")
            phases.append((stage, _as_constraint_tuple(constraints, f"phase {name}")))
        phases.sort(key=lambda row: row[0].value)
        return cls(
            schema=raw["schema"],
            global_constraints=_as_constraint_tuple(raw["global"], "global"),
            phases=tuple(phases),
        )


def parse_workflow_constraints(content: str) -> WorkflowConstraints:
    """Parse policy YAML without accepting YAML graph or executable features."""
    if not isinstance(content, str) or not content.strip():
        raise PolicyViolationError("constraint content must be a non-empty string")
    if _contains_control_character(content):
        raise PolicyViolationError("constraint content contains control characters")
    try:
        tokens = tuple(yaml.scan(content))
        if any(isinstance(token, (AnchorToken, AliasToken, TagToken)) for token in tokens):
            raise PolicyViolationError("constraint content cannot use anchors, aliases, or tags")
        if any(isinstance(event, AliasEvent) for event in yaml.parse(content)):
            raise PolicyViolationError("constraint content cannot use aliases")
        raw = yaml.load(content, Loader=_UniqueKeyLoader)
    except PolicyViolationError:
        raise
    except yaml.YAMLError as error:
        raise PolicyViolationError(f"invalid constraint YAML: {error}") from error
    return WorkflowConstraints.from_dict(raw)


def extract_policy_skill_constraints(markdown: str) -> str:
    """Extract the sole fenced YAML policy document from an installed SKILL.md."""
    if not isinstance(markdown, str) or not markdown.startswith("---\n"):
        raise PolicyViolationError("policy skill requires YAML frontmatter")
    frontmatter_end = markdown.find("\n---\n", 4)
    if frontmatter_end < 0:
        raise PolicyViolationError("policy skill frontmatter is not terminated")
    body = markdown[frontmatter_end + 5 :].strip()
    if body.count("```") != 2:
        raise PolicyViolationError(
            "policy skill body must contain exactly one fenced yaml document"
        )
    match = re.fullmatch(r"```yaml\n(?P<content>.+)\n```", body, flags=re.DOTALL)
    if match is None:
        raise PolicyViolationError(
            "policy skill body must contain exactly one fenced yaml document"
        )
    content = match.group("content")
    parse_workflow_constraints(content)
    return content


def _as_constraint_tuple(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise PolicyViolationError(f"{label} constraints must be a list")
    return tuple(value)


def _validate_constraints(constraints: tuple[str, ...], label: str) -> None:
    if not isinstance(constraints, tuple) or not 1 <= len(constraints) <= MAX_CONSTRAINTS_PER_SCOPE:
        raise PolicyViolationError(
            f"{label} constraints must contain 1-{MAX_CONSTRAINTS_PER_SCOPE} strings"
        )
    for constraint in constraints:
        if not isinstance(constraint, str) or not constraint.strip():
            raise PolicyViolationError(f"{label} constraints must contain non-empty strings")
        if _contains_control_character(constraint):
            raise PolicyViolationError(f"{label} constraints contain control characters")
        size = len(constraint.encode("utf-8"))
        if size > MAX_CONSTRAINT_BYTES:
            raise PolicyViolationError(
                f"{label} constraints must be at most {MAX_CONSTRAINT_BYTES} UTF-8 bytes each"
            )


def _contains_control_character(value: str) -> bool:
    return any(
        character not in {"\n", "\t"} and unicodedata.category(character) == "Cc"
        for character in value
    )
