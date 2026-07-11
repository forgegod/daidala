"""Durable profile-local persistence for Wingstaff policy ledgers."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path

from .errors import WorkflowError
from .state import WorkflowLedger

SCHEMA_VERSION = 1
_DB_FILE = "policy-ledger.sqlite3"


class StoreError(WorkflowError):
    """Raised when a policy-ledger persistence operation fails."""


@dataclass(frozen=True)
class ObservedLedger:
    ledger: WorkflowLedger
    updated_at: str


class WorkflowStore:
    """Thin SQLite store keyed by ``workflow_id`` with optimistic updates."""

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
                version = connection.execute(
                    "SELECT value FROM schema_meta WHERE key = 'schema_version'"
                ).fetchone()
                if version is None or version["value"] != str(SCHEMA_VERSION):
                    raise StoreError("unsupported policy-ledger schema version")
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS policy_ledgers (
                        workflow_id TEXT PRIMARY KEY,
                        board_slug TEXT NOT NULL,
                        pack_name TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        ledger_json TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS policy_ledgers_board "
                    "ON policy_ledgers(board_slug, created_at)"
                )
                connection.execute("COMMIT")
            except Exception:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise

    def create(self, ledger: WorkflowLedger) -> WorkflowLedger:
        """Insert a fresh policy ledger."""
        payload = _serialize(ledger)
        with self._connect() as connection:
            connection.execute("BEGIN")
            try:
                connection.execute(
                    """
                    INSERT INTO policy_ledgers(
                        workflow_id, board_slug, pack_name,
                        created_at, updated_at, ledger_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ledger.workflow_id,
                        ledger.board_slug,
                        ledger.pack_name,
                        ledger.created_at.isoformat(),
                        ledger.updated_at.isoformat(),
                        payload,
                    ),
                )
                connection.execute("COMMIT")
            except sqlite3.IntegrityError as error:
                connection.execute("ROLLBACK")
                raise StoreError(
                    f"workflow {ledger.workflow_id!r} already exists"
                ) from error
            except Exception:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise
        return ledger

    def get(self, workflow_id: str) -> WorkflowLedger:
        """Return the policy ledger for ``workflow_id``."""
        return self._load(workflow_id).ledger

    def get_with_token(self, workflow_id: str) -> ObservedLedger:
        """Return the ledger with its optimistic-concurrency token."""
        return self._load(workflow_id)

    def update(
        self,
        ledger: WorkflowLedger,
        *,
        expected_updated_at: str | None = None,
    ) -> WorkflowLedger:
        """Replace a ledger, optionally requiring an observed update token."""
        payload = _serialize(ledger)
        with self._connect() as connection:
            connection.execute("BEGIN")
            try:
                if expected_updated_at is None:
                    cursor = connection.execute(
                        """
                        UPDATE policy_ledgers
                        SET board_slug = ?, pack_name = ?, updated_at = ?, ledger_json = ?
                        WHERE workflow_id = ?
                        """,
                        (
                            ledger.board_slug,
                            ledger.pack_name,
                            ledger.updated_at.isoformat(),
                            payload,
                            ledger.workflow_id,
                        ),
                    )
                    if cursor.rowcount == 0:
                        raise StoreError(f"unknown workflow: {ledger.workflow_id!r}")
                else:
                    cursor = connection.execute(
                        """
                        UPDATE policy_ledgers
                        SET board_slug = ?, pack_name = ?, updated_at = ?, ledger_json = ?
                        WHERE workflow_id = ? AND updated_at = ?
                        """,
                        (
                            ledger.board_slug,
                            ledger.pack_name,
                            ledger.updated_at.isoformat(),
                            payload,
                            ledger.workflow_id,
                            expected_updated_at,
                        ),
                    )
                    if cursor.rowcount == 0:
                        raise StoreError(
                            f"workflow {ledger.workflow_id!r} was modified concurrently"
                        )
                connection.execute("COMMIT")
            except Exception:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise
        return ledger

    def upsert(
        self,
        ledger: WorkflowLedger,
        *,
        expected_updated_at: str | None = None,
    ) -> WorkflowLedger:
        """Insert or update while preserving the original creation timestamp."""
        existing = self._try_get_optional(ledger.workflow_id)
        if existing is None:
            return self.create(ledger)
        merged = ledger
        if existing.ledger.created_at != ledger.created_at:
            merged = replace(
                ledger,
                created_at=existing.ledger.created_at,
                updated_at=max(ledger.updated_at, existing.ledger.created_at),
            )
        return self.update(merged, expected_updated_at=expected_updated_at)

    def list_all(self) -> tuple[WorkflowLedger, ...]:
        """Return every policy ledger ordered by creation time."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT ledger_json FROM policy_ledgers ORDER BY created_at ASC"
            ).fetchall()
        return tuple(_deserialize(row["ledger_json"]) for row in rows)

    def _load(self, workflow_id: str) -> ObservedLedger:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT ledger_json, updated_at FROM policy_ledgers WHERE workflow_id = ?",
                (workflow_id,),
            ).fetchone()
        if row is None:
            raise StoreError(f"unknown workflow: {workflow_id!r}")
        return ObservedLedger(
            ledger=_deserialize(row["ledger_json"]),
            updated_at=str(row["updated_at"]),
        )

    def _try_get_optional(self, workflow_id: str) -> ObservedLedger | None:
        try:
            return self._load(workflow_id)
        except StoreError:
            return None


def _serialize(ledger: WorkflowLedger) -> str:
    return json.dumps(ledger.to_dict(), ensure_ascii=False, sort_keys=True)


def _deserialize(payload: str) -> WorkflowLedger:
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as error:
        raise StoreError(f"stored workflow ledger is not valid JSON: {error}") from error
    return WorkflowLedger.from_dict(raw)