from __future__ import annotations

import json
import struct
import subprocess
import sys
from pathlib import Path

CHECKER = Path(__file__).parents[1] / "scripts" / "check_records.py"


def run_checker(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECKER), str(root)],
        capture_output=True,
        check=False,
        text=True,
    )


def write_png(path: Path, width: int = 1440, height: int = 960) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\rIHDR"
        + struct.pack(">II", width, height)
    )


def write_cap(root: Path, *, surface: str = "none") -> Path:
    path = root / "docs/product/capabilities/CAP-0001-example.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# CAP-0001: Example\n\n"
        "**Status:** implemented\n"
        f"**Primary surface:** {surface}\n\n"
        "## Outcome\n\nAvailable now.\n\n"
        "## Behavior\n\n- Does the thing.\n\n"
        "## Evidence\n\n"
        "### Runtime\n\n- [source](../../../src.py)\n\n"
        "### Tests\n\n- [tests](../../../tests.py)\n\n"
        "## Contracts\n\n- Current contract.\n\n"
        "## Links\n\n- Current links.\n",
        encoding="utf-8",
    )
    product = root / "docs/product/README.md"
    product.parent.mkdir(parents=True, exist_ok=True)
    product.write_text("[CAP-0001](capabilities/CAP-0001-example.md)\n", encoding="utf-8")
    return path


def write_chg(root: Path, *, status: str = "in-progress", affected: str = "CAP-0001") -> Path:
    path = root / "docs/changes/active/CHG-0001-example.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# CHG-0001: Example\n\n"
        f"**Status:** {status}\n"
        "**Source request:** Direct operator request: \"example\"\n"
        f"**Affected capabilities:** {affected}\n"
        "**Created:** 2026-08-10\n\n"
        "## Outcome\n\nUpdated behavior.\n\n"
        "## Scope\n\n- One slice.\n\n"
        "## Phases\n\n"
        "| Phase | Status | Verification gate |\n"
        "|---|---|---|\n"
        "| Slice | in-progress | Tests pass. |\n\n"
        "## Decisions\n\n- None.\n\n"
        "## Evidence\n\nPending.\n",
        encoding="utf-8",
    )
    return path


def write_wireframes(root: Path, screens: list[dict[str, object]]) -> None:
    wireframes = root / "docs/product/wireframes"
    wireframes.mkdir(parents=True, exist_ok=True)
    (wireframes / "manifest.json").write_text(
        json.dumps({"version": 1, "screens": screens}), encoding="utf-8"
    )
    links = "".join(
        f'<a href="{screen["html"]}">HTML</a><a href="{screen["png"]}">PNG</a>'
        for screen in screens
    )
    (wireframes / "index.html").write_text(links, encoding="utf-8")
    for screen in screens:
        html = wireframes / str(screen["html"])
        html.parent.mkdir(parents=True, exist_ok=True)
        html.write_text("<!doctype html><title>Example</title>", encoding="utf-8")
        viewport = screen["viewport"]
        assert isinstance(viewport, dict)
        write_png(
            wireframes / str(screen["png"]),
            int(viewport["width"]),
            int(viewport["height"]),
        )


def test_checker_accepts_valid_records_without_a_qualifying_surface(tmp_path: Path) -> None:
    write_cap(tmp_path)
    write_chg(tmp_path)
    write_wireframes(tmp_path, [])

    result = run_checker(tmp_path)

    assert result.returncode == 0, result.stderr
    assert "1 capabilities, 1 change record(s), 0 wireframe(s)" in result.stdout


def test_checker_rejects_terminal_active_change_and_unknown_capability(tmp_path: Path) -> None:
    write_cap(tmp_path)
    path = write_chg(tmp_path, status="done", affected="CAP-9999")
    path.write_text(
        path.read_text(encoding="utf-8").replace("in-progress", "done"),
        encoding="utf-8",
    )
    write_wireframes(tmp_path, [])

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert "terminal CHG belongs in archive/" in result.stderr
    assert "unknown capability ID: CAP-9999" in result.stderr


def test_checker_requires_exact_wireframe_inventory_links_and_dimensions(tmp_path: Path) -> None:
    cap = write_cap(tmp_path, surface="Dashboard")
    cap.write_text(
        cap.read_text(encoding="utf-8")
        .replace(
            "- Current links.",
            "- [HTML](../wireframes/html/CAP-0001-example.html)\n"
            "- [PNG](../wireframes/exports/CAP-0001-example.png)",
        ),
        encoding="utf-8",
    )
    write_chg(tmp_path)
    screen = {
        "capability": "CAP-0001",
        "slug": "CAP-0001-example",
        "title": "Example",
        "html": "html/CAP-0001-example.html",
        "png": "exports/CAP-0001-example.png",
        "viewport": {"width": 1440, "height": 960},
    }
    write_wireframes(tmp_path, [screen])

    result = run_checker(tmp_path)
    assert result.returncode == 0, result.stderr

    write_png(tmp_path / "docs/product/wireframes/exports/CAP-0001-extra.png")
    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert "PNG inventory does not match exports/" in result.stderr


def test_checker_reports_non_object_manifest_without_crashing(tmp_path: Path) -> None:
    write_cap(tmp_path)
    write_chg(tmp_path)
    wireframes = tmp_path / "docs/product/wireframes"
    wireframes.mkdir(parents=True)
    (wireframes / "manifest.json").write_text("[]", encoding="utf-8")

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert "expected version 1 and screens list" in result.stderr
