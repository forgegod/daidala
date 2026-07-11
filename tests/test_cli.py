from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import pytest

from wingstaff import cli

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


@dataclass
class FakeState:
    workflow_id: str = "wf-1"

    def to_dict(self) -> dict[str, str]:
        return {"workflow_id": self.workflow_id, "board_slug": "wingstaff-test"}


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

    def approve(self, workflow_id: str, *, plan_digest: str) -> FakeState:
        return self._call("approve", workflow_id, plan_digest=plan_digest)

    def cancel(self, workflow_id: str, *, reason: str) -> FakeState:
        return self._call("cancel", workflow_id, reason=reason)

    def combined_status(self, workflow_id: str) -> list[FakeCardStatus]:
        self.calls.append(("combined_status", (workflow_id,), {}))
        return [FakeCardStatus()]


def _host_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="hermes wingstaff")
    cli.register_cli(parser)
    return parser.parse_args(argv)


def _factory(service: FakeService) -> cli.ServiceFactory:
    return cast(cli.ServiceFactory, lambda: service)


@pytest.mark.parametrize(
    "argv",
    [
        [
            "start",
            "/repo",
            "Implement feature",
            "--board",
            "wingstaff-test",
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
    assert not (tmp_path / "wingstaff").exists()


def test_init_apply_creates_profile_local_schema(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    result = cli.main(["init", "--apply"])
    payload = json.loads(capsys.readouterr().out)

    assert result == 0
    assert payload["dry_run"] is False
    assert Path(payload["database"]).is_file()
    assert Path(payload["database"]).parent == tmp_path / "wingstaff"


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
            "wingstaff-test",
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
                "board": "wingstaff-test",
                "title": "Define workflow",
                "body": "workflow_id=wf-1 stage=define",
                "assignee": "engineer",
                "parents": [],
                "workspace_path": "/repo",
                "idempotency_key": "wingstaff:wf-1:0:define",
                "skills": ["wingstaff:orchestrate", "aidlc-adapter"],
            },
        )
    )
    shown = json.loads(
        cli._dispatch_kanban_cli(
            run,
            "kanban_show",
            {"board": "wingstaff-test", "task_id": "t_define"},
        )
    )

    assert created == {"ok": True, "status": "ready", "task_id": "t_define"}
    assert shown["task"]["id"] == "t_define"
    assert commands[0] == (
        "hermes",
        "kanban",
        "--board",
        "wingstaff-test",
        "create",
        "Define workflow",
        "--body",
        "workflow_id=wf-1 stage=define",
        "--assignee",
        "engineer",
        "--workspace",
        "dir:/repo",
        "--idempotency-key",
        "wingstaff:wf-1:0:define",
        "--skill",
        "wingstaff:orchestrate",
        "--skill",
        "aidlc-adapter",
        "--json",
    )
    assert commands[1] == (
        "hermes",
        "kanban",
        "--board",
        "wingstaff-test",
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
            {"board": "wingstaff-test", "task_id": "t_missing"},
        )
    )

    assert payload["ok"] is False
    assert "t_missing" in payload["error"]
