"""Hermes plugin tool handlers."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from .kanban import KanbanGraphAdapter, ToolDispatcher
from .locations import resolve_data_root
from .packs import load_pack
from .service import WorkflowService
from .state import WorkflowStage
from .store import WorkflowStore

ServiceFactory = Callable[[], WorkflowService]
_host_dispatch: ToolDispatcher | None = None


def configure_host(dispatch_tool: ToolDispatcher) -> None:
    """Bind the public plugin-context tool dispatcher for this process."""
    global _host_dispatch
    _host_dispatch = dispatch_tool


def _default_service() -> WorkflowService:
    root = resolve_data_root() / "wingstaff"
    kanban = KanbanGraphAdapter(_host_dispatch) if _host_dispatch is not None else None
    return WorkflowService(WorkflowStore(root), kanban=kanban)


_service_factory: ServiceFactory = _default_service


def pack_info(args: dict[str, Any], **kwargs: Any) -> str:
    """Return validated pack metadata as a Hermes-compatible JSON string."""
    del kwargs

    def operation(values: dict[str, Any]) -> dict[str, Any]:
        pack = load_pack(str(values.get("pack") or "addyosmani"))
        return {
            "pack": pack.name,
            "source": pack.source,
            "lifecycle": list(pack.lifecycle),
            "human_gate_after": pack.human_gate_after,
            "skills": {
                stage.id: [
                    skill.install or f"bundled:{skill.bundled}" for skill in stage.skills
                ]
                for stage in pack.stages
            },
        }

    return _handle(args, allowed={"pack"}, required=set(), operation=operation)


def start(args: dict[str, Any], **kwargs: Any) -> str:
    """Create a validated policy ledger for one named Kanban board."""
    del kwargs
    return _service_handler(
        args,
        allowed={
            "board_slug",
            "target_repository",
            "goal",
            "stage_profiles",
            "pack",
            "workflow_id",
        },
        required={
            "board_slug",
            "target_repository",
            "goal",
            "stage_profiles",
            "workflow_id",
        },
        operation=lambda service, values: service.start(
            board_slug=str(values["board_slug"]),
            target_repository=str(values["target_repository"]),
            goal=str(values["goal"]),
            stage_profiles=values["stage_profiles"],
            pack_name=str(values.get("pack") or "addyosmani"),
            workflow_id=str(values["workflow_id"]),
        ),
    )


def status(args: dict[str, Any], **kwargs: Any) -> str:
    """Return policy facts beside live, read-only Kanban card status."""
    del kwargs
    return _handle(
        args,
        allowed={"workflow_id"},
        required={"workflow_id"},
        operation=lambda values: _combined_status(
            _service_factory(), str(values["workflow_id"])
        ),
    )


def _combined_status(service: WorkflowService, workflow_id: str) -> dict[str, Any]:
    ledger = service.status(workflow_id)
    return {
        "workflow": ledger.to_dict(),
        "kanban": [row.to_dict() for row in service.combined_status(workflow_id)],
    }


def approve(args: dict[str, Any], **kwargs: Any) -> str:
    """Approve the exact current plan digest."""
    del kwargs
    return _service_handler(
        args,
        allowed={"workflow_id", "plan_digest"},
        required={"workflow_id", "plan_digest"},
        operation=lambda service, values: service.approve(
            str(values["workflow_id"]), str(values["plan_digest"])
        ),
    )


def cancel(args: dict[str, Any], **kwargs: Any) -> str:
    """Clean up Wingstaff-owned worktree state before Kanban archival."""
    del kwargs
    return _service_handler(
        args,
        allowed={"workflow_id", "reason"},
        required={"workflow_id", "reason"},
        operation=lambda service, values: service.cancel(
            str(values["workflow_id"]), str(values["reason"])
        ),
    )


def submit_artifact(args: dict[str, Any], **kwargs: Any) -> str:
    """Persist a definition, plan, or review artifact."""
    del kwargs
    return _service_handler(
        args,
        allowed={"workflow_id", "stage", "content"},
        required={"workflow_id", "stage", "content"},
        operation=lambda service, values: service.submit_artifact(
            str(values["workflow_id"]),
            stage=WorkflowStage(str(values["stage"])),
            content=str(values["content"]),
        ),
    )


def prepare_implementation(args: dict[str, Any], **kwargs: Any) -> str:
    """Create the exact-approved Wingstaff worktree."""
    del kwargs
    return _service_handler(
        args,
        allowed={"workflow_id"},
        required={"workflow_id"},
        operation=lambda service, values: service.prepare_implementation(
            str(values["workflow_id"])
        ),
    )


def capture_implementation(args: dict[str, Any], **kwargs: Any) -> str:
    """Capture the real implementation worktree diff."""
    del kwargs
    return _service_handler(
        args,
        allowed={"workflow_id"},
        required={"workflow_id"},
        operation=lambda service, values: service.capture_implementation(
            str(values["workflow_id"])
        ),
    )


def record_verification(args: dict[str, Any], **kwargs: Any) -> str:
    """Persist command output and structured verification evidence."""
    del kwargs
    return _service_handler(
        args,
        allowed={"workflow_id", "command", "exit_code", "output"},
        required={"workflow_id", "command", "exit_code", "output"},
        operation=lambda service, values: service.record_verification(
            str(values["workflow_id"]),
            command=str(values["command"]),
            exit_code=values["exit_code"],
            output=str(values["output"]),
        ),
    )


def deliver(args: dict[str, Any], **kwargs: Any) -> str:
    """Record delivery without committing or pushing target changes."""
    del kwargs
    return _service_handler(
        args,
        allowed={"workflow_id"},
        required={"workflow_id"},
        operation=lambda service, values: service.deliver(str(values["workflow_id"])),
    )


def _service_handler(
    args: dict[str, Any],
    *,
    allowed: set[str],
    required: set[str],
    operation: Callable[[WorkflowService, dict[str, Any]], Any],
) -> str:
    return _handle(
        args,
        allowed=allowed,
        required=required,
        operation=lambda values: {"workflow": operation(_service_factory(), values).to_dict()},
    )


def _handle(
    args: dict[str, Any],
    *,
    allowed: set[str],
    required: set[str],
    operation: Callable[[dict[str, Any]], dict[str, Any]],
) -> str:
    try:
        values = _validate_args(args, allowed=allowed, required=required)
        return json.dumps({"success": True, **operation(values)}, sort_keys=True)
    except Exception as error:  # noqa: BLE001 - Hermes handler boundary
        return json.dumps(
            {
                "success": False,
                "error": error.__class__.__name__,
                "message": str(error),
            },
            sort_keys=True,
        )


def _validate_args(
    args: dict[str, Any], *, allowed: set[str], required: set[str]
) -> dict[str, Any]:
    if not isinstance(args, dict):
        raise TypeError("tool arguments must be an object")
    unknown = sorted(set(args) - allowed)
    if unknown:
        raise ValueError(f"unknown arguments: {', '.join(unknown)}")
    missing = sorted(
        name
        for name in required
        if name not in args or args[name] is None or args[name] == ""
    )
    if missing:
        raise ValueError(f"missing required arguments: {', '.join(missing)}")
    return args
