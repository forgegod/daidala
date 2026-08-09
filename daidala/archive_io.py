"""Policy-neutral verified tar/gzip archive operations.

Callers authorize source and destination roots. This module validates only archive
members, byte limits, archive integrity, and safe filesystem mechanics.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import stat
import tarfile
import tempfile
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO, cast

from .errors import WorkflowError

_ARCHIVE_FORMAT = "daidala.archive/v1"
_MANIFEST_MAX_BYTES = 1024 * 1024
_SHA256_LENGTH = 64


class ArchiveError(WorkflowError):
    """Raised when archive input, integrity, or filesystem safety checks fail."""


@dataclass(frozen=True)
class ArchiveLimits:
    """Finite limits for one archive operation."""

    max_files: int = 1_024
    max_file_bytes: int = 64 * 1024 * 1024
    max_total_bytes: int = 256 * 1024 * 1024
    max_archive_bytes: int = 512 * 1024 * 1024

    def __post_init__(self) -> None:
        for value in (
            self.max_files,
            self.max_file_bytes,
            self.max_total_bytes,
            self.max_archive_bytes,
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ArchiveError("archive invalid-input")


_DEFAULT_LIMITS = ArchiveLimits()


@dataclass(frozen=True, order=True)
class ArchiveMember:
    """One verified regular-file member recorded in a manifest."""

    path: str
    size: int
    sha256: str

    def __post_init__(self) -> None:
        _safe_member_path(self.path)
        if isinstance(self.size, bool) or not isinstance(self.size, int) or self.size < 0:
            raise ArchiveError("archive invalid-input")
        _safe_sha256(self.sha256)

    def to_dict(self) -> dict[str, object]:
        return {"path": self.path, "sha256": self.sha256, "size": self.size}

    @classmethod
    def from_dict(cls, raw: object) -> ArchiveMember:
        if not isinstance(raw, dict) or set(raw) != {"path", "sha256", "size"}:
            raise ArchiveError("archive invalid-input")
        return cls(path=raw["path"], size=raw["size"], sha256=raw["sha256"])


@dataclass(frozen=True)
class ArchiveManifest:
    """Strict canonical manifest for one verified archive."""

    archive_sha256: str
    archive_size: int
    members: tuple[ArchiveMember, ...]
    format: str = _ARCHIVE_FORMAT

    def __post_init__(self) -> None:
        if self.format != _ARCHIVE_FORMAT:
            raise ArchiveError("archive invalid-input")
        _safe_sha256(self.archive_sha256)
        if isinstance(self.archive_size, bool) or not isinstance(self.archive_size, int):
            raise ArchiveError("archive invalid-input")
        if self.archive_size < 0 or not isinstance(self.members, tuple):
            raise ArchiveError("archive invalid-input")
        if any(not isinstance(member, ArchiveMember) for member in self.members):
            raise ArchiveError("archive invalid-input")
        paths = tuple(member.path for member in self.members)
        if tuple(sorted(paths)) != paths or len(set(paths)) != len(paths):
            raise ArchiveError("archive invalid-input")

    def to_dict(self) -> dict[str, object]:
        return {
            "archive_sha256": self.archive_sha256,
            "archive_size": self.archive_size,
            "format": self.format,
            "members": [member.to_dict() for member in self.members],
        }

    def canonical_bytes(self) -> bytes:
        encoded = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        return encoded + b"\n"

    @classmethod
    def from_bytes(cls, content: bytes) -> ArchiveManifest:
        if not isinstance(content, bytes) or not content or len(content) > _MANIFEST_MAX_BYTES:
            raise ArchiveError("archive invalid-input")
        try:
            raw = json.loads(content.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
        except (UnicodeDecodeError, json.JSONDecodeError, ArchiveError) as error:
            raise ArchiveError("archive invalid-input") from error
        if not isinstance(raw, dict) or set(raw) != {
            "archive_sha256",
            "archive_size",
            "format",
            "members",
        }:
            raise ArchiveError("archive invalid-input")
        members = raw["members"]
        if not isinstance(members, list):
            raise ArchiveError("archive invalid-input")
        return cls(
            archive_sha256=raw["archive_sha256"],
            archive_size=raw["archive_size"],
            format=raw["format"],
            members=tuple(ArchiveMember.from_dict(member) for member in members),
        )


@dataclass(frozen=True)
class ArchiveResult:
    """Published archive paths plus the canonical verified manifest."""

    archive_path: Path
    manifest_path: Path
    manifest: ArchiveManifest


def create_archive(
    source_root: Path,
    members: Iterable[str],
    archive_path: Path,
    manifest_path: Path,
    *,
    limits: ArchiveLimits = _DEFAULT_LIMITS,
) -> ArchiveResult:
    """Create and publish a deterministic verified tar/gzip archive.

    Member authorization, storage policy, and destination naming remain caller-owned.
    A retry returns existing output only when its manifest and bytes are identical.
    """
    try:
        root = _source_root(source_root)
        selected = _selected_members(members, limits)
        archive, manifest, output_directory = _output_paths(archive_path, manifest_path)
        temporary_archive: Path | None = None
        temporary_manifest: Path | None = None
        try:
            temporary_archive = _temporary_file(output_directory, ".daidala-archive-")
            recorded = _write_archive(root, selected, temporary_archive, limits)
            archive_digest, archive_size = _digest_file(temporary_archive, limits.max_archive_bytes)
            expected = ArchiveManifest(
                archive_sha256=archive_digest,
                archive_size=archive_size,
                members=recorded,
            )
            temporary_manifest = _temporary_file(output_directory, ".daidala-manifest-")
            _write_bytes(temporary_manifest, expected.canonical_bytes())
            _chmod(temporary_manifest, 0o600)
            _verify(temporary_archive, temporary_manifest, limits)
            result = _publish(
                temporary_archive,
                temporary_manifest,
                archive,
                manifest,
                expected,
                limits,
            )
            temporary_archive = None
            temporary_manifest = None
            return result
        finally:
            if temporary_archive is not None:
                temporary_archive.unlink(missing_ok=True)
            if temporary_manifest is not None:
                temporary_manifest.unlink(missing_ok=True)
    except ArchiveError as error:
        raise _operation_error("create", error) from error
    except (OSError, EOFError, tarfile.TarError) as error:
        raise ArchiveError("archive create: io") from error


def verify_archive(
    archive_path: Path,
    manifest_path: Path,
    *,
    limits: ArchiveLimits = _DEFAULT_LIMITS,
) -> ArchiveManifest:
    """Verify the manifest, raw archive bytes, and every tar member."""
    try:
        return _verify(Path(archive_path), Path(manifest_path), limits)
    except ArchiveError as error:
        raise _operation_error("verify", error) from error
    except (OSError, EOFError, tarfile.TarError) as error:
        raise ArchiveError("archive verify: io") from error


def inventory_archive(
    archive_path: Path,
    manifest_path: Path,
    *,
    limits: ArchiveLimits = _DEFAULT_LIMITS,
) -> ArchiveManifest:
    """Return the verified immutable member inventory for one archive."""
    try:
        return _verify(Path(archive_path), Path(manifest_path), limits)
    except ArchiveError as error:
        raise _operation_error("inventory", error) from error
    except (OSError, EOFError, tarfile.TarError) as error:
        raise ArchiveError("archive inventory: io") from error


def restore_archive(
    archive_path: Path,
    manifest_path: Path,
    destination_root: Path,
    *,
    limits: ArchiveLimits = _DEFAULT_LIMITS,
) -> ArchiveManifest:
    """Restore verified regular files beneath a caller-authorized destination root."""
    try:
        archive = Path(archive_path)
        manifest = _verify(archive, Path(manifest_path), limits)
        destination = _destination_root(destination_root)
        expected = {member.path: member for member in manifest.members}
        with _open_tar(archive) as handle:
            for info in handle:
                observed = _tar_member(info, limits)
                recorded = expected.get(observed.path)
                if recorded is None or recorded.size != observed.size:
                    raise ArchiveError("archive integrity")
                stream = handle.extractfile(info)
                if stream is None:
                    raise ArchiveError("archive integrity")
                _restore_member(destination, recorded, cast(BinaryIO, stream))
        return manifest
    except ArchiveError as error:
        raise _operation_error("restore", error) from error
    except (OSError, EOFError, tarfile.TarError) as error:
        raise ArchiveError("archive restore: io") from error


def _verify(archive: Path, manifest_path: Path, limits: ArchiveLimits) -> ArchiveManifest:
    manifest = _read_manifest(manifest_path)
    if manifest.archive_size > limits.max_archive_bytes:
        raise ArchiveError("archive bounds")
    digest, size = _digest_file(archive, limits.max_archive_bytes)
    if digest != manifest.archive_sha256 or size != manifest.archive_size:
        raise ArchiveError("archive integrity")
    with _open_tar(archive) as handle:
        observed = _inspect_tar(handle, limits)
    if observed != manifest.members:
        raise ArchiveError("archive integrity")
    return manifest


def _selected_members(members: Iterable[str], limits: ArchiveLimits) -> tuple[PurePosixPath, ...]:
    if isinstance(members, (str, bytes)):
        raise ArchiveError("archive invalid-input")
    try:
        selected = tuple(_safe_member_path(member) for member in members)
    except TypeError as error:
        raise ArchiveError("archive invalid-input") from error
    if len(selected) > limits.max_files:
        raise ArchiveError("archive bounds")
    paths = tuple(path.as_posix() for path in selected)
    if len(set(paths)) != len(paths):
        raise ArchiveError("archive unsafe-member")
    return tuple(sorted(selected, key=lambda path: path.as_posix()))


def _source_root(source_root: Path) -> Path:
    root = Path(source_root)
    try:
        metadata = root.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise ArchiveError("archive unsafe-member")
        return root.resolve(strict=True)
    except ArchiveError:
        raise
    except OSError as error:
        raise ArchiveError("archive io") from error


def _write_archive(
    root: Path,
    selected: tuple[PurePosixPath, ...],
    destination: Path,
    limits: ArchiveLimits,
) -> tuple[ArchiveMember, ...]:
    recorded: list[ArchiveMember] = []
    total = 0
    try:
        with destination.open("wb") as raw:
            _chmod(destination, 0o600)
            with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as compressed:
                with tarfile.open(
                    fileobj=compressed,
                    mode="w",
                    format=tarfile.GNU_FORMAT,
                ) as archive:
                    for relative in selected:
                        stream, metadata = _open_source_member(root, relative)
                        try:
                            size = metadata.st_size
                            if (
                                size > limits.max_file_bytes
                                or total + size > limits.max_total_bytes
                            ):
                                raise ArchiveError("archive bounds")
                            reader = _DigestReader(stream)
                            info = tarfile.TarInfo(relative.as_posix())
                            info.mode = 0o600
                            info.uid = 0
                            info.gid = 0
                            info.uname = ""
                            info.gname = ""
                            info.mtime = 0
                            info.size = size
                            archive.addfile(info, reader)
                            _assert_source_unchanged(stream, metadata, reader.size)
                            recorded.append(
                                ArchiveMember(
                                    path=relative.as_posix(),
                                    size=reader.size,
                                    sha256=reader.digest.hexdigest(),
                                )
                            )
                            total += reader.size
                        finally:
                            stream.close()
            raw.flush()
            _fsync_file(raw.fileno())
    except ArchiveError:
        raise
    except (OSError, tarfile.TarError) as error:
        raise ArchiveError("archive io") from error
    return tuple(recorded)


def _open_source_member(root: Path, relative: PurePosixPath) -> tuple[BinaryIO, os.stat_result]:
    current = root
    try:
        for segment in relative.parts[:-1]:
            current = current / segment
            metadata = current.lstat()
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
                raise ArchiveError("archive unsafe-member")
        path = current / relative.name
        initial = path.lstat()
        if (
            stat.S_ISLNK(initial.st_mode)
            or not stat.S_ISREG(initial.st_mode)
            or initial.st_nlink != 1
        ):
            raise ArchiveError("archive unsafe-member")
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        stream = os.fdopen(descriptor, "rb")
        opened = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or (opened.st_dev, opened.st_ino, opened.st_size)
            != (initial.st_dev, initial.st_ino, initial.st_size)
        ):
            stream.close()
            raise ArchiveError("archive unsafe-member")
        return stream, opened
    except ArchiveError:
        raise
    except OSError as error:
        raise ArchiveError("archive unsafe-member") from error


def _assert_source_unchanged(stream: BinaryIO, initial: os.stat_result, copied: int) -> None:
    try:
        final = os.fstat(stream.fileno())
    except OSError as error:
        raise ArchiveError("archive io") from error
    if (
        copied != initial.st_size
        or (final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns)
        != (initial.st_dev, initial.st_ino, initial.st_size, initial.st_mtime_ns)
    ):
        raise ArchiveError("archive integrity")


def _output_paths(archive_path: Path, manifest_path: Path) -> tuple[Path, Path, Path]:
    archive = Path(archive_path)
    manifest = Path(manifest_path)
    if not archive.name or not manifest.name or archive == manifest:
        raise ArchiveError("archive invalid-input")
    if archive.parent.resolve() != manifest.parent.resolve():
        raise ArchiveError("archive invalid-input")
    directory = archive.parent
    try:
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        metadata = directory.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise ArchiveError("archive unsafe-member")
        _chmod(directory, 0o700)
    except ArchiveError:
        raise
    except OSError as error:
        raise ArchiveError("archive io") from error
    return archive, manifest, directory


def _destination_root(destination_root: Path) -> Path:
    root = Path(destination_root)
    try:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        metadata = root.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise ArchiveError("archive unsafe-member")
        _chmod(root, 0o700)
        return root.resolve(strict=True)
    except ArchiveError:
        raise
    except OSError as error:
        raise ArchiveError("archive io") from error


def _publish(
    temporary_archive: Path,
    temporary_manifest: Path,
    archive: Path,
    manifest: Path,
    expected: ArchiveManifest,
    limits: ArchiveLimits,
) -> ArchiveResult:
    archive_exists = _regular_output_exists(archive)
    manifest_exists = _regular_output_exists(manifest)
    if archive_exists and manifest_exists:
        actual = _verify(archive, manifest, limits)
        if actual != expected:
            raise ArchiveError("archive conflict")
        return ArchiveResult(archive_path=archive, manifest_path=manifest, manifest=actual)
    if archive_exists:
        raise ArchiveError("archive conflict")
    if manifest_exists:
        if _read_manifest(manifest) != expected:
            raise ArchiveError("archive conflict")
        os.replace(temporary_archive, archive)
        _chmod(archive, 0o600)
        _fsync_directory(archive.parent)
        return ArchiveResult(archive_path=archive, manifest_path=manifest, manifest=expected)

    # Publish the manifest first. An interrupted publish can leave a harmless
    # manifest without an archive, but can never expose an archive without its
    # verified digest contract.
    os.replace(temporary_manifest, manifest)
    _chmod(manifest, 0o600)
    _fsync_directory(manifest.parent)
    os.replace(temporary_archive, archive)
    _chmod(archive, 0o600)
    _fsync_directory(archive.parent)
    return ArchiveResult(archive_path=archive, manifest_path=manifest, manifest=expected)


def _regular_output_exists(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    except OSError as error:
        raise ArchiveError("archive io") from error
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
    ):
        raise ArchiveError("archive unsafe-member")
    return True


def _read_manifest(path: Path) -> ArchiveManifest:
    return ArchiveManifest.from_bytes(_read_regular_file(Path(path), _MANIFEST_MAX_BYTES))


def _digest_file(path: Path, maximum: int) -> tuple[str, int]:
    try:
        metadata = Path(path).lstat()
        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
        ):
            raise ArchiveError("archive unsafe-member")
        if metadata.st_size > maximum:
            raise ArchiveError("archive bounds")
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(opened.st_mode)
                or opened.st_nlink != 1
                or opened.st_size != metadata.st_size
            ):
                raise ArchiveError("archive unsafe-member")
            digest = hashlib.sha256()
            size = 0
            while chunk := stream.read(64 * 1024):
                size += len(chunk)
                if size > maximum:
                    raise ArchiveError("archive bounds")
                digest.update(chunk)
            if os.fstat(stream.fileno()).st_size != size:
                raise ArchiveError("archive integrity")
        return digest.hexdigest(), size
    except ArchiveError:
        raise
    except OSError as error:
        raise ArchiveError("archive io") from error


def _read_regular_file(path: Path, maximum: int) -> bytes:
    try:
        metadata = Path(path).lstat()
        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
        ):
            raise ArchiveError("archive unsafe-member")
        if metadata.st_size > maximum:
            raise ArchiveError("archive bounds")
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(opened.st_mode)
                or opened.st_nlink != 1
                or opened.st_size != metadata.st_size
            ):
                raise ArchiveError("archive unsafe-member")
            content = stream.read(maximum + 1)
        if len(content) > maximum:
            raise ArchiveError("archive bounds")
        return content
    except ArchiveError:
        raise
    except OSError as error:
        raise ArchiveError("archive io") from error


@contextmanager
def _open_tar(path: Path) -> Iterator[tarfile.TarFile]:
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as stream:
            metadata = os.fstat(stream.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise ArchiveError("archive unsafe-member")
            with tarfile.open(fileobj=stream, mode="r:gz") as archive:
                yield archive
    except ArchiveError:
        raise
    except (OSError, EOFError, tarfile.TarError) as error:
        raise ArchiveError("archive integrity") from error


def _inspect_tar(handle: tarfile.TarFile, limits: ArchiveLimits) -> tuple[ArchiveMember, ...]:
    members: list[ArchiveMember] = []
    total = 0
    for info in handle:
        member = _tar_member(info, limits)
        total += member.size
        if total > limits.max_total_bytes or len(members) >= limits.max_files:
            raise ArchiveError("archive bounds")
        stream = handle.extractfile(info)
        if stream is None:
            raise ArchiveError("archive integrity")
        reader = _DigestReader(cast(BinaryIO, stream))
        try:
            while reader.read(64 * 1024):
                pass
        finally:
            stream.close()
        if reader.size != member.size:
            raise ArchiveError("archive integrity")
        members.append(ArchiveMember(member.path, member.size, reader.digest.hexdigest()))
    result = tuple(members)
    paths = tuple(member.path for member in result)
    if tuple(sorted(paths)) != paths or len(set(paths)) != len(paths):
        raise ArchiveError("archive integrity")
    return result


def _tar_member(info: tarfile.TarInfo, limits: ArchiveLimits) -> ArchiveMember:
    if not info.isreg() or info.issym() or info.islnk() or info.isdev() or info.isfifo():
        raise ArchiveError("archive unsafe-member")
    path = _safe_member_path(info.name).as_posix()
    if info.size < 0 or info.size > limits.max_file_bytes:
        raise ArchiveError("archive bounds")
    return ArchiveMember(path=path, size=info.size, sha256=hashlib.sha256(b"").hexdigest())


def _restore_member(destination: Path, member: ArchiveMember, stream: BinaryIO) -> None:
    relative = _safe_member_path(member.path)
    parent = destination
    try:
        for segment in relative.parts[:-1]:
            parent = parent / segment
            if parent.exists():
                metadata = parent.lstat()
                if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
                    raise ArchiveError("archive unsafe-member")
            else:
                parent.mkdir(mode=0o700)
            _chmod(parent, 0o700)
        target = parent / relative.name
        if target.exists() or target.is_symlink():
            if not _regular_output_exists(target):
                raise ArchiveError("archive unsafe-member")
            content = _read_regular_file(target, member.size)
            if (
                len(content) != member.size
                or hashlib.sha256(content).hexdigest() != member.sha256
            ):
                raise ArchiveError("archive conflict")
            return
        temporary = _temporary_file(parent, ".daidala-restore-")
        try:
            _chmod(temporary, 0o600)
            reader = _DigestReader(stream)
            with temporary.open("wb") as output:
                while chunk := reader.read(64 * 1024):
                    output.write(chunk)
                output.flush()
                _fsync_file(output.fileno())
            if reader.size != member.size or reader.digest.hexdigest() != member.sha256:
                raise ArchiveError("archive integrity")
            try:
                os.link(temporary, target)
            except FileExistsError as error:
                content = _read_regular_file(target, member.size)
                if (
                    len(content) != member.size
                    or hashlib.sha256(content).hexdigest() != member.sha256
                ):
                    raise ArchiveError("archive conflict") from error
            _chmod(target, 0o600)
            _fsync_directory(parent)
        finally:
            temporary.unlink(missing_ok=True)
    except ArchiveError:
        raise
    except OSError as error:
        raise ArchiveError("archive io") from error


def _temporary_file(directory: Path, prefix: str) -> Path:
    descriptor, temporary = tempfile.mkstemp(dir=directory, prefix=prefix)
    os.close(descriptor)
    return Path(temporary)


def _write_bytes(path: Path, content: bytes) -> None:
    try:
        with path.open("wb") as stream:
            stream.write(content)
            stream.flush()
            _fsync_file(stream.fileno())
    except OSError as error:
        raise ArchiveError("archive io") from error


def _fsync_file(descriptor: int) -> None:
    os.fsync(descriptor)


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _chmod(path: Path, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except OSError as error:
        raise ArchiveError("archive io") from error


def _safe_member_path(value: object) -> PurePosixPath:
    if (
        not isinstance(value, str)
        or not value
        or "\x00" in value
        or "\\" in value
        or len(value) > 512
    ):
        raise ArchiveError("archive invalid-input")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or path.as_posix() != value
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ArchiveError("archive unsafe-member")
    return path


def _safe_sha256(value: object) -> str:
    if not isinstance(value, str) or len(value) != _SHA256_LENGTH:
        raise ArchiveError("archive invalid-input")
    try:
        int(value, 16)
    except ValueError as error:
        raise ArchiveError("archive invalid-input") from error
    if value.lower() != value:
        raise ArchiveError("archive invalid-input")
    return value


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ArchiveError("archive invalid-input")
        result[key] = value
    return result


def _operation_error(operation: str, error: ArchiveError) -> ArchiveError:
    message = str(error)
    for cause in ("invalid-input", "unsafe-member", "bounds", "io", "integrity", "conflict"):
        if message.endswith(cause):
            return ArchiveError(f"archive {operation}: {cause}")
    return ArchiveError(f"archive {operation}: integrity")


class _DigestReader:
    def __init__(self, stream: BinaryIO) -> None:
        self._stream = stream
        self.digest = hashlib.sha256()
        self.size = 0

    def read(self, amount: int = -1) -> bytes:
        chunk = self._stream.read(amount)
        if chunk:
            self.digest.update(chunk)
            self.size += len(chunk)
        return chunk
