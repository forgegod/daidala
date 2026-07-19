from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pytest

from daidala import cli
from daidala.prerequisites import (
    CHECKLIST_DIGEST,
    CHECKS,
    CheckStatus,
    PrerequisiteReport,
    run_prerequisite_diagnosis,
)

ROOT = Path(__file__).parents[1]
REVISION = "a" * 40
PROJECT_ID = "PVT_kwDOExample"
PROJECT_URL = "https://github.com/users/forgegod/projects/1"


def _registration_content(checkout: Path) -> str:
    return f"""\
schema: daidala.controller-registration/v1
project_id: forgegod-daidala
checkout: {checkout}
controller_profile: daidala-self-improvement
board: daidala-forgegod-daidala
repository_identity:
  canonical: forgegod/daidala
  verified_remote: git@github.com:forgegod/daidala.git
credentials:
  intake: github-daidala-read-issues
  findings: github-daidala-write-issues
approval:
  maintainers: [forgegod]
notifications:
  adapter: hermes-gateway
  target: attended-daidala
evaluator:
  backend: restricted-container
  network: denied-by-default
limits:
  active_cycles: 1
  goal_turns: 12
  delegated_workers: 3
  research_query_batches: 3
  extracted_sources: 3
  wall_clock_seconds: 3600
"""


BINDINGS = """\
schema: daidala.credential-bindings/v1
project_id: forgegod-daidala
bindings:
  - alias: github-daidala-read-issues
    resolver: environment
    environment_variable: DAIDALA_GITHUB_INTAKE_TOKEN
  - alias: github-daidala-write-issues
    resolver: environment
    environment_variable: DAIDALA_GITHUB_FINDINGS_TOKEN
"""


def _evidence() -> dict[str, object]:
    denied = ["contents-write", "administration", "merge", "release", "deployment"]
    return {
        "schema": "daidala.prerequisite-evidence/v1",
        "project_id": "forgegod-daidala",
        "approved_controller_revision": REVISION,
        "sticky_profile": "hermes-vc",
        "credential_capabilities": [
            {
                "alias": "github-daidala-read-issues",
                "capability": "github-intake",
                "allowed": [
                    "read-organization",
                    "read-project",
                    "read-public-repository",
                ],
                "denied": denied,
                "expires_on": "2026-12-31",
                "read_probe_receipt": "receipt-intake",
                "write_probe_identity": None,
            },
            {
                "alias": "github-daidala-write-issues",
                "capability": "github-findings",
                "allowed": ["metadata-read", "issues-read-write"],
                "denied": denied,
                "expires_on": "2026-12-31",
                "read_probe_receipt": "receipt-findings",
                "write_probe_identity": "approved-controlled-issue",
            },
        ],
        "github_project": {
            "owner": "forgegod",
            "project_id": PROJECT_ID,
            "url": PROJECT_URL,
            "fields": [
                "category",
                "priority",
                "readiness",
                "claim-owner",
                "claim-lease-expiry",
                "cycle-id",
                "workflow-id",
                "terminal-comparison-outcome",
            ],
            "read_probe_receipt": "receipt-project",
        },
        "notification": {
            "adapter": "hermes-gateway",
            "target_alias": "attended-daidala",
            "authorized_maintainer": "forgegod",
            "receipt_id": "receipt-notification",
        },
        "evaluator": {
            "backend": "restricted-container",
            "network": "denied-by-default",
            "image_identity": "example/evaluator@sha256:" + "b" * 64,
            "fresh_home": True,
            "network_denied": True,
            "controller_credentials_absent": True,
            "bounded_mounts": True,
            "receipt_id": "receipt-evaluator",
        },
    }


@dataclass
class Fixture:
    repository: Path
    manifest: Path
    profile_root: Path
    registration: Path


