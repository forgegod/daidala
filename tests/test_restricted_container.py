from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path

import pytest

from daidala.restricted_container import (
    ContainerIsolationError,
    RestrictedContainerExecutor,
    RestrictedContainerRequest,
    probe_restricted_container,
)

DIGEST = "3220992391c1182a0cfe4c64453511772c54f4c39e960d26a5e327960675982e"
IMAGE = f"catthehacker/ubuntu@sha256:{DIGEST}"
CONTROLLER_REVISION = "8" * 40
IMAGE_INSPECTION = json.dumps(
    {
        "Id": f"sha256:{DIGEST}",
        "RepoDigests": [IMAGE],
        "Config": {"Volumes": None},
    }
)
PROBE_OUTPUT = "\n".join(
    [
        "schema=daidala.restricted-container-probe/v1",
        "home=/home/evaluator",
        "hermes_home=/home/evaluator",
        "home_was_fresh=true",
        "workspace_writable=true",
        "network_interfaces=lo",
        "environment_keys=DAIDALA_EVALUATOR_PROBE,HOME,HERMES_HOME,HOSTNAME,LANG,PATH",
    ]
)


@dataclass
class FakeRunner:
    results: list[tuple[int, str]]
    calls: list[tuple[tuple[str, ...], Mapping[str, str]]] = field(default_factory=list)

    def __call__(
        self, command: tuple[str, ...], environment: Mapping[str, str]
    ) -> tuple[int, str]:
        self.calls.append((command, dict(environment)))
        return self.results.pop(0)


def _runner(probe_output: str = PROBE_OUTPUT) -> FakeRunner:
    return FakeRunner([(0, IMAGE_INSPECTION), (0, probe_output)])


def test_probe_runs_exact_restricted_container_policy_without_forwarding_credentials() -> None:
    runner = _runner()

    evidence = probe_restricted_container(
        IMAGE,
        runner=runner,
        environ={
            "PATH": "/usr/bin",
            "LANG": "C.UTF-8",
            "GH_TOKEN": "must-not-reach-child",
            "HERMES_HOME": "/controller/home",
        },
        uid=1000,
        gid=1000,
    )

    assert evidence.to_dict() == {
        "backend": "restricted-container",
        "network": "denied-by-default",
        "image_identity": IMAGE,
        "fresh_home": True,
        "network_denied": True,
        "controller_credentials_absent": True,
        "bounded_mounts": True,
        "receipt_id": evidence.receipt_id,
    }
    assert evidence.receipt_id.startswith("sha256:")
    assert len(evidence.receipt_id) == 71

    inspect_command, inspect_environment = runner.calls[0]
    run_command, run_environment = runner.calls[1]
    assert inspect_command == (
        "docker",
        "image",
        "inspect",
        IMAGE,
        "--format",
        "{{json .}}",
    )
    assert inspect_environment == run_environment == {
        "LANG": "C.UTF-8",
        "PATH": "/usr/bin",
    }
    assert run_command[:3] == ("docker", "run", "--rm")
    assert ("--network", "none") == tuple(
        run_command[run_command.index("--network") : run_command.index("--network") + 2]
    )
    assert "--read-only" in run_command
    assert ("--cap-drop", "ALL") == tuple(
        run_command[run_command.index("--cap-drop") : run_command.index("--cap-drop") + 2]
    )
    assert ("--security-opt", "no-new-privileges") == tuple(
        run_command[
            run_command.index("--security-opt") : run_command.index("--security-opt") + 2
        ]
    )
    assert ("--user", "1000:1000") == tuple(
        run_command[run_command.index("--user") : run_command.index("--user") + 2]
    )
    assert run_command.count("--mount") == 1
    mount = run_command[run_command.index("--mount") + 1]
    assert mount.startswith("type=bind,src=")
    assert mount.endswith(",dst=/workspace")
    assert "readonly" not in mount
    assert "GH_TOKEN" not in "\n".join(run_command)
    assert "/controller/home" not in "\n".join(run_command)
    assert run_command[-4:] == (IMAGE, "/bin/sh", "-ceu", run_command[-1])


