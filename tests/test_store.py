from __future__ import annotations

import sqlite3
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from wingstaff.state import (
    DeliveryMode,
    WorkflowStage,
    WorkflowState,
    WorkflowStatus,
)
from wingstaff.store import StoreError, WorkflowStore
from wingstaff.workflow import (
    approve_plan,
    new_workflow,
    record_artifact,
    record_verification,
    start_implementation,
    validate_target,
)

NOW = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)
TARGET = "/tmp/wingstaff-store-target"
WORKTREE = "/tmp/wingstaff-store-worktrees/workflow-1"


def make_draft() -> WorkflowState:
    return new_workflow(
        workflow_id="workflow-1",
        target_repository=TARGET,
        requested_goal="Fix the failing test",
        pack_name="addyosmani",
        pack_source_revision="abcdef",
        created_at=NOW,
    )


def make_awaiting_approval() -> WorkflowState:
    state = validate_target(
        make_draft(),
        target_is_clean=True,
        baseline_commit="deadbeef",
        validated_at=NOW + timedelta(minutes=1),
    )
    state = record_artifact(
        state,
        stage=WorkflowStage.DEFINE,
        path="artifacts/define.md",
        digest="define-v1",
        recorded_at=NOW + timedelta(minutes=2),
    )
    return record_artifact(
        state,
        stage=WorkflowStage.PLAN,
        path="artifacts/plan.md",
        digest="plan-v1",
        recorded_at=NOW + timedelta(minutes=3),
    )


@pytest.fixture
def data_root(tmp_path: Path) -> Path:
    root = tmp_path / "wingstaff-data"
    root.mkdir()
    return root


def test_store_directory_is_created_and_db_file_lives_under_it(tmp_path: Path) -> None:
    nested = tmp_path / "missing" / "deeper"
    store = WorkflowStore(nested)

    assert nested.is_dir()
    assert store.db_path == nested / "workflows.sqlite3"
    assert store.db_path.is_file()


def test_create_get_update_round_trip_preserves_state(data_root: Path) -> None:
    store = WorkflowStore(data_root)
    state = make_draft()
    store.create(state)

    fetched = store.get("workflow-1")
    assert fetched == state
    assert store.list_active() == (state,)

    approved = approve_plan(
        make_awaiting_approval(),
        plan_digest="plan-v1",
        decided_at=NOW + timedelta(minutes=4),
    )
    store.update(approved)

    refreshed = store.get("workflow-1")
    assert refreshed.status is WorkflowStatus.APPROVED
    assert refreshed.approval is not None
    assert refreshed.approval.plan_digest == "plan-v1"
    assert refreshed.created_at == NOW


def test_create_rejects_duplicate_workflow_id(data_root: Path) -> None:
    store = WorkflowStore(data_root)
    store.create(make_draft())

    with pytest.raises(StoreError, match="already exists"):
        store.create(make_draft())


def test_update_unknown_workflow_is_an_error(data_root: Path) -> None:
    store = WorkflowStore(data_root)

    with pytest.raises(StoreError, match="unknown workflow"):
        store.update(make_draft())


def test_get_unknown_workflow_is_an_error(data_root: Path) -> None:
    store = WorkflowStore(data_root)

    with pytest.raises(StoreError, match="unknown workflow"):
        store.get("missing")


def test_upsert_inserts_when_missing_and_preserves_created_at(data_root: Path) -> None:
    store = WorkflowStore(data_root)
    store.upsert(make_draft())

    later = make_awaiting_approval()
    store.upsert(later)

    fetched = store.get("workflow-1")
    assert fetched == later
    assert fetched.created_at == NOW


def test_restart_recovers_state_from_existing_db(tmp_path: Path) -> None:
    root = tmp_path / "wingstaff-data"

    first = WorkflowStore(root)
    completed = make_awaiting_approval()
    completed = approve_plan(
        completed,
        plan_digest="plan-v1",
        decided_at=NOW + timedelta(minutes=4),
    )
    completed = start_implementation(
        completed,
        worktree_path=WORKTREE,
        started_at=NOW + timedelta(minutes=4),
    )
    completed = record_artifact(
        completed,
        stage=WorkflowStage.IMPLEMENT,
        path="artifacts/implementation.diff",
        digest="diff-v1",
        recorded_at=NOW + timedelta(minutes=5),
    )
    completed = record_verification(
        completed,
        command="pytest",
        exit_code=0,
        output_reference="artifacts/pytest.txt",
        recorded_at=NOW + timedelta(minutes=6),
    )
    first.create(completed)

    second = WorkflowStore(root)
    recovered = second.get("workflow-1")

    assert recovered.status is WorkflowStatus.RUNNING
    assert recovered.current_stage is WorkflowStage.REVIEW
    assert recovered.target_is_clean is True
    assert recovered.baseline_commit == "deadbeef"
    assert recovered.worktree_path == WORKTREE
    assert recovered.delivery_mode is DeliveryMode.REVIEWED_DIFF_ONLY
    assert recovered.verification_evidence[0].exit_code == 0


