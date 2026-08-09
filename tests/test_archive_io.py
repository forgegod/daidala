from __future__ import annotations

import errno
import hashlib
import io
import json
import os
import stat
import tarfile
from pathlib import Path

import pytest

from daidala import archive_io
from daidala.archive_io import (
    ArchiveError,
    ArchiveLimits,
    create_archive,
    inventory_archive,
    read_archive_member,
    restore_archive,
    verify_archive,
)


def archive_paths(tmp_path: Path) -> tuple[Path, Path]:
    output = tmp_path / "archives"
    return output / "evidence.tar.gz", output / "evidence.manifest.json"


def make_source(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    (source / "binary.bin").write_bytes(b"\x00\xff\x00payload\n")
    nested = source / "nested"
    nested.mkdir()
    (nested / "notes.txt").write_text("verified\n", encoding="utf-8")
    return source


def source_members() -> tuple[str, ...]:
    return ("nested/notes.txt", "binary.bin")


def test_archive_round_trip_is_deterministic_verified_and_mode_safe(tmp_path: Path) -> None:
    source = make_source(tmp_path)
    archive, manifest = archive_paths(tmp_path)

    first = create_archive(source, source_members(), archive, manifest)
    again = create_archive(source, tuple(reversed(source_members())), archive, manifest)

    assert again == first
    assert first.manifest.archive_sha256 == hashlib.sha256(archive.read_bytes()).hexdigest()
    assert [member.path for member in first.manifest.members] == ["binary.bin", "nested/notes.txt"]
    assert archive.stat().st_mode & 0o777 == 0o600
    assert manifest.stat().st_mode & 0o777 == 0o600
    assert archive.parent.stat().st_mode & 0o777 == 0o700
    assert inventory_archive(archive, manifest) == first.manifest
    assert verify_archive(archive, manifest) == first.manifest

    restored = tmp_path / "restored"
    assert restore_archive(archive, manifest, restored) == first.manifest
    assert (restored / "binary.bin").read_bytes() == (source / "binary.bin").read_bytes()
    assert (restored / "nested" / "notes.txt").read_bytes() == (
        source / "nested" / "notes.txt"
    ).read_bytes()
    assert (restored / "binary.bin").stat().st_mode & 0o777 == 0o600
    assert (restored / "nested").stat().st_mode & 0o777 == 0o700


def test_read_archive_member_revalidates_integrity_mode_and_bounds(tmp_path: Path) -> None:
    source = make_source(tmp_path)
    archive, manifest = archive_paths(tmp_path)
    create_archive(source, source_members(), archive, manifest)

    assert read_archive_member(
        archive, manifest, "nested/notes.txt", max_bytes=64
    ) == b"verified\n"
    with pytest.raises(ArchiveError, match="bounds"):
        read_archive_member(archive, manifest, "nested/notes.txt", max_bytes=4)

    archive.chmod(0o644)
    with pytest.raises(ArchiveError, match="unsafe-member"):
        read_archive_member(archive, manifest, "nested/notes.txt", max_bytes=64)


def test_archive_rejects_unsafe_or_duplicate_member_names_without_leaking_them(
    tmp_path: Path,
) -> None:
    source = make_source(tmp_path)
    archive, manifest = archive_paths(tmp_path)

    candidates = (
        ("/absolute",),
        ("../escape",),
        ("nested/../notes.txt",),
        ("binary.bin", "binary.bin"),
    )
    for members in candidates:
        with pytest.raises(ArchiveError, match="unsafe-member|invalid-input") as raised:
            create_archive(source, members, archive, manifest)
        assert str(raised.value).startswith("archive create:")
        assert "binary.bin" not in str(raised.value)
        assert "escape" not in str(raised.value)


def test_archive_rejects_symlink_hard_link_and_special_file_sources(tmp_path: Path) -> None:
    source = make_source(tmp_path)
    archive, manifest = archive_paths(tmp_path)

    (source / "link").symlink_to("binary.bin")
    with pytest.raises(ArchiveError, match="unsafe-member"):
        create_archive(source, ("link",), archive, manifest)

    os.link(source / "binary.bin", source / "hard-link.bin")
    with pytest.raises(ArchiveError, match="unsafe-member"):
        create_archive(source, ("hard-link.bin",), archive, manifest)

    fifo = source / "pipe"
    os.mkfifo(fifo)
    try:
        with pytest.raises(ArchiveError, match="unsafe-member"):
            create_archive(source, ("pipe",), archive, manifest)
    finally:
        fifo.unlink()


def test_archive_enforces_member_and_size_bounds(tmp_path: Path) -> None:
    source = make_source(tmp_path)
    archive, manifest = archive_paths(tmp_path)

    with pytest.raises(ArchiveError, match="bounds"):
        create_archive(
            source,
            source_members(),
            archive,
            manifest,
            limits=ArchiveLimits(
                max_files=1,
                max_file_bytes=64,
                max_total_bytes=128,
                max_archive_bytes=512,
            ),
        )
    with pytest.raises(ArchiveError, match="bounds"):
        create_archive(
            source,
            ("binary.bin",),
            archive,
            manifest,
            limits=ArchiveLimits(
                max_files=2,
                max_file_bytes=4,
                max_total_bytes=128,
                max_archive_bytes=512,
            ),
        )
    with pytest.raises(ArchiveError, match="bounds"):
        create_archive(
            source,
            source_members(),
            archive,
            manifest,
            limits=ArchiveLimits(
                max_files=2,
                max_file_bytes=64,
                max_total_bytes=10,
                max_archive_bytes=512,
            ),
        )
    with pytest.raises(ArchiveError, match="bounds"):
        create_archive(
            source,
            source_members(),
            archive,
            manifest,
            limits=ArchiveLimits(
                max_files=2,
                max_file_bytes=64,
                max_total_bytes=128,
                max_archive_bytes=32,
            ),
        )


def test_archive_rejects_tampering_and_conflicting_retries(tmp_path: Path) -> None:
    source = make_source(tmp_path)
    archive, manifest = archive_paths(tmp_path)
    result = create_archive(source, source_members(), archive, manifest)

    (source / "binary.bin").write_bytes(b"changed")
    with pytest.raises(ArchiveError, match="conflict"):
        create_archive(source, source_members(), archive, manifest)

    archive.write_bytes(b"tampered")
    with pytest.raises(ArchiveError, match="integrity"):
        verify_archive(archive, manifest)

    restored = tmp_path / "restored"
    archive.write_bytes(b"tampered")
    assert result.manifest.archive_sha256 != hashlib.sha256(archive.read_bytes()).hexdigest()
    with pytest.raises(ArchiveError, match="integrity"):
        restore_archive(archive, manifest, restored)


def test_restore_is_idempotent_and_rejects_conflicting_output(tmp_path: Path) -> None:
    source = make_source(tmp_path)
    archive, manifest = archive_paths(tmp_path)
    create_archive(source, source_members(), archive, manifest)
    restored = tmp_path / "restored"

    restore_archive(archive, manifest, restored)
    restore_archive(archive, manifest, restored)
    (restored / "binary.bin").write_bytes(b"conflict")
    with pytest.raises(ArchiveError, match="conflict"):
        restore_archive(archive, manifest, restored)


@pytest.mark.parametrize("error_number", (errno.ENOSPC, errno.EACCES))
def test_archive_cleans_partial_output_when_fsync_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error_number: int,
) -> None:
    source = make_source(tmp_path)
    archive, manifest = archive_paths(tmp_path)

    def fail_fsync(_: int) -> None:
        raise OSError(error_number, "simulated write failure")

    monkeypatch.setattr(archive_io, "_fsync_file", fail_fsync)
    with pytest.raises(ArchiveError, match="io"):
        create_archive(source, source_members(), archive, manifest)

    assert not archive.exists()
    assert not manifest.exists()
    assert not list(archive.parent.glob(".daidala-archive-*"))
    assert (source / "binary.bin").read_bytes() == b"\x00\xff\x00payload\n"


