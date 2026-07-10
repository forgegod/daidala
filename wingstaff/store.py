"""Durable local persistence for Wingstaff workflows.

Workflows are stored as a single SQLite database inside the profile-aware data
root. The store owns its own transaction boundaries, treats the workflow
table as the source of truth, and refuses to substitute a guessed payload.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import WorkflowError
from .state import WorkflowState

SCHEMA_VERSION = 1
_DB_FILE = "workflows.sqlite3"


class StoreError(WorkflowError):
    """Raised when a persistence operation fails its contract."""


@dataclass(frozen=True)
class ObservedWorkflow:
    state: WorkflowState
    updated_at: str


def _coerce_updated_at(value: Any) -> str:
    return str(value)


class WorkflowStore:
    """Thin SQLite store keyed by ``workflow_id``."""

    def __init__(self, data_root: Path) -> None:
        self._data_root = Path(data_root)
        self._data_root.mkdir(parents=True, exist_ok=True)
        self._db_path = self._data_root / _DB_FILE
        self._init_schema()

    @property
    def data_root(self) -> Path:
        return self._data_root

    @property
    def db_path(self) -> Path:
        return self._db_path

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._db_path, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        finally:
            connection.close()

    def _init_schema(self) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN")
            try:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_meta (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    "INSERT OR IGNORE INTO schema_meta(key, value) VALUES (?, ?)",
                    ("schema_version", str(SCHEMA_VERSION)),
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS workflows (
                        workflow_id TEXT PRIMARY KEY,
                        status TEXT NOT NULL,
                        pack_name TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        state_json TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS workflows_status ON workflows(status)"
                )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise

    def create(self, state: WorkflowState) -> WorkflowState:
        """Insert a new workflow. Fails if the workflow_id already exists."""
        payload = json.dumps(state.to_dict(), ensure_ascii=False, sort_keys=True)
        with self._connect() as connection:
            connection.execute("BEGIN")
            try:
                connection.execute(
                    """
                    INSERT INTO workflows(
                        workflow_id, status, pack_name, created_at, updated_at, state_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        state.workflow_id,
                        state.status.value,
                        state.pack_name,
                        state.created_at.isoformat(),
                        state.updated_at.isoformat(),
                        payload,
                    ),
                )
                connection.execute("COMMIT")
            except sqlite3.IntegrityError as error:
                connection.execute("ROLLBACK")
                raise StoreError(
                    f"workflow {state.workflow_id!r} already exists"
                ) from error
            except Exception:
                connection.execute("ROLLBACK")
                raise
        return state

    def get(self, workflow_id: str) -> WorkflowState:
        """Return the stored workflow state for ``workflow_id``."""
        return self._load(workflow_id).state

    def get_with_token(self, workflow_id: str) -> ObservedWorkflow:
        """Return the stored workflow and an optimistic-concurrency token."""
        return self._load(workflow_id)

    def update(
        self, state: WorkflowState, *, expected_updated_at: str | None = None
    ) -> WorkflowState:
        """Replace the stored workflow with ``state``.

        When ``expected_updated_at`` is supplied it must match the stored
        ``updated_at``; otherwise the update is rejected with ``StoreError``.
        This guards the contract that two processes cannot apply concurrent
        transitions to the same workflow.
        """
        payload = json.dumps(state.to_dict(), ensure_ascii=False, sort_keys=True)
        with self._connect() as connection:
            connection.execute("BEGIN")
            try:
                if expected_updated_at is not None:
                    cursor = connection.execute(
                        """
                        UPDATE workflows
                        SET status = ?, pack_name = ?, updated_at = ?, state_json = ?
                        WHERE workflow_id = ? AND updated_at = ?
                        """,
                        (
                            state.status.value,
                            state.pack_name,
                            state.updated_at.isoformat(),
                            payload,
                            state.workflow_id,
                            expected_updated_at,
                        ),
                    )
                    if cursor.rowcount == 0:
                        connection.execute("ROLLBACK")
                        raise StoreError(
                            f"workflow {state.workflow_id!r} was modified concurrently"
                        )
                else:
                    cursor = connection.execute(
                        """
                        UPDATE workflows
                        SET status = ?, pack_name = ?, updated_at = ?, state_json = ?
                        WHERE workflow_id = ?
                        """,
                        (
                            state.status.value,
                            state.pack_name,
                            state.updated_at.isoformat(),
                            payload,
                            state.workflow_id,
                        ),
                    )
                    if cursor.rowcount == 0:
                        connection.execute("ROLLBACK")
                        raise StoreError(f"unknown workflow: {state.workflow_id!r}")
                connection.execute("COMMIT")
            except Exception:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise
        return state

    def list_active(self) -> tuple[WorkflowState, ...]:
        """Return all stored workflows ordered by created_at."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT state_json FROM workflows ORDER BY created_at ASC"
            ).fetchall()
        return tuple(_deserialize(row["state_json"]) for row in rows)

    def upsert(
        self,
        state: WorkflowState,
        *,
        expected_updated_at: str | None = None,
    ) -> WorkflowState:
        """Insert or update atomically, preserving the original created_at.

        ``expected_updated_at`` is forwarded to :meth:`update` and enforces
        optimistic concurrency when the workflow already exists.
        """
        existing = self._try_get_optional(state.workflow_id)
        if existing is None:
            return self.create(state)
        merged = state
        if existing.state.created_at != state.created_at:
            merged = _with_created_at(state, existing.state.created_at)
        return self.update(merged, expected_updated_at=expected_updated_at)

    def _load(self, workflow_id: str) -> ObservedWorkflow:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT state_json, updated_at FROM workflows WHERE workflow_id = ?",
                (workflow_id,),
            ).fetchone()
        if row is None:
            raise StoreError(f"unknown workflow: {workflow_id!r}")
        return ObservedWorkflow(
            state=_deserialize(row["state_json"]),
            updated_at=_coerce_updated_at(row["updated_at"]),
        )

    def _try_get_optional(self, workflow_id: str) -> ObservedWorkflow | None:
        try:
            return self._load(workflow_id)
        except StoreError:
            return None


def _deserialize(payload: str) -> WorkflowState:
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as error:
        raise StoreError(f"stored workflow is not valid JSON: {error}") from error
    return WorkflowState.from_dict(raw)


def _with_created_at(state: WorkflowState, created_at) -> WorkflowState:
    from dataclasses import replace

    return replace(state, created_at=created_at, updated_at=max(state.updated_at, created_at))
