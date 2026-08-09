"""Bounded checkout inventory, policy, and refresh-preview primitives.

This module owns operational checkout state.  It consumes the strict root document
from :mod:`daidala.checkout_root` and never accepts a browser-supplied path or
remote URL.
"""
from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import cast

from .archive_io import ArchiveError, create_archive, verify_archive
from .checkout_root import (
    OWNER_FILENAME,
    CheckoutConfig,
    CheckoutRootError,
    CheckoutRootStore,
    checkout_path,
    owner_marker_content,
    validate_reusable_checkout,
    write_owner_marker,
)
from .errors import PolicyViolationError
from .profile_files import ProfileFileError, atomic_write_private_text, read_private_text
from .projects import _require_slug
from .registrations import ControllerRegistration

REFRESH_STATE_SCHEMA = "daidala.checkout-refresh-state/v1"
REFRESH_STATE_FILENAME = "checkout-refresh-state.json"
MAX_REFRESH_STATE_BYTES = 512 * 1024
MAX_REFRESH_ROWS = 1024
MAX_STATUS_OUTPUT_BYTES = 1024 * 1024
GIT_STATUS_TIMEOUT_SECONDS = 30
MAX_BACKUPS = 1024
BACKUP_FILENAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}\.[0-9]{10}\.tar\.gz$")
BACKUP_MANIFEST_SUFFIX = ".manifest.json"


class CheckoutError(PolicyViolationError):
    """Raised for blocked checkout inventory, policy, or lifecycle actions."""


@dataclass(frozen=True)
class TtlPolicy:
    mode: str
    ttl_hours: int

    def __post_init__(self) -> None:
        CheckoutConfig(root=Path("/tmp"), mode=self.mode, ttl_hours=self.ttl_hours)

    @classmethod
    def from_config(cls, config: CheckoutConfig) -> TtlPolicy:
        return cls(mode=config.mode, ttl_hours=config.ttl_hours)

    def to_dict(self) -> dict[str, object]:
        return {"mode": self.mode, "ttl_hours": self.ttl_hours}


@dataclass(frozen=True)
class RefreshReceipt:
    project_id: str
    checkout: str
    registration_digest: str
    head: str
    refreshed_at: str

    def __post_init__(self) -> None:
        _require_slug(self.project_id, "checkout receipt project ID")
        if not isinstance(self.checkout, str) or not Path(self.checkout).is_absolute():
            raise CheckoutError("checkout receipt path is invalid")
        if not isinstance(self.registration_digest, str) or len(self.registration_digest) != 64:
            raise CheckoutError("checkout receipt registration digest is invalid")
        if not isinstance(self.head, str) or len(self.head) != 40:
            raise CheckoutError("checkout receipt HEAD is invalid")
        try:
            parsed = datetime.fromisoformat(self.refreshed_at.replace("Z", "+00:00"))
        except (TypeError, ValueError) as error:
            raise CheckoutError("checkout receipt timestamp is invalid") from error
        if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
            raise CheckoutError("checkout receipt timestamp must be UTC")

    def to_dict(self) -> dict[str, str]:
        return {
            "project_id": self.project_id,
            "checkout": self.checkout,
            "registration_digest": self.registration_digest,
            "head": self.head,
            "refreshed_at": self.refreshed_at,
        }

    @classmethod
    def from_dict(cls, raw: object) -> RefreshReceipt:
        if not isinstance(raw, dict) or set(raw) != {
            "project_id", "checkout", "registration_digest", "head", "refreshed_at"
        }:
            raise CheckoutError("checkout receipt fields are invalid")
        return cls(**raw)


