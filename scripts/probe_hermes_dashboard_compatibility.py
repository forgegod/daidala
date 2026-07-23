#!/usr/bin/env python3
"""Probe Daidala's supported Hermes dashboard extension boundary in isolation."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from probe_hermes_compatibility import (
    SUPPORTED_HOST,
    HostIdentity,
    ProbeError,
    add_expected_host_arguments,
    expected_host_from_args,
    require_isolated_root,
    require_version,
    run,
)

SDK_VERSION = "1.1.0"
TAB_PATH = "/daidala"
SLOT = "sessions:top"


def _request(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    token: str | None = None,
) -> tuple[int, str]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"} if data is not None else {}
    if token is not None:
        headers["X-Hermes-Session-Token"] = token
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8")


def _packaged_dashboard() -> Path:
    spec = importlib.util.find_spec("dashboard")
    if spec is None or spec.submodule_search_locations is None:
        raise ProbeError("installed Daidala wheel does not contain the dashboard package")
    dashboard = Path(next(iter(spec.submodule_search_locations))).resolve()
    required = (
        dashboard / "manifest.json",
        dashboard / "plugin_api.py",
        dashboard / "dist" / "index.js",
        dashboard / "dist" / "style.css",
    )
    if any(not path.is_file() for path in required):
        raise ProbeError("installed Daidala dashboard package is incomplete")
    return dashboard


def _write_probe_plugin(home: Path) -> Path:
    packaged = _packaged_dashboard()
    dashboard = home / "plugins" / "daidala" / "dashboard"
    dashboard.parent.mkdir(parents=True)
    shutil.copytree(packaged, dashboard)
    (home / "config.yaml").write_text(
        "plugins:\n  enabled:\n    - daidala\n", encoding="utf-8"
    )
    (dashboard.parent / "plugin.yaml").write_text(
        "name: daidala\nversion: 0.2.0\ndescription: Dashboard compatibility probe\n",
        encoding="utf-8",
    )
    return dashboard


def _setup_payload(root: Path) -> dict[str, Any]:
    return {
        "board_slug": "daidala-compat",
        "target_repository": str(root / "target"),
        "goal": "Verify packaged setup preview without mutation.",
        "stage_profiles": {
            stage: f"probe-{stage}"
            for stage in ("define", "plan", "implement", "verify", "review", "deliver")
        },
        "pack": "addyosmani",
        "workflow_id": "compat-preview",
        "constraints_content": "global:\n  - Keep the preview read-only.\n",
    }


def exercise(
    root: Path,
    hermes: str,
    port: int,
    expected_host: HostIdentity = SUPPORTED_HOST,
) -> dict[str, Any]:
    require_isolated_root(root)
    home = root / "home"
    dashboard = _write_probe_plugin(home)
    env = os.environ.copy()
    env["HERMES_HOME"] = str(home)
    session_token = "daidala-compat-session"
    env["HERMES_DASHBOARD_SESSION_TOKEN"] = session_token
    env.pop("HERMES_PROFILE", None)
    version = require_version(run([hermes, "--version"], env=env), expected_host)
    process = subprocess.Popen(
        [
            hermes,
            "dashboard",
            "--isolated",
            "--no-open",
            "--skip-build",
            "--port",
            str(port),
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                status, _ = _request(f"{base}/api/dashboard/plugins")
                if status == 200:
                    break
            except OSError:
                pass
            if process.poll() is not None:
                output = process.stdout.read() if process.stdout else ""
                raise ProbeError(f"dashboard exited before readiness: {output.strip()}")
            time.sleep(0.2)
        else:
            raise ProbeError("dashboard did not become ready within 30 seconds")

        status, body = _request(f"{base}/api/dashboard/plugins")
        manifests = json.loads(body)
        plugin = next((item for item in manifests if item.get("name") == "daidala"), None)
        if status != 200 or plugin is None:
            raise ProbeError("dashboard did not discover the Daidala manifest")
        if plugin.get("tab", {}).get("path") != TAB_PATH or plugin.get("slots") != [SLOT]:
            raise ProbeError("dashboard changed the Daidala tab or slot registration")
        asset_digests: dict[str, str] = {}
        for asset in ("manifest.json", "dist/index.js", "dist/style.css"):
            asset_status, asset_body = _request(f"{base}/dashboard-plugins/daidala/{asset}")
            if asset_status != 200:
                raise ProbeError(f"dashboard asset was not served: {asset}")
            expected_body = (dashboard / asset).read_text(encoding="utf-8")
            if asset_body != expected_body:
                raise ProbeError(f"dashboard did not serve packaged asset bytes: {asset}")
            asset_digests[asset] = hashlib.sha256(asset_body.encode("utf-8")).hexdigest()
        health_status, _ = _request(f"{base}/api/plugins/daidala/health")
        if health_status != 401:
            raise ProbeError(
                f"plugin API auth boundary drifted: expected 401, observed {health_status}"
            )
        state_paths = (home / "daidala", home / "kanban", home / "kanban.db")
        if any(path.exists() for path in state_paths):
            raise ProbeError("dashboard created workflow or Kanban state before setup preview")
        setup = _setup_payload(root)
        preview_status, preview_body = _request(
            f"{base}/api/plugins/daidala/wizard/preview",
            method="POST",
            payload=setup,
            token=session_token,
        )
        preview = json.loads(preview_body)
        expected_request = {
            **setup,
            "pack_name": setup["pack"],
            "constraints_content": setup["constraints_content"].strip(),
            "constraints_skill": None,
            "constraints_skill_digest": None,
        }
        if (
            preview_status != 200
            or preview.get("confirmed") is not False
            or preview.get("request") != expected_request
        ):
            detail = json.dumps(
                {
                    "status": preview_status,
                    "observed": preview,
                    "expected_request": expected_request,
                },
                sort_keys=True,
            )
            raise ProbeError(f"packaged setup preview contract drifted: {detail}")
        start_status, start_body = _request(
            f"{base}/api/plugins/daidala/wizard/start",
            method="POST",
            payload=setup,
            token=session_token,
        )
        if start_status != 400 or "explicit confirmation is required" not in start_body:
            raise ProbeError("unconfirmed packaged setup did not fail closed")
        if any(path.exists() for path in state_paths):
            raise ProbeError("preview or unconfirmed setup mutated workflow or Kanban state")
        return {
            "success": True,
            "hermes": version,
            "sdk_version": SDK_VERSION,
            "plugin": {
                "source": plugin.get("source"),
                "tab": TAB_PATH,
                "slot": SLOT,
                "assets_served": True,
                "asset_digests": asset_digests,
                "packaged_router": True,
                "api_mounted_and_auth_gated": True,
            },
            "setup": {
                "preview_confirmed": False,
                "unconfirmed_start_status": 400,
                "state_unchanged": True,
            },
            "browser_assertions": {
                "sdk_global": f"window.__HERMES_PLUGIN_SDK__.sdkVersion == {SDK_VERSION!r}",
                "tab_test_id": "daidala-phase0",
                "slot_test_id": "daidala-slot",
            },
        }
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hermes", default="hermes", help="Hermes executable to probe")
    parser.add_argument("--port", default=9120, type=int, help="Isolated dashboard port")
    parser.add_argument("--keep-temp", action="store_true", help="Keep the isolated probe root")
    add_expected_host_arguments(parser)
    args = parser.parse_args(argv)
    expected_host = expected_host_from_args(parser, args)
    root = Path(tempfile.mkdtemp(prefix="daidala-dashboard-compat-"))
    try:
        result = exercise(root, args.hermes, args.port, expected_host)
        if args.keep_temp:
            result["probe_root"] = str(root)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ProbeError, ValueError, json.JSONDecodeError) as error:
        print(f"Hermes dashboard compatibility probe failed: {error}", file=sys.stderr)
        return 1
    finally:
        if not args.keep_temp:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
