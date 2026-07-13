from __future__ import annotations

import json
from pathlib import Path

import yaml

import daidala
from daidala.tools import pack_info


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

    daidala.register(ctx)

    assert [tool["name"] for tool in ctx.tools] == [
        "daidala_pack_info",
        "daidala_start",
        "daidala_status",
        "daidala_replace_constraints",
        "daidala_approve",
        "daidala_cancel",
        "daidala_submit_artifact",
        "daidala_prepare_implementation",
        "daidala_capture_implementation",
        "daidala_record_skill_activation",
        "daidala_record_verification",
        "daidala_deliver",
    ]
    assert all(tool["toolset"] == "daidala" for tool in ctx.tools)
    assert [name for name, _ in ctx.skills] == ["aidlc-adapter", "orchestrate", "setup"]
    assert all(path.name == "SKILL.md" for _, path in ctx.skills)
    legacy_prefix = "wing" + "staff_"
    assert not any(tool["name"].startswith(legacy_prefix) for tool in ctx.tools)
    orchestrate = next(path for name, path in ctx.skills if name == "orchestrate")
    instructions = orchestrate.read_text(encoding="utf-8")
    assert "stage-profile mapping" in instructions
    setup = next(path for name, path in ctx.skills if name == "setup")
    setup_instructions = setup.read_text(encoding="utf-8")
    assert "explicitly confirm that exact preview" in setup_instructions
    assert "dashboard is available" in setup_instructions
    assert len(ctx.cli_commands) == 1
    assert ctx.cli_commands[0]["name"] == "daidala"


def test_manifest_tool_inventory_matches_runtime_registration() -> None:
    ctx = FakeContext()
    daidala.register(ctx)
    manifest = yaml.safe_load(
        (Path(__file__).parents[1] / "plugin.yaml").read_text(encoding="utf-8")
    )

    assert manifest["description"] == (
        "Hermes-native AI workshop for crafted, human-approved work through "
        "specialist agents and skills."
    )
    assert manifest["provides_tools"] == [tool["name"] for tool in ctx.tools]


def test_pack_info_returns_json_string() -> None:
    result = json.loads(pack_info({"pack": "addyosmani"}))

    assert result["success"] is True
    assert result["human_gate_after"] == "plan"
    assert result["lifecycle"][2] == "implement"


def test_pack_info_reports_bundled_skill_provider() -> None:
    result = json.loads(pack_info({"pack": "aidlc"}))

    assert result["success"] is True
    skill = result["skills"]["implement"][0]
    assert skill["name"] == "aidlc-adapter"
    assert skill["provider"] == {
        "kind": "bundled",
        "reference": "aidlc-adapter",
    }
    assert skill["content_digest"]["source"] == "bundled-resource"
    assert skill["activation"] == "required"


def test_pack_info_reports_unknown_pack_without_raising() -> None:
    result = json.loads(pack_info({"pack": "missing"}))

    assert result == {
        "success": False,
        "error": "PackError",
        "message": "unknown bundled pack: 'missing'",
    }
