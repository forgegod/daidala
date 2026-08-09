"""Atomic, private replacement for profile-local configuration files."""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

from .errors import PolicyViolationError


class ProfileFileError(PolicyViolationError):
    """Raised when a profile-local configuration file is unsafe or unavailable."""


def read_private_text(path: Path, *, maximum_bytes: int, label: str) -> str:
    """Read one regular, mode-0600 profile file without accepting a symlink."""

    _require_absolute_path(path, label)
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        raise
    except OSError as error:
        raise ProfileFileError(f"cannot read {label}") from error
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise ProfileFileError(f"{label} must be a regular file")
    if metadata.st_mode & 0o777 != 0o600:
        raise ProfileFileError(f"{label} must use mode 0600")
    if metadata.st_size > maximum_bytes:
        raise ProfileFileError(f"{label} exceeds {maximum_bytes} bytes")
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as stream:
            content = stream.read(maximum_bytes + 1)
    except OSError as error:
        raise ProfileFileError(f"cannot read {label}") from error
    if len(content) > maximum_bytes:
        raise ProfileFileError(f"{label} exceeds {maximum_bytes} bytes")
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ProfileFileError(f"{label} is not UTF-8") from error


def atomic_write_private_text(path: Path, content: str, *, label: str) -> None:
    """Replace one regular profile file atomically with a mode-0600 file."""

    _require_absolute_path(path, label)
    if not isinstance(content, str):
        raise ProfileFileError(f"{label} content must be text")
    parent = path.parent
    _require_safe_directory(parent, label)
    if path.exists() or path.is_symlink():
        try:
            metadata = path.lstat()
        except OSError as error:
            raise ProfileFileError(f"cannot inspect {label}") from error
        if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
            raise ProfileFileError(f"{label} must be a regular file")
    temporary: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(prefix=".daidala-", dir=parent)
        temporary = Path(temporary_name)
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
        _fsync_directory(parent)
    except OSError as error:
        raise ProfileFileError(f"cannot replace {label}") from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _require_absolute_path(path: Path, label: str) -> None:
    if (
        not isinstance(path, Path)
        or not path.is_absolute()
        or "." in path.parts
        or ".." in path.parts
    ):
        raise ProfileFileError(f"{label} path must be absolute and normalized")


def _require_safe_directory(path: Path, label: str) -> None:
    _require_absolute_path(path, label)
    try:
        metadata = path.lstat()
    except OSError as error:
        raise ProfileFileError(f"{label} parent is unavailable") from error
    if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise ProfileFileError(f"{label} parent must be a real directory")
    if path.resolve() != path:
        raise ProfileFileError(f"{label} parent cannot traverse a symlink")


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
