"""Public Hermes Kanban adapter for Daidala workflow graphs."""

from __future__ import annotations

import json
import shlex
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from .constraints import WorkflowConstraints
from .packs import WorkflowPack
from .state import WorkflowLedger, WorkflowStage


class KanbanError(RuntimeError):
    """Raised when the documented Hermes host boundary fails closed."""


ToolDispatcher = Callable[[str, dict[str, object]], str]


@dataclass(frozen=True)
class KanbanTask:
    task_id: str
    status: str | None


@dataclass(frozen=True)
class KanbanCardStatus:
    stage: WorkflowStage
    task_id: str
    status: str
    assignee: str

    def to_dict(self) -> dict[str, str]:
        return {
            "stage": self.stage.value,
            "task_id": self.task_id,
            "status": self.status,
            "assignee": self.assignee,
        }


@dataclass(frozen=True)
class KanbanGraphAdapter:
    """Drive one named board through an injected public Hermes host boundary."""

    dispatch_tool: ToolDispatcher

    MAX_CARD_BODY_CHARS = 8192

    def validate_assignees(self, board_slug: str, profiles: Sequence[str]) -> None:
        command = (
            f"hermes kanban --board {shlex.quote(board_slug)} assignees --json"
        )
        rows = self._terminal_json(command)
        if not isinstance(rows, list):
            raise KanbanError("kanban assignees returned invalid JSON")
        available = {
            row["name"]
            for row in rows
            if isinstance(row, dict)
            and isinstance(row.get("name"), str)
            and row.get("on_disk") is True
        }
        requested = {profile.strip() for profile in profiles if profile.strip()}
        missing = sorted(requested - available)
        if missing:
            raise KanbanError(f"unknown Kanban assignee profile(s): {', '.join(missing)}")

    def ensure_card(
        self,
        ledger: WorkflowLedger,
        pack: WorkflowPack,
        *,
        stage: WorkflowStage,
        parents: Sequence[str] = (),
        constraints: WorkflowConstraints | None = None,
    ) -> KanbanTask:
        if (ledger.current_constraints is None) != (constraints is None):
            raise KanbanError("card constraints do not match the current workflow identity")
        if stage in {
            WorkflowStage.IMPLEMENT,
            WorkflowStage.VERIFY,
            WorkflowStage.REVIEW,
            WorkflowStage.DELIVER,
        } and (
            ledger.approval is None
            or not ledger.worktree_owned
            or ledger.worktree_path is None
        ):
            raise KanbanError("post-gate cards require approval and an owned worktree")
        revision = (
            0
            if stage in {WorkflowStage.DEFINE, WorkflowStage.PLAN}
            else ledger.plan_revision
        )
        constraint_key = ledger.current_constraints_digest or "none"
        idempotency_key = (
            f"daidala:{ledger.workflow_id}:{revision}:{ledger.policy_revision}:"
            f"{constraint_key}:{stage.value}"
        )
        args: dict[str, object] = {
            "title": f"daidala {ledger.workflow_id}: {stage.value}",
            "assignee": ledger.profile_for(stage),
            "body": self._card_body(ledger, stage, constraints),
            "parents": list(parents),
            "idempotency_key": idempotency_key,
            "skills": self._stage_skills(pack, stage),
            "board": ledger.board_slug,
        }
        if stage is WorkflowStage.APPROVAL:
            args["initial_status"] = "blocked"
        elif stage in {
            WorkflowStage.IMPLEMENT,
            WorkflowStage.VERIFY,
            WorkflowStage.REVIEW,
            WorkflowStage.DELIVER,
        }:
            args["workspace_kind"] = "dir"
            args["workspace_path"] = ledger.worktree_path
        else:
            args["workspace_kind"] = "dir"
            args["workspace_path"] = ledger.target_repository
        payload = self._tool_json("kanban_create", args)
        task_id = payload.get("task_id")
        status = payload.get("status")
        if not isinstance(task_id, str) or not task_id.strip():
            raise KanbanError("kanban_create omitted task_id")
        if status is not None and not isinstance(status, str):
            raise KanbanError("kanban_create returned invalid status")
        return KanbanTask(task_id=task_id, status=status)

    def complete_approval(self, ledger: WorkflowLedger) -> None:
        card = ledger.card_for(WorkflowStage.APPROVAL)
        if card is None or ledger.approval is None:
            raise KanbanError("approval completion requires a recorded approval card")
        current = self.show_card(ledger, WorkflowStage.APPROVAL)
        if current.status == "done":
            return
        self._tool_json(
            "kanban_complete",
            {
                "task_id": card.task_id,
                "summary": "Daidala exact-digest approval recorded",
                "metadata": {
                    "workflow_id": ledger.workflow_id,
                    "stage": WorkflowStage.APPROVAL.value,
                    "plan_revision": ledger.plan_revision,
                    "plan_digest": ledger.approval.plan_digest,
                    "constraints_revision": ledger.approval.constraints_revision,
                    "constraints_digest": ledger.approval.constraints_digest,
                },
                "board": ledger.board_slug,
            },
        )

    def show_card(
        self,
        ledger: WorkflowLedger,
        stage: WorkflowStage,
    ) -> KanbanCardStatus:
        card = ledger.card_for(stage)
        if card is None:
            raise KanbanError(f"workflow has no {stage.value} card")
        payload = self._tool_json(
            "kanban_show",
            {"task_id": card.task_id, "board": ledger.board_slug},
        )
        task = payload.get("task")
        if not isinstance(task, Mapping):
            raise KanbanError("kanban_show omitted task")
        task_id = task.get("id")
        status = task.get("status")
        assignee = task.get("assignee")
        if task_id != card.task_id:
            raise KanbanError("kanban_show returned the wrong task")
        if not isinstance(status, str) or not status:
            raise KanbanError("kanban_show returned invalid status")
        if not isinstance(assignee, str) or not assignee:
            raise KanbanError("kanban_show returned invalid assignee")
        return KanbanCardStatus(stage, card.task_id, status, assignee)

    def combined_status(self, ledger: WorkflowLedger) -> tuple[KanbanCardStatus, ...]:
        return tuple(
            self.show_card(ledger, stage)
            for stage in WorkflowStage
            if ledger.card_for(stage) is not None
        )

    def archive(
        self,
        ledger: WorkflowLedger,
        reason: str,
        *,
        stages: set[WorkflowStage] | None = None,
        before_policy_revision: int | None = None,
    ) -> None:
        cards = tuple(
            card
            for card in ledger.card_references
            if stages is None or card.stage in stages
            if before_policy_revision is None
            or card.policy_revision < before_policy_revision
        )
        if not cards:
            return
        for card in cards:
            self._tool_json(
                "kanban_comment",
                {
                    "task_id": card.task_id,
                    "body": f"Daidala cancellation: {reason}",
                    "board": ledger.board_slug,
                },
            )
        ids = " ".join(shlex.quote(card.task_id) for card in cards)
        self._terminal(
            f"hermes kanban --board {shlex.quote(ledger.board_slug)} archive {ids}"
        )

    def _card_body(
        self,
        ledger: WorkflowLedger,
        stage: WorkflowStage,
        constraints: WorkflowConstraints | None,
    ) -> str:
        lines = [
            f"Daidala workflow: {ledger.workflow_id}",
            f"Stage: {stage.value}",
            f"Plan revision: {ledger.plan_revision}",
            f"Policy revision: {ledger.policy_revision}",
            f"Pack: {ledger.pack_name}",
            f"Pack revision: {ledger.pack_source_revision}",
            f"Goal: {ledger.requested_goal}",
        ]
        if ledger.current_plan_digest:
            lines.append(f"Plan digest: {ledger.current_plan_digest}")
        if ledger.worktree_path:
            lines.append(f"Persistent worktree: {ledger.worktree_path}")
        if stage is not WorkflowStage.APPROVAL:
            current = ledger.current_constraints
            lines.extend(
                [
                    "--- Workflow constraints ---",
                    "Constraint revision: "
                    f"{current.identity.constraints_revision if current else 'none'}",
                    f"Constraint digest: {current.identity.digest if current else 'none'}",
                    f"Constraint artifact: {current.path if current else 'none'}",
                ]
            )
            if constraints is not None:
                lines.extend(
                    f"- {constraint}" for constraint in constraints.constraints_for(stage)
                )
            lines.extend(
                [
                    "Block if a constraint conflicts with requested work or prescribes "
                    "methodology/capabilities.",
                    "--- End workflow constraints ---",
                ]
            )
        lines.append("Use Daidala policy/evidence tools; Hermes Kanban owns lifecycle state.")
        body = "\n".join(lines)
        if len(body) > self.MAX_CARD_BODY_CHARS:
            raise KanbanError(
                f"rendered Kanban card body must be at most {self.MAX_CARD_BODY_CHARS} characters"
            )
        return body

    @staticmethod
    def _stage_skills(pack: WorkflowPack, stage: WorkflowStage) -> list[str]:
        if stage is WorkflowStage.APPROVAL:
            return []
        selected = next(row for row in pack.stages if row.id == stage.value)
        return [
            "daidala:orchestrate",
            *(
                f"daidala:{skill.name}" if skill.bundled else skill.name
                for skill in selected.skills
            ),
        ]

    def _tool_json(self, name: str, args: dict[str, object]) -> dict[str, object]:
        try:
            payload = json.loads(self.dispatch_tool(name, args))
        except (TypeError, json.JSONDecodeError) as error:
            raise KanbanError(f"{name} returned invalid JSON") from error
        if not isinstance(payload, dict) or payload.get("ok") is not True:
            message = payload.get("error") if isinstance(payload, dict) else None
            raise KanbanError(f"{name} failed: {message or 'unknown error'}")
        return payload

    def _terminal_json(self, command: str) -> object:
        output = self._terminal(command)
        try:
            return json.loads(output)
        except json.JSONDecodeError as error:
            raise KanbanError("Kanban CLI returned invalid JSON") from error

    def _terminal(self, command: str) -> str:
        try:
            payload = json.loads(self.dispatch_tool("terminal", {"command": command}))
        except (TypeError, json.JSONDecodeError) as error:
            raise KanbanError("terminal returned invalid JSON") from error
        if not isinstance(payload, dict):
            raise KanbanError("terminal returned invalid JSON")
        exit_code = payload.get("exit_code")
        output = payload.get("output")
        if isinstance(exit_code, bool) or not isinstance(exit_code, int):
            raise KanbanError("terminal omitted exit_code")
        if not isinstance(output, str):
            raise KanbanError("terminal omitted output")
        if exit_code != 0:
            raise KanbanError(f"Kanban CLI failed with exit code {exit_code}")
        return output