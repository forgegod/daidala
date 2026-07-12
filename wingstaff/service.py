"""Application service for Wingstaff policy and artifact operations."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .constraints import WorkflowConstraints
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
from .state import (
    ActivationCategory,
    ActivationDecision,
    ActivationManifest,
    ActivationManifestReference,
    ActivationReferenceState,
    SkillDigest,
    StageProfile,
    WorkflowLedger,
    WorkflowStage,
)
from .store import StoreError, WorkflowStore
from .workflow import (
    _require_stage_activation,
    approve_plan,
    new_workflow,
    record_artifact,
    record_card,
    record_skill_activation,
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
            pack_source_revision=pack.source_revision,
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
        _require_stage_activation(observed.ledger, stage)
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
        _require_stage_activation(ledger, WorkflowStage.IMPLEMENT)
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
        _require_stage_activation(observed.ledger, WorkflowStage.VERIFY)
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

    def record_skill_activation(
        self,
        workflow_id: str,
        *,
        stage: WorkflowStage,
        supersedes_digest: str | None,
        decisions: list[dict],
        board_slug: str,
        task_id: str,
    ) -> tuple[ActivationManifestReference, WorkflowLedger]:
        """Validate, reserve, create, and finalize one worker activation manifest."""
        for attempt in range(3):
            try:
                return self._record_skill_activation_once(
                    workflow_id,
                    stage=stage,
                    supersedes_digest=supersedes_digest,
                    decisions=decisions,
                    board_slug=board_slug,
                    task_id=task_id,
                )
            except StoreError as error:
                if "modified concurrently" not in str(error) or attempt == 2:
                    raise
        raise AssertionError("unreachable activation retry state")

    def _record_skill_activation_once(
        self,
        workflow_id: str,
        *,
        stage: WorkflowStage,
        supersedes_digest: str | None,
        decisions: list[dict],
        board_slug: str,
        task_id: str,
    ) -> tuple[ActivationManifestReference, WorkflowLedger]:
        observed = self.store.get_with_token(workflow_id)
        ledger = observed.ledger
        card = ledger.card_for(stage)
        if board_slug != ledger.board_slug:
            raise ServiceError("Kanban board does not match the workflow")
        if card is None or task_id != card.task_id:
            raise ServiceError("Kanban task does not match the current stage card")
        live = self._require_kanban().show_card(ledger, stage)
        if live.assignee != ledger.profile_for(stage):
            raise ServiceError("Kanban task assignee does not match the current stage profile")
        pack = load_pack(ledger.pack_name)
        manifest = _activation_manifest(
            ledger,
            pack,
            stage=stage,
            supersedes_digest=supersedes_digest,
            decisions=decisions,
        )
        references = [
            row
            for row in ledger.activation_manifests
            if row.stage is stage
            and row.plan_revision == ledger.activation_revision_for(stage)
            and row.policy_revision == ledger.policy_revision
            and row.constraints_digest == ledger.current_constraints_digest
        ]
        latest = references[-1] if references else None
        if latest is not None and latest.state is ActivationReferenceState.FINALIZED:
            existing = self._workspace.read_activation_manifest(workflow_id, latest.path)
            if (
                existing.decisions == manifest.decisions
                and existing.supersedes_digest == supersedes_digest
            ):
                return latest, ledger
            manifest = replace(manifest, sequence=latest.sequence + 1)
        path = self._workspace.activation_manifest_path(workflow_id, manifest)
        pending = record_skill_activation(
            ledger,
            manifest=manifest,
            pack=pack,
            path=path,
            state=ActivationReferenceState.PENDING,
            recorded_at=self._clock(),
        )
        if pending is not ledger:
            pending = self.store.update(pending, expected_updated_at=observed.updated_at)
        reference = pending.activation_manifests[-1]
        if reference.state is ActivationReferenceState.FINALIZED:
            return reference, pending
        try:
            stored = self._workspace.write_activation_manifest(workflow_id, manifest)
        except ExecutionError as error:
            if "already exists" not in str(error):
                raise
            existing = self._workspace.read_activation_manifest(workflow_id, path)
            if existing.canonical_bytes() != manifest.canonical_bytes():
                raise ServiceError("existing activation artifact content conflicts") from error
        else:
            if stored.path != path or stored.digest != reference.digest:
                raise ServiceError("stored activation artifact does not match its reservation")
        observed = self.store.get_with_token(workflow_id)
        finalized = record_skill_activation(
            observed.ledger,
            manifest=manifest,
            pack=pack,
            path=path,
            state=ActivationReferenceState.FINALIZED,
            recorded_at=self._clock(),
        )
        if finalized is not observed.ledger:
            finalized = self.store.update(finalized, expected_updated_at=observed.updated_at)
        return finalized.activation_manifests[-1], finalized

    def deliver(self, workflow_id: str) -> WorkflowLedger:
        """Record reviewed evidence and remove the worktree without commit or push."""
        observed = self.store.get_with_token(workflow_id)
        ledger = observed.ledger
        _require_stage_activation(ledger, WorkflowStage.DELIVER)
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
        constraints = None
        current = ledger.current_constraints
        if current is not None:
            artifact = self._workspace.read_constraints_artifact(
                ledger.workflow_id, current.path
            )
            constraints = WorkflowConstraints.from_dict(
                json.loads(artifact.canonical_content)
            )
        task = self._require_kanban().ensure_card(
            ledger,
            pack,
            stage=stage,
            parents=parents,
            constraints=constraints,
        )
        revision = (
            0
            if stage in {WorkflowStage.DEFINE, WorkflowStage.PLAN}
            else ledger.plan_revision
        )
        constraint_key = ledger.current_constraints_digest or "none"
        updated = record_card(
            ledger,
            stage=stage,
            task_id=task.task_id,
            idempotency_key=(
                f"wingstaff:{ledger.workflow_id}:{revision}:"
                f"{ledger.policy_revision}:{constraint_key}:{stage.value}"
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


def _activation_manifest(
    ledger: WorkflowLedger,
    pack,
    *,
    stage: WorkflowStage,
    supersedes_digest: str | None,
    decisions: list[dict],
) -> ActivationManifest:
    if not isinstance(decisions, list):
        raise ServiceError("activation decisions must be an array")
    pack_stage = next((row for row in pack.stages if row.id == stage.value), None)
    if pack_stage is None:
        raise ServiceError("activation stage is not declared by the selected pack")
    if len(decisions) != len(pack_stage.skills):
        raise ServiceError("activation decisions must cover the exact stage skill set")
    supplied: dict[str, dict] = {}
    expected_fields = {
        "name",
        "category",
        "rank",
        "matched_criteria",
        "evidence",
        "rationale",
        "condition",
    }
    for raw in decisions:
        if not isinstance(raw, dict) or set(raw) != expected_fields:
            raise ServiceError("activation decision fields are invalid")
        name = raw["name"]
        if not isinstance(name, str) or name in supplied:
            raise ServiceError("activation decision names must be unique strings")
        supplied[name] = raw
    expected_names = {skill.name for skill in pack_stage.skills}
    if set(supplied) != expected_names:
        raise ServiceError("activation decisions must cover the exact stage skill set")
    digests = {row.name: row.digest for row in ledger.skill_digests}
    enriched = tuple(
        ActivationDecision(
            name=skill.name,
            skill_digest=digests[skill.name],
            activation_mode=skill.activation,
            category=ActivationCategory(supplied[skill.name]["category"]),
            rank=supplied[skill.name]["rank"],
            matched_criteria=tuple(supplied[skill.name]["matched_criteria"]),
            evidence=tuple(supplied[skill.name]["evidence"]),
            rationale=supplied[skill.name]["rationale"],
            condition=supplied[skill.name]["condition"],
        )
        for skill in pack_stage.skills
    )
    references = [
        row
        for row in ledger.activation_manifests
        if row.stage is stage
        and row.plan_revision == ledger.activation_revision_for(stage)
        and row.policy_revision == ledger.policy_revision
        and row.constraints_digest == ledger.current_constraints_digest
    ]
    sequence = references[-1].sequence if references else 1
    return ActivationManifest(
        schema="wingstaff.skill-activation/v1",
        workflow_id=ledger.workflow_id,
        stage=stage,
        plan_revision=ledger.activation_revision_for(stage),
        pack=ledger.pack_name,
        pack_source_revision=ledger.pack_source_revision,
        sequence=sequence,
        supersedes_digest=supersedes_digest,
        decisions=enriched,
        policy_revision=ledger.policy_revision,
        constraints_digest=ledger.current_constraints_digest,
    )


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