@pytest.mark.parametrize(
    "image",
    [
        "catthehacker/ubuntu:act-latest",
        "sha256:" + DIGEST,
        "catthehacker/ubuntu@sha256:short",
        "Catthehacker/ubuntu@sha256:" + DIGEST,
    ],
)
def test_probe_rejects_noncanonical_or_unpinned_image_before_docker(
    image: str,
) -> None:
    runner = _runner()

    with pytest.raises(ContainerIsolationError, match="pinned image"):
        probe_restricted_container(image, runner=runner, environ={"PATH": "/usr/bin"})

    assert not runner.calls


def test_probe_rejects_image_with_declared_volumes() -> None:
    inspection = json.dumps(
        {
            "Id": f"sha256:{DIGEST}",
            "RepoDigests": [IMAGE],
            "Config": {"Volumes": {"/host-like-state": {}}},
        }
    )
    runner = FakeRunner([(0, inspection)])

    with pytest.raises(ContainerIsolationError, match="declares volumes"):
        probe_restricted_container(IMAGE, runner=runner, environ={"PATH": "/usr/bin"})

    assert len(runner.calls) == 1


def test_probe_rejects_extra_network_interface() -> None:
    runner = _runner(PROBE_OUTPUT.replace("network_interfaces=lo", "network_interfaces=eth0,lo"))

    with pytest.raises(ContainerIsolationError, match="network isolation"):
        probe_restricted_container(IMAGE, runner=runner, environ={"PATH": "/usr/bin"})


def test_probe_rejects_sensitive_environment_key_from_image() -> None:
    runner = _runner(
        PROBE_OUTPUT.replace(
            "HOSTNAME,LANG,PATH",
            "GITHUB_TOKEN,HOSTNAME,LANG,PATH",
        )
    )

    with pytest.raises(ContainerIsolationError, match="credential-like environment"):
        probe_restricted_container(IMAGE, runner=runner, environ={"PATH": "/usr/bin"})


def test_probe_rejects_failed_container_and_oversized_output() -> None:
    failed = FakeRunner([(0, IMAGE_INSPECTION), (17, "probe failed")])
    with pytest.raises(ContainerIsolationError, match="exited with 17"):
        probe_restricted_container(IMAGE, runner=failed, environ={"PATH": "/usr/bin"})
    oversized = FakeRunner([(0, IMAGE_INSPECTION), (0, "x" * 65_537)])
    with pytest.raises(ContainerIsolationError, match="output exceeds"):
        probe_restricted_container(IMAGE, runner=oversized, environ={"PATH": "/usr/bin"})


def _request_files() -> list[tuple[str, str]]:
    fixture_src = (
        "from calculator import answer\n\n\n"
        "class TestAnswer(unittest.TestCase):\n"
        "    def test_answer(self):\n"
        "        self.assertEqual(answer(), 2)\n"
    )
    return [
        ("calculator.py", "def answer():\n    return 1\n"),
        ("test_calculator.py", fixture_src),
    ]


def _build_request() -> RestrictedContainerRequest:
    from daidala.restricted_container import RestrictedContainerRequest

    return RestrictedContainerRequest(
        workflow_id="cycle-" + "0" * 64,
        role="baseline",
        repository_revision="9" * 40,
        controller_revision=CONTROLLER_REVISION,
        image_identity=IMAGE,
        files=tuple(_request_files()),
        command=("/bin/sh", "-c", "python3 -m unittest test_calculator.py"),
        expected_exit_code=1,
    )


def test_request_loads_and_rejects_malformed_payload(tmp_path: Path) -> None:
    from daidala.restricted_container import load_restricted_container_request

    request = _build_request()
    payload_path = tmp_path / "request.json"
    payload_path.write_text(json.dumps(request.to_dict()), encoding="utf-8")

    loaded = load_restricted_container_request(payload_path)
    assert loaded == request
    assert loaded.digest == request.digest
    assert loaded.to_dict()["schema"] == "daidala.restricted-container-request/v2"
    assert loaded.to_dict()["controller_revision"] == CONTROLLER_REVISION

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema": "wrong"}), encoding="utf-8")
    with pytest.raises(ContainerIsolationError, match="fields are invalid"):
        load_restricted_container_request(bad)
    overflow = tmp_path / "overflow.json"
    overflow.write_text("x" * (1_048_577), encoding="utf-8")
    with pytest.raises(ContainerIsolationError, match="exceeds 1048576 bytes"):
        load_restricted_container_request(overflow)


