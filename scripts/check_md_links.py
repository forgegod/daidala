#!/usr/bin/env python3
"""Validate local Markdown links and heading anchors without dependencies."""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

IGNORED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "site-packages",
    "wingstaff.egg-info",
}
HEADING_RE = re.compile(r"^ {0,3}(#{1,6})\s+(.+?)\s*$")
CUSTOM_ID_RE = re.compile(r"\s*\{#([A-Za-z][\w-]*)\}\s*$")
INLINE_LINK_RE = re.compile(
    r'''!?\[([^]]*)\]\(\s*(?:<([^>]+)>|([^\s)]+))'''
    r'''(?:\s+(?:"[^"]*"|'[^']*'|\([^)]*\)))?\s*\)'''
)
REFERENCE_DEF_RE = re.compile(r'^\s*\[([^]]+)\]:\s+(?:<([^>]+)>|(\S+))(?:\s+["\'(].*)?$')
REFERENCE_USE_RE = re.compile(r"(?<!!)\[([^]]+)\]\[([^]]*)\]")
AUTOLINK_RE = re.compile(r"<((?:data:|ftp://|https?://|mailto:|tel:)[^>]+)>")
EXTERNAL_SCHEMES = {"data", "ftp", "http", "https", "mailto", "tel"}


def markdown_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix.lower() == ".md" else []
    return sorted(
        path
        for path in root.rglob("*.md")
        if not any(part in IGNORED_DIRS for part in path.relative_to(root).parts)
    )


def visible_lines(path: Path) -> list[tuple[int, str]]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    visible: list[tuple[int, str]] = []
    fence: str | None = None
    for number, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        marker = stripped[:3]
        if marker in {"```", "~~~"}:
            if fence is None:
                fence = marker
            elif marker == fence:
                fence = None
            continue
        if fence is None and not line.startswith(("    ", "\t")):
            visible.append((number, line))
    return visible


def slugify(text: str) -> str:
    text = CUSTOM_ID_RE.sub("", text)
    text = re.sub(r"\s+#+\s*$", "", text).strip().lower()
    text = re.sub(r"[^\w\s\-\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", "", text)
    return re.sub(r"[\s-]+", "-", text).strip("-")


def heading_ids(path: Path, cache: dict[Path, set[str]]) -> set[str]:
    resolved = path.resolve()
    if resolved in cache:
        return cache[resolved]

    counts: Counter[str] = Counter()
    result: set[str] = set()
    for _, line in visible_lines(resolved):
        match = HEADING_RE.match(line)
        if not match:
            continue
        text = match.group(2)
        custom = CUSTOM_ID_RE.search(text)
        base = custom.group(1) if custom else slugify(text)
        if not base:
            continue
        duplicate = counts[base]
        result.add(base if duplicate == 0 else f"{base}-{duplicate}")
        counts[base] += 1

    cache[resolved] = result
    return result


def split_destination(raw: str) -> tuple[str, str | None, str | None]:
    destination = raw.strip()
    if destination.startswith("<") and destination.endswith(">"):
        destination = destination[1:-1]
    else:
        destination = re.split(r"\s+[\"']", destination, maxsplit=1)[0]

    parsed = urlsplit(destination)
    if parsed.scheme.lower() in EXTERNAL_SCHEMES or parsed.netloc:
        return destination, None, None
    return destination, unquote(parsed.path), unquote(parsed.fragment) or None


def display_path(path: Path, root: Path) -> str:
    """Return a stable path relative to the checked root."""
    return Path(os.path.relpath(path.resolve(), root)).as_posix()


def check_destination(
    source: Path,
    line: int,
    raw: str,
    heading_cache: dict[Path, set[str]],
    root: Path,
) -> list[str]:
    display, relative_path, anchor = split_destination(raw)
    if relative_path is None:
        return []

    target = source if not relative_path else source.parent / relative_path
    target = target.resolve()
    source_display = display_path(source, root)
    if not target.is_file():
        return [f"{source_display}:{line}: missing file: {display}"]

    if anchor and target.suffix.lower() == ".md":
        if anchor not in heading_ids(target, heading_cache):
            target_display = display_path(target, root)
            return [
                f"{source_display}:{line}: missing anchor #{anchor} in {target_display}"
            ]
    return []


def check_file(path: Path, heading_cache: dict[Path, set[str]], root: Path) -> list[str]:
    errors: list[str] = []
    definitions: dict[str, tuple[int, str]] = {}
    visible = visible_lines(path)

    for line_number, line in visible:
        definition = REFERENCE_DEF_RE.match(line)
        if definition:
            definitions[definition.group(1).casefold()] = (
                line_number,
                definition.group(2) or definition.group(3),
            )

    for line_number, line in visible:
        definition = REFERENCE_DEF_RE.match(line)
        if definition:
            raw = definition.group(2) or definition.group(3)
            errors.extend(check_destination(path, line_number, raw, heading_cache, root))
            continue

        without_autolinks = AUTOLINK_RE.sub("", line)
        for match in INLINE_LINK_RE.finditer(without_autolinks):
            raw = match.group(2) or match.group(3)
            errors.extend(
                check_destination(path, line_number, raw, heading_cache, root)
            )

        without_inline = INLINE_LINK_RE.sub("", without_autolinks)
        for match in REFERENCE_USE_RE.finditer(without_inline):
            reference = (match.group(2) or match.group(1)).casefold()
            if reference not in definitions:
                path_display = display_path(path, root)
                errors.append(
                    f"{path_display}:{line_number}: undefined reference link: [{reference}]"
                )

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate local links and anchors in Markdown files."
    )
    parser.add_argument("path", nargs="?", default=".", type=Path)
    args = parser.parse_args(argv)

    root = args.path.resolve()
    if not root.exists():
        parser.error(f"path does not exist: {args.path}")

    files = markdown_files(root)
    display_root = root if root.is_dir() else root.parent
    cache: dict[Path, set[str]] = {}
    errors = [
        error for path in files for error in check_file(path, cache, display_root)
    ]
    if errors:
        print("\n".join(errors), file=sys.stderr)
        print(f"Markdown link check failed: {len(errors)} issue(s)", file=sys.stderr)
        return 1

    print(f"Markdown link check passed: {len(files)} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
