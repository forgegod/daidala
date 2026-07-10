from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

CHECKER = Path(__file__).parents[1] / "scripts" / "check_release_contents.py"


def initialize_repository(path: Path, files: dict[str, bytes]) -> None:
    for name, content in files.items():
        target = path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)


def run_checker(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECKER), str(root), *args],
        capture_output=True,
        check=False,
        text=True,
    )


def test_release_checker_accepts_clean_repository_and_wheel(tmp_path: Path) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    initialize_repository(root, {"README.md": b"safe release\n"})
    wheel = tmp_path / "clean.whl"
    with ZipFile(wheel, "w") as archive:
        archive.writestr("wingstaff/__init__.py", "__version__ = 'test'\n")

    result = run_checker(root, "--wheel", str(wheel))

    assert result.returncode == 0, result.stderr
    assert "1 tracked file(s), 1 wheel member(s)" in result.stdout


def test_release_checker_rejects_runtime_state_and_secret_signatures(tmp_path: Path) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    initialize_repository(
        root,
        {
            "state.db": b"runtime state",
            "config.txt": b"-----BEGIN " + b"PRIVATE KEY-----\nnot-a-real-key\n",
        },
    )

    result = run_checker(root)

    assert result.returncode == 1
    assert "state.db: forbidden release path" in result.stderr
    assert "config.txt: possible private key" in result.stderr
    assert "Release-content check failed: 2 issue(s)" in result.stderr