def test_verify_rejects_link_and_traversal_members_before_restore(tmp_path: Path) -> None:
    archive, manifest = archive_paths(tmp_path)
    archive.parent.mkdir(mode=0o700)
    payload = b"not a regular file"
    info = tarfile.TarInfo("safe.txt")
    info.type = tarfile.SYMTYPE
    info.linkname = "target"
    info.size = 0
    with tarfile.open(archive, "w:gz") as handle:
        handle.addfile(info)
    _write_manifest(
        archive,
        manifest,
        [{"path": "safe.txt", "size": 0, "sha256": hashlib.sha256(b"").hexdigest()}],
    )
    with pytest.raises(ArchiveError, match="unsafe-member"):
        verify_archive(archive, manifest)

    with tarfile.open(archive, "w:gz") as handle:
        traversal = tarfile.TarInfo("../escape")
        traversal.size = len(payload)
        handle.addfile(traversal, io.BytesIO(payload))
    _write_manifest(
        archive,
        manifest,
        [
            {
                "path": "../escape",
                "size": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        ],
    )
    with pytest.raises(ArchiveError, match="unsafe-member"):
        restore_archive(archive, manifest, tmp_path / "restored")


def _write_manifest(archive: Path, manifest: Path, members: list[dict[str, object]]) -> None:
    payload = {
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "archive_size": archive.stat().st_size,
        "format": "daidala.archive/v1",
        "members": members,
    }
    content = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    manifest.write_text(content, encoding="utf-8")
    manifest.chmod(stat.S_IRUSR | stat.S_IWUSR)
