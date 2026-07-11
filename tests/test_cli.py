from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import pytest

from wingstaff import cli


@dataclass
class FakeState:
    workflow_id: str = "wf-1"

    def to_dict(self) -> dict[str, str]:
        return {"workflow_id": self.workflow_id, "board_slug": "wingstaff-test"}


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