@pytest.fixture
def configured_fixture(tmp_path: Path) -> Fixture:
    repository = tmp_path / "repository"
    manifest = repository / ".daidala" / "project.yaml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text((ROOT / ".daidala/project.yaml").read_text(encoding="utf-8"))
    profile_root = tmp_path / "profile"
    registration = profile_root / "projects" / "forgegod-daidala" / "registration.yaml"
    registration.parent.mkdir(parents=True)
    registration.write_text(_registration_content(repository), encoding="utf-8")
    registration.with_name("credential-bindings.yaml").write_text(BINDINGS, encoding="utf-8")
    registration.with_name("prerequisite-evidence.json").write_text(
        json.dumps(_evidence()), encoding="utf-8"
    )
    return Fixture(repository, manifest, profile_root, registration)


@dataclass
class FakeRunner:
    fixture: Fixture
    malformed_command: tuple[str, ...] | None = None
    malformed_output: str = "not-json"
    unavailable_prefix: tuple[str, ...] | None = None
    calls: list[tuple[tuple[str, ...], Mapping[str, str]]] = field(default_factory=list)

    def __call__(
        self, command: tuple[str, ...], environment: Mapping[str, str]
    ) -> tuple[int, str]:
        self.calls.append((command, environment))
        if (
            self.unavailable_prefix is not None
            and command[: len(self.unavailable_prefix)] == self.unavailable_prefix
        ):
            return 127, "unavailable"
        if command == self.malformed_command:
            return 0, self.malformed_output
        if command[:4] == ("git", "-C", str(self.fixture.repository), "remote"):
            return 0, "git@github.com:forgegod/daidala.git"
        if command[:3] == ("git", "-C", str(self.fixture.repository)):
            return (0, REVISION) if command[-2:] == ("rev-parse", "HEAD") else (0, "")
        plugin_dir = self.fixture.profile_root / "plugins" / "daidala"
        if command[:3] == ("git", "-C", str(plugin_dir)):
            return (0, REVISION) if command[-2:] == ("rev-parse", "HEAD") else (0, "")
        if command == ("hermes", "profile", "list"):
            active = (
                "daidala-self-improvement"
                if environment.get("HERMES_HOME") == str(self.fixture.profile_root)
                else "hermes-vc"
            )
            controller_marker = "◆" if active == "daidala-self-improvement" else " "
            sticky_marker = "◆" if active == "hermes-vc" else " "
            return 0, (
                f" {controller_marker}daidala-self-improvement\n"
                f" {sticky_marker}hermes-vc"
            )
        if command == ("hermes", "profile", "show", "daidala-self-improvement"):
            return 0, f"Profile: daidala-self-improvement\nPath:    {self.fixture.profile_root}"
        if command[-4:] == ("plugins", "list", "--no-bundled", "--json"):
            return 0, json.dumps([{"name": "daidala", "status": "enabled"}])
        if command == ("hermes", "kanban", "boards", "list", "--json"):
            return 0, json.dumps(
                [
                    {
                        "slug": "daidala-forgegod-daidala",
                        "archived": False,
                        "default_workdir": str(self.fixture.repository),
                    }
                ]
            )
        if command[-2:] == ("stats", "--json"):
            return 0, json.dumps({"counts": {}, "total": 0})
        if "packs" in command and "validate" in command:
            return 0, "{}"
        if command[:3] == ("gh", "issue", "list"):
            return 0, "[]"
        if command[:3] == ("gh", "project", "list"):
            return 0, json.dumps(
                {
                    "projects": [{"id": PROJECT_ID, "url": PROJECT_URL}],
                    "totalCount": 1,
                }
            )
        if command[-2:] == ("gateway", "status"):
            return 0, "Gateway running"
        if command[:2] == ("docker", "version"):
            return 0, "27.0|27.0"
        if command[:3] == ("docker", "network", "inspect"):
            return 0, "none|null"
        if command[:3] == ("docker", "image", "inspect"):
            return 0, "sha256:" + "b" * 64
        raise AssertionError(f"unexpected command: {command}")


