from __future__ import annotations

import json

import pytest

from wingstaff.kanban import KanbanGraphAdapter

STAGE_PROFILES = {
    "define": "architect",
    "plan": "architect",
    "implement": "engineer",
    "verify": "engineer",
    "review": "reviewer",
    "deliver": "engineer",
}


class FakeKanbanHost:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.cards: dict[str, dict[str, object]] = {}
        self.by_key: dict[str, str] = {}
        self.archived: list[str] = []
        self.comments: dict[str, list[str]] = {}
        self.profiles = {"architect", "engineer", "reviewer"}

    def dispatch(self, name: str, args: dict[str, object]) -> str:
        self.calls.append((name, args))
        if name == "terminal":
            command = str(args["command"])
            if " assignees --json" in command:
                rows = [
                    {"name": profile, "on_disk": True, "counts": {}}
                    for profile in sorted(self.profiles)
                ]
                return json.dumps({"exit_code": 0, "output": json.dumps(rows)})
            if " archive " in command:
                self.archived.extend(command.split(" archive ", 1)[1].split())
                return json.dumps({"exit_code": 0, "output": ""})
        if name == "kanban_create":
            key = str(args["idempotency_key"])
            task_id = self.by_key.setdefault(key, f"t_{len(self.by_key) + 1}")
            self.cards.setdefault(
                task_id,
                {
                    "id": task_id,
                    "status": (
                        "blocked" if args.get("initial_status") == "blocked" else "ready"
                    ),
                    "assignee": args["assignee"],
                    "args": dict(args),
                },
            )
            return json.dumps(
                {"ok": True, "task_id": task_id, "status": self.cards[task_id]["status"]}
            )
        if name == "kanban_show":
            task_id = str(args["task_id"])
            task = {**self.cards[task_id], "comments": self.comments.get(task_id, [])}
            return json.dumps({"ok": True, "task": task})
        if name == "kanban_complete":
            task_id = str(args["task_id"])
            self.cards[task_id]["status"] = "done"
            self.cards[task_id]["completion_summary"] = args.get("summary")
            self.cards[task_id]["completion_metadata"] = args.get("metadata")
            return json.dumps({"ok": True, "task_id": task_id, "status": "done"})
        if name == "kanban_comment":
            task_id = str(args["task_id"])
            self.comments.setdefault(task_id, []).append(str(args["body"]))
            return json.dumps({"ok": True, "task_id": task_id})
        if name == "kanban_block":
            task_id = str(args["task_id"])
            self.cards[task_id]["status"] = "blocked"
            self.cards[task_id]["block_kind"] = args.get("kind")
            self.cards[task_id]["block_reason"] = args["reason"]
            return json.dumps({"ok": True, "task_id": task_id, "status": "blocked"})
        if name == "kanban_unblock":
            task_id = str(args["task_id"])
            self.cards[task_id]["status"] = "ready"
            return json.dumps({"ok": True, "task_id": task_id, "status": "ready"})
        raise AssertionError(f"unexpected host call: {name}")


@pytest.fixture
def fake_kanban_host() -> FakeKanbanHost:
    return FakeKanbanHost()


@pytest.fixture
def kanban_adapter(fake_kanban_host: FakeKanbanHost) -> KanbanGraphAdapter:
    return KanbanGraphAdapter(fake_kanban_host.dispatch)


@pytest.fixture
def stage_profiles() -> dict[str, str]:
    return dict(STAGE_PROFILES)
