from __future__ import annotations

from pathlib import Path

import pytest

from daidala.projects import parse_project_manifest
from daidala.setup_wizard import (
    LocalProjectInitializer,
    SetupRequest,
    SetupWizardError,
    active_profile,
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
    assert active_profile(run) == "default"
    create_board(run, slug="project-alpha", name="Project Alpha")
    assert calls == [
        ("hermes", "kanban", "boards", "list", "--json"),
        ("hermes", "profile", "list"),
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


def test_active_profile_uses_only_an_inventory_validated_runtime_root_fallback() -> None:
    def run(_args):
        return (
            0,
            " ◆default         model        stopped\n"
            "  daidala-dashboard-fixture-20260727t141923z —        stopped",
        )

    assert (
        active_profile(
            run,
            fallback_name="daidala-dashboard-fixture-20260727t141923z",
        )
        == "daidala-dashboard-fixture-20260727t141923z"
    )

    assert active_profile(run, fallback_name="unknown") == "default"

    def no_active(_args):
        return 0, "  default         model        stopped\n  fixture         model        stopped"

    with pytest.raises(SetupWizardError, match="candidate 'unknown'.*not present"):
        active_profile(no_active, fallback_name="unknown")


def test_invalid_board_slug_is_rejected_without_command() -> None:
    calls = []
    with pytest.raises(SetupWizardError, match="kebab-case"):
        create_board(lambda command: calls.append(command) or (0, ""), slug="Bad Slug")
    assert calls == []


def test_local_project_preview_is_path_free_and_apply_initializes_policy(tmp_path: Path) -> None:
    root = (tmp_path / "controller").resolve()
    root.mkdir()
    calls: list[tuple[str, ...]] = []

    def run(command: tuple[str, ...]) -> tuple[int, str]:
        calls.append(command)
        if command == ("hermes", "kanban", "boards", "list", "--json"):
            return 0, "[]"
        if command[:3] == ("git", "init", "--quiet"):
            Path(command[-1]).mkdir()
        return 0, ""

    initializer = LocalProjectInitializer(root, run)
    preview = initializer.preview("example-app", "Example app")

    assert preview.to_dict()["project_id"] == "example-app"
    assert "target_repository" not in preview.to_dict()
    assert calls == [("hermes", "kanban", "boards", "list", "--json")]

    applied = initializer.apply("example-app", "Example app", preview.digest)

    target = root / "work" / "example-app"
    manifest_path = target / ".daidala/project.yaml"
    manifest = parse_project_manifest(manifest_path.read_text(encoding="utf-8"))
    assert applied == preview
    assert manifest.repository.forge == "local"
    assert manifest.repository.canonical == "local/example-app"
    assert calls[-1] == (
        "hermes",
        "kanban",
        "boards",
        "create",
        "daidala-local-example-app",
        "--name",
        "Example app",
        "--default-workdir",
        str(target),
    )


def test_local_project_initializer_rejects_stale_preview_without_mutation(tmp_path: Path) -> None:
    root = (tmp_path / "controller").resolve()
    root.mkdir()
    calls: list[tuple[str, ...]] = []
    initializer = LocalProjectInitializer(
        root,
        lambda command: calls.append(command) or (0, "[]"),
    )

    with pytest.raises(SetupWizardError, match="inputs changed"):
        initializer.apply("example-app", "Example app", "0" * 64)

    assert not (root / "work").exists()
    assert calls == [("hermes", "kanban", "boards", "list", "--json")]