def _run(
    fixture: Fixture,
    *,
    live: bool = True,
    runner: FakeRunner | None = None,
    extra_environ: Mapping[str, str] | None = None,
):
    selected = runner or FakeRunner(fixture)
    environ = {
        "PATH": "/bin",
        "DAIDALA_GITHUB_INTAKE_TOKEN": "intake-secret",
        "DAIDALA_GITHUB_FINDINGS_TOKEN": "findings-secret",
    }
    environ.update(extra_environ or {})
    report = run_prerequisite_diagnosis(
        project_manifest=fixture.manifest,
        registration=fixture.registration,
        live=live,
        runner=selected,
        environ=environ,
        current_date=date(2026, 7, 14),
    )
    return report, selected


def test_complete_live_diagnosis_passes_without_leaking_or_persisting_tokens(
    configured_fixture: Fixture,
) -> None:
    report, runner = _run(configured_fixture)

    assert report.status is CheckStatus.PASS
    assert report.exit_code == 0
    assert tuple(row.check_id for row in report.checks) == tuple(row.check_id for row in CHECKS)
    serialized = json.dumps(report.to_dict(), sort_keys=True)
    assert "intake-secret" not in serialized
    assert "findings-secret" not in serialized
    github_environments = [
        environment for command, environment in runner.calls if command[0] == "gh"
    ]
    assert github_environments
    assert {environment["GH_TOKEN"] for environment in github_environments if environment} == {
        "intake-secret",
        "findings-secret",
    }
    assert all(
        set(environment or {}) <= {"PATH", "GH_TOKEN"}
        for environment in github_environments
    )
    assert all(
        environment == {"PATH": "/bin"}
        for command, environment in runner.calls
        if command[0] != "gh"
    )
    assert PrerequisiteReport.from_dict(report.to_dict()) == report


def test_native_profile_invocation_accepts_retained_non_controller_sticky_profile(
    configured_fixture: Fixture,
) -> None:
    report, runner = _run(
        configured_fixture,
        extra_environ={"HERMES_HOME": str(configured_fixture.profile_root)},
    )

    assert report.status is CheckStatus.PASS
    assert any(
        environment.get("HERMES_HOME") == str(configured_fixture.profile_root)
        for command, environment in runner.calls
        if command == ("hermes", "profile", "list")
    )


def test_non_live_diagnosis_reports_live_checks_not_run_and_remains_blocked(
    configured_fixture: Fixture,
) -> None:
    report, runner = _run(configured_fixture, live=False)
    statuses = {row.check_id: row.status for row in report.checks}

    assert report.status is CheckStatus.BLOCKED
    assert report.exit_code == 2
    assert statuses["SI-GITHUB-INTAKE"] is CheckStatus.NOT_RUN
    assert statuses["SI-GITHUB-FINDINGS"] is CheckStatus.NOT_RUN
    assert statuses["SI-GITHUB-PROJECT"] is CheckStatus.NOT_RUN
    assert statuses["SI-NOTIFICATION"] is CheckStatus.NOT_RUN
    assert statuses["SI-EVALUATOR"] is CheckStatus.NOT_RUN
    assert not any(command[0] in {"gh", "docker"} for command, _ in runner.calls)


def test_missing_registration_reports_every_check_once_without_guessing_aliases(
    configured_fixture: Fixture,
) -> None:
    runner = FakeRunner(configured_fixture)
    report = run_prerequisite_diagnosis(
        project_manifest=configured_fixture.manifest,
        live=True,
        runner=runner,
        environ={},
    )

    assert report.exit_code == 2
    assert len(report.checks) == len(CHECKS)
    assert next(
        row for row in report.checks if row.check_id == "SI-REPOSITORY"
    ).status is CheckStatus.PASS
    assert all(
        row.status is CheckStatus.BLOCKED
        for row in report.checks
        if row.check_id != "SI-REPOSITORY"
    )
    assert not any(command[0] in {"gh", "docker"} for command, _ in runner.calls)


