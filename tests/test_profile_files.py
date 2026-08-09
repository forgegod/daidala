from __future__ import annotations

import stat
from pathlib import Path

import pytest

from daidala.profile_files import ProfileFileError, atomic_write_private_text, read_private_text


def test_atomic_private_replacement_round_trips_with_mode_0600(tmp_path: Path) -> None:
    path = tmp_path / "state.yaml"

    atomic_write_private_text(path, "first\n", label="test state")
    atomic_write_private_text(path, "second\n", label="test state")

    assert read_private_text(path, maximum_bytes=100, label="test state") == "second\n"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert not list(tmp_path.glob(".daidala-*"))


def test_private_replacement_rejects_symlink_destination(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.write_text("protected\n", encoding="utf-8")
    path = tmp_path / "state.yaml"
    path.symlink_to(target)

    with pytest.raises(ProfileFileError, match="regular file"):
        atomic_write_private_text(path, "replacement\n", label="test state")

    assert target.read_text(encoding="utf-8") == "protected\n"
