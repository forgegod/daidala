from __future__ import annotations

import json
from pathlib import Path

import wingstaff
from wingstaff.tools import pack_info


class FakeContext:
    def __init__(self) -> None:
        self.tools: list[dict] = []
        self.skills: list[tuple[str, Path]] = []

    def register_tool(self, **kwargs) -> None:
        self.tools.append(kwargs)

    def register_skill(self, name: str, path: Path) -> None:
        self.skills.append((name, path))


def test_register_exposes_tool_and_namespaced_skill_source() -> None:
    ctx = FakeContext()

    wingstaff.register(ctx)

    assert [tool["name"] for tool in ctx.tools] == ["wingstaff_pack_info"]
    assert [name for name, _ in ctx.skills] == ["orchestrate"]
    assert ctx.skills[0][1].name == "SKILL.md"


def test_pack_info_returns_json_string() -> None:
    result = json.loads(pack_info({"pack": "addyosmani"}))

    assert result["success"] is True
    assert result["human_gate_after"] == "plan"
    assert result["lifecycle"][2] == "implement"


def test_pack_info_reports_unknown_pack_without_raising() -> None:
    result = json.loads(pack_info({"pack": "missing"}))

    assert result == {"success": False, "error": "unknown bundled pack: 'missing'"}
