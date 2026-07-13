from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from daidala.cli import main
from daidala.packs import load_pack
from daidala.skills import (
    ProfileSkillContentRegistry,
    SkillRevisionError,
    content_registry_from_digests,
    hash_skill_directory,
    inventory_from_names,
    plan_pack_install,
    required_skills,
    version_satisfies,
)


def expected_digests() -> dict[str, str]:
    return {
        skill.name: skill.content_digest
        for skill in required_skills(load_pack("addyosmani"))
    }


def test_profile_registry_hashes_complete_skill_directory(tmp_path: Path) -> None:
    skill = tmp_path / "skills" / "category" / "idea-refine"
    (skill / "scripts").mkdir(parents=True)
    (skill / "SKILL.md").write_text("skill\n", encoding="utf-8")
    (skill / "scripts" / "run.sh").write_text("run\n", encoding="utf-8")

    registry = ProfileSkillContentRegistry(tmp_path / "skills")

    assert registry.installed_names() == frozenset({"idea-refine"})
    assert registry.content_digest("idea-refine") == hash_skill_directory(skill)
    assert registry.skill_markdown("idea-refine") == "skill\n"
    assert registry.content_digest("missing") is None
    assert registry.skill_markdown("missing") is None


def test_install_plan_blocks_source_content_host_and_recursive_drift() -> None:
    pack = load_pack("addyosmani")
    names = [skill.name for skill in required_skills(pack)]
    digests = expected_digests()
    digests["interview-me"] = "0" * 64

    plan = plan_pack_install(
        pack,
        inventory_from_names(names),
        content_registry_from_digests(digests),
        resolved_revision="0" * 40,
        hermes_version="0.19.0",
        recursive=True,
    )

    assert plan.ready_to_apply is False
    assert plan.revision_mismatches == ("interview-me",)
    assert any("source revision mismatch" in blocker for blocker in plan.blockers)
    assert any("does not satisfy" in blocker for blocker in plan.blockers)
    assert any("recursive" in blocker for blocker in plan.blockers)


def test_version_constraint_has_exact_bounded_semantics() -> None:
    constraint = ">=0.18.2,<0.19.0"

    assert version_satisfies("0.18.2", constraint)
    assert version_satisfies("0.18.9", constraint)
    assert not version_satisfies("0.18.1", constraint)
    assert not version_satisfies("0.19.0", constraint)


def test_cli_install_defaults_to_complete_dry_run_without_mutation(
    capsys: pytest.CaptureFixture[str],
) -> None:
    pack = load_pack("addyosmani")
    commands: list[tuple[str, ...]] = []

    result = main(
        ["packs", "install", "addyosmani"],
        inventory=inventory_from_names([]),
        registry=content_registry_from_digests({}),
        revision_resolver=lambda source: pack.source_revision,
        hermes_version="0.18.2",
        command_runner=lambda command: (commands.append(command) or 0, "unexpected"),
    )
    payload = json.loads(capsys.readouterr().out)

    assert result == 0
    assert payload["success"] is True
    assert payload["dry_run"] is True
    assert payload["source"] == "https://github.com/addyosmani/agent-skills"
    assert payload["pinned_revision"] == pack.source_revision
    assert len(payload["actions"]) == 20
    assert payload["actions"][0]["command"] == [
        "hermes",
        "skills",
        "install",
        "addyosmani/agent-skills/skills/interview-me",
        "--yes",
    ]
    assert commands == []


def test_cli_apply_uses_fake_hermes_boundary_and_post_verifies(
    capsys: pytest.CaptureFixture[str],
) -> None:
    pack = load_pack("addyosmani")
    digests = expected_digests()

    @dataclass
    class MutableInventory:
        names: set[str]

        def installed_names(self) -> frozenset[str]:
            return frozenset(self.names)

    @dataclass
    class MutableRegistry:
        values: dict[str, str]

        def content_digest(self, name: str) -> str | None:
            return self.values.get(name)

    inventory = MutableInventory(set())
    registry = MutableRegistry({})
    commands: list[tuple[str, ...]] = []

    def run(command: tuple[str, ...]) -> tuple[int, str]:
        name = command[3].rsplit("/", 1)[-1]
        commands.append(command)
        inventory.names.add(name)
        registry.values[name] = digests[name]
        return 0, f"installed {name}"

    result = main(
        ["packs", "install", "addyosmani", "--apply"],
        inventory=inventory,
        registry=registry,
        revision_resolver=lambda source: pack.source_revision,
        hermes_version="0.18.2",
        command_runner=run,
    )
    payload = json.loads(capsys.readouterr().out)

    assert result == 0
    assert payload["success"] is True
    assert payload["dry_run"] is False
    assert payload["actions"] == []
    assert len(payload["executed"]) == 20
    assert len(commands) == 20


def test_cli_recursive_request_fails_without_mutation(
    capsys: pytest.CaptureFixture[str],
) -> None:
    pack = load_pack("addyosmani")

    result = main(
        ["packs", "install", "addyosmani", "--recursive"],
        inventory=inventory_from_names([]),
        registry=content_registry_from_digests({}),
        revision_resolver=lambda source: pack.source_revision,
        hermes_version="0.18.2",
    )
    payload = json.loads(capsys.readouterr().out)

    assert result == 1
    assert payload["success"] is False
    assert payload["dry_run"] is True
    assert any("recursive" in blocker for blocker in payload["blockers"])


def test_cli_check_blocks_revision_mismatch_and_update_plan_never_mutates(
    capsys: pytest.CaptureFixture[str],
) -> None:
    pack = load_pack("addyosmani")
    names = [skill.name for skill in required_skills(pack)]
    digests = expected_digests()
    digests["idea-refine"] = "f" * 64

    check_result = main(
        ["packs", "check", "addyosmani"],
        inventory=inventory_from_names(names),
        registry=content_registry_from_digests(digests),
        revision_resolver=lambda source: pack.source_revision,
        hermes_version="0.18.2",
    )
    check = json.loads(capsys.readouterr().out)

    update_result = main(
        ["packs", "update-plan", "addyosmani"],
        inventory=inventory_from_names(names),
        registry=content_registry_from_digests(digests),
        revision_resolver=lambda source: "0" * 40,
        hermes_version="0.18.2",
    )
    update = json.loads(capsys.readouterr().out)

    assert check_result == 1
    assert check["success"] is False
    assert check["revision_mismatches"] == ["idea-refine"]
    assert update_result == 0
    assert update["success"] is True
    assert update["dry_run"] is True
    assert any("source revision mismatch" in blocker for blocker in update["blockers"])


def test_revision_error_is_actionable() -> None:
    pack = load_pack("addyosmani")
    registry = content_registry_from_digests({})

    with pytest.raises(
        SkillRevisionError,
        match="wingstaff packs update-plan addyosmani",
    ):
        from daidala.skills import require_pack_skill_revisions

        require_pack_skill_revisions(pack, registry)
