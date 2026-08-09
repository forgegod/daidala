"""Dry-run-first initialization for the profile-local policy ledger."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from .store import WorkflowStore

_INITIALIZATION_LOCK = Lock()


class InitializationError(RuntimeError):
    """Raised when a confirmed initialization preview is stale or invalid."""


@dataclass(frozen=True)
class InitializationPreview:
    """A non-mutating observation of one profile-local ledger target."""

    data_root: Path
    database: Path
    initialized: bool
    digest: str

    @property
    def effects(self) -> tuple[str, ...]:
        if self.initialized:
            return ("No change: the policy-ledger schema already exists.",)
        return (
            "Create the profile-local Daidala directory.",
            "Create the policy-ledger SQLite schema.",
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "data_root": str(self.data_root),
            "database": str(self.database),
            "initialized": self.initialized,
            "effects": list(self.effects),
            "preview_digest": self.digest,
        }


def preview_initialization(data_root: Path) -> InitializationPreview:
    """Observe the policy-ledger target without creating files or directories."""

    root = Path(data_root).expanduser().resolve() / "daidala"
    database = root / "policy-ledger.sqlite3"
    initialized = database.is_file()
    identity = json.dumps(
        {
            "database": str(database),
            "data_root": str(root),
            "initialized": initialized,
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    return InitializationPreview(
        data_root=root,
        database=database,
        initialized=initialized,
        digest=hashlib.sha256(identity.encode("utf-8")).hexdigest(),
    )


def apply_initialization(
    data_root: Path,
    *,
    preview_digest: str,
    confirm: bool,
) -> tuple[InitializationPreview, bool]:
    """Apply one fresh, literally confirmed preview; return ``(preview, created)``."""

    if confirm is not True:
        raise InitializationError("initialization requires confirm: true")
    if not isinstance(preview_digest, str) or len(preview_digest) != 64:
        raise InitializationError("initialization preview digest is invalid")
    with _INITIALIZATION_LOCK:
        preview = preview_initialization(data_root)
        if preview.digest != preview_digest:
            raise InitializationError("initialization preview is stale")
        if preview.initialized:
            return preview, False
        WorkflowStore(preview.data_root)
        return preview_initialization(data_root), True