def test_malformed_host_json_is_checker_error_but_keeps_complete_report(
    configured_fixture: Fixture,
) -> None:
    malformed = ("hermes", "kanban", "boards", "list", "--json")
    runner = FakeRunner(configured_fixture, malformed_command=malformed)
    report, _ = _run(configured_fixture, runner=runner)

    assert report.exit_code == 1
    assert report.status is CheckStatus.ERROR
    assert len(report.checks) == len(CHECKS)
    board = next(row for row in report.checks if row.check_id == "SI-BOARD")
    assert board.status is CheckStatus.ERROR
    assert sum(command == malformed for command, _ in runner.calls) == 1


def test_malformed_github_issue_shape_is_checker_error(
    configured_fixture: Fixture,
) -> None:
    malformed = (
        "gh", "issue", "list", "--repo", "forgegod/daidala",
        "--limit", "1", "--json", "number",
    )
    runner = FakeRunner(
        configured_fixture,
        malformed_command=malformed,
        malformed_output='[{"number": "invalid"}]',
    )
    report, _ = _run(configured_fixture, runner=runner)
    intake = next(row for row in report.checks if row.check_id == "SI-GITHUB-INTAKE")

    assert report.exit_code == 1
    assert intake.status is CheckStatus.ERROR


def test_unavailable_live_boundary_is_exact_blocker_not_success(
    configured_fixture: Fixture,
) -> None:
    runner = FakeRunner(configured_fixture, unavailable_prefix=("docker",))
    report, _ = _run(configured_fixture, runner=runner)
    evaluator = next(row for row in report.checks if row.check_id == "SI-EVALUATOR")

    assert report.exit_code == 2
    assert evaluator.status is CheckStatus.BLOCKED
    assert "unavailable" in (evaluator.blocker or "")


def test_denied_capability_metadata_fails_before_credential_resolution(
    configured_fixture: Fixture,
) -> None:
    evidence_path = configured_fixture.registration.with_name("prerequisite-evidence.json")
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["credential_capabilities"][0]["denied"] = ["contents-write"]
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    report, runner = _run(configured_fixture)
    intake = next(row for row in report.checks if row.check_id == "SI-GITHUB-INTAKE")

    assert report.exit_code == 2
    assert intake.status is CheckStatus.BLOCKED
    assert "denied capabilities" in (intake.blocker or "")
    assert not any(
        command[:3] == ("gh", "issue", "list")
        and environment is not None
        and environment.get("GH_TOKEN") == "intake-secret"
        for command, environment in runner.calls
    )


def test_intake_requires_read_organization_capability_before_credential_resolution(
    configured_fixture: Fixture,
) -> None:
    evidence_path = configured_fixture.registration.with_name("prerequisite-evidence.json")
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["credential_capabilities"][0]["allowed"] = [
        "read-project",
        "read-public-repository",
    ]
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    report, runner = _run(configured_fixture)
    intake = next(row for row in report.checks if row.check_id == "SI-GITHUB-INTAKE")

    assert report.exit_code == 2
    assert intake.status is CheckStatus.BLOCKED
    assert "allowed capabilities" in (intake.blocker or "")
    assert not any(
        command[:3] == ("gh", "issue", "list")
        and environment is not None
        and environment.get("GH_TOKEN") == "intake-secret"
        for command, environment in runner.calls
    )


def test_expired_capability_evidence_fails_before_credential_resolution(
    configured_fixture: Fixture,
) -> None:
    evidence_path = configured_fixture.registration.with_name("prerequisite-evidence.json")
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["credential_capabilities"][0]["expires_on"] = "2026-07-13"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    report, runner = _run(configured_fixture)
    intake = next(row for row in report.checks if row.check_id == "SI-GITHUB-INTAKE")

    assert intake.status is CheckStatus.BLOCKED
    assert "expired" in (intake.blocker or "")
    assert not any(
        command[:3] == ("gh", "issue", "list")
        and environment is not None
        and environment.get("GH_TOKEN") == "intake-secret"
        for command, environment in runner.calls
    )


