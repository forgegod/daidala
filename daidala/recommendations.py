"""Pure deterministic recommendation derivation for the Daidala dashboard.

Recommendations are projections of current Daidala policy facts and read-only
live Kanban state into a finite, machine-readable vocabulary. They do not
dispatch workers, mutate cards, score users, predict completion, or use an
LLM. The backend owns this complete vocabulary; the skill and UI must not
invent aliases.

Each recommendation contains:

- ``action_kind`` — one of the documented finite set;
- ``workflow_id`` — the workflow the recommendation belongs to;
- optional ``card_id`` and ``evidence_ref``;
- exact ``plan_revision``/``plan_digest`` and ``constraints_revision``/
  ``constraints_digest`` when relevant;
- ``rationale`` and optional ``blocker_kind`` or missing-capability detail.

Blocked-card payloads additionally identify the concrete missing profile,
skill, capability, comment, or verification command and exit code.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from typing import Any

from .state import (
    ActivationManifestReference,
    ApprovalRecord,
    CardReference,
    VerificationEvidence,
    WorkflowConstraintsArtifact,
    WorkflowConstraintsReference,
    WorkflowLedger,
    WorkflowStage,
)

# Finite action-kind vocabulary. The backend owns this complete set; the
# skill and UI must not invent aliases. See plan §"Pending decisions and
# recommendations".
ACTION_KINDS: tuple[str, ...] = (
    "approve_current_tuple",
    "reapprove_current_tuple",
    "resolve_blocked_card",
    "restore_capability",
    "resolve_verification_failure",
    "replace_rejected_plan",
    "wait_for_dispatch",
    "deliver_reviewed_diff",
)


@dataclass(frozen=True)
class KanbanSnapshot:
    """One live, read-only Kanban card snapshot for a single workflow stage."""

    stage: WorkflowStage
    task_id: str
    status: str
    assignee: str
    block_kind: str | None = None
    block_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage.value,
            "task_id": self.task_id,
            "status": self.status,
            "assignee": self.assignee,
            "block_kind": self.block_kind,
            "block_reason": self.block_reason,
        }


@dataclass(frozen=True)
class Recommendation:
    """One finite machine-readable next-action recommendation."""

    action_kind: str
    workflow_id: str
    rationale: str
    plan_revision: int | None = None
    plan_digest: str | None = None
    constraints_revision: int | None = None
    constraints_digest: str | None = None
    card_id: str | None = None
    evidence_ref: str | None = None
    blocker_kind: str | None = None
    missing_profile: str | None = None
    missing_skill: str | None = None
    missing_capability: str | None = None
    verification_command: str | None = None
    verification_exit_code: int | None = None

    def __post_init__(self) -> None:
        if self.action_kind not in ACTION_KINDS:
            raise ValueError(
                f"recommendation action_kind must be one of {ACTION_KINDS!r}, "
                f"observed {self.action_kind!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}


@dataclass(frozen=True)
class ConstraintView:
    """Immutable view of the current constraint revision for the UI."""

    revision: int
    digest: str
    path: str
    source_skill: str | None
    source_digest: str | None
    canonical_content: str

    @classmethod
    def from_artifact(
        cls, reference: WorkflowConstraintsReference, artifact: WorkflowConstraintsArtifact
    ) -> ConstraintView:
        return cls(
            revision=reference.identity.constraints_revision,
            digest=reference.identity.digest,
            path=reference.path,
            source_skill=artifact.source.name if artifact.source else None,
            source_digest=artifact.source.digest if artifact.source else None,
            canonical_content=artifact.canonical_content,
        )


@dataclass(frozen=True)
class DecisionSummary:
    """Pure summary of workflow decisions and constraints for the UI."""

    pending_decisions: tuple[Recommendation, ...]
    current_constraints: ConstraintView | None = None
    constraint_revisions: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    approvals: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "pending_decisions": [row.to_dict() for row in self.pending_decisions],
            "current_constraints": (
                asdict(self.current_constraints) if self.current_constraints else None
            ),
            "constraint_revisions": list(self.constraint_revisions),
            "approvals": list(self.approvals),
        }


def derive_recommendations(
    ledger: WorkflowLedger,
    kanban: Iterable[KanbanSnapshot],
    constraints_artifact: WorkflowConstraintsArtifact | None = None,
) -> tuple[Recommendation, ...]:
    """Derive the finite set of pending decisions for one workflow.

    The function is pure: it reads ``ledger``, ``kanban``, and an optional
    constraint artifact, and returns recommendations without performing I/O,
    mutating state, or invoking model judgment. Snapshots whose ``stage`` is
    not represented by a card in the ledger are ignored; cards absent from
    ``kanban`` are treated as "host unavailable" and produce no
    recommendations of their own.
    """
    snapshots = {row.stage: row for row in kanban}
    recommendations: list[Recommendation] = []

    plan_artifact = ledger.artifact_for(WorkflowStage.PLAN)
    plan_digest = plan_artifact.digest if plan_artifact else None
    plan_revision = ledger.plan_revision
    constraints_digest = ledger.current_constraints_digest
    constraints_revision = ledger.current_constraints_revision

    if plan_artifact is not None:
        if ledger.approval is None:
            recommendations.append(
                Recommendation(
                    action_kind="approve_current_tuple",
                    workflow_id=ledger.workflow_id,
                    rationale=(
                        "Review the captured plan and approve its displayed "
                        "plan and constraint digests to unblock implementation."
                    ),
                    plan_revision=plan_revision,
                    plan_digest=plan_digest,
                    constraints_revision=constraints_revision,
                    constraints_digest=constraints_digest,
                )
            )
        elif ledger.approval is not None and not _approval_matches_ledger(
            ledger, ledger.approval, plan_artifact
        ):
            recommendations.append(
                Recommendation(
                    action_kind="reapprove_current_tuple",
                    workflow_id=ledger.workflow_id,
                    rationale=(
                        "Current plan or constraint identity differs from the "
                        "recorded approval. Re-review and approve the current "
                        "tuple; stale approval cannot be reused."
                    ),
                    plan_revision=plan_revision,
                    plan_digest=plan_digest,
                    constraints_revision=constraints_revision,
                    constraints_digest=constraints_digest,
                )
            )

    blocked = _blocked_cards(ledger, snapshots)
    for snapshot, card, missing in blocked:
        if missing == "verification":
            evidence = _latest_verification(ledger)
            recommendations.append(
                Recommendation(
                    action_kind="resolve_verification_failure",
                    workflow_id=ledger.workflow_id,
                    rationale=(
                        "Verification evidence has a non-zero exit code. "
                        "Inspect the immutable output and choose plan "
                        "replacement or an evidence-backed retry."
                    ),
                    card_id=card.task_id,
                    evidence_ref=evidence.output_reference if evidence else None,
                    verification_command=evidence.command if evidence else None,
                    verification_exit_code=evidence.exit_code if evidence else None,
                )
            )
            continue
        if missing == "capability":
            references = [
                row
                for row in ledger.activation_manifests
                if row.stage is snapshot.stage and row.blocked
            ]
            reference = references[-1] if references else None
            recommendations.append(
                _capability_recommendation(
                    ledger, snapshot, card, reference, constraints_artifact
                )
            )
            continue
        if missing == "needs_input":
            recommendations.append(
                Recommendation(
                    action_kind="resolve_blocked_card",
                    workflow_id=ledger.workflow_id,
                    rationale=(
                        "Card is blocked awaiting needs_input. Read its "
                        "latest evidence and comment with the requested "
                        "decision, then use the normal Kanban unblock."
                    ),
                    card_id=card.task_id,
                )
            )
            continue
        if missing == "review":
            recommendations.append(
                Recommendation(
                    action_kind="replace_rejected_plan",
                    workflow_id=ledger.workflow_id,
                    rationale=(
                        "Review rejected the captured implementation. "
                        "Replace the plan; do not patch the captured diff "
                        "in place."
                    ),
                    card_id=card.task_id,
                )
            )
            continue
        recommendations.append(
            Recommendation(
                action_kind="resolve_blocked_card",
                workflow_id=ledger.workflow_id,
                rationale=(
                    "Card is blocked; inspect its blocker kind and resolve "
                    "through the normal Kanban unblock path."
                ),
                card_id=card.task_id,
                blocker_kind=snapshot.block_kind,
            )
        )

    wait_for_dispatch = _dispatch_ready_workflow(ledger, snapshots)
    if wait_for_dispatch is not None:
        recommendations.append(wait_for_dispatch)

    if _deliver_ready(ledger, snapshots):
        deliver_card = ledger.card_for(WorkflowStage.DELIVER)
        review_artifact = ledger.artifact_for(WorkflowStage.REVIEW)
        assert deliver_card is not None and review_artifact is not None
        recommendations.append(
            Recommendation(
                action_kind="deliver_reviewed_diff",
                workflow_id=ledger.workflow_id,
                rationale=(
                    "Deliver is ready. Review the immutable diff and "
                    "evidence, then run delivery; commit and push remain "
                    "false."
                ),
                card_id=deliver_card.task_id,
                evidence_ref=review_artifact.path,
            )
        )

    return tuple(recommendations)


def _approval_matches_ledger(
    ledger: WorkflowLedger, approval: ApprovalRecord, plan_artifact: Any
) -> bool:
    return (
        approval.plan_digest == plan_artifact.digest
        and approval.plan_revision == ledger.plan_revision
        and approval.constraints_revision == ledger.current_constraints_revision
        and approval.constraints_digest == ledger.current_constraints_digest
    )


def _blocked_cards(
    ledger: WorkflowLedger, snapshots: dict[WorkflowStage, KanbanSnapshot]
) -> list[tuple[KanbanSnapshot, CardReference, str]]:
    blocked: list[tuple[KanbanSnapshot, CardReference, str]] = []
    for stage in WorkflowStage:
        if stage is WorkflowStage.APPROVAL:
            continue
        card = ledger.card_for(stage)
        snapshot = snapshots.get(stage)
        if card is None or snapshot is None:
            continue
        if snapshot.status != "blocked":
            continue
        kind = (snapshot.block_kind or "").strip().lower() or "needs_input"
        if stage is WorkflowStage.VERIFY and kind in {"verification", "verification_failure"}:
            blocked.append((snapshot, card, "verification"))
        elif kind == "capability":
            blocked.append((snapshot, card, "capability"))
        elif kind == "review":
            blocked.append((snapshot, card, "review"))
        else:
            blocked.append((snapshot, card, "needs_input"))
    return blocked


def _capability_recommendation(
    ledger: WorkflowLedger,
    snapshot: KanbanSnapshot,
    card: CardReference,
    reference: ActivationManifestReference | None,
    constraints_artifact: WorkflowConstraintsArtifact | None,
) -> Recommendation:
    profile = snapshot.assignee
    missing_skill: str | None = None
    missing_capability: str | None = None
    rationale = (
        "Fix the named profile, tool, skill, access, or context problem "
        "before retrying."
    )
    return Recommendation(
        action_kind="restore_capability",
        workflow_id=ledger.workflow_id,
        rationale=rationale,
        card_id=card.task_id,
        blocker_kind=snapshot.block_kind,
        missing_profile=profile,
        missing_skill=missing_skill,
        missing_capability=missing_capability,
        evidence_ref=reference.path if reference else None,
    )


def _latest_verification(ledger: WorkflowLedger) -> VerificationEvidence | None:
    if not ledger.verification_evidence:
        return None
    return max(
        ledger.verification_evidence,
        key=lambda row: row.recorded_at,
    )


def _dispatch_ready_workflow(
    ledger: WorkflowLedger, snapshots: dict[WorkflowStage, KanbanSnapshot]
) -> Recommendation | None:
    """Detect a workflow whose prerequisites for the next card are complete.

    When every prerequisite for the next linked executable card is satisfied
    but the card has not appeared, dispatch is presumed in flight. The
    recommendation tells the operator to wait rather than duplicate work.
    """
    for stage in (
        WorkflowStage.DEFINE,
        WorkflowStage.PLAN,
        WorkflowStage.IMPLEMENT,
        WorkflowStage.VERIFY,
        WorkflowStage.REVIEW,
        WorkflowStage.DELIVER,
    ):
        card = ledger.card_for(stage)
        snapshot = snapshots.get(stage)
        if card is None or snapshot is not None:
            continue
        if not _prerequisites_complete(ledger, stage, snapshots):
            continue
        return Recommendation(
            action_kind="wait_for_dispatch",
            workflow_id=ledger.workflow_id,
            rationale=(
                "All prerequisites for the next linked card are complete. "
                "Wait for or inspect Hermes dispatch; do not create duplicate "
                "work."
            ),
        )
    return None


def _prerequisites_complete(
    ledger: WorkflowLedger,
    stage: WorkflowStage,
    snapshots: dict[WorkflowStage, KanbanSnapshot],
) -> bool:
    if stage is WorkflowStage.DEFINE:
        return True
    parent_stage = {
        WorkflowStage.PLAN: WorkflowStage.DEFINE,
        WorkflowStage.APPROVAL: WorkflowStage.PLAN,
        WorkflowStage.IMPLEMENT: WorkflowStage.APPROVAL,
        WorkflowStage.VERIFY: WorkflowStage.IMPLEMENT,
        WorkflowStage.REVIEW: WorkflowStage.VERIFY,
        WorkflowStage.DELIVER: WorkflowStage.REVIEW,
    }[stage]
    parent_artifact_required = stage in {
        WorkflowStage.PLAN,
        WorkflowStage.IMPLEMENT,
        WorkflowStage.VERIFY,
        WorkflowStage.REVIEW,
        WorkflowStage.DELIVER,
    }
    if parent_artifact_required and ledger.artifact_for(parent_stage) is None:
        return False
    parent_card = ledger.card_for(parent_stage)
    parent_snapshot = snapshots.get(parent_stage)
    if parent_card is None:
        return False
    if parent_snapshot is None:
        return False
    if parent_snapshot.status != "done":
        return False
    if stage is WorkflowStage.IMPLEMENT and (
        ledger.approval is None or not ledger.worktree_owned
    ):
        return False
    return True


def _deliver_ready(
    ledger: WorkflowLedger, snapshots: dict[WorkflowStage, KanbanSnapshot]
) -> bool:
    deliver_card = ledger.card_for(WorkflowStage.DELIVER)
    deliver_snapshot = snapshots.get(WorkflowStage.DELIVER)
    if deliver_card is None or deliver_snapshot is None:
        return False
    if deliver_snapshot.status == "done":
        return False
    review_artifact = ledger.artifact_for(WorkflowStage.REVIEW)
    implement_artifact = ledger.artifact_for(WorkflowStage.IMPLEMENT)
    if review_artifact is None or implement_artifact is None:
        return False
    if not ledger.worktree_owned or not ledger.worktree_path:
        return False
    return deliver_snapshot.status == "ready"


__all__ = [
    "ACTION_KINDS",
    "ConstraintView",
    "DecisionSummary",
    "KanbanSnapshot",
    "Recommendation",
    "derive_recommendations",
]