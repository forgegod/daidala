from __future__ import annotations

import json
from pathlib import Path

import wingstaff
from wingstaff.tools import pack_info


class FakeContext:
    def __init__(self) -> None:
        self.tools: list[dict] = []
        self.skills: list[tuple[str, Path]] = []
        self.cli_commands: list[dict] = []

    def register_tool(self, **kwargs) -> None:
        self.tools.append(kwargs)

    def register_skill(self, name: str, path: Path) -> None:
        self.skills.append((name, path))

    def register_cli_command(self, **kwargs) -> None:
        self.cli_commands.append(kwargs)

    def dispatch_tool(self, name: str, args: dict) -> str:
        del name, args
        return json.dumps({"ok": True, "task_id": "t_fake", "status": "ready"})


def test_register_exposes_tool_and_namespaced_skill_source() -> None:
    ctx = FakeContext()

    wingstaff.register(ctx)

    assert [tool["name"] for tool in ctx.tools] == [
        "wingstaff_pack_info",
        "wingstaff_start",
        "wingstaff_status",
        "wingstaff_validate",
        "wingstaff_approve",
        "wingstaff_modify",
        "wingstaff_cancel",
        "wingstaff_submit_artifact",
        "wingstaff_prepare_implementation",
        "wingstaff_capture_implementation",
        "wingstaff_record_verification",
        "wingstaff_deliver",
    ]
    assert all(tool["toolset"] == "wingstaff" for tool in ctx.tools)
    assert [name for name, _ in ctx.skills] == ["orchestrate"]
    assert ctx.skills[0][1].name == "SKILL.md"
    assert len(ctx.cli_commands) == 1
    assert ctx.cli_commands[0]["name"] == "wingstaff"


def test_pack_info_returns_json_string() -> None:
    result = json.loads(pack_info({"pack": "addyosmani"}))

    assert result["success"] is True
    assert result["human_gate_after"] == "plan"
    assert result["lifecycle"][2] == "implement"


def test_pack_info_reports_unknown_pack_without_raising() -> None:
    result = json.loads(pack_info({"pack": "missing"}))

    assert result == {
        "success": False,
        "error": "PackError",
        "message": "unknown bundled pack: 'missing'",
    }
