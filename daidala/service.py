"""Application service for Daidala policy and artifact operations."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .artifact_access import (
    ArtifactAccessService,
    ArtifactArchiveLookup,
    ArtifactCatalogEntry,
    ArtifactExport,
    ArtifactId,
    ArtifactText,
    CurrentPlanEvidence,
)
from .constraints import (
    WorkflowConstraints,
    extract_policy_skill_constraints,
    parse_workflow_constraints,
)
from .errors import WorkflowError
from .execution import ExecutionError, ExecutionWorkspace
from .kanban import KanbanCardStatus, KanbanGraphAdapter
from .packs import WorkflowPack, load_pack
from .revision import (
    ReviewDecisionPreview,
    build_review_decision_preview,
    build_review_packet,
    normalize_review_feedback,
)
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
    ApprovalSummary,
    ConstraintSourceProvenance,
    PlanRevisionRequestReference,
    ReviewDisposition,
    ReviewDispositionAction,
    ReviewFinding,
    ReviewOutcome,
    ReviewRecord,
    SkillDigest,
    StageProfile,
    WorkflowConstraintsArtifact,
    WorkflowConstraintsIdentity,
    WorkflowLedger,
    WorkflowStage,
)
from .store import StoreError, WorkflowStore
from .workflow import (
    _require_stage_activation,
    approve_plan,
    begin_plan_revision,
    invalidate_approval,
    new_workflow,
    record_artifact,
    record_card,
    record_constraints,
    record_plan_revision_request,
    record_review,
    record_review_disposition,
    record_skill_activation,
    record_verification,
    record_worktree,
    release_worktree,
    replace_plan,
)


class ServiceError(WorkflowError):
    """Raised when an operation cannot satisfy the policy boundary."""


@dataclass(frozen=True)
class StartPreflight:
    """Mutation-free facts shared by dashboard preview and workflow start."""

    pack: WorkflowPack
    constraint_input: tuple[WorkflowConstraints, ConstraintSourceProvenance | None] | None
    kanban: KanbanGraphAdapter
    target: Path
    baseline_commit: str
    stage_profiles: tuple[StageProfile, ...]


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
        artifact_archive_lookup: ArtifactArchiveLookup | None = None,
    ) -> None:
        self.store = store
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or (lambda: str(uuid4()))
        self._skill_inventory = skill_inventory or HermesSkillInventory()
        self._skill_content_registry = skill_content_registry or ProfileSkillContentRegistry(
            store.data_root.parent / "skills"
        )
        self._workspace = ExecutionWorkspace(store.data_root)
        self._artifact_access = ArtifactAccessService(
            store, archive_lookup=artifact_archive_lookup
        )
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
        constraints_content: str | None = None,
        constraints_skill: str | None = None,
        constraints_skill_digest: str | None = None,
        expected_baseline_commit: str | None = None,
    ) -> WorkflowLedger:
        """Validate inputs and create or resume the initial Kanban graph."""
        preflight = self.validate_start_preflight(
            board_slug=board_slug,
            target_repository=target_repository,
            stage_profiles=stage_profiles,
            pack_name=pack_name,
            workflow_id=workflow_id,
            constraints_content=constraints_content,
            constraints_skill=constraints_skill,
            constraints_skill_digest=constraints_skill_digest,
            expected_baseline_commit=expected_baseline_commit,
        )
        selected_id = workflow_id or self._id_factory()
        try:
            existing = self.store.get(selected_id)
        except StoreError as error:
            if not str(error).startswith("unknown workflow:"):
                raise
        else:
            if (
                expected_baseline_commit is not None
                and existing.baseline_commit != expected_baseline_commit
            ):
                raise ServiceError("existing workflow baseline does not match expected baseline")
            _require_restart_match(
                existing,
                board_slug=board_slug,
                target_repository=target_repository,
                goal=goal,
                pack_name=preflight.pack.name,
                stage_profiles=preflight.stage_profiles,
            )
            if preflight.constraint_input is not None:
                constraints, source = preflight.constraint_input
                if existing.current_constraints_digest != constraints.digest:
                    raise ServiceError("restart constraint content does not match")
                if existing.constraint_references[-1].source != source:
                    raise ServiceError("restart constraint source does not match")
            return self._ensure_initial_graph(existing, preflight.pack)
        skills = tuple(
            SkillDigest(name=name, digest=digest)
            for name, digest in pack_skill_digests(preflight.pack)
        )
        ledger = new_workflow(
            workflow_id=selected_id,
            board_slug=board_slug,
            target_repository=str(preflight.target),
            baseline_commit=preflight.baseline_commit,
            requested_goal=goal,
            pack_name=preflight.pack.name,
            pack_source_revision=preflight.pack.source_revision,
            skill_digests=skills,
            stage_profiles=preflight.stage_profiles,
            created_at=self._clock(),
        )
        created = self.store.create(ledger)
        if preflight.constraint_input is None:
            return self._ensure_initial_graph(created, preflight.pack)
        constraints, source = preflight.constraint_input
        return self.replace_constraints(
            selected_id,
            content=constraints.canonical_bytes().decode("utf-8"),
            expected_current_digest=None,
            source=source,
        )

    def validate_start_preflight(
        self,
        *,
        board_slug: str,
        target_repository: str,
        stage_profiles: dict[str, str],
        pack_name: str = "addyosmani",
        workflow_id: str | None = None,
        constraints_content: str | None = None,
        constraints_skill: str | None = None,
        constraints_skill_digest: str | None = None,
        expected_baseline_commit: str | None = None,
    ) -> StartPreflight:
        """Validate every non-mutating start prerequisite exactly once."""
        pack = load_pack(pack_name)
        require_pack_skills(pack, self._skill_inventory)
        require_pack_skill_revisions(pack, self._skill_content_registry)
        constraint_input = self._resolve_constraint_input(
            content=constraints_content,
            skill_name=constraints_skill,
            skill_digest=constraints_skill_digest,
        )
        if workflow_id is not None:
            self._workspace.validate_workflow_id(workflow_id)
        profiles = _stage_profiles(stage_profiles)
        kanban = self._require_kanban()
        kanban.validate_assignees(board_slug, [row.profile for row in profiles])
        target = _canonical_local_path(target_repository)
        baseline, is_clean = _inspect_repository(target)
        if not is_clean:
            raise ServiceError("target repository is dirty")
        if expected_baseline_commit is not None and baseline != expected_baseline_commit:
            raise ServiceError("repository baseline does not match expected baseline")
        return StartPreflight(
            pack=pack,
            constraint_input=constraint_input,
            kanban=kanban,
            target=target,
            baseline_commit=baseline,
            stage_profiles=profiles,
        )

    def status(self, workflow_id: str) -> WorkflowLedger:
        """Return Daidala policy facts without reading or copying Kanban status."""
        return self.store.get(workflow_id)

    def _resolve_constraint_input(
        self,
        *,
        content: str | None,
        skill_name: str | None,
        skill_digest: str | None,
    ) -> tuple[WorkflowConstraints, ConstraintSourceProvenance | None] | None:
        if content is not None and skill_name is not None:
            raise ServiceError("constraint content and constraint skill are mutually exclusive")
        if skill_digest is not None and skill_name is None:
            raise ServiceError("constraint skill digest requires a constraint skill")
        if content is not None:
            return parse_workflow_constraints(content), None
        if skill_name is None:
            return None
        if skill_digest is None:
            raise ServiceError("constraint skill requires its installed directory digest")
        observed_digest = self._skill_content_registry.content_digest(skill_name)
        if observed_digest != skill_digest:
            raise ServiceError("constraint skill digest does not match installed content")
        markdown = self._skill_content_registry.skill_markdown(skill_name)
        if markdown is None:
            raise ServiceError(f"constraint skill is not installed: {skill_name!r}")
        constraints = parse_workflow_constraints(extract_policy_skill_constraints(markdown))
        return constraints, ConstraintSourceProvenance(skill_name, skill_digest)

    def combined_status(self, workflow_id: str) -> tuple[KanbanCardStatus, ...]:
        """Read live card status without persisting it in Daidala."""
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
        updated = self.prepare_implementation(workflow_id)
        return self._ensure_post_gate_graph(updated, load_pack(updated.pack_name))

    def replace_plan(
        self,
        workflow_id: str,
        *,
        path: str,
        digest: str,
        approval_summary: dict,
    ) -> WorkflowLedger:
        """Record a new plan revision and invalidate approval."""
        observed = self.store.get_with_token(workflow_id)
        previous = observed.ledger
        expected_relative_path = self._workspace.stage_artifact_relative_path(
            stage=WorkflowStage.PLAN,
            policy_revision=previous.policy_revision,
            plan_revision=previous.plan_revision + 1,
            filename="plan.md",
        )
        expected_path = self._workspace.artifact_path(workflow_id, expected_relative_path)
        if Path(path).resolve() != Path(expected_path).resolve():
            raise ServiceError("replacement plan path does not match its revision identity")
        try:
            stored_digest = hashlib.sha256(Path(expected_path).read_bytes()).hexdigest()
        except OSError as error:
            raise ServiceError("replacement plan artifact cannot be read") from error
        if digest != stored_digest:
            raise ServiceError("replacement plan digest does not match artifact content")
        invalidated = invalidate_approval(previous, invalidated_at=self._clock())
        if invalidated is not previous:
            previous = self.store.update(
                invalidated,
                expected_updated_at=observed.updated_at,
            )
            observed = self.store.get_with_token(workflow_id)
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
            approval_summary=ApprovalSummary.from_dict(approval_summary),
            replaced_at=self._clock(),
        )
        updated = self.store.update(updated, expected_updated_at=observed.updated_at)
        return updated

    def replace_constraints(
        self,
        workflow_id: str,
        *,
        content: str,
        expected_current_digest: str | None,
        source: ConstraintSourceProvenance | None = None,
    ) -> WorkflowLedger:
        """Materialize new policy, invalidate stale work, and recreate define/plan."""
        constraints = parse_workflow_constraints(content)
        observed = self.store.get_with_token(workflow_id)
        ledger = observed.ledger
        current_digest = ledger.current_constraints_digest
        if expected_current_digest != current_digest:
            raise ServiceError("expected current constraint digest does not match")

        if (
            constraints.digest == current_digest
            and not ledger.worktree_owned
            and all(
                reference.constraints_digest == current_digest
                for reference in ledger.card_references
            )
        ):
            return ledger

        if constraints.digest != current_digest:
            identity = WorkflowConstraintsIdentity(
                policy_revision=ledger.policy_revision + 1,
                constraints_revision=len(ledger.constraint_references) + 1,
                digest=constraints.digest,
            )
            artifact = WorkflowConstraintsArtifact(
                schema="daidala.workflow-constraints-artifact/v1",
                workflow_id=workflow_id,
                identity=identity,
                canonical_content=constraints.canonical_bytes().decode("utf-8"),
                source=source,
            )
            path = self._workspace.constraints_artifact_path(
                workflow_id, identity.constraints_revision
            )
            try:
                stored = self._workspace.write_constraints_artifact(workflow_id, artifact)
            except ExecutionError as error:
                if "already exists" not in str(error):
                    raise
                if self._workspace.read_constraints_artifact(workflow_id, path) != artifact:
                    raise ServiceError("existing constraint artifact content conflicts") from error
            else:
                if stored.path != path or stored.digest != constraints.digest:
                    raise ServiceError("stored constraint artifact does not match its identity")
            ledger = record_constraints(
                ledger,
                artifact=artifact,
                path=path,
                expected_current_digest=expected_current_digest,
                recorded_at=self._clock(),
            )
            ledger = self.store.update(ledger, expected_updated_at=observed.updated_at)

        self._require_kanban().archive(
            ledger,
            "constraint revision replaced",
            before_policy_revision=ledger.policy_revision,
        )
        if ledger.worktree_owned and ledger.worktree_path is not None:
            self._workspace.remove_worktree(
                ledger.target_repository,
                ledger.worktree_path,
            )
            observed = self.store.get_with_token(workflow_id)
            ledger = release_worktree(observed.ledger, released_at=self._clock())
            ledger = self.store.update(ledger, expected_updated_at=observed.updated_at)
        return self._ensure_initial_graph(ledger, load_pack(ledger.pack_name))

    def replace_constraint_input(
        self,
        workflow_id: str,
        *,
        expected_current_digest: str | None,
        content: str | None = None,
        skill_name: str | None = None,
        skill_digest: str | None = None,
    ) -> WorkflowLedger:
        """Resolve one explicit source and replace the current constraint revision."""
        resolved = self._resolve_constraint_input(
            content=content,
            skill_name=skill_name,
            skill_digest=skill_digest,
        )
        if resolved is None:
            raise ServiceError("constraint replacement requires content or a constraint skill")
        constraints, source = resolved
        return self.replace_constraints(
            workflow_id,
            content=constraints.canonical_bytes().decode("utf-8"),
            expected_current_digest=expected_current_digest,
            source=source,
        )

    def cancel(self, workflow_id: str, reason: str) -> WorkflowLedger:
        """Remove a Daidala-owned worktree; Kanban owns cancellation state."""
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
        approval_summary: dict | None = None,
        board_slug: str,
        task_id: str,
    ) -> WorkflowLedger:
        """Store and record a model-produced definition or plan."""
        if not isinstance(content, str) or not content.strip():
            raise ServiceError("artifact content must be a non-empty string")
        if stage not in {WorkflowStage.DEFINE, WorkflowStage.PLAN}:
            raise ServiceError(f"stage {stage.value!r} cannot be submitted as text")
        if stage is WorkflowStage.PLAN:
            if not isinstance(approval_summary, dict):
                raise ServiceError("plan artifact requires an approval_summary object")
            summary = ApprovalSummary.from_dict(approval_summary)
        else:
            if approval_summary is not None:
                raise ServiceError("approval_summary is accepted only for plan artifacts")
            summary = None
        observed = self.store.get_with_token(workflow_id)
        self._require_current_card_context(
            observed.ledger, stage, board_slug=board_slug, task_id=task_id
        )
        _require_stage_activation(observed.ledger, stage)
        filename = {
            WorkflowStage.DEFINE: "define.md",
            WorkflowStage.PLAN: "plan.md",
        }[stage]
        relative_path = self._workspace.stage_artifact_relative_path(
            stage=stage,
            policy_revision=observed.ledger.policy_revision,
            plan_revision=observed.ledger.plan_revision,
            filename=filename,
        )
        artifact = self._workspace.write_artifact(workflow_id, relative_path, content)
        updated = record_artifact(
            observed.ledger,
            stage=stage,
            path=artifact.path,
            digest=artifact.digest,
            recorded_at=self._clock(),
            approval_summary=summary,
        )
        stored = self.store.update(updated, expected_updated_at=observed.updated_at)
        return stored

    def submit_review(
        self,
        workflow_id: str,
        *,
        outcome: str,
        summary: dict,
        findings: list[dict],
        board_slug: str,
        task_id: str,
    ) -> WorkflowLedger:
        """Record structured automated review evidence for the current revision."""
        observed = self.store.get_with_token(workflow_id)
        ledger = observed.ledger
        self._require_current_card_context(
            ledger, WorkflowStage.REVIEW, board_slug=board_slug, task_id=task_id
        )
        implementation = ledger.artifact_for(WorkflowStage.IMPLEMENT)
        activation = ledger.activation_for(WorkflowStage.REVIEW)
        if implementation is None or activation is None:
            raise ServiceError("review requires implementation and finalized review activation")
        if not isinstance(findings, list):
            raise ServiceError("review findings must be an array")
        required_fields = {"id", "severity", "blocking", "title", "rationale", "evidence_digests"}
        if any(not isinstance(row, dict) or set(row) != required_fields for row in findings):
            raise ServiceError("review finding fields are invalid")
        try:
            review_summary = ApprovalSummary.from_dict(summary)
            record = ReviewRecord(
                workflow_id=ledger.workflow_id,
                plan_digest=ledger.current_plan_digest or "",
                plan_revision=ledger.plan_revision,
                policy_revision=ledger.policy_revision,
                constraints_revision=ledger.current_constraints_revision,
                constraints_digest=ledger.current_constraints_digest,
                implementation_digest=implementation.digest,
                verification_digests=tuple(
                    sorted(
                        {
                            row.output_digest
                            for row in ledger.verification_evidence
                            if row.exit_code == 0
                        }
                    )
                ),
                activation_digest=activation.digest,
                outcome=ReviewOutcome(outcome),
                summary=review_summary,
                summary_digest=review_summary.digest_for(implementation.digest),
                findings=tuple(
                    sorted(
                        (
                            ReviewFinding(
                                finding_id=row["id"],
                                severity=row["severity"],
                                blocking=row["blocking"],
                                title=row["title"],
                                rationale=row["rationale"],
                                evidence_digests=tuple(row["evidence_digests"]),
                            )
                            for row in findings
                        ),
                        key=lambda finding: finding.finding_id,
                    )
                ),
                recorded_at=(
                    ledger.review.recorded_at if ledger.review is not None else self._clock()
                ),
            )
        except (TypeError, ValueError) as error:
            raise ServiceError(f"invalid review evidence: {error}") from error
        updated = record_review(ledger, review=record)
        stored = (
            ledger
            if updated is ledger
            else self.store.update(updated, expected_updated_at=observed.updated_at)
        )
        if record.outcome is ReviewOutcome.ACCEPTED:
            self._require_kanban().complete_review(stored, review_digest=record.digest)
        else:
            self._require_kanban().block_review(
                stored,
                reason=(
                    f"review-required: outcome={record.outcome.value}; "
                    f"review_digest={record.digest}"
                ),
            )
        return stored

    def decide_review(
        self,
        workflow_id: str,
        *,
        review_digest: str,
        action: str,
        actor: str,
        rationale: str,
        _project_to_kanban: bool = True,
    ) -> WorkflowLedger:
        """Record one attended review disposition and open delivery only on acceptance."""
        observed = self.store.get_with_token(workflow_id)
        ledger = observed.ledger
        review = ledger.review
        if review is None or review.digest != review_digest:
            raise ServiceError("review disposition must name the exact current review digest")
        try:
            disposition = ReviewDisposition(
                review_digest=review_digest,
                implementation_digest=review.implementation_digest,
                verification_digests=review.verification_digests,
                plan_digest=review.plan_digest,
                plan_revision=review.plan_revision,
                policy_revision=review.policy_revision,
                constraints_revision=review.constraints_revision,
                constraints_digest=review.constraints_digest,
                action=ReviewDispositionAction(action),
                actor=actor,
                rationale=rationale,
                decided_at=(
                    ledger.review_disposition.decided_at
                    if ledger.review_disposition is not None
                    else self._clock()
                ),
            )
        except (TypeError, ValueError) as error:
            raise ServiceError(f"invalid review disposition: {error}") from error
        updated = record_review_disposition(ledger, disposition=disposition)
        if updated is not ledger:
            updated = self.store.update(updated, expected_updated_at=observed.updated_at)
        if not _project_to_kanban:
            return updated
        if disposition.action is ReviewDispositionAction.ACCEPT_DELIVERY:
            review_card = updated.card_for(WorkflowStage.REVIEW)
            if review_card is None:
                raise ServiceError("delivery requires a current review card")
            return self._ensure_card(
                updated,
                load_pack(updated.pack_name),
                WorkflowStage.DELIVER,
                parents=(review_card.task_id,),
            )
        return updated

    def review_packet(self, workflow_id: str) -> dict[str, object]:
        """Return the bounded current review/disposition decision surface."""
        return build_review_packet(self.store.get(workflow_id))

    def preview_review_decision(
        self,
        workflow_id: str,
        *,
        action: str,
        actor: str,
        rationale: str,
    ) -> ReviewDecisionPreview:
        """Preview one exact attended review action without mutation."""
        try:
            selected = ReviewDispositionAction(action)
        except ValueError as error:
            raise ServiceError(f"invalid review disposition action: {action!r}") from error
        return build_review_decision_preview(
            self.store.get(workflow_id),
            action=selected,
            actor=actor,
            rationale=rationale,
        )

    def apply_review_decision(
        self,
        workflow_id: str,
        *,
        action: str,
        actor: str,
        rationale: str,
        expected_review_digest: str,
        expected_preview_digest: str,
        confirm: bool,
    ) -> dict[str, object]:
        """Apply only a freshly recomputed review preview after literal confirmation."""
        if confirm is not True:
            raise ServiceError("explicit review decision confirmation is required")
        try:
            selected = ReviewDispositionAction(action)
        except ValueError as error:
            raise ServiceError(f"invalid review disposition action: {action!r}") from error
        ledger = self.store.get(workflow_id)
        pending = ledger.pending_revision_request
        if selected is ReviewDispositionAction.REQUEST_REVISION and pending is not None:
            if (
                pending.source_review_digest != expected_review_digest
                or pending.preview_digest != expected_preview_digest
                or pending.normalized_feedback != normalize_review_feedback(rationale)
            ):
                raise ServiceError("review decision inputs changed after preview")
            updated = self._resume_revision_request(workflow_id, pending.preview_digest)
            plan_card = updated.card_for(WorkflowStage.PLAN)
            return {
                "preview": None,
                "replayed": True,
                "workflow": {
                    "workflow_id": updated.workflow_id,
                    "plan_revision": updated.plan_revision,
                    "plan_card_id": plan_card.task_id if plan_card else None,
                },
                "review": build_review_packet(updated),
            }
        preview = build_review_decision_preview(
            ledger,
            action=selected,
            actor=actor,
            rationale=rationale,
        )
        if preview.review_digest != expected_review_digest:
            raise ServiceError("review digest changed after preview")
        if preview.digest != expected_preview_digest:
            raise ServiceError("review decision inputs changed after preview")
        if selected is ReviewDispositionAction.ACCEPT_DELIVERY:
            updated = self.decide_review(
                workflow_id,
                review_digest=preview.review_digest,
                action=selected.value,
                actor=preview.actor,
                rationale=preview.rationale,
            )
        elif selected is ReviewDispositionAction.REJECT_WORKFLOW:
            self.decide_review(
                workflow_id,
                review_digest=preview.review_digest,
                action=selected.value,
                actor=preview.actor,
                rationale=preview.rationale,
            )
            updated = self.cancel(workflow_id, preview.rationale)
        else:
            updated = self._start_revision_request(workflow_id, preview)
        plan_card = updated.card_for(WorkflowStage.PLAN)
        return {
            "preview": preview.to_dict(),
            "replayed": False,
            "workflow": {
                "workflow_id": updated.workflow_id,
                "plan_revision": updated.plan_revision,
                "plan_card_id": plan_card.task_id if plan_card else None,
            },
            "review": build_review_packet(updated),
        }

    def _start_revision_request(
        self,
        workflow_id: str,
        preview: ReviewDecisionPreview,
    ) -> WorkflowLedger:
        if (
            preview.action is not ReviewDispositionAction.REQUEST_REVISION
            or preview.revision_request_digest is None
            or preview.successor_packet_digest is None
        ):
            raise ServiceError("revision request preview is incomplete")
        self.decide_review(
            workflow_id,
            review_digest=preview.review_digest,
            action=preview.action.value,
            actor=preview.actor,
            rationale=preview.rationale,
            _project_to_kanban=False,
        )
        observed = self.store.get_with_token(workflow_id)
        ledger = observed.ledger
        disposition = ledger.review_disposition
        review = ledger.review
        review_card = ledger.card_for(WorkflowStage.REVIEW)
        if disposition is None or review is None or review_card is None:
            raise ServiceError("revision request lost its current review tuple")
        target_revision = ledger.plan_revision + 1
        request_relative = self._workspace.stage_artifact_relative_path(
            stage=WorkflowStage.PLAN,
            policy_revision=ledger.policy_revision,
            plan_revision=target_revision,
            filename="revision-request.json",
        )
        packet_relative = self._workspace.stage_artifact_relative_path(
            stage=WorkflowStage.PLAN,
            policy_revision=ledger.policy_revision,
            plan_revision=target_revision,
            filename="successor-plan-packet.json",
        )
        request_artifact = self._workspace.write_artifact(
            workflow_id,
            request_relative,
            preview.revision_request_bytes().decode("utf-8"),
        )
        packet_artifact = self._workspace.write_artifact(
            workflow_id,
            packet_relative,
            preview.successor_packet_bytes().decode("utf-8"),
        )
        if (
            request_artifact.digest != preview.revision_request_digest
            or packet_artifact.digest != preview.successor_packet_digest
        ):
            raise ServiceError("generated revision artifact digest does not match preview")
        request = PlanRevisionRequestReference(
            workflow_id=workflow_id,
            source_review_digest=review.digest,
            source_disposition_digest=disposition.digest,
            source_plan_digest=review.plan_digest,
            source_plan_revision=review.plan_revision,
            source_policy_revision=review.policy_revision,
            source_constraints_revision=review.constraints_revision,
            source_constraints_digest=review.constraints_digest,
            implementation_digest=review.implementation_digest,
            verification_digests=review.verification_digests,
            target_plan_revision=target_revision,
            preview_digest=preview.digest,
            request_path=request_artifact.path,
            request_digest=request_artifact.digest,
            successor_packet_path=packet_artifact.path,
            successor_packet_digest=packet_artifact.digest,
            source_review_card_id=review_card.task_id,
            source_card_ids=tuple(row["task_id"] for row in preview.cards_to_archive),
            actor=preview.actor,
            normalized_feedback=preview.rationale,
            requested_at=self._clock(),
        )
        updated = record_plan_revision_request(ledger, request=request)
        self.store.update(updated, expected_updated_at=observed.updated_at)
        return self._resume_revision_request(workflow_id, preview.digest)

    def _resume_revision_request(
        self,
        workflow_id: str,
        preview_digest: str,
    ) -> WorkflowLedger:
        observed = self.store.get_with_token(workflow_id)
        ledger = observed.ledger
        request = ledger.pending_revision_request
        if request is None or request.preview_digest != preview_digest:
            raise ServiceError("pending revision request does not match the preview")
        if request.cards_archived_at is None:
            self._require_kanban().archive(
                ledger,
                None,
                task_ids=set(request.source_card_ids),
            )
            archived_at = self._clock()
            updated_request = replace(request, cards_archived_at=archived_at)
            updated = replace(
                ledger,
                revision_requests=(*ledger.revision_requests[:-1], updated_request),
                updated_at=archived_at,
            )
            ledger = self.store.update(updated, expected_updated_at=observed.updated_at)
            observed = self.store.get_with_token(workflow_id)
            request = ledger.pending_revision_request
            assert request is not None
        if request.worktree_released_at is None:
            if ledger.worktree_owned and ledger.worktree_path:
                self._workspace.remove_worktree(
                    ledger.target_repository,
                    ledger.worktree_path,
                )
            released_at = self._clock()
            updated = release_worktree(ledger, released_at=released_at)
            updated_request = replace(request, worktree_released_at=released_at)
            updated = replace(
                updated,
                revision_requests=(*updated.revision_requests[:-1], updated_request),
                updated_at=released_at,
            )
            ledger = self.store.update(updated, expected_updated_at=observed.updated_at)
            observed = self.store.get_with_token(workflow_id)
            request = ledger.pending_revision_request
            assert request is not None
        if ledger.plan_revision == request.source_plan_revision:
            updated = begin_plan_revision(
                ledger,
                preview_digest=preview_digest,
                advanced_at=self._clock(),
            )
            ledger = self.store.update(updated, expected_updated_at=observed.updated_at)
        plan_card = ledger.card_for(WorkflowStage.PLAN)
        if plan_card is None:
            ledger = self._ensure_card(
                ledger,
                load_pack(ledger.pack_name),
                WorkflowStage.PLAN,
                parents=(request.source_review_card_id,),
            )
        return ledger

    def list_artifacts(
        self,
        workflow_id: str,
        *,
        kinds: tuple[str, ...] | None = None,
        revisions: tuple[int, ...] | None = None,
        ledger: WorkflowLedger | None = None,
    ) -> tuple[ArtifactCatalogEntry, ...]:
        """List metadata for exact active ledger-owned artifacts."""
        return self._artifact_access.list(
            workflow_id, kinds=kinds, revisions=revisions, ledger=ledger
        )

    def read_artifact_text(
        self,
        workflow_id: str,
        artifact_id: str | ArtifactId,
        *,
        ledger: WorkflowLedger | None = None,
    ) -> ArtifactText:
        """Read one verified bounded text artifact by opaque ledger identity."""
        return self._artifact_access.read_text(
            workflow_id, artifact_id, ledger=ledger
        )

    def export_artifact(
        self,
        workflow_id: str,
        artifact_id: str | ArtifactId,
        output: str | Path,
        *,
        overwrite: bool = False,
    ) -> ArtifactExport:
        """Export one verified artifact without accepting a source path."""
        return self._artifact_access.export(
            workflow_id, artifact_id, output, overwrite=overwrite
        )

    def current_plan_evidence(
        self, workflow_id: str, *, ledger: WorkflowLedger | None = None
    ) -> CurrentPlanEvidence:
        """Resolve the exact current plan and its source-bound approval summary."""
        return self._artifact_access.current_plan(workflow_id, ledger=ledger)

    def current_implementation_changed_paths(
        self, workflow_id: str, *, ledger: WorkflowLedger | None = None
    ) -> tuple[str, ...]:
        """Return the generated changed-path manifest for the exact current review."""
        if ledger is None:
            ledger = self.store.get(workflow_id)
        elif ledger.workflow_id != workflow_id:
            raise ServiceError("implementation snapshot workflow identity is stale")
        review = ledger.review
        implementation = ledger.artifact_for(WorkflowStage.IMPLEMENT)
        if review is None or implementation is None:
            raise ServiceError("workflow has no current reviewed implementation")
        if implementation.digest != review.implementation_digest:
            raise ServiceError("review implementation identity is stale")
        return self._implementation_changed_paths(ledger)

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

    def capture_implementation(
        self, workflow_id: str, *, board_slug: str, task_id: str
    ) -> WorkflowLedger:
        """Capture the immutable pre-verification diff and changed-path scope."""
        observed = self.store.get_with_token(workflow_id)
        ledger = observed.ledger
        self._require_current_card_context(
            ledger, WorkflowStage.IMPLEMENT, board_slug=board_slug, task_id=task_id
        )
        _require_stage_activation(ledger, WorkflowStage.IMPLEMENT)
        existing = ledger.artifact_for(WorkflowStage.IMPLEMENT)
        if existing is not None:
            return ledger
        if not ledger.worktree_path or not ledger.worktree_owned:
            raise ExecutionError("workflow has no Daidala-owned implementation worktree")
        diff = self._workspace.capture_diff(ledger.worktree_path)
        changed_paths = self._workspace.changed_paths(ledger.worktree_path)
        artifact = self._workspace.write_artifact(
            workflow_id,
            self._workspace.stage_artifact_relative_path(
                stage=WorkflowStage.IMPLEMENT,
                policy_revision=ledger.policy_revision,
                plan_revision=ledger.plan_revision,
                filename="implementation.diff",
            ),
            diff,
        )
        self._workspace.write_json_artifact(
            workflow_id,
            self._workspace.stage_artifact_relative_path(
                stage=WorkflowStage.IMPLEMENT,
                policy_revision=ledger.policy_revision,
                plan_revision=ledger.plan_revision,
                filename="implementation-paths.json",
            ),
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
        board_slug: str,
        task_id: str,
    ) -> WorkflowLedger:
        """Persist actual command output and structured verification evidence."""
        observed = self.store.get_with_token(workflow_id)
        self._require_current_card_context(
            observed.ledger,
            WorkflowStage.VERIFY,
            board_slug=board_slug,
            task_id=task_id,
        )
        _require_stage_activation(observed.ledger, WorkflowStage.VERIFY)
        output_digest = hashlib.sha256(output.encode("utf-8")).hexdigest()
        artifact = self._workspace.write_artifact(
            workflow_id,
            self._workspace.stage_artifact_relative_path(
                stage=WorkflowStage.VERIFY,
                policy_revision=observed.ledger.policy_revision,
                plan_revision=observed.ledger.plan_revision,
                filename=f"verification-{output_digest}.txt",
            ),
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

    def deliver(self, workflow_id: str, *, board_slug: str, task_id: str) -> WorkflowLedger:
        """Record reviewed evidence and remove the worktree without commit or push."""
        observed = self.store.get_with_token(workflow_id)
        ledger = observed.ledger
        self._require_current_card_context(
            ledger, WorkflowStage.DELIVER, board_slug=board_slug, task_id=task_id
        )
        _require_stage_activation(ledger, WorkflowStage.DELIVER)
        delivery = ledger.artifact_for(WorkflowStage.DELIVER)
        if delivery is None:
            if not ledger.worktree_path or not ledger.worktree_owned:
                raise ExecutionError("workflow has no Daidala-owned implementation worktree")
            changed_paths = self._implementation_changed_paths(ledger)
            payload = {
                "workflow_id": ledger.workflow_id,
                "baseline_commit": ledger.baseline_commit,
                "changed_paths": list(changed_paths),
                "verification": [
                    evidence.to_dict() for evidence in ledger.verification_evidence
                ],
                "committed": False,
                "pushed": False,
            }
            artifact = self._workspace.write_json_artifact(
                workflow_id,
                self._workspace.stage_artifact_relative_path(
                    stage=WorkflowStage.DELIVER,
                    policy_revision=ledger.policy_revision,
                    plan_revision=ledger.plan_revision,
                    filename="delivery.json",
                ),
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

    def _implementation_changed_paths(self, ledger: WorkflowLedger) -> tuple[str, ...]:
        implementation_reference = ledger.artifact_for(WorkflowStage.IMPLEMENT)
        if implementation_reference is None:
            raise ExecutionError("workflow has no current implementation artifact")
        manifest = self._workspace.read_json_artifact(
            ledger.workflow_id,
            str(Path(implementation_reference.path).with_name("implementation-paths.json")),
        )
        changed_paths = manifest.get("changed_paths")
        if (
            not isinstance(changed_paths, list)
            or len(changed_paths) > 4096
            or not all(
                isinstance(path, str)
                and bool(path)
                and "\x00" not in path
                and len(path.encode("utf-8")) <= 4096
                for path in changed_paths
            )
            or changed_paths != sorted(set(changed_paths))
        ):
            raise ExecutionError("implementation changed-path manifest is invalid")
        return tuple(changed_paths)

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

    def _ensure_post_gate_graph(self, ledger: WorkflowLedger, pack) -> WorkflowLedger:
        parent = ledger.card_for(WorkflowStage.PLAN)
        if parent is None or ledger.artifact_for(WorkflowStage.PLAN) is None:
            raise ServiceError("post-gate graph requires the current plan card and artifact")
        if ledger.approval is None:
            raise ServiceError("post-gate graph requires exact ledger approval")
        for stage in (
            WorkflowStage.IMPLEMENT,
            WorkflowStage.VERIFY,
            WorkflowStage.REVIEW,
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
            if stage is WorkflowStage.DEFINE
            else ledger.plan_revision
        )
        constraint_key = ledger.current_constraints_digest or "none"
        updated = record_card(
            ledger,
            stage=stage,
            task_id=task.task_id,
            idempotency_key=(
                f"daidala:{ledger.workflow_id}:{revision}:"
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

    def _require_current_card_context(
        self,
        ledger: WorkflowLedger,
        stage: WorkflowStage,
        *,
        board_slug: str,
        task_id: str,
    ) -> None:
        if board_slug != ledger.board_slug:
            raise ServiceError("Kanban board does not match the workflow")
        card = ledger.card_for(stage)
        if card is None or task_id != card.task_id:
            raise ServiceError("Kanban task does not match the current stage card")
        live = self._require_kanban().show_card(ledger, stage)
        if live.assignee != ledger.profile_for(stage):
            raise ServiceError("Kanban task assignee does not match the current stage profile")


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
        schema="daidala.skill-activation/v1",
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