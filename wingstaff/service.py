"""Application service for Wingstaff policy and artifact operations."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .errors import WorkflowError
from .execution import ExecutionError, ExecutionWorkspace
from .packs import load_pack
from .skills import (
    HermesSkillInventory,
    ProfileSkillContentRegistry,
    SkillContentRegistry,
    SkillInventory,
    pack_skill_digests,
    require_pack_skill_revisions,
    require_pack_skills,
)
from .state import SkillDigest, WorkflowLedger, WorkflowStage
from .store import WorkflowStore
from .workflow import (
    approve_plan,
    new_workflow,
    record_artifact,
    record_verification,
    record_worktree,
    release_worktree,
    replace_plan,
)


class ServiceError(WorkflowError):
    """Raised when an operation cannot satisfy the policy boundary."""


class WorkflowService:
    """Coordinate policy checks, artifacts, worktrees, and durable ledgers."""

    def __init__(
        self,
        store: WorkflowStore,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
        skill_inventory: SkillInventory | None = None,
        skill_content_registry: SkillContentRegistry | None = None,
    ) -> None:
        self.store = store
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: str(uuid4()))
        self._skill_inventory = skill_inventory or HermesSkillInventory()
        self._skill_content_registry = skill_content_registry or ProfileSkillContentRegistry(
            store.data_root.parent / "skills"
        )
        self._workspace = ExecutionWorkspace(store.data_root)

    def start(
        self,
        *,
        board_slug: str,
        target_repository: str,
        goal: str,
        pack_name: str = "addyosmani",
        workflow_id: str | None = None,
    ) -> WorkflowLedger:
        """Validate deterministic inputs and create a fresh policy ledger."""
        pack = load_pack(pack_name)
        require_pack_skills(pack, self._skill_inventory)
        require_pack_skill_revisions(pack, self._skill_content_registry)
        selected_id = workflow_id or self._id_factory()
        self._workspace.validate_workflow_id(selected_id)
        target = _canonical_local_path(target_repository)
        baseline, is_clean = _inspect_repository(target)
        if not is_clean:
            raise ServiceError("target repository is dirty")
        skills = tuple(
            SkillDigest(name=name, digest=digest)
            for name, digest in pack_skill_digests(pack)
        )
        ledger = new_workflow(
            workflow_id=selected_id,
            board_slug=board_slug,
            target_repository=str(target),
            baseline_commit=baseline,
            requested_goal=goal,
            pack_name=pack.name,
            pack_source_revision=f"{pack.source}@{pack.source_revision}",
            skill_digests=skills,
            created_at=self._clock(),
        )
        return self.store.create(ledger)

    def status(self, workflow_id: str) -> WorkflowLedger:
        """Return Wingstaff policy facts without reading or copying Kanban status."""
        return self.store.get(workflow_id)

    def approve(self, workflow_id: str, plan_digest: str) -> WorkflowLedger:
        """Approve exactly the current durable plan revision and digest."""
        observed = self.store.get_with_token(workflow_id)
        updated = approve_plan(
            observed.ledger,
            plan_digest=plan_digest,
            decided_at=self._clock(),
        )
        return self.store.update(updated, expected_updated_at=observed.updated_at)

    def replace_plan(
        self,
        workflow_id: str,
        *,
        path: str,
        digest: str,
    ) -> WorkflowLedger:
        """Record a new plan revision and invalidate approval."""
        observed = self.store.get_with_token(workflow_id)
        updated = replace_plan(
            observed.ledger,
            path=path,
            digest=digest,
            replaced_at=self._clock(),
        )
        return self.store.update(updated, expected_updated_at=observed.updated_at)

    def cancel(self, workflow_id: str, reason: str) -> WorkflowLedger:
        """Remove a Wingstaff-owned worktree; Kanban owns cancellation state."""
        if not isinstance(reason, str) or not reason.strip():
            raise ServiceError("cancellation reason must be a non-empty string")
        observed = self.store.get_with_token(workflow_id)
        ledger = observed.ledger
        if not ledger.worktree_owned or ledger.worktree_path is None:
            return ledger
        self._workspace.remove_worktree(
            ledger.target_repository,
            ledger.worktree_path,
        )
        updated = release_worktree(ledger, released_at=self._clock())
        return self.store.update(updated, expected_updated_at=observed.updated_at)

    def submit_artifact(
        self,
        workflow_id: str,
        *,
        stage: WorkflowStage,
        content: str,
    ) -> WorkflowLedger:
        """Store and record a model-produced definition, plan, or review."""
        if not isinstance(content, str) or not content.strip():
            raise ServiceError("artifact content must be a non-empty string")
        if stage not in {WorkflowStage.DEFINE, WorkflowStage.PLAN, WorkflowStage.REVIEW}:
            raise ServiceError(f"stage {stage.value!r} cannot be submitted as text")
        observed = self.store.get_with_token(workflow_id)
        filename = {
            WorkflowStage.DEFINE: "define.md",
            WorkflowStage.PLAN: "plan.md",
            WorkflowStage.REVIEW: "review.md",
        }[stage]
        artifact = self._workspace.write_artifact(workflow_id, filename, content)
        updated = record_artifact(
            observed.ledger,
            stage=stage,
            path=artifact.path,
            digest=artifact.digest,
            recorded_at=self._clock(),
        )
        return self.store.update(updated, expected_updated_at=observed.updated_at)

    def prepare_implementation(self, workflow_id: str) -> WorkflowLedger:
        """Create and record a worktree only after exact plan approval."""
        observed = self.store.get_with_token(workflow_id)
        ledger = observed.ledger
        if ledger.worktree_owned and ledger.worktree_path:
            return ledger
        baseline, is_clean = _inspect_repository(Path(ledger.target_repository))
        if not is_clean or baseline != ledger.baseline_commit:
            raise ServiceError("target repository changed after workflow creation")
        worktree = self._workspace.create_worktree(
            workflow_id,
            ledger.target_repository,
            ledger.baseline_commit,
        )
        updated = record_worktree(
            ledger,
            worktree_path=worktree,
            recorded_at=self._clock(),
        )
        return self.store.update(updated, expected_updated_at=observed.updated_at)

    def capture_implementation(self, workflow_id: str) -> WorkflowLedger:
        """Capture the immutable pre-verification diff and changed-path scope."""
        observed = self.store.get_with_token(workflow_id)
        ledger = observed.ledger
        existing = ledger.artifact_for(WorkflowStage.IMPLEMENT)
        if existing is not None:
            return ledger
        if not ledger.worktree_path or not ledger.worktree_owned:
            raise ExecutionError("workflow has no Wingstaff-owned implementation worktree")
        diff = self._workspace.capture_diff(ledger.worktree_path)
        changed_paths = self._workspace.changed_paths(ledger.worktree_path)
        artifact = self._workspace.write_artifact(
            workflow_id,
            "implementation.diff",
            diff,
        )
        self._workspace.write_json_artifact(
            workflow_id,
            "implementation-paths.json",
            {"changed_paths": list(changed_paths)},
        )
        updated = record_artifact(
            ledger,
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
    ) -> WorkflowLedger:
        """Persist actual command output and structured verification evidence."""
        observed = self.store.get_with_token(workflow_id)
        artifact = self._workspace.write_artifact(
            workflow_id,
            "verification.txt",
            output,
        )
        updated = record_verification(
            observed.ledger,
            command=command,
            exit_code=exit_code,
            output_reference=artifact.path,
            output_digest=artifact.digest,
            recorded_at=self._clock(),
        )
        return self.store.update(updated, expected_updated_at=observed.updated_at)

    def deliver(self, workflow_id: str) -> WorkflowLedger:
        """Record reviewed evidence and remove the worktree without commit or push."""
        observed = self.store.get_with_token(workflow_id)
        ledger = observed.ledger
        delivery = ledger.artifact_for(WorkflowStage.DELIVER)
        if delivery is None:
            if not ledger.worktree_path or not ledger.worktree_owned:
                raise ExecutionError("workflow has no Wingstaff-owned implementation worktree")
            implementation = self._workspace.read_json_artifact(
                workflow_id,
                "implementation-paths.json",
            )
            changed_paths = implementation.get("changed_paths")
            if not isinstance(changed_paths, list) or not all(
                isinstance(path, str) and path for path in changed_paths
            ):
                raise ExecutionError("implementation changed-path manifest is invalid")
            payload = {
                "workflow_id": ledger.workflow_id,
                "baseline_commit": ledger.baseline_commit,
                "changed_paths": changed_paths,
                "verification": [
                    evidence.to_dict() for evidence in ledger.verification_evidence
                ],
                "committed": False,
                "pushed": False,
            }
            artifact = self._workspace.write_json_artifact(
                workflow_id,
                "delivery.json",
                payload,
            )
            ledger = record_artifact(
                ledger,
                stage=WorkflowStage.DELIVER,
                path=artifact.path,
                digest=artifact.digest,
                recorded_at=self._clock(),
            )
            ledger = self.store.update(
                ledger,
                expected_updated_at=observed.updated_at,
            )
        if ledger.worktree_path and ledger.worktree_owned:
            self._workspace.remove_worktree(
                ledger.target_repository,
                ledger.worktree_path,
            )
            observed_after_delivery = ledger.updated_at.isoformat()
            ledger = release_worktree(ledger, released_at=self._clock())
            ledger = self.store.update(
                ledger,
                expected_updated_at=observed_after_delivery,
            )
        return ledger


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