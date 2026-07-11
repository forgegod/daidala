from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from wingstaff import tools
from wingstaff.packs import load_pack
from wingstaff.service import WorkflowService
from wingstaff.skills import (
    HermesSkillInventory,
    MissingSkillsError,
    SkillInventoryError,
    content_registry_from_digests,
    inventory_from_names,
    pack_skill_digests,
    require_pack_skills,
    required_skills,
)
from wingstaff.store import WorkflowStore


def test_required_skills_are_exact_deduplicated_and_lifecycle_ordered() -> None:
    requirements = required_skills(load_pack("addyosmani"))

    assert len(requirements) == 20
    assert requirements[0].name == "interview-me"
    assert requirements[-1].name == "deprecation-and-migration"
    assert [skill.name for skill in requirements].count("test-driven-development") == 1


def test_pack_skill_digests_include_bundled_and_external_skills() -> None:
    external = pack_skill_digests(load_pack("addyosmani"))
    bundled = pack_skill_digests(load_pack("aidlc"))

    assert len(external) == 20
    assert [name for name, _ in bundled] == ["aidlc-adapter"]
    assert len(bundled[0][1]) == 64


def test_missing_exact_name_reports_actionable_install_target() -> None:
    pack = load_pack("addyosmani")
    names = {skill.name for skill in required_skills(pack)}
    names.remove("interview-me")
    names.add("interview_me")

    with pytest.raises(MissingSkillsError) as captured:
        require_pack_skills(pack, inventory_from_names(names))

    assert [skill.name for skill in captured.value.missing] == ["interview-me"]
    assert "interview-me" in str(captured.value)
    assert "addyosmani/agent-skills/skills/interview-me" in str(captured.value)


def test_complete_inventory_passes_without_mutation() -> None:
    pack = load_pack("addyosmani")
    names = frozenset(skill.name for skill in required_skills(pack))

    @dataclass
    class FakeInventory:
        calls: int = 0

        def installed_names(self) -> frozenset[str]:
            self.calls += 1
            return names

    inventory = FakeInventory()
    result = require_pack_skills(pack, inventory)

    assert len(result) == 20
    assert inventory.calls == 1
    assert names == frozenset(skill.name for skill in required_skills(pack))


def test_hermes_inventory_reads_exact_names_from_json() -> None:
    payload = json.dumps(
        {
            "success": True,
            "skills": [
                {"name": "interview-me", "description": "Interview"},
                {"name": "planning-and-task-breakdown", "description": "Plan"},
            ],
        }
    )

    inventory = HermesSkillInventory(list_skills=lambda: payload)

    assert inventory.installed_names() == frozenset(
        {"interview-me", "planning-and-task-breakdown"}
    )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ("not-json", "invalid JSON"),
        (json.dumps({"success": False, "error": "scan failed"}), "scan failed"),
        (json.dumps({"success": True}), "omitted the skills list"),
        (json.dumps({"success": True, "skills": [{}]}), "invalid name"),
    ],
)
def test_hermes_inventory_rejects_invalid_host_results(
    payload: str, message: str
) -> None:
    inventory = HermesSkillInventory(list_skills=lambda: payload)

    with pytest.raises(SkillInventoryError, match=message):
        inventory.installed_names()


def test_missing_skill_blocks_tool_start_without_creating_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack = load_pack("addyosmani")
    names = {skill.name for skill in required_skills(pack)}
    names.remove("interview-me")
    service = WorkflowService(
        WorkflowStore(tmp_path / "data"),
        skill_inventory=inventory_from_names(names),
        skill_content_registry=content_registry_from_digests(
            {skill.name: skill.content_digest for skill in required_skills(pack)}
        ),
        id_factory=lambda: "must-not-be-created",
    )
    monkeypatch.setattr(tools, "_service_factory", lambda: service)

    result = json.loads(
        tools.start(
            {
                "target_repository": str(tmp_path / "target"),
                "board_slug": "wingstaff-test",
                "goal": "must stop before draft creation",
            }
        )
    )

    assert result["success"] is False
    assert result["error"] == "MissingSkillsError"
    assert "addyosmani/agent-skills/skills/interview-me" in result["message"]
    assert service.store.list_all() == ()
