from __future__ import annotations

import pytest

from daidala.gateway import (
    classify_gateway_status,
    probe_profile_gateway,
    probe_profile_gateways,
    stopped_worker_gateways,
    validate_profile_name,
)


@pytest.mark.parametrize(
    ("exit_code", "output", "expected"),
    (
        (0, "Active: active (running)\nUser gateway service is running", "running"),
        (3, "User gateway service is stopped", "stopped"),
        (0, "Gateway is not running", "stopped"),
        (0, "Active: inactive (dead)", "stopped"),
        (
            0,
            "Stale gateway_state.json: recorded state 'running' but the recorded "
            "process is gone\nUser gateway service is stopped",
            "stopped",
        ),
        (1, "unexpected failure", "unavailable"),
        (0, "", "unavailable"),
    ),
)
def test_classify_gateway_status(exit_code: int, output: str, expected: str) -> None:
    assert classify_gateway_status(exit_code, output) == expected


def test_invalid_profile_name_is_rejected() -> None:
    with pytest.raises(ValueError, match="invalid worker profile name"):
        validate_profile_name("bad;profile")


def test_probe_collects_unique_profiles_in_order() -> None:
    calls: list[tuple[str, ...]] = []

    def runner(command: tuple[str, ...]) -> tuple[int, str]:
        calls.append(command)
        profile = command[2]
        if profile == "worker-b":
            return 3, "Gateway is not running"
        return 0, "Active: active (running)"

    statuses = probe_profile_gateways(("worker-a", "worker-b", "worker-a"), runner)

    assert [row.to_dict() for row in statuses] == [
        {"profile": "worker-a", "status": "running"},
        {"profile": "worker-b", "status": "stopped"},
    ]
    assert calls == [
        ("hermes", "-p", "worker-a", "gateway", "status"),
        ("hermes", "-p", "worker-b", "gateway", "status"),
    ]
    assert stopped_worker_gateways(statuses) == ("worker-b",)


def test_probe_treats_host_exceptions_as_unavailable() -> None:
    def runner(_command: tuple[str, ...]) -> tuple[int, str]:
        raise OSError("hermes missing")

    status = probe_profile_gateway("demo-worker", runner)

    assert status.status == "unavailable"
    assert stopped_worker_gateways((status,)) == ("demo-worker",)
