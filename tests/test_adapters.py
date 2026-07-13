from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from daidala.adapters import (
    ClaimIdentity,
    FindingRecord,
    IntakeCategory,
    IntakeRecord,
    NotificationReceipt,
    PublicationState,
    stable_finding_id,
)
from daidala.errors import PolicyViolationError

NOW = datetime(2026, 7, 13, 12, 0, tzinfo=UTC)


def test_intake_claim_and_notification_records_are_normalized_and_bounded() -> None:
    claim = ClaimIdentity("controller-1", NOW, NOW + timedelta(minutes=15))
    intake = IntakeRecord(
        adapter="github-issues",
        item_id="42",
        source_url="https://github.com/forgegod/daidala/issues/42",
        category=IntakeCategory.REGRESSION,
        priority=1,
        goal="Fix the reproducible regression",
        acceptance_criteria=("The failing test passes.",),
        evidence_digests=("a" * 64,),
        dependencies=(),
        risk="Low; temporary fixture only.",
        admission_actor="maintainer-1",
        ready=True,
        claim=claim,
    )
    receipt = NotificationReceipt("hermes-gateway", "attended-daidala", "receipt-1", NOW)

    assert intake.claim == claim
    assert receipt.receipt_id == "receipt-1"
    with pytest.raises(PolicyViolationError, match="unready"):
        replace(intake, ready=False)
    with pytest.raises(PolicyViolationError, match="expire after"):
        ClaimIdentity("controller-1", NOW, NOW)


def test_findings_deduplicate_by_stable_identity_and_require_verified_publication() -> None:
    finding_id = stable_finding_id(
        "forgegod-daidala",
        IntakeCategory.COMPATIBILITY,
        "Hermes candidate breaks discovery",
        "b" * 64,
    )
    assert finding_id == stable_finding_id(
        "forgegod-daidala",
        IntakeCategory.COMPATIBILITY,
        "Hermes candidate breaks discovery",
        "b" * 64,
    )
    assert finding_id != stable_finding_id(
        "forgegod-daidala",
        IntakeCategory.COMPATIBILITY,
        "Hermes candidate breaks discovery",
        "c" * 64,
    )

    local = FindingRecord(
        finding_id=finding_id,
        project_id="forgegod-daidala",
        category=IntakeCategory.COMPATIBILITY,
        title="Hermes candidate breaks discovery",
        evidence_digest="b" * 64,
        acceptance_criteria=("Plugin discovery succeeds in a fresh evaluator.",),
        publication_state=PublicationState.PENDING,
    )
    with pytest.raises(PolicyViolationError, match="returned remote identity"):
        replace(local, publication_state=PublicationState.PUBLISHED)
    with pytest.raises(PolicyViolationError, match="cannot claim remote identity"):
        replace(local, remote_identity="issue-42")
    with pytest.raises(PolicyViolationError, match="canonical inputs"):
        replace(local, finding_id="finding-wrong")

    published = replace(
        local,
        publication_state=PublicationState.PUBLISHED,
        remote_identity="issue-42",
        remote_url="https://github.com/forgegod/daidala/issues/42",
    )
    assert published.remote_url is not None