class RefreshStateStore:
    """Strict private receipt store updated only after successful lifecycle work."""

    def __init__(self, data_root: Path) -> None:
        if (
            not isinstance(data_root, Path)
            or not data_root.is_absolute()
            or data_root.resolve() != data_root
        ):
            raise CheckoutError("checkout state root must be absolute and resolved")
        self.path = data_root / REFRESH_STATE_FILENAME

    def read(self) -> tuple[RefreshReceipt, ...]:
        try:
            content = read_private_text(
                self.path, maximum_bytes=MAX_REFRESH_STATE_BYTES, label="checkout refresh state"
            )
        except FileNotFoundError:
            return ()
        except ProfileFileError as error:
            raise CheckoutError(str(error)) from error
        try:
            raw = json.loads(content)
        except json.JSONDecodeError as error:
            raise CheckoutError("checkout refresh state is invalid") from error
        if (
            not isinstance(raw, dict)
            or set(raw) != {"schema", "rows"}
            or raw["schema"] != REFRESH_STATE_SCHEMA
        ):
            raise CheckoutError("checkout refresh state schema is invalid")
        if not isinstance(raw["rows"], list) or len(raw["rows"]) > MAX_REFRESH_ROWS:
            raise CheckoutError("checkout refresh state rows are invalid")
        rows = tuple(RefreshReceipt.from_dict(row) for row in raw["rows"])
        if tuple(sorted(row.project_id for row in rows)) != tuple(row.project_id for row in rows):
            raise CheckoutError("checkout refresh state rows are not canonical")
        if len({row.project_id for row in rows}) != len(rows):
            raise CheckoutError("checkout refresh state rows are duplicated")
        return rows

    def replace(self, rows: tuple[RefreshReceipt, ...]) -> bool:
        project_ids = tuple(row.project_id for row in rows)
        if len(rows) > MAX_REFRESH_ROWS or tuple(sorted(project_ids)) != project_ids:
            raise CheckoutError("checkout refresh state rows are invalid")
        content = json.dumps(
            {"schema": REFRESH_STATE_SCHEMA, "rows": [row.to_dict() for row in rows]},
            separators=(",", ":"),
            sort_keys=True,
        ) + "\n"
        try:
            current = read_private_text(
                self.path, maximum_bytes=MAX_REFRESH_STATE_BYTES, label="checkout refresh state"
            )
        except FileNotFoundError:
            current = None
        except ProfileFileError as error:
            raise CheckoutError(str(error)) from error
        if current == content:
            return False
        try:
            atomic_write_private_text(self.path, content, label="checkout refresh state")
        except ProfileFileError as error:
            raise CheckoutError(str(error)) from error
        return True


@dataclass(frozen=True)
class CheckoutStatus:
    project_id: str
    state: str
    path_exists: bool
    owner_healthy: bool
    origin_healthy: bool
    receipt_healthy: bool
    observed_head: str | None
    tracked_count: int = 0
    untracked_count: int = 0
    ignored_count: int = 0
    receipt_age_hours: float | None = None
    recovery_required: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "project_id": self.project_id,
            "state": self.state,
            "path_exists": self.path_exists,
            "owner_healthy": self.owner_healthy,
            "origin_healthy": self.origin_healthy,
            "receipt_healthy": self.receipt_healthy,
            "observed_head": self.observed_head,
            "tracked_count": self.tracked_count,
            "untracked_count": self.untracked_count,
            "ignored_count": self.ignored_count,
            "receipt_age_hours": self.receipt_age_hours,
            "recovery_required": self.recovery_required,
        }


Runner = Callable[[tuple[str, ...], Path], tuple[int, bytes, bytes]]


