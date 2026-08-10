"""Hermes plugin tool handlers."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .checkouts import CheckoutManager
from .kanban import KanbanGraphAdapter, ToolDispatcher
from .locations import resolve_data_root
from .packs import load_pack
from .plan_admission import admit_plan_source
from .registrations import list_controller_registrations
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
    root = resolve_data_root() / "daidala"
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
            "constraints_content",
            "constraints_skill",
            "constraints_skill_digest",
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
            constraints_content=values.get("constraints_content"),
            constraints_skill=values.get("constraints_skill"),
            constraints_skill_digest=values.get("constraints_skill_digest"),
        ),
    )


def start_from_plan(args: dict[str, Any], **kwargs: Any) -> str:
    """Preview or admit one Git-pinned pending plan phase without source disclosure."""
    del kwargs
    allowed = {
        "board_slug",
        "target_repository",
        "plan_path",
        "source_revision",
        "phase_number",
        "stage_profiles",
        "pack",
        "workflow_id",
        "predecessor_workflow_id",
        "constraints_content",
        "constraints_skill",
        "constraints_skill_digest",
        "apply",
        "expected_preview_digest",
    }
    required = {
        "board_slug",
        "target_repository",
        "plan_path",
        "source_revision",
        "phase_number",
        "stage_profiles",
        "workflow_id",
    }
    try:
        values = _validate_args(args, allowed=allowed, required=required)
    except Exception as error:  # noqa: BLE001 - Hermes handler boundary
        return _tool_error(error)

    apply = values.get("apply", False)
    expected_preview_digest = values.get("expected_preview_digest")
    if not isinstance(apply, bool):
        return _plan_admission_error("apply must be a boolean")
    if apply and expected_preview_digest is None:
        return _plan_admission_error("apply requires expected_preview_digest")
    if not apply and expected_preview_digest is not None:
        return _plan_admission_error("expected_preview_digest requires apply")

    try:
        packet = admit_plan_source(
            repository=Path(str(values["target_repository"])),
            plan_path=values["plan_path"],
            source_revision=values["source_revision"],
            baseline_commit=values["source_revision"],
            phase_number=values["phase_number"],
            predecessor_workflow_id=values.get("predecessor_workflow_id"),
        )
        service = _service_factory()
        common = {
            "packet": packet,
            "board_slug": values["board_slug"],
            "stage_profiles": values["stage_profiles"],
            "pack_name": values.get("pack") or "addyosmani",
            "workflow_id": values["workflow_id"],
            "predecessor_workflow_id": values.get("predecessor_workflow_id"),
            "constraints_content": values.get("constraints_content"),
            "constraints_skill": values.get("constraints_skill"),
            "constraints_skill_digest": values.get("constraints_skill_digest"),
        }
        if apply:
            assert isinstance(expected_preview_digest, str)
            service.start_from_plan(
                **common, expected_preview_digest=expected_preview_digest
            )
            preview_digest = expected_preview_digest
        else:
            preview_digest = service.preview_start_from_plan(**common).digest
    except Exception:  # noqa: BLE001 - source and service errors stay bounded
        return _plan_admission_error("plan admission rejected")
    return json.dumps(
        {
            "success": True,
            "operation": "start-from-plan",
            "dry_run": not apply,
            "workflow_id": values["workflow_id"],
            "plan_source": _plan_source_metadata(packet),
            "preview_digest": preview_digest,
        },
        sort_keys=True,
    )


def _plan_source_metadata(packet: Any) -> dict[str, Any]:
    return {
        "plan_id": packet.plan_id,
        "execution_slot": packet.execution_slot,
        "phase_number": packet.phase_number,
        "source_revision": packet.reference.source_revision,
        "baseline_commit": packet.reference.baseline_commit,
        "plan_digest": packet.reference.plan_digest,
        "packet_digest": packet.digest,
    }


def _plan_admission_error(message: str) -> str:
    return json.dumps(
        {"success": False, "error": "PlanAdmissionError", "message": message},
        sort_keys=True,
    )


def _tool_error(error: Exception) -> str:
    return json.dumps(
        {
            "success": False,
            "error": error.__class__.__name__,
            "message": str(error),
        },
        sort_keys=True,
    )


def replace_constraints(args: dict[str, Any], **kwargs: Any) -> str:
    """Replace constraints from explicit content or an exact installed policy skill."""
    del kwargs

    def operation(service: WorkflowService, values: dict[str, Any]):
        if "expected_current_digest" not in values:
            raise ValueError("missing required arguments: expected_current_digest")
        return service.replace_constraint_input(
            str(values["workflow_id"]),
            expected_current_digest=values["expected_current_digest"],
            content=values.get("constraints_content"),
            skill_name=values.get("constraints_skill"),
            skill_digest=values.get("constraints_skill_digest"),
        )

    return _service_handler(
        args,
        allowed={
            "workflow_id",
            "expected_current_digest",
            "constraints_content",
            "constraints_skill",
            "constraints_skill_digest",
        },
        required={"workflow_id"},
        operation=operation,
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


def checkouts_status(args: dict[str, Any], **kwargs: Any) -> str:
    """Return report-only checkout status projections for future cron consumption."""

    del kwargs

    def operation(_values: dict[str, Any]) -> dict[str, Any]:
        data_root = resolve_data_root().resolve()
        manager = CheckoutManager(data_root)
        registrations = list_controller_registrations(data_root)
        return {"checkouts": [row.to_dict() for row in manager.statuses(registrations)]}

    return _handle(args, allowed=set(), required=set(), operation=operation)


def _combined_status(service: WorkflowService, workflow_id: str) -> dict[str, Any]:
    ledger = service.status(workflow_id)
    return {
        "workflow": ledger.to_dict(),
        "kanban": [row.to_dict() for row in service.combined_status(workflow_id)],
    }


def approve(args: dict[str, Any], **kwargs: Any) -> str:
    """Approve the exact current plan digest."""
    del kwargs

    def operation(values: dict[str, Any]) -> dict[str, Any]:
        if "HERMES_KANBAN_TASK" in os.environ:
            raise ValueError("approval is unavailable from Hermes Kanban worker context")
        workflow = _service_factory().approve(
            str(values["workflow_id"]), str(values["plan_digest"])
        )
        return {"workflow": workflow.to_dict()}

    return _handle(
        args,
        allowed={"workflow_id", "plan_digest"},
        required={"workflow_id", "plan_digest"},
        operation=operation,
    )


def cancel(args: dict[str, Any], **kwargs: Any) -> str:
    """Clean up Daidala-owned worktree state before Kanban archival."""
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
    """Persist a definition or plan artifact."""
    del kwargs
    return _service_handler(
        args,
        allowed={"workflow_id", "stage", "content", "approval_summary"},
        required={"workflow_id", "stage", "content"},
        operation=lambda service, values: service.submit_artifact(
            str(values["workflow_id"]),
            stage=WorkflowStage(str(values["stage"])),
            content=str(values["content"]),
            approval_summary=values.get("approval_summary"),
            **_worker_context(),
        ),
    )


def submit_review(args: dict[str, Any], **kwargs: Any) -> str:
    """Persist source-bound structured review evidence from the review worker."""
    del kwargs
    return _service_handler(
        args,
        allowed={"workflow_id", "outcome", "summary", "findings"},
        required={"workflow_id", "outcome", "summary", "findings"},
        operation=lambda service, values: service.submit_review(
            str(values["workflow_id"]),
            outcome=str(values["outcome"]),
            summary=values["summary"],
            findings=values["findings"],
            **_worker_context(),
        ),
    )


def decide_review(args: dict[str, Any], **kwargs: Any) -> str:
    """Record an attended review disposition for the exact review digest."""
    del kwargs

    def operation(values: dict[str, Any]) -> dict[str, Any]:
        if "HERMES_KANBAN_TASK" in os.environ:
            raise ValueError("review disposition is unavailable from Hermes Kanban worker context")
        workflow = _service_factory().decide_review(
            str(values["workflow_id"]),
            review_digest=str(values["review_digest"]),
            action=str(values["action"]),
            actor=str(values["actor"]),
            rationale=str(values["rationale"]),
        )
        return {"workflow": workflow.to_dict()}

    return _handle(
        args,
        allowed={"workflow_id", "review_digest", "action", "actor", "rationale"},
        required={"workflow_id", "review_digest", "action", "actor", "rationale"},
        operation=operation,
    )


def prepare_implementation(args: dict[str, Any], **kwargs: Any) -> str:
    """Create the exact-approved Daidala worktree."""
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
        return _tool_error(error)


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
