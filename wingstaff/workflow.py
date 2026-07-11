"""Deterministic updates to the Wingstaff policy and artifact ledger."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from .errors import PolicyViolationError
from .packs import WorkflowPack
from .state import (
    ActivationManifest,
    ActivationManifestReference,
    ActivationReferenceState,
    ApprovalRecord,
    ArtifactReference,
    CardReference,
    SkillDigest,
    StageProfile,
    VerificationEvidence,
    WorkflowLedger,
    WorkflowStage,
)


def new_workflow(
    *,
    workflow_id: str,
    board_slug: str,
    target_repository: str,
    baseline_commit: str,
    requested_goal: str,
    pack_name: str,
    pack_source_revision: str,
    skill_digests: tuple[SkillDigest, ...],
    stage_profiles: tuple[StageProfile, ...],
    created_at: datetime,
) -> WorkflowLedger:
    """Create a policy ledger after deterministic preflight validation."""
    return WorkflowLedger(
        workflow_id=workflow_id,
        board_slug=board_slug,
        target_repository=target_repository,
        baseline_commit=baseline_commit,
        requested_goal=requested_goal,
        pack_name=pack_name,
        pack_source_revision=pack_source_revision,
        skill_digests=skill_digests,
        stage_profiles=stage_profiles,
        created_at=created_at,
        updated_at=created_at,
    )


def record_card(
    ledger: WorkflowLedger,
    *,
    stage: WorkflowStage,
    task_id: str,
    idempotency_key: str,
    recorded_at: datetime,
) -> WorkflowLedger:
    """Record one host-owned Kanban card without copying its status."""
    revision = _card_revision(ledger, stage)
    expected_key = f"wingstaff:{ledger.workflow_id}:{revision}:{stage.value}"
    if idempotency_key != expected_key:
        raise PolicyViolationError(
            f"Kanban idempotency key must be {expected_key!r}"
        )
    candidate = CardReference(
        stage=stage,
        plan_revision=revision,
        task_id=task_id,
        idempotency_key=idempotency_key,
    )
    existing = next(
        (
            row
            for row in ledger.card_references
            if row.stage is stage and row.plan_revision == revision
        ),
        None,
    )
    if existing == candidate:
        return ledger
    if existing is not None:
        raise PolicyViolationError(
            f"stage {stage.value!r} already maps to a different Kanban card"
        )
    if stage is WorkflowStage.APPROVAL and ledger.current_plan_digest is None:
        raise PolicyViolationError("approval card requires a plan artifact")
    if stage in {
        WorkflowStage.IMPLEMENT,
        WorkflowStage.VERIFY,
        WorkflowStage.REVIEW,
        WorkflowStage.DELIVER,
    }:
        _require_approval(ledger)
    _require_not_before(ledger, recorded_at)
    return replace(
        ledger,
        card_references=(*ledger.card_references, candidate),
        updated_at=recorded_at,
    )


def record_artifact(
    ledger: WorkflowLedger,
    *,
    stage: WorkflowStage,
    path: str,
    digest: str,
    recorded_at: datetime,
) -> WorkflowLedger:
    """Record an immutable stage artifact after its Wingstaff policy checks."""
    if stage in {WorkflowStage.APPROVAL, WorkflowStage.VERIFY}:
        raise PolicyViolationError(
            f"stage {stage.value!r} uses approval or verification evidence, not an artifact"
        )
    revision = 0 if stage is WorkflowStage.DEFINE else ledger.plan_revision
    candidate = ArtifactReference(
        stage=stage,
        plan_revision=revision,
        path=path,
        digest=digest,
        recorded_at=recorded_at,
    )
    existing = ledger.artifact_for(stage)
    if existing == candidate:
        return ledger
    if existing is not None:
        raise PolicyViolationError(
            f"stage {stage.value!r} already has a different artifact"
        )
    _require_not_before(ledger, recorded_at)
    if stage is WorkflowStage.PLAN:
        _require_artifact(ledger, WorkflowStage.DEFINE)
    elif stage is WorkflowStage.IMPLEMENT:
        _require_approval(ledger)
        _require_worktree(ledger)
    elif stage is WorkflowStage.REVIEW:
        _require_successful_verification(ledger)
    elif stage is WorkflowStage.DELIVER:
        _require_successful_verification(ledger)
        _require_artifact(ledger, WorkflowStage.REVIEW)
    return replace(
        ledger,
        artifacts=(*ledger.artifacts, candidate),
        updated_at=recorded_at,
    )


def approve_plan(
    ledger: WorkflowLedger,
    *,
    plan_digest: str,
    decided_at: datetime,
) -> WorkflowLedger:
    """Bind approval to the exact current plan revision and digest."""
    candidate = ApprovalRecord(
        plan_digest=plan_digest,
        plan_revision=ledger.plan_revision,
        decided_at=decided_at,
    )
    if (
        ledger.approval is not None
        and ledger.approval.plan_digest == plan_digest
        and ledger.approval.plan_revision == ledger.plan_revision
    ):
        return ledger
    plan = ledger.artifact_for(WorkflowStage.PLAN)
    if plan is None or plan.digest != plan_digest:
        raise PolicyViolationError("approval must match the current plan digest")
    if ledger.approval is not None:
        raise PolicyViolationError("current plan revision already has a different approval")
    _require_not_before(ledger, decided_at)
    return replace(ledger, approval=candidate, updated_at=decided_at)


def replace_plan(
    ledger: WorkflowLedger,
    *,
    path: str,
    digest: str,
    replaced_at: datetime,
) -> WorkflowLedger:
    """Create a fresh plan revision and invalidate approval and post-gate facts."""
    current = ledger.artifact_for(WorkflowStage.PLAN)
    if current is None:
        raise PolicyViolationError("plan replacement requires a plan artifact")
    if ledger.worktree_owned:
        raise PolicyViolationError("release the owned worktree before replacing the plan")
    if current.path == path and current.digest == digest and ledger.approval is None:
        return ledger
    _require_not_before(ledger, replaced_at)
    revision = ledger.plan_revision + 1
    replacement = ArtifactReference(
        stage=WorkflowStage.PLAN,
        plan_revision=revision,
        path=path,
        digest=digest,
        recorded_at=replaced_at,
    )
    return replace(
        ledger,
        plan_revision=revision,
        artifacts=(*ledger.artifacts, replacement),
        approval=None,
        verification_evidence=(),
        updated_at=replaced_at,
    )


def record_worktree(
    ledger: WorkflowLedger,
    *,
    worktree_path: str,
    recorded_at: datetime,
) -> WorkflowLedger:
    """Record one Wingstaff-owned worktree after exact plan approval."""
    if ledger.worktree_path == worktree_path and ledger.worktree_owned:
        return ledger
    if ledger.worktree_path is not None:
        raise PolicyViolationError("workflow already owns a different worktree")
    _require_approval(ledger)
    _require_not_before(ledger, recorded_at)
    path = Path(worktree_path)
    if not path.is_absolute() or path == Path(ledger.target_repository):
        raise PolicyViolationError(
            "worktree path must be an absolute local path distinct from the target repository"
        )
    return replace(
        ledger,
        worktree_path=worktree_path,
        worktree_owned=True,
        updated_at=recorded_at,
    )


def release_worktree(
    ledger: WorkflowLedger,
    *,
    released_at: datetime,
) -> WorkflowLedger:
    """Clear ownership after the validated worktree has been removed."""
    if ledger.worktree_path is None and not ledger.worktree_owned:
        return ledger
    _require_not_before(ledger, released_at)
    return replace(
        ledger,
        worktree_path=None,
        worktree_owned=False,
        updated_at=released_at,
    )


def record_verification(
    ledger: WorkflowLedger,
    *,
    command: str,
    exit_code: int,
    output_reference: str,
    output_digest: str,
    recorded_at: datetime,
) -> WorkflowLedger:
    """Record verification evidence without mirroring the Kanban card status."""
    _require_approval(ledger)
    _require_worktree(ledger)
    _require_artifact(ledger, WorkflowStage.IMPLEMENT)
    evidence = VerificationEvidence(
        command=command,
        exit_code=exit_code,
        output_reference=output_reference,
        output_digest=output_digest,
        plan_revision=ledger.plan_revision,
        recorded_at=recorded_at,
    )
    for existing in ledger.verification_evidence:
        if (
            existing.command == evidence.command
            and existing.exit_code == evidence.exit_code
            and existing.output_reference == evidence.output_reference
            and existing.output_digest == evidence.output_digest
            and existing.plan_revision == evidence.plan_revision
        ):
            return ledger
    _require_not_before(ledger, recorded_at)
    return replace(
        ledger,
        verification_evidence=(*ledger.verification_evidence, evidence),
        updated_at=recorded_at,
    )


def record_skill_activation(
    ledger: WorkflowLedger,
    *,
    manifest: ActivationManifest,
    pack: WorkflowPack,
    path: str,
    state: ActivationReferenceState,
    recorded_at: datetime,
) -> WorkflowLedger:
    """Reserve or finalize one exact, immutable skill activation manifest."""
    if not isinstance(state, ActivationReferenceState):
        raise PolicyViolationError("activation reference state must be pending or finalized")
    _validate_activation_manifest(ledger, manifest, pack)
    digest = hashlib.sha256(manifest.canonical_bytes()).hexdigest()
    revision = ledger.activation_revision_for(manifest.stage)
    references = [
        reference
        for reference in ledger.activation_manifests
        if reference.stage is manifest.stage and reference.plan_revision == revision
    ]
    latest = references[-1] if references else None

    if state is ActivationReferenceState.FINALIZED:
        if latest is None or latest.digest != digest or latest.sequence != manifest.sequence:
            raise PolicyViolationError("activation finalization requires its pending reference")
        if latest.path != path or latest.blocked != manifest.blocked:
            raise PolicyViolationError(
                "activation finalization does not match its pending reference"
            )
        if latest.state is ActivationReferenceState.FINALIZED:
            return ledger
        _require_not_before(ledger, recorded_at)
        finalized = replace(latest, state=ActivationReferenceState.FINALIZED)
        rows = tuple(
            finalized if reference is latest else reference
            for reference in ledger.activation_manifests
        )
        return replace(ledger, activation_manifests=rows, updated_at=recorded_at)

    if latest is not None and latest.digest == digest:
        if latest.path != path or latest.sequence != manifest.sequence:
            raise PolicyViolationError("activation retry does not match its existing reference")
        return ledger
    if latest is not None and latest.state is ActivationReferenceState.PENDING:
        raise PolicyViolationError("pending activation must be recovered before supersession")
    expected_sequence = 1 if latest is None else latest.sequence + 1
    expected_supersedes = None if latest is None else latest.digest
    if manifest.sequence != expected_sequence:
        raise PolicyViolationError(f"activation sequence must be {expected_sequence}")
    if manifest.supersedes_digest != expected_supersedes:
        raise PolicyViolationError("activation must supersede the latest effective digest")
    _require_not_before(ledger, recorded_at)
    pending = ActivationManifestReference(
        stage=manifest.stage,
        plan_revision=manifest.plan_revision,
        sequence=manifest.sequence,
        path=path,
        digest=digest,
        state=ActivationReferenceState.PENDING,
        blocked=manifest.blocked,
        supersedes_digest=manifest.supersedes_digest,
    )
    return replace(
        ledger,
        activation_manifests=(*ledger.activation_manifests, pending),
        updated_at=recorded_at,
    )


def _validate_activation_manifest(
    ledger: WorkflowLedger,
    manifest: ActivationManifest,
    pack: WorkflowPack,
) -> None:
    if manifest.workflow_id != ledger.workflow_id:
        raise PolicyViolationError("activation workflow ID does not match the ledger")
    if manifest.plan_revision != ledger.activation_revision_for(manifest.stage):
        raise PolicyViolationError("activation plan revision does not match the stage")
    if manifest.pack != ledger.pack_name or manifest.pack != pack.name:
        raise PolicyViolationError("activation pack does not match the ledger")
    if (
        manifest.pack_source_revision != ledger.pack_source_revision
        or manifest.pack_source_revision != pack.source_revision
    ):
        raise PolicyViolationError("activation pack source revision does not match the ledger")
    stage = next((row for row in pack.stages if row.id == manifest.stage.value), None)
    if stage is None:
        raise PolicyViolationError("activation stage is not declared by the selected pack")
    if [decision.name for decision in manifest.decisions] != [
        skill.name for skill in stage.skills
    ]:
        raise PolicyViolationError(
            "activation decisions must exactly follow pack stage skill order"
        )
    digests = {skill.name: skill.digest for skill in ledger.skill_digests}
    for decision, skill in zip(manifest.decisions, stage.skills, strict=True):
        if decision.activation_mode is not skill.activation:
            raise PolicyViolationError("activation mode does not match pack policy")
        if decision.skill_digest != digests.get(skill.name):
            raise PolicyViolationError("activation skill digest does not match the ledger")


def _require_stage_activation(ledger: WorkflowLedger, stage: WorkflowStage) -> None:
    reference = ledger.activation_for(stage)
    if reference is None:
        raise PolicyViolationError(
            f"operation requires a finalized {stage.value} skill activation manifest"
        )
    if reference.blocked:
        raise PolicyViolationError(f"{stage.value} skill activation is blocked")


def _card_revision(ledger: WorkflowLedger, stage: WorkflowStage) -> int:
    if stage in {WorkflowStage.DEFINE, WorkflowStage.PLAN}:
        return 0
    return ledger.plan_revision


def _require_approval(ledger: WorkflowLedger) -> None:
    if ledger.approval is None:
        raise PolicyViolationError("operation requires exact approval of the current plan")


def _require_worktree(ledger: WorkflowLedger) -> None:
    if ledger.worktree_path is None or not ledger.worktree_owned:
        raise PolicyViolationError("operation requires a Wingstaff-owned worktree")


def _require_artifact(ledger: WorkflowLedger, stage: WorkflowStage) -> None:
    if ledger.artifact_for(stage) is None:
        raise PolicyViolationError(f"operation requires the {stage.value} artifact")


def _require_successful_verification(ledger: WorkflowLedger) -> None:
    evidence = ledger.verification_evidence
    if not evidence or evidence[-1].exit_code != 0:
        raise PolicyViolationError("operation requires successful verification evidence")


def _require_not_before(ledger: WorkflowLedger, recorded_at: datetime) -> None:
    if recorded_at < ledger.updated_at:
        raise PolicyViolationError(
            f"recorded_at cannot be before updated_at {ledger.updated_at.isoformat()}"
        )