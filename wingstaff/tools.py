"""Hermes plugin tool handlers."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from .locations import resolve_data_root
from .packs import load_pack
from .service import WorkflowService
from .store import WorkflowStore

ServiceFactory = Callable[[], WorkflowService]


def _default_service() -> WorkflowService:
    root = resolve_data_root() / "wingstaff"
    return WorkflowService(WorkflowStore(root))


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
                stage.id: [skill.install for skill in stage.skills]
                for stage in pack.stages
            },
        }

    return _handle(args, allowed={"pack"}, required=set(), operation=operation)


def start(args: dict[str, Any], **kwargs: Any) -> str:
    """Create a durable draft workflow."""
    del kwargs
    return _service_handler(
        args,
        allowed={"target_repository", "goal", "pack", "workflow_id"},
        required={"target_repository", "goal"},
        operation=lambda service, values: service.start(
            target_repository=str(values["target_repository"]),
            goal=str(values["goal"]),
            pack_name=str(values.get("pack") or "addyosmani"),
            workflow_id=(str(values["workflow_id"]) if values.get("workflow_id") else None),
        ),
    )


def status(args: dict[str, Any], **kwargs: Any) -> str:
    """Return a durable workflow without mutating it."""
    del kwargs
    return _service_handler(
        args,
        allowed={"workflow_id"},
        required={"workflow_id"},
        operation=lambda service, values: service.status(str(values["workflow_id"])),
    )


def validate(args: dict[str, Any], **kwargs: Any) -> str:
    """Validate the selected pack and local target repository."""
    del kwargs
    return _service_handler(
        args,
        allowed={"workflow_id"},
        required={"workflow_id"},
        operation=lambda service, values: service.validate(str(values["workflow_id"])),
    )


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


def modify(args: dict[str, Any], **kwargs: Any) -> str:
    """Replace the plan artifact and invalidate approval."""
    del kwargs
    return _service_handler(
        args,
        allowed={"workflow_id", "path", "digest"},
        required={"workflow_id", "path", "digest"},
        operation=lambda service, values: service.modify(
            str(values["workflow_id"]),
            path=str(values["path"]),
            digest=str(values["digest"]),
        ),
    )


def cancel(args: dict[str, Any], **kwargs: Any) -> str:
    """Cancel a nonterminal workflow."""
    del kwargs
    return _service_handler(
        args,
        allowed={"workflow_id", "reason"},
        required={"workflow_id", "reason"},
        operation=lambda service, values: service.cancel(
            str(values["workflow_id"]), str(values["reason"])
        ),
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
