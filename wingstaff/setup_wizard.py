"""Typed, confirmation-gated setup requests for the dashboard wizard."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

EXECUTABLE_STAGES = ("define", "plan", "implement", "verify", "review", "deliver")
CommandRunner = Callable[[tuple[str, ...]], tuple[int, str]]


class SetupWizardError(ValueError):
    """A setup request cannot be previewed or started safely."""


@dataclass(frozen=True)
class SetupRequest:
    board_slug: str
    target_repository: str
    goal: str
    stage_profiles: dict[str, str]
    pack: str = "addyosmani"
    workflow_id: str | None = None
    constraints_content: str | None = None
    constraints_skill: str | None = None
    constraints_skill_digest: str | None = None

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> SetupRequest:
        required = ("board_slug", "target_repository", "goal", "stage_profiles")
        missing = [name for name in required if name not in payload]
        if missing:
            raise SetupWizardError(f"missing required setup fields: {', '.join(missing)}")
        profiles = payload["stage_profiles"]
        if not isinstance(profiles, Mapping):
            raise SetupWizardError("stage_profiles must be an object")
        normalized_profiles = {str(key): str(value).strip() for key, value in profiles.items()}
        if set(normalized_profiles) != set(EXECUTABLE_STAGES) or any(
            not value for value in normalized_profiles.values()
        ):
            raise SetupWizardError("stage_profiles must name every executable stage exactly once")
        values = {
            name: payload.get(name)
            for name in (
                "board_slug",
                "target_repository",
                "goal",
                "pack",
                "workflow_id",
                "constraints_content",
                "constraints_skill",
                "constraints_skill_digest",
            )
        }
        board_slug = _required_text(values["board_slug"], "board_slug")
        target_repository = _required_text(
            values["target_repository"], "target_repository"
        )
        goal = _required_text(values["goal"], "goal")
        pack = values["pack"] if isinstance(values["pack"], str) else "addyosmani"
        if pack not in {"addyosmani", "aidlc"}:
            raise SetupWizardError("pack must be addyosmani or aidlc")
        content = values["constraints_content"]
        skill = values["constraints_skill"]
        digest = values["constraints_skill_digest"]
        if content is not None and skill is not None:
            raise SetupWizardError(
                "constraints_content and constraints_skill are mutually exclusive"
            )
        if (skill is None) != (digest is None):
            raise SetupWizardError("constraints_skill requires constraints_skill_digest")
        return cls(
            board_slug=board_slug,
            target_repository=target_repository,
            goal=goal,
            stage_profiles=normalized_profiles,
            pack=pack,
            workflow_id=_optional_text(values["workflow_id"]),
            constraints_content=_optional_text(content),
            constraints_skill=_optional_text(skill),
            constraints_skill_digest=_optional_text(digest),
        )

    def start_kwargs(self) -> dict[str, Any]:
        return {
            "board_slug": self.board_slug,
            "target_repository": self.target_repository,
            "goal": self.goal,
            "stage_profiles": self.stage_profiles,
            "pack_name": self.pack,
            "workflow_id": self.workflow_id,
            "constraints_content": self.constraints_content,
            "constraints_skill": self.constraints_skill,
            "constraints_skill_digest": self.constraints_skill_digest,
        }

    def preview(self) -> dict[str, Any]:
        return {
            "confirmed": False,
            "request": {**self.start_kwargs(), "pack": self.pack},
            "mutations": [
                "validate the target repository and exact installed skills",
                "create the policy ledger and approval-gated Kanban graph",
            ],
        }


def confirmed_start(
    payload: Mapping[str, Any],
    start: Callable[..., Any],
) -> Any:
    """Invoke the existing start path only after literal ``confirm: true``."""
    if payload.get("confirm") is not True:
        raise SetupWizardError("explicit confirmation is required before setup mutation")
    request = SetupRequest.from_payload(payload)
    return start(**request.start_kwargs())


def list_boards(run: CommandRunner) -> list[dict[str, Any]]:
    code, output = run(("hermes", "kanban", "boards", "list", "--json"))
    if code != 0:
        raise SetupWizardError("could not list Hermes Kanban boards")
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as error:
        raise SetupWizardError("Hermes returned invalid board JSON") from error
    if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
        raise SetupWizardError("Hermes returned an invalid board list")
    return payload


def create_board(run: CommandRunner, *, slug: str, name: str | None = None) -> None:
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise SetupWizardError("board slug must be lowercase kebab-case")
    command = ["hermes", "kanban", "boards", "create", slug]
    if name:
        command.extend(("--name", name.strip()))
    code, _output = run(tuple(command))
    if code != 0:
        raise SetupWizardError("could not create Hermes Kanban board")


def list_profiles(run: CommandRunner) -> list[str]:
    code, output = run(("hermes", "profile", "list"))
    if code != 0:
        raise SetupWizardError("could not list Hermes profiles")
    rows: list[str] = []
    for line in output.splitlines():
        match = re.match(r"^\s*[◆ ]?([a-zA-Z0-9][a-zA-Z0-9_-]*)\s{2,}", line)
        if match and match.group(1) != "Profile":
            rows.append(match.group(1))
    if not rows:
        raise SetupWizardError("Hermes returned no parseable profiles")
    return rows


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise SetupWizardError("optional setup values must be non-empty strings")
    return value.strip()


def _required_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SetupWizardError(f"{name} must be a non-empty string")
    return value.strip()
