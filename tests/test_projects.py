from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
import yaml

from daidala.errors import PolicyViolationError
from daidala.packs import load_pack, pack_content_digest
from daidala.projects import ProjectManifest, parse_project_manifest

ROOT = Path(__file__).parents[1]
MANIFEST_PATH = ROOT / ".daidala" / "project.yaml"


def manifest_content() -> str:
    return MANIFEST_PATH.read_text(encoding="utf-8")


def test_daidala_project_manifest_is_strict_canonical_and_pins_pack_resources() -> None:
    manifest = parse_project_manifest(manifest_content())

    assert manifest.project_id == "forgegod-daidala"
    assert manifest.repository.canonical == "forgegod/daidala"
    assert manifest.default_pack == "addyosmani"
    assert ProjectManifest.from_dict(manifest.to_dict()) == manifest
    assert len(manifest.digest) == 64
    assert {
        pack.name: (pack.source_revision, pack.content_digest)
        for pack in manifest.allowed_packs
    } == {
        name: (load_pack(name).source_revision, pack_content_digest(name))
        for name in ("addyosmani", "aidlc")
    }
    with pytest.raises(FrozenInstanceError):
        manifest.project_id = "changed"  # type: ignore[misc]


def test_mapping_order_and_yaml_style_do_not_change_manifest_identity() -> None:
    first = parse_project_manifest(manifest_content())
    raw = yaml.safe_load(manifest_content())
    second = parse_project_manifest(yaml.safe_dump(raw, sort_keys=True))

    assert second == first
    assert second.digest == first.digest


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (
            manifest_content() + "project_id: duplicate\n",
            "duplicate key",
        ),
        (
            manifest_content().replace(
                "allowed_remote_urls:\n    - git@github.com:forgegod/daidala.git",
                "allowed_remote_urls: &urls\n    - git@github.com:forgegod/daidala.git",
            ),
            "anchors",
        ),
        (manifest_content() + "unknown: true\n", "unknown"),
        (
            manifest_content().replace(".daidala/constraints.yaml", "../constraints.yaml"),
            "cannot escape",
        ),
        (
            manifest_content().replace(
                "content_digest: 991faf8e26d1c472230dcbf2c29baae9925ad9b9e0cd954f1d90b374302b7832",
                "content_digest: BAD",
            ),
            "SHA-256",
        ),
    ],
)
def test_project_manifest_malformed_inputs_fail_closed(content: str, message: str) -> None:
    with pytest.raises(PolicyViolationError, match=message):
        parse_project_manifest(content)


def test_project_manifest_rejects_duplicate_pack_identity_and_unallowed_default() -> None:
    raw = yaml.safe_load(manifest_content())
    raw["workflow"]["allowed_packs"].append(raw["workflow"]["allowed_packs"][0])
    with pytest.raises(PolicyViolationError, match="duplicate identities"):
        ProjectManifest.from_dict(raw)

    raw = yaml.safe_load(manifest_content())
    raw["workflow"]["default_pack"] = "unknown"
    with pytest.raises(PolicyViolationError, match="default pack"):
        ProjectManifest.from_dict(raw)
