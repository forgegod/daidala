"""Typed, confirmation-gated setup requests for the dashboard wizard."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
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


def create_board(
    run: CommandRunner,
    *,
    slug: str,
    name: str | None = None,
    default_workdir: str | None = None,
) -> None:
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise SetupWizardError("board slug must be lowercase kebab-case")
    command = ["hermes", "kanban", "boards", "create", slug]
    if name:
        command.extend(("--name", name.strip()))
    if default_workdir is not None:
        if not isinstance(default_workdir, str) or not default_workdir.startswith("/"):
            raise SetupWizardError("board default workdir must be an absolute path")
        command.extend(("--default-workdir", default_workdir))
    code, _output = run(tuple(command))
    if code != 0:
        raise SetupWizardError("could not create Hermes Kanban board")


@dataclass(frozen=True)
class LocalProjectPreview:
    """Path-bound but browser-safe proposal for a fresh local workspace."""

    project_id: str
    board_slug: str
    board_name: str
    target_repository: str
    file_digests: tuple[tuple[str, str], ...]

    @property
    def digest(self) -> str:
        payload = {
            "project_id": self.project_id,
            "board_slug": self.board_slug,
            "board_name": self.board_name,
            "target_repository": self.target_repository,
            "file_digests": self.file_digests,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "board": {"slug": self.board_slug, "name": self.board_name},
            "files": [{"path": path, "digest": digest} for path, digest in self.file_digests],
            "mutations": [
                "git init",
                "write default .daidala policy",
                "create the initial commit",
                "create an unbound Hermes board with this local Git root as default workdir",
            ],
            "preview_digest": self.digest,
        }


class LocalProjectInitializer:
    """Create one fresh local Git workspace from trusted profile configuration."""

    def __init__(self, data_root: Path, run: CommandRunner) -> None:
        if not isinstance(data_root, Path) or not data_root.is_absolute():
            raise SetupWizardError("local-project data root must be absolute")
        self.data_root = data_root.resolve()
        self.run = run

    def preview(self, project_id: object, board_name: object) -> LocalProjectPreview:
        from .checkout_root import CheckoutRootStore, checkout_path
        from .projects import _require_slug
        from .repository_bootstrap import build_local_bootstrap_files

        if not isinstance(project_id, str):
            raise SetupWizardError("local project slug must be a string")
        slug = project_id.strip()
        try:
            _require_slug(slug, "local project slug")
        except ValueError as error:
            raise SetupWizardError(str(error)) from error
        if len(slug) > 100:
            raise SetupWizardError("local project slug exceeds board-name capacity")
        if not isinstance(board_name, str) or not board_name.strip():
            raise SetupWizardError("local project board display name is required")
        target = checkout_path(CheckoutRootStore(self.data_root).read().root, slug)
        if target.exists() or target.is_symlink():
            raise SetupWizardError("derived local project directory already exists")
        board_slug = f"daidala-local-{slug}"
        boards = list_boards(self.run)
        if any(row.get("slug") == board_slug for row in boards):
            raise SetupWizardError("derived local project board already exists")
        files = build_local_bootstrap_files(slug)
        return LocalProjectPreview(
            project_id=slug,
            board_slug=board_slug,
            board_name=board_name.strip(),
            target_repository=str(target),
            file_digests=tuple((row.path, row.digest) for row in files),
        )

    def apply(
        self, project_id: object, board_name: object, preview_digest: object
    ) -> LocalProjectPreview:
        if not isinstance(preview_digest, str) or len(preview_digest) != 64:
            raise SetupWizardError("local project preview digest is required")
        preview = self.preview(project_id, board_name)
        if preview.digest != preview_digest:
            raise SetupWizardError("local project inputs changed after preview")
        from .repository_bootstrap import build_local_bootstrap_files

        target = Path(preview.target_repository)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise SetupWizardError("cannot create local project parent directory") from error
        self._command(("git", "init", "--quiet", str(target)), "initialize local Git repository")
        try:
            policy_root = target / ".daidala"
            policy_root.mkdir()
            for file in build_local_bootstrap_files(preview.project_id):
                (target / file.path).write_text(file.content, encoding="utf-8")
        except OSError as error:
            raise SetupWizardError("cannot write local project policy") from error
        self._command(
            ("git", "-C", str(target), "add", ".daidala"), "stage local project policy"
        )
        self._command(
            (
                "git",
                "-C",
                str(target),
                "commit",
                "--quiet",
                "-m",
                "chore: initialize Daidala project",
            ),
            "create local project initial commit",
        )
        create_board(
            self.run,
            slug=preview.board_slug,
            name=preview.board_name,
            default_workdir=preview.target_repository,
        )
        return preview

    def _command(self, command: tuple[str, ...], action: str) -> None:
        code, _output = self.run(command)
        if code != 0:
            raise SetupWizardError(f"could not {action}")


def list_profiles(run: CommandRunner) -> list[str]:
    output = _profile_list_output(run)
    rows: list[str] = []
    for line in output.splitlines():
        parsed = _parse_profile_row(line)
        if parsed is not None:
            rows.append(parsed[0])
    if not rows:
        raise SetupWizardError("Hermes returned no parseable profiles")
    return rows


def active_profile(
    run: CommandRunner,
    *,
    fallback_name: str | None = None,
) -> str:
    """Return the active or runtime-root profile from documented inventory."""

    output = _profile_list_output(run)
    profiles: list[str] = []
    active: str | None = None
    for line in output.splitlines():
        parsed = _parse_profile_row(line)
        if parsed is None:
            continue
        name, is_active = parsed
        profiles.append(name)
        if is_active:
            active = name
    if fallback_name is not None and fallback_name in profiles:
        return fallback_name
    if active is not None:
        return active
    if fallback_name is not None:
        raise SetupWizardError(
            f"Hermes returned no active profile and runtime-root candidate "
            f"{fallback_name!r} is not present in profile inventory"
        )
    raise SetupWizardError("Hermes returned no active profile")


def _profile_list_output(run: CommandRunner) -> str:
    code, output = run(("hermes", "profile", "list"))
    if code != 0:
        raise SetupWizardError("could not list Hermes profiles")
    return output


def _parse_profile_row(line: str) -> tuple[str, bool] | None:
    match = re.match(
        r"^\s*(?P<active>◆)?\s*(?P<name>[a-zA-Z0-9][a-zA-Z0-9._-]*)(?:\s+|$)",
        line,
    )
    if match is None or match.group("name") == "Profile":
        return None
    return match.group("name"), match.group("active") is not None


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
