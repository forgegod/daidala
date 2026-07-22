#!/usr/bin/env python3
"""Probe packaged Daidala plugin loading through public Hermes CLI surfaces."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from probe_hermes_compatibility import (
    SUPPORTED_HOST,
    HostIdentity,
    ProbeError,
    add_expected_host_arguments,
    expected_host_from_args,
    parse_json,
    require_isolated_root,
    require_version,
    run,
)

PACKS = ("addyosmani", "aidlc")
PLUGIN_NAME = "daidala"
PLUGIN_VERSION = "0.2.0"


def _prepare_home(home: Path, plugin_directory: Path | None) -> None:
    home.mkdir(parents=True)
    (home / "config.yaml").write_text(
        "plugins:\n  enabled:\n    - daidala\n",
        encoding="utf-8",
    )
    if plugin_directory is None:
        return
    source = plugin_directory.expanduser().resolve()
    if not (source / "plugin.yaml").is_file() or not (source / "__init__.py").is_file():
        raise ProbeError("plugin directory must contain plugin.yaml and __init__.py")
    destination = home / "plugins" / PLUGIN_NAME
    destination.parent.mkdir(parents=True)
    destination.symlink_to(source, target_is_directory=True)


def _plugin_inventory(hermes: str, env: dict[str, str]) -> dict[str, Any] | None:
    payload = parse_json(
        run([hermes, "plugins", "list", "--enabled", "--json"], env=env),
        "enabled plugin inventory",
    )
    if not isinstance(payload, list):
        raise ProbeError("enabled plugin inventory is not a JSON list")
    plugin = next(
        (item for item in payload if isinstance(item, dict) and item.get("name") == PLUGIN_NAME),
        None,
    )
    if plugin is None:
        return None
    if plugin.get("status") != "enabled":
        raise ProbeError(f"Daidala plugin is not enabled: {plugin.get('status')!r}")
    if plugin.get("version") != PLUGIN_VERSION:
        raise ProbeError(
            f"Daidala plugin version drifted: expected {PLUGIN_VERSION}, "
            f"observed {plugin.get('version')!r}"
        )
    return plugin


def _validate_pack(command: list[str], env: dict[str, str], label: str) -> dict[str, Any]:
    payload = parse_json(run(command, env=env), label)
    if not isinstance(payload, dict) or payload.get("success") is not True:
        raise ProbeError(f"{label} did not return a successful pack result")
    return payload


def exercise(
    root: Path,
    hermes: str,
    daidala: str,
    expected_host: HostIdentity = SUPPORTED_HOST,
    plugin_directory: Path | None = None,
) -> dict[str, Any]:
    require_isolated_root(root)
    home = root / "home"
    _prepare_home(home, plugin_directory)
    env = os.environ.copy()
    env["HERMES_HOME"] = str(home)
    env.pop("HERMES_PROFILE", None)

    version = require_version(run([hermes, "--version"], env=env), expected_host)
    plugin = _plugin_inventory(hermes, env)
    packs: dict[str, dict[str, Any]] = {}
    for pack in PACKS:
        native = _validate_pack(
            [hermes, PLUGIN_NAME, "packs", "validate", pack],
            env,
            f"native {pack} validation",
        )
        standalone = _validate_pack(
            [daidala, "packs", "validate", pack],
            env,
            f"standalone {pack} validation",
        )
        if native != standalone:
            raise ProbeError(f"native and standalone {pack} validation differ")
        packs[pack] = native

    return {
        "success": True,
        "hermes": version,
        "plugin": {
            "name": PLUGIN_NAME,
            "version": PLUGIN_VERSION,
            "reported": plugin is not None,
            "source": plugin.get("source") if plugin else None,
            "status": plugin.get("status") if plugin else None,
            "discovery": "directory" if plugin_directory else "entrypoint",
        },
        "cli": {
            "native_command": PLUGIN_NAME,
            "standalone_command": Path(daidala).name,
            "packs": packs,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hermes", default="hermes", help="Hermes executable to probe")
    parser.add_argument("--daidala", default="daidala", help="Daidala executable to compare")
    parser.add_argument(
        "--plugin-directory",
        type=Path,
        help="Optional directory-plugin source; omit to probe the installed entry point",
    )
    parser.add_argument("--keep-temp", action="store_true", help="Keep the isolated probe root")
    add_expected_host_arguments(parser)
    args = parser.parse_args(argv)
    expected_host = expected_host_from_args(parser, args)
    root = Path(tempfile.mkdtemp(prefix="daidala-plugin-compat-"))
    try:
        result = exercise(
            root,
            args.hermes,
            args.daidala,
            expected_host,
            args.plugin_directory,
        )
        if args.keep_temp:
            result["probe_root"] = str(root)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ProbeError, ValueError, json.JSONDecodeError) as error:
        print(f"Hermes plugin compatibility probe failed: {error}", file=sys.stderr)
        return 1
    finally:
        if not args.keep_temp:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
