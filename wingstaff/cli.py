"""Standalone Wingstaff diagnostics and pack-dependency CLI."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections.abc import Callable
from typing import cast

from .locations import resolve_data_root
from .packs import PackError, load_pack
from .skills import (
    PackInstallPlan,
    ProfileSkillContentRegistry,
    SkillContentRegistry,
    SkillInventory,
    plan_pack_install,
)

CommandRunner = Callable[[tuple[str, ...]], tuple[int, str]]
RevisionResolver = Callable[[str], str]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wingstaff")
    sub = parser.add_subparsers(dest="command", required=True)
    packs = sub.add_parser("packs", help="Inspect workflow packs")
    packs_sub = packs.add_subparsers(dest="packs_command", required=True)

    validate = packs_sub.add_parser("validate", help="Validate a bundled pack")
    validate.add_argument("name")

    install = packs_sub.add_parser(
        "install", help="Plan or apply pinned external skill installation"
    )
    install.add_argument("name")
    install.add_argument(
        "--apply", action="store_true", help="Apply the displayed missing-skill mutations"
    )
    install.add_argument(
        "--recursive",
        action="store_true",
        help="Request recursive installation when the host supports it",
    )

    check = packs_sub.add_parser(
        "check", help="Check installed skill names, content, source, and host version"
    )
    check.add_argument("name")

    update_plan = packs_sub.add_parser(
        "update-plan", help="Plan controlled changes without mutating installed skills"
    )
    update_plan.add_argument("name")
    return parser


def main(
    argv: list[str] | None = None,
    *,
    inventory: SkillInventory | None = None,
    registry: SkillContentRegistry | None = None,
    revision_resolver: RevisionResolver | None = None,
    hermes_version: str | None = None,
    command_runner: CommandRunner | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    try:
        pack = load_pack(args.name)
    except PackError as exc:
        _print({"success": False, "error": str(exc)})
        return 1

    if args.packs_command == "validate":
        _print(
            {
                "success": True,
                "pack": pack.name,
                "source": pack.source,
                "source_revision": pack.source_revision,
                "lifecycle": list(pack.lifecycle),
                "human_gate_after": pack.human_gate_after,
            }
        )
        return 0

    selected_registry = registry or ProfileSkillContentRegistry(
        resolve_data_root() / "skills"
    )
    selected_inventory = inventory or cast(SkillInventory, selected_registry)
    resolver = revision_resolver or _resolve_revision
    version = hermes_version or _resolve_hermes_version()
    try:
        plan = plan_pack_install(
            pack,
            selected_inventory,
            selected_registry,
            resolved_revision=resolver(pack.source),
            hermes_version=version,
            recursive=getattr(args, "recursive", False),
        )
    except Exception as exc:  # noqa: BLE001 - host command/registry boundary
        _print({"success": False, "error": type(exc).__name__, "message": str(exc)})
        return 1

    if args.packs_command == "install":
        if not args.apply:
            _print(
                _plan_payload(
                    plan,
                    operation="install",
                    dry_run=True,
                    success=plan.ready_to_apply,
                )
            )
            return 0 if plan.ready_to_apply else 1
        if not plan.ready_to_apply:
            _print(_plan_payload(plan, operation="install", dry_run=False, success=False))
            return 1
        runner = command_runner or _run_command
        executed: list[dict[str, object]] = []
        for action in plan.actions:
            code, output = runner(action.command)
            executed.append(
                {
                    "name": action.name,
                    "command": list(action.command),
                    "exit_code": code,
                    "output": output,
                }
            )
            if code != 0:
                payload = _plan_payload(
                    plan, operation="install", dry_run=False, success=False
                )
                payload["executed"] = executed
                _print(payload)
                return 1
        verified = plan_pack_install(
            pack,
            selected_inventory,
            selected_registry,
            resolved_revision=resolver(pack.source),
            hermes_version=version,
        )
        success = verified.ready_to_apply and not verified.actions
        payload = _plan_payload(
            verified, operation="install", dry_run=False, success=success
        )
        payload["executed"] = executed
        _print(payload)
        return 0 if success else 1

    if args.packs_command == "check":
        success = plan.ready_to_apply and not plan.actions
        _print(_plan_payload(plan, operation="check", dry_run=True, success=success))
        return 0 if success else 1

    _print(_plan_payload(plan, operation="update-plan", dry_run=True, success=True))
    return 0


def _plan_payload(
    plan: PackInstallPlan, *, operation: str, dry_run: bool, success: bool
) -> dict[str, object]:
    return {
        "success": success,
        "operation": operation,
        "dry_run": dry_run,
        **plan.to_dict(),
    }


def _resolve_revision(source: str) -> str:
    completed = subprocess.run(
        ["git", "ls-remote", source, "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    revision = completed.stdout.strip().split("\t", 1)[0]
    if completed.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", revision):
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown error"
        raise RuntimeError(f"could not resolve {source} HEAD: {detail}")
    return revision


def _resolve_hermes_version() -> str:
    code, output = _run_command(("hermes", "--version"))
    match = re.search(r"Hermes Agent v(\d+\.\d+\.\d+)", output)
    if code != 0 or match is None:
        raise RuntimeError("could not resolve Hermes semantic version")
    return match.group(1)


def _run_command(command: tuple[str, ...]) -> tuple[int, str]:
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    output = completed.stdout
    if completed.stderr:
        output += completed.stderr
    return completed.returncode, output.strip()


def _print(payload: dict[str, object]) -> None:
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
