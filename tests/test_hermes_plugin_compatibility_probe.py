from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

PROBE = Path(__file__).parents[1] / "scripts" / "probe_hermes_plugin_compatibility.py"

FAKE_HERMES = r'''#!/usr/bin/env python3
import json
import os
import sys

args = sys.argv[1:]
if args == ["--version"]:
    if os.environ.get("FAKE_VERSION_MODE") == "candidate":
        print("Hermes Agent v0.19.0 (2026.7.20) · upstream 3ef6bbd2")
    else:
        print("Hermes Agent v0.18.2 (2026.7.7.2) · upstream 4281151a")
    raise SystemExit(0)

if args == ["plugins", "list", "--enabled", "--json"]:
    if os.environ.get("FAKE_PLUGIN_OMITTED") == "1":
        print("[]")
    else:
        print(json.dumps([{
            "name": "daidala",
            "status": os.environ.get("FAKE_PLUGIN_STATUS", "enabled"),
            "version": "0.2.0",
            "source": os.environ.get("FAKE_PLUGIN_SOURCE", "entrypoint"),
        }]))
    raise SystemExit(0)

if args[:3] == ["daidala", "packs", "validate"]:
    if os.environ.get("FAKE_NATIVE_FAIL") == "1":
        print("native failure", file=sys.stderr)
        raise SystemExit(1)
    pack = args[3]
    print(json.dumps({"success": True, "pack": pack, "source_revision": pack + "-rev"}))
    raise SystemExit(0)

print(f"unsupported fake Hermes command: {args}", file=sys.stderr)
raise SystemExit(2)
'''

FAKE_DAIDALA = r'''#!/usr/bin/env python3
import json
import sys

args = sys.argv[1:]
if args[:2] == ["packs", "validate"]:
    pack = args[2]
    print(json.dumps({"success": True, "pack": pack, "source_revision": pack + "-rev"}))
    raise SystemExit(0)
print(f"unsupported fake Daidala command: {args}", file=sys.stderr)
raise SystemExit(2)
'''


def run_probe(
    tmp_path: Path,
    arguments: list[str] | None = None,
    **environment: str,
) -> subprocess.CompletedProcess[str]:
    hermes = tmp_path / "hermes"
    daidala = tmp_path / "daidala"
    hermes.write_text(FAKE_HERMES, encoding="utf-8")
    daidala.write_text(FAKE_DAIDALA, encoding="utf-8")
    hermes.chmod(0o755)
    daidala.chmod(0o755)
    env = os.environ.copy()
    env.update(environment)
    env["TMPDIR"] = str(tmp_path)
    return subprocess.run(
        [
            sys.executable,
            str(PROBE),
            "--hermes",
            str(hermes),
            "--daidala",
            str(daidala),
            *(arguments or []),
        ],
        cwd=PROBE.parents[1],
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )


def test_probe_loads_plugin_and_compares_native_standalone_packs(tmp_path: Path) -> None:
    result = run_probe(tmp_path)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["hermes"] == {
        "semver": "0.18.2",
        "build": "2026.7.7.2",
        "upstream": "4281151a",
    }
    assert payload["plugin"] == {
        "name": "daidala",
        "version": "0.2.0",
        "reported": True,
        "source": "entrypoint",
        "status": "enabled",
        "discovery": "entrypoint",
    }
    assert sorted(payload["cli"]["packs"]) == ["addyosmani", "aidlc"]
    assert not list(tmp_path.glob("daidala-plugin-compat-*"))


def test_probe_accepts_explicit_candidate_identity(tmp_path: Path) -> None:
    result = run_probe(
        tmp_path,
        [
            "--expected-semver",
            "0.19.0",
            "--expected-build",
            "2026.7.20",
            "--expected-upstream",
            "3ef6bbd2",
        ],
        FAKE_VERSION_MODE="candidate",
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["hermes"]["semver"] == "0.19.0"


def test_probe_accepts_native_plugin_load_when_inventory_omits_entrypoint(
    tmp_path: Path,
) -> None:
    result = run_probe(tmp_path, FAKE_PLUGIN_OMITTED="1")

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["plugin"]["reported"] is False


def test_probe_rejects_reported_plugin_error(tmp_path: Path) -> None:
    result = run_probe(tmp_path, FAKE_PLUGIN_STATUS="error: register failed")

    assert result.returncode == 1
    assert "plugin is not enabled" in result.stderr
    assert not list(tmp_path.glob("daidala-plugin-compat-*"))


def test_probe_rejects_native_command_failure(tmp_path: Path) -> None:
    result = run_probe(tmp_path, FAKE_NATIVE_FAIL="1")

    assert result.returncode == 1
    assert "native addyosmani validation" not in result.stdout
    assert "native failure" in result.stderr
    assert not list(tmp_path.glob("daidala-plugin-compat-*"))


def test_probe_rejects_root_inside_active_hermes_home(tmp_path: Path) -> None:
    result = run_probe(tmp_path, HERMES_HOME=str(tmp_path))

    assert result.returncode == 1
    assert "inside the active HERMES_HOME" in result.stderr
    assert not list(tmp_path.glob("daidala-plugin-compat-*"))


def test_probe_loads_directory_plugin_from_isolated_symlink(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "plugin.yaml").write_text("name: daidala\nversion: 0.2.0\n", encoding="utf-8")
    (source / "__init__.py").write_text("def register(ctx):\n    pass\n", encoding="utf-8")

    result = run_probe(
        tmp_path,
        ["--plugin-directory", str(source)],
        FAKE_PLUGIN_SOURCE="git",
    )

    assert result.returncode == 0, result.stderr
    plugin = json.loads(result.stdout)["plugin"]
    assert plugin["discovery"] == "directory"
    assert plugin["source"] == "git"
    assert source.is_dir()
    assert not list(tmp_path.glob("daidala-plugin-compat-*"))
