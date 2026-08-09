from __future__ import annotations

from pathlib import Path

import pytest

from daidala.checkout_root import (
    OWNER_FILENAME,
    CheckoutConfig,
    CheckoutRootError,
    CheckoutRootStore,
    owner_marker_content,
    parse_checkout_config,
    write_owner_marker,
)
from daidala.registrations import ControllerRegistration, RegistrationLimits


def registration(root: Path, *, project_id: str = "project-one") -> ControllerRegistration:
    return ControllerRegistration(
        project_id=project_id,
        checkout=str(root / project_id),
        controller_profile="controller",
        board="board",
        repository_canonical="forgegod/daidala",
        verified_remote="git@github.com:forgegod/daidala.git",
        intake_credential="github-read",
        findings_credential="github-write",
        maintainers=("forgegod",),
        notification_adapter="hermes-gateway",
        notification_target="attended",
        notification_destination="telegram:target",
        evaluator_backend="restricted-container",
        evaluator_network="denied-by-default",
        limits=RegistrationLimits(1, 1, 0, 0, 0, 60),
    )


def test_checkout_root_defaults_and_private_round_trip(tmp_path: Path) -> None:
    store = CheckoutRootStore(tmp_path)
    config = CheckoutConfig(root=tmp_path / "root")

    assert store.read() == CheckoutConfig(root=tmp_path / "work")
    assert store.write(config, (registration(config.root),)) is True
    assert store.read() == config
    assert store.path.stat().st_mode & 0o777 == 0o600
    assert store.write(config, (registration(config.root),)) is False


def test_checkout_root_rejects_unknown_document_fields_and_registration_mismatch(
    tmp_path: Path,
) -> None:
    with pytest.raises(CheckoutRootError, match="fields"):
        parse_checkout_config(
            "schema: daidala.checkouts/v1\ncheckouts:\n"
            f"  root: {tmp_path / 'root'}\n  mode: disabled\n  ttl_hours: 0\n  extra: no\n"
        )

    store = CheckoutRootStore(tmp_path)
    with pytest.raises(CheckoutRootError, match="does not match registrations"):
        store.write(CheckoutConfig(root=tmp_path / "root"), (registration(tmp_path / "other"),))
    assert not store.path.exists()


def test_checkout_root_rejects_symlink_components(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(target, target_is_directory=True)

    with pytest.raises(CheckoutRootError, match="symlink"):
        CheckoutConfig(root=alias / "work")


def test_checkout_root_uses_the_exact_phase_two_ttl_modes(tmp_path: Path) -> None:
    root = tmp_path / "root"

    assert CheckoutConfig(root=root) == CheckoutConfig(
        root=root, mode="disabled", ttl_hours=0
    )
    assert CheckoutConfig(root=root, mode="wipe-if-clean", ttl_hours=1).mode == "wipe-if-clean"
    assert (
        CheckoutConfig(root=root, mode="backup-then-wipe", ttl_hours=8760).mode
        == "backup-then-wipe"
    )
    with pytest.raises(CheckoutRootError, match="mode"):
        CheckoutConfig(root=root, mode="manual", ttl_hours=0)
    with pytest.raises(CheckoutRootError, match="requires ttl_hours 0"):
        CheckoutConfig(root=root, mode="disabled", ttl_hours=1)
    with pytest.raises(CheckoutRootError, match="TTL checkout modes"):
        CheckoutConfig(root=root, mode="wipe-if-clean", ttl_hours=0)


def test_checkout_owner_witness_is_strict_json_and_private(tmp_path: Path) -> None:
    root = tmp_path / "root"
    checkout = root / "project-one"
    checkout.mkdir(parents=True)

    write_owner_marker(checkout, "project-one")

    marker = checkout / OWNER_FILENAME
    assert marker.read_text(encoding="utf-8") == owner_marker_content("project-one")
    assert marker.stat().st_mode & 0o777 == 0o600
    assert owner_marker_content("project-one") != "project-one\n"
