"""Classify Hermes gateway liveness for worker profiles.

The Kanban dispatcher that claims Ready cards runs inside a Hermes gateway.
Start and dashboard readiness therefore treat each selected worker profile's
gateway as mandatory. This module is a pure host-output classifier plus a
bounded command probe; it never starts a gateway.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

CommandRunner = Callable[[tuple[str, ...]], tuple[int, str]]

GatewayState = Literal["running", "stopped", "unavailable"]

_PROFILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")


@dataclass(frozen=True)
class GatewayStatus:
    profile: str
    status: GatewayState

    def to_dict(self) -> dict[str, str]:
        return {"profile": self.profile, "status": self.status}


def classify_gateway_status(exit_code: int, output: str) -> GatewayState:
    """Map a ``hermes gateway status`` result onto a finite readiness state."""

    if not isinstance(exit_code, int) or isinstance(exit_code, bool):
        return "unavailable"
    normalized = output.lower() if isinstance(output, str) else ""
    if (
        "stopped" in normalized
        or "not running" in normalized
        or "inactive (dead)" in normalized
    ):
        return "stopped"
    if exit_code == 0 and re.search(r"\brunning\b", normalized):
        return "running"
    return "unavailable"


def validate_profile_name(profile: str) -> str:
    """Return a safe worker profile name or raise ``ValueError``."""

    name = profile.strip()
    if _PROFILE_RE.fullmatch(name) is None:
        raise ValueError(f"invalid worker profile name: {profile!r}")
    return name


def probe_profile_gateway(profile: str, runner: CommandRunner) -> GatewayStatus:
    """Run the documented Hermes gateway-status command for one profile."""

    name = validate_profile_name(profile)
    try:
        exit_code, output = runner(("hermes", "-p", name, "gateway", "status"))
    except Exception:  # host boundary; never leak probe internals
        return GatewayStatus(profile=name, status="unavailable")
    return GatewayStatus(profile=name, status=classify_gateway_status(exit_code, output))


def probe_profile_gateways(
    profiles: Sequence[str], runner: CommandRunner
) -> tuple[GatewayStatus, ...]:
    """Probe unique worker profiles in stable order."""

    unique: list[str] = []
    seen: set[str] = set()
    for profile in profiles:
        name = validate_profile_name(profile)
        if name in seen:
            continue
        seen.add(name)
        unique.append(name)
    return tuple(probe_profile_gateway(name, runner) for name in unique)


def stopped_worker_gateways(statuses: Sequence[GatewayStatus]) -> tuple[str, ...]:
    """Return worker profile names whose gateway is not running."""

    return tuple(row.profile for row in statuses if row.status != "running")
