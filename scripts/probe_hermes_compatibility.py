#!/usr/bin/env python3
"""Probe Daidala's supported Hermes compatibility boundary in isolation."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from daidala.skills import ProfileSkillContentRegistry, hash_skill_directory

SUPPORTED_SEMVER = "0.18.2"
SUPPORTED_BUILD = "2026.7.7.2"
SUPPORTED_UPSTREAM = "4281151a"
INTACT_BODY_CHARS = 8192
TRUNCATED_BODY_CHARS = 8300
VERSION_RE = re.compile(
    r"Hermes Agent v(?P<semver>\S+) \((?P<build>[^)]+)\) · upstream (?P<upstream>[0-9a-f]+)"
)


class ProbeError(RuntimeError):
    """Compatibility evidence was missing, changed, or malformed."""


def run(command: list[str], *, env: dict[str, str]) -> str:
    result = subprocess.run(command, capture_output=True, check=False, env=env, text=True)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "no output"
        raise ProbeError(f"command failed ({result.returncode}): {' '.join(command)}\n{detail}")
    return result.stdout


def parse_json(output: str, label: str) -> Any:
    try:
        return json.loads(output)
    except json.JSONDecodeError as error:
        raise ProbeError(f"{label} did not return valid JSON: {error}") from error


def require_version(output: str) -> dict[str, str]:
    match = VERSION_RE.search(output)
    if match is None:
        raise ProbeError("Hermes version output is missing semantic, build, or upstream identity")
    observed = match.groupdict()
    expected = {
        "semver": SUPPORTED_SEMVER,
        "build": SUPPORTED_BUILD,
        "upstream": SUPPORTED_UPSTREAM,
    }
    if observed != expected:
        raise ProbeError(f"unsupported Hermes identity: expected {expected}, observed {observed}")
    return observed


def create_task(
    hermes: str,
    board: str,
    title: str,
    body: str,
    *,
    env: dict[str, str],
) -> str:
    output = run(
        [hermes, "kanban", "--board", board, "create", title, "--body", body, "--json"],
        env=env,
    )
    payload = parse_json(output, f"create {title}")
    task_id = payload.get("id") if isinstance(payload, dict) else None
    if not isinstance(task_id, str) or not task_id:
        raise ProbeError(f"create {title} JSON is missing a task id")
    return task_id


def exercise(root: Path, hermes: str) -> dict[str, Any]:
    home = root / "home"
    skill = home / "skills" / "policy-probe"
    skill.mkdir(parents=True)
    markdown = (
        "---\nname: policy-probe\ndescription: Compatibility probe policy.\n---\n"
        "```yaml\nschema: daidala.workflow-constraints/v1\nglobal:\n"
        "  - Never push.\n```\n"
    )
    (skill / "SKILL.md").write_text(markdown, encoding="utf-8")
    env = os.environ.copy()
    env["HERMES_HOME"] = str(home)
    env.pop("HERMES_PROFILE", None)

    version = require_version(run([hermes, "--version"], env=env))
    registry = ProfileSkillContentRegistry(home / "skills")
    installed = sorted(registry.installed_names())
    if installed != ["policy-probe"]:
        raise ProbeError(
            f"exact skill inventory drifted: expected ['policy-probe'], observed {installed}"
        )
    digest = registry.content_digest("policy-probe")
    if digest is None:
        raise ProbeError("policy skill registry did not resolve the exact installed name")
    if digest != hash_skill_directory(skill):
        raise ProbeError("policy skill registry digest disagrees with Daidala directory hashing")
    if len(digest) != 64:
        raise ProbeError("policy skill directory digest is not SHA-256")

    board = "daidala-compatibility"
    run([hermes, "kanban", "boards", "create", board, "--name", "Daidala compatibility"], env=env)
    run([hermes, "kanban", "--board", board, "init"], env=env)

    parent = create_task(hermes, board, "compat-parent", "parent", env=env)
    child = create_task(hermes, board, "compat-child", "child", env=env)
    run([hermes, "kanban", "--board", board, "link", parent, child], env=env)
    run([hermes, "kanban", "--board", board, "comment", parent, "compatibility-comment"], env=env)
    shown = parse_json(
        run([hermes, "kanban", "--board", board, "show", parent, "--json"], env=env),
        "show parent",
    )
    shown_task = shown.get("task") if isinstance(shown, dict) else None
    if not isinstance(shown_task, dict) or shown_task.get("id") != parent:
        raise ProbeError("show output did not preserve the created parent identity")
    run([hermes, "kanban", "--board", board, "complete", parent], env=env)
    run([hermes, "kanban", "--board", board, "complete", child], env=env)
    run([hermes, "kanban", "--board", board, "archive", parent, child], env=env)

    intact = "A" * INTACT_BODY_CHARS
    oversized = "B" * TRUNCATED_BODY_CHARS
    intact_id = create_task(hermes, board, "compat-intact", intact, env=env)
    oversized_id = create_task(hermes, board, "compat-truncated", oversized, env=env)
    intact_context = run([hermes, "kanban", "--board", board, "context", intact_id], env=env)
    oversized_context = run(
        [hermes, "kanban", "--board", board, "context", oversized_id], env=env
    )
    if intact not in intact_context:
        raise ProbeError(f"{INTACT_BODY_CHARS}-character body was not preserved in worker context")
    if oversized in oversized_context or "truncat" not in oversized_context.lower():
        raise ProbeError(f"{TRUNCATED_BODY_CHARS}-character body was not visibly truncated")

    return {
        "success": True,
        "hermes": version,
        "skill": {"name": "policy-probe", "digest": digest},
        "kanban": {
            "board": board,
            "operations": ["create", "show", "comment", "link", "complete", "archive"],
        },
        "worker_context": {"intact": INTACT_BODY_CHARS, "truncated": TRUNCATED_BODY_CHARS},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hermes", default="hermes", help="Hermes executable to probe")
    parser.add_argument("--keep-temp", action="store_true", help="Keep the isolated probe root")
    args = parser.parse_args(argv)
    root = Path(tempfile.mkdtemp(prefix="daidala-hermes-compat-"))
    try:
        result = exercise(root, args.hermes)
        if args.keep_temp:
            result["probe_root"] = str(root)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ProbeError) as error:
        print(f"Hermes compatibility probe failed: {error}", file=sys.stderr)
        return 1
    finally:
        if not args.keep_temp:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
