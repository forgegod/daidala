from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from daidala.adapters import IntakeCompletionReceipt, NotificationReceipt
from daidala.completion import (
    CompletionArtifactStore,
    CompletionCoordinator,
    CycleCompletion,
    CycleCompletionPreview,
)
from daidala.errors import PolicyViolationError
from daidala.prerequisites import _active_admission_paths

NOW = datetime(2026, 7, 20, 10, 0, tzinfo=UTC)
CYCLE = "cycle-" + "a" * 64


def preview() -> CycleCompletionPreview:
    return CycleCompletionPreview(
        cycle_id=CYCLE,
        workflow_id=CYCLE,
        intake_item_id="42",
        admission_digest="1" * 64,
        plan_revision=1,
        plan_digest="2" * 64,
        review_digest="3" * 64,
        delivery_digest="4" * 64,
        verification_digests=("5" * 64,),
    )


def remote() -> IntakeCompletionReceipt:
    return IntakeCompletionReceipt(
        adapter="github-issues",
        item_id="42",
        cycle_id=CYCLE,
        source_url="https://github.com/forgegod/daidala/issues/42",
        state="closed",
        state_reason="completed",
        claim_released=True,
        completed_at=NOW,
    )


def notification() -> NotificationReceipt:
    return NotificationReceipt(
        event_id=f"{CYCLE}:completed",
        adapter="hermes-gateway",
        target_alias="attended-daidala",
        receipt_id="receipt-complete",
        delivered_at=NOW,
    )


def test_completion_records_round_trip_and_reject_identity_drift() -> None:
    value = CycleCompletion(preview(), remote(), notification(), NOW)

    assert CycleCompletionPreview.from_dict(value.preview.to_dict()) == value.preview
    assert CycleCompletion.from_dict(value.to_dict()) == value
    assert len(value.preview.digest) == len(value.digest) == 64
    with pytest.raises(PolicyViolationError, match="workflow ID"):
        replace(value.preview, workflow_id="another-cycle")
    with pytest.raises(PolicyViolationError, match="intake item"):
        replace(value, remote_receipt=replace(remote(), item_id="43"))
    raw = value.to_dict()
    raw["unknown"] = True
    with pytest.raises(PolicyViolationError, match="fields mismatch"):
        CycleCompletion.from_dict(raw)


def test_completion_preview_accepts_initial_plan_revision() -> None:
    initial = replace(preview(), plan_revision=0)

    assert CycleCompletionPreview.from_dict(initial.to_dict()) == initial
    for invalid in (-1, True):
        with pytest.raises(PolicyViolationError, match="non-negative integer"):
            replace(preview(), plan_revision=invalid)


def test_completion_store_is_immutable_and_preserves_admission(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    cycle_root = root / "projects" / "forgegod-daidala" / "cycles" / CYCLE
    cycle_root.mkdir(parents=True)
    admission = cycle_root / "admission.json"
    admission.write_text("{}", encoding="utf-8")
    store = CompletionArtifactStore(root)
    value = CycleCompletion(preview(), remote(), notification(), NOW)

    store.save_remote_receipt(value.preview, value.remote_receipt)
    store.save_completion(value)
    store.save_remote_receipt(value.preview, value.remote_receipt)
    store.save_completion(value)

    assert store.load_remote_receipt(value.preview) == value.remote_receipt
    assert store.load_completion(value.preview) == value
    assert (cycle_root / "completion.json").stat().st_mode & 0o777 == 0o600
    assert admission.read_text(encoding="utf-8") == "{}"
    with pytest.raises(PolicyViolationError, match="conflicts"):
        store.save_completion(replace(value, completed_at=NOW.replace(minute=1)))


def test_completion_coordinator_converges_remote_notification_and_record(
    tmp_path: Path,
) -> None:
    root = tmp_path.resolve()
    cycle_root = root / "projects" / "forgegod-daidala" / "cycles" / CYCLE
    cycle_root.mkdir(parents=True)
    (cycle_root / "admission.json").write_text("{}", encoding="utf-8")

    class Intake:
        calls = 0

        def complete(self, item_id: str, cycle_id: str) -> IntakeCompletionReceipt:
            self.calls += 1
            assert (item_id, cycle_id) == ("42", CYCLE)
            return remote()

    class Notifications:
        calls = 0

        def deliver(self, payload: dict[str, object]) -> NotificationReceipt:
            self.calls += 1
            assert payload["event_id"] == f"{CYCLE}:completed"
            return notification()

    intake = Intake()
    notifications = Notifications()
    subject = CompletionCoordinator(
        store=CompletionArtifactStore(root),
        intake_adapter=intake,  # type: ignore[arg-type]
        notification_adapter=notifications,
        clock=lambda: NOW,
    )
    registration = SimpleNamespace(
        notification_adapter="hermes-gateway",
        notification_target="attended-daidala",
    )

    first = subject.complete(preview(), registration)  # type: ignore[arg-type]
    second = subject.complete(preview(), registration)  # type: ignore[arg-type]

    assert first == second
    assert intake.calls == notifications.calls == 1
    assert (cycle_root / "completion-remote.json").is_file()
    assert (cycle_root / "completion-notification.json").is_file()
    assert (cycle_root / "completion.json").is_file()


def test_only_valid_matching_completion_releases_admission_ownership(
    tmp_path: Path,
) -> None:
    root = tmp_path.resolve()
    cycles_root = root / "projects" / "forgegod-daidala" / "cycles"
    cycle_root = cycles_root / CYCLE
    cycle_root.mkdir(parents=True)
    admission = cycle_root / "admission.json"
    admission.write_text("{}", encoding="utf-8")

    assert _active_admission_paths(cycles_root) == (admission,)

    matching_preview = replace(
        preview(), admission_digest=hashlib.sha256(admission.read_bytes()).hexdigest()
    )
    completion = CycleCompletion(
        matching_preview,
        remote(),
        notification(),
        NOW,
    )
    CompletionArtifactStore(root).save_completion(completion)

    assert _active_admission_paths(cycles_root) == ()

    raw = (cycle_root / "completion.json").read_text(encoding="utf-8")
    (cycle_root / "completion.json").write_text(raw + "x", encoding="utf-8")
    with pytest.raises(PolicyViolationError, match="cannot release"):
        _active_admission_paths(cycles_root)
