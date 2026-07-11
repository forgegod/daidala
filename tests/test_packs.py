from __future__ import annotations

import pytest

from wingstaff.packs import PackError, SkillActivationMode, load_pack, validate_pack


def pack_with_skills(skills: list[dict[str, str]]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "name": "test-pack",
        "source": "https://github.com/owner/repo",
        "source_revision": "a" * 40,
        "lifecycle": {
            "human_gate_after": "plan",
            "stages": [
                {"id": stage, "skills": [dict(skill) for skill in skills]}
                for stage in ("define", "plan", "implement", "verify", "review", "deliver")
            ],
        },
    }


@pytest.mark.parametrize(
    ("name", "digest", "message"),
    [
        ("../skill", "b" * 64, "lowercase slug"),
        ("skill", "B" * 64, "lowercase hex digest"),
    ],
)
def test_skill_identity_fields_are_path_safe_and_canonical(
    name: str, digest: str, message: str
) -> None:
    raw = {
        "schema_version": 1,
        "name": "broken",
        "source": "https://github.com/owner/repo",
        "source_revision": "a" * 40,
        "lifecycle": {
            "human_gate_after": "plan",
            "stages": [
                {
                    "id": stage,
                    "skills": [
                        {
                            "name": name,
                            "activation": "required",
                            "install": f"owner/repo/{name}",
                            "content_digest": digest,
                        }
                    ],
                }
                for stage in ("define", "plan", "implement", "verify", "review", "deliver")
            ],
        },
    }

    with pytest.raises(PackError, match=message):
        validate_pack(raw)


def test_addyosmani_pack_has_stable_lifecycle_and_preimplementation_gate() -> None:
    pack = load_pack("addyosmani")

    assert pack.lifecycle == ("define", "plan", "implement", "verify", "review", "deliver")
    assert pack.human_gate_after == "plan"
    assert all(stage.skills for stage in pack.stages)


def test_bundled_packs_declare_exact_activation_modes() -> None:
    addyosmani = load_pack("addyosmani")
    expected = {
        "define": {
            "interview-me": SkillActivationMode.CONDITIONAL,
            "idea-refine": SkillActivationMode.CONDITIONAL,
            "spec-driven-development": SkillActivationMode.REQUIRED,
        },
        "plan": {"planning-and-task-breakdown": SkillActivationMode.REQUIRED},
        "implement": {
            name: SkillActivationMode.CONDITIONAL
            for name in (
                "incremental-implementation",
                "test-driven-development",
                "source-driven-development",
                "doubt-driven-development",
            )
        },
        "verify": {
            name: SkillActivationMode.CONDITIONAL
            for name in (
                "test-driven-development",
                "debugging-and-error-recovery",
                "browser-testing-with-devtools",
            )
        },
        "review": {
            "code-review-and-quality": SkillActivationMode.REQUIRED,
            "code-simplification": SkillActivationMode.CONDITIONAL,
            "security-and-hardening": SkillActivationMode.CONDITIONAL,
            "performance-optimization": SkillActivationMode.CONDITIONAL,
        },
        "deliver": {
            name: SkillActivationMode.CONDITIONAL
            for name in (
                "git-workflow-and-versioning",
                "ci-cd-and-automation",
                "documentation-and-adrs",
                "observability-and-instrumentation",
                "shipping-and-launch",
                "deprecation-and-migration",
            )
        },
    }

    assert {
        stage.id: {skill.name: skill.activation for skill in stage.skills}
        for stage in addyosmani.stages
    } == expected

    aidlc = load_pack("aidlc")
    assert all(
        skill.activation is SkillActivationMode.REQUIRED
        for stage in aidlc.stages
        for skill in stage.skills
    )


@pytest.mark.parametrize("activation", [None, "sometimes"])
def test_skill_activation_is_required_and_closed(activation: str | None) -> None:
    skill = {
        "name": "skill",
        "install": "owner/repo/skill",
        "content_digest": "b" * 64,
    }
    if activation is not None:
        skill["activation"] = activation

    with pytest.raises(PackError, match="activation"):
        validate_pack(pack_with_skills([skill]))


def test_stage_rejects_more_than_manifest_decision_limit() -> None:
    skills = [
        {
            "name": f"skill-{index}",
            "activation": "conditional",
            "install": f"owner/repo/skill-{index}",
            "content_digest": f"{index:064x}",
        }
        for index in range(33)
    ]

    with pytest.raises(PackError, match="more than 32 skills"):
        validate_pack(pack_with_skills(skills))


def test_aidlc_pack_uses_one_pack_owned_skill_without_external_install() -> None:
    pack = load_pack("aidlc")

    assert pack.lifecycle == ("define", "plan", "implement", "verify", "review", "deliver")
    assert pack.human_gate_after == "plan"
    assert {skill.name for stage in pack.stages for skill in stage.skills} == {
        "aidlc-adapter"
    }
    assert all(
        skill.bundled == "aidlc-adapter" and not skill.is_external
        for stage in pack.stages
        for skill in stage.skills
    )


def test_skill_reference_requires_exactly_one_provider() -> None:
    raw = {
        "schema_version": 1,
        "name": "broken",
        "source": "https://github.com/owner/repo",
        "source_revision": "a" * 40,
        "lifecycle": {
            "human_gate_after": "plan",
            "stages": [
                {
                    "id": stage,
                    "skills": [
                        {
                            "name": "skill",
                            "activation": "required",
                            "install": "owner/repo/skill",
                            "bundled": "skill",
                            "content_digest": "b" * 64,
                        }
                    ],
                }
                for stage in ("define", "plan", "implement", "verify", "review", "deliver")
            ],
        },
    }

    with pytest.raises(PackError, match="exactly one of install or bundled"):
        validate_pack(raw)


def test_skill_install_target_must_match_name() -> None:
    raw = {
        "schema_version": 1,
        "name": "broken",
        "source": "https://github.com/owner/repo",
        "source_revision": "a" * 40,
        "lifecycle": {
            "human_gate_after": "plan",
            "stages": [
                {
                    "id": stage,
                    "skills": [
                        {
                            "name": "expected",
                            "activation": "required",
                            "install": "owner/repo/other",
                            "content_digest": "b" * 64,
                        }
                    ],
                }
                for stage in ("define", "plan", "implement", "verify", "review", "deliver")
            ],
        },
    }

    with pytest.raises(PackError, match="does not match install target"):
        validate_pack(raw)


def test_gate_cannot_be_after_implementation() -> None:
    raw = {
        "schema_version": 1,
        "name": "broken",
        "source": "https://github.com/owner/repo",
        "source_revision": "a" * 40,
        "lifecycle": {
            "human_gate_after": "review",
            "stages": [
                {
                    "id": stage,
                    "skills": [
                        {
                            "name": "skill",
                            "activation": "required",
                            "install": "owner/repo/skill",
                            "content_digest": "b" * 64,
                        }
                    ],
                }
                for stage in ("define", "plan", "implement", "verify", "review", "deliver")
            ],
        },
    }

    with pytest.raises(PackError, match="before implementation"):
        validate_pack(raw)