@pytest.mark.parametrize(
    "controller_revision",
    [None, "8" * 39, "8" * 41, "8" * 64, "A" * 40, "g" * 40, 8],
)
def test_request_rejects_invalid_controller_revision(
    controller_revision: object,
) -> None:
    raw = _build_request().to_dict()
    raw["controller_revision"] = controller_revision

    with pytest.raises(ContainerIsolationError, match="controller revision"):
        RestrictedContainerRequest.from_dict(raw)


def test_request_rejects_v1_missing_and_unknown_fields() -> None:
    raw = _build_request().to_dict()

    for mutate in (
        lambda value: value.update(schema="daidala.restricted-container-request/v1"),
        lambda value: value.pop("controller_revision"),
        lambda value: value.update(unknown=True),
    ):
        malformed = dict(raw)
        mutate(malformed)
        with pytest.raises(ContainerIsolationError):
            RestrictedContainerRequest.from_dict(malformed)


def test_request_run_retains_immutable_evidence_and_rejects_drift(tmp_path: Path) -> None:
    from daidala.restricted_container import run_restricted_container_request

    class SequencedRunner:
        def __init__(self, fixtures: list[tuple[int, str]]) -> None:
            self.fixtures = list(fixtures)
            self.calls: list[tuple[tuple[str, ...], Mapping[str, str]]] = []

        def __call__(
            self, command: tuple[str, ...], environment: Mapping[str, str]
        ) -> tuple[int, str]:
            self.calls.append((command, dict(environment)))
            return self.fixtures.pop(0)

    runner = SequencedRunner(
        [
            (0, IMAGE_INSPECTION),
            (
                1,
                "F\n======================================================================\n"
                "FAIL: test_answer (test_calculator.TestAnswer)\n"
                "--------------------------------------------------------------------\n"
                "AssertionError: 1 != 2\n",
            ),
            (0, IMAGE_INSPECTION),
            (0, "Ran 1 test\nOK"),
        ]
    )
    executor = RestrictedContainerExecutor(
        IMAGE, runner=runner, environ={"PATH": "/usr/bin"}, uid=1000, gid=1000
    )
    evidence, path = run_restricted_container_request(
        _build_request(),
        tmp_path.resolve(),
        executor=executor,
    )
    assert evidence.exit_code == 1
    assert evidence.expected_exit_code == 1
    assert evidence.role == "baseline"
    assert evidence.repository_revision == "9" * 40
    assert evidence.controller_revision == CONTROLLER_REVISION
    assert evidence.request_digest == _build_request().digest
    assert evidence.to_dict()["schema"] == "daidala.restricted-container-execution/v2"
    assert evidence.image_id == f"sha256:{DIGEST}"
    assert path.read_bytes() == json.dumps(
        evidence.to_dict(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    changed_raw = _build_request().to_dict()
    changed_raw["controller_revision"] = "7" * 40
    changed = RestrictedContainerRequest.from_dict(changed_raw)
    assert changed.digest != _build_request().digest

    changed_evidence, changed_path = run_restricted_container_request(
        changed, tmp_path.resolve(), executor=executor
    )
    assert changed_evidence.controller_revision == "7" * 40
    assert changed_evidence.request_digest == changed.digest
    assert changed_evidence.digest != evidence.digest
    assert changed_path != path

    with pytest.raises(ContainerIsolationError, match="execution schema"):
        replace(evidence, schema="daidala.restricted-container-execution/v1")
    with pytest.raises(ContainerIsolationError, match="controller revision"):
        replace(evidence, controller_revision="A" * 40)

    docker_argv, child_environment = runner.calls[1]
    assert CONTROLLER_REVISION not in "\n".join(docker_argv)
    assert CONTROLLER_REVISION not in child_environment.values()
