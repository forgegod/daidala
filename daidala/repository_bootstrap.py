"""Preview-confirmed bootstrap of committed Daidala policy on a non-default branch."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .constraints import DEFAULT_CONSTRAINT_TEMPLATE, parse_workflow_constraints
from .errors import PolicyViolationError
from .live_adapters import RuntimeRunner, run_runtime_command, safe_runtime_environment
from .packs import load_pack, pack_content_digest
from .projects import ProjectManifest, parse_project_manifest
from .repository_registration import (
    CLASSIFICATION_NEEDS_BOOTSTRAP,
    MAX_GITHUB_OUTPUT_BYTES,
    RepositoryRegistrationService,
    parse_github_repository_url,
)

BOOTSTRAP_PREVIEW_SCHEMA = "daidala.repository-bootstrap-preview/v1"
# Conventional Commits–style branch name (type/description), not a commit message.
BOOTSTRAP_BRANCH = "chore/daidala-bootstrap-project-policy"
BOOTSTRAP_CONFIRMATION = "bootstrap-repository"
PROJECT_POLICY_PATH = ".daidala/project.yaml"
CONSTRAINTS_PATH = ".daidala/constraints.yaml"
_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,127}$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
_BRANCH = re.compile(r"^[A-Za-z0-9._/-]{1,200}$")


class RepositoryBootstrapError(PolicyViolationError):
    """A repository bootstrap request cannot be previewed or applied safely."""


@dataclass(frozen=True)
class BootstrapFile:
    path: str
    content: str
    digest: str

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "bytes": len(self.content.encode("utf-8")),
            "digest": self.digest,
        }


@dataclass(frozen=True)
class BootstrapPreview:
    """Public bootstrap proposal bound by an exact digest."""

    repository_canonical: str
    controller_profile: str
    project_id: str
    target_branch: str
    default_branch: str
    base_commit_sha: str
    files: tuple[BootstrapFile, ...]
    manifest_digest: str
    schema: str = BOOTSTRAP_PREVIEW_SCHEMA

    @property
    def digest(self) -> str:
        payload = {
            "schema": self.schema,
            "repository": self.repository_canonical,
            "controller_profile": self.controller_profile,
            "project_id": self.project_id,
            "target_branch": self.target_branch,
            "default_branch": self.default_branch,
            "base_commit_sha": self.base_commit_sha,
            "files": [
                {"path": row.path, "digest": row.digest, "content": row.content}
                for row in self.files
            ],
            "manifest_digest": self.manifest_digest,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, object]:
        links = bootstrap_github_links(
            repository_canonical=self.repository_canonical,
            target_branch=self.target_branch,
            default_branch=self.default_branch,
        )
        return {
            "schema": self.schema,
            "valid": True,
            "classification": CLASSIFICATION_NEEDS_BOOTSTRAP,
            "next_action": "bootstrap",
            "repository": self.repository_canonical,
            "controller_profile": self.controller_profile,
            "project_id": self.project_id,
            "target_branch": self.target_branch,
            "default_branch": self.default_branch,
            "base_commit_sha": self.base_commit_sha,
            "files": [row.to_dict() for row in self.files],
            "manifest_digest": self.manifest_digest,
            "preview_digest": self.digest,
            "links": links,
            "writes": {
                "branch": self.target_branch,
                "file_count": len(self.files),
                "registration": False,
                "default_branch": False,
                "pull_request": False,
            },
            "next_step": (
                "Open the compare/pull-request link, merge on GitHub outside Daidala, "
                "then inspect and register the repository."
            ),
        }


@dataclass(frozen=True)
class BootstrapResult:
    preview: BootstrapPreview
    commit_sha: str
    branch: str

    def to_dict(self) -> dict[str, object]:
        payload = self.preview.to_dict()
        payload["applied"] = True
        payload["commit_sha"] = self.commit_sha
        payload["branch"] = self.branch
        return payload


@dataclass
class RepositoryBootstrapService:
    """Generate conservative Daidala policy and publish it on a non-default branch."""

    data_root: Path
    controller_profile: str
    runner: RuntimeRunner = field(default_factory=lambda: run_runtime_command)
    environ: Mapping[str, str] = field(default_factory=lambda: dict(os.environ))

    def __post_init__(self) -> None:
        if not isinstance(self.data_root, Path) or not self.data_root.is_absolute():
            raise RepositoryBootstrapError(
                "repository bootstrap data root must be an absolute path"
            )
        self.data_root = self.data_root.resolve()
        if not isinstance(self.controller_profile, str) or not _SLUG.fullmatch(
            self.controller_profile
        ):
            raise RepositoryBootstrapError("repository bootstrap profile is invalid")

    def preview(self, github_url: str) -> BootstrapPreview:
        registration = RepositoryRegistrationService(
            self.data_root,
            self.controller_profile,
            runner=self.runner,
            environ=self.environ,
        )
        classification = registration.classify(github_url)
        if classification.status != CLASSIFICATION_NEEDS_BOOTSTRAP:
            raise RepositoryBootstrapError(
                classification.reason
                if classification.reason
                else "repository does not need bootstrap"
            )
        claimed = parse_github_repository_url(github_url)
        metadata = self._github_json(("gh", "api", f"repos/{claimed}"), "metadata")
        canonical = metadata.get("full_name")
        default_branch = metadata.get("default_branch")
        if (
            not isinstance(canonical, str)
            or not _REPOSITORY.fullmatch(canonical)
            or not isinstance(default_branch, str)
            or not default_branch
            or "/" in default_branch
            or default_branch == BOOTSTRAP_BRANCH
        ):
            raise RepositoryBootstrapError("GitHub repository metadata response is invalid")
        if default_branch.startswith("daidala/"):
            raise RepositoryBootstrapError("repository default branch cannot be a Daidala branch")
        ref = self._github_json(
            ("gh", "api", f"repos/{canonical}/git/ref/heads/{default_branch}"),
            "default branch",
        )
        object_payload = ref.get("object")
        if not isinstance(object_payload, dict):
            raise RepositoryBootstrapError("GitHub default branch response is invalid")
        base_sha = object_payload.get("sha")
        if not isinstance(base_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", base_sha):
            raise RepositoryBootstrapError("GitHub default branch commit is invalid")
        try:
            existing = self._github_json(
                ("gh", "api", f"repos/{canonical}/git/ref/heads/{BOOTSTRAP_BRANCH}"),
                "bootstrap branch",
            )
        except RepositoryBootstrapError:
            existing = None
        if existing is not None:
            raise RepositoryBootstrapError(
                f"bootstrap branch {BOOTSTRAP_BRANCH!r} already exists; "
                "merge or delete it outside Daidala"
            )
        files = build_bootstrap_files(canonical)
        manifest = parse_project_manifest(files[0].content)
        return BootstrapPreview(
            repository_canonical=canonical,
            controller_profile=self.controller_profile,
            project_id=manifest.project_id,
            target_branch=BOOTSTRAP_BRANCH,
            default_branch=default_branch,
            base_commit_sha=base_sha,
            files=files,
            manifest_digest=manifest.digest,
        )

    def apply(
        self,
        github_url: str,
        *,
        expected_preview_digest: str,
        confirmation: str,
    ) -> BootstrapResult:
        if confirmation != BOOTSTRAP_CONFIRMATION:
            raise RepositoryBootstrapError(
                f"bootstrap requires literal confirmation {BOOTSTRAP_CONFIRMATION!r}"
            )
        preview = self.preview(github_url)
        if expected_preview_digest != preview.digest:
            raise RepositoryBootstrapError("repository bootstrap preview is stale")
        commit_sha = self._publish_branch(preview)
        return BootstrapResult(preview=preview, commit_sha=commit_sha, branch=preview.target_branch)

    def _publish_branch(self, preview: BootstrapPreview) -> str:
        canonical = preview.repository_canonical
        base_commit = self._github_json(
            ("gh", "api", f"repos/{canonical}/git/commits/{preview.base_commit_sha}"),
            "base commit",
        )
        base_tree = base_commit.get("tree")
        if not isinstance(base_tree, dict) or not isinstance(base_tree.get("sha"), str):
            raise RepositoryBootstrapError("GitHub base commit tree is invalid")
        tree_entries: list[dict[str, str]] = []
        for row in preview.files:
            blob = self._github_json(
                (
                    "gh",
                    "api",
                    "--method",
                    "POST",
                    f"repos/{canonical}/git/blobs",
                    "--input",
                    "-",
                ),
                "blob",
                stdin=json.dumps(
                    {
                        "content": base64.b64encode(row.content.encode("utf-8")).decode("ascii"),
                        "encoding": "base64",
                    }
                ),
            )
            blob_sha = blob.get("sha")
            if not isinstance(blob_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", blob_sha):
                raise RepositoryBootstrapError("GitHub blob response is invalid")
            tree_entries.append(
                {
                    "path": row.path,
                    "mode": "100644",
                    "type": "blob",
                    "sha": blob_sha,
                }
            )
        tree_payload = {
            "base_tree": base_tree["sha"],
            "tree": tree_entries,
        }
        tree = self._github_json(
            (
                "gh",
                "api",
                "--method",
                "POST",
                f"repos/{canonical}/git/trees",
                "--input",
                "-",
            ),
            "tree",
            stdin=json.dumps(tree_payload),
        )
        tree_sha = tree.get("sha")
        if not isinstance(tree_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", tree_sha):
            raise RepositoryBootstrapError("GitHub tree response is invalid")
        commit_payload = {
            "message": (
                "chore(daidala): bootstrap committed project policy\n\n"
                "Introduce conservative .daidala policy on a non-default branch. "
                "Merge outside Daidala before registration."
            ),
            "tree": tree_sha,
            "parents": [preview.base_commit_sha],
        }
        commit = self._github_json(
            (
                "gh",
                "api",
                "--method",
                "POST",
                f"repos/{canonical}/git/commits",
                "--input",
                "-",
            ),
            "commit",
            stdin=json.dumps(commit_payload),
        )
        commit_sha = commit.get("sha")
        if not isinstance(commit_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
            raise RepositoryBootstrapError("GitHub commit response is invalid")
        self._github_json(
            (
                "gh",
                "api",
                "--method",
                "POST",
                f"repos/{canonical}/git/refs",
                "-f",
                f"ref=refs/heads/{preview.target_branch}",
                "-f",
                f"sha={commit_sha}",
            ),
            "branch ref",
        )
        return commit_sha

    def _github_json(
        self,
        command: tuple[str, ...],
        label: str,
        *,
        stdin: str | None = None,
    ) -> dict[str, object]:
        environment = safe_runtime_environment(self.environ)
        environment.update({"GH_PROMPT_DISABLED": "1", "GIT_TERMINAL_PROMPT": "0"})
        if stdin is None:
            code, output = self.runner(command, environment)
        else:
            code, output = _run_with_stdin(command, environment, stdin, self.runner)
        if (
            isinstance(code, bool)
            or not isinstance(code, int)
            or not isinstance(output, str)
            or len(output.encode("utf-8")) > MAX_GITHUB_OUTPUT_BYTES
            or code != 0
        ):
            raise RepositoryBootstrapError(
                f"GitHub repository {label} is unavailable through the host authentication"
            )
        try:
            payload = json.loads(output)
        except json.JSONDecodeError as error:
            raise RepositoryBootstrapError(
                f"GitHub repository {label} response is invalid"
            ) from error
        if not isinstance(payload, dict):
            raise RepositoryBootstrapError(f"GitHub repository {label} response must be an object")
        return payload


def bootstrap_github_links(
    *,
    repository_canonical: str,
    target_branch: str,
    default_branch: str,
) -> dict[str, str]:
    """Build public GitHub browser URLs for operator follow-up outside Daidala."""

    if not isinstance(repository_canonical, str) or not _REPOSITORY.fullmatch(
        repository_canonical
    ):
        raise RepositoryBootstrapError("bootstrap repository identity is invalid")
    if (
        not isinstance(target_branch, str)
        or not isinstance(default_branch, str)
        or not _BRANCH.fullmatch(target_branch)
        or not _BRANCH.fullmatch(default_branch)
        or target_branch == default_branch
    ):
        raise RepositoryBootstrapError("bootstrap branch identities are invalid")
    root = f"https://github.com/{repository_canonical}"
    # GitHub accepts slash-containing branch names as path segments in tree/compare URLs.
    return {
        "branch": f"{root}/tree/{target_branch}",
        "daidala_tree": f"{root}/tree/{target_branch}/.daidala",
        "compare_pull_request": (
            f"{root}/compare/{default_branch}...{target_branch}"
            "?expand=1"
            "&title=chore%3A%20bootstrap%20Daidala%20project%20policy"
            "&body=Adds%20conservative%20.daidala%20policy%20generated%20by%20Daidala%20bootstrap."
            "%20Review%20and%20merge%20to%20enable%20registration."
        ),
    }


def build_bootstrap_files(canonical: str) -> tuple[BootstrapFile, ...]:
    """Build conservative committed policy files for one GitHub repository."""

    if not isinstance(canonical, str) or not _REPOSITORY.fullmatch(canonical):
        raise RepositoryBootstrapError("bootstrap repository identity is invalid")
    owner, name = canonical.split("/", 1)
    project_id = _project_id(owner, name)
    return _build_policy_files(
        project_id,
        {
            "forge": "github",
            "canonical": canonical,
            "allowed_remote_urls": [
                f"git@github.com:{canonical}.git",
                f"https://github.com/{canonical}.git",
            ],
        },
    )


def build_local_bootstrap_files(project_id: str) -> tuple[BootstrapFile, ...]:
    """Build conservative committed policy files for a local-only Git repository."""

    if not isinstance(project_id, str) or not _SLUG.fullmatch(project_id):
        raise RepositoryBootstrapError("local project ID is invalid")
    return _build_policy_files(
        project_id,
        {
            "forge": "local",
            "canonical": f"local/{project_id}",
            "allowed_remote_urls": [],
        },
    )


def _build_policy_files(
    project_id: str, repository: dict[str, object]
) -> tuple[BootstrapFile, ...]:
    addy = load_pack("addyosmani")
    aidlc = load_pack("aidlc")
    constraints = DEFAULT_CONSTRAINT_TEMPLATE
    parse_workflow_constraints(constraints)
    manifest_payload: dict[str, Any] = {
        "schema": "daidala.project/v1",
        "project_id": project_id,
        "repository": repository,
        "workflow": {
            "allowed_packs": [
                {
                    "name": "addyosmani",
                    "source_revision": addy.source_revision,
                    "content_digest": pack_content_digest("addyosmani"),
                },
                {
                    "name": "aidlc",
                    "source_revision": aidlc.source_revision,
                    "content_digest": pack_content_digest("aidlc"),
                },
            ],
            "default_pack": "addyosmani",
            "default_constraints": {"source": CONSTRAINTS_PATH},
        },
        "verification": {
            "suites": [
                {
                    "id": "repository",
                    "kind": "deterministic",
                    "commands": ["true"],
                    "timeout_seconds": 60,
                }
            ]
        },
        "improvement": {
            "mutable_paths": ["src/**", "docs/**", ".daidala/constraints.yaml"],
            "protected_paths": [".daidala/project.yaml", ".git/**", ".env"],
            "maximum_changed_files": 20,
            "approval_roles": ["maintainer"],
        },
        "intake": {
            "adapter": "github-issues",
            "eligible_categories": [
                "regression",
                "improvement",
                "compatibility",
                "skill-gap",
                "research-candidate",
            ],
        },
        "release": {
            "allow_commit": False,
            "allow_push": False,
            "allow_publish": False,
        },
    }
    # Validate by round-tripping through the strict parser.
    rendered_manifest = yaml.safe_dump(
        manifest_payload,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
    manifest = parse_project_manifest(rendered_manifest)
    assert isinstance(manifest, ProjectManifest)
    files = (
        _file(PROJECT_POLICY_PATH, rendered_manifest),
        _file(CONSTRAINTS_PATH, constraints if constraints.endswith("\n") else constraints + "\n"),
    )
    return files


def _file(path: str, content: str) -> BootstrapFile:
    encoded = content.encode("utf-8")
    return BootstrapFile(
        path=path,
        content=content,
        digest=hashlib.sha256(encoded).hexdigest(),
    )


def _project_id(owner: str, repository: str) -> str:
    raw = f"{owner}-{repository}".lower().replace(".", "-").replace("_", "-")
    collapsed = re.sub(r"-+", "-", raw).strip("-")
    if not _SLUG.fullmatch(collapsed):
        raise RepositoryBootstrapError("derived project ID is invalid")
    return collapsed


def _run_with_stdin(
    command: tuple[str, ...],
    environment: Mapping[str, str],
    stdin: str,
    runner: RuntimeRunner,
) -> tuple[int, str]:
    """Send JSON bodies to gh for tree/commit creation while keeping runners injectable."""

    supports_stdin = getattr(runner, "supports_stdin", False)
    if supports_stdin is True:
        return runner(command, environment, stdin)  # type: ignore[call-arg, misc]
    if runner is run_runtime_command:
        import subprocess

        completed = subprocess.run(  # noqa: S603 - fixed command tuple from callers
            list(command),
            input=stdin,
            text=True,
            capture_output=True,
            env=dict(environment),
            check=False,
        )
        output = (
            completed.stdout
            if completed.returncode == 0
            else (completed.stderr or completed.stdout)
        )
        return completed.returncode, output
    # Test doubles ignore stdin body and receive only command/env.
    return runner(command, environment)
