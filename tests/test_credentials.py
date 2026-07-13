from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from daidala.credentials import (
    CredentialBindings,
    credential_bindings_path,
    parse_credential_bindings,
)
from daidala.errors import PolicyViolationError


def bindings_content() -> str:
    return """\
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


def test_credential_bindings_round_trip_and_resolve_only_explicit_environment_names() -> None:
    bindings = parse_credential_bindings(bindings_content())

    assert CredentialBindings.from_dict(bindings.to_dict()) == bindings
    assert bindings.resolve(
        "github-daidala-read-issues",
        {"DAIDALA_GITHUB_INTAKE_TOKEN": "secret-value", "GH_TOKEN": "wrong"},
    ) == "secret-value"


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda raw: raw.update({"token": "secret"}), "unknown"),
        (
            lambda raw: raw["bindings"][0].update({"resolver": "bitwarden"}),
            "resolver must be 'environment'",
        ),
        (
            lambda raw: raw["bindings"][0].update({"environment_variable": "GH_TOKEN"}),
            "alias-specific",
        ),
        (
            lambda raw: raw["bindings"][1].update(
                {"environment_variable": raw["bindings"][0]["environment_variable"]}
            ),
            "cannot reuse",
        ),
    ],
)
def test_credential_bindings_reject_values_inference_and_ambiguous_environment_mapping(
    mutate: object, message: str
) -> None:
    raw = yaml.safe_load(bindings_content())
    mutate(raw)  # type: ignore[operator]

    with pytest.raises(PolicyViolationError, match=message):
        CredentialBindings.from_dict(raw)


def test_credential_resolution_fails_closed_for_missing_variable_or_alias() -> None:
    bindings = parse_credential_bindings(bindings_content())

    with pytest.raises(PolicyViolationError, match="unavailable"):
        bindings.resolve("github-daidala-read-issues", {})
    with pytest.raises(PolicyViolationError, match="no explicit binding"):
        bindings.resolve("missing-alias", {})


def test_credential_binding_path_is_profile_local_to_registration() -> None:
    registration = Path("/profile/projects/forgegod-daidala/registration.yaml")

    assert credential_bindings_path(registration) == registration.with_name(
        "credential-bindings.yaml"
    )
    with pytest.raises(PolicyViolationError, match="absolute"):
        credential_bindings_path(Path("projects/registration.yaml"))
