from __future__ import annotations

import base64
import json
import stat
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

import daidala.repository_registration as repository_registration_module
from daidala.credentials import parse_credential_bindings
from daidala.errors import PolicyViolationError
from daidala.profile_files import ProfileFileError
from daidala.registrations import parse_controller_registration
from daidala.repository_registration import (
    DELIVERY_CREDENTIAL_ALIAS,
    REGISTRATION_DEFAULTS_FILENAME,
    WRITE_DEFAULTS_CONFIRMATION,
    RegistrationDefaultsService,
    RepositoryRegistrationError,
    RepositoryRegistrationService,
    parse_github_repository_url,
    parse_registration_defaults,
    resolve_profile_root,
)

REPOSITORY = Path(__file__).parents[1]
MANIFEST = (REPOSITORY / ".daidala" / "project.yaml").read_text(encoding="utf-8")


def defaults_payload() -> dict[str, object]:
    return {
        "schema": "daidala.repository-registration-defaults/v1",
        "credentials": {
            "intake": {
                "alias": "github-daidala-read-issues",
                "resolver": "environment",
                "environment_variable": "DAIDALA_GITHUB_INTAKE_TOKEN",
            },
            "findings": {
                "alias": "github-daidala-write-issues",
                "resolver": "environment",
                "environment_variable": "DAIDALA_GITHUB_FINDINGS_TOKEN",
            },
        },
        "approval": {"maintainers": ["forgegod"]},
        "notifications": {
            "adapter": "hermes-gateway",
            "target": "attended-daidala",
            "destination": "telegram:-1001234567890:17585",
        },
        "evaluator": {
            "backend": "restricted-container",
            "network": "denied-by-default",
        },
        "limits": {
            "active_cycles": 1,
            "goal_turns": 12,
            "delegated_workers": 3,
            "research_query_batches": 3,
            "extracted_sources": 3,
            "wall_clock_seconds": 3600,
        },
    }


