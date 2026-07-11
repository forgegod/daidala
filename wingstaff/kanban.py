"""Public Hermes Kanban tool adapter for approved implementation work."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass

from .packs import WorkflowPack
from .state import WorkflowLedger


class KanbanError(RuntimeError):
    """Raised when the public Hermes Kanban boundary rejects a task."""


ToolDispatcher = Callable[[str, dict[str, object]], str]


@dataclass(frozen=True)
class KanbanTask:
    task_id: str
    status: str | None


@dataclass(frozen=True)
class KanbanCoordinator:
    """Create retry-safe cards through ``PluginContext.dispatch_tool``."""

    dispatch_tool: ToolDispatcher

    def ensure_implementation_task(
        self,
        state: WorkflowLedger,
        pack: WorkflowPack,
        *,
        assignee: str,
    ) -> KanbanTask:
        if not state.worktree_path or not state.worktree_owned or state.approval is None:
            raise KanbanError("implementation task requires an approved Wingstaff-owned worktree")
        selected_assignee = assignee.strip()
        if not selected_assignee:
            raise KanbanError("implementation task requires an assignee profile")
        implement = next(stage for stage in pack.stages if stage.id == "implement")
        args: dict[str, object] = {
            "title": f"wingstaff {state.workflow_id}: implement",
            "assignee": selected_assignee,
            "body": (
                f"Wingstaff workflow: {state.workflow_id}\n"
                "Stage: implement\n"
                f"Goal: {state.requested_goal}\n"
                f"Approved plan digest: {state.approval.plan_digest}\n"
                f"Persistent worktree: {state.worktree_path}\n"
                "Use Wingstaff policy tools for capture and evidence. Hermes Kanban "
                "remains authoritative for lifecycle state."
            ),
            "workspace_kind": "worktree",
            "workspace_path": state.worktree_path,
            "idempotency_key": (
                f"wingstaff:{state.workflow_id}:{state.plan_revision}:implement"
            ),
            "skills": [skill.name for skill in implement.skills],
        }
        try:
            payload = json.loads(self.dispatch_tool("kanban_create", args))
        except (TypeError, json.JSONDecodeError) as error:
            raise KanbanError("kanban_create returned invalid JSON") from error
        if not isinstance(payload, dict) or payload.get("ok") is not True:
            message = payload.get("error") if isinstance(payload, dict) else None
            raise KanbanError(f"kanban_create failed: {message or 'unknown error'}")
        task_id = payload.get("task_id")
        status = payload.get("status")
        if not isinstance(task_id, str) or not task_id.strip():
            raise KanbanError("kanban_create omitted task_id")
        if status is not None and not isinstance(status, str):
            raise KanbanError("kanban_create returned invalid status")
        return KanbanTask(task_id=task_id, status=status)