class CheckoutManager:
    """Read checkout state and construct confirmation-bound refresh previews."""

    def __init__(
        self,
        data_root: Path,
        *,
        runner: Runner | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.data_root = data_root.resolve()
        self.root_store = CheckoutRootStore(self.data_root)
        self.receipts = RefreshStateStore(self.data_root)
        self.runner = runner or _run_git
        self.now = now or (lambda: datetime.now(UTC))

    def policy(self) -> TtlPolicy:
        return TtlPolicy.from_config(self._config())

    def backups(self) -> tuple[str, ...]:
        """List only regular, canonical backup files below the configured root."""

        directory = self._backup_directory(create=False)
        if directory is None:
            return ()
        try:
            entries = tuple(directory.iterdir())
        except OSError as error:
            raise CheckoutError("checkout backup directory is unreadable") from error
        if len(entries) > MAX_BACKUPS:
            raise CheckoutError("checkout backup inventory exceeds its limit")
        backups: list[str] = []
        for entry in entries:
            try:
                entry_stat = entry.lstat()
            except OSError as error:
                raise CheckoutError("checkout backup metadata is unreadable") from error
            if stat.S_ISLNK(entry_stat.st_mode) or not stat.S_ISREG(entry_stat.st_mode):
                raise CheckoutError("checkout backup entry is invalid")
            if not BACKUP_FILENAME.fullmatch(entry.name):
                continue
            if entry.resolve(strict=True).parent != directory.resolve(strict=True):
                raise CheckoutError("checkout backup entry is invalid")
            backups.append(entry.name)
        return tuple(sorted(backups))

    def preview_backup_prune(self, filenames: object) -> dict[str, object]:
        if not isinstance(filenames, list) or not all(isinstance(name, str) for name in filenames):
            raise CheckoutError("checkout backup names are invalid")
        names = cast(list[str], filenames)
        requested = tuple(sorted(set(names)))
        available = self.backups()
        if any(name not in available for name in requested):
            raise CheckoutError("checkout backup selection is stale or invalid")
        payload = {"backups": requested, "available": available}
        return {**payload, "preview_digest": _digest(payload)}

    def apply_backup_prune(
        self, *, filenames: object, preview_digest: object, confirm: object
    ) -> dict[str, object]:
        if confirm is not True or not isinstance(preview_digest, str):
            raise CheckoutError("checkout backup prune requires confirmed preview")
        preview = self.preview_backup_prune(filenames)
        if preview["preview_digest"] != preview_digest:
            raise CheckoutError("checkout backup prune preview is stale")
        directory = self._backup_directory(create=False)
        if directory is None:
            raise CheckoutError("checkout backup selection is stale or invalid")
        selected = tuple(str(name) for name in preview["backups"])
        for name in selected:
            self._validated_backup_path(directory, name)
            self._validated_backup_manifest(directory, name)
        try:
            for name in selected:
                self._validated_backup_path(directory, name).unlink()
                manifest = self._backup_manifest_path(directory, name)
                if manifest.exists():
                    manifest.unlink()
        except OSError as error:
            raise CheckoutError("checkout backup pruning failed") from error
        return {"removed": list(preview["backups"]), "remaining": list(self.backups())}

    def status(
        self, registration: ControllerRegistration, *, ignore_operation: Path | None = None
    ) -> CheckoutStatus:
        config = self._config()
        path = checkout_path(config.root, registration.project_id)
        recovery_required = self._operation_recovery_required(
            config.root, registration.project_id, ignore_operation=ignore_operation
        )
        if path != Path(registration.checkout):
            return CheckoutStatus(
                registration.project_id,
                "wrong_owner",
                False,
                False,
                False,
                False,
                None,
                recovery_required=recovery_required,
            )
        if path.is_symlink():
            return CheckoutStatus(
                registration.project_id,
                "symlink_path",
                True,
                False,
                False,
                False,
                None,
                recovery_required=recovery_required,
            )
        if not path.exists():
            return CheckoutStatus(
                registration.project_id,
                "missing_checkout",
                False,
                False,
                False,
                False,
                None,
                recovery_required=recovery_required,
            )
        try:
            validate_reusable_checkout(path, registration, self._compat_runner)
            self._validate_marker_git_state(path)
        except CheckoutRootError as error:
            state = "wrong_origin" if "origin" in str(error) else "unowned"
            return CheckoutStatus(
                registration.project_id,
                state,
                True,
                False,
                state != "wrong_origin",
                False,
                None,
                recovery_required=recovery_required,
            )
        head = self._git_text(("git", "-C", str(path), "rev-parse", "HEAD"), path)
        if head is None:
            raise CheckoutError("checkout HEAD is unavailable")
        receipt = next(
            (row for row in self.receipts.read() if row.project_id == registration.project_id), None
        )
        receipt_age = self._receipt_age_hours(receipt)
        receipt_healthy = bool(
            receipt
            and receipt.checkout == str(path)
            and receipt.registration_digest == registration.digest
            and receipt.head == head
            and receipt_age is not None
        )
        tracked, untracked, ignored = self._status_counts(path, registration.project_id)
        state = "git_dirty" if tracked or untracked or ignored else "ok"
        return CheckoutStatus(
            registration.project_id,
            state,
            True,
            True,
            True,
            receipt_healthy,
            head,
            tracked,
            untracked,
            ignored,
            receipt_age if receipt_healthy else None,
            recovery_required,
        )

    def statuses(
        self, registrations: tuple[ControllerRegistration, ...]
    ) -> tuple[CheckoutStatus, ...]:
        return tuple(self.status(registration) for registration in registrations)

    def preview_refresh(self, registration: ControllerRegistration) -> dict[str, object]:
        return self._preview_refresh(registration)

    def _preview_refresh(
        self, registration: ControllerRegistration, *, ignore_operation: Path | None = None
    ) -> dict[str, object]:
        status = self.status(registration, ignore_operation=ignore_operation)
        policy = self.policy()
        if status.recovery_required:
            raise CheckoutError("checkout requires manual recovery")
        if status.state == "missing_checkout":
            action = "clone"
        elif status.state not in {"ok", "git_dirty"}:
            raise CheckoutError("checkout refresh is blocked by current checkout status")
        elif status.tracked_count or status.untracked_count:
            raise CheckoutError("checkout refresh is blocked by tracked or untracked changes")
        elif status.ignored_count and policy.mode != "backup-then-wipe":
            raise CheckoutError("ignored checkout files require backup-then-wipe")
        elif policy.mode == "disabled":
            action = "replace"
        elif not status.receipt_healthy or status.receipt_age_hours is None:
            action = "replace"
        elif status.receipt_age_hours <= policy.ttl_hours:
            action = "noop"
        else:
            action = "replace"
        payload = {
            "project_id": registration.project_id,
            "policy": policy.to_dict(),
            "status": status.to_dict(),
            "action": action,
        }
        return {**payload, "preview_digest": _digest(payload)}

    def apply_refresh(
        self,
        registration: ControllerRegistration,
        *,
        preview_digest: object,
        confirm: object,
    ) -> dict[str, object]:
        if confirm is not True or not isinstance(preview_digest, str):
            raise CheckoutError("checkout refresh requires confirmed preview")
        preview = self.preview_refresh(registration)
        if preview["preview_digest"] != preview_digest:
            raise CheckoutError("checkout refresh preview is stale")
        if preview["action"] == "noop":
            return {
                "changed": False,
                "project_id": registration.project_id,
                "status": self.status(registration).to_dict(),
            }
        config = self._config()
        root = self._ensure_checkout_root(config.root, create=True)
        path = checkout_path(root, registration.project_id)
        try:
            if self._operation_recovery_required(root, registration.project_id):
                raise CheckoutError("checkout requires manual recovery")
            temporary = self._operation_path(root, registration.project_id, "clone")
            if preview["action"] == "clone" and (path.exists() or path.is_symlink()):
                raise CheckoutError("checkout appeared after preview")
            head = self._clone_to_temporary(registration, temporary)
            if preview["action"] == "clone":
                if path.exists() or path.is_symlink():
                    raise CheckoutError("checkout appeared during clone")
                self._publish_new_checkout(registration, temporary, path, head)
            else:
                refreshed = self._preview_refresh(registration, ignore_operation=temporary)
                if (
                    refreshed["action"] != "replace"
                    or refreshed["policy"] != preview["policy"]
                ):
                    raise CheckoutError("checkout refresh changed during clone")
                if config.mode == "backup-then-wipe":
                    self._backup_checkout(path, registration)
                self._replace_checkout(registration, temporary, path, head)
        except CheckoutRootError as error:
            raise CheckoutError(str(error)) from error
        except OSError as error:
            raise CheckoutError("checkout lifecycle I/O failed") from error
        return {
            "changed": True,
            "project_id": registration.project_id,
            "status": self.status(registration).to_dict(),
        }

    def _write_receipt(self, registration: ControllerRegistration, path: Path, head: str) -> None:
        receipt = RefreshReceipt(
            project_id=registration.project_id,
            checkout=str(path),
            registration_digest=registration.digest,
            head=head,
            refreshed_at=self.now().astimezone(UTC).isoformat().replace("+00:00", "Z"),
        )
        rows = tuple(row for row in self.receipts.read() if row.project_id != receipt.project_id)
        self.receipts.replace(tuple(sorted((*rows, receipt), key=lambda row: row.project_id)))

    def preview_adopt(self, registration: ControllerRegistration) -> dict[str, object]:
        config = self._config()
        path = checkout_path(config.root, registration.project_id)
        if path != Path(registration.checkout):
            raise CheckoutError("checkout adoption is blocked by the registration path")
        if self._operation_recovery_required(config.root, registration.project_id):
            raise CheckoutError("checkout requires manual recovery")
        self._validate_adoptable_checkout(path, registration)
        payload = {
            "project_id": registration.project_id,
            "action": "adopt",
            "status": self.status(registration).to_dict(),
        }
        return {**payload, "preview_digest": _digest(payload)}

    def apply_adopt(
        self,
        registration: ControllerRegistration,
        *,
        preview_digest: object,
        confirm: object,
    ) -> dict[str, object]:
        if confirm is not True or not isinstance(preview_digest, str):
            raise CheckoutError("checkout adoption requires confirmed preview")
        preview = self.preview_adopt(registration)
        if preview["preview_digest"] != preview_digest:
            raise CheckoutError("checkout adoption preview is stale")
        path = checkout_path(self._config().root, registration.project_id)
        self._validate_adoptable_checkout(path, registration)
        head = self._git_text(("git", "-C", str(path), "rev-parse", "HEAD"), path)
        if head is None:
            raise CheckoutError("checkout HEAD is unavailable")
        try:
            write_owner_marker(path, registration.project_id)
        except CheckoutRootError as error:
            raise CheckoutError("checkout adoption owner witness failed") from error
        try:
            self._write_receipt(registration, path, head)
        except CheckoutError as error:
            self._remove_owner_marker_after_failed_adoption(path, registration.project_id)
            raise CheckoutError("checkout adoption receipt failed") from error
        return {
            "changed": True,
            "project_id": registration.project_id,
            "status": self.status(registration).to_dict(),
        }

    def _config(self) -> CheckoutConfig:
        try:
            return self.root_store.read()
        except CheckoutRootError as error:
            raise CheckoutError(str(error)) from error

    def _ensure_checkout_root(self, root: Path, *, create: bool) -> Path:
        try:
            if create:
                root.mkdir(mode=0o700, parents=True, exist_ok=True)
            if not root.exists():
                return root
            for candidate in (*root.parents, root):
                if candidate.exists() or candidate.is_symlink():
                    if stat.S_ISLNK(candidate.lstat().st_mode):
                        raise CheckoutError("checkout root cannot traverse a symlink")
            metadata = root.lstat()
            if not stat.S_ISDIR(metadata.st_mode) or root.resolve(strict=True) != root:
                raise CheckoutError("checkout root is invalid")
            return root
        except CheckoutError:
            raise
        except OSError as error:
            raise CheckoutError("checkout root is unavailable") from error

    def _backup_directory(self, *, create: bool) -> Path | None:
        root = self._ensure_checkout_root(self._config().root, create=create)
        if not root.exists():
            return None
        directory = root / "_backups"
        try:
            if create:
                directory.mkdir(mode=0o700, exist_ok=True)
                os.chmod(directory, 0o700)
            if not directory.exists():
                return None
            metadata = directory.lstat()
            if (
                stat.S_ISLNK(metadata.st_mode)
                or not stat.S_ISDIR(metadata.st_mode)
                or directory.resolve(strict=True).parent != root.resolve(strict=True)
            ):
                raise CheckoutError("checkout backup directory is invalid")
            return directory
        except CheckoutError:
            raise
        except OSError as error:
            raise CheckoutError("checkout backup directory is unavailable") from error

    @staticmethod
    def _backup_manifest_path(directory: Path, name: str) -> Path:
        return directory / f"{name}{BACKUP_MANIFEST_SUFFIX}"

    def _validated_backup_path(self, directory: Path, name: str) -> Path:
        if not BACKUP_FILENAME.fullmatch(name):
            raise CheckoutError("checkout backup selection is invalid")
        path = directory / name
        try:
            metadata = path.lstat()
            if (
                stat.S_ISLNK(metadata.st_mode)
                or not stat.S_ISREG(metadata.st_mode)
                or path.resolve(strict=True).parent != directory.resolve(strict=True)
            ):
                raise CheckoutError("checkout backup selection is invalid")
            return path
        except CheckoutError:
            raise
        except OSError as error:
            raise CheckoutError("checkout backup selection is invalid") from error

    def _validated_backup_manifest(self, directory: Path, name: str) -> Path | None:
        path = self._backup_manifest_path(directory, name)
        if not path.exists() and not path.is_symlink():
            return None
        try:
            metadata = path.lstat()
            if (
                stat.S_ISLNK(metadata.st_mode)
                or not stat.S_ISREG(metadata.st_mode)
                or path.resolve(strict=True).parent != directory.resolve(strict=True)
            ):
                raise CheckoutError("checkout backup selection is invalid")
            return path
        except CheckoutError:
            raise
        except OSError as error:
            raise CheckoutError("checkout backup selection is invalid") from error

    def _operation_recovery_required(
        self, root: Path, project_id: str, *, ignore_operation: Path | None = None
    ) -> bool:
        root = self._ensure_checkout_root(root, create=False)
        if not root.exists():
            return False
        pattern = re.compile(
            rf"^\.{re.escape(project_id)}\.(?:clone|replace)\.[0-9]{{10}}\.[0-9]+$"
        )
        try:
            with os.scandir(root) as entries:
                for index, entry in enumerate(entries, start=1):
                    if index > MAX_BACKUPS:
                        raise CheckoutError("checkout root inventory exceeds its limit")
                    if ignore_operation is not None and Path(entry.path) == ignore_operation:
                        continue
                    if pattern.fullmatch(entry.name):
                        return True
        except CheckoutError:
            raise
        except OSError as error:
            raise CheckoutError("checkout root inventory is unavailable") from error
        return False

    def _operation_path(self, root: Path, project_id: str, kind: str) -> Path:
        if kind not in {"clone", "replace"}:
            raise CheckoutError("checkout operation kind is invalid")
        timestamp = int(self.now().astimezone(UTC).timestamp())
        if not 0 <= timestamp <= 9_999_999_999:
            raise CheckoutError("checkout operation time is invalid")
        path = root / f".{project_id}.{kind}.{timestamp:010d}.{os.getpid()}"
        if path.exists() or path.is_symlink():
            raise CheckoutError("checkout operation directory already exists")
        return path

    def _clone_to_temporary(self, registration: ControllerRegistration, temporary: Path) -> str:
        code, _stdout, _stderr = self.runner(
            ("git", "clone", registration.verified_remote, str(temporary)), temporary
        )
        if code != 0:
            raise CheckoutError("checkout clone failed")
        try:
            atomic_write_private_text(
                temporary / OWNER_FILENAME,
                owner_marker_content(registration.project_id),
                label="checkout owner marker",
            )
        except ProfileFileError as error:
            raise CheckoutError(str(error)) from error
        self._validate_clone(temporary, registration)
        head = self._git_text(("git", "-C", str(temporary), "rev-parse", "HEAD"), temporary)
        if head is None:
            raise CheckoutError("checkout clone has no verified HEAD")
        return head

    def _validate_clone(self, path: Path, registration: ControllerRegistration) -> None:
        try:
            metadata = path.lstat()
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
                raise CheckoutError("checkout clone shape is invalid")
        except CheckoutError:
            raise
        except OSError as error:
            raise CheckoutError("checkout clone shape is invalid") from error
        self._validate_origin(path, registration)
        self._validate_marker_git_state(path)
        if self._status_counts(path, registration.project_id) != (0, 0, 0):
            raise CheckoutError("checkout clone is not clean")

    def _validate_origin(self, path: Path, registration: ControllerRegistration) -> None:
        code, stdout, _stderr = self.runner(
            ("git", "-C", str(path), "config", "--get", "remote.origin.url"), path
        )
        expected = registration.verified_remote.encode("utf-8")
        if code != 0 or stdout not in {expected, expected + b"\n"}:
            raise CheckoutError("checkout origin does not match trusted registration")

    def _validate_marker_git_state(self, path: Path) -> None:
        for command in (
            ("git", "-C", str(path), "ls-files", "--error-unmatch", OWNER_FILENAME),
            ("git", "-C", str(path), "check-ignore", "--quiet", OWNER_FILENAME),
        ):
            code, _stdout, _stderr = self.runner(command, path)
            if code == 0:
                raise CheckoutError("checkout owner marker is tracked or ignored")
            if code != 1:
                raise CheckoutError("checkout owner marker state is unavailable")

    def _validate_adoptable_checkout(
        self, path: Path, registration: ControllerRegistration
    ) -> None:
        self._ensure_checkout_root(path.parent, create=False)
        if path != Path(registration.checkout):
            raise CheckoutError("checkout adoption is blocked by the registration path")
        try:
            metadata = path.lstat()
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
                raise CheckoutError("checkout adoption requires a real checkout")
            (path / OWNER_FILENAME).lstat()
        except FileNotFoundError:
            pass
        except CheckoutError:
            raise
        except OSError as error:
            raise CheckoutError("checkout adoption cannot inspect the owner marker") from error
        else:
            raise CheckoutError("checkout adoption requires an unowned checkout")
        self._validate_origin(path, registration)
        self._validate_marker_git_state(path)
        if self._status_counts(path, registration.project_id, require_marker=False) != (0, 0, 0):
            raise CheckoutError("checkout adoption requires a clean checkout")

    def _remove_owner_marker_after_failed_adoption(self, path: Path, project_id: str) -> None:
        marker = path / OWNER_FILENAME
        try:
            if (
                read_private_text(marker, maximum_bytes=256, label="checkout owner marker")
                == owner_marker_content(project_id)
            ):
                marker.unlink()
        except (FileNotFoundError, ProfileFileError, OSError):
            return

    def _publish_new_checkout(
        self, registration: ControllerRegistration, temporary: Path, path: Path, head: str
    ) -> None:
        self._move(temporary, path)
        try:
            self._write_receipt(registration, path, head)
        except CheckoutError as error:
            try:
                self._move(path, temporary)
            except (CheckoutError, OSError) as rollback_error:
                raise CheckoutError(
                    "checkout clone receipt failed; manual recovery required"
                ) from rollback_error
            raise CheckoutError("checkout clone receipt failed") from error

    def _replace_checkout(
        self, registration: ControllerRegistration, temporary: Path, path: Path, head: str
    ) -> None:
        old = self._operation_path(path.parent, registration.project_id, "replace")
        self._move(path, old)
        try:
            self._move(temporary, path)
        except (CheckoutError, OSError) as error:
            try:
                self._move(old, path)
            except (CheckoutError, OSError) as rollback_error:
                raise CheckoutError(
                    "checkout replacement failed; manual recovery required"
                ) from rollback_error
            raise CheckoutError(
                "checkout replacement failed; original checkout restored"
            ) from error
        try:
            self._write_receipt(registration, path, head)
        except CheckoutError as error:
            try:
                self._move(path, temporary)
                self._move(old, path)
            except (CheckoutError, OSError) as rollback_error:
                raise CheckoutError(
                    "checkout replacement receipt failed; manual recovery required"
                ) from rollback_error
            raise CheckoutError(
                "checkout replacement receipt failed; original checkout restored"
            ) from error
        self._remove_operation_directory(old, registration.project_id)

    def _move(self, source: Path, destination: Path) -> None:
        try:
            os.replace(source, destination)
            return
        except OSError as error:
            if error.errno != errno.EXDEV:
                raise
        try:
            shutil.copytree(source, destination, symlinks=True)
            shutil.rmtree(source)
        except OSError as error:
            raise CheckoutError("checkout cross-device replacement failed") from error

    def _remove_operation_directory(self, path: Path, project_id: str) -> None:
        pattern = re.compile(
            rf"^\.{re.escape(project_id)}\.(?:clone|replace)\.[0-9]{{10}}\.[0-9]+$"
        )
        if not pattern.fullmatch(path.name):
            raise CheckoutError("checkout operation directory is invalid")
        try:
            metadata = path.lstat()
            marker = read_private_text(
                path / OWNER_FILENAME, maximum_bytes=256, label="checkout owner marker"
            )
            if (
                stat.S_ISLNK(metadata.st_mode)
                or not stat.S_ISDIR(metadata.st_mode)
                or marker != owner_marker_content(project_id)
            ):
                raise CheckoutError("checkout operation directory is invalid")
            shutil.rmtree(path)
        except CheckoutError:
            raise
        except (OSError, ProfileFileError) as error:
            raise CheckoutError(
                "checkout replacement cleanup failed; manual recovery required"
            ) from error

    def _backup_checkout(self, path: Path, registration: ControllerRegistration) -> None:
        directory = self._backup_directory(create=True)
        if directory is None:
            raise CheckoutError("checkout backup directory is unavailable")
        timestamp = int(self.now().astimezone(UTC).timestamp())
        if not 0 <= timestamp <= 9_999_999_999:
            raise CheckoutError("checkout backup time is invalid")
        name = f"{registration.project_id}.{timestamp:010d}.tar.gz"
        archive = directory / name
        manifest = self._backup_manifest_path(directory, name)
        if archive.exists() or archive.is_symlink() or manifest.exists() or manifest.is_symlink():
            raise CheckoutError("checkout backup destination already exists")
        try:
            create_archive(path, self._backup_members(path), archive, manifest)
            verify_archive(archive, manifest)
        except ArchiveError as error:
            self._discard_incomplete_backup(archive, manifest)
            raise CheckoutError("checkout backup creation failed") from error

    def _backup_members(self, path: Path) -> tuple[str, ...]:
        members: list[str] = []

        def visit(directory: Path, relative: PurePosixPath) -> None:
            try:
                entries = tuple(os.scandir(directory))
            except OSError as error:
                raise CheckoutError("checkout backup cannot inspect working tree") from error
            for entry in entries:
                child_relative = relative / entry.name
                if relative == PurePosixPath(".") and entry.name in {".git", OWNER_FILENAME}:
                    continue
                try:
                    metadata = entry.stat(follow_symlinks=False)
                except OSError as error:
                    raise CheckoutError("checkout backup cannot inspect working tree") from error
                if stat.S_ISLNK(metadata.st_mode):
                    raise CheckoutError("checkout backup rejects unsafe working-tree entries")
                if stat.S_ISDIR(metadata.st_mode):
                    visit(Path(entry.path), child_relative)
                elif stat.S_ISREG(metadata.st_mode):
                    members.append(child_relative.as_posix())
                    if len(members) > MAX_BACKUPS:
                        raise CheckoutError("checkout backup exceeds its file limit")
                else:
                    raise CheckoutError("checkout backup rejects unsafe working-tree entries")

        visit(path, PurePosixPath("."))
        return tuple(sorted(members))

    @staticmethod
    def _discard_incomplete_backup(archive: Path, manifest: Path) -> None:
        for path in (archive, manifest):
            try:
                metadata = path.lstat()
            except FileNotFoundError:
                continue
            except OSError:
                continue
            if stat.S_ISREG(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode):
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    continue

    def _receipt_age_hours(self, receipt: RefreshReceipt | None) -> float | None:
        if receipt is None:
            return None
        try:
            refreshed = datetime.fromisoformat(receipt.refreshed_at.replace("Z", "+00:00"))
            age = (self.now().astimezone(UTC) - refreshed.astimezone(UTC)).total_seconds() / 3600
        except (TypeError, ValueError):
            return None
        return age if age >= 0 else None

    def replace_policy(self, *, mode: object, ttl_hours: object) -> bool:
        self.preview_policy(mode=mode, ttl_hours=ttl_hours)
        raise CheckoutError("checkout policy replacement requires confirmed preview")

    def preview_policy(self, *, mode: object, ttl_hours: object) -> dict[str, object]:
        config = self._config()
        if (
            not isinstance(mode, str)
            or isinstance(ttl_hours, bool)
            or not isinstance(ttl_hours, int)
        ):
            raise CheckoutError("checkout policy fields are invalid")
        try:
            proposed = CheckoutConfig(root=config.root, mode=mode, ttl_hours=ttl_hours)
        except CheckoutRootError as error:
            raise CheckoutError(str(error)) from error
        payload = {
            "current": TtlPolicy.from_config(config).to_dict(),
            "proposed": TtlPolicy.from_config(proposed).to_dict(),
        }
        return {
            **payload,
            "preview_digest": _digest(payload),
        }

    def apply_policy(
        self,
        *,
        mode: object,
        ttl_hours: object,
        preview_digest: object,
        confirm: object,
    ) -> dict[str, object]:
        if confirm is not True or not isinstance(preview_digest, str):
            raise CheckoutError("checkout policy apply requires confirmed preview")
        preview = self.preview_policy(mode=mode, ttl_hours=ttl_hours)
        if preview["preview_digest"] != preview_digest:
            raise CheckoutError("checkout policy preview is stale")
        changed = self._write_policy(preview["proposed"])
        return {"changed": changed, "policy": preview["proposed"]}

    def _write_policy(self, raw: object) -> bool:
        if not isinstance(raw, dict):
            raise CheckoutError("checkout policy is invalid")
        try:
            policy = TtlPolicy(**raw)
            config = self._config()
            return self.root_store.write(
                CheckoutConfig(root=config.root, mode=policy.mode, ttl_hours=policy.ttl_hours), ()
            )
        except CheckoutRootError as error:
            raise CheckoutError(str(error)) from error

    def _compat_runner(
        self, command: tuple[str, ...], _environment: Mapping[str, str]
    ) -> tuple[int, str]:
        code, stdout, stderr = self.runner(command, Path(command[2]))
        return code, (stdout + stderr).decode("utf-8", "surrogateescape")

    def _git_text(self, command: tuple[str, ...], path: Path) -> str | None:
        code, stdout, _stderr = self.runner(command, path)
        text = stdout.decode("utf-8", "surrogateescape").strip()
        return text if code == 0 and re.fullmatch(r"[0-9a-f]{40}", text) else None

    def _status_counts(
        self, path: Path, project_id: str, *, require_marker: bool = True
    ) -> tuple[int, int, int]:
        marker = path / OWNER_FILENAME
        if require_marker:
            try:
                marker_content = read_private_text(
                    marker, maximum_bytes=256, label="checkout owner marker"
                )
            except (FileNotFoundError, ProfileFileError) as error:
                raise CheckoutError("checkout owner marker is unavailable") from error
            if marker_content != owner_marker_content(project_id):
                raise CheckoutError("checkout owner marker is invalid")
        command = (
            "git", "-C", str(path), "status", "--porcelain=v1", "-z",
            "--untracked-files=all", "--ignored=matching",
        )
        code, stdout, stderr = self.runner(command, path)
        if code != 0 or len(stdout) + len(stderr) > MAX_STATUS_OUTPUT_BYTES:
            raise CheckoutError("checkout status command is unavailable")
        if stdout and not stdout.endswith(b"\x00"):
            raise CheckoutError("checkout status command returned malformed output")
        tracked = untracked = ignored = 0
        records = stdout.split(b"\x00")
        index = 0
        while index < len(records) - 1:
            record = records[index]
            index += 1
            if not record:
                raise CheckoutError("checkout status command returned malformed output")
            if len(record) < 4 or record[2:3] != b" ":
                raise CheckoutError("checkout status command returned malformed output")
            code = record[:2]
            name = record[3:]
            if code[0:1] in {b"R", b"C"} or code[1:2] in {b"R", b"C"}:
                if index >= len(records) - 1 or not records[index]:
                    raise CheckoutError("checkout status command returned malformed output")
                index += 1
            if require_marker and code == b"??" and name == OWNER_FILENAME.encode():
                continue
            if code == b"??":
                untracked += 1
            elif code == b"!!":
                ignored += 1
            else:
                tracked += 1
        return tracked, untracked, ignored


def _run_git(command: tuple[str, ...], _path: Path) -> tuple[int, bytes, bytes]:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            timeout=GIT_STATUS_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise CheckoutError("checkout git command is unavailable") from error
    return completed.returncode, completed.stdout, completed.stderr


def _digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()