def write_defaults(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "repository-registration-defaults.yaml"
    path.write_text(yaml.safe_dump(defaults_payload(), sort_keys=False), encoding="utf-8")
    path.chmod(0o600)


class GitHubRunner:
    def __init__(self, manifest: str = MANIFEST, *, wrap_manifest_content: bool = False) -> None:
        self.manifest = manifest
        self.wrap_manifest_content = wrap_manifest_content
        self.commands: list[tuple[str, ...]] = []
        self.environments: list[dict[str, str]] = []

    def __call__(
        self, command: tuple[str, ...], environment: Mapping[str, str]
    ) -> tuple[int, str]:
        self.commands.append(command)
        self.environments.append(dict(environment))
        if command == ("hermes", "profile", "list"):
            return 0, "◆ daidala-self-improvement\n"
        if command == ("hermes", "kanban", "boards", "list", "--json"):
            return 0, "[]"
        if command[:4] == ("hermes", "kanban", "boards", "create"):
            return 0, "created"
        if command == ("gh", "api", "repos/forgegod/daidala"):
            return 0, json.dumps(
                {
                    "full_name": "forgegod/daidala",
                    "ssh_url": "git@github.com:forgegod/daidala.git",
                    "clone_url": "https://github.com/forgegod/daidala.git",
                }
            )
        if command == (
            "gh",
            "api",
            "repos/forgegod/daidala/contents/.daidala/project.yaml",
        ):
            content = self.manifest.encode("utf-8")
            encoded = base64.b64encode(content).decode("ascii")
            if self.wrap_manifest_content:
                encoded = base64.encodebytes(content).decode("ascii")
            return 0, json.dumps(
                {
                    "type": "file",
                    "encoding": "base64",
                    "size": len(content),
                    "content": encoded,
                }
            )
        return 1, "private error that must not be surfaced"


@pytest.mark.parametrize(
    "value",
    (
        "https://github.com/forgegod/daidala",
        "https://github.com/forgegod/daidala.git",
        "ssh://git@github.com/forgegod/daidala.git",
        "git@github.com:forgegod/daidala.git",
        "github.com/forgegod/daidala",
    ),
)
def test_github_repository_urls_normalize_page_and_clone_forms(value: str) -> None:
    assert parse_github_repository_url(value) == "forgegod/daidala"


@pytest.mark.parametrize(
    "value",
    (
        "/private/repository",
        "https://gitlab.com/forgegod/daidala",
        "http://github.com/forgegod/daidala",
        "https://token@github.com/forgegod/daidala",
        "https://github.com/forgegod/daidala/issues/1",
        "https://github.com/forgegod/daidala?tab=readme",
        "https://github.com/forgegod/daidala#readme",
    ),
)
def test_github_repository_urls_reject_unsafe_or_non_repository_forms(value: str) -> None:
    with pytest.raises(RepositoryRegistrationError):
        parse_github_repository_url(value)


def test_registration_defaults_are_strict_and_validate_private_authority() -> None:
    payload = defaults_payload()
    defaults = parse_registration_defaults(yaml.safe_dump(payload, sort_keys=False))

    assert "board" not in defaults.to_dict()
    assert defaults.notification_destination.startswith("telegram:")
    payload["unknown"] = True
    with pytest.raises(PolicyViolationError, match="unknown"):
        parse_registration_defaults(yaml.safe_dump(payload, sort_keys=False))


def test_classify_missing_manifest_is_needs_bootstrap(tmp_path: Path) -> None:
    root = (tmp_path / "controller").resolve()
    write_defaults(root)

    class MissingManifestRunner(GitHubRunner):
        def __call__(
            self, command: tuple[str, ...], environment: Mapping[str, str]
        ) -> tuple[int, str]:
            self.commands.append(command)
            self.environments.append(dict(environment))
            if command == ("gh", "api", "repos/forgegod/orphan"):
                return 0, json.dumps(
                    {
                        "full_name": "forgegod/orphan",
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
            return 1, "private error that must not be surfaced"

    service = RepositoryRegistrationService(
        root,
        "daidala-dashboard",
        runner=MissingManifestRunner(),
        environ={"PATH": "/usr/bin"},
    )

    classification = service.classify("https://github.com/forgegod/orphan")
    payload = classification.to_dict()

    assert classification.status == "needs-bootstrap"
    assert classification.next_action == "bootstrap"
    assert classification.reason == "committed project policy is missing"
    assert payload["classification"] == "needs-bootstrap"
    assert payload["repository"] == "forgegod/orphan"
    assert payload["valid"] is False
    assert "private error" not in json.dumps(payload)


def test_preview_is_path_secret_and_private_destination_free(tmp_path: Path) -> None:
    root = (tmp_path / "controller").resolve()
    write_defaults(root)
    runner = GitHubRunner()
    service = RepositoryRegistrationService(
        root,
        "daidala-self-improvement",
        runner=runner,
        environ={"PATH": "/usr/bin", "GH_TOKEN": "must-not-reach-preview"},
    )

    preview = service.preview("https://github.com/forgegod/daidala")
    payload = preview.to_dict()
    rendered = json.dumps(payload)

    assert payload["repository"] == "forgegod/daidala"
    assert payload["project_id"] == "forgegod-daidala"
    assert payload["board"] == "daidala-forgegod-daidala"
    assert payload["board_action"] == "create"
    assert payload["writes"] == {
        "record_count": 2,
        "registration": True,
        "credential_bindings": True,
        "board": "create",
    }
    assert payload["release"] == {
        "allow_commit": False,
        "allow_push": False,
        "allow_publish": False,
    }
    assert payload["readiness"] == {
        "board_selected": True,
        "attended_target_configured": True,
        "credential_available": False,
    }
    assert str(root) not in rendered
    assert "telegram:" not in rendered
    assert "environment_variable" not in rendered
    assert "credential_alias" not in rendered
    assert "github-repository-delivery" not in rendered
    assert "GH_TOKEN" not in runner.environments[0]
    assert runner.environments[0]["GH_PROMPT_DISABLED"] == "1"


def test_preview_accepts_github_wrapped_base64_manifest_content(tmp_path: Path) -> None:
    root = (tmp_path / "controller").resolve()
    write_defaults(root)
    service = RepositoryRegistrationService(
        root,
        "daidala-self-improvement",
        runner=GitHubRunner(wrap_manifest_content=True),
        environ={"PATH": "/usr/bin"},
    )

    preview = service.preview("https://github.com/forgegod/daidala")

    assert preview.project_id == "forgegod-daidala"


def test_apply_reinspects_and_writes_exactly_two_private_records(tmp_path: Path) -> None:
    root = (tmp_path / "controller").resolve()
    write_defaults(root)
    runner = GitHubRunner()
    service = RepositoryRegistrationService(
        root, "daidala-self-improvement", runner=runner, environ={"PATH": "/usr/bin"}
    )
    url = "https://github.com/forgegod/daidala"
    preview = service.preview(url)

    applied = service.apply(
        url,
        expected_preview_digest=preview.digest,
        confirmation="register-repository",
    )

    project_root = root / "projects" / "forgegod-daidala"
    assert applied.digest == preview.digest
    assert sorted(path.name for path in project_root.iterdir()) == [
        "credential-bindings.yaml",
        "registration.yaml",
    ]
    registration_file = project_root / "registration.yaml"
    bindings_file = project_root / "credential-bindings.yaml"
    registration = parse_controller_registration(registration_file.read_text(encoding="utf-8"))
    bindings = parse_credential_bindings(bindings_file.read_text(encoding="utf-8"))
    assert registration.repository_canonical == "forgegod/daidala"
    assert registration.checkout == str(root / "work" / "forgegod-daidala")
    assert [row.alias for row in bindings.bindings] == [
        "github-daidala-read-issues",
        "github-daidala-write-issues",
        DELIVERY_CREDENTIAL_ALIAS,
    ]
    assert stat.S_IMODE(registration_file.stat().st_mode) == 0o600
    assert stat.S_IMODE(bindings_file.stat().st_mode) == 0o600
    assert runner.commands[-1] == (
        "hermes",
        "kanban",
        "boards",
        "create",
        "daidala-forgegod-daidala",
        "--default-workdir",
        str(root / "work" / "forgegod-daidala"),
    )
    assert len(runner.commands) == 9


def test_preview_rejects_a_board_registered_by_another_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = (tmp_path / "controller").resolve()
    other_root = (tmp_path / "other-controller").resolve()
    write_defaults(root)
    other_root.mkdir()
    monkeypatch.setattr(repository_registration_module, "list_profiles", lambda _run: ["other"])
    monkeypatch.setattr(
        repository_registration_module, "resolve_profile_root", lambda _profile, _run: other_root
    )
    monkeypatch.setattr(
        repository_registration_module,
        "list_controller_registrations",
        lambda path: (SimpleNamespace(board="daidala-forgegod-daidala"),)
        if path == other_root
        else (),
    )
    service = RepositoryRegistrationService(
        root, "daidala-self-improvement", runner=GitHubRunner(), environ={"PATH": "/usr/bin"}
    )

    with pytest.raises(
        RepositoryRegistrationError, match="already registered by a Daidala project"
    ):
        service.preview("https://github.com/forgegod/daidala")


def test_apply_removes_new_bindings_when_registration_publish_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = (tmp_path / "controller").resolve()
    write_defaults(root)
    service = RepositoryRegistrationService(
        root, "daidala-self-improvement", runner=GitHubRunner(), environ={"PATH": "/usr/bin"}
    )
    original_write = repository_registration_module.atomic_write_private_text

    def fail_registration_write(path: Path, content: str, *, label: str) -> None:
        if label == "controller registration":
            raise ProfileFileError("injected registration write failure")
        original_write(path, content, label=label)

    monkeypatch.setattr(
        repository_registration_module, "atomic_write_private_text", fail_registration_write
    )

    preview = service.preview("https://github.com/forgegod/daidala")
    with pytest.raises(ProfileFileError, match="injected registration write failure"):
        service.apply(
            "https://github.com/forgegod/daidala",
            expected_preview_digest=preview.digest,
            confirmation="register-repository",
        )

    project_root = root / "projects" / "forgegod-daidala"
    assert not (project_root / "registration.yaml").exists()
    assert not (project_root / "credential-bindings.yaml").exists()


def test_apply_rejects_stale_digest_without_writing(tmp_path: Path) -> None:
    root = (tmp_path / "controller").resolve()
    write_defaults(root)
    service = RepositoryRegistrationService(
        root,
        "daidala-self-improvement",
        runner=GitHubRunner(),
        environ={"PATH": "/usr/bin"},
    )

    with pytest.raises(RepositoryRegistrationError, match="stale"):
        service.apply(
            "https://github.com/forgegod/daidala",
            expected_preview_digest="0" * 64,
            confirmation="register-repository",
        )

    assert not (root / "projects").exists()


def test_manifest_identity_and_allowed_remote_are_fail_closed(tmp_path: Path) -> None:
    root = (tmp_path / "controller").resolve()
    write_defaults(root)
    mismatched = (
        MANIFEST.replace("canonical: forgegod/daidala", "canonical: other/daidala")
        .replace("git@github.com:forgegod/daidala.git", "git@github.com:other/daidala.git")
    )
    service = RepositoryRegistrationService(
        root,
        "daidala-self-improvement",
        runner=GitHubRunner(mismatched),
        environ={"PATH": "/usr/bin"},
    )
    with pytest.raises(RepositoryRegistrationError, match="canonical identity"):
        service.preview("https://github.com/forgegod/daidala")

    disallowed = MANIFEST.replace(
        "git@github.com:forgegod/daidala.git", "git@github.com:other/daidala.git"
    )
    service.runner = GitHubRunner(disallowed)
    with pytest.raises(PolicyViolationError, match="allowed remote URLs"):
        service.preview("https://github.com/forgegod/daidala")


def test_profile_root_resolves_only_from_hermes_profile_show(tmp_path: Path) -> None:
    root = (tmp_path / "profile").resolve()
    root.mkdir()
    commands: list[tuple[str, ...]] = []

    def run(command: tuple[str, ...]) -> tuple[int, str]:
        commands.append(command)
        return 0, f"Profile: controller\nPath: {root}\nModel: configured"

    assert resolve_profile_root("controller", run) == root
    assert commands == [("hermes", "profile", "show", "controller")]


def _write_registration_pair(root: Path, project_id: str = "example-site") -> None:
    project_root = root / "projects" / project_id
    project_root.mkdir(parents=True)
    registration = {
        "schema": "daidala.controller-registration/v2",
        "project_id": project_id,
        "checkout": "/tmp/example-checkout",
        "controller_profile": "controller",
        "board": "daidala-example-site",
        "repository_identity": {
            "canonical": "example-org/example-site",
            "verified_remote": "git@github.com:example-org/example-site.git",
        },
        "credentials": {
            "intake": "github-read-issues",
            "findings": "github-write-issues",
        },
        "approval": {"maintainers": ["example-operator"]},
        "notifications": {
            "adapter": "hermes-gateway",
            "target": "attended-example",
            "destination": "telegram:-1000000000000:1",
        },
        "evaluator": {
            "backend": "restricted-container",
            "network": "denied-by-default",
        },
        "limits": {
            "active_cycles": 1,
            "goal_turns": 12,
            "delegated_workers": 3,
            "research_query_batches": 3,
            "extracted_sources": 3,
            "wall_clock_seconds": 3600,
        },
    }
    bindings = {
        "schema": "daidala.credential-bindings/v1",
        "project_id": project_id,
        "bindings": [
            {
                "alias": "github-read-issues",
                "resolver": "environment",
                "environment_variable": "EXAMPLE_GITHUB_INTAKE_TOKEN",
            },
            {
                "alias": "github-write-issues",
                "resolver": "environment",
                "environment_variable": "EXAMPLE_GITHUB_FINDINGS_TOKEN",
            },
        ],
    }
    for name, payload in (
        ("registration.yaml", registration),
        ("credential-bindings.yaml", bindings),
    ):
        path = project_root / name
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        path.chmod(0o600)


def test_defaults_preview_reports_missing_file(tmp_path: Path) -> None:
    root = (tmp_path / "controller").resolve()
    root.mkdir()
    preview = RegistrationDefaultsService(root, "controller").preview()

    assert preview.valid is False
    assert preview.source == "missing"
    assert "not configured" in preview.reason
    assert preview.seed_available is False
    assert "checkout" not in json.dumps(preview.to_dict())


def test_defaults_preview_and_apply_from_source_text(tmp_path: Path) -> None:
    root = (tmp_path / "controller").resolve()
    root.mkdir()
    content = yaml.safe_dump(defaults_payload(), sort_keys=False)
    service = RegistrationDefaultsService(root, "controller")
    preview = service.preview(source_text=content)

    assert preview.valid is True
    assert preview.source == "input"
    assert preview.defaults is not None
    path = root / REGISTRATION_DEFAULTS_FILENAME
    assert not path.exists()

    applied = service.apply(
        expected_preview_digest=preview.digest,
        confirmation=WRITE_DEFAULTS_CONFIRMATION,
        source_text=content,
    )
    assert applied.digest == preview.digest
    assert path.is_file()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    loaded = parse_registration_defaults(path.read_text(encoding="utf-8"))
    assert loaded.intake_binding.alias == "github-daidala-read-issues"


def test_defaults_seed_from_one_registration(tmp_path: Path) -> None:
    root = (tmp_path / "controller").resolve()
    root.mkdir()
    _write_registration_pair(root)
    service = RegistrationDefaultsService(root, "controller")
    preview = service.preview(seed=True)

    assert preview.valid is True
    assert preview.source == "seed"
    assert preview.seed_project_id == "example-site"
    assert preview.defaults is not None
    assert preview.defaults.intake_binding.environment_variable == (
        "EXAMPLE_GITHUB_INTAKE_TOKEN"
    )
    service.apply(
        expected_preview_digest=preview.digest,
        confirmation=WRITE_DEFAULTS_CONFIRMATION,
        seed=True,
    )
    existing = service.preview()
    assert existing.valid is True
    assert existing.source == "existing"


def test_defaults_seed_requires_exactly_one_registration(tmp_path: Path) -> None:
    root = (tmp_path / "controller").resolve()
    root.mkdir()
    preview = RegistrationDefaultsService(root, "controller").preview(seed=True)
    assert preview.valid is False
    assert "exactly one" in preview.reason
