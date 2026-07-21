from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from daidala import cli
from daidala.adapters import NotificationReceipt
from daidala.evaluation import EvaluatorIsolationEvidence
from daidala.reconciliation import (
    ReconciliationOutcome,
    ReconciliationPreview,
    ReconciliationResult,
)
from daidala.restricted_container import (
    RestrictedContainerEvidence,
    RestrictedContainerRequest,
)

PROFILE_ARGS = [
    "--default-profile",
    "engineer",
    "--stage-profile",
    "define=architect",
    "--stage-profile",
    "plan=architect",
    "--stage-profile",
    "review=reviewer",
]
PINNED_EVALUATOR_IMAGE = (
    "catthehacker/ubuntu@sha256:"
    "3220992391c1182a0cfe4c64453511772c54f4c39e960d26a5e327960675982e"
)
CONTROLLER_REVISION = "0" * 40
RECONCILIATION_CYCLE = "cycle-" + "e" * 64


@dataclass
class FakeState:
    workflow_id: str = "wf-1"

    def to_dict(self) -> dict[str, str]:
        return {"workflow_id": self.workflow_id, "board_slug": "daidala-test"}


@dataclass
class FakeCardStatus:
    def to_dict(self) -> dict[str, str]:
        return {"stage": "define", "status": "ready"}


@dataclass
class FakeService:
    calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = field(default_factory=list)
    fail: bool = False

    def _call(self, name: str, *args: Any, **kwargs: Any) -> FakeState:
        self.calls.append((name, args, kwargs))
        if self.fail:
            raise RuntimeError("service failed")
        return FakeState()

    def start(self, **kwargs: Any) -> FakeState:
        return self._call("start", **kwargs)

    def status(self, workflow_id: str) -> FakeState:
        return self._call("status", workflow_id)

    def replace_constraint_input(self, workflow_id: str, **kwargs: Any) -> FakeState:
        return self._call("replace_constraint_input", workflow_id, **kwargs)

    def approve(self, workflow_id: str, *, plan_digest: str) -> FakeState:
        return self._call("approve", workflow_id, plan_digest=plan_digest)

    def cancel(self, workflow_id: str, *, reason: str) -> FakeState:
        return self._call("cancel", workflow_id, reason=reason)

    def combined_status(self, workflow_id: str) -> list[FakeCardStatus]:
        self.calls.append(("combined_status", (workflow_id,), {}))
        return [FakeCardStatus()]


@dataclass
class FakeAdmissionPreview:
    cycle_id: str = "cycle-" + "b" * 64
    intake_digest: str = "a" * 64

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "daidala.admission-preview/v1",
            "dry_run": True,
            "cycle": {"cycle_id": self.cycle_id},
            "workflow_id": self.cycle_id,
            "intake_digest": self.intake_digest,
        }


@dataclass
class FakeProjectCycleResult:
    preview: FakeAdmissionPreview = field(default_factory=FakeAdmissionPreview)

    def to_dict(self) -> dict[str, object]:
        return {
            "dry_run": False,
            "preview": self.preview.to_dict(),
            "admission": {"workflow_id": self.preview.cycle_id},
            "receipt": {"receipt_id": "telegram:10"},
        }


@dataclass
class FakeCompletionPreview:
    digest: str = "c" * 64

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "daidala.cycle-completion-preview/v1",
            "cycle_id": "cycle-" + "b" * 64,
        }


@dataclass
class FakeCompletionResult:
    preview: FakeCompletionPreview = field(default_factory=FakeCompletionPreview)

    def to_dict(self) -> dict[str, object]:
        return {
            "dry_run": False,
            "preview_digest": self.preview.digest,
            "completion_digest": "d" * 64,
        }


@dataclass
class FakeCancellationPreview:
    digest: str = "e" * 64

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "daidala.cycle-cancellation-preview/v1",
            "cycle_id": "cycle-" + "b" * 64,
            "reason": "Controlled probe completed.",
        }


