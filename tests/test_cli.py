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
from daidala.cycles import CycleMode
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
class FakeArtifactEntry:
    def to_dict(self) -> dict[str, object]:
        return {
            "artifact_id": "a" * 64,
            "workflow_id": "wf-1",
            "kind": "stage",
            "stage": "plan",
            "policy_revision": 1,
            "plan_revision": 0,
            "digest": "b" * 64,
            "recorded_at": "2026-07-27T08:00:00+00:00",
            "size": 14,
            "availability": "active",
            "approval_summary_digest": None,
        }


@dataclass
class FakeArtifactText:
    content: str = "# Exact plan\n"


@dataclass
class FakeArtifactExport:
    destination: Path

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact_id": "a" * 64,
            "workflow_id": "wf-1",
            "digest": "b" * 64,
            "size": 14,
            "destination": str(self.destination),
        }


@dataclass
class FakeReviewPreview:
    digest: str = "b" * 64

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "daidala.review-decision-preview/v1",
            "review_digest": "a" * 64,
            "action": "request_revision",
            "rationale": "Revise the exact plan boundary.",
            "preview_digest": self.digest,
        }


@dataclass
class FakeCuratorPayload:
    operation: str
    digest: str = "d" * 64

    def to_dict(self) -> dict[str, object]:
        return {
            "operation": self.operation,
            "state_digest": "c" * 64,
            "preview_digest": self.digest,
            "workflow_id": "wf-1",
            "archive_id": "e" * 64,
            "actions": [],
        }


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

    def list_artifacts(self, workflow_id: str) -> tuple[FakeArtifactEntry, ...]:
        self.calls.append(("list_artifacts", (workflow_id,), {}))
        if self.fail:
            raise RuntimeError("service failed")
        return (FakeArtifactEntry(),)

    def read_artifact_text(self, workflow_id: str, artifact_id: str) -> FakeArtifactText:
        self.calls.append(("read_artifact_text", (workflow_id, artifact_id), {}))
        if self.fail:
            raise RuntimeError("service failed")
        return FakeArtifactText()

    def export_artifact(
        self,
        workflow_id: str,
        artifact_id: str,
        output: Path,
        *,
        overwrite: bool = False,
    ) -> FakeArtifactExport:
        self.calls.append(
            (
                "export_artifact",
                (workflow_id, artifact_id, output),
                {"overwrite": overwrite},
            )
        )
        if self.fail:
            raise RuntimeError("service failed")
        return FakeArtifactExport(destination=output)

    def replace_constraint_input(self, workflow_id: str, **kwargs: Any) -> FakeState:
        return self._call("replace_constraint_input", workflow_id, **kwargs)

    def approve(self, workflow_id: str, *, plan_digest: str) -> FakeState:
        return self._call("approve", workflow_id, plan_digest=plan_digest)

    def cancel(self, workflow_id: str, *, reason: str) -> FakeState:
        return self._call("cancel", workflow_id, reason=reason)

    def review_packet(self, workflow_id: str) -> dict[str, object]:
        self.calls.append(("review_packet", (workflow_id,), {}))
        if self.fail:
            raise RuntimeError("service failed")
        return {
            "workflow_id": workflow_id,
            "review_digest": "a" * 64,
            "allowed_actions": ["request_revision"],
        }

    def preview_review_decision(self, workflow_id: str, **kwargs: Any) -> FakeReviewPreview:
        self.calls.append(("preview_review_decision", (workflow_id,), kwargs))
        if self.fail:
            raise RuntimeError("service failed")
        return FakeReviewPreview()

    def apply_review_decision(self, workflow_id: str, **kwargs: Any) -> dict[str, object]:
        self.calls.append(("apply_review_decision", (workflow_id,), kwargs))
        if self.fail:
            raise RuntimeError("service failed")
        return {
            "replayed": False,
            "workflow": {"workflow_id": workflow_id, "plan_revision": 1},
            "review": {"cards": {"plan": "task-plan-1"}},
        }

    def combined_status(self, workflow_id: str) -> list[FakeCardStatus]:
        self.calls.append(("combined_status", (workflow_id,), {}))
        return [FakeCardStatus()]

    def curator_status(self) -> FakeCuratorPayload:
        self.calls.append(("curator_status", (), {}))
        return FakeCuratorPayload("status")

    def preview_curator_run(self) -> FakeCuratorPayload:
        self.calls.append(("preview_curator_run", (), {}))
        return FakeCuratorPayload("run")

    def apply_curator_run(self, *, expected_preview_digest: str) -> FakeCuratorPayload:
        return self._curator_call(
            "apply_curator_run", "run", expected_preview_digest=expected_preview_digest
        )

    def preview_curator_pin(self, workflow_id: str, *, pinned: bool) -> FakeCuratorPayload:
        return self._curator_call(
            "preview_curator_pin", "pin" if pinned else "unpin", workflow_id, pinned=pinned
        )

    def apply_curator_pin(
        self, workflow_id: str, *, pinned: bool, expected_preview_digest: str
    ) -> FakeCuratorPayload:
        return self._curator_call(
            "apply_curator_pin",
            "pin" if pinned else "unpin",
            workflow_id,
            pinned=pinned,
            expected_preview_digest=expected_preview_digest,
        )

    def preview_curator_archive(self, workflow_id: str) -> FakeCuratorPayload:
        return self._curator_call("preview_curator_archive", "archive", workflow_id)

    def apply_curator_archive(
        self, workflow_id: str, *, expected_preview_digest: str
    ) -> FakeCuratorPayload:
        return self._curator_call(
            "apply_curator_archive",
            "archive",
            workflow_id,
            expected_preview_digest=expected_preview_digest,
        )

    def list_curator_archives(self) -> tuple[dict[str, object], ...]:
        self.calls.append(("list_curator_archives", (), {}))
        return ({"workflow_id": "wf-1", "archive_id": "e" * 64, "member_count": 3},)

    def preview_curator_restore(
        self, workflow_id: str, archive_id: str
    ) -> FakeCuratorPayload:
        return self._curator_call(
            "preview_curator_restore", "restore", workflow_id, archive_id
        )

    def apply_curator_restore(
        self,
        workflow_id: str,
        archive_id: str,
        *,
        expected_preview_digest: str,
    ) -> FakeCuratorPayload:
        return self._curator_call(
            "apply_curator_restore",
            "restore",
            workflow_id,
            archive_id,
            expected_preview_digest=expected_preview_digest,
        )

    def _curator_call(
        self,
        name: str,
        operation: str,
        *args: Any,
        **kwargs: Any,
    ) -> FakeCuratorPayload:
        self.calls.append((name, args, kwargs))
        if self.fail:
            raise RuntimeError("service failed")
        return FakeCuratorPayload(operation)


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


