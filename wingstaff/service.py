"""Application service for Wingstaff lifecycle tools."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .errors import WorkflowError
from .packs import __version__, load_pack
from .skills import HermesSkillInventory, SkillInventory, require_pack_skills
from .state import WorkflowState
from .store import WorkflowStore
from .workflow import (
    approve_plan,
    cancel_workflow,
    modify_plan,
    new_workflow,
    validate_target,
)


class ServiceError(WorkflowError):
    """Raised when a lifecycle operation cannot satisfy its boundary contract."""


class WorkflowService:
    """Coordinate deterministic transitions with durable persistence."""

    def __init__(
        self,
        store: WorkflowStore,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
        skill_inventory: SkillInventory | None = None,
    ) -> None:
        self.store = store
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: str(uuid4()))
        self._skill_inventory = skill_inventory or HermesSkillInventory()

    def start(
        self,
        *,
        target_repository: str,
        goal: str,
        pack_name: str = "addyosmani",
        workflow_id: str | None = None,
    ) -> WorkflowState:
        """Create a draft after validating only local deterministic inputs."""
        pack = load_pack(pack_name)
        require_pack_skills(pack, self._skill_inventory)
        target = _canonical_local_path(target_repository)
        state = new_workflow(
            workflow_id=workflow_id or self._id_factory(),
            target_repository=str(target),
            requested_goal=goal,
            pack_name=pack.name,
            pack_source_revision=f"wingstaff@{__version__}",
            created_at=self._clock(),
        )
        return self.store.create(state)

    def status(self, workflow_id: str) -> WorkflowState:
        """Return durable state without changing it."""
        return self.store.get(workflow_id)

    def validate(self, workflow_id: str) -> WorkflowState:
        """Validate the selected pack and the target repository's clean baseline."""
        observed = self.store.get_with_token(workflow_id)
        state = observed.state
        pack = load_pack(state.pack_name)
        require_pack_skills(pack, self._skill_inventory)
        baseline, is_clean = _inspect_repository(Path(state.target_repository))
        updated = validate_target(
            state,
            target_is_clean=is_clean,
            baseline_commit=baseline if is_clean else None,
            validated_at=self._clock(),
        )
        return self.store.update(updated, expected_updated_at=observed.updated_at)

    def approve(self, workflow_id: str, plan_digest: str) -> WorkflowState:
        """Approve exactly the current durable plan digest."""
        observed = self.store.get_with_token(workflow_id)
        updated = approve_plan(
            observed.state,
            plan_digest=plan_digest,
            decided_at=self._clock(),
        )
        return self.store.update(updated, expected_updated_at=observed.updated_at)

    def modify(
        self,
        workflow_id: str,
        *,
        path: str,
        digest: str,
    ) -> WorkflowState:
        """Replace the plan artifact and invalidate any durable approval."""
        observed = self.store.get_with_token(workflow_id)
        updated = modify_plan(
            observed.state,
            path=path,
            digest=digest,
            modified_at=self._clock(),
        )
        return self.store.update(updated, expected_updated_at=observed.updated_at)

    def cancel(self, workflow_id: str, reason: str) -> WorkflowState:
        """Record terminal operator cancellation."""
        observed = self.store.get_with_token(workflow_id)
        updated = cancel_workflow(
            observed.state,
            reason=reason,
            cancelled_at=self._clock(),
        )
        return self.store.update(updated, expected_updated_at=observed.updated_at)


def _canonical_local_path(value: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ServiceError("target_repository must be a non-empty absolute local path")
    expanded = Path(value).expanduser()
    if not expanded.is_absolute() or "://" in value or value.startswith("git@"):
        raise ServiceError("target_repository must be a non-empty absolute local path")
    return expanded.resolve()


def _inspect_repository(target: Path) -> tuple[str, bool]:
    root = _git(target, "rev-parse", "--show-toplevel")
    if Path(root).resolve() != target.resolve():
        raise ServiceError("target_repository must name the repository root")
    baseline = _git(target, "rev-parse", "HEAD")
    status = _git(target, "status", "--porcelain=v1", "--untracked-files=normal")
    return baseline, not bool(status)


def _git(target: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(target), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ServiceError(f"cannot inspect target repository: {error}") from error
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "git command failed"
        raise ServiceError(f"cannot inspect target repository: {message}")
    return completed.stdout.strip()
