from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from daidala.initialization import (
    InitializationError,
    apply_initialization,
    preview_initialization,
)


def test_preview_does_not_create_a_profile_ledger(tmp_path: Path) -> None:
    preview = preview_initialization(tmp_path)

    assert preview.initialized is False
    assert not (tmp_path / "daidala").exists()
    assert len(preview.digest) == 64


def test_confirmed_fresh_apply_creates_once_then_is_a_noop(tmp_path: Path) -> None:
    preview = preview_initialization(tmp_path)

    applied, created = apply_initialization(
        tmp_path, preview_digest=preview.digest, confirm=True
    )
    repeated, repeated_created = apply_initialization(
        tmp_path, preview_digest=applied.digest, confirm=True
    )

    assert created is True
    assert repeated_created is False
    assert applied.initialized is repeated.initialized is True
    assert applied.database.is_file()


def test_apply_rejects_a_stale_preview_without_creating_files(tmp_path: Path) -> None:
    with pytest.raises(InitializationError, match="stale"):
        apply_initialization(tmp_path, preview_digest="0" * 64, confirm=True)

    assert not (tmp_path / "daidala").exists()


def test_apply_requires_literal_confirmation(tmp_path: Path) -> None:
    preview = preview_initialization(tmp_path)

    with pytest.raises(InitializationError, match="confirm"):
        apply_initialization(tmp_path, preview_digest=preview.digest, confirm=False)

    assert not (tmp_path / "daidala").exists()


def test_concurrent_confirmed_apply_creates_one_schema(tmp_path: Path) -> None:
    preview = preview_initialization(tmp_path)

    def apply_once(_: int) -> bool | str:
        try:
            return apply_initialization(
                tmp_path, preview_digest=preview.digest, confirm=True
            )[1]
        except InitializationError:
            return "stale"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(apply_once, range(2)))

    assert sorted(results, key=str) == [True, "stale"]
    assert (tmp_path / "daidala" / "policy-ledger.sqlite3").is_file()