@dataclass
class FakeCancellationResult:
    preview: FakeCancellationPreview = field(default_factory=FakeCancellationPreview)

    def to_dict(self) -> dict[str, object]:
        return {
            "dry_run": False,
            "preview_digest": self.preview.digest,
            "cancellation_digest": "f" * 64,
        }


def _reconciliation_preview() -> ReconciliationPreview:
    return ReconciliationPreview(
        project_id="forgegod-daidala",
        board="daidala-self-improvement",
        controller_profile="daidala-self-improvement",
        manifest_digest="a" * 64,
        registration_digest="b" * 64,
        outcome=ReconciliationOutcome.ADMISSION_PREVIEW,
        candidate_count=2,
        cycle_id=RECONCILIATION_CYCLE,
        workflow_id=RECONCILIATION_CYCLE,
        intake_item_id="42",
        intake_digest="c" * 64,
    )


def _reconciliation_result() -> ReconciliationResult:
    preview = _reconciliation_preview()
    return ReconciliationResult(
        preview=preview,
        outcome=ReconciliationOutcome.ADMITTED,
        notification_receipts=(
            NotificationReceipt(
                event_id=f"{RECONCILIATION_CYCLE}:admitted",
                adapter="hermes-gateway",
                target_alias="attended-daidala",
                receipt_id="telegram:11",
                delivered_at=datetime(2026, 7, 20, 20, 0, tzinfo=UTC),
            ),
        ),
    )


@dataclass
class FakeProjectCycles:
    calls: list[tuple[str, dict[str, object]]] = field(default_factory=list)

    def preview(self, **kwargs: object) -> FakeAdmissionPreview:
        self.calls.append(("preview", kwargs))
        return FakeAdmissionPreview()

    def admit(self, **kwargs: object) -> FakeProjectCycleResult:
        self.calls.append(("admit", kwargs))
        return FakeProjectCycleResult()

    def preview_completion(self, **kwargs: object) -> FakeCompletionPreview:
        self.calls.append(("preview_completion", kwargs))
        return FakeCompletionPreview()

    def complete(self, **kwargs: object) -> FakeCompletionResult:
        self.calls.append(("complete", kwargs))
        return FakeCompletionResult()

    def preview_cancellation(self, **kwargs: object) -> FakeCancellationPreview:
        self.calls.append(("preview_cancellation", kwargs))
        return FakeCancellationPreview()

    def cancel_cycle(self, **kwargs: object) -> FakeCancellationResult:
        self.calls.append(("cancel_cycle", kwargs))
        return FakeCancellationResult()

    def preview_reconciliation(self, **kwargs: object) -> ReconciliationPreview:
        self.calls.append(("preview_reconciliation", kwargs))
        return _reconciliation_preview()

    def reconcile(self, **kwargs: object) -> ReconciliationResult:
        self.calls.append(("reconcile", kwargs))
        if kwargs["expected_preview_digest"] != _reconciliation_preview().digest:
            raise ValueError("expected reconciliation preview digest is stale")
        return _reconciliation_result()


def _host_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="hermes daidala")
    cli.register_cli(parser)
    return parser.parse_args(argv)


def _factory(service: FakeService) -> cli.ServiceFactory:
    return cast(cli.ServiceFactory, lambda: service)


def _project_cycle_factory(service: FakeProjectCycles) -> cli.ProjectCycleFactory:
    return cast(cli.ProjectCycleFactory, lambda: service)


def _reconcile_argv() -> list[str]:
    return [
        "project-cycle",
        "reconcile",
        "--project-manifest",
        "/repo/.daidala/project.yaml",
        "--registration",
        "/profile/projects/forgegod-daidala/registration.yaml",
        "--default-profile",
        "daidala-self-improvement",
        "--stage-profile",
        "review=reviewer",
        "--pack",
        "addyosmani",
        "--candidate-limit",
        "7",
        "--claim-lease-seconds",
        "600",
    ]