def test_artifact_list_json_is_byte_identical_across_both_cli_surfaces(capsys) -> None:
    standalone = FakeService()
    native = FakeService()
    argv = ["artifacts", "list", "wf-1", "--json"]

    standalone_code = cli.main(argv, service_factory=_factory(standalone))
    standalone_output = capsys.readouterr().out
    native_code = cli.run_command(_host_args(argv), service_factory=_factory(native))
    native_output = capsys.readouterr().out

    assert standalone_code == native_code == 0
    assert standalone_output == native_output
    assert standalone.calls == native.calls == [("list_artifacts", ("wf-1",), {})]
    payload = json.loads(native_output)
    assert payload["operation"] == "artifacts-list"
    assert payload["artifacts"][0]["artifact_id"] == "a" * 64
    assert "content" not in native_output


def test_artifact_list_human_output_contains_metadata_only(capsys) -> None:
    service = FakeService()

    assert cli.main(["artifacts", "list", "wf-1"], service_factory=_factory(service)) == 0
    output = capsys.readouterr().out

    assert output.startswith("artifact_id\tkind\tstage\tpolicy_revision")
    assert "plan" in output
    assert "# Exact plan" not in output


@pytest.mark.parametrize("operation", ("show", "export"))
def test_artifact_show_and_export_have_native_standalone_parity(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    operation: str,
) -> None:
    standalone = FakeService()
    native = FakeService()
    argv = ["artifacts", operation, "wf-1", "a" * 64]
    if operation == "export":
        argv.extend(["--output", str(tmp_path / "artifact.bin"), "--overwrite"])

    standalone_code = cli.main(argv, service_factory=_factory(standalone))
    standalone_output = capsys.readouterr().out
    native_code = cli.run_command(_host_args(argv), service_factory=_factory(native))
    native_output = capsys.readouterr().out

    assert standalone_code == native_code == 0
    assert standalone_output == native_output
    assert standalone.calls == native.calls
    if operation == "show":
        assert native_output == "# Exact plan\n"
        assert native.calls[0][0] == "read_artifact_text"
    else:
        assert json.loads(native_output)["operation"] == "artifacts-export"
        assert native.calls[0][0] == "export_artifact"
        assert native.calls[0][2] == {"overwrite": True}


