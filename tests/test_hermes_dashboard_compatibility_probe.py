from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path

PROBE = Path(__file__).resolve().parents[1] / "scripts" / "probe_hermes_dashboard_compatibility.py"

FAKE_HERMES = r'''#!/usr/bin/env python3
import json
import os
import socket
import sys
from pathlib import Path

args = sys.argv[1:]
home = Path(os.environ["HERMES_HOME"])
state_path = home / "fake-hermes-state.json"
state = json.loads(state_path.read_text()) if state_path.exists() else {"next": 1}

if args == ["--version"]:
    mode = os.environ.get("FAKE_VERSION_MODE", "ok")
    if mode == "missing":
        print("Hermes Agent unknown")
    elif mode == "candidate":
        print("Hermes Agent v0.19.0 (2026.7.20) · upstream 3ef6bbd2")
    elif mode == "changed":
        print("Hermes Agent v0.19.0 (2026.8.1) · upstream deadbeef")
    else:
        print("Hermes Agent v0.18.2 (2026.7.7.2) · upstream 4281151a")
    raise SystemExit(0)

if args[:1] == ["dashboard"]:
    port = int(args[args.index("--port") + 1])
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", port))
    sock.listen(8)
    body = json.dumps([{
        "name": "daidala", "label": "Daidala", "version": "0.2.0",
        "tab": {"path": "/daidala", "position": "after:kanban"},
        "slots": ["sessions:top"], "entry": "dist/index.js", "css": "dist/style.css",
        "has_api": True, "source": "user",
    }]).encode()
    while True:
        conn, _ = sock.accept()
        data = conn.recv(4096)
        if not data:
            break
        first = data.split(b" ", 2)[1].decode()
        if first == "/api/dashboard/plugins":
            response = (b"HTTP/1.1 200 OK\r\n"
                        b"Content-Type: application/json\r\n"
                        b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body)
        elif first.startswith("/dashboard-plugins/daidala/"):
            response = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok"
        elif first == "/api/plugins/daidala/health":
            response = b"HTTP/1.1 401 Unauthorized\r\nContent-Length: 0\r\n\r\n"
        else:
            response = b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n"
        conn.sendall(response)
        conn.close()
    raise SystemExit(0)
'''


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def run_probe(
    tmp_path: Path,
    arguments: list[str] | None = None,
    **environment: str,
) -> subprocess.CompletedProcess[str]:
    hermes = tmp_path / "hermes"
    hermes.write_text(FAKE_HERMES, encoding="utf-8")
    hermes.chmod(0o755)
    env = os.environ.copy()
    env.update(environment)
    env["TMPDIR"] = str(tmp_path)
    return subprocess.run(
        [
            sys.executable,
            str(PROBE),
            "--hermes",
            str(hermes),
            "--port",
            str(_free_port()),
            *(arguments or []),
        ],
        cwd=PROBE.parents[1],
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )


def test_probe_discovers_dashboard_plugin_and_serves_assets(tmp_path: Path) -> None:
    result = run_probe(tmp_path)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["hermes"]["semver"] == "0.18.2"
    assert payload["hermes"]["build"] == "2026.7.7.2"
    assert payload["hermes"]["upstream"] == "4281151a"
    assert payload["plugin"]["tab"] == "/daidala"
    assert payload["plugin"]["slot"] == "sessions:top"
    assert payload["plugin"]["assets_served"] is True
    assert payload["plugin"]["api_mounted_and_auth_gated"] is True
    assert not list(tmp_path.glob("daidala-dashboard-compat-*"))


def test_probe_rejects_changed_supported_host_identity(tmp_path: Path) -> None:
    result = run_probe(tmp_path, FAKE_VERSION_MODE="changed")

    assert result.returncode == 1
    assert "unsupported Hermes identity" in result.stderr
    assert "0.19.0" in result.stderr
    assert not list(tmp_path.glob("daidala-dashboard-compat-*"))


def test_probe_accepts_one_complete_explicit_candidate_identity(tmp_path: Path) -> None:
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
    assert json.loads(result.stdout)["hermes"] == {
        "semver": "0.19.0",
        "build": "2026.7.20",
        "upstream": "3ef6bbd2",
    }


def test_probe_rejects_partial_explicit_candidate_identity(tmp_path: Path) -> None:
    result = run_probe(tmp_path, ["--expected-semver", "0.19.0"])

    assert result.returncode == 2
    assert "must be supplied together" in result.stderr
    assert not list(tmp_path.glob("daidala-dashboard-compat-*"))


def test_probe_rejects_missing_host_identity_fields(tmp_path: Path) -> None:
    result = run_probe(tmp_path, FAKE_VERSION_MODE="missing")

    assert result.returncode == 1
    assert "missing semantic, build, or upstream identity" in result.stderr
    assert not list(tmp_path.glob("daidala-dashboard-compat-*"))


def test_probe_rejects_manifest_drift(tmp_path: Path) -> None:
    fake_path = tmp_path / "fake-assets"
    fake_path.mkdir()
    (fake_path / "hermes").write_text(
        FAKE_HERMES.replace(
            '"name": "daidala", "label": "Daidala"',
            '"name": "renamed", "label": "Renamed"',
        ),
        encoding="utf-8",
    )
    (fake_path / "hermes").chmod(0o755)

    env = os.environ.copy()
    env["TMPDIR"] = str(tmp_path)
    env.pop("FAKE_VERSION_MODE", None)

    cmd = [
        sys.executable,
        str(PROBE),
        "--hermes",
        str(fake_path / "hermes"),
        "--port",
        str(_free_port()),
    ]
    result = subprocess.run(
        cmd,
        cwd=PROBE.parents[1],
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )

    assert result.returncode == 1
    assert "did not discover" in result.stderr
    assert not list(tmp_path.glob("daidala-dashboard-compat-*"))
