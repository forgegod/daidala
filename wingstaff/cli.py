"""Shared standalone and Hermes-native Wingstaff operator CLI."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
from collections.abc import Callable
from importlib import resources
from typing import NoReturn, cast

from .kanban import KanbanGraphAdapter
from .locations import resolve_data_root
from .packs import PackError, load_pack
from .service import WorkflowService
from .skills import (
    PackInstallPlan,
    ProfileSkillContentRegistry,
    SkillContentRegistry,
    SkillInventory,
    plan_pack_install,
)
from .state import WorkflowStage
from .store import WorkflowStore

CommandRunner = Callable[[tuple[str, ...]], tuple[int, str]]
RevisionResolver = Callable[[str], str]
ServiceFactory = Callable[[], WorkflowService]


def register_cli(parser: argparse.ArgumentParser) -> None:
    """Register the command tree shared by ``wingstaff`` and ``hermes wingstaff``."""
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Preview or initialize the profile-local policy ledger")
    init.add_argument("--apply", action="store_true", help="Create the ledger directory and schema")

    doctor = sub.add_parser("doctor", help="Check host, pack, and installed skill readiness")
    doctor.add_argument("--pack", default="addyosmani")

    start = sub.add_parser("start", help="Validate inputs and create the initial Kanban graph")
    start.add_argument("target_repository")
    start.add_argument("goal")
    start.add_argument("--board", required=True, dest="board_slug")
    start.add_argument(
        "--default-profile",
        dest="profile",
        required=True,
        help="Default existing Hermes profile for every executable stage",
    )
    start.add_argument(
        "--stage-profile",
        action="append",
        default=[],
        metavar="STAGE=PROFILE",
        help="Override the default profile for one executable stage (repeatable)",
    )
    start.add_argument("--pack", default="addyosmani")
    start.add_argument("--workflow-id", required=True)

    status = sub.add_parser(
        "status", help="Show Wingstaff policy facts and live Kanban card status"
    )
    status.add_argument("workflow_id")

    approve = sub.add_parser("approve", help="Approve the exact current plan digest")
    approve.add_argument("workflow_id")
    approve.add_argument("plan_digest")

    cancel = sub.add_parser(
        "cancel", help="Archive workflow cards and clean the Wingstaff-owned worktree"
    )
    cancel.add_argument("workflow_id")
    cancel.add_argument("reason")

    packs = sub.add_parser("packs", help="Inspect or install workflow-pack dependencies")
    packs_sub = packs.add_subparsers(dest="packs_command", required=True)
    packs_sub.add_parser("list", help="List bundled workflow packs")

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


def build_parser(*, prog: str = "wingstaff") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog)
    register_cli(parser)
    return parser


def dispatch_cli(args: argparse.Namespace) -> NoReturn:
    """Hermes callback that preserves process exit codes on the v0.18.2 host."""
    # Hermes v0.18.2 invokes plugin callbacks but discards their return values.
    # SystemExit is therefore the only argparse-compatible process-code boundary.
    raise SystemExit(run_command(args))


def main(
    argv: list[str] | None = None,
    *,
    inventory: SkillInventory | None = None,
    registry: SkillContentRegistry | None = None,
    revision_resolver: RevisionResolver | None = None,
    hermes_version: str | None = None,
    command_runner: CommandRunner | None = None,
    service_factory: ServiceFactory | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    return run_command(
        args,
        inventory=inventory,
        registry=registry,
        revision_resolver=revision_resolver,
        hermes_version=hermes_version,
        command_runner=command_runner,
        service_factory=service_factory,
    )


def run_command(
    args: argparse.Namespace,
    *,
    inventory: SkillInventory | None = None,
    registry: SkillContentRegistry | None = None,
    revision_resolver: RevisionResolver | None = None,
    hermes_version: str | None = None,
    command_runner: CommandRunner | None = None,
    service_factory: ServiceFactory | None = None,
) -> int:
    """Execute one parsed command and return its process exit code."""
    try:
        if args.command == "init":
            return _run_init(args)
        if args.command == "doctor":
            return _run_pack_operation(
                argparse.Namespace(command="packs", packs_command="check", name=args.pack),
                inventory=inventory,
                registry=registry,
                revision_resolver=revision_resolver,
                hermes_version=hermes_version,
                command_runner=command_runner,
                operation="doctor",
            )
        if args.command in {"start", "status", "approve", "cancel"}:
            selected_factory = service_factory or (
                lambda: _default_service(command_runner=command_runner)
            )
            return _run_lifecycle(args, selected_factory)
        if args.command == "packs":
            return _run_pack_operation(
                args,
                inventory=inventory,
                registry=registry,
                revision_resolver=revision_resolver,
                hermes_version=hermes_version,
                command_runner=command_runner,
            )
        raise ValueError(f"unsupported command: {args.command}")
    except Exception as exc:  # noqa: BLE001 - process boundary
        _print({"success": False, "error": type(exc).__name__, "message": str(exc)})
        return 1


def _run_init(args: argparse.Namespace) -> int:
    data_root = resolve_data_root() / "wingstaff"
    if not args.apply:
        _print(
            {
                "success": True,
                "operation": "init",
                "dry_run": True,
                "data_root": str(data_root),
            }
        )
        return 0
    store = WorkflowStore(data_root)
    _print(
        {
            "success": True,
            "operation": "init",
            "dry_run": False,
            "data_root": str(store.data_root),
            "database": str(store.db_path),
        }
    )
    return 0


def _run_lifecycle(args: argparse.Namespace, service_factory: ServiceFactory) -> int:
    service = service_factory()
    if args.command == "start":
        state = service.start(
            board_slug=args.board_slug,
            target_repository=args.target_repository,
            goal=args.goal,
            stage_profiles=_parse_stage_profiles(args.profile, args.stage_profile),
            pack_name=args.pack,
            workflow_id=args.workflow_id,
        )

    elif args.command == "status":
        state = service.status(args.workflow_id)
        _print(
            {
                "success": True,
                "operation": args.command,
                "workflow": state.to_dict(),
                "kanban": [
                    row.to_dict() for row in service.combined_status(args.workflow_id)
                ],
            }
        )
        return 0
    elif args.command == "approve":
        state = service.approve(args.workflow_id, plan_digest=args.plan_digest)
    else:
        state = service.cancel(args.workflow_id, reason=args.reason)
    _print({"success": True, "operation": args.command, "workflow": state.to_dict()})
    return 0


def _parse_stage_profiles(default_profile: str, values: list[str]) -> dict[str, str]:
    executable = {
        stage.value for stage in WorkflowStage if stage is not WorkflowStage.APPROVAL
    }
    mapping = {stage: default_profile for stage in executable}
    overridden: set[str] = set()
    for value in values:
        stage, separator, profile = value.partition("=")
        if not separator or not stage.strip() or not profile.strip():
            raise ValueError("--stage-profile must use STAGE=PROFILE")
        if stage not in executable:
            raise ValueError(f"unknown --stage-profile stage: {stage}")
        if stage in overridden:
            raise ValueError(f"duplicate --stage-profile stage: {stage}")
        mapping[stage] = profile
        overridden.add(stage)
    return mapping


def _run_pack_operation(
    args: argparse.Namespace,
    *,
    inventory: SkillInventory | None,
    registry: SkillContentRegistry | None,
    revision_resolver: RevisionResolver | None,
    hermes_version: str | None,
    command_runner: CommandRunner | None,
    operation: str | None = None,
) -> int:
    if args.packs_command == "list":
        names = _bundled_pack_names()
        _print({"success": True, "operation": "list", "packs": names})
        return 0

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

    selected_registry = registry or ProfileSkillContentRegistry(resolve_data_root() / "skills")
    selected_inventory = inventory or cast(SkillInventory, selected_registry)
    resolver = revision_resolver or _resolve_revision
    version = hermes_version or _resolve_hermes_version()
    plan = plan_pack_install(
        pack,
        selected_inventory,
        selected_registry,
        resolved_revision=resolver(pack.source),
        hermes_version=version,
        recursive=getattr(args, "recursive", False),
    )

    selected_operation = operation or args.packs_command
    if args.packs_command == "install":
        if not args.apply:
            _print(
                _plan_payload(
                    plan,
                    operation=selected_operation,
                    dry_run=True,
                    success=plan.ready_to_apply,
                )
            )
            return 0 if plan.ready_to_apply else 1
        if not plan.ready_to_apply:
            _print(
                _plan_payload(
                    plan, operation=selected_operation, dry_run=False, success=False
                )
            )
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
                    plan, operation=selected_operation, dry_run=False, success=False
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
            verified, operation=selected_operation, dry_run=False, success=success
        )
        payload["executed"] = executed
        _print(payload)
        return 0 if success else 1

    success = plan.ready_to_apply and not plan.actions
    _print(
        _plan_payload(
            plan,
            operation=selected_operation,
            dry_run=True,
            success=True if args.packs_command == "update-plan" else success,
        )
    )
    if args.packs_command == "update-plan":
        return 0
    return 0 if success else 1


def _bundled_pack_names() -> list[str]:
    root = resources.files(__package__).joinpath("packs")
    return sorted(
        item.name.removesuffix(".yaml")
        for item in root.iterdir()
        if item.name.endswith(".yaml")
    )


def _default_service(*, command_runner: CommandRunner | None = None) -> WorkflowService:
    data_root = resolve_data_root()
    registry = ProfileSkillContentRegistry(data_root / "skills")
    runner = command_runner or _run_command
    return WorkflowService(
        WorkflowStore(data_root / "wingstaff"),
        skill_inventory=registry,
        skill_content_registry=registry,
        kanban=KanbanGraphAdapter(
            lambda name, args: _dispatch_kanban_cli(runner, name, args)
        ),
    )


def _dispatch_kanban_cli(
    runner: CommandRunner,
    name: str,
    args: dict[str, object],
) -> str:
    """Translate the narrow graph adapter boundary to public Hermes CLI calls."""
    if name == "terminal":
        command = tuple(shlex.split(str(args["command"])))
        if command[:2] != ("hermes", "kanban"):
            return json.dumps(
                {"exit_code": 1, "output": "refused non-Kanban host command"}
            )
        code, output = runner(command)
        return json.dumps({"exit_code": code, "output": output})

    board = str(args["board"])
    prefix = ("hermes", "kanban", "--board", board)
    if name == "kanban_create":
        command = [*prefix, "create", str(args["title"])]
        command.extend(("--body", str(args["body"])))
        assignee = args.get("assignee")
        if assignee is not None:
            command.extend(("--assignee", str(assignee)))
        for parent in cast(list[object], args.get("parents", [])):
            command.extend(("--parent", str(parent)))
        workspace_path = args.get("workspace_path")
        if workspace_path is not None:
            command.extend(("--workspace", f"dir:{workspace_path}"))
        command.extend(("--idempotency-key", str(args["idempotency_key"])))
        for skill in cast(list[object], args.get("skills", [])):
            command.extend(("--skill", str(skill)))
        initial_status = args.get("initial_status")
        if initial_status is not None:
            command.extend(("--initial-status", str(initial_status)))
        command.append("--json")
        code, output = runner(tuple(command))
        if code != 0:
            return json.dumps({"ok": False, "error": output})
        payload = _parse_cli_json(output)
        return json.dumps(
            {
                "ok": True,
                "task_id": payload.get("id"),
                "status": payload.get("status"),
            }
        )

    task_id = str(args["task_id"])
    if name == "kanban_show":
        code, output = runner((*prefix, "show", task_id, "--json"))
        if code != 0:
            return json.dumps({"ok": False, "error": output})
        payload = _parse_cli_json(output)
        return json.dumps({"ok": True, "task": payload.get("task")})

    if name == "kanban_complete":
        command = [*prefix, "complete", task_id]
        summary = args.get("summary")
        if summary is not None:
            command.extend(("--summary", str(summary)))
        metadata = args.get("metadata")
        if metadata is not None:
            command.extend(("--metadata", json.dumps(metadata, sort_keys=True)))
        code, output = runner(tuple(command))
        return json.dumps(
            {"ok": code == 0, "task_id": task_id, "error": output if code else None}
        )

    if name == "kanban_comment":
        code, output = runner(
            (*prefix, "comment", task_id, str(args["body"]))
        )
        return json.dumps(
            {"ok": code == 0, "task_id": task_id, "error": output if code else None}
        )

    return json.dumps({"ok": False, "error": f"unsupported Kanban operation: {name}"})


def _parse_cli_json(output: str) -> dict[str, object]:
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as error:
        raise RuntimeError("Hermes Kanban CLI returned invalid JSON") from error
    if not isinstance(payload, dict):
        raise RuntimeError("Hermes Kanban CLI returned a non-object JSON payload")
    return cast(dict[str, object], payload)


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
