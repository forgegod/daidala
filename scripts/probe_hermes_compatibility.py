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
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from daidala.skills import ProfileSkillContentRegistry, hash_skill_directory

SUPPORTED_SEMVER = "0.20.0"
SUPPORTED_BUILD = "2026.8.3"
SUPPORTED_REVISION = "3c27eb6234bf91b8ceee9e9071591b31e9b148cb"
INTACT_BODY_CHARS = 8192
TRUNCATED_BODY_CHARS = 8300
VERSION_RE = re.compile(
    r"Hermes Agent v(?P<semver>\S+) \((?P<build>[^)]+)\)"
)
REVISION_RE = re.compile(r"[0-9a-f]{40}")


@dataclass(frozen=True)
class HostIdentity:
    semver: str
    build: str
    revision: str

    def to_dict(self) -> dict[str, str]:
        return {
            "semver": self.semver,
            "build": self.build,
            "revision": self.revision,
        }


SUPPORTED_HOST = HostIdentity(SUPPORTED_SEMVER, SUPPORTED_BUILD, SUPPORTED_REVISION)


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


def add_expected_host_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--expected-semver")
    parser.add_argument("--expected-build")
    parser.add_argument("--expected-revision")


def expected_host_from_args(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> HostIdentity:
    values = (args.expected_semver, args.expected_build, args.expected_revision)
    if any(value is None for value in values):
        if any(value is not None for value in values):
            parser.error(
                "--expected-semver, --expected-build, and --expected-revision "
                "must be supplied together"
            )
        return SUPPORTED_HOST
    return HostIdentity(*values)


def require_isolated_root(root: Path) -> None:
    active_home_value = os.environ.get("HERMES_HOME")
    if not active_home_value:
        return
    active_home = Path(active_home_value).expanduser().resolve()
    resolved_root = root.resolve()
    if resolved_root == active_home or active_home in resolved_root.parents:
        raise ProbeError("isolated probe root resolves inside the active HERMES_HOME")


def _read_revision(path: Path) -> str | None:
    try:
        revision = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return revision if REVISION_RE.fullmatch(revision) else None


def _executable_revision(executable: str, env: dict[str, str]) -> tuple[str, str]:
    resolved_value = shutil.which(executable, path=env.get("PATH")) or executable
    resolved = Path(resolved_value).expanduser().resolve(strict=True)
    for directory in resolved.parents:
        if not (directory / ".git").exists():
            continue
        result = subprocess.run(
            ["git", "-C", str(directory), "rev-parse", "HEAD"],
            capture_output=True,
            check=False,
            env=env,
            text=True,
        )
        revision = result.stdout.strip()
        if result.returncode == 0 and REVISION_RE.fullmatch(revision):
            return revision, "git-head"

    metadata_candidates = [resolved.parent / ".hermes_build_sha"]
    for python_name in ("python", "python3"):
        python = resolved.parent / python_name
        if not python.is_file() or not os.access(python, os.X_OK):
            continue
        result = subprocess.run(
            [
                str(python),
                "-c",
                "import sysconfig; print(sysconfig.get_path('purelib'))",
            ],
            capture_output=True,
            check=False,
            env=env,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            metadata_candidates.append(Path(result.stdout.strip()) / ".hermes_build_sha")
    for candidate in metadata_candidates:
        revision = _read_revision(candidate)
        if revision is not None:
            return revision, "build-metadata"
    raise ProbeError("Hermes executable has no local Git revision or build metadata")


def require_host_identity(
    output: str,
    executable: str,
    *,
    env: dict[str, str],
    expected: HostIdentity = SUPPORTED_HOST,
) -> dict[str, str]:
    match = VERSION_RE.search(output)
    if match is None:
        raise ProbeError("Hermes version output is missing semantic or build identity")
    revision, revision_source = _executable_revision(executable, env)
    observed = {**match.groupdict(), "revision": revision}
    expected_dict = expected.to_dict()
    if observed != expected_dict:
        raise ProbeError(
            f"unsupported Hermes identity: expected {expected_dict}, observed {observed}"
        )
    return {**observed, "revision_source": revision_source}


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


def exercise(
    root: Path, hermes: str, expected_host: HostIdentity = SUPPORTED_HOST
) -> dict[str, Any]:
    require_isolated_root(root)
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

    version = require_host_identity(
        run([hermes, "--version"], env=env),
        hermes,
        env=env,
        expected=expected_host,
    )
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
    add_expected_host_arguments(parser)
    args = parser.parse_args(argv)
    expected_host = expected_host_from_args(parser, args)
    root = Path(tempfile.mkdtemp(prefix="daidala-hermes-compat-"))
    try:
        result = exercise(root, args.hermes, expected_host)
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
