from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from daidala.archive_io import inventory_archive
from daidala.checkout_root import CheckoutConfig, CheckoutRootStore, write_owner_marker
from daidala.checkouts import CheckoutError, CheckoutManager, RefreshReceipt, RefreshStateStore
from daidala.registrations import ControllerRegistration, RegistrationLimits


def registration(root: Path) -> ControllerRegistration:
    return ControllerRegistration(
        project_id="project-one",
        checkout=str(root / "project-one"),
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


HEAD = "a" * 40


class FakeGit:
    def __init__(self, *, ignored_existing: bool = False, tracked_existing: bool = False) -> None:
        self.ignored_existing = ignored_existing
        self.tracked_existing = tracked_existing

    def __call__(self, command: tuple[str, ...], path: Path) -> tuple[int, bytes, bytes]:
        if command[:2] == ("git", "clone"):
            destination = Path(command[-1])
            destination.mkdir()
            (destination / ".git").mkdir()
            (destination / "new.txt").write_text("new\n", encoding="utf-8")
            return 0, b"", b""
        if command[-3:] == ("config", "--get", "remote.origin.url"):
            return 0, b"git@github.com:forgegod/daidala.git\n", b""
        if command[-3:] == ("ls-files", "--error-unmatch", ".daidala-owner"):
            return 1, b"", b""
        if command[-3:] == ("check-ignore", "--quiet", ".daidala-owner"):
            return 1, b"", b""
        if command[-2:] == ("rev-parse", "HEAD"):
            return 0, f"{HEAD}\n".encode(), b""
        if "status" in command:
            records: list[bytes] = []
            if (path / "legacy.txt").exists():
                if self.tracked_existing:
                    records.append(b" M legacy.txt")
                elif self.ignored_existing:
                    records.append(b"!! cache.bin")
            if (path / ".daidala-owner").exists():
                records.append(b"?? .daidala-owner")
            return 0, b"\x00".join(records) + (b"\x00" if records else b""), b""
        raise AssertionError(command)


def configured_manager(
    tmp_path: Path,
    *,
    mode: str = "disabled",
    ttl_hours: int = 0,
    owned: bool = True,
    now: datetime = datetime(2026, 8, 9, 12, tzinfo=UTC),
    git: FakeGit | None = None,
) -> tuple[CheckoutManager, ControllerRegistration, Path, FakeGit]:
    root = tmp_path / "work"
    row = registration(root)
    CheckoutRootStore(tmp_path).write(
        CheckoutConfig(root=root, mode=mode, ttl_hours=ttl_hours), (row,)
    )
    checkout = root / row.project_id
    checkout.mkdir(parents=True)
    (checkout / ".git").mkdir()
    (checkout / "legacy.txt").write_text("legacy\n", encoding="utf-8")
    if owned:
        write_owner_marker(checkout, row.project_id)
    fake_git = git or FakeGit()
    return CheckoutManager(tmp_path, runner=fake_git, now=lambda: now), row, checkout, fake_git


def write_receipt(
    manager: CheckoutManager,
    row: ControllerRegistration,
    checkout: Path,
    refreshed_at: datetime,
) -> None:
    manager.receipts.replace(
        (
            RefreshReceipt(
                project_id=row.project_id,
                checkout=str(checkout),
                registration_digest=row.digest,
                head=HEAD,
                refreshed_at=refreshed_at.isoformat(),
            ),
        )
    )


def test_refresh_state_is_private_strict_and_canonical(tmp_path: Path) -> None:
    store = RefreshStateStore(tmp_path)
    receipt = RefreshReceipt(
        project_id="project-one",
        checkout=str(tmp_path / "work" / "project-one"),
        registration_digest="a" * 64,
        head="b" * 40,
        refreshed_at=datetime(2026, 8, 9, tzinfo=UTC).isoformat(),
    )

    assert store.replace((receipt,)) is True
    assert store.read() == (receipt,)
    assert store.path.stat().st_mode & 0o777 == 0o600
    assert store.replace((receipt,)) is False


def test_checkout_preview_is_path_derived_and_missing_checkout_only_plans_clone(
    tmp_path: Path,
) -> None:
    root = tmp_path / "work"
    row = registration(root)
    CheckoutRootStore(tmp_path).write(CheckoutConfig(root=root), (row,))
    manager = CheckoutManager(tmp_path)

    preview = manager.preview_refresh(row)

    assert preview["action"] == "clone"
    status = preview["status"]
    assert isinstance(status, dict)
    assert status["state"] == "missing_checkout"
    assert isinstance(preview["preview_digest"], str)


def test_policy_rejects_provisional_phase_zero_vocabulary(tmp_path: Path) -> None:
    manager = CheckoutManager(tmp_path)

    with pytest.raises(CheckoutError, match="mode"):
        manager.replace_policy(mode="manual", ttl_hours=0)


def test_policy_apply_requires_a_fresh_literal_confirmation(tmp_path: Path) -> None:
    manager = CheckoutManager(tmp_path)
    preview = manager.preview_policy(mode="wipe-if-clean", ttl_hours=24)

    with pytest.raises(CheckoutError, match="confirmed preview"):
        manager.apply_policy(
            mode="wipe-if-clean",
            ttl_hours=24,
            preview_digest=preview["preview_digest"],
            confirm=False,
        )
    with pytest.raises(CheckoutError, match="stale"):
        manager.apply_policy(
            mode="backup-then-wipe",
            ttl_hours=24,
            preview_digest=preview["preview_digest"],
            confirm=True,
        )

    assert manager.apply_policy(
        mode="wipe-if-clean",
        ttl_hours=24,
        preview_digest=preview["preview_digest"],
        confirm=True,
    ) == {"changed": True, "policy": {"mode": "wipe-if-clean", "ttl_hours": 24}}
    assert CheckoutManager(tmp_path).policy().to_dict() == {
        "mode": "wipe-if-clean",
        "ttl_hours": 24,
    }


def test_owner_marker_is_the_only_ignored_status_record_excluded(tmp_path: Path) -> None:
    root = tmp_path / "work"
    checkout = root / "project-one"
    checkout.mkdir(parents=True)
    write_owner_marker(checkout, "project-one")
    manager = CheckoutManager(
        tmp_path,
        runner=lambda _command, _path: (0, b"?? .daidala-owner\x00", b""),
    )

    assert manager._status_counts(checkout, "project-one") == (0, 0, 0)


def test_backup_pruning_requires_named_fresh_confirmation(tmp_path: Path) -> None:
    root = tmp_path / "work"
    backups = root / "_backups"
    backups.mkdir(parents=True)
    filename = "project-one.0000000001.tar.gz"
    (backups / filename).write_bytes(b"archive")
    (backups / "not-a-backup.txt").write_bytes(b"ignored")
    CheckoutRootStore(tmp_path).write(CheckoutConfig(root=root), ())
    manager = CheckoutManager(tmp_path)

    preview = manager.preview_backup_prune([filename])
    with pytest.raises(CheckoutError, match="confirmed preview"):
        manager.apply_backup_prune(
            filenames=[filename], preview_digest=preview["preview_digest"], confirm=False
        )
    assert manager.apply_backup_prune(
        filenames=[filename], preview_digest=preview["preview_digest"], confirm=True
    ) == {"removed": [filename], "remaining": []}
    assert (backups / "not-a-backup.txt").exists()


def test_existing_clean_refresh_replaces_only_after_validated_clone(tmp_path: Path) -> None:
    manager, row, checkout, _git = configured_manager(tmp_path)

    preview = manager.preview_refresh(row)

    assert preview["action"] == "replace"
    result = manager.apply_refresh(
        row, preview_digest=preview["preview_digest"], confirm=True
    )

    assert result["changed"] is True
    assert (checkout / "new.txt").read_text(encoding="utf-8") == "new\n"
    assert not (checkout / "legacy.txt").exists()
    assert manager.receipts.read()[0].head == HEAD
    assert not tuple(checkout.parent.glob(".project-one.clone.*"))
    assert not tuple(checkout.parent.glob(".project-one.replace.*"))


def test_missing_checkout_clone_publishes_only_after_owner_and_receipt_are_durable(
    tmp_path: Path,
) -> None:
    root = tmp_path / "work"
    row = registration(root)
    CheckoutRootStore(tmp_path).write(CheckoutConfig(root=root), (row,))
    manager = CheckoutManager(tmp_path, runner=FakeGit())

    preview = manager.preview_refresh(row)
    result = manager.apply_refresh(row, preview_digest=preview["preview_digest"], confirm=True)

    assert preview["action"] == "clone"
    status = result["status"]
    assert isinstance(status, dict)
    assert status["receipt_healthy"] is True
    assert (root / row.project_id / "new.txt").exists()
    assert not tuple(root.glob(".project-one.clone.*"))


def test_failed_clone_preserves_missing_target_and_leaves_operation_for_recovery(
    tmp_path: Path,
) -> None:
    root = tmp_path / "work"
    row = registration(root)
    CheckoutRootStore(tmp_path).write(CheckoutConfig(root=root), (row,))
    fake_git = FakeGit()

    def fail_clone(command: tuple[str, ...], path: Path) -> tuple[int, bytes, bytes]:
        if command[:2] == ("git", "clone"):
            Path(command[-1]).mkdir()
            return 1, b"", b""
        return fake_git(command, path)

    manager = CheckoutManager(tmp_path, runner=fail_clone)
    preview = manager.preview_refresh(row)

    with pytest.raises(CheckoutError, match="clone failed"):
        manager.apply_refresh(row, preview_digest=preview["preview_digest"], confirm=True)

    assert not (root / row.project_id).exists()
    assert tuple(root.glob(".project-one.clone.*"))


def test_ttl_uses_receipt_age_not_checkout_commit_age(tmp_path: Path) -> None:
    now = datetime(2026, 8, 9, 12, tzinfo=UTC)
    manager, row, checkout, _git = configured_manager(
        tmp_path, mode="wipe-if-clean", ttl_hours=24, now=now
    )
    write_receipt(manager, row, checkout, now - timedelta(hours=1))

    assert manager.preview_refresh(row)["action"] == "noop"

    write_receipt(manager, row, checkout, now - timedelta(hours=25))
    assert manager.preview_refresh(row)["action"] == "replace"


def test_backup_then_wipe_archives_ignored_files_before_replacement(tmp_path: Path) -> None:
    now = datetime(2026, 8, 9, 12, tzinfo=UTC)
    manager, row, checkout, _git = configured_manager(
        tmp_path,
        mode="backup-then-wipe",
        ttl_hours=24,
        now=now,
        git=FakeGit(ignored_existing=True),
    )
    write_receipt(manager, row, checkout, now - timedelta(hours=25))

    preview = manager.preview_refresh(row)
    assert preview["action"] == "replace"
    manager.apply_refresh(row, preview_digest=preview["preview_digest"], confirm=True)

    name = f"project-one.{int(now.timestamp()):010d}.tar.gz"
    backups = checkout.parent / "_backups"
    manifest = backups / f"{name}.manifest.json"
    inventory = inventory_archive(backups / name, manifest)
    assert [member.path for member in inventory.members] == ["legacy.txt"]
    assert (checkout / "new.txt").exists()


def test_archive_failure_preserves_original_checkout_and_no_partial_archive(tmp_path: Path) -> None:
    now = datetime(2026, 8, 9, 12, tzinfo=UTC)
    manager, row, checkout, _git = configured_manager(
        tmp_path,
        mode="backup-then-wipe",
        ttl_hours=24,
        now=now,
        git=FakeGit(ignored_existing=True),
    )
    (checkout / "unsafe-link").symlink_to("legacy.txt")
    write_receipt(manager, row, checkout, now - timedelta(hours=25))
    preview = manager.preview_refresh(row)

    with pytest.raises(CheckoutError, match="unsafe"):
        manager.apply_refresh(row, preview_digest=preview["preview_digest"], confirm=True)

    assert (checkout / "legacy.txt").exists()
    assert not tuple((checkout.parent / "_backups").glob("*.tar.gz"))
    assert manager.status(row).recovery_required is True


def test_swap_failure_rolls_back_original_and_reports_surviving_operation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager, row, checkout, _git = configured_manager(tmp_path)
    preview = manager.preview_refresh(row)
    original_move = manager._move

    def fail_clone_swap(source: Path, destination: Path) -> None:
        if source.name.startswith(".project-one.clone.") and destination == checkout:
            raise OSError("simulated swap failure")
        original_move(source, destination)

    monkeypatch.setattr(manager, "_move", fail_clone_swap)

    with pytest.raises(CheckoutError, match="original checkout restored"):
        manager.apply_refresh(row, preview_digest=preview["preview_digest"], confirm=True)

    assert (checkout / "legacy.txt").exists()
    assert manager.status(row).recovery_required is True


def test_receipt_failure_rolls_back_existing_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager, row, checkout, _git = configured_manager(tmp_path)
    preview = manager.preview_refresh(row)

    def fail_receipt(*_args: object) -> None:
        raise CheckoutError("simulated receipt failure")

    monkeypatch.setattr(manager, "_write_receipt", fail_receipt)

    with pytest.raises(CheckoutError, match="original checkout restored"):
        manager.apply_refresh(row, preview_digest=preview["preview_digest"], confirm=True)

    assert (checkout / "legacy.txt").exists()
    assert manager.status(row).recovery_required is True


def test_clean_unowned_checkout_requires_confirmation_then_writes_witness_and_receipt(
    tmp_path: Path,
) -> None:
    manager, row, checkout, _git = configured_manager(tmp_path, owned=False)

    preview = manager.preview_adopt(row)
    assert preview["action"] == "adopt"
    with pytest.raises(CheckoutError, match="confirmed preview"):
        manager.apply_adopt(row, preview_digest=preview["preview_digest"], confirm=False)

    result = manager.apply_adopt(row, preview_digest=preview["preview_digest"], confirm=True)

    assert result["changed"] is True
    assert (checkout / ".daidala-owner").exists()
    assert manager.status(row).receipt_healthy is True


def test_adoption_rejects_dirty_checkout_without_writing_owner_marker(tmp_path: Path) -> None:
    manager, row, checkout, _git = configured_manager(
        tmp_path, owned=False, git=FakeGit(tracked_existing=True)
    )

    with pytest.raises(CheckoutError, match="clean"):
        manager.preview_adopt(row)

    assert not (checkout / ".daidala-owner").exists()


def test_adoption_receipt_failure_removes_new_owner_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager, row, checkout, _git = configured_manager(tmp_path, owned=False)
    preview = manager.preview_adopt(row)

    def fail_receipt(*_args: object) -> None:
        raise CheckoutError("simulated receipt failure")

    monkeypatch.setattr(manager, "_write_receipt", fail_receipt)

    with pytest.raises(CheckoutError, match="receipt failed"):
        manager.apply_adopt(row, preview_digest=preview["preview_digest"], confirm=True)

    assert not (checkout / ".daidala-owner").exists()


def test_status_parser_counts_rename_once_and_rejects_malformed_output(tmp_path: Path) -> None:
    root = tmp_path / "work"
    checkout = root / "project-one"
    checkout.mkdir(parents=True)
    write_owner_marker(checkout, "project-one")
    manager = CheckoutManager(
        tmp_path,
        runner=lambda _command, _path: (
            0,
            b"R  new-name\x00old-name\x00?? .daidala-owner\x00",
            b"",
        ),
    )

    assert manager._status_counts(checkout, "project-one") == (1, 0, 0)

    manager.runner = lambda _command, _path: (0, b" M missing-nul", b"")
    with pytest.raises(CheckoutError, match="malformed"):
        manager._status_counts(checkout, "project-one")
