from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace

import pytest

from daidala.errors import PolicyViolationError
from daidala.prerequisites import CheckStatus
from daidala.project_cycles import ProjectCycleOperator
from daidala.state import WorkflowStage

ROOT = Path(__file__).parents[1]
BASELINE = "b" * 40


def _issue_body() -> str:
    return (
        """\
### Category

regression

### Originating experiment, test case, or source identity

UC-01 / TC-F04-01

### Expected behavior

The temporary calculator returns 2.

### Observed behavior

The temporary calculator returns 1.

### Redacted evidence reference and SHA-256 digest

uc-01 sha256:"""
        + "a" * 64
        + """

### Acceptance criteria

- The failing test passes.

### Dependencies and risk

Temporary fixture only.

### Priority

1

### Publication state

local
"""
    )


class Runtime:
    def __init__(self, checkout: Path) -> None:
        self.checkout = checkout
        self.calls: list[tuple[tuple[str, ...], dict[str, str]]] = []

    def __call__(
        self, command: tuple[str, ...], environment: Mapping[str, str]
    ) -> tuple[int, str]:
        env = dict(environment)
        self.calls.append((command, env))
        if command[:4] == ("git", "-C", str(self.checkout), "rev-parse"):
            return 0, BASELINE
        if command[:4] == ("git", "-C", str(self.checkout), "status"):
            return 0, ""
        if command[:4] == ("git", "-C", str(self.checkout), "remote"):
            return 0, "git@github.com:forgegod/daidala.git"
        if command[:3] == ("gh", "issue", "view"):
            assert env["GH_TOKEN"] == "read-token"
            return 0, json.dumps(
                {
                    "number": 42,
                    "url": "https://github.com/forgegod/daidala/issues/42",
                    "title": "[Daidala SI] Fix temporary calculator",
                    "body": _issue_body(),
                    "state": "OPEN",
                    "labels": [
                        {"name": "daidala-si"},
                        {"name": "daidala-si:ready"},
                        {"name": "daidala-si:regression"},
                        {"name": "daidala-si:priority-1"},
                    ],
                }
            )
        if command[:3] == ("gh", "api", "--paginate"):
            assert env["GH_TOKEN"] == "read-token"
            assert command[-2:] == ("--jq", ".[]")
            if command[3].endswith("/events?per_page=100"):
                return 0, json.dumps(
                    {
                        "event": "labeled",
                        "label": {"name": "daidala-si:ready"},
                        "actor": {"login": "forgegod"},
                    }
                )
            if command[3].endswith("/comments?per_page=100"):
                return 0, ""
        raise AssertionError(f"unexpected command: {command}")


def _stage_profiles() -> dict[str, str]:
    return {
        stage.value: "daidala-self-improvement"
        for stage in WorkflowStage
        if stage is not WorkflowStage.APPROVAL
    }


def _operator(tmp_path: Path) -> tuple[ProjectCycleOperator, Path, Path, Runtime, list[Path]]:
    checkout = tmp_path / "checkout"
    policy = checkout / ".daidala"
    policy.mkdir(parents=True)
    (policy / "project.yaml").write_text(
        (ROOT / ".daidala/project.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (policy / "constraints.yaml").write_text(
        (ROOT / ".daidala/constraints.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    profile_root = tmp_path / "profile"
    project_root = profile_root / "projects" / "forgegod-daidala"
    project_root.mkdir(parents=True)
    registration = project_root / "registration.yaml"
    registration.write_text(
        f"""\
schema: daidala.controller-registration/v2
project_id: forgegod-daidala
checkout: {checkout}
controller_profile: daidala-self-improvement
board: daidala-forgegod-daidala
repository_identity:
  canonical: forgegod/daidala
  verified_remote: git@github.com:forgegod/daidala.git
credentials:
  intake: github-read
  findings: github-write
approval:
  maintainers: [forgegod]
notifications:
  adapter: hermes-gateway
  target: attended-daidala
  destination: telegram:-1001234567890:17585
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
""",
        encoding="utf-8",
    )
    (project_root / "credential-bindings.yaml").write_text(
        """\
schema: daidala.credential-bindings/v1
project_id: forgegod-daidala
bindings:
  - alias: github-read
    resolver: environment
    environment_variable: GH_READ_TOKEN
  - alias: github-write
    resolver: environment
    environment_variable: GH_WRITE_TOKEN
""",
        encoding="utf-8",
    )
    runtime = Runtime(checkout)
    workflow_roots: list[Path] = []

    def build_workflow(
        root: Path, runner: object, environ: object
    ) -> object:
        workflow_roots.append(root)
        raise AssertionError("workflow factory must not run before exact identity matches")

    operator = ProjectCycleOperator(
        runner=runtime,
        environ={
            "PATH": "/usr/bin",
            "HOME": str(tmp_path / "home"),
            "GH_READ_TOKEN": "read-token",
            "GH_WRITE_TOKEN": "write-token",
        },
        diagnose=lambda **kwargs: SimpleNamespace(status=CheckStatus.PASS),
        workflow_factory=build_workflow,  # type: ignore[arg-type]
    )
    return operator, policy / "project.yaml", registration, runtime, workflow_roots


def test_project_cycle_preview_composes_live_inputs_without_runtime_mutation(
    tmp_path: Path,
) -> None:
    operator, manifest, registration, runtime, workflow_roots = _operator(tmp_path)

    preview = operator.preview(
        project_manifest=manifest,
        registration=registration,
        issue_id="42",
        stage_profiles=_stage_profiles(),
        pack_name="addyosmani",
    )

    profile_root = registration.parents[2]
    assert preview.cycle.cycle_id.startswith("cycle-")
    assert preview.intake_digest
    assert preview.checkout == str(manifest.parents[1])
    assert workflow_roots == []
    assert not (profile_root / "daidala").exists()
    assert not (registration.parent / "cycles").exists()
    assert not any(call[0][:3] == ("gh", "issue", "comment") for call in runtime.calls)


def test_project_cycle_apply_rejects_stale_preview_before_workflow_or_claim(
    tmp_path: Path,
) -> None:
    operator, manifest, registration, runtime, workflow_roots = _operator(tmp_path)
    preview = operator.preview(
        project_manifest=manifest,
        registration=registration,
        issue_id="42",
        stage_profiles=_stage_profiles(),
    )

    with pytest.raises(PolicyViolationError, match="expected cycle ID"):
        operator.admit(
            project_manifest=manifest,
            registration=registration,
            issue_id="42",
            stage_profiles=_stage_profiles(),
            expected_cycle_id="cycle-" + "0" * 64,
            expected_intake_digest=preview.intake_digest,
        )

    assert workflow_roots == []
    assert not any(
        call[0][:3] in {("gh", "issue", "comment"), ("gh", "issue", "edit")}
        for call in runtime.calls
    )