def test_findings_requires_prior_approved_controlled_write_probe(
    configured_fixture: Fixture,
) -> None:
    evidence_path = configured_fixture.registration.with_name("prerequisite-evidence.json")
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["credential_capabilities"][1]["write_probe_identity"] = None
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    report, runner = _run(configured_fixture)
    findings = next(row for row in report.checks if row.check_id == "SI-GITHUB-FINDINGS")

    assert findings.status is CheckStatus.BLOCKED
    assert "write probe" in (findings.blocker or "")
    assert not any(
        command[:3] == ("gh", "issue", "list")
        and environment is not None
        and environment.get("GH_TOKEN") == "findings-secret"
        for command, environment in runner.calls
    )


def test_partially_configured_environment_reports_missing_retained_receipt(
    configured_fixture: Fixture,
) -> None:
    evidence_path = configured_fixture.registration.with_name("prerequisite-evidence.json")
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["notification"] = None
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    report, _ = _run(configured_fixture)
    notification = next(row for row in report.checks if row.check_id == "SI-NOTIFICATION")

    assert report.exit_code == 2
    assert notification.status is CheckStatus.BLOCKED
    assert "receipt is missing" in (notification.blocker or "")


def test_invalid_manifest_returns_strict_error_report(tmp_path: Path) -> None:
    manifest = tmp_path / "project.yaml"
    manifest.write_text("schema: wrong\n", encoding="utf-8")

    report = run_prerequisite_diagnosis(project_manifest=manifest)

    assert report.exit_code == 1
    assert report.status is CheckStatus.ERROR
    assert report.project_id is None
    assert report.checks == ()
    assert PrerequisiteReport.from_dict(report.to_dict()) == report


def test_registration_input_uses_its_specific_size_bound(
    configured_fixture: Fixture,
) -> None:
    configured_fixture.registration.write_text("x" * 32_769, encoding="utf-8")

    report = run_prerequisite_diagnosis(
        project_manifest=configured_fixture.manifest,
        registration=configured_fixture.registration,
    )

    assert report.exit_code == 1
    assert report.error is not None
    assert "controller registration exceeds 32768 bytes" in report.error


def test_guide_ready_to_admit_ids_exactly_match_checker_registry() -> None:
    guide = (ROOT / "docs/16-self-improvement-setup.md").read_text(encoding="utf-8")
    table = guide.split("## 11. Ready-to-admit gate", 1)[1]
    guide_ids = re.findall(r"\| `(?P<id>SI-[A-Z0-9-]+)` \|", table)

    assert guide_ids == [definition.check_id for definition in CHECKS]
    assert re.fullmatch(r"[0-9a-f]{64}", CHECKLIST_DIGEST)


def test_standalone_and_native_doctor_outputs_and_exit_codes_match(
    configured_fixture: Fixture, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = [
        "doctor",
        "--project-manifest",
        str(configured_fixture.manifest),
        "--registration",
        str(configured_fixture.registration),
        "--live",
    ]
    environment = {
        "PATH": "/bin",
        "DAIDALA_GITHUB_INTAKE_TOKEN": "intake-secret",
        "DAIDALA_GITHUB_FINDINGS_TOKEN": "findings-secret",
    }
    standalone_runner = FakeRunner(configured_fixture)
    native_runner = FakeRunner(configured_fixture)

    standalone_code = cli.main(
        argv, doctor_runner=standalone_runner, doctor_environ=environment
    )
    standalone_output = json.loads(capsys.readouterr().out)
    parser = argparse.ArgumentParser(prog="hermes daidala")
    cli.register_cli(parser)
    native_code = cli.run_command(
        parser.parse_args(argv), doctor_runner=native_runner, doctor_environ=environment
    )
    native_output = json.loads(capsys.readouterr().out)

    assert native_code == standalone_code == 0
    assert native_output == standalone_output
