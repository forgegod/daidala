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
import subprocess
import sys

args = sys.argv[1:]
if args == ["--version"]:
    if os.environ.get("FAKE_VERSION_MODE") == "baseline":
        print("Hermes Agent v0.18.2 (2026.7.7.2) · upstream 4281151a")
    else:
        print("Hermes Agent v0.19.0 (2026.7.20) · upstream 3ef6bbd2")
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

if args[:3] == ["daidala", "project-cycle", "admit"]:
    result = subprocess.run(
        [os.environ["FAKE_DAIDALA_PATH"], *args[1:]],
        capture_output=True,
        env=os.environ,
        text=True,
    )
    if result.returncode == 0 and os.environ.get("FAKE_ADMISSION_MISMATCH") == "1":
        payload = json.loads(result.stdout)
        payload["preview"]["workflow_id"] = "cycle-" + "e" * 64
        print(json.dumps(payload, sort_keys=True))
    else:
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
    raise SystemExit(result.returncode)

print(f"unsupported fake Hermes command: {args}", file=sys.stderr)
raise SystemExit(2)
'''

FAKE_DAIDALA = r'''#!/usr/bin/env python3
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from daidala.constraints import parse_workflow_constraints
from daidala.packs import load_pack, pack_content_digest
from daidala.projects import parse_project_manifest
from daidala.registrations import parse_controller_registration

args = sys.argv[1:]
if args[:2] == ["packs", "validate"]:
    pack = args[2]
    print(json.dumps({"success": True, "pack": pack, "source_revision": pack + "-rev"}))
    raise SystemExit(0)
if args[:2] == ["project-cycle", "admit"]:
    def value(flag):
        return args[args.index(flag) + 1]

    manifest_path = Path(value("--project-manifest"))
    registration_path = Path(value("--registration"))
    manifest = parse_project_manifest(manifest_path.read_text(encoding="utf-8"))
    registration = parse_controller_registration(
        registration_path.read_text(encoding="utf-8")
    )
    constraints = parse_workflow_constraints(
        (manifest_path.parent / "constraints.yaml").read_text(encoding="utf-8")
    )
    baseline = subprocess.run(
        ["git", "-C", registration.checkout, "rev-parse", "HEAD"],
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()
    stage_profiles = []
    for index, token in enumerate(args):
        if token == "--stage-profile":
            stage, profile = args[index + 1].split("=", 1)
            stage_profiles.append({"stage": stage, "profile": profile})
    pack = load_pack("addyosmani")
    cycle = {
        "schema": "daidala.cycle-identity/v1",
        "project_id": manifest.project_id,
        "mode": "improve",
        "intake_adapter": "github-issue",
        "intake_item_id": "42",
        "manifest_digest": manifest.digest,
        "baseline_revision": baseline,
        "pack_name": "addyosmani",
        "pack_source_revision": pack.source_revision,
        "pack_content_digest": pack_content_digest("addyosmani"),
        "candidate_identity": None,
    }
    workflow_id = "cycle-" + hashlib.sha256(
        json.dumps(cycle, sort_keys=True).encode()
    ).hexdigest()
    payload = {
        "success": True,
        "operation": "project-cycle-admit",
        "dry_run": True,
        "preview": {
            "schema": "daidala.admission-preview/v1",
            "dry_run": True,
            "cycle": cycle,
            "workflow_id": workflow_id,
            "board": registration.board,
            "checkout": registration.checkout,
            "registration_digest": registration.digest,
            "constraints_digest": constraints.digest,
            "stage_profiles": stage_profiles,
            "intake_digest": "d" * 64,
        },
    }
    if os.environ.get("FAKE_PREVIEW_MUTATION") == "1":
        registration_path.write_text("mutated\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
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
    env["FAKE_DAIDALA_PATH"] = str(daidala)
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
        "semver": "0.19.0",
        "build": "2026.7.20",
        "upstream": "3ef6bbd2",
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
    admission = payload["cli"]["admission_preview"]
    assert admission["native_exit"] == admission["standalone_exit"] == 0
    assert admission["byte_identical"] is True
    assert admission["state_unchanged"] is True
    assert admission["mutation_commands"] == 0
    assert not list(tmp_path.glob("daidala-plugin-compat-*"))


def test_probe_output_is_byte_identical_across_isolated_runs(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()

    first = run_probe(first_root)
    second = run_probe(second_root)

    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout


def test_probe_accepts_explicit_baseline_identity(tmp_path: Path) -> None:
    result = run_probe(
        tmp_path,
        [
            "--expected-semver",
            "0.18.2",
            "--expected-build",
            "2026.7.7.2",
            "--expected-upstream",
            "4281151a",
        ],
        FAKE_VERSION_MODE="baseline",
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["hermes"]["semver"] == "0.18.2"


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


def test_probe_rejects_native_standalone_admission_mismatch(tmp_path: Path) -> None:
    result = run_probe(tmp_path, FAKE_ADMISSION_MISMATCH="1")

    assert result.returncode == 1
    assert "admission preview JSON differ" in result.stderr
    assert not list(tmp_path.glob("daidala-plugin-compat-*"))


def test_probe_rejects_admission_preview_mutation(tmp_path: Path) -> None:
    result = run_probe(tmp_path, FAKE_PREVIEW_MUTATION="1")

    assert result.returncode == 1
    assert "preview mutated isolated state" in result.stderr
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
