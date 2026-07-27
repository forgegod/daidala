"""Bounded read models and deterministic previews for attended review decisions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .errors import PolicyViolationError
from .state import (
    PlanRevisionRequestReference,
    ReviewDispositionAction,
    ReviewOutcome,
    WorkflowLedger,
    WorkflowStage,
)

MAX_REVIEW_FEEDBACK_BYTES = 4096
_POST_GATE_STAGES = (
    WorkflowStage.IMPLEMENT,
    WorkflowStage.VERIFY,
    WorkflowStage.REVIEW,
    WorkflowStage.DELIVER,
)


def normalize_review_feedback(value: str) -> str:
    if not isinstance(value, str):
        raise PolicyViolationError("review rationale must be text")
    normalized = value.strip()
    if not normalized:
        raise PolicyViolationError("review rationale must not be empty")
    if "\x00" in normalized or len(normalized.encode("utf-8")) > MAX_REVIEW_FEEDBACK_BYTES:
        raise PolicyViolationError(
            "review rationale must be valid bounded text "
            f"({MAX_REVIEW_FEEDBACK_BYTES} bytes maximum)"
        )
    return normalized


def _public_revision_request(
    request: PlanRevisionRequestReference,
) -> dict[str, Any]:
    packet = request.to_dict()
    packet.pop("request_path", None)
    packet.pop("successor_packet_path", None)
    return packet


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )


def _digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_json_bytes(payload)).hexdigest()


def _artifact_id(
    workflow_id: str,
    stage: WorkflowStage,
    *,
    policy_revision: int,
    plan_revision: int,
    digest: str,
) -> str:
    return (
        f"{workflow_id}:{stage.value}:policy-{policy_revision}:"
        f"plan-{plan_revision}:{digest}"
    )


@dataclass(frozen=True)
class ReviewDecisionPreview:
    workflow_id: str
    review_digest: str
    action: ReviewDispositionAction
    actor: str
    rationale: str
    rationale_digest: str
    cards_to_archive: tuple[dict[str, str], ...]
    worktree_to_release: str | None
    next_plan_revision: int | None
    next_assignee: str | None
    next_state: str
    revision_request: dict[str, Any] | None = None
    revision_request_digest: str | None = None
    successor_packet: dict[str, Any] | None = None
    successor_packet_digest: str | None = None

    def __post_init__(self) -> None:
        if bool(self.revision_request) != bool(self.revision_request_digest):
            raise PolicyViolationError("revision request payload and digest must both be present")
        if bool(self.successor_packet) != bool(self.successor_packet_digest):
            raise PolicyViolationError("successor packet payload and digest must both be present")

    def identity_dict(self) -> dict[str, Any]:
        return {
            "schema": "daidala.review-decision-preview/v1",
            "workflow_id": self.workflow_id,
            "review_digest": self.review_digest,
            "action": self.action.value,
            "actor": self.actor,
            "rationale": self.rationale,
            "rationale_digest": self.rationale_digest,
            "cards_to_archive": list(self.cards_to_archive),
            "worktree_to_release": self.worktree_to_release,
            "next_plan_revision": self.next_plan_revision,
            "next_assignee": self.next_assignee,
            "next_state": self.next_state,
            "revision_request": self.revision_request,
            "revision_request_digest": self.revision_request_digest,
            "successor_packet": self.successor_packet,
            "successor_packet_digest": self.successor_packet_digest,
        }

    @property
    def digest(self) -> str:
        return _digest(self.identity_dict())

    def to_dict(self) -> dict[str, Any]:
        return {**self.identity_dict(), "preview_digest": self.digest}

    def revision_request_bytes(self) -> bytes:
        if self.revision_request is None:
            raise PolicyViolationError("decision does not produce a revision request")
        return _json_bytes(self.revision_request)

    def successor_packet_bytes(self) -> bytes:
        if self.successor_packet is None:
            raise PolicyViolationError("decision does not produce a successor packet")
        return _json_bytes(self.successor_packet)


def build_review_packet(ledger: WorkflowLedger) -> dict[str, Any]:
    """Project the current bounded review/disposition decision surface."""
    review = ledger.review
    if review is None:
        pending = ledger.pending_revision_request
        if pending is None:
            raise PolicyViolationError("workflow has no current structured review")
        pending_packet = _public_revision_request(pending)
        plan_card = ledger.card_for(WorkflowStage.PLAN)
        return {
            "schema": "daidala.review-packet/v1",
            "workflow_id": ledger.workflow_id,
            "board_slug": ledger.board_slug,
            "review": None,
            "review_digest": pending.source_review_digest,
            "disposition": None,
            "allowed_actions": [],
            "cards": {
                "review": pending.source_review_card_id,
                "plan": plan_card.task_id if plan_card else None,
            },
            "pending_revision_request": pending_packet,
        }
    review_card = ledger.card_for(WorkflowStage.REVIEW)
    plan_card = ledger.card_for(WorkflowStage.PLAN)
    allowed = [
        ReviewDispositionAction.REQUEST_REVISION.value,
        ReviewDispositionAction.REJECT_WORKFLOW.value,
    ]
    if review.outcome is ReviewOutcome.ACCEPTED and not any(
        finding.blocking for finding in review.findings
    ):
        allowed.insert(0, ReviewDispositionAction.ACCEPT_DELIVERY.value)
    return {
        "schema": "daidala.review-packet/v1",
        "workflow_id": ledger.workflow_id,
        "board_slug": ledger.board_slug,
        "exact_tuple": {
            "plan_digest": review.plan_digest,
            "plan_revision": review.plan_revision,
            "policy_revision": review.policy_revision,
            "constraints_revision": review.constraints_revision,
            "constraints_digest": review.constraints_digest,
            "implementation_digest": review.implementation_digest,
            "verification_digests": list(review.verification_digests),
            "activation_digest": review.activation_digest,
        },
        "review": review.to_dict(),
        "review_digest": review.digest,
        "disposition": (
            ledger.review_disposition.to_dict() if ledger.review_disposition else None
        ),
        "allowed_actions": allowed,
        "cards": {
            "review": review_card.task_id if review_card else None,
            "plan": plan_card.task_id if plan_card else None,
        },
        "pending_revision_request": (
            _public_revision_request(ledger.pending_revision_request)
            if ledger.pending_revision_request
            else None
        ),
    }


def build_review_decision_preview(
    ledger: WorkflowLedger,
    *,
    action: ReviewDispositionAction,
    actor: str,
    rationale: str,
) -> ReviewDecisionPreview:
    review = ledger.review
    if review is None:
        raise PolicyViolationError("review decision requires a current structured review")
    actor = normalize_review_feedback(actor)
    if len(actor) > 200:
        raise PolicyViolationError("review actor must be at most 200 characters")
    rationale = normalize_review_feedback(rationale)
    rationale_digest = hashlib.sha256(rationale.encode("utf-8")).hexdigest()
    existing = ledger.review_disposition
    if existing is not None:
        if (
            existing.review_digest != review.digest
            or existing.action is not action
            or existing.rationale != rationale
        ):
            raise PolicyViolationError("current review already has a different disposition")
        actor = existing.actor
        rationale_digest = hashlib.sha256(rationale.encode("utf-8")).hexdigest()
    if action is ReviewDispositionAction.ACCEPT_DELIVERY and (
        review.outcome is not ReviewOutcome.ACCEPTED
        or any(finding.blocking for finding in review.findings)
    ):
        raise PolicyViolationError(
            "delivery acceptance requires an accepted review without blocking findings"
        )
    cards = (
        ()
        if action is ReviewDispositionAction.ACCEPT_DELIVERY
        else tuple(
            {"stage": stage.value, "task_id": card.task_id}
            for stage in _POST_GATE_STAGES
            if (card := ledger.card_for(stage)) is not None
        )
    )
    common = {
        "workflow_id": ledger.workflow_id,
        "review_digest": review.digest,
        "action": action,
        "actor": actor,
        "rationale": rationale,
        "rationale_digest": rationale_digest,
        "cards_to_archive": cards,
        "worktree_to_release": (
            ledger.worktree_path
            if ledger.worktree_owned
            and action is not ReviewDispositionAction.ACCEPT_DELIVERY
            else None
        ),
    }
    if action is not ReviewDispositionAction.REQUEST_REVISION:
        return ReviewDecisionPreview(
            **common,
            next_plan_revision=None,
            next_assignee=None,
            next_state=(
                "delivery_accepted"
                if action is ReviewDispositionAction.ACCEPT_DELIVERY
                else "workflow_rejected"
            ),
        )

    plan = ledger.artifact_for(WorkflowStage.PLAN)
    definition = ledger.artifact_for(WorkflowStage.DEFINE)
    implementation = ledger.artifact_for(WorkflowStage.IMPLEMENT)
    review_card = ledger.card_for(WorkflowStage.REVIEW)
    if definition is None or plan is None or implementation is None or review_card is None:
        raise PolicyViolationError(
            "revision request requires definition, current plan, implementation, and review card"
        )
    target_revision = ledger.plan_revision + 1
    findings = [finding.to_dict() for finding in review.findings]
    disposition_preview = {
        "action": action.value,
        "actor": actor,
        "rationale": rationale,
        "rationale_digest": rationale_digest,
    }
    disposition_preview_digest = _digest(disposition_preview)
    request_payload: dict[str, Any] = {
        "schema": "daidala.plan-revision-request/v1",
        "workflow_id": ledger.workflow_id,
        "source_as_of": review.recorded_at.isoformat(),
        "source_review": review.to_dict(),
        "source_review_digest": review.digest,
        "source_disposition": disposition_preview,
        "source_plan": {
            "artifact_id": _artifact_id(
                ledger.workflow_id,
                WorkflowStage.PLAN,
                policy_revision=ledger.policy_revision,
                plan_revision=ledger.plan_revision,
                digest=plan.digest,
            ),
            "digest": plan.digest,
            "plan_revision": ledger.plan_revision,
            "policy_revision": ledger.policy_revision,
            "constraints_revision": ledger.current_constraints_revision,
            "constraints_digest": ledger.current_constraints_digest,
        },
        "rejected_implementation": {
            "artifact_id": _artifact_id(
                ledger.workflow_id,
                WorkflowStage.IMPLEMENT,
                policy_revision=ledger.policy_revision,
                plan_revision=ledger.plan_revision,
                digest=implementation.digest,
            ),
            "digest": implementation.digest,
        },
        "verification": [
            {
                "artifact_id": (
                    f"{ledger.workflow_id}:verification:plan-{ledger.plan_revision}:{digest}"
                ),
                "digest": digest,
            }
            for digest in review.verification_digests
        ],
        "target_plan_revision": target_revision,
    }
    request_digest = _digest(request_payload)
    successor_payload: dict[str, Any] = {
        "schema": "daidala.successor-plan-packet/v1",
        "workflow_id": ledger.workflow_id,
        "target_plan_revision": target_revision,
        "source_plan_revision": ledger.plan_revision,
        "source_definition_digest": definition.digest,
        "source_policy_revision": ledger.policy_revision,
        "source_constraints_revision": ledger.current_constraints_revision,
        "source_constraints_digest": ledger.current_constraints_digest,
        "pack": ledger.pack_name,
        "pack_source_revision": ledger.pack_source_revision,
        "plan_profile": ledger.profile_for(WorkflowStage.PLAN),
        "plan_skills": [
            {"name": row.name, "digest": row.digest} for row in ledger.skill_digests
        ],
        "source_review": {
            "artifact_id": (
                f"{ledger.workflow_id}:review:plan-{ledger.plan_revision}:{review.digest}"
            ),
            "digest": review.digest,
            "card_id": review_card.task_id,
            "activation_digest": review.activation_digest,
        },
        "source_disposition_preview": {
            "artifact_id": (
                f"{ledger.workflow_id}:review-disposition-preview:"
                f"{review.digest}:{disposition_preview_digest}"
            ),
            "digest": disposition_preview_digest,
        },
        "source_implementation": {
            "artifact_id": _artifact_id(
                ledger.workflow_id,
                WorkflowStage.IMPLEMENT,
                policy_revision=ledger.policy_revision,
                plan_revision=ledger.plan_revision,
                digest=implementation.digest,
            ),
            "digest": implementation.digest,
        },
        "source_verification": [
            {
                "artifact_id": (
                    f"{ledger.workflow_id}:verification:plan-{ledger.plan_revision}:{digest}"
                ),
                "digest": digest,
            }
            for digest in review.verification_digests
        ],
        "findings": findings,
        "normalized_feedback": rationale,
        "revision_request_digest": request_digest,
        "durable_goal": ledger.requested_goal,
    }
    successor_digest = _digest(successor_payload)
    return ReviewDecisionPreview(
        **common,
        next_plan_revision=target_revision,
        next_assignee=ledger.profile_for(WorkflowStage.PLAN),
        next_state="plan_revision_pending",
        revision_request=request_payload,
        revision_request_digest=request_digest,
        successor_packet=successor_payload,
        successor_packet_digest=successor_digest,
    )
