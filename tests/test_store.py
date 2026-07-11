from __future__ import annotations

import sqlite3
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from wingstaff.state import SkillDigest, WorkflowLedger, WorkflowStage
from wingstaff.store import StoreError, WorkflowStore
from wingstaff.workflow import approve_plan, new_workflow, record_artifact

NOW = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)
TARGET = "/tmp/wingstaff-store-target"


def make_ledger(workflow_id: str = "workflow-1") -> WorkflowLedger:
    return new_workflow(
        workflow_id=workflow_id,
        board_slug="wingstaff-test",
        target_repository=TARGET,
        baseline_commit="deadbeef",
        requested_goal="Fix the failing test",
        pack_name="addyosmani",
        pack_source_revision="source@abcdef",
        skill_digests=(SkillDigest(name="interview-me", digest="digest-1"),),
        created_at=NOW,
    )


def make_planned() -> WorkflowLedger:
    ledger = record_artifact(
        make_ledger(),
        stage=WorkflowStage.DEFINE,
        path="artifacts/define.md",
        digest="define-v1",
        recorded_at=NOW + timedelta(minutes=1),
    )
    return record_artifact(
        ledger,
        stage=WorkflowStage.PLAN,
        path="artifacts/plan.md",
        digest="plan-v1",
        recorded_at=NOW + timedelta(minutes=2),
    )


@pytest.fixture
def data_root(tmp_path: Path) -> Path:
    return tmp_path / "wingstaff-data"


def test_store_creates_fresh_policy_ledger_schema(data_root: Path) -> None:
    store = WorkflowStore(data_root)

    assert store.db_path == data_root / "policy-ledger.sqlite3"
    with sqlite3.connect(store.db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(policy_ledgers)").fetchall()
        }

    assert tables == {"schema_meta", "policy_ledgers"}
    assert "status" not in columns
    assert "current_stage" not in columns
    assert not (data_root / "workflows.sqlite3").exists()


def test_create_get_update_and_list_round_trip(data_root: Path) -> None:
    store = WorkflowStore(data_root)
    ledger = make_ledger()
    store.create(ledger)

    assert store.get("workflow-1") == ledger
    assert store.list_all() == (ledger,)

    planned = make_planned()
    store.update(planned)
    assert store.get("workflow-1") == planned


def test_duplicate_unknown_and_corrupt_rows_fail_closed(data_root: Path) -> None:
    store = WorkflowStore(data_root)
    store.create(make_ledger())

    with pytest.raises(StoreError, match="already exists"):
        store.create(make_ledger())
    with pytest.raises(StoreError, match="unknown workflow"):
        store.get("missing")
    with pytest.raises(StoreError, match="unknown workflow"):
        store.update(make_ledger("missing"))

    with sqlite3.connect(store.db_path) as connection:
        connection.execute(
            """
            INSERT INTO policy_ledgers(
                workflow_id, board_slug, pack_name, created_at, updated_at, ledger_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "workflow-bad",
                "wingstaff-test",
                "addyosmani",
                NOW.isoformat(),
                NOW.isoformat(),
                "not-json",
            ),
        )
    with pytest.raises(StoreError, match="not valid JSON"):
        store.get("workflow-bad")


def test_restart_recovers_policy_facts_without_operational_status(data_root: Path) -> None:
    first = WorkflowStore(data_root)
    approved = approve_plan(
        make_planned(),
        plan_digest="plan-v1",
        decided_at=NOW + timedelta(minutes=3),
    )
    first.create(approved)

    recovered = WorkflowStore(data_root).get("workflow-1")

    assert recovered == approved
    assert recovered.approval is not None
    assert recovered.board_slug == "wingstaff-test"
    assert "status" not in recovered.to_dict()


def test_optimistic_concurrency_rejects_second_writer(data_root: Path) -> None:
    store = WorkflowStore(data_root)
    store.create(make_planned())
    a = WorkflowStore(data_root)
    b = WorkflowStore(data_root)
    observed_a = a.get_with_token("workflow-1")
    observed_b = b.get_with_token("workflow-1")

    approved_a = approve_plan(
        observed_a.ledger,
        plan_digest="plan-v1",
        decided_at=NOW + timedelta(minutes=3),
    )
    a.update(approved_a, expected_updated_at=observed_a.updated_at)

    approved_b = approve_plan(
        observed_b.ledger,
        plan_digest="plan-v1",
        decided_at=NOW + timedelta(minutes=4),
    )
    with pytest.raises(StoreError, match="modified concurrently"):
        b.update(approved_b, expected_updated_at=observed_b.updated_at)


def test_upsert_preserves_original_creation_time(data_root: Path) -> None:
    store = WorkflowStore(data_root)
    store.upsert(make_ledger())
    later = make_planned()
    store.upsert(later)

    assert store.get("workflow-1").created_at == NOW


def test_schema_version_mismatch_is_rejected(data_root: Path) -> None:
    data_root.mkdir(parents=True)
    database = data_root / "policy-ledger.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO schema_meta(key, value) VALUES ('schema_version', '99')"
        )

    with pytest.raises(StoreError, match="unsupported"):
        WorkflowStore(data_root)


def test_concurrent_creates_do_not_corrupt_store(data_root: Path) -> None:
    store = WorkflowStore(data_root)
    ledgers = tuple(make_ledger(f"workflow-{index}") for index in range(8))
    errors: list[Exception] = []

    def worker(ledger: WorkflowLedger) -> None:
        try:
            store.create(ledger)
        except Exception as error:  # noqa: BLE001 - test thread boundary
            errors.append(error)

    threads = [threading.Thread(target=worker, args=(ledger,)) for ledger in ledgers]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert {ledger.workflow_id for ledger in store.list_all()} == {
        ledger.workflow_id for ledger in ledgers
    }


def test_data_root_resolution_still_prefers_explicit_context_and_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from wingstaff import locations

    explicit = tmp_path / "explicit"
    monkeypatch.setenv(locations.ENV_OVERRIDE, str(tmp_path / "from-env"))
    assert locations.resolve_data_root(explicit=explicit) == explicit.resolve()

    class _Context:
        data_dir = tmp_path / "from-context"

    assert locations.resolve_data_root(context=_Context()) == (
        tmp_path / "from-context"
    ).resolve()