from __future__ import annotations

import pytest

from wingstaff.packs import PackError, load_pack, validate_pack


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
