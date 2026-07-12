#!/usr/bin/env python3
"""Probe Wingstaff's supported Hermes dashboard extension boundary in isolation."""

from __future__ import annotations

import argparse
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

from probe_hermes_compatibility import ProbeError, require_version, run

SDK_VERSION = "1.1.0"
TAB_PATH = "/wingstaff"
SLOT = "sessions:top"


def _request(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8")


def _write_probe_plugin(home: Path) -> None:
    dashboard = home / "plugins" / "wingstaff" / "dashboard"
    (dashboard / "dist").mkdir(parents=True)
    (home / "config.yaml").write_text(
        "plugins:\n  enabled:\n    - wingstaff\n", encoding="utf-8"
    )
    (dashboard.parent / "plugin.yaml").write_text(
        "name: wingstaff\nversion: 0.1.0\ndescription: Dashboard compatibility probe\n",
        encoding="utf-8",
    )
    manifest = {
        "name": "wingstaff",
        "label": "Wingstaff",
        "version": "0.1.0",
        "tab": {"path": TAB_PATH, "position": "after:kanban"},
        "slots": [SLOT],
        "entry": "dist/index.js",
        "css": "dist/style.css",
        "api": "plugin_api.py",
    }
    (dashboard / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (dashboard / "dist" / "index.js").write_text(
        '(function(){"use strict";const SDK=window.__HERMES_PLUGIN_SDK__;'
        'const React=SDK.React;function Page(){return React.createElement("main",'
        '{"data-testid":"wingstaff-phase0"},React.createElement("h1",null,'
        '"Wingstaff Phase 0"));}function Slot(){return React.createElement("div",'
        '{"data-testid":"wingstaff-slot"},"Wingstaff decisions: 0");}'
        'window.__HERMES_PLUGINS__.register("wingstaff",Page);'
        f'window.__HERMES_PLUGINS__.registerSlot("wingstaff","{SLOT}",Slot);}})();',
        encoding="utf-8",
    )
    (dashboard / "dist" / "style.css").write_text(
        '[data-testid="wingstaff-phase0"] { padding: 2rem; }\n', encoding="utf-8"
    )
    (dashboard / "plugin_api.py").write_text(
        'from fastapi import APIRouter\nrouter = APIRouter()\n'
        '@router.get("/health")\ndef health():\n'
        '    return {"success": True, "plugin": "wingstaff"}\n',
        encoding="utf-8",
    )


def exercise(root: Path, hermes: str, port: int) -> dict[str, Any]:
    home = root / "home"
    _write_probe_plugin(home)
    env = os.environ.copy()
    env["HERMES_HOME"] = str(home)
    env.pop("HERMES_PROFILE", None)
    version = require_version(run([hermes, "--version"], env=env))
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
        plugin = next((item for item in manifests if item.get("name") == "wingstaff"), None)
        if status != 200 or plugin is None:
            raise ProbeError("dashboard did not discover the Wingstaff manifest")
        if plugin.get("tab", {}).get("path") != TAB_PATH or plugin.get("slots") != [SLOT]:
            raise ProbeError("dashboard changed the Wingstaff tab or slot registration")
        for asset in ("manifest.json", "dist/index.js", "dist/style.css"):
            asset_status, _ = _request(f"{base}/dashboard-plugins/wingstaff/{asset}")
            if asset_status != 200:
                raise ProbeError(f"dashboard asset was not served: {asset}")
        health_status, _ = _request(f"{base}/api/plugins/wingstaff/health")
        if health_status != 401:
            raise ProbeError(
                f"plugin API auth boundary drifted: expected 401, observed {health_status}"
            )
        return {
            "success": True,
            "hermes": version,
            "sdk_version": SDK_VERSION,
            "plugin": {
                "source": plugin.get("source"),
                "tab": TAB_PATH,
                "slot": SLOT,
                "assets_served": True,
                "api_mounted_and_auth_gated": True,
            },
            "browser_assertions": {
                "sdk_global": f"window.__HERMES_PLUGIN_SDK__.sdkVersion == {SDK_VERSION!r}",
                "tab_test_id": "wingstaff-phase0",
                "slot_test_id": "wingstaff-slot",
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
    args = parser.parse_args(argv)
    root = Path(tempfile.mkdtemp(prefix="wingstaff-dashboard-compat-"))
    try:
        result = exercise(root, args.hermes, args.port)
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