def test_concurrent_duplicate_transitions_only_persist_once(
    data_root: Path, tmp_path: Path
) -> None:
    store = WorkflowStore(data_root)
    initial = make_awaiting_approval()
    store.create(initial)

    # Two processes observe the same workflow at the same updated_at. The
    # first one wins the update; the second is rejected because its
    # ``expected_updated_at`` no longer matches the stored value. The
    # approving digest is the same on both sides — that is the race this
    # guard exists to prevent.
    a = WorkflowStore(data_root)
    b = WorkflowStore(data_root)
    observed_a = a.get_with_token("workflow-1")
    observed_b = b.get_with_token("workflow-1")
    assert observed_a.updated_at == observed_b.updated_at

    approved_a = approve_plan(
        observed_a.state,
        plan_digest="plan-v1",
        decided_at=NOW + timedelta(minutes=4),
    )
    a.update(approved_a, expected_updated_at=observed_a.updated_at)

    approved_b = approve_plan(
        observed_b.state,
        plan_digest="plan-v1",
        decided_at=NOW + timedelta(minutes=5),
    )
    with pytest.raises(StoreError, match="modified concurrently"):
        b.update(approved_b, expected_updated_at=observed_b.updated_at)

    a_state = a.get("workflow-1")
    assert a_state.status is WorkflowStatus.APPROVED
    assert a_state.approval is not None
    assert a_state.approval.plan_digest == "plan-v1"


def test_schema_migration_from_empty_db_creates_required_tables(
    data_root: Path,
) -> None:
    WorkflowStore(data_root)

    with sqlite3.connect(data_root / "workflows.sqlite3") as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert {"schema_meta", "workflows"}.issubset(tables)


def test_corrupt_state_row_raises_store_error(data_root: Path) -> None:
    store = WorkflowStore(data_root)
    with sqlite3.connect(store.db_path) as connection:
        connection.execute(
            """
            INSERT INTO workflows(
                workflow_id, status, pack_name, created_at, updated_at, state_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "workflow-bad",
                WorkflowStatus.DRAFT.value,
                "addyosmani",
                NOW.isoformat(),
                NOW.isoformat(),
                "not-json",
            ),
        )

    with pytest.raises(StoreError, match="not valid JSON"):
        store.get("workflow-bad")


def test_data_root_resolution_prefers_explicit_argument(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from wingstaff import locations

    sentinel = tmp_path / "explicit"
    monkeypatch.setenv(locations.ENV_OVERRIDE, str(tmp_path / "from-env"))

    assert locations.resolve_data_root(explicit=sentinel) == sentinel.resolve()


def test_data_root_resolution_prefers_hermes_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from wingstaff import locations

    monkeypatch.setenv(locations.ENV_OVERRIDE, "/tmp/hermes-profile-home")

    root = locations.resolve_data_root()
    assert root == Path("/tmp/hermes-profile-home").resolve()


def test_data_root_resolution_uses_context_data_dir(tmp_path: Path) -> None:
    from wingstaff import locations

    class _Context:
        data_dir = tmp_path / "from-context"

    assert locations.resolve_data_root(context=_Context()) == (tmp_path / "from-context").resolve()


def test_data_root_resolution_refuses_to_guess(monkeypatch: pytest.MonkeyPatch) -> None:
    from wingstaff import locations

    monkeypatch.delenv(locations.ENV_OVERRIDE, raising=False)

    import sys
    monkeypatch.setitem(sys.modules, "hermes_cli.config", None)
    monkeypatch.setitem(sys.modules, "hermes_cli", None)

    with pytest.raises(locations.DataRootError, match="HERMES_HOME"):
        locations.resolve_data_root()


def test_concurrent_workers_dont_corrupt_store(data_root: Path) -> None:
    store = WorkflowStore(data_root)
    states = tuple(
        new_workflow(
            workflow_id=f"workflow-{index}",
            target_repository=TARGET,
            requested_goal="goal",
            pack_name="addyosmani",
            pack_source_revision="rev",
            created_at=NOW,
        )
        for index in range(8)
    )

    errors: list[Exception] = []

    def worker(state: WorkflowState) -> None:
        try:
            store.create(state)
        except Exception as error:  # noqa: BLE001 - test thread boundary
            errors.append(error)

    threads = [threading.Thread(target=worker, args=(state,)) for state in states]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert {state.workflow_id for state in store.list_active()} == {
        state.workflow_id for state in states
    }
