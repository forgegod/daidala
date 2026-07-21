from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from daidala.adapters import IntakeCancellationReceipt, NotificationReceipt
from daidala.cancellation import (
    CancellationArtifactStore,
    CancellationCoordinator,
    CycleCancellation,
    CycleCancellationPreview,
)
from daidala.errors import PolicyViolationError
from daidala.prerequisites import active_admission_paths

NOW = datetime(2026, 7, 21, 10, 0, tzinfo=UTC)
CYCLE = "cycle-" + "a" * 64
PROJECT = "forgegod-daidala"
REASON = "Controlled admission replay completed without implementation."


def preview() -> CycleCancellationPreview:
    return CycleCancellationPreview(
        project_id=PROJECT,
        cycle_id=CYCLE,
        workflow_id=CYCLE,
        board="daidala-forgegod-daidala",
        controller_profile="daidala-self-improvement",
        intake_item_id="42",
        admission_digest="1" * 64,
        manifest_digest="2" * 64,
        registration_digest="3" * 64,
        workflow_digest="4" * 64,
        reason=REASON,
    )


def remote() -> IntakeCancellationReceipt:
    return IntakeCancellationReceipt(
        adapter="github-issues",
        item_id="42",
        cycle_id=CYCLE,
        reason_digest=preview().reason_digest,
        source_url="https://github.com/forgegod/daidala/issues/42",
        state="closed",
        state_reason="not_planned",
        claim_released=True,
        canceled_at=NOW,
    )


def notification() -> NotificationReceipt:
    return NotificationReceipt(
        event_id=f"{CYCLE}:cancelled",
        adapter="hermes-gateway",
        target_alias="attended-daidala",
        receipt_id="receipt-cancel",
        delivered_at=NOW,
    )


def test_cancellation_records_round_trip_and_reject_identity_drift() -> None:
    value = CycleCancellation(preview(), remote(), notification(), NOW)

    assert CycleCancellationPreview.from_dict(dict(value.preview.to_dict())) == value.preview
    assert CycleCancellation.from_dict(value.to_dict()) == value
    assert len(value.preview.reason_digest) == len(value.preview.digest) == len(value.digest) == 64
    with pytest.raises(PolicyViolationError, match="workflow ID"):
        replace(value.preview, workflow_id="another-cycle")
    with pytest.raises(PolicyViolationError, match="reason"):
        replace(value, remote_receipt=replace(remote(), reason_digest="5" * 64))
    raw = value.to_dict()
    raw["unknown"] = True
    with pytest.raises(PolicyViolationError, match="fields mismatch"):
        CycleCancellation.from_dict(raw)


def test_cancellation_store_is_immutable(tmp_path: Path) -> None:
    store = CancellationArtifactStore(tmp_path, PROJECT, CYCLE)
    value = CycleCancellation(preview(), remote(), notification(), NOW)

    store.save_remote_receipt(value.remote_receipt)
    store.save_workflow_receipt(value.preview)
    store.save_notification_receipt(value.notification_receipt)
    store.save_cancellation(value)
    store.save_cancellation(value)

    assert store.load_remote_receipt() == value.remote_receipt
    assert store.load_workflow_receipt(value.preview) is not None
    assert store.load_notification_receipt() == value.notification_receipt
    assert store.load_cancellation() == value
    assert (store.root / "cancellation.json").stat().st_mode & 0o777 == 0o600
    with pytest.raises(PolicyViolationError, match="conflicts"):
        store.save_cancellation(replace(value, canceled_at=NOW.replace(minute=1)))


