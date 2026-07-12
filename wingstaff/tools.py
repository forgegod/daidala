"""Hermes plugin tool handlers."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any

from .kanban import KanbanGraphAdapter, ToolDispatcher
from .locations import resolve_data_root
from .packs import load_pack
from .service import WorkflowService
from .skills import pack_skill_digests
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
        digests = dict(pack_skill_digests(pack))
        return {
            "pack": pack.name,
            "source": pack.source,
            "source_revision": pack.source_revision,
            "hermes_version_constraint": pack.hermes_version_constraint,
            "lifecycle": list(pack.lifecycle),
            "human_gate_after": pack.human_gate_after,
            "skills": {
                stage.id: [
                    {
                        "name": skill.name,
                        "provider": {
                            "kind": "external" if skill.is_external else "bundled",
                            "reference": skill.install or skill.bundled,
                        },
                        "content_digest": {
                            "sha256": digests[skill.name],
                            "source": "pack" if skill.is_external else "bundled-resource",
                        },
                        "activation": skill.activation.value,
                    }
                    for skill in stage.skills
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
            **_worker_context(),
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
            str(values["workflow_id"]), **_worker_context()
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
            **_worker_context(),
        ),
    )


def record_skill_activation(args: dict[str, Any], **kwargs: Any) -> str:
    """Persist skill decisions authorized by the executing Kanban card context."""
    del kwargs

    def operation(values: dict[str, Any]) -> dict[str, Any]:
        if "supersedes_digest" not in values:
            raise ValueError("missing required arguments: supersedes_digest")
        board_slug = os.environ.get("HERMES_KANBAN_BOARD")
        task_id = os.environ.get("HERMES_KANBAN_TASK")
        if not board_slug or not board_slug.strip() or not task_id or not task_id.strip():
            raise ValueError("skill activation requires Hermes Kanban worker context")
        reference, ledger = _service_factory().record_skill_activation(
            str(values["workflow_id"]),
            stage=WorkflowStage(str(values["stage"])),
            supersedes_digest=values["supersedes_digest"],
            decisions=values["decisions"],
            board_slug=board_slug,
            task_id=task_id,
        )
        return {"activation": reference.to_dict(), "workflow": ledger.to_dict()}

    return _handle(
        args,
        allowed={"workflow_id", "stage", "supersedes_digest", "decisions"},
        required={"workflow_id", "stage", "decisions"},
        operation=operation,
    )


def deliver(args: dict[str, Any], **kwargs: Any) -> str:
    """Record delivery without committing or pushing target changes."""
    del kwargs
    return _service_handler(
        args,
        allowed={"workflow_id"},
        required={"workflow_id"},
        operation=lambda service, values: service.deliver(
            str(values["workflow_id"]), **_worker_context()
        ),
    )


def _worker_context() -> dict[str, str]:
    board_slug = os.environ.get("HERMES_KANBAN_BOARD")
    task_id = os.environ.get("HERMES_KANBAN_TASK")
    if not board_slug or not board_slug.strip() or not task_id or not task_id.strip():
        raise ValueError("evidence operation requires Hermes Kanban worker context")
    return {"board_slug": board_slug, "task_id": task_id}


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
