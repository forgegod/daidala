from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from daidala.pack_service import (
    MAX_SKILL_DOCUMENT_BYTES,
    PackConfirmationError,
    PackService,
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


def build_service(
    registry: MutableRegistry,
    *,
    runner=None,
    revision=None,
) -> PackService:
    return PackService(
        inventory=registry,
        registry=registry,
        revision_resolver=revision or (lambda pack: pack.source_revision),
        hermes_version_resolver=lambda: "0.19.0",
        command_runner=runner or (lambda _command: (0, "")),
    )


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
    assert document["content"].startswith("---\nname: aidlc-adapter")
    assert document["byte_size"] == len(document["content"].encode("utf-8"))
    assert document["byte_size"] <= MAX_SKILL_DOCUMENT_BYTES
    assert document["stages"] == [
        "define",
        "plan",
        "implement",
        "verify",
        "review",
        "deliver",
    ]
    assert "path" not in document


def test_content_rejects_undeclared_and_hides_missing_external_paths() -> None:
    service = build_service(MutableRegistry())

    with pytest.raises(UnknownPackSkillError, match="not declared"):
        service.skill_content("aidlc", "not-declared")

    missing = service.skill_content("addyosmani", "interview-me").to_dict()
    expected = next(
        skill for skill in required_skills(load_pack("addyosmani")) if skill.name == "interview-me"
    )

    assert missing == {
        "pack": "addyosmani",
        "skill": "interview-me",
        "stages": ["define"],
        "activation": ["conditional"],
        "bundled": False,
        "external": True,
        "install_target": expected.install,
        "expected_digest": expected.content_digest,
        "observed_digest": None,
        "installed": False,
        "ready": False,
        "available": False,
        "byte_size": None,
        "content": None,
        "unavailable_reason": "skill is not installed",
    }


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
        name = command[3].rsplit("/", 1)[-1]
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
