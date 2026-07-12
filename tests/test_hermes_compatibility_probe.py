from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

PROBE = Path(__file__).parents[1] / "scripts" / "probe_hermes_compatibility.py"

FAKE_HERMES = r'''#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]
home = Path(os.environ["HERMES_HOME"])
state_path = home / "fake-hermes-state.json"
state = json.loads(state_path.read_text()) if state_path.exists() else {"tasks": {}, "next": 1}

if args == ["--version"]:
    mode = os.environ.get("FAKE_VERSION_MODE", "ok")
    if mode == "missing":
        print("Hermes Agent unknown")
    elif mode == "changed":
        print("Hermes Agent v0.19.0 (2026.8.1) · upstream deadbeef")
    else:
        print("Hermes Agent v0.18.2 (2026.7.7.2) · upstream 4281151a")
    raise SystemExit(0)

if args[:2] == ["kanban", "boards"] or args[-1:] == ["init"]:
    raise SystemExit(0)
command = args[3]
rest = args[4:]
if command == "create":
    task_id = f"t_{state['next']}"
    state["next"] += 1
    state["tasks"][task_id] = {
        "id": task_id,
        "title": rest[0],
        "body": rest[rest.index("--body") + 1],
    }
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state))
    print(json.dumps({"id": task_id}))
elif command == "show":
    print(json.dumps({"task": state["tasks"][rest[0]]}))
elif command == "context":
    body = state["tasks"][rest[0]]["body"]
    limit = int(os.environ.get("FAKE_INTACT_LIMIT", "8192"))
    if len(body) > limit:
        print(body[:limit] + "\n[truncated]")
    else:
        print(body)
elif command in {"link", "comment", "complete", "archive"}:
    pass
else:
    print(f"unsupported fake Hermes command: {args}", file=sys.stderr)
    raise SystemExit(2)
'''


def run_probe(tmp_path: Path, **environment: str) -> subprocess.CompletedProcess[str]:
    hermes = tmp_path / "hermes"
    hermes.write_text(FAKE_HERMES, encoding="utf-8")
    hermes.chmod(0o755)
    env = os.environ.copy()
    env.update(environment)
    env["TMPDIR"] = str(tmp_path)
    return subprocess.run(
        [sys.executable, str(PROBE), "--hermes", str(hermes)],
        cwd=PROBE.parents[1],
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )


def test_probe_parses_supported_host_and_cleans_isolated_home(tmp_path: Path) -> None:
    result = run_probe(tmp_path)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["hermes"] == {
        "semver": "0.18.2",
        "build": "2026.7.7.2",
        "upstream": "4281151a",
    }
    assert payload["skill"]["name"] == "policy-probe"
    assert len(payload["skill"]["digest"]) == 64
    assert payload["worker_context"] == {"intact": 8192, "truncated": 8300}
    assert not list(tmp_path.glob("wingstaff-hermes-compat-*"))


def test_probe_rejects_changed_supported_host_identity(tmp_path: Path) -> None:
    result = run_probe(tmp_path, FAKE_VERSION_MODE="changed")

    assert result.returncode == 1
    assert "unsupported Hermes identity" in result.stderr
    assert "0.19.0" in result.stderr


def test_probe_rejects_missing_host_identity_fields(tmp_path: Path) -> None:
    result = run_probe(tmp_path, FAKE_VERSION_MODE="missing")

    assert result.returncode == 1
    assert "missing semantic, build, or upstream identity" in result.stderr


def test_probe_rejects_worker_context_boundary_drift_and_cleans(tmp_path: Path) -> None:
    result = run_probe(tmp_path, FAKE_INTACT_LIMIT="8000")

    assert result.returncode == 1
    assert "8192-character body was not preserved" in result.stderr
    assert not list(tmp_path.glob("wingstaff-hermes-compat-*"))
