from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from daidala.repository_bootstrap import (
    BOOTSTRAP_BRANCH,
    RepositoryBootstrapError,
    RepositoryBootstrapService,
    build_bootstrap_files,
)
from daidala.repository_registration import CLASSIFICATION_NEEDS_BOOTSTRAP
from tests.test_repository_registration import write_defaults


class BootstrapRunner:
    def __init__(self) -> None:
        self.commands: list[tuple[str, ...]] = []
        self.inputs: list[str | None] = []
        self.supports_stdin = True
        self.blobs = 0
        self.published = False

    def __call__(
        self,
        command: tuple[str, ...],
        environment: Mapping[str, str],
        stdin: str | None = None,
    ) -> tuple[int, str]:
        self.commands.append(command)
        self.inputs.append(stdin)
        if command[:3] == ("gh", "api", "repos/forgegod/orphan"):
            return 0, json.dumps(
                {
                    "full_name": "forgegod/orphan",
                    "default_branch": "main",
                    "ssh_url": "git@github.com:forgegod/orphan.git",
                    "clone_url": "https://github.com/forgegod/orphan.git",
                }
            )
        if command == (
            "gh",
            "api",
            "repos/forgegod/orphan/contents/.daidala/project.yaml",
        ):
            return 1, json.dumps({"message": "Not Found", "status": "404"})
        if command == ("gh", "api", "repos/forgegod/orphan/git/ref/heads/main"):
            return 0, json.dumps({"object": {"sha": "a" * 40}})
        if command == (
            "gh",
            "api",
            f"repos/forgegod/orphan/git/ref/heads/{BOOTSTRAP_BRANCH}",
        ):
            return 1, json.dumps({"message": "Not Found", "status": "404"})
        if command == ("gh", "api", f"repos/forgegod/orphan/git/commits/{'a' * 40}"):
            return 0, json.dumps({"tree": {"sha": "b" * 40}})
        if command[:5] == ("gh", "api", "--method", "POST", "repos/forgegod/orphan/git/blobs"):
            self.blobs += 1
            return 0, json.dumps({"sha": f"{self.blobs:040d}"})
        if command[:5] == ("gh", "api", "--method", "POST", "repos/forgegod/orphan/git/trees"):
            return 0, json.dumps({"sha": "c" * 40})
        if command[:5] == (
            "gh",
            "api",
            "--method",
            "POST",
            "repos/forgegod/orphan/git/commits",
        ):
            return 0, json.dumps({"sha": "d" * 40})
        if command[:5] == ("gh", "api", "--method", "POST", "repos/forgegod/orphan/git/refs"):
            self.published = True
            return 0, json.dumps({"ref": f"refs/heads/{BOOTSTRAP_BRANCH}"})
        return 1, "unexpected command"


def test_build_bootstrap_files_are_strict_and_conservative() -> None:
    files = build_bootstrap_files("forgegod/orphan")
    paths = [row.path for row in files]
    assert paths == [".daidala/project.yaml", ".daidala/constraints.yaml"]
    assert "allow_commit: false" in files[0].content
    assert "allow_push: false" in files[0].content
    assert "forgegod/orphan" in files[0].content
    assert "schema: daidala.workflow-constraints/v1" in files[1].content


def test_bootstrap_preview_and_apply_publish_non_default_branch(tmp_path: Path) -> None:
    root = (tmp_path / "controller").resolve()
    write_defaults(root)
    runner = BootstrapRunner()
    service = RepositoryBootstrapService(
        root,
        "daidala-dashboard",
        runner=runner,
        environ={"PATH": "/usr/bin"},
    )
    url = "https://github.com/forgegod/orphan"

    preview = service.preview(url)
    payload = preview.to_dict()

    assert preview.target_branch == BOOTSTRAP_BRANCH
    assert preview.default_branch == "main"
    assert payload["classification"] == CLASSIFICATION_NEEDS_BOOTSTRAP
    assert payload["writes"]["registration"] is False
    assert payload["writes"]["default_branch"] is False
    assert "private" not in json.dumps(payload)

    applied = service.apply(
        url,
        expected_preview_digest=preview.digest,
        confirmation="bootstrap-repository",
    )

    assert applied.commit_sha == "d" * 40
    assert applied.branch == BOOTSTRAP_BRANCH
    assert runner.published is True
    assert runner.blobs == 2
    assert not (root / "projects").exists()


def test_bootstrap_rejects_stale_digest_and_existing_branch(tmp_path: Path) -> None:
    root = (tmp_path / "controller").resolve()
    write_defaults(root)
    runner = BootstrapRunner()
    service = RepositoryBootstrapService(
        root, "daidala-dashboard", runner=runner, environ={"PATH": "/usr/bin"}
    )
    url = "https://github.com/forgegod/orphan"

    with pytest.raises(RepositoryBootstrapError, match="stale"):
        service.apply(
            url,
            expected_preview_digest="0" * 64,
            confirmation="bootstrap-repository",
        )

    class ExistingBranchRunner(BootstrapRunner):
        def __call__(
            self,
            command: tuple[str, ...],
            environment: Mapping[str, str],
            stdin: str | None = None,
        ) -> tuple[int, str]:
            if command == (
                "gh",
                "api",
                f"repos/forgegod/orphan/git/ref/heads/{BOOTSTRAP_BRANCH}",
            ):
                return 0, json.dumps({"object": {"sha": "e" * 40}})
            return super().__call__(command, environment, stdin)

    service.runner = ExistingBranchRunner()
    with pytest.raises(RepositoryBootstrapError, match="already exists"):
        service.preview(url)
