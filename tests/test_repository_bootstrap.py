from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from daidala.projects import parse_project_manifest
from daidala.repository_bootstrap import (
    BOOTSTRAP_BRANCH,
    BootstrapReceiptStore,
    RepositoryBootstrapError,
    RepositoryBootstrapService,
    build_bootstrap_files,
    build_local_bootstrap_files,
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
        if command[:4] == ("gh", "pr", "create", "--repo"):
            assert command[4] == "forgegod/orphan"
            assert "--base" in command and command[command.index("--base") + 1] == "main"
            assert "--head" in command and command[command.index("--head") + 1] == BOOTSTRAP_BRANCH
            return 0, "https://github.com/forgegod/orphan/pull/12"
        return 1, "unexpected command"


def test_build_bootstrap_files_are_strict_and_conservative() -> None:
    files = build_bootstrap_files("forgegod/orphan")
    paths = [row.path for row in files]
    assert paths == [".daidala/project.yaml", ".daidala/constraints.yaml"]
    assert "allow_commit: false" in files[0].content
    assert "allow_push: false" in files[0].content
    assert "forgegod/orphan" in files[0].content
    assert "schema: daidala.workflow-constraints/v1" in files[1].content


def test_build_local_bootstrap_files_are_strict_and_have_no_remote() -> None:
    files = build_local_bootstrap_files("example-app")
    manifest = parse_project_manifest(files[0].content)

    assert [row.path for row in files] == [".daidala/project.yaml", ".daidala/constraints.yaml"]
    assert manifest.project_id == "example-app"
    assert manifest.repository.forge == "local"
    assert manifest.repository.canonical == "local/example-app"
    assert manifest.repository.allowed_remote_urls == ()
    assert manifest.allow_commit is False
    assert manifest.allow_push is False


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
    assert payload["writes"]["pull_request"] is True
    assert payload["links"] == {
        "branch": "https://github.com/forgegod/orphan/tree/chore/daidala-bootstrap-project-policy",
        "daidala_tree": (
            "https://github.com/forgegod/orphan/tree/"
            "chore/daidala-bootstrap-project-policy/.daidala"
        ),
        "compare_pull_request": (
            "https://github.com/forgegod/orphan/compare/"
            "main...chore/daidala-bootstrap-project-policy"
            "?expand=1"
            "&title=chore%3A%20bootstrap%20Daidala%20project%20policy"
            "&body=Adds%20conservative%20.daidala%20policy%20generated%20by%20Daidala%20bootstrap."
            "%20Review%20and%20merge%20to%20enable%20registration."
        ),
    }
    assert "private" not in json.dumps(payload)

    applied = service.apply(
        url,
        expected_preview_digest=preview.digest,
        confirmation="bootstrap-repository",
    )

    assert applied.commit_sha == "d" * 40
    assert applied.branch == BOOTSTRAP_BRANCH
    assert applied.pull_request == "https://github.com/forgegod/orphan/pull/12"
    assert runner.published is True
    assert runner.blobs == 2
    assert not (root / "projects").exists()
    receipts = BootstrapReceiptStore(root).read()
    assert len(receipts) == 1
    assert receipts[0].repository_canonical == "forgegod/orphan"
    assert receipts[0].pull_request == "https://github.com/forgegod/orphan/pull/12"
    assert receipts[0].open_url() == "https://github.com/forgegod/orphan/pull/12"


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


def test_bootstrap_receipt_hides_registered_repositories(tmp_path: Path) -> None:
    root = (tmp_path / "controller").resolve()
    write_defaults(root)
    runner = BootstrapRunner()
    service = RepositoryBootstrapService(
        root, "daidala-dashboard", runner=runner, environ={"PATH": "/usr/bin"}
    )
    service.apply(
        "https://github.com/forgegod/orphan",
        expected_preview_digest=service.preview("https://github.com/forgegod/orphan").digest,
        confirmation="bootstrap-repository",
    )
    store = BootstrapReceiptStore(root)

    visible = store.pending_for(exclude_repositories=set())
    hidden = store.pending_for(exclude_repositories={"forgegod/orphan"})

    assert [row.repository_canonical for row in visible] == ["forgegod/orphan"]
    assert hidden == ()
    store.remove("forgegod/orphan")
    assert store.read() == ()
