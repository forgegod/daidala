from __future__ import annotations

from datetime import UTC, datetime

import pytest

from daidala.errors import PolicyViolationError
from daidala.state import (
    ApprovalSummary,
    ReviewDisposition,
    ReviewDispositionAction,
    ReviewFinding,
    ReviewOutcome,
    ReviewRecord,
)

NOW = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)
DIGEST = "a" * 64


def review(*, outcome: ReviewOutcome, findings: tuple[ReviewFinding, ...] = ()) -> ReviewRecord:
    summary = ApprovalSummary(
        headline="Review summary.",
        changes=("Inspect the implementation diff.",),
        affected_areas=("fixture",),
        risks=(),
        verification=("pytest passed.",),
    )
    return ReviewRecord(
        workflow_id="review-fixture",
        plan_digest=DIGEST,
        plan_revision=1,
        policy_revision=1,
        constraints_revision=1,
        constraints_digest="b" * 64,
        implementation_digest="c" * 64,
        verification_digests=("d" * 64,),
        activation_digest="e" * 64,
        outcome=outcome,
        summary=summary,
        summary_digest=summary.digest_for("c" * 64),
        findings=findings,
        recorded_at=NOW,
    )


def test_accepted_review_rejects_blocking_finding() -> None:
    finding = ReviewFinding(
        finding_id="unsafe-change",
        severity="high",
        blocking=True,
        title="Unsafe change.",
        rationale="The implementation evidence requires revision.",
        evidence_digests=("c" * 64,),
    )

    with pytest.raises(PolicyViolationError, match="accepted review cannot contain blocking"):
        review(outcome=ReviewOutcome.ACCEPTED, findings=(finding,))


def test_disposition_carries_the_exact_review_evidence_tuple() -> None:
    record = review(outcome=ReviewOutcome.ACCEPTED)
    disposition = ReviewDisposition(
        review_digest=record.digest,
        implementation_digest=record.implementation_digest,
        verification_digests=record.verification_digests,
        plan_digest=record.plan_digest,
        plan_revision=record.plan_revision,
        policy_revision=record.policy_revision,
        constraints_revision=record.constraints_revision,
        constraints_digest=record.constraints_digest,
        action=ReviewDispositionAction.ACCEPT_DELIVERY,
        actor="fixture operator",
        rationale="Accept the exact reviewed evidence for delivery.",
        decided_at=NOW,
    )

    assert disposition.to_dict()["review_digest"] == record.digest
    assert disposition.action is ReviewDispositionAction.ACCEPT_DELIVERY


def test_review_summary_digest_is_bound_to_implementation() -> None:
    record = review(outcome=ReviewOutcome.ACCEPTED)

    assert ReviewRecord.from_dict(record.to_dict()) == record
    with pytest.raises(PolicyViolationError, match="summary digest"):
        ReviewRecord.from_dict({**record.to_dict(), "summary_digest": "f" * 64})
    with pytest.raises(PolicyViolationError, match="unknown: unexpected"):
        ReviewRecord.from_dict({**record.to_dict(), "unexpected": True})


def test_review_finding_evidence_is_canonical() -> None:
    with pytest.raises(PolicyViolationError, match="sorted and unique"):
        ReviewFinding(
            finding_id="duplicate-evidence",
            severity="medium",
            blocking=True,
            title="Duplicate evidence.",
            rationale="The same evidence digest was repeated.",
            evidence_digests=("c" * 64, "c" * 64),
        )