def test_artifact_errors_are_nonzero_content_free_and_equivalent(capsys) -> None:
    standalone = FakeService(fail=True)
    native = FakeService(fail=True)
    argv = ["artifacts", "show", "wf-1", "a" * 64]

    standalone_code = cli.main(argv, service_factory=_factory(standalone))
    standalone_output = capsys.readouterr().out
    native_code = cli.run_command(_host_args(argv), service_factory=_factory(native))
    native_output = capsys.readouterr().out

    assert standalone_code == native_code == 1
    assert standalone_output == native_output
    assert json.loads(native_output) == {
        "success": False,
        "error": "RuntimeError",
        "message": "service failed",
    }
    assert "# Exact plan" not in native_output


@pytest.mark.parametrize(
    "argv",
    [
        ["curator", "status"],
        ["curator", "run"],
        ["curator", "pin", "wf-1"],
        ["curator", "unpin", "wf-1"],
        ["curator", "archive", "wf-1"],
        ["curator", "list-archived"],
        ["curator", "restore", "wf-1", "e" * 64],
    ],
)
def test_curator_commands_are_dry_run_first_and_have_native_standalone_parity(
    argv: list[str], capsys
) -> None:
    standalone = FakeService()
    native = FakeService()

    standalone_code = cli.main(argv, service_factory=_factory(standalone))
    standalone_output = capsys.readouterr().out
    native_code = cli.run_command(_host_args(argv), service_factory=_factory(native))
    native_output = capsys.readouterr().out

    assert standalone_code == native_code == 0
    assert standalone.calls == native.calls
    assert json.loads(standalone_output) == json.loads(native_output)
    payload = json.loads(native_output)
    if argv[1] not in {"status", "list-archived"}:
        assert payload["dry_run"] is True


