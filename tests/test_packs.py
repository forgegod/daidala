from __future__ import annotations

import pytest

from wingstaff.packs import PackError, load_pack, validate_pack


def test_addyosmani_pack_has_stable_lifecycle_and_preimplementation_gate() -> None:
    pack = load_pack("addyosmani")

    assert pack.lifecycle == ("define", "plan", "implement", "verify", "review", "deliver")
    assert pack.human_gate_after == "plan"
    assert all(stage.skills for stage in pack.stages)


def test_skill_install_target_must_match_name() -> None:
    raw = {
        "schema_version": 1,
        "name": "broken",
        "source": "https://example.invalid/skills",
        "lifecycle": {
            "human_gate_after": "plan",
            "stages": [
                {"id": stage, "skills": [{"name": "expected", "install": "owner/repo/other"}]}
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
        "source": "https://example.invalid/skills",
        "lifecycle": {
            "human_gate_after": "review",
            "stages": [
                {
                    "id": stage,
                    "skills": [{"name": "skill", "install": "owner/repo/skill"}],
                }
                for stage in ("define", "plan", "implement", "verify", "review", "deliver")
            ],
        },
    }

    with pytest.raises(PackError, match="before implementation"):
        validate_pack(raw)
