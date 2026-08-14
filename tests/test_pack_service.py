from __future__ import annotations

from dataclasses import dataclass, field

import pytest
import yaml

from daidala.pack_service import (
    MAX_SKILL_DOCUMENT_BYTES,
    PackConfirmationError,
    PackService,
    ProfileSkillAvailabilityState,
    SkillAction,
    StalePackPreviewError,
    UnknownPackSkillError,
)
from daidala.packs import load_pack
from daidala.skills import required_skills


@dataclass
class MutableRegistry:
    digests: dict[str, str] = field(default_factory=dict)
    documents: dict[str, str] = field(default_factory=dict)

    def installed_names(self) -> frozenset[str]:
        return frozenset(self.digests)

    def content_digest(self, name: str) -> str | None:
        return self.digests.get(name)

    def skill_markdown(self, name: str) -> str | None:
        return self.documents.get(name)


@dataclass
class MutableSkillState:
    disabled: set[str] = field(default_factory=set)
    updates: list[tuple[tuple[str, ...], bool]] = field(default_factory=list)

    def disabled_names(self) -> frozenset[str]:
        return frozenset(self.disabled)

    def set_enabled(self, names: tuple[str, ...], *, enabled: bool) -> None:
        self.updates.append((names, enabled))
        if enabled:
            self.disabled.difference_update(names)
        else:
            self.disabled.update(names)


def build_service(
    registry: MutableRegistry,
    *,
    runner=None,
    revision=None,
    skill_state: MutableSkillState | None = None,
) -> PackService:
    return PackService(
        inventory=registry,
        registry=registry,
        skill_state=skill_state or MutableSkillState(),
        revision_resolver=revision or (lambda pack: pack.source_revision),
        hermes_version_resolver=lambda: "0.19.0",
        command_runner=runner or (lambda _command: (0, "")),
    )


def test_profile_skill_state_writes_a_yaml_list_and_preserves_other_config(tmp_path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "model: example/model\nskills:\n  disabled:\n    - existing\n",
        encoding="utf-8",
    )
    config_path.chmod(0o600)
    state = ProfileSkillAvailabilityState(config_path)

    state.set_enabled(("new-skill",), enabled=False)
    state.set_enabled(("existing",), enabled=True)

    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert payload == {
        "model": "example/model",
        "skills": {"disabled": ["new-skill"]},
    }
    assert state.disabled_names() == frozenset({"new-skill"})


def test_validation_and_check_share_complete_pack_projection() -> None:
    service = build_service(MutableRegistry())

    validation = service.validate("aidlc").to_dict()
    check = service.check("aidlc").to_dict()

    assert validation["name"] == "aidlc"
    assert validation["lifecycle"] == [
        "define",
        "plan",
        "implement",
        "verify",
        "review",
        "deliver",
    ]
    assert len(validation["stages"]) == 6
    assert check["ready"] is True
    assert check["installable"] is True
    assert check["actions"] == []
    assert len(check["preview_digest"]) == 64
    assert all(
        skill["observed_digest"] == skill["expected_digest"]
        for stage in check["stages"]
        for skill in stage["skills"]
    )


def test_declared_bundled_skill_returns_exact_bounded_document() -> None:
    service = build_service(MutableRegistry())

    document = service.skill_content("aidlc", "aidlc-adapter").to_dict()

    assert document["available"] is True
    assert document["content_origin"] == "bundled"
    assert document["content"].startswith("---\nname: aidlc-adapter")
    assert document["byte_size"] == len(document["content"].encode("utf-8"))
    assert document["byte_size"] <= MAX_SKILL_DOCUMENT_BYTES
    assert document["enabled"] is True
    assert document["source_url"] == (
        "https://github.com/forgegod/daidala/tree/main/daidala/skills/aidlc-adapter"
    )
    assert document["stages"] == [
        "define",
        "plan",
        "implement",
        "verify",
        "review",
        "deliver",
    ]
    assert "path" not in document


def test_content_rejects_undeclared_and_hides_uninstalled_external_document() -> None:
    service = build_service(MutableRegistry())

    with pytest.raises(UnknownPackSkillError, match="not declared"):
        service.skill_content("aidlc", "not-declared")

    document = service.skill_content("addyosmani", "interview-me").to_dict()
    expected = next(
        skill for skill in required_skills(load_pack("addyosmani")) if skill.name == "interview-me"
    )

    assert document["pack"] == "addyosmani"
    assert document["skill"] == "interview-me"
    assert document["stages"] == ["define"]
    assert document["activation"] == ["conditional"]
    assert document["install_target"] == (
        "https://raw.githubusercontent.com/forgegod/addyosmani-agent-skills/"
        + load_pack("addyosmani").source_revision
        + "/skills/interview-me/SKILL.md"
    )
    assert document["expected_digest"] == expected.content_digest
    assert document["observed_digest"] is None
    assert document["installed"] is False
    assert document["ready"] is False
    assert document["available"] is False
    assert document["content_origin"] is None
    assert document["source_revision"] == load_pack("addyosmani").source_revision
    assert document["content"] is None
    assert document["byte_size"] is None
    assert document["unavailable_reason"] == "skill is not installed"
    assert document["enabled"] is None
    assert document["source_url"] == (
        "https://github.com/forgegod/addyosmani-agent-skills/tree/"
        + load_pack("addyosmani").source_revision
        + "/skills/interview-me"
    )
    assert "path" not in document