@pytest.mark.parametrize(
    "argv",
    [
        [
            "start",
            "/repo",
            "Implement feature",
            "--board",
            "daidala-test",
            *PROFILE_ARGS,
            "--workflow-id",
            "wf-1",
        ],
        ["status", "wf-1"],
        ["approve", "wf-1", "a" * 64],
        ["cancel", "wf-1", "operator requested cancellation"],
    ],
)
def test_standalone_and_hermes_surfaces_make_equivalent_service_calls(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    standalone = FakeService()
    host = FakeService()

    standalone_code = cli.main(argv, service_factory=_factory(standalone))
    standalone_output = capsys.readouterr().out
    host_code = cli.run_command(_host_args(argv), service_factory=_factory(host))
    host_output = capsys.readouterr().out

    assert host_code == standalone_code == 0
    assert host.calls == standalone.calls
    assert json.loads(host_output) == json.loads(standalone_output)
    if argv[0] == "start":
        assert [call[0] for call in host.calls] == ["start"]
        assert host.calls[0][2]["stage_profiles"] == {
            "define": "architect",
            "plan": "architect",
            "implement": "engineer",
            "verify": "engineer",
            "review": "reviewer",
            "deliver": "engineer",
        }
    if argv[0] == "status":
        assert json.loads(host_output)["kanban"] == [
            {"stage": "define", "status": "ready"}
        ]


def test_init_is_dry_run_by_default(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    result = cli.main(["init"])
    payload = json.loads(capsys.readouterr().out)

    assert result == 0
    assert payload["dry_run"] is True
    assert not (tmp_path / "daidala").exists()


def test_init_apply_creates_profile_local_schema(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    legacy_root = tmp_path / ("wing" + "staff")
    legacy_root.mkdir()
    sentinel = legacy_root / "do-not-read"
    sentinel.write_text("legacy", encoding="utf-8")

    result = cli.main(["init", "--apply"])
    payload = json.loads(capsys.readouterr().out)

    assert result == 0
    assert payload["dry_run"] is False
    assert Path(payload["database"]).is_file()
    assert Path(payload["database"]).parent == tmp_path / "daidala"
    assert sentinel.read_text(encoding="utf-8") == "legacy"


def test_evaluator_probe_is_dry_run_by_default(capsys) -> None:
    calls: list[str] = []

    def unexpected_probe(image: str) -> EvaluatorIsolationEvidence:
        calls.append(image)
        raise AssertionError("dry-run must not start a container")

    code = cli.main(
        ["evaluator", "probe", "--image", PINNED_EVALUATOR_IMAGE],
        container_probe=unexpected_probe,
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert calls == []
    assert payload["success"] is True
    assert payload["operation"] == "evaluator-probe"
    assert payload["dry_run"] is True
    assert payload["policy"]["image_identity"] == PINNED_EVALUATOR_IMAGE
    assert payload["policy"]["network"] == "none"
    assert payload["policy"]["controller_environment_inherited"] is False


def test_evaluator_probe_apply_is_equivalent_on_standalone_and_native_surfaces(
    capsys,
) -> None:
    calls: list[str] = []

    def probe(image: str) -> EvaluatorIsolationEvidence:
        calls.append(image)
        return EvaluatorIsolationEvidence(
            backend="restricted-container",
            network="denied-by-default",
            image_identity=image,
            fresh_home=True,
            network_denied=True,
            controller_credentials_absent=True,
            bounded_mounts=True,
            receipt_id="sha256:" + "a" * 64,
        )

    argv = ["evaluator", "probe", "--image", PINNED_EVALUATOR_IMAGE, "--apply"]
    standalone_code = cli.main(argv, container_probe=probe)
    standalone = json.loads(capsys.readouterr().out)
    native_code = cli.run_command(_host_args(argv), container_probe=probe)
    native = json.loads(capsys.readouterr().out)

    assert standalone_code == native_code == 0
    assert calls == [PINNED_EVALUATOR_IMAGE, PINNED_EVALUATOR_IMAGE]
    assert native == standalone
    assert standalone["success"] is True
    assert standalone["dry_run"] is False
    assert standalone["evidence"]["receipt_id"] == "sha256:" + "a" * 64


def test_evaluator_run_apply_uses_profile_local_daidala_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workflow_id = "cycle-" + "0" * 64
    request = RestrictedContainerRequest(
        workflow_id=workflow_id,
        role="baseline",
        repository_revision="1" * 40,
        controller_revision=CONTROLLER_REVISION,
        image_identity=PINNED_EVALUATOR_IMAGE,
        files=(("test.py", "raise SystemExit(1)\n"),),
        command=("python3", "test.py"),
        expected_exit_code=1,
    )
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(request.to_dict()), encoding="utf-8")
    calls: list[Path] = []

    def run_request(
        observed: RestrictedContainerRequest,
        data_root: Path,
    ) -> tuple[RestrictedContainerEvidence, Path]:
        assert observed == request
        calls.append(data_root)
        evidence = RestrictedContainerEvidence(
            request_digest=request.digest,
            workflow_id=workflow_id,
            role="baseline",
            repository_revision="1" * 40,
            controller_revision=CONTROLLER_REVISION,
            image_identity=PINNED_EVALUATOR_IMAGE,
            image_id="sha256:" + "2" * 64,
            fixture_digest="3" * 64,
            command=request.command,
            expected_exit_code=1,
            exit_code=1,
            output="expected failure",
            output_digest="4" * 64,
        )
        return evidence, data_root / "evidence.json"

    dry_run_code = cli.main(
        ["evaluator", "run", "--request", str(request_path)],
        container_request_runner=run_request,
    )
    dry_run_payload = json.loads(capsys.readouterr().out)
    assert dry_run_code == 0
    assert calls == []
    assert dry_run_payload["request"]["controller_revision"] == CONTROLLER_REVISION
    assert dry_run_payload["request_digest"] == request.digest

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    code = cli.main(
        ["evaluator", "run", "--request", str(request_path), "--apply"],
        container_request_runner=run_request,
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert calls == [(tmp_path / "daidala").resolve()]
    assert payload["success"] is True
    assert payload["evidence"]["exit_code"] == 1
    assert payload["evidence"]["controller_revision"] == CONTROLLER_REVISION


def test_project_cycle_admission_is_dry_run_by_default_on_both_surfaces(capsys) -> None:
    standalone = FakeProjectCycles()
    native = FakeProjectCycles()
    argv = [
        "project-cycle",
        "admit",
        "--project-manifest",
        "/repo/.daidala/project.yaml",
        "--registration",
        "/profile/projects/forgegod-daidala/registration.yaml",
        "--issue",
        "42",
        "--default-profile",
        "daidala-self-improvement",
        "--pack",
        "addyosmani",
    ]

    standalone_code = cli.main(
        argv, project_cycle_factory=_project_cycle_factory(standalone)
    )
    standalone_payload = json.loads(capsys.readouterr().out)
    native_code = cli.run_command(
        _host_args(argv), project_cycle_factory=_project_cycle_factory(native)
    )
    native_payload = json.loads(capsys.readouterr().out)

    assert standalone_code == native_code == 0
    assert native.calls == standalone.calls
    assert native.calls[0][0] == "preview"
    assert native.calls[0][1]["issue_id"] == "42"
    assert native_payload == standalone_payload
    assert native_payload["dry_run"] is True
    assert native_payload["preview"]["intake_digest"] == "a" * 64


def test_project_cycle_apply_requires_and_forwards_exact_preview_identity(capsys) -> None:
    service = FakeProjectCycles()
    cycle_id = "cycle-" + "b" * 64
    argv = [
        "project-cycle",
        "admit",
        "--project-manifest",
        "/repo/.daidala/project.yaml",
        "--registration",
        "/profile/projects/forgegod-daidala/registration.yaml",
        "--issue",
        "42",
        "--default-profile",
        "daidala-self-improvement",
        "--apply",
        "--expected-cycle-id",
        cycle_id,
        "--expected-intake-digest",
        "a" * 64,
    ]

    code = cli.main(argv, project_cycle_factory=_project_cycle_factory(service))
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert service.calls[0][0] == "admit"
    assert service.calls[0][1]["expected_cycle_id"] == cycle_id
    assert service.calls[0][1]["expected_intake_digest"] == "a" * 64
    assert payload["dry_run"] is False


def test_project_cycle_apply_without_exact_preview_identity_fails_before_service(capsys) -> None:
    service = FakeProjectCycles()
    code = cli.main(
        [
            "project-cycle",
            "admit",
            "--project-manifest",
            "/repo/.daidala/project.yaml",
            "--registration",
            "/profile/projects/forgegod-daidala/registration.yaml",
            "--issue",
            "42",
            "--default-profile",
            "daidala-self-improvement",
            "--apply",
        ],
        project_cycle_factory=_project_cycle_factory(service),
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 1
    assert service.calls == []
    assert "requires --expected-cycle-id" in payload["message"]


def test_reconciliation_help_is_equivalent_on_standalone_and_native_surfaces(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as standalone_exit:
        cli.build_parser(prog="daidala").parse_args(
            ["project-cycle", "reconcile", "--help"]
        )
    standalone = capsys.readouterr().out
    native_parser = argparse.ArgumentParser(prog="hermes daidala")
    cli.register_cli(native_parser)
    with pytest.raises(SystemExit) as native_exit:
        native_parser.parse_args(["project-cycle", "reconcile", "--help"])
    native = capsys.readouterr().out

    assert standalone_exit.value.code == native_exit.value.code == 0
    expected_options = {
        "--project-manifest",
        "--registration",
        "--default-profile",
        "--stage-profile",
        "--pack",
        "--candidate-limit",
        "--claim-lease-seconds",
        "--apply",
        "--expected-preview-digest",
    }
    for option in expected_options:
        assert option in standalone
        assert option in native


def test_reconciliation_is_dry_run_by_default_on_both_surfaces(capsys) -> None:
    standalone = FakeProjectCycles()
    native = FakeProjectCycles()
    argv = _reconcile_argv()

    standalone_code = cli.main(
        argv, project_cycle_factory=_project_cycle_factory(standalone)
    )
    standalone_payload = json.loads(capsys.readouterr().out)
    native_code = cli.run_command(
        _host_args(argv), project_cycle_factory=_project_cycle_factory(native)
    )
    native_payload = json.loads(capsys.readouterr().out)

    assert standalone_code == native_code == 0
    assert native.calls == standalone.calls
    assert native.calls[0][0] == "preview_reconciliation"
    assert native.calls[0][1]["candidate_limit"] == 7
    assert native.calls[0][1]["claim_lease_seconds"] == 600
    assert native_payload == standalone_payload
    assert native_payload["dry_run"] is True
    assert native_payload["preview_digest"] == _reconciliation_preview().digest
    assert native_payload["selected_issue_id"] == "42"
    assert native_payload["board"] == "daidala-self-improvement"
    assert native_payload["current_stage"] is None
    assert native_payload["receipt_ids"] == []
    assert native_payload["inspection_command"] == (
        f"hermes -p daidala-self-improvement daidala status {RECONCILIATION_CYCLE}"
    )


def test_reconciliation_apply_requires_and_forwards_exact_preview_digest(capsys) -> None:
    service = FakeProjectCycles()
    base = [*_reconcile_argv(), "--apply"]

    missing_code = cli.main(
        base, project_cycle_factory=_project_cycle_factory(service)
    )
    missing = json.loads(capsys.readouterr().out)
    assert missing_code == 1
    assert service.calls == []
    assert "requires --expected-preview-digest" in missing["message"]

    stale_code = cli.main(
        [*base, "--expected-preview-digest", "0" * 64],
        project_cycle_factory=_project_cycle_factory(service),
    )
    stale = json.loads(capsys.readouterr().out)
    assert stale_code == 1
    assert service.calls[-1][0] == "reconcile"
    assert "stale" in stale["message"]

    code = cli.main(
        [*base, "--expected-preview-digest", _reconciliation_preview().digest],
        project_cycle_factory=_project_cycle_factory(service),
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert service.calls[-1][0] == "reconcile"
    assert service.calls[-1][1]["expected_preview_digest"] == (
        _reconciliation_preview().digest
    )
    assert payload["dry_run"] is False
    assert payload["outcome"] == "admitted"
    assert payload["receipt_ids"] == ["telegram:11"]


def test_reconciliation_expected_digest_is_rejected_without_apply(capsys) -> None:
    service = FakeProjectCycles()
    code = cli.main(
        [
            *_reconcile_argv(),
            "--expected-preview-digest",
            _reconciliation_preview().digest,
        ],
        project_cycle_factory=_project_cycle_factory(service),
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert service.calls == []
    assert "requires --apply" in payload["message"]


def test_project_cycle_completion_is_dry_run_by_default_on_both_surfaces(capsys) -> None:
    standalone = FakeProjectCycles()
    native = FakeProjectCycles()
    cycle_id = "cycle-" + "b" * 64
    argv = [
        "project-cycle",
        "complete",
        "--project-manifest",
        "/repo/.daidala/project.yaml",
        "--registration",
        "/profile/projects/forgegod-daidala/registration.yaml",
        "--cycle-id",
        cycle_id,
    ]

    standalone_code = cli.main(
        argv, project_cycle_factory=_project_cycle_factory(standalone)
    )
    standalone_payload = json.loads(capsys.readouterr().out)
    native_code = cli.run_command(
        _host_args(argv), project_cycle_factory=_project_cycle_factory(native)
    )
    native_payload = json.loads(capsys.readouterr().out)

    assert standalone_code == native_code == 0
    assert native.calls == standalone.calls
    assert native.calls == [
        (
            "preview_completion",
            {
                "project_manifest": Path("/repo/.daidala/project.yaml"),
                "registration": Path(
                    "/profile/projects/forgegod-daidala/registration.yaml"
                ),
                "cycle_id": cycle_id,
            },
        )
    ]
    assert native_payload == standalone_payload
    assert native_payload["dry_run"] is True
    assert native_payload["preview_digest"] == "c" * 64


def test_project_cycle_completion_apply_requires_exact_preview_digest(capsys) -> None:
    service = FakeProjectCycles()
    cycle_id = "cycle-" + "b" * 64
    base = [
        "project-cycle",
        "complete",
        "--project-manifest",
        "/repo/.daidala/project.yaml",
        "--registration",
        "/profile/projects/forgegod-daidala/registration.yaml",
        "--cycle-id",
        cycle_id,
        "--apply",
    ]

    missing_code = cli.main(
        base, project_cycle_factory=_project_cycle_factory(service)
    )
    missing_payload = json.loads(capsys.readouterr().out)
    assert missing_code == 1
    assert service.calls == []
    assert "requires --expected-preview-digest" in missing_payload["message"]

    code = cli.main(
        [*base, "--expected-preview-digest", "c" * 64],
        project_cycle_factory=_project_cycle_factory(service),
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert service.calls[0][0] == "complete"
    assert service.calls[0][1]["expected_preview_digest"] == "c" * 64
    assert payload["dry_run"] is False
    assert payload["completion_digest"] == "d" * 64


def test_project_cycle_cancellation_is_dry_run_by_default_on_both_surfaces(capsys) -> None:
    standalone = FakeProjectCycles()
    native = FakeProjectCycles()
    cycle_id = "cycle-" + "b" * 64
    reason = "Controlled probe completed."
    argv = [
        "project-cycle",
        "cancel",
        "--project-manifest",
        "/repo/.daidala/project.yaml",
        "--registration",
        "/profile/projects/forgegod-daidala/registration.yaml",
        "--cycle-id",
        cycle_id,
        "--reason",
        reason,
    ]

    standalone_code = cli.main(
        argv, project_cycle_factory=_project_cycle_factory(standalone)
    )
    standalone_payload = json.loads(capsys.readouterr().out)
    native_code = cli.run_command(
        _host_args(argv), project_cycle_factory=_project_cycle_factory(native)
    )
    native_payload = json.loads(capsys.readouterr().out)

    assert standalone_code == native_code == 0
    assert native.calls == standalone.calls
    assert native.calls == [
        (
            "preview_cancellation",
            {
                "project_manifest": Path("/repo/.daidala/project.yaml"),
                "registration": Path(
                    "/profile/projects/forgegod-daidala/registration.yaml"
                ),
                "cycle_id": cycle_id,
                "reason": reason,
            },
        )
    ]
    assert native_payload == standalone_payload
    assert native_payload["dry_run"] is True
    assert native_payload["preview_digest"] == "e" * 64


def test_project_cycle_cancellation_apply_requires_exact_preview_digest(capsys) -> None:
    service = FakeProjectCycles()
    cycle_id = "cycle-" + "b" * 64
    base = [
        "project-cycle",
        "cancel",
        "--project-manifest",
        "/repo/.daidala/project.yaml",
        "--registration",
        "/profile/projects/forgegod-daidala/registration.yaml",
        "--cycle-id",
        cycle_id,
        "--reason",
        "Controlled probe completed.",
        "--apply",
    ]

    missing_code = cli.main(
        base, project_cycle_factory=_project_cycle_factory(service)
    )
    missing_payload = json.loads(capsys.readouterr().out)
    assert missing_code == 1
    assert service.calls == []
    assert "requires --expected-preview-digest" in missing_payload["message"]

    code = cli.main(
        [*base, "--expected-preview-digest", "e" * 64],
        project_cycle_factory=_project_cycle_factory(service),
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert service.calls[0][0] == "cancel_cycle"
    assert service.calls[0][1]["expected_preview_digest"] == "e" * 64
    assert payload["dry_run"] is False
    assert payload["cancellation_digest"] == "f" * 64


def test_packs_list_uses_shared_command_tree(capsys) -> None:
    standalone_code = cli.main(["packs", "list"])
    standalone = json.loads(capsys.readouterr().out)
    host_code = cli.run_command(_host_args(["packs", "list"]))
    host = json.loads(capsys.readouterr().out)

    assert host_code == standalone_code == 0
    assert host == standalone == {
        "operation": "list",
        "packs": ["addyosmani", "aidlc"],
        "success": True,
    }


def test_service_error_has_same_nonzero_exit_code(capsys) -> None:
    standalone = FakeService(fail=True)
    host = FakeService(fail=True)
    argv = ["status", "wf-1"]

    standalone_code = cli.main(argv, service_factory=_factory(standalone))
    standalone_payload = json.loads(capsys.readouterr().out)
    host_code = cli.run_command(_host_args(argv), service_factory=_factory(host))
    host_payload = json.loads(capsys.readouterr().out)

    assert host_code == standalone_code == 1
    assert host_payload == standalone_payload
    assert host_payload["error"] == "RuntimeError"


def test_hermes_callback_preserves_dispatch_exit_code(monkeypatch) -> None:
    monkeypatch.setattr(cli, "run_command", lambda args: 7)

    with pytest.raises(SystemExit) as raised:
        cli.dispatch_cli(argparse.Namespace())

    assert raised.value.code == 7


def test_default_profile_expands_without_stage_overrides(capsys) -> None:
    service = FakeService()

    code = cli.main(
        [
            "start",
            "/repo",
            "Implement feature",
            "--board",
            "daidala-test",
            "--default-profile",
            "engineer",
            "--workflow-id",
            "wf-1",
        ],
        service_factory=_factory(service),
    )

    assert code == 0
    assert set(service.calls[0][2]["stage_profiles"].values()) == {"engineer"}
    assert json.loads(capsys.readouterr().out)["success"] is True


def test_constraint_file_start_and_replacement_share_service_paths(tmp_path, capsys) -> None:
    constraint_file = tmp_path / "constraints.yaml"
    constraint_file.write_text(
        "schema: daidala.workflow-constraints/v1\nglobal: [Never push.]\n",
        encoding="utf-8",
    )
    service = FakeService()

    start_code = cli.main(
        [
            "start", "/repo", "Implement feature", "--board", "daidala-test",
            "--default-profile", "engineer", "--workflow-id", "wf-1",
            "--constraints-file", str(constraint_file),
        ],
        service_factory=_factory(service),
    )
    capsys.readouterr()
    replace_code = cli.run_command(
        _host_args(
            ["replace-constraints", "wf-1", "a" * 64,
             "--constraints-file", str(constraint_file)]
        ),
        service_factory=_factory(service),
    )

    assert start_code == replace_code == 0
    assert service.calls[0][2]["constraints_content"].startswith("schema:")
    assert service.calls[1] == (
        "replace_constraint_input",
        ("wf-1",),
        {
            "expected_current_digest": "a" * 64,
            "content": constraint_file.read_text(encoding="utf-8"),
            "skill_name": None,
            "skill_digest": None,
        },
    )


def test_constraint_skill_requires_exact_digest_before_service_call(capsys) -> None:
    service = FakeService()

    code = cli.main(
        ["replace-constraints", "wf-1", "--constraints-skill", "no-push-policy"],
        service_factory=_factory(service),
    )

    assert code == 1
    assert service.calls == []
    assert "requires --constraints-skill-digest" in json.loads(capsys.readouterr().out)["message"]


def test_cli_kanban_dispatch_translates_public_create_and_show_commands() -> None:
    commands: list[tuple[str, ...]] = []

    def run(command: tuple[str, ...]) -> tuple[int, str]:
        commands.append(command)
        if "create" in command:
            return 0, json.dumps({"id": "t_define", "status": "ready"})
        return 0, json.dumps({"task": {"id": "t_define", "status": "ready"}})

    created = json.loads(
        cli._dispatch_kanban_cli(
            run,
            "kanban_create",
            {
                "board": "daidala-test",
                "title": "Define workflow",
                "body": "workflow_id=wf-1 stage=define",
                "assignee": "engineer",
                "parents": [],
                "workspace_path": "/repo",
                "idempotency_key": "daidala:wf-1:0:define",
                "skills": ["daidala:orchestrate", "daidala:aidlc-adapter"],
            },
        )
    )
    shown = json.loads(
        cli._dispatch_kanban_cli(
            run,
            "kanban_show",
            {"board": "daidala-test", "task_id": "t_define"},
        )
    )

    assert created == {"ok": True, "status": "ready", "task_id": "t_define"}
    assert shown["task"]["id"] == "t_define"
    assert commands[0] == (
        "hermes",
        "kanban",
        "--board",
        "daidala-test",
        "create",
        "Define workflow",
        "--body",
        "workflow_id=wf-1 stage=define",
        "--assignee",
        "engineer",
        "--workspace",
        "dir:/repo",
        "--idempotency-key",
        "daidala:wf-1:0:define",
        "--skill",
        "daidala:orchestrate",
        "--skill",
        "daidala:aidlc-adapter",
        "--json",
    )
    assert commands[1] == (
        "hermes",
        "kanban",
        "--board",
        "daidala-test",
        "show",
        "t_define",
        "--json",
    )


def test_cli_kanban_dispatch_refuses_non_kanban_terminal_command() -> None:
    result = json.loads(
        cli._dispatch_kanban_cli(
            lambda command: pytest.fail(f"unexpected command: {command}"),
            "terminal",
            {"command": "rm -rf /"},
        )
    )

    assert result == {
        "exit_code": 1,
        "output": "refused non-Kanban host command",
    }


@pytest.mark.parametrize("output", ("not-json", "[]"))
def test_cli_kanban_json_parser_rejects_invalid_host_output(output: str) -> None:
    with pytest.raises(RuntimeError, match="Hermes Kanban CLI returned"):
        cli._parse_cli_json(output)


def test_cli_kanban_dispatch_propagates_host_command_failure() -> None:
    payload = json.loads(
        cli._dispatch_kanban_cli(
            lambda command: (2, f"failed: {' '.join(command)}"),
            "kanban_show",
            {"board": "daidala-test", "task_id": "t_missing"},
        )
    )

    assert payload["ok"] is False
    assert "t_missing" in payload["error"]
