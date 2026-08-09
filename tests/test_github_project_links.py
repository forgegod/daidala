from __future__ import annotations

from pathlib import Path

import pytest

from daidala.github_project_links import (
    GitHubProjectLink,
    GitHubProjectLinkError,
    GitHubProjectLinksStore,
    GitHubProjectVerifier,
    parse_github_project_links,
)
from daidala.profile_files import atomic_write_private_text
from daidala.registrations import ControllerRegistration, RegistrationLimits


def registration() -> ControllerRegistration:
    return ControllerRegistration(
        project_id="project-one",
        checkout="/workspace/project-one",
        controller_profile="controller",
        board="board",
        repository_canonical="forgegod/daidala",
        verified_remote="git@github.com:forgegod/daidala.git",
        intake_credential="github-read",
        findings_credential="github-write",
        maintainers=("forgegod",),
        notification_adapter="hermes-gateway",
        notification_target="attended",
        notification_destination="telegram:target",
        evaluator_backend="restricted-container",
        evaluator_network="denied-by-default",
        limits=RegistrationLimits(1, 1, 0, 0, 0, 60),
    )


def link() -> GitHubProjectLink:
    return GitHubProjectLink("project-one", "ForgeGod", 1, "PVT_kwDOABCD")


def test_project_links_round_trip_private_store_and_noop(tmp_path: Path) -> None:
    store = GitHubProjectLinksStore(tmp_path)

    assert store.replace((link(),), (registration(),)) is True
    assert store.read((registration(),)) == (link(),)
    assert store.path.stat().st_mode & 0o777 == 0o600
    assert store.replace((link(),), (registration(),)) is False


def test_project_links_reject_duplicate_unknown_and_invalid_owner() -> None:
    duplicate = """\
schema: daidala.github-project-links/v1
links:
  - project_id: project-one
    owner: forgegod
    project_number: 1
    project_node_id: PVT_one
  - project_id: project-one
    owner: forgegod
    project_number: 2
    project_node_id: PVT_two
"""
    with pytest.raises(GitHubProjectLinkError, match="duplicate"):
        parse_github_project_links(duplicate)
    with pytest.raises(GitHubProjectLinkError, match="owner"):
        GitHubProjectLink("project-one", "bad_owner", 1, "PVT_one")
    with pytest.raises(GitHubProjectLinkError, match="non-control"):
        GitHubProjectLink("project-one", "forgegod", 1, "PVT_one\n")


def test_project_links_reject_unregistered_project(tmp_path: Path) -> None:
    store = GitHubProjectLinksStore(tmp_path)
    with pytest.raises(GitHubProjectLinkError, match="not registered"):
        store.replace((link(),), ())


def test_verifier_reports_missing_credential_bindings_as_a_bounded_blocker(
    tmp_path: Path,
) -> None:
    def runner(command: tuple[str, ...], _environment: object) -> tuple[int, str]:
        if command == ("gh", "--version"):
            return 0, "gh version 2.40.0"
        if command == ("gh", "project", "view", "--help"):
            return 0, "<number> --owner --format json"
        raise AssertionError(f"unexpected command: {command}")

    verifier = GitHubProjectVerifier(runner=runner, environ={})

    with pytest.raises(GitHubProjectLinkError, match="credential bindings are unavailable"):
        verifier.verify(
            registration=registration(),
            registration_file=tmp_path / "registration.yaml",
            owner="forgegod",
            project_number=1,
        )


def test_verifier_reports_missing_prerequisite_evidence_as_a_bounded_blocker(
    tmp_path: Path,
) -> None:
    def runner(command: tuple[str, ...], _environment: object) -> tuple[int, str]:
        if command == ("gh", "--version"):
            return 0, "gh version 2.40.0"
        if command == ("gh", "project", "view", "--help"):
            return 0, "<number> --owner --format json"
        raise AssertionError(f"unexpected command: {command}")

    atomic_write_private_text(
        tmp_path / "credential-bindings.yaml",
        """\
schema: daidala.credential-bindings/v1
project_id: project-one
bindings:
  - alias: github-read
    resolver: environment
    environment_variable: DAIDALA_GITHUB_READ_TOKEN
""",
        label="credential bindings",
    )
    verifier = GitHubProjectVerifier(
        runner=runner,
        environ={"DAIDALA_GITHUB_READ_TOKEN": "fixture"},
    )

    with pytest.raises(GitHubProjectLinkError, match="prerequisite evidence is unavailable"):
        verifier.verify(
            registration=registration(),
            registration_file=tmp_path / "registration.yaml",
            owner="forgegod",
            project_number=1,
        )
