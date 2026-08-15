from __future__ import annotations

import pytest

from daidala.packs import PackError, SkillActivationMode, load_pack, validate_pack


def pack_with_skills(skills: list[dict[str, str]]) -> dict[str, object]:
    catalog = [
        {key: value for key, value in skill.items() if key != "activation"}
        for skill in skills
    ]
    bindings = []
    for skill in skills:
        binding = {"name": skill["name"]}
        if "activation" in skill:
            binding["activation"] = skill["activation"]
        bindings.append(binding)
    return {
        "schema_version": 2,
        "name": "test-pack",
        "source": "https://github.com/owner/repo",
        "source_revision": "a" * 40,
        "skills": catalog,
        "lifecycle": {
            "human_gate_after": "plan",
            "stages": [
                {"id": stage, "skills": [dict(binding) for binding in bindings]}
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
    raw = pack_with_skills(
        [
            {
                "name": name,
                "activation": "required",
                "install": f"owner/repo/{name}",
                "content_digest": digest,
            }
        ]
    )

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
    assert len(pack.skills) == 1
    assert pack.skills[0].bundled == "aidlc-adapter"
    assert not pack.skills[0].is_external
    assert all(
        tuple(skill.name for skill in stage.skills) == ("aidlc-adapter",)
        for stage in pack.stages
    )


def test_skill_reference_requires_exactly_one_provider() -> None:
    raw = pack_with_skills(
        [
            {
                "name": "skill",
                "activation": "required",
                "install": "owner/repo/skill",
                "bundled": "skill",
                "content_digest": "b" * 64,
            }
        ]
    )

    with pytest.raises(PackError, match="exactly one of install or bundled"):
        validate_pack(raw)


def test_skill_install_target_must_match_name() -> None:
    raw = pack_with_skills(
        [
            {
                "name": "expected",
                "activation": "required",
                "install": "owner/repo/other",
                "content_digest": "b" * 64,
            }
        ]
    )

    with pytest.raises(PackError, match="does not match install target"):
        validate_pack(raw)


def test_skill_install_target_rejects_unsafe_path_segments() -> None:
    raw = pack_with_skills(
        [
            {
                "name": "skill",
                "activation": "required",
                "install": "owner/repo/x/../skill",
                "content_digest": "b" * 64,
            }
        ]
    )

    with pytest.raises(PackError, match="lowercase slug path segments"):
        validate_pack(raw)


def test_schema_v1_is_rejected_without_compatibility_parsing() -> None:
    raw = pack_with_skills(
        [
            {
                "name": "skill",
                "activation": "required",
                "install": "owner/repo/skill",
                "content_digest": "b" * 64,
            }
        ]
    )
    raw["schema_version"] = 1

    with pytest.raises(PackError, match="schema_version must be 2"):
        validate_pack(raw)


def test_catalog_only_skill_is_valid_without_a_stage_binding() -> None:
    raw = pack_with_skills(
        [
            {
                "name": "bound",
                "activation": "required",
                "install": "owner/repo/bound",
                "content_digest": "b" * 64,
            }
        ]
    )
    catalog = raw["skills"]
    assert isinstance(catalog, list)
    catalog.append(
        {
            "name": "catalog-only",
            "install": "owner/repo/catalog-only",
            "content_digest": "c" * 64,
        }
    )

    pack = validate_pack(raw)

    assert [skill.name for skill in pack.skills] == ["bound", "catalog-only"]
    assert {skill.name for stage in pack.stages for skill in stage.skills} == {"bound"}


def test_duplicate_catalog_names_are_rejected() -> None:
    raw = pack_with_skills(
        [
            {
                "name": "skill",
                "activation": "required",
                "install": "owner/repo/skill",
                "content_digest": "b" * 64,
            }
        ]
    )
    catalog = raw["skills"]
    assert isinstance(catalog, list)
    catalog.append(dict(catalog[0]))

    with pytest.raises(PackError, match="duplicate catalog skill name"):
        validate_pack(raw)


def test_stage_binding_must_resolve_catalog_and_own_no_provider_fields() -> None:
    raw = pack_with_skills(
        [
            {
                "name": "skill",
                "activation": "required",
                "install": "owner/repo/skill",
                "content_digest": "b" * 64,
            }
        ]
    )
    lifecycle = raw["lifecycle"]
    assert isinstance(lifecycle, dict)
    stages = lifecycle["stages"]
    assert isinstance(stages, list)
    stages[0]["skills"][0]["name"] = "missing"

    with pytest.raises(PackError, match="unknown catalog skill"):
        validate_pack(raw)

    stages[0]["skills"][0] = {
        "name": "skill",
        "activation": "required",
        "install": "owner/repo/skill",
    }
    with pytest.raises(PackError, match="unknown field: install"):
        validate_pack(raw)


def test_gate_cannot_be_after_implementation() -> None:
    raw = pack_with_skills(
        [
            {
                "name": "skill",
                "activation": "required",
                "install": "owner/repo/skill",
                "content_digest": "b" * 64,
            }
        ]
    )
    lifecycle = raw["lifecycle"]
    assert isinstance(lifecycle, dict)
    lifecycle["human_gate_after"] = "review"

    with pytest.raises(PackError, match="before implementation"):
        validate_pack(raw)
