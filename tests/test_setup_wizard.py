from __future__ import annotations

import pytest

from wingstaff.setup_wizard import (
    SetupRequest,
    SetupWizardError,
    confirmed_start,
    create_board,
    list_boards,
    list_profiles,
)

PROFILES = {
    "define": "default",
    "plan": "default",
    "implement": "default",
    "verify": "default",
    "review": "default",
    "deliver": "default",
}


def payload() -> dict:
    return {
        "board_slug": "engineering",
        "target_repository": "/tmp/repo",
        "goal": "Add the requested feature",
        "stage_profiles": PROFILES,
        "pack": "addyosmani",
        "workflow_id": "wf-1",
    }


def test_preview_preserves_the_public_start_request_without_mutating() -> None:
    source = payload()

    preview = SetupRequest.from_payload(source).preview()

    assert preview["confirmed"] is False
    assert preview["request"]["board_slug"] == "engineering"
    assert preview["request"]["pack_name"] == "addyosmani"
    assert preview["request"]["stage_profiles"] == PROFILES
    assert source == payload()


def test_declined_setup_never_invokes_start() -> None:
    calls = []

    with pytest.raises(SetupWizardError, match="explicit confirmation"):
        confirmed_start(payload(), lambda **kwargs: calls.append(kwargs))

    assert calls == []


def test_confirmed_setup_invokes_existing_start_shape_once() -> None:
    source = {**payload(), "confirm": True}
    calls = []

    result = confirmed_start(source, lambda **kwargs: calls.append(kwargs) or "started")

    assert result == "started"
    assert len(calls) == 1
    assert calls[0]["pack_name"] == "addyosmani"
    assert calls[0]["workflow_id"] == "wf-1"
    assert "confirm" not in calls[0]


@pytest.mark.parametrize(
    "change",
    (
        {"stage_profiles": {"define": "default"}},
        {"pack": "unknown"},
        {"constraints_content": "x", "constraints_skill": "policy"},
        {"constraints_skill": "policy"},
    ),
)
def test_invalid_requests_fail_before_start(change: dict) -> None:
    source = {**payload(), **change, "confirm": True}
    calls = []

    with pytest.raises(SetupWizardError):
        confirmed_start(source, lambda **kwargs: calls.append(kwargs))

    assert calls == []


def test_inventory_uses_only_documented_hermes_commands() -> None:
    calls = []

    def run(command):
        calls.append(command)
        if command[-1] == "--json":
            return 0, '[{"slug":"default"}]'
        return 0, " ◆default         model        stopped\n  reviewer        model        stopped"

    assert list_boards(run) == [{"slug": "default"}]
    assert list_profiles(run) == ["default", "reviewer"]
    create_board(run, slug="project-alpha", name="Project Alpha")
    assert calls == [
        ("hermes", "kanban", "boards", "list", "--json"),
        ("hermes", "profile", "list"),
        (
            "hermes",
            "kanban",
            "boards",
            "create",
            "project-alpha",
            "--name",
            "Project Alpha",
        ),
    ]


def test_invalid_board_slug_is_rejected_without_command() -> None:
    calls = []
    with pytest.raises(SetupWizardError, match="kebab-case"):
        create_board(lambda command: calls.append(command) or (0, ""), slug="Bad Slug")
    assert calls == []
