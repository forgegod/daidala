#!/usr/bin/env python3
"""Validate Daidala capability, change, and wireframe records."""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from pathlib import Path
from typing import Any

CAP_FILE_RE = re.compile(r"^(CAP-\d{4})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
CHG_FILE_RE = re.compile(r"^(CHG-\d{4})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
LINK_RE = re.compile(r"!?\[[^]]*\]\(([^\s)]+)(?:\s+[^)]*)?\)")
CAP_STATUS = {"implemented", "deprecated"}
CHG_STATUS = {"pending", "in-progress", "blocked", "done", "cancelled"}
PHASE_STATUS = {"pending", "in-progress", "blocked", "done", "cancelled"}
CAP_SECTIONS = ("Outcome", "Behavior", "Evidence", "Contracts", "Links")
CHG_SECTIONS = ("Outcome", "Scope", "Phases", "Decisions", "Evidence")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def field(text: str, name: str) -> str | None:
    match = re.search(rf"^\*\*{re.escape(name)}:\*\*\s*(.+?)\s*$", text, re.MULTILINE)
    return match.group(1).strip() if match else None


def section(text: str, heading: str, *, level: int = 2) -> str | None:
    marker = "#" * level
    match = re.search(
        rf"^{marker}\s+{re.escape(heading)}\s*$\n(.*?)(?=^#{{1,{level}}}\s+|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    return match.group(1).strip() if match else None


def display(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def load_text(path: Path, root: Path, errors: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        errors.append(f"{display(path, root)}: cannot read UTF-8 text: {error}")
        return ""


def require_sections(
    path: Path, text: str, headings: tuple[str, ...], root: Path, errors: list[str]
) -> None:
    for heading in headings:
        if section(text, heading) is None:
            errors.append(f"{display(path, root)}: missing section: ## {heading}")


def validate_capabilities(root: Path, errors: list[str]) -> dict[str, tuple[Path, str]]:
    product = root / "docs" / "product"
    index_path = product / "README.md"
    index = load_text(index_path, root, errors)
    capability_dir = product / "capabilities"
    paths = sorted(capability_dir.glob("CAP-*.md")) if capability_dir.is_dir() else []
    if not paths:
        errors.append("docs/product/capabilities: no CAP records found")
        return {}

    indexed_targets = LINK_RE.findall(index)
    capabilities: dict[str, tuple[Path, str]] = {}
    for path in paths:
        match = CAP_FILE_RE.fullmatch(path.name)
        if match is None:
            errors.append(f"{display(path, root)}: invalid CAP filename")
            continue
        cap_id = match.group(1)
        text = load_text(path, root, errors)
        heading = re.search(r"^#\s+(CAP-\d{4}):\s+\S", text, re.MULTILINE)
        if heading is None or heading.group(1) != cap_id:
            errors.append(f"{display(path, root)}: heading must start with # {cap_id}: ")
        if cap_id in capabilities:
            errors.append(f"{display(path, root)}: duplicate capability ID: {cap_id}")
        capabilities[cap_id] = (path, text)

        status = field(text, "Status")
        if status not in CAP_STATUS:
            errors.append(f"{display(path, root)}: invalid or missing Status: {status!r}")
        primary_surface = field(text, "Primary surface")
        if not primary_surface:
            errors.append(f"{display(path, root)}: missing Primary surface")
        require_sections(path, text, CAP_SECTIONS, root, errors)

        runtime = section(text, "Runtime", level=3)
        tests = section(text, "Tests", level=3)
        if runtime is None or not LINK_RE.search(runtime):
            errors.append(f"{display(path, root)}: Evidence/Runtime needs a source link")
        if tests is None or not LINK_RE.search(tests):
            errors.append(f"{display(path, root)}: Evidence/Tests needs a test link")

        target = f"capabilities/{path.name}"
        if indexed_targets.count(target) != 1:
            errors.append(
                f"docs/product/README.md: must link {target} exactly once"
            )
    return capabilities


def phase_statuses(text: str) -> list[str]:
    body = section(text, "Phases") or ""
    statuses: list[str] = []
    for line in body.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[1] in PHASE_STATUS:
            statuses.append(cells[1])
    return statuses


def validate_changes(
    root: Path,
    capabilities: dict[str, tuple[Path, str]],
    errors: list[str],
) -> int:
    changes_root = root / "docs" / "changes"
    count = 0
    for location in ("active", "archive"):
        directory = changes_root / location
        paths = sorted(directory.glob("CHG-*.md")) if directory.is_dir() else []
        for path in paths:
            count += 1
            match = CHG_FILE_RE.fullmatch(path.name)
            if match is None:
                errors.append(f"{display(path, root)}: invalid CHG filename")
                continue
            chg_id = match.group(1)
            text = load_text(path, root, errors)
            heading = re.search(r"^#\s+(CHG-\d{4}):\s+\S", text, re.MULTILINE)
            if heading is None or heading.group(1) != chg_id:
                errors.append(f"{display(path, root)}: heading must start with # {chg_id}: ")

            status = field(text, "Status")
            if status not in CHG_STATUS:
                errors.append(f"{display(path, root)}: invalid or missing Status: {status!r}")
            if location == "active" and status in {"done", "cancelled"}:
                errors.append(f"{display(path, root)}: terminal CHG belongs in archive/")
            if location == "archive" and status not in {"done", "cancelled"}:
                errors.append(f"{display(path, root)}: non-terminal CHG belongs in active/")

            source_request = field(text, "Source request")
            if not source_request:
                errors.append(f"{display(path, root)}: missing Source request")
            if not field(text, "Created"):
                errors.append(f"{display(path, root)}: missing Created date")
            affected = field(text, "Affected capabilities") or ""
            affected_ids = re.findall(r"CAP-\d{4}", affected)
            if not affected_ids:
                errors.append(f"{display(path, root)}: no affected capability IDs")
            for cap_id in affected_ids:
                if cap_id not in capabilities:
                    errors.append(f"{display(path, root)}: unknown capability ID: {cap_id}")
            require_sections(path, text, CHG_SECTIONS, root, errors)

            phases = phase_statuses(text)
            if not phases:
                errors.append(f"{display(path, root)}: Phases table has no recognized rows")
            if status == "in-progress" and phases.count("in-progress") != 1:
                errors.append(
                    f"{display(path, root)}: in-progress CHG needs exactly one in-progress phase"
                )
            if status in {"pending", "blocked", "done", "cancelled"} and "in-progress" in phases:
                errors.append(
                    f"{display(path, root)}: {status} CHG cannot have an in-progress phase"
                )
            if status == "done" and any(phase != "done" for phase in phases):
                errors.append(f"{display(path, root)}: done CHG requires all phases done")
    return count


def png_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        data = path.read_bytes()[:24]
    except OSError:
        return None
    if len(data) != 24 or not data.startswith(PNG_SIGNATURE) or data[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", data[16:24])


def validate_wireframes(
    root: Path,
    capabilities: dict[str, tuple[Path, str]],
    errors: list[str],
) -> int:
    wireframes = root / "docs" / "product" / "wireframes"
    manifest_path = wireframes / "manifest.json"
    try:
        payload: Any = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        errors.append(f"docs/product/wireframes/manifest.json: cannot read: {error}")
        return 0
    screens = payload.get("screens") if isinstance(payload, dict) else None
    version = payload.get("version") if isinstance(payload, dict) else None
    if version != 1 or not isinstance(screens, list):
        errors.append("docs/product/wireframes/manifest.json: expected version 1 and screens list")
        return 0

    index = load_text(wireframes / "index.html", root, errors)
    manifest_html: set[str] = set()
    manifest_png: set[str] = set()
    manifest_caps: set[str] = set()
    for position, screen in enumerate(screens):
        if not isinstance(screen, dict):
            errors.append(
                "docs/product/wireframes/manifest.json: "
                f"screen {position} is not an object"
            )
            continue
        cap_id = screen.get("capability")
        html = screen.get("html")
        png = screen.get("png")
        viewport = screen.get("viewport")
        if not isinstance(cap_id, str) or cap_id not in capabilities:
            errors.append(f"docs/product/wireframes/manifest.json: unknown capability: {cap_id!r}")
            continue
        if cap_id in manifest_caps:
            errors.append(f"docs/product/wireframes/manifest.json: duplicate capability: {cap_id}")
        manifest_caps.add(cap_id)
        if not isinstance(html, str) or not re.fullmatch(r"html/CAP-\d{4}-[a-z0-9-]+\.html", html):
            errors.append(f"docs/product/wireframes/manifest.json: invalid HTML path for {cap_id}")
            continue
        if not isinstance(png, str) or not re.fullmatch(r"exports/CAP-\d{4}-[a-z0-9-]+\.png", png):
            errors.append(f"docs/product/wireframes/manifest.json: invalid PNG path for {cap_id}")
            continue
        manifest_html.add(html)
        manifest_png.add(png)
        cap_path, cap_text = capabilities[cap_id]
        if f"../wireframes/{html}" not in cap_text or f"../wireframes/{png}" not in cap_text:
            errors.append(f"{display(cap_path, root)}: missing manifest HTML/PNG links")
        if f'href="{html}"' not in index or f'href="{png}"' not in index:
            errors.append(f"docs/product/wireframes/index.html: missing links for {cap_id}")
        html_path = wireframes / html
        png_path = wireframes / png
        if not html_path.is_file():
            errors.append(f"{display(html_path, root)}: missing generated HTML")
        dimensions = png_dimensions(png_path)
        if dimensions is None:
            errors.append(f"{display(png_path, root)}: missing or invalid PNG")
        elif not isinstance(viewport, dict) or dimensions != (
            viewport.get("width"),
            viewport.get("height"),
        ):
            errors.append(
                f"{display(png_path, root)}: PNG dimensions {dimensions} "
                "do not match manifest viewport"
            )

    actual_html = {
        path.relative_to(wireframes).as_posix()
        for path in (wireframes / "html").glob("CAP-*.html")
    }
    actual_png = {
        path.relative_to(wireframes).as_posix()
        for path in (wireframes / "exports").glob("CAP-*.png")
    }
    if actual_html != manifest_html:
        errors.append("docs/product/wireframes/manifest.json: HTML inventory does not match html/")
    if actual_png != manifest_png:
        errors.append(
            "docs/product/wireframes/manifest.json: "
            "PNG inventory does not match exports/"
        )

    qualifying = {
        cap_id
        for cap_id, (_, text) in capabilities.items()
        if not (field(text, "Primary surface") or "").casefold().startswith("none")
    }
    if qualifying != manifest_caps:
        errors.append(
            "docs/product/wireframes/manifest.json: qualifying CAP inventory mismatch: "
            f"expected {sorted(qualifying)}, got {sorted(manifest_caps)}"
        )
    return len(screens)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    errors: list[str] = []

    capabilities = validate_capabilities(root, errors)
    changes = validate_changes(root, capabilities, errors)
    wireframes = validate_wireframes(root, capabilities, errors)

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print(f"Record check failed: {len(errors)} issue(s)", file=sys.stderr)
        return 1
    print(
        f"Record check passed: {len(capabilities)} capabilities, "
        f"{changes} change record(s), {wireframes} wireframe(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