def test_installed_external_document_is_available() -> None:
    skill = next(
        skill for skill in required_skills(load_pack("addyosmani")) if skill.name == "interview-me"
    )
    assert skill.content_digest is not None
    service = build_service(
        MutableRegistry(
            digests={skill.name: skill.content_digest},
            documents={skill.name: "# installed\n"},
        )
    )

    document = service.skill_content("addyosmani", skill.name).to_dict()

    assert document["installed"] is True
    assert document["ready"] is True
    assert document["content_origin"] == "installed"
    assert document["content"] == "# installed\n"


def test_disabled_skill_is_installed_but_not_ready() -> None:
    state = MutableSkillState(disabled={"daidala:aidlc-adapter"})
    service = build_service(MutableRegistry(), skill_state=state)

    check = service.check("aidlc").to_dict()
    document = service.skill_content("aidlc", "aidlc-adapter").to_dict()

    assert check["ready"] is False
    assert check["actions"] == []
    assert check["activation_blockers"] == ["required skill 'aidlc-adapter' is disabled"]
    assert all(
        skill["installed"] is True and skill["enabled"] is False and skill["ready"] is False
        for stage in check["stages"]
        for skill in stage["skills"]
    )
    assert document["installed"] is True
    assert document["enabled"] is False
    assert document["ready"] is False


def test_individual_enable_and_disable_require_fresh_confirmed_preview() -> None:
    state = MutableSkillState(disabled={"daidala:aidlc-adapter"})
    service = build_service(MutableRegistry(), skill_state=state)
    preview = service.preview_action("aidlc", SkillAction.ENABLE, skill_name="aidlc-adapter")

    assert preview.to_dict()["skills"] == ["aidlc-adapter"]
    assert preview.to_dict()["action"] == "enable"

    with pytest.raises(PackConfirmationError, match="confirmation"):
        service.apply_action(
            "aidlc",
            SkillAction.ENABLE,
            skill_name="aidlc-adapter",
            expected_preview_digest=preview.preview_digest,
            confirm=False,
        )

    state.disabled.add("other-skill")
    result = service.apply_action(
        "aidlc",
        SkillAction.ENABLE,
        skill_name="aidlc-adapter",
        expected_preview_digest=preview.preview_digest,
        confirm=True,
    ).to_dict()

    assert result["affected"] == ["aidlc-adapter"]
    assert result["pack"]["ready"] is True
    assert state.updates == [(("daidala:aidlc-adapter",), True)]
    assert "other-skill" in state.disabled

    disable = service.preview_action("aidlc", SkillAction.DISABLE)
    assert disable.to_dict()["skills"] == ["aidlc-adapter"]
    disabled = service.apply_action(
        "aidlc",
        SkillAction.DISABLE,
        expected_preview_digest=disable.preview_digest,
        confirm=True,
    ).to_dict()
    assert disabled["pack"]["ready"] is False
    assert state.updates[-1] == (("daidala:aidlc-adapter",), False)


def test_external_skill_toggle_uses_its_bare_host_name() -> None:
    skill = next(
        skill for skill in required_skills(load_pack("addyosmani")) if skill.name == "interview-me"
    )
    assert skill.content_digest is not None
    state = MutableSkillState()
    service = build_service(
        MutableRegistry(digests={skill.name: skill.content_digest}),
        skill_state=state,
    )
    preview = service.preview_action("addyosmani", SkillAction.DISABLE, skill_name=skill.name)

    service.apply_action(
        "addyosmani",
        SkillAction.DISABLE,
        skill_name=skill.name,
        expected_preview_digest=preview.preview_digest,
        confirm=True,
    )

    assert state.updates == [(("interview-me",), False)]


