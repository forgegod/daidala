from __future__ import annotations

import subprocess
import sys
from pathlib import Path

CHECKER = Path(__file__).parents[1] / "scripts" / "check_md_links.py"


def run_checker(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECKER), str(path)],
        capture_output=True,
        check=False,
        text=True,
    )


def test_checker_accepts_supported_markdown_forms(tmp_path: Path) -> None:
    (tmp_path / "image.png").write_bytes(b"not-an-image-but-an-existing-target")
    (tmp_path / "target.md").write_text(
        "\ufeff# Target\n\n"
        "  ## Leading heading\n\n"
        "## Repeat\n\n"
        "## Repeat\n\n"
        "## Custom heading {#chosen}\n",
        encoding="utf-8",
    )
    (tmp_path / "source.md").write_text(
        "[target](target.md#target)\n"
        "[leading](target.md#leading-heading)\n"
        "[duplicate](target.md#repeat-1)\n"
        "[custom](target.md#chosen)\n"
        "[quoted](target.md \"title\")\n"
        "[parenthesized](target.md (title))\n"
        "![image](image.png)\n"
        "[reference][target-ref]\n"
        "[target-ref]: target.md#target\n"
        "<https://example.com/path>\n"
        "<ftp://example.com/archive>\n"
        "```markdown\n"
        "[ignored fenced link](missing-fenced.md)\n"
        "```\n\n"
        "    [ignored indented link](missing-indented.md)\n",
        encoding="utf-8",
    )

    result = run_checker(tmp_path)

    assert result.returncode == 0, result.stderr
    assert "Markdown link check passed: 2 file(s)" in result.stdout


def test_checker_reports_relative_missing_targets_and_failure_exit(tmp_path: Path) -> None:
    (tmp_path / "target.md").write_text("# Existing\n", encoding="utf-8")
    (tmp_path / "source.md").write_text(
        "[missing](missing.md)\n[anchor](target.md#absent)\n",
        encoding="utf-8",
    )

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert "source.md:1: missing file: missing.md" in result.stderr
    assert "source.md:2: missing anchor #absent in target.md" in result.stderr
    assert str(tmp_path) not in result.stderr
    assert "Markdown link check failed: 2 issue(s)" in result.stderr
