"""Opt-in Hermes Cron scheduling for deterministic artifact curation."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import subprocess
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .artifact_curator import CuratorPolicy
from .errors import PolicyViolationError
from .profile_files import ProfileFileError, atomic_write_private_text, read_private_text

_STATE_SCHEMA = "daidala.artifact-curator-cron/v1"
_STATE_FILENAME = "artifact-curator-cron.json"
_SCRIPT_NAME = "daidala-artifact-curator.sh"
_JOB_NAME = "daidala-artifact-curator"
_MAX_STATE_BYTES = 16 * 1024
_MAX_INTERVAL_BYTES = 256
_JOB_ID = re.compile(r"^[0-9a-f]{12}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_CREATE_OUTPUT = re.compile(r"Created job:\s*([0-9a-f]{12})")
_UPDATE_OUTPUT = re.compile(r"Updated job:\s*([0-9a-f]{12})")
_SCRIPT = """#!/usr/bin/env bash
set -euo pipefail
exec daidala curator tick
"""
_SCRIPT_DIGEST = hashlib.sha256(_SCRIPT.encode("utf-8")).hexdigest()
_SCRIPT_ENTRYPOINT = "daidala curator tick"

CronCommandRunner = Callable[[tuple[str, ...]], tuple[int, str]]


class CuratorCronError(PolicyViolationError):
    """Raised when the curator Cron boundary cannot be verified safely."""


@dataclass(frozen=True)
class CuratorCronRecord:
    job_id: str
    controller_profile: str
    interval: str
    policy_digest: str
    script_name: str = _SCRIPT_NAME
    script_digest: str = _SCRIPT_DIGEST
    script_entrypoint: str = _SCRIPT_ENTRYPOINT

    def __post_init__(self) -> None:
        if not isinstance(self.job_id, str) or not _JOB_ID.fullmatch(self.job_id):
            raise CuratorCronError("artifact curator Cron job ID is invalid")
        _profile_name(self.controller_profile)
        _interval(self.interval)
        _digest(self.policy_digest, "artifact curator policy digest")
        if (
            self.script_name != _SCRIPT_NAME
            or self.script_digest != _SCRIPT_DIGEST
            or self.script_entrypoint != _SCRIPT_ENTRYPOINT
        ):
            raise CuratorCronError("artifact curator Cron script identity is invalid")

    def to_dict(self) -> dict[str, str]:
        return {
            "job_id": self.job_id,
            "controller_profile": self.controller_profile,
            "interval": self.interval,
            "policy_digest": self.policy_digest,
            "script_name": self.script_name,
            "script_digest": self.script_digest,
            "script_entrypoint": self.script_entrypoint,
        }

    @classmethod
    def from_dict(cls, raw: object) -> CuratorCronRecord:
        expected = {
            "job_id",
            "controller_profile",
            "interval",
            "policy_digest",
            "script_name",
            "script_digest",
            "script_entrypoint",
        }
        if not isinstance(raw, dict) or set(raw) != expected:
            raise CuratorCronError("artifact curator Cron state schema is invalid")
        try:
            return cls(**raw)
        except TypeError as error:
            raise CuratorCronError("artifact curator Cron state schema is invalid") from error


@dataclass(frozen=True)
class CuratorCronDocument:
    record: CuratorCronRecord | None = None
    schema: str = _STATE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != _STATE_SCHEMA or (
            self.record is not None and not isinstance(self.record, CuratorCronRecord)
        ):
            raise CuratorCronError("artifact curator Cron state schema is invalid")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "record": self.record.to_dict() if self.record is not None else None,
        }

    def canonical_bytes(self) -> bytes:
        content = _canonical(self.to_dict()) + b"\n"
        if len(content) > _MAX_STATE_BYTES:
            raise CuratorCronError("artifact curator Cron state exceeds its document bound")
        return content

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    @classmethod
    def from_dict(cls, raw: object) -> CuratorCronDocument:
        if not isinstance(raw, dict) or set(raw) != {"schema", "record"}:
            raise CuratorCronError("artifact curator Cron state schema is invalid")
        if raw["schema"] != _STATE_SCHEMA:
            raise CuratorCronError("artifact curator Cron state schema is invalid")
        record = raw["record"]
        return cls(
            schema=raw["schema"],
            record=CuratorCronRecord.from_dict(record) if record is not None else None,
        )


class CuratorCronStore:
    """Strict profile-local compare-and-swap document for one exact Cron job."""

    def __init__(self, data_root: Path) -> None:
        root = Path(data_root)
        if not root.is_absolute() or root.resolve() != root:
            raise CuratorCronError("artifact curator Cron root must be absolute and resolved")
        self.path = root / _STATE_FILENAME

    def read(self) -> CuratorCronDocument:
        try:
            content = read_private_text(
                self.path,
                maximum_bytes=_MAX_STATE_BYTES,
                label="artifact curator Cron state",
            )
        except FileNotFoundError:
            return CuratorCronDocument()
        except ProfileFileError as error:
            raise CuratorCronError("artifact curator Cron state is unavailable") from error
        try:
            raw = json.loads(content, object_pairs_hook=_reject_duplicate_keys)
            return CuratorCronDocument.from_dict(raw)
        except (json.JSONDecodeError, CuratorCronError) as error:
            raise CuratorCronError("artifact curator Cron state schema is invalid") from error

    def replace(
        self, document: CuratorCronDocument, *, expected_digest: str
    ) -> CuratorCronDocument:
        _digest(expected_digest, "artifact curator Cron state digest")
        current = self.read()
        if current.digest != expected_digest:
            raise CuratorCronError("artifact curator Cron state was modified concurrently")
        if current == document:
            return current
        try:
            atomic_write_private_text(
                self.path,
                document.canonical_bytes().decode("utf-8"),
                label="artifact curator Cron state",
            )
        except ProfileFileError as error:
            raise CuratorCronError("artifact curator Cron state cannot be replaced") from error
        return document


@dataclass(frozen=True)
class CuratorCronPreview:
    operation: str
    action: str
    state_digest: str
    controller_profile: str
    interval: str | None
    policy_digest: str
    job_id: str | None
    script_name: str
    script_digest: str
    script_entrypoint: str

    def _identity(self) -> dict[str, object]:
        return {
            "schema": "daidala.artifact-curator-cron-preview/v1",
            "operation": self.operation,
            "action": self.action,
            "state_digest": self.state_digest,
            "controller_profile": self.controller_profile,
            "interval": self.interval,
            "policy_digest": self.policy_digest,
            "job_id": self.job_id,
            "script_name": self.script_name,
            "script_digest": self.script_digest,
            "script_entrypoint": self.script_entrypoint,
        }

    @property
    def digest(self) -> str:
        return hashlib.sha256(_canonical(self._identity())).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return {**self._identity(), "preview_digest": self.digest}


@dataclass(frozen=True)
class CuratorCronResult:
    operation: str
    action: str
    replayed: bool
    record: CuratorCronRecord | None

    def to_dict(self) -> dict[str, object]:
        return {
            "operation": self.operation,
            "action": self.action,
            "replayed": self.replayed,
            "record": self.record.to_dict() if self.record is not None else None,
        }


class CuratorCronManager:
    """Preview and apply one profile-bound public Hermes Cron registration."""

    def __init__(
        self,
        data_root: Path,
        *,
        command_runner: CronCommandRunner | None = None,
    ) -> None:
        root = Path(data_root)
        if not root.is_absolute() or root.resolve() != root:
            raise CuratorCronError("artifact curator Cron root must be absolute and resolved")
        self.data_root = root
        self.profile_root = root.parent
        self.controller_profile = _controller_profile(self.profile_root)
        self.store = CuratorCronStore(root)
        self.script_path = self.profile_root / "scripts" / _SCRIPT_NAME
        self.lock_path = root / ".artifact-curator-cron.lock"
        self.command_runner = command_runner or _run_command

    def status(self) -> CuratorCronDocument:
        return self.store.read()

    def preview_setup(self, interval: str, policy: CuratorPolicy) -> CuratorCronPreview:
        selected_interval = _interval(interval)
        document = self.store.read()
        policy_digest = policy.digest
        current = document.record
        desired_matches = bool(
            current is not None
            and current.controller_profile == self.controller_profile
            and current.interval == selected_interval
            and current.policy_digest == policy_digest
        )
        if current is None:
            action = "create"
        elif desired_matches and self._script_matches():
            action = "none"
        elif desired_matches:
            action = "repair-script"
        else:
            action = "update"
        return CuratorCronPreview(
            operation="setup",
            action=action,
            state_digest=document.digest,
            controller_profile=self.controller_profile,
            interval=selected_interval,
            policy_digest=policy_digest,
            job_id=current.job_id if current is not None else None,
            script_name=_SCRIPT_NAME,
            script_digest=_SCRIPT_DIGEST,
            script_entrypoint=_SCRIPT_ENTRYPOINT,
        )

    def apply_setup(
        self,
        interval: str,
        policy: CuratorPolicy,
        *,
        expected_preview_digest: str,
        confirmed_controller_profile: str,
    ) -> CuratorCronResult:
        with _exclusive_lock(self.lock_path):
            return self._apply_setup_unlocked(
                interval,
                policy,
                expected_preview_digest=expected_preview_digest,
                confirmed_controller_profile=confirmed_controller_profile,
            )

    def _apply_setup_unlocked(
        self,
        interval: str,
        policy: CuratorPolicy,
        *,
        expected_preview_digest: str,
        confirmed_controller_profile: str,
    ) -> CuratorCronResult:
        preview = self.preview_setup(interval, policy)
        self._require_confirmation(
            preview,
            expected_preview_digest=expected_preview_digest,
            confirmed_controller_profile=confirmed_controller_profile,
        )
        if preview.action == "none":
            return CuratorCronResult("setup", "none", True, self.store.read().record)
        self._write_script()
        if preview.action == "repair-script":
            return CuratorCronResult("setup", "repair-script", False, self.store.read().record)
        if preview.action == "create":
            job_id = self._create_job(preview.interval)
        else:
            if preview.job_id is None:
                raise CuratorCronError("artifact curator Cron update lacks a recorded job ID")
            self._update_job(preview.job_id, preview.interval)
            job_id = preview.job_id
        if preview.interval is None:
            raise CuratorCronError("artifact curator Cron interval is missing")
        record = CuratorCronRecord(
            job_id=job_id,
            controller_profile=preview.controller_profile,
            interval=preview.interval,
            policy_digest=preview.policy_digest,
        )
        try:
            self.store.replace(
                CuratorCronDocument(record=record),
                expected_digest=preview.state_digest,
            )
        except CuratorCronError:
            if preview.action == "create":
                self.command_runner(("hermes", "cron", "remove", job_id))
            raise
        return CuratorCronResult("setup", preview.action, False, record)

    def preview_remove(self, policy: CuratorPolicy) -> CuratorCronPreview:
        document = self.store.read()
        current = document.record
        return CuratorCronPreview(
            operation="remove",
            action="remove" if current is not None else "none",
            state_digest=document.digest,
            controller_profile=self.controller_profile,
            interval=current.interval if current is not None else None,
            policy_digest=policy.digest,
            job_id=current.job_id if current is not None else None,
            script_name=_SCRIPT_NAME,
            script_digest=_SCRIPT_DIGEST,
            script_entrypoint=_SCRIPT_ENTRYPOINT,
        )

    def apply_remove(
        self,
        policy: CuratorPolicy,
        *,
        expected_preview_digest: str,
        confirmed_controller_profile: str,
    ) -> CuratorCronResult:
        with _exclusive_lock(self.lock_path):
            return self._apply_remove_unlocked(
                policy,
                expected_preview_digest=expected_preview_digest,
                confirmed_controller_profile=confirmed_controller_profile,
            )

    def _apply_remove_unlocked(
        self,
        policy: CuratorPolicy,
        *,
        expected_preview_digest: str,
        confirmed_controller_profile: str,
    ) -> CuratorCronResult:
        preview = self.preview_remove(policy)
        self._require_confirmation(
            preview,
            expected_preview_digest=expected_preview_digest,
            confirmed_controller_profile=confirmed_controller_profile,
        )
        if preview.action == "none":
            return CuratorCronResult("remove", "none", True, None)
        if preview.job_id is None:
            raise CuratorCronError("artifact curator Cron removal lacks a recorded job ID")
        code, _output = self.command_runner(("hermes", "cron", "remove", preview.job_id))
        if code != 0:
            raise CuratorCronError("Hermes Cron removal failed")
        self.store.replace(
            CuratorCronDocument(),
            expected_digest=preview.state_digest,
        )
        return CuratorCronResult("remove", "remove", False, None)

    def require_current_policy(self, policy: CuratorPolicy) -> CuratorCronRecord:
        record = self.store.read().record
        if record is None:
            raise CuratorCronError("artifact curator Cron job is not registered")
        if record.controller_profile != self.controller_profile:
            raise CuratorCronError("artifact curator Cron controller profile does not match")
        if record.policy_digest != policy.digest:
            raise CuratorCronError("artifact curator policy changed after Cron setup")
        if not self._script_matches():
            raise CuratorCronError("artifact curator Cron script identity does not match")
        return record

    def _create_job(self, interval: str | None) -> str:
        if interval is None:
            raise CuratorCronError("artifact curator Cron interval is missing")
        code, output = self.command_runner(
            (
                "hermes",
                "cron",
                "create",
                interval,
                "--no-agent",
                "--script",
                _SCRIPT_NAME,
                "--deliver",
                "local",
                "--name",
                _JOB_NAME,
            )
        )
        match = _first_line_match(output, _CREATE_OUTPUT)
        if code != 0 or match is None:
            raise CuratorCronError("Hermes Cron creation failed")
        return match.group(1)

    def _update_job(self, job_id: str, interval: str | None) -> None:
        if interval is None:
            raise CuratorCronError("artifact curator Cron interval is missing")
        code, output = self.command_runner(
            (
                "hermes",
                "cron",
                "edit",
                job_id,
                "--schedule",
                interval,
                "--script",
                _SCRIPT_NAME,
                "--no-agent",
                "--deliver",
                "local",
                "--name",
                _JOB_NAME,
            )
        )
        match = _first_line_match(output, _UPDATE_OUTPUT)
        if code != 0 or match is None or match.group(1) != job_id:
            raise CuratorCronError("Hermes Cron update failed")

    def _write_script(self) -> None:
        scripts = self.script_path.parent
        try:
            scripts.mkdir(mode=0o700, exist_ok=True)
        except OSError as error:
            raise CuratorCronError(
                "artifact curator Cron scripts directory is unavailable"
            ) from error
        if scripts.is_symlink() or scripts.resolve() != scripts:
            raise CuratorCronError("artifact curator Cron scripts directory is unsafe")
        try:
            atomic_write_private_text(
                self.script_path,
                _SCRIPT,
                label="artifact curator Cron script",
            )
        except ProfileFileError as error:
            raise CuratorCronError("artifact curator Cron script cannot be installed") from error

    def _script_matches(self) -> bool:
        try:
            content = read_private_text(
                self.script_path,
                maximum_bytes=4096,
                label="artifact curator Cron script",
            )
        except FileNotFoundError:
            return False
        except ProfileFileError as error:
            raise CuratorCronError("artifact curator Cron script is unavailable") from error
        return hashlib.sha256(content.encode("utf-8")).hexdigest() == _SCRIPT_DIGEST

    @staticmethod
    def _require_confirmation(
        preview: CuratorCronPreview,
        *,
        expected_preview_digest: str,
        confirmed_controller_profile: str,
    ) -> None:
        _digest(expected_preview_digest, "artifact curator Cron preview digest")
        if preview.digest != expected_preview_digest:
            raise CuratorCronError("artifact curator Cron preview digest does not match")
        if confirmed_controller_profile != preview.controller_profile:
            raise CuratorCronError("artifact curator Cron controller profile is not confirmed")


def _controller_profile(profile_root: Path) -> str:
    if profile_root.parent.name == "profiles":
        return _profile_name(profile_root.name)
    return "default"


def _profile_name(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > 128
        or any(character in value for character in "\x00\r\n\t")
    ):
        raise CuratorCronError("artifact curator controller profile is invalid")
    return value


def _interval(value: object) -> str:
    if (
        not isinstance(value, str)
        or value != value.strip()
        or not value
        or len(value.encode("utf-8")) > _MAX_INTERVAL_BYTES
        or any(character in value for character in "\x00\r\n")
    ):
        raise CuratorCronError("artifact curator Cron interval is invalid")
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise CuratorCronError(f"{label} is invalid")
    return value


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise CuratorCronError("artifact curator Cron state has duplicate keys")
        result[key] = value
    return result


def _first_line_match(output: str, pattern: re.Pattern[str]) -> re.Match[str] | None:
    first_line = next((line.strip() for line in output.splitlines() if line.strip()), "")
    return pattern.fullmatch(first_line)


@contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise CuratorCronError("artifact curator Cron lock contention") from error
        yield
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def _run_command(command: tuple[str, ...]) -> tuple[int, str]:
    completed = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return completed.returncode, completed.stdout
