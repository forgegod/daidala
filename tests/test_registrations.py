from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from daidala.errors import PolicyViolationError
from daidala.projects import parse_project_manifest
from daidala.registrations import (
    ControllerRegistration,
    parse_controller_registration,
    registration_path,
)

ROOT = Path(__file__).parents[1]


def registration_content() -> str:
    return """\
schema: daidala.controller-registration/v1
project_id: forgegod-daidala
checkout: /srv/daidala
controller_profile: daidala-self-improvement
board: daidala-forgegod-daidala
repository_identity:
  canonical: forgegod/daidala
  verified_remote: git@github.com:forgegod/daidala.git
credentials:
  intake: github-daidala-read-issues
  findings: github-daidala-write-issues
approval:
  maintainers: [local-operator]
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


def test_registration_round_trip_manifest_binding_and_profile_storage_path() -> None:
    registration = parse_controller_registration(registration_content())
    manifest = parse_project_manifest((ROOT / ".daidala/project.yaml").read_text())

    registration.validate_manifest(manifest)
    assert ControllerRegistration.from_dict(registration.to_dict()) == registration
    assert registration_path(Path("/var/lib/hermes/profile"), registration.project_id) == Path(
        "/var/lib/hermes/profile/projects/forgegod-daidala/registration.yaml"
    )
    assert len(registration.digest) == 64


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda raw: raw.update({"extra": True}), "unknown"),
        (lambda raw: raw.update({"checkout": "../daidala"}), "absolute POSIX"),
        (lambda raw: raw.update({"checkout": "/srv/daidala/"}), "absolute POSIX"),
        (
            lambda raw: raw["evaluator"].update({"backend": "local-shell"}),
            "restricted-container",
        ),
        (
            lambda raw: raw["limits"].update({"active_cycles": 2}),
            "1 to 1",
        ),
        (
            lambda raw: raw["credentials"].update(
                {"findings": raw["credentials"]["intake"]}
            ),
            "distinct aliases",
        ),
    ],
)
def test_registration_invalid_authority_and_bounds_fail_closed(
    mutate: object, message: str
) -> None:
    raw = yaml.safe_load(registration_content())
    mutate(raw)  # type: ignore[operator]
    with pytest.raises(PolicyViolationError, match=message):
        ControllerRegistration.from_dict(raw)


def test_registration_mismatch_cannot_repair_manifest_identity() -> None:
    raw = yaml.safe_load(registration_content())
    raw["repository_identity"]["canonical"] = "forgegod/other"
    registration = ControllerRegistration.from_dict(raw)
    manifest = parse_project_manifest((ROOT / ".daidala/project.yaml").read_text())

    with pytest.raises(PolicyViolationError, match="does not match manifest"):
        registration.validate_manifest(manifest)


def test_registration_path_requires_hermes_resolved_absolute_root() -> None:
    with pytest.raises(PolicyViolationError, match="absolute resolved"):
        registration_path(Path("relative/profile"), "forgegod-daidala")
    with pytest.raises(PolicyViolationError, match="absolute resolved"):
        registration_path(Path("/profile/../other"), "forgegod-daidala")
