from __future__ import annotations

from pathlib import Path

import wingstaff
from wingstaff.schemas import START


def setup_contract() -> str:
    return (Path(wingstaff.__file__).parent / "skills" / "setup" / "SKILL.md").read_text(
        encoding="utf-8"
    )


def test_setup_skill_pins_exact_current_start_schema() -> None:
    instructions = setup_contract()
    properties = START["parameters"]["properties"]
    required = START["parameters"]["required"]

    assert set(properties) == {
        "board_slug",
        "target_repository",
        "goal",
        "stage_profiles",
        "pack",
        "workflow_id",
        "constraints_content",
        "constraints_skill",
        "constraints_skill_digest",
    }
    assert required == [
        "board_slug",
        "target_repository",
        "goal",
        "stage_profiles",
        "workflow_id",
    ]
    for parameter in properties:
        assert f"`{parameter}`" in instructions
    for stage in START["parameters"]["properties"]["stage_profiles"]["required"]:
        assert f"`{stage}`" in instructions


def test_setup_skill_requires_preview_and_explicit_confirmation_before_start() -> None:
    instructions = setup_contract()

    preview = instructions.index("Build and display the exact request")
    confirmation = instructions.index("explicitly confirm that exact preview")
    start = instructions.index("call `wingstaff_start` exactly once")
    assert preview < confirmation < start
    assert "A general request to\n   configure Wingstaff is not confirmation" in instructions
    assert "If the preview changes" in instructions


def test_setup_skill_keeps_dashboard_and_non_dashboard_requests_identical() -> None:
    instructions = setup_contract()

    assert "This skill works without the web dashboard" in instructions
    assert "its\n   absence never changes the request or blocks setup" in instructions
    assert "Do not add\naliases" in instructions
    assert (
        "Setup prepares and starts; `wingstaff:orchestrate` remains the\nworker contract"
        in instructions
    )
