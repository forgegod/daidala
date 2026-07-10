"""Application service for Wingstaff lifecycle tools."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .errors import WorkflowError
from .execution import ExecutionError, ExecutionWorkspace
from .kanban import KanbanCoordinator
from .packs import load_pack
from .skills import (
    HermesSkillInventory,
    ProfileSkillContentRegistry,
    SkillContentRegistry,
    SkillInventory,
    require_pack_skill_revisions,
    require_pack_skills,
)
from .state import WorkflowStage, WorkflowState, WorkflowStatus
from .store import WorkflowStore
from .workflow import (
    approve_plan,
    cancel_workflow,
    modify_plan,
    new_workflow,
    record_artifact,
    record_verification,
    start_implementation,
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
        skill_content_registry: SkillContentRegistry | None = None,
        kanban: KanbanCoordinator | None = None,
    ) -> None:
        self.store = store
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: str(uuid4()))
        self._skill_inventory = skill_inventory or HermesSkillInventory()
        self._skill_content_registry = skill_content_registry or ProfileSkillContentRegistry(
            store.data_root.parent / "skills"
        )
        self._workspace = ExecutionWorkspace(store.data_root)
        self._kanban = kanban

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
        require_pack_skill_revisions(pack, self._skill_content_registry)
        selected_id = workflow_id or self._id_factory()
        self._workspace.validate_workflow_id(selected_id)
        target = _canonical_local_path(target_repository)
        state = new_workflow(
            workflow_id=selected_id,
            target_repository=str(target),
            requested_goal=goal,
            pack_name=pack.name,
            pack_source_revision=f"{pack.source}@{pack.source_revision}",
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
        require_pack_skill_revisions(pack, self._skill_content_registry)
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
        if observed.state.worktree_path:
            self._workspace.remove_worktree(
                observed.state.target_repository, observed.state.worktree_path
            )
        return self.store.update(updated, expected_updated_at=observed.updated_at)

    def submit_artifact(
        self,
        workflow_id: str,
        *,
        stage: WorkflowStage,
        content: str,
    ) -> WorkflowState:
        """Store and record a model-produced definition, plan, or review."""
        if not isinstance(content, str) or not content.strip():
            raise ServiceError("artifact content must be a non-empty string")
        if stage not in {WorkflowStage.DEFINE, WorkflowStage.PLAN, WorkflowStage.REVIEW}:
            raise ServiceError(f"stage {stage.value!r} cannot be submitted as text")
        observed = self.store.get_with_token(workflow_id)
        state = observed.state
        if state.status is not WorkflowStatus.RUNNING or state.current_stage is not stage:
            raise ServiceError(
                f"artifact requires running/{stage.value}; workflow is "
                f"{state.status.value}/{state.current_stage.value}"
            )
        filename = {
            WorkflowStage.DEFINE: "define.md",
            WorkflowStage.PLAN: "plan.md",
            WorkflowStage.REVIEW: "review.md",
        }[stage]
        artifact = self._workspace.write_artifact(workflow_id, filename, content)
        updated = record_artifact(
            state,
            stage=stage,
            path=artifact.path,
            digest=artifact.digest,
            recorded_at=self._clock(),
        )
        return self.store.update(updated, expected_updated_at=observed.updated_at)

    def prepare_implementation(
        self, workflow_id: str, *, assignee: str | None = None
    ) -> WorkflowState:
        """Create the approved worktree and retry-safe Hermes implementation card."""
        observed = self.store.get_with_token(workflow_id)
        state = observed.state
        if (
            state.status is WorkflowStatus.RUNNING
            and state.current_stage is WorkflowStage.IMPLEMENT
            and state.worktree_path
        ):
            self._ensure_implementation_task(state, assignee)
            return state
        if state.status is not WorkflowStatus.APPROVED:
            raise ServiceError("implementation requires approved workflow state")
        baseline, is_clean = _inspect_repository(Path(state.target_repository))
        if not is_clean or baseline != state.baseline_commit:
            raise ServiceError("target repository changed after validation")
        if state.baseline_commit is None:
            raise ServiceError("workflow has no validated baseline commit")
        worktree = self._workspace.create_worktree(
            workflow_id,
            state.target_repository,
            state.baseline_commit,
        )
        updated = start_implementation(
            state,
            worktree_path=worktree,
            started_at=self._clock(),
        )
        persisted = self.store.update(updated, expected_updated_at=observed.updated_at)
        self._ensure_implementation_task(persisted, assignee)
        return persisted

    def _ensure_implementation_task(
        self, state: WorkflowState, assignee: str | None
    ) -> None:
        if self._kanban is None:
            return
        if not assignee or not assignee.strip():
            raise ServiceError("Kanban implementation requires an assignee profile")
        self._kanban.ensure_implementation_task(
            state,
            load_pack(state.pack_name),
            assignee=assignee,
        )

    def capture_implementation(self, workflow_id: str) -> WorkflowState:
        """Capture the real worktree diff and advance to verification."""
        observed = self.store.get_with_token(workflow_id)
        state = observed.state
        if (
            state.status is WorkflowStatus.RUNNING
            and state.current_stage is WorkflowStage.VERIFY
            and state.artifact_for(WorkflowStage.IMPLEMENT) is not None
        ):
            return state
        if (
            state.status is not WorkflowStatus.RUNNING
            or state.current_stage is not WorkflowStage.IMPLEMENT
        ):
            raise ServiceError("diff capture requires active implementation")
        if not state.worktree_path:
            raise ExecutionError("workflow has no implementation worktree")
        diff = self._workspace.capture_diff(state.worktree_path)
        changed_paths = self._workspace.changed_paths(state.worktree_path)
        artifact = self._workspace.write_artifact(
            workflow_id, "implementation.diff", diff
        )
        self._workspace.write_json_artifact(
            workflow_id,
            "implementation-paths.json",
            {"changed_paths": list(changed_paths)},
        )
        updated = record_artifact(
            state,
            stage=WorkflowStage.IMPLEMENT,
            path=artifact.path,
            digest=artifact.digest,
            recorded_at=self._clock(),
        )
        return self.store.update(updated, expected_updated_at=observed.updated_at)

    def record_verification(
        self,
        workflow_id: str,
        *,
        command: str,
        exit_code: int,
        output: str,
    ) -> WorkflowState:
        """Persist actual command output and structured verification evidence."""
        observed = self.store.get_with_token(workflow_id)
        state = observed.state
        if (
            state.status is not WorkflowStatus.RUNNING
            or state.current_stage is not WorkflowStage.VERIFY
        ):
            raise ServiceError("verification evidence requires verification stage")
        artifact = self._workspace.write_artifact(
            workflow_id, "verification.txt", output
        )
        updated = record_verification(
            state,
            command=command,
            exit_code=exit_code,
            output_reference=artifact.path,
            recorded_at=self._clock(),
        )
        return self.store.update(updated, expected_updated_at=observed.updated_at)

    def deliver(self, workflow_id: str) -> WorkflowState:
        """Record reviewed paths and evidence without committing or pushing."""
        observed = self.store.get_with_token(workflow_id)
        state = observed.state
        if (
            state.status is not WorkflowStatus.RUNNING
            or state.current_stage is not WorkflowStage.DELIVER
        ):
            raise ServiceError("delivery requires a completed review")
        if not state.worktree_path:
            raise ExecutionError("workflow has no implementation worktree")
        implementation = self._workspace.read_json_artifact(
            workflow_id, "implementation-paths.json"
        )
        changed_paths = implementation.get("changed_paths")
        if not isinstance(changed_paths, list) or not all(
            isinstance(path, str) and path for path in changed_paths
        ):
            raise ExecutionError("implementation changed-path manifest is invalid")
        payload = {
            "workflow_id": state.workflow_id,
            "baseline_commit": state.baseline_commit,
            "changed_paths": changed_paths,
            "verification": [
                evidence.to_dict() for evidence in state.verification_evidence
            ],
            "committed": False,
            "pushed": False,
        }
        artifact = self._workspace.write_json_artifact(
            workflow_id, "delivery.json", payload
        )
        self._workspace.remove_worktree(state.target_repository, state.worktree_path)
        updated = record_artifact(
            state,
            stage=WorkflowStage.DELIVER,
            path=artifact.path,
            digest=artifact.digest,
            recorded_at=self._clock(),
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