def test_individual_install_only_applies_and_verifies_selected_skill() -> None:
    pack = load_pack("addyosmani")
    required = {skill.name: skill for skill in required_skills(pack)}
    registry = MutableRegistry()
    commands: list[tuple[str, ...]] = []

    def run(command: tuple[str, ...]) -> tuple[int, str]:
        commands.append(command)
        name = command[3].removesuffix("/SKILL.md").rsplit("/", 1)[-1]
        skill = required[name]
        assert skill.content_digest is not None
        registry.digests[skill.name] = skill.content_digest
        registry.documents[skill.name] = f"# {skill.name}\n"
        return 0, "installed"

    service = build_service(registry, runner=run)
    preview = service.preview_action("addyosmani", SkillAction.INSTALL, skill_name="interview-me")
    assert preview.to_dict()["skills"] == ["interview-me"]

    result = service.apply_action(
        "addyosmani",
        SkillAction.INSTALL,
        skill_name="interview-me",
        expected_preview_digest=preview.preview_digest,
        confirm=True,
    ).to_dict()

    assert result["affected"] == ["interview-me"]
    assert result["pack"]["ready"] is False
    assert len(result["pack"]["actions"]) == 19
    assert commands == [
        (
            "hermes",
            "skills",
            "install",
            (
                "https://raw.githubusercontent.com/forgegod/addyosmani-agent-skills/"
                f"{pack.source_revision}/skills/interview-me/SKILL.md"
            ),
            "--yes",
        )
    ]


def test_individual_install_accepts_digest_mismatch_as_a_warning() -> None:
    registry = MutableRegistry()

    def run(command: tuple[str, ...]) -> tuple[int, str]:
        name = command[3].removesuffix("/SKILL.md").rsplit("/", 1)[-1]
        registry.digests[name] = "f" * 64
        registry.documents[name] = f"# {name}\n"
        return 0, "installed"

    service = build_service(registry, runner=run)
    preview = service.preview_action("addyosmani", SkillAction.INSTALL, skill_name="interview-me")

    result = service.apply_action(
        "addyosmani",
        SkillAction.INSTALL,
        skill_name="interview-me",
        expected_preview_digest=preview.preview_digest,
        confirm=True,
    ).to_dict()

    assert result["affected"] == ["interview-me"]
    pack_result = result["pack"]
    assert isinstance(pack_result, dict)
    assert pack_result["revision_mismatches"] == ["interview-me"]
    assert not any("controlled update" in blocker for blocker in pack_result["blockers"])


def test_digest_mismatch_warns_without_blocking_pack_readiness() -> None:
    pack = load_pack("addyosmani")
    digests = {
        skill.name: skill.content_digest
        for skill in required_skills(pack)
        if skill.content_digest is not None
    }
    digests["idea-refine"] = "f" * 64

    check = build_service(MutableRegistry(digests=digests)).check("addyosmani").to_dict()

    assert check["ready"] is True
    assert check["installable"] is True
    assert check["revision_mismatches"] == ["idea-refine"]
    assert check["blockers"] == []


def test_oversized_document_returns_metadata_without_partial_content() -> None:
    skill = next(iter(required_skills(load_pack("addyosmani"))))
    assert skill.content_digest is not None
    registry = MutableRegistry(
        digests={skill.name: skill.content_digest},
        documents={skill.name: "x" * (MAX_SKILL_DOCUMENT_BYTES + 1)},
    )

    document = build_service(registry).skill_content("addyosmani", skill.name).to_dict()

    assert document["available"] is False
    assert document["byte_size"] == MAX_SKILL_DOCUMENT_BYTES + 1
    assert document["content"] is None
    assert document["unavailable_reason"] == "skill document exceeds 1048576 bytes"


def test_install_requires_confirmation_and_rejects_stale_preview_before_commands() -> None:
    registry = MutableRegistry()
    revision = {"value": load_pack("addyosmani").source_revision}
    commands: list[tuple[str, ...]] = []
    service = build_service(
        registry,
        runner=lambda command: (commands.append(command) or 0, ""),
        revision=lambda _pack: revision["value"],
    )
    preview = service.check("addyosmani")

    with pytest.raises(PackConfirmationError, match="confirmation"):
        service.install(
            "addyosmani",
            expected_preview_digest=preview.preview_digest,
            confirm=False,
        )

    revision["value"] = "0" * 40
    with pytest.raises(StalePackPreviewError, match="changed"):
        service.install(
            "addyosmani",
            expected_preview_digest=preview.preview_digest,
            confirm=True,
        )

    assert commands == []


def test_confirmed_install_executes_exact_actions_and_post_verifies() -> None:
    pack = load_pack("addyosmani")
    required = {skill.name: skill for skill in required_skills(pack)}
    registry = MutableRegistry()
    commands: list[tuple[str, ...]] = []

    def run(command: tuple[str, ...]) -> tuple[int, str]:
        commands.append(command)
        name = command[3].removesuffix("/SKILL.md").rsplit("/", 1)[-1]
        assert required[name].content_digest is not None
        registry.digests[name] = required[name].content_digest
        registry.documents[name] = f"# {name}\n"
        return 0, "installed"

    service = build_service(registry, runner=run)
    preview = service.check("addyosmani")
    result = service.install(
        "addyosmani",
        expected_preview_digest=preview.preview_digest,
        confirm=True,
    ).to_dict()

    assert result["success"] is True
    assert result["applied_preview_digest"] == preview.preview_digest
    assert len(result["executed"]) == len(required) == 20
    assert len(commands) == 20
    assert result["pack"]["ready"] is True
    assert result["pack"]["actions"] == []