def test_cancellation_coordinator_converges_all_boundaries(tmp_path: Path) -> None:
    class Intake:
        calls = 0

        def cancel(
            self, item_id: str, cycle_id: str, reason_digest: str
        ) -> IntakeCancellationReceipt:
            self.calls += 1
            assert (item_id, cycle_id, reason_digest) == (
                "42",
                CYCLE,
                preview().reason_digest,
            )
            return remote()

    class Workflow:
        calls = 0

        def cancel(self, workflow_id: str, reason: str) -> SimpleNamespace:
            self.calls += 1
            assert (workflow_id, reason) == (CYCLE, REASON)
            return SimpleNamespace(
                workflow_id=CYCLE,
                worktree_owned=False,
                worktree_path=None,
            )

    class Notifications:
        calls = 0

        def deliver(self, payload: dict[str, object]) -> NotificationReceipt:
            self.calls += 1
            assert payload["event_id"] == f"{CYCLE}:cancelled"
            return notification()

    intake = Intake()
    workflow = Workflow()
    notifications = Notifications()
    subject = CancellationCoordinator(
        store=CancellationArtifactStore(tmp_path, PROJECT, CYCLE),
        intake_adapter=intake,  # type: ignore[arg-type]
        notification_adapter=notifications,
        workflow=workflow,  # type: ignore[arg-type]
        clock=lambda: NOW,
    )
    registration = SimpleNamespace(
        notification_adapter="hermes-gateway",
        notification_target="attended-daidala",
    )

    first = subject.cancel(preview(), registration)  # type: ignore[arg-type]
    second = subject.cancel(preview(), registration)  # type: ignore[arg-type]

    assert first == second
    assert intake.calls == notifications.calls == 1
    assert workflow.calls == 1
    assert (
        tmp_path
        / "projects"
        / PROJECT
        / "cycles"
        / CYCLE
        / "cancellation-workflow.json"
    ).is_file()


def test_cancellation_retry_does_not_repeat_remote_or_workflow_mutation(
    tmp_path: Path,
) -> None:
    class Intake:
        calls = 0

        def cancel(
            self, item_id: str, cycle_id: str, reason_digest: str
        ) -> IntakeCancellationReceipt:
            self.calls += 1
            return remote()

    class Workflow:
        calls = 0

        def cancel(self, workflow_id: str, reason: str) -> SimpleNamespace:
            self.calls += 1
            return SimpleNamespace(
                workflow_id=CYCLE,
                worktree_owned=False,
                worktree_path=None,
            )

    class Notifications:
        calls = 0

        def deliver(self, payload: dict[str, object]) -> NotificationReceipt:
            self.calls += 1
            if self.calls == 1:
                raise PolicyViolationError("notification unavailable")
            return notification()

    intake = Intake()
    workflow = Workflow()
    notifications = Notifications()
    subject = CancellationCoordinator(
        store=CancellationArtifactStore(tmp_path, PROJECT, CYCLE),
        intake_adapter=intake,  # type: ignore[arg-type]
        notification_adapter=notifications,
        workflow=workflow,  # type: ignore[arg-type]
        clock=lambda: NOW,
    )
    registration = SimpleNamespace(
        notification_adapter="hermes-gateway",
        notification_target="attended-daidala",
    )

    with pytest.raises(PolicyViolationError, match="notification unavailable"):
        subject.cancel(preview(), registration)  # type: ignore[arg-type]
    result = subject.cancel(preview(), registration)  # type: ignore[arg-type]

    assert result.preview == preview()
    assert intake.calls == workflow.calls == 1
    assert notifications.calls == 2


def test_valid_matching_cancellation_releases_admission_ownership(
    tmp_path: Path,
) -> None:
    cycles_root = tmp_path / "projects" / PROJECT / "cycles"
    cycle_root = cycles_root / CYCLE
    cycle_root.mkdir(parents=True)
    admission = cycle_root / "admission.json"
    admission.write_text("{}", encoding="utf-8")

    assert active_admission_paths(cycles_root) == (admission,)

    matching_preview = replace(
        preview(), admission_digest=hashlib.sha256(admission.read_bytes()).hexdigest()
    )
    value = CycleCancellation(matching_preview, remote(), notification(), NOW)
    CancellationArtifactStore(tmp_path, PROJECT, CYCLE).save_cancellation(value)

    assert active_admission_paths(cycles_root) == ()

    (cycle_root / "completion.json").write_text("{}", encoding="utf-8")
    with pytest.raises(PolicyViolationError, match="multiple terminal"):
        active_admission_paths(cycles_root)
