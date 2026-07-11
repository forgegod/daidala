"""Application service for Wingstaff policy and artifact operations."""

from __future__ import annotations

import hashlib
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .errors import WorkflowError
from .execution import ExecutionError, ExecutionWorkspace
from .kanban import KanbanCardStatus, KanbanGraphAdapter
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
from .state import SkillDigest, StageProfile, WorkflowLedger, WorkflowStage
from .store import StoreError, WorkflowStore
from .workflow import (
    approve_plan,
    new_workflow,
    record_artifact,
    record_card,
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
        kanban: KanbanGraphAdapter | None = None,
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
        board_slug: str,
        target_repository: str,
        goal: str,
        stage_profiles: dict[str, str],
        pack_name: str = "addyosmani",
        workflow_id: str | None = None,
    ) -> WorkflowLedger:
        """Validate inputs and create or resume the initial Kanban graph."""
        pack = load_pack(pack_name)
        require_pack_skills(pack, self._skill_inventory)
        require_pack_skill_revisions(pack, self._skill_content_registry)
        kanban = self._require_kanban()
        selected_id = workflow_id or self._id_factory()
        self._workspace.validate_workflow_id(selected_id)
        profiles = _stage_profiles(stage_profiles)
        kanban.validate_assignees(board_slug, [row.profile for row in profiles])
        try:
            existing = self.store.get(selected_id)
        except StoreError as error:
            if not str(error).startswith("unknown workflow:"):
                raise
        else:
            _require_restart_match(
                existing,
                board_slug=board_slug,
                target_repository=target_repository,
                goal=goal,
                pack_name=pack.name,
                stage_profiles=profiles,
            )
            return self._ensure_initial_graph(existing, pack)
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
            stage_profiles=profiles,
            created_at=self._clock(),
        )
        return self._ensure_initial_graph(self.store.create(ledger), pack)

    def status(self, workflow_id: str) -> WorkflowLedger:
        """Return Wingstaff policy facts without reading or copying Kanban status."""
        return self.store.get(workflow_id)

    def combined_status(self, workflow_id: str) -> tuple[KanbanCardStatus, ...]:
        """Read live card status without persisting it in Wingstaff."""
        return self._require_kanban().combined_status(self.store.get(workflow_id))

    def approve(self, workflow_id: str, plan_digest: str) -> WorkflowLedger:
        """Approve exactly the current durable plan revision and digest."""
        observed = self.store.get_with_token(workflow_id)
        updated = approve_plan(
            observed.ledger,
            plan_digest=plan_digest,
            decided_at=self._clock(),
        )
        if updated is not observed.ledger:
            updated = self.store.update(updated, expected_updated_at=observed.updated_at)
        self._require_kanban().complete_approval(updated)
        updated = self.prepare_implementation(workflow_id)
        return self._ensure_post_gate_graph(updated, load_pack(updated.pack_name))

    def replace_plan(
        self,
        workflow_id: str,
        *,
        path: str,
        digest: str,
    ) -> WorkflowLedger:
        """Record a new plan revision and invalidate approval."""
        observed = self.store.get_with_token(workflow_id)
        previous = observed.ledger
        obsolete = set(WorkflowStage) - {WorkflowStage.DEFINE, WorkflowStage.PLAN}
        self._require_kanban().archive(
            previous,
            "plan revision replaced",
            stages=obsolete,
        )
        if previous.worktree_owned and previous.worktree_path is not None:
            self._workspace.remove_worktree(
                previous.target_repository,
                previous.worktree_path,
            )
            released = release_worktree(previous, released_at=self._clock())
            previous = self.store.update(
                released,
                expected_updated_at=observed.updated_at,
            )
            observed = self.store.get_with_token(workflow_id)
        updated = replace_plan(
            previous,
            path=path,
            digest=digest,
            replaced_at=self._clock(),
        )
        updated = self.store.update(updated, expected_updated_at=observed.updated_at)
        return self._ensure_approval_card(updated, load_pack(updated.pack_name))

    def cancel(self, workflow_id: str, reason: str) -> WorkflowLedger:
        """Remove a Wingstaff-owned worktree; Kanban owns cancellation state."""
        if not isinstance(reason, str) or not reason.strip():
            raise ServiceError("cancellation reason must be a non-empty string")
        observed = self.store.get_with_token(workflow_id)
        ledger = observed.ledger
        self._require_kanban().archive(ledger, reason.strip())
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
        stored = self.store.update(updated, expected_updated_at=observed.updated_at)
        if stage is WorkflowStage.PLAN:
            return self._ensure_approval_card(stored, load_pack(stored.pack_name))
        return stored

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
        output_digest = hashlib.sha256(output.encode("utf-8")).hexdigest()
        artifact = self._workspace.write_artifact(
            workflow_id,
            f"verification-{output_digest}.txt",
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

    def _ensure_initial_graph(self, ledger: WorkflowLedger, pack) -> WorkflowLedger:
        ledger = self._ensure_card(ledger, pack, WorkflowStage.DEFINE)
        define = ledger.card_for(WorkflowStage.DEFINE)
        assert define is not None
        return self._ensure_card(
            ledger,
            pack,
            WorkflowStage.PLAN,
            parents=(define.task_id,),
        )

    def _ensure_approval_card(self, ledger: WorkflowLedger, pack) -> WorkflowLedger:
        plan = ledger.card_for(WorkflowStage.PLAN)
        if plan is None or ledger.artifact_for(WorkflowStage.PLAN) is None:
            raise ServiceError("approval card requires the plan card and artifact")
        return self._ensure_card(
            ledger,
            pack,
            WorkflowStage.APPROVAL,
            parents=(plan.task_id,),
        )

    def _ensure_post_gate_graph(self, ledger: WorkflowLedger, pack) -> WorkflowLedger:
        parent = ledger.card_for(WorkflowStage.APPROVAL)
        if parent is None:
            raise ServiceError("post-gate graph requires the approval card")
        for stage in (
            WorkflowStage.IMPLEMENT,
            WorkflowStage.VERIFY,
            WorkflowStage.REVIEW,
            WorkflowStage.DELIVER,
        ):
            ledger = self._ensure_card(
                ledger,
                pack,
                stage,
                parents=(parent.task_id,),
            )
            parent = ledger.card_for(stage)
            assert parent is not None
        return ledger

    def _ensure_card(
        self,
        ledger: WorkflowLedger,
        pack,
        stage: WorkflowStage,
        *,
        parents: tuple[str, ...] = (),
    ) -> WorkflowLedger:
        task = self._require_kanban().ensure_card(
            ledger,
            pack,
            stage=stage,
            parents=parents,
        )
        revision = (
            0
            if stage in {WorkflowStage.DEFINE, WorkflowStage.PLAN}
            else ledger.plan_revision
        )
        updated = record_card(
            ledger,
            stage=stage,
            task_id=task.task_id,
            idempotency_key=(
                f"wingstaff:{ledger.workflow_id}:"
                f"{revision}:{stage.value}"
            ),
            recorded_at=self._clock(),
        )
        if updated is ledger:
            return ledger
        return self.store.update(updated, expected_updated_at=ledger.updated_at.isoformat())

    def _require_kanban(self) -> KanbanGraphAdapter:
        if self._kanban is None:
            raise ServiceError("Kanban host dispatch is unavailable")
        return self._kanban


def _stage_profiles(values: dict[str, str]) -> tuple[StageProfile, ...]:
    if not isinstance(values, dict):
        raise ServiceError("stage_profiles must be an object")
    expected = {stage.value for stage in WorkflowStage if stage is not WorkflowStage.APPROVAL}
    if set(values) != expected:
        missing = sorted(expected - set(values))
        unknown = sorted(set(values) - expected)
        details = []
        if missing:
            details.append(f"missing: {', '.join(missing)}")
        if unknown:
            details.append(f"unknown: {', '.join(unknown)}")
        raise ServiceError(f"stage_profiles must map every executable stage ({'; '.join(details)})")
    return tuple(
        StageProfile(stage=stage, profile=values[stage.value])
        for stage in WorkflowStage
        if stage is not WorkflowStage.APPROVAL
    )


def _require_restart_match(
    ledger: WorkflowLedger,
    *,
    board_slug: str,
    target_repository: str,
    goal: str,
    pack_name: str,
    stage_profiles: tuple[StageProfile, ...],
) -> None:
    expected = (
        board_slug,
        str(_canonical_local_path(target_repository)),
        goal,
        pack_name,
        stage_profiles,
    )
    actual = (
        ledger.board_slug,
        ledger.target_repository,
        ledger.requested_goal,
        ledger.pack_name,
        ledger.stage_profiles,
    )
    if actual != expected:
        raise ServiceError("workflow restart inputs do not match the existing ledger")


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