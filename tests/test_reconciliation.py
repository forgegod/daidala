from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from daidala.adapters import (
    FindingRecord,
    FindingsAdapter,
    IntakeCategory,
    PublicationState,
    stable_finding_id,
)
from daidala.errors import PolicyViolationError
from daidala.reconciliation import ClaimRecoveryEvidence, PendingFindingStore

NOW = datetime(2026, 7, 13, 12, 0, tzinfo=UTC)
CYCLE_ID = "cycle-" + "a" * 64


def pending_finding() -> FindingRecord:
    evidence_digest = "b" * 64
    title = "Hermes candidate breaks discovery"
    return FindingRecord(
        finding_id=stable_finding_id(
            "forgegod-daidala", IntakeCategory.COMPATIBILITY, title, evidence_digest
        ),
        project_id="forgegod-daidala",
        category=IntakeCategory.COMPATIBILITY,
        title=title,
        evidence_digest=evidence_digest,
        acceptance_criteria=("Fresh discovery succeeds.",),
        publication_state=PublicationState.PENDING,
    )


class FakeFindings(FindingsAdapter):
    def __init__(self, *, mutate_title: bool = False) -> None:
        self.mutate_title = mutate_title
        self.calls = 0

    def synchronize(self, finding: FindingRecord) -> FindingRecord:
        self.calls += 1
        title = "Changed by adapter" if self.mutate_title else finding.title
        finding_id = (
            stable_finding_id(
                finding.project_id, finding.category, title, finding.evidence_digest
            )
            if self.mutate_title
            else finding.finding_id
        )
        return replace(
            finding,
            finding_id=finding_id,
            title=title,
            publication_state=PublicationState.PUBLISHED,
            remote_identity="issue-42",
            remote_url="https://github.com/forgegod/daidala/issues/42",
        )


def test_pending_finding_replay_returns_verified_publication(tmp_path: Path) -> None:
    store = PendingFindingStore(tmp_path)
    pending = store.save_pending(pending_finding())
    adapter = FakeFindings()

    first = store.synchronize(pending.finding_id, pending.project_id, adapter)
    second = store.synchronize(pending.finding_id, pending.project_id, adapter)

    assert first == second
    assert first.publication_state is PublicationState.PUBLISHED
    assert adapter.calls == 1


def test_pending_finding_rejects_adapter_identity_mutation(tmp_path: Path) -> None:
    store = PendingFindingStore(tmp_path)
    pending = store.save_pending(pending_finding())

    with pytest.raises(PolicyViolationError, match="immutable finding fields"):
        store.synchronize(pending.finding_id, pending.project_id, FakeFindings(mutate_title=True))


def test_claim_recovery_requires_expiry_and_two_no_owner_proofs() -> None:
    recoverable = ClaimRecoveryEvidence(
        cycle_id=CYCLE_ID,
        intake_item_id="42",
        claimant=CYCLE_ID,
        observed_at=NOW,
        lease_expires_at=NOW - timedelta(seconds=1),
        daidala_has_active_owner=False,
        board_has_active_owner=False,
    )

    assert recoverable.recoverable
    recoverable.require_recoverable()
    with pytest.raises(PolicyViolationError, match="no active owner"):
        replace(recoverable, board_has_active_owner=True).require_recoverable()
    with pytest.raises(PolicyViolationError, match="has not expired"):
        replace(recoverable, lease_expires_at=NOW + timedelta(seconds=1)).require_recoverable()