@pytest.mark.parametrize(
    ("argv", "service_method"),
    [
        (["curator", "run"], "apply_curator_run"),
        (["curator", "pin", "wf-1"], "apply_curator_pin"),
        (["curator", "unpin", "wf-1"], "apply_curator_pin"),
        (["curator", "archive", "wf-1"], "apply_curator_archive"),
        (
            ["curator", "restore", "wf-1", "e" * 64],
            "apply_curator_restore",
        ),
    ],
)
def test_curator_apply_requires_and_forwards_exact_preview_digest(
    argv: list[str], service_method: str, capsys
) -> None:
    missing = FakeService()
    assert cli.main([*argv, "--apply"], service_factory=_factory(missing)) == 1
    assert "--expected-preview-digest" in capsys.readouterr().out
    assert missing.calls == []

    service = FakeService()
    digest = "d" * 64
    assert (
        cli.main(
            [*argv, "--apply", "--expected-preview-digest", digest],
            service_factory=_factory(service),
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["dry_run"] is False
    assert service.calls[0][0] == service_method
    assert service.calls[0][2]["expected_preview_digest"] == digest


def test_review_show_uses_identical_standalone_and_native_dispatch(capsys) -> None:
    standalone = FakeService()
    native = FakeService()
    argv = ["review", "show", "wf-1"]

    standalone_code = cli.main(argv, service_factory=_factory(standalone))
    standalone_payload = json.loads(capsys.readouterr().out)
    native_code = cli.run_command(_host_args(argv), service_factory=_factory(native))
    native_payload = json.loads(capsys.readouterr().out)

    assert standalone_code == native_code == 0
    assert standalone.calls == native.calls == [("review_packet", ("wf-1",), {})]
    assert standalone_payload == native_payload
    assert native_payload["review"]["review_digest"] == "a" * 64


@pytest.mark.parametrize(
    ("cli_action", "service_action"),
    [
        ("accept-delivery", "accept_delivery"),
        ("request-revision", "request_revision"),
        ("reject-workflow", "reject_workflow"),
    ],
)
def test_review_decision_preview_maps_actions_without_persisting_file_path(
    tmp_path: Path,
    capsys,
    cli_action: str,
    service_action: str,
) -> None:
    rationale = tmp_path / "rationale.txt"
    rationale.write_text("Revise the exact plan boundary.\n", encoding="utf-8")
    standalone = FakeService()
    native = FakeService()
    argv = [
        "review",
        "decide",
        "wf-1",
        cli_action,
        "--rationale-file",
        str(rationale),
    ]

    standalone_code = cli.main(argv, service_factory=_factory(standalone))
    standalone_output = capsys.readouterr().out
    native_code = cli.run_command(_host_args(argv), service_factory=_factory(native))
    native_output = capsys.readouterr().out

    assert standalone_code == native_code == 0
    assert standalone.calls == native.calls
    assert standalone.calls[0][0] == "preview_review_decision"
    assert standalone.calls[0][2]["action"] == service_action
    assert standalone.calls[0][2]["rationale"] == "Revise the exact plan boundary.\n"
    assert json.loads(standalone_output) == json.loads(native_output)
    assert json.loads(native_output)["dry_run"] is True
    assert str(rationale) not in standalone_output
    assert str(rationale) not in native_output


def test_review_decision_apply_requires_and_forwards_exact_digests(
    tmp_path: Path,
    capsys,
) -> None:
    rationale = tmp_path / "rationale.txt"
    rationale.write_text("Revise the exact plan boundary.\n", encoding="utf-8")
    service = FakeService()
    base = [
        "review",
        "decide",
        "wf-1",
        "request-revision",
        "--rationale-file",
        str(rationale),
        "--apply",
    ]

    missing_code = cli.main(base, service_factory=_factory(service))
    missing_payload = json.loads(capsys.readouterr().out)
    assert missing_code == 1
    assert service.calls == []
    assert "requires --expected-review-digest" in missing_payload["message"]

    standalone = FakeService()
    native = FakeService()
    argv = [
        *base,
        "--expected-review-digest",
        "a" * 64,
        "--expected-preview-digest",
        "b" * 64,
    ]
    standalone_code = cli.main(argv, service_factory=_factory(standalone))
    standalone_payload = json.loads(capsys.readouterr().out)
    native_code = cli.run_command(_host_args(argv), service_factory=_factory(native))
    native_payload = json.loads(capsys.readouterr().out)

    assert standalone_code == native_code == 0
    assert standalone.calls == native.calls
    name, positional, keywords = native.calls[0]
    assert name == "apply_review_decision"
    assert positional == ("wf-1",)
    assert keywords["expected_review_digest"] == "a" * 64
    assert keywords["expected_preview_digest"] == "b" * 64
    assert keywords["confirm"] is True
    assert native_payload == standalone_payload
    assert native_payload["workflow"]["plan_revision"] == 1
    assert native_payload["review"]["cards"]["plan"] == "task-plan-1"
    assert str(rationale) not in json.dumps(native_payload)


@pytest.mark.parametrize("kind", ["symlink", "oversized"])
def test_review_decision_rejects_unsafe_rationale_files(
    tmp_path: Path,
    capsys,
    kind: str,
) -> None:
    target = tmp_path / "target.txt"
    target.write_text("Review rationale.\n", encoding="utf-8")
    rationale = tmp_path / "rationale.txt"
    if kind == "symlink":
        rationale.symlink_to(target)
    else:
        rationale.write_text("x" * 4097, encoding="utf-8")
    service = FakeService()

    code = cli.main(
        [
            "review",
            "decide",
            "wf-1",
            "request-revision",
            "--rationale-file",
            str(rationale),
        ],
        service_factory=_factory(service),
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 1
    assert service.calls == []
    assert "rationale-file" in payload["message"]


def test_review_cli_exposes_no_direct_phase_rewind() -> None:
    with pytest.raises(SystemExit):
        _host_args(["review", "move", "wf-1", "plan"])


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

    assert cli.main(["init"]) == 0
    preview = json.loads(capsys.readouterr().out)["preview"]

    result = cli.main(
        ["init", "--apply", "--preview-digest", preview["preview_digest"], "--confirm"]
    )
    payload = json.loads(capsys.readouterr().out)

    assert result == 0
    assert payload["dry_run"] is False
    assert Path(payload["database"]).is_file()
    assert Path(payload["database"]).parent == tmp_path / "daidala"
    assert payload["created"] is True
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
        "--mode",
        "evaluate-pack",
        "--candidate-identity",
        "pack:aidlc:e49341dbeb8af82758dd85e96ed7fe9bcf38a447",
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
    assert native.calls[0][1]["mode"] is CycleMode.EVALUATE_PACK
    assert native.calls[0][1]["candidate_identity"] == (
        "pack:aidlc:e49341dbeb8af82758dd85e96ed7fe9bcf38a447"
    )
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
        "--mode",
        "evaluate-pack",
        "--candidate-identity",
        "pack:aidlc:e49341dbeb8af82758dd85e96ed7fe9bcf38a447",
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
    assert service.calls[0][1]["mode"] is CycleMode.EVALUATE_PACK
    assert service.calls[0][1]["candidate_identity"] == (
        "pack:aidlc:e49341dbeb8af82758dd85e96ed7fe9bcf38a447"
    )
    assert payload["dry_run"] is False


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        (["--mode", "evaluate-pack"], "requires --candidate-identity"),
        (["--candidate-identity", "pack:aidlc"], "requires a comparison mode"),
    ],
)
def test_project_cycle_admission_rejects_incomplete_comparison_identity_before_service(
    extra: list[str], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
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
            *extra,
        ],
        project_cycle_factory=_project_cycle_factory(service),
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 1
    assert service.calls == []
    assert message in payload["message"]


def test_project_cycle_admit_help_exposes_comparison_identity_on_both_surfaces(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as standalone_exit:
        cli.build_parser(prog="daidala").parse_args(["project-cycle", "admit", "--help"])
    standalone = capsys.readouterr().out
    native_parser = argparse.ArgumentParser(prog="hermes daidala")
    cli.register_cli(native_parser)
    with pytest.raises(SystemExit) as native_exit:
        native_parser.parse_args(["project-cycle", "admit", "--help"])
    native = capsys.readouterr().out

    assert standalone_exit.value.code == native_exit.value.code == 0
    for option in ("--mode", "--candidate-identity"):
        assert option in standalone
        assert option in native
    assert "evaluate-pack" in standalone
    assert "evaluate-pack" in native


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


@pytest.mark.parametrize(
    "argv",
    [
        ["packs", "list"],
        ["packs", "validate", "addyosmani"],
        ["packs", "validate", "aidlc"],
    ],
)
def test_stateless_pack_commands_do_not_resolve_a_profile_root(
    argv: list[str], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail_root_resolution() -> Path:
        raise AssertionError("stateless pack command must not resolve a profile root")

    monkeypatch.setattr(cli, "resolve_data_root", fail_root_resolution)

    standalone_code = cli.main(argv)
    standalone = json.loads(capsys.readouterr().out)
    host_code = cli.run_command(_host_args(argv))
    host = json.loads(capsys.readouterr().out)

    assert host_code == standalone_code == 0
    assert host == standalone
    assert standalone["success"] is True
    if argv[1] == "validate":
        assert standalone["name"] == argv[2]


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


def test_cli_kanban_dispatch_translates_unblock_command() -> None:
    commands: list[tuple[str, ...]] = []

    result = json.loads(
        cli._dispatch_kanban_cli(
            lambda command: (commands.append(command) or 0, ""),
            "kanban_unblock",
            {"board": "daidala-test", "task_id": "t_verify", "reason": "evidence recorded"},
        )
    )

    assert result == {"ok": True, "task_id": "t_verify", "error": None}
    assert commands == [
        (
            "hermes", "kanban", "--board", "daidala-test", "unblock", "t_verify",
            "--reason", "evidence recorded",
        )
    ]


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
