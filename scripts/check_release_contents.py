#!/usr/bin/env python3
"""Reject sensitive or runtime-only content from the repository and built wheels."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

FORBIDDEN_PARTS = {".env", ".hermes", "__pycache__", "work"}
FORBIDDEN_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".pyc", ".pyo"}
SUPERSEDED_IDENTITY = bytes((119, 105, 110, 103, 115, 116, 97, 102, 102)).decode("ascii")
SECRET_PATTERNS = {
    "private key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "AWS access key": re.compile(rb"(?<![A-Z0-9])AKIA[0-9A-Z]{16}(?![A-Z0-9])"),
    "GitHub token": re.compile(rb"(?<![A-Za-z0-9_])gh[pousr]_[A-Za-z0-9]{36,255}"),
    "OpenAI key": re.compile(rb"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9_-]{32,}"),
}


def forbidden_path(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(FORBIDDEN_PARTS.intersection(path.parts)) or path.suffix in FORBIDDEN_SUFFIXES


def tracked_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode(errors="replace").strip() or "git ls-files failed")
    return [root / item.decode() for item in result.stdout.split(b"\0") if item]


def check_payload(name: str, payload: bytes) -> list[str]:
    errors = [f"{name}: forbidden release path"] if forbidden_path(name) else []
    if SUPERSEDED_IDENTITY in name.casefold():
        errors.append(f"{name}: superseded project identity in release path")
    if b"\0" in payload:
        return errors
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        text = ""
    if SUPERSEDED_IDENTITY in text.casefold():
        errors.append(f"{name}: superseded project identity in release content")
    for label, pattern in SECRET_PATTERNS.items():
        if pattern.search(payload):
            errors.append(f"{name}: possible {label}")
    return errors


def check_repository(root: Path) -> tuple[list[str], int]:
    errors: list[str] = []
    files = tracked_files(root)
    for path in files:
        errors.extend(check_payload(path.relative_to(root).as_posix(), path.read_bytes()))
    return errors, len(files)


def check_wheel(path: Path) -> tuple[list[str], int]:
    errors: list[str] = []
    with ZipFile(path) as archive:
        names = [name for name in archive.namelist() if not name.endswith("/")]
        for name in names:
            errors.extend(check_payload(name, archive.read(name)))
    return errors, len(names)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", type=Path)
    parser.add_argument("--wheel", action="append", default=[], type=Path)
    args = parser.parse_args(argv)

    root = args.root.resolve()
    try:
        errors, repository_count = check_repository(root)
        wheel_count = 0
        for wheel in args.wheel:
            wheel_errors, count = check_wheel(wheel.resolve())
            errors.extend(wheel_errors)
            wheel_count += count
    except (OSError, RuntimeError) as error:
        print(f"Release-content check failed: {error}", file=sys.stderr)
        return 2

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print(f"Release-content check failed: {len(errors)} issue(s)", file=sys.stderr)
        return 1

    print(
        f"Release-content check passed: {repository_count} tracked file(s), "
        f"{wheel_count} wheel member(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
