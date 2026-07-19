"""Restricted-container execution and isolation evidence for evaluator setup."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import PolicyViolationError
from .evaluation import EvaluatorIsolationEvidence, validate_pinned_image_identity

PROBE_SCHEMA = "daidala.restricted-container-probe/v1"
POLICY_VERSION = "daidala.restricted-container-policy/v1"
MAX_OUTPUT_BYTES = 65_536
_ALLOWED_DOCKER_ENV = frozenset(
    {
        "DOCKER_CERT_PATH",
        "DOCKER_CONFIG",
        "DOCKER_CONTEXT",
        "DOCKER_HOST",
        "DOCKER_TLS_VERIFY",
        "LANG",
        "LC_ALL",
        "PATH",
    }
)
_CREDENTIAL_KEY = re.compile(
    r"(?:TOKEN|PASSWORD|PASSWD|SECRET|CREDENTIAL|API_KEY|PRIVATE_KEY|ACCESS_KEY)",
    re.IGNORECASE,
)
_CONTAINER_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
_PROBE_SCRIPT = r"""
test ! -e "$HOME/.daidala-probe"
printf 'probe\n' >"$HOME/.daidala-probe"
test -w /workspace
printf 'probe\n' >/workspace/.daidala-probe
rm -f /workspace/.daidala-probe
interfaces=""
for interface in /sys/class/net/*; do
    name="${interface##*/}"
    interfaces="${interfaces}${interfaces:+,}${name}"
done
environment_keys="$(env | sed 's/=.*//' | LC_ALL=C sort | tr '\n' ',' | sed 's/,$//')"
printf '%s\n' \
    'schema=daidala.restricted-container-probe/v1' \
    "home=$HOME" \
    "hermes_home=$HERMES_HOME" \
    'home_was_fresh=true' \
    'workspace_writable=true' \
    "network_interfaces=$interfaces" \
    "environment_keys=$environment_keys"
""".strip()

ContainerRunner = Callable[[tuple[str, ...], Mapping[str, str]], tuple[int, str]]


class ContainerIsolationError(ValueError):
    """Raised when a restricted-container policy or probe cannot be proven."""


@dataclass(frozen=True)
class RestrictedContainerExecution:
    image_identity: str
    image_id: str
    command: tuple[str, ...]
    exit_code: int
    output: str


class RestrictedContainerExecutor:
    """Run commands in one pinned, credential-free, denied-network container."""

    def __init__(
        self,
        image_identity: str,
        *,
        runner: ContainerRunner | None = None,
        environ: Mapping[str, str] | None = None,
        uid: int | None = None,
        gid: int | None = None,
    ) -> None:
        try:
            validate_pinned_image_identity(image_identity)
        except PolicyViolationError as error:
            raise ContainerIsolationError(
                "restricted-container requires a canonical pinned image name@sha256:<digest>"
            ) from error
        selected_uid = os.getuid() if uid is None else uid
        selected_gid = os.getgid() if gid is None else gid
        if (
            type(selected_uid) is not int
            or type(selected_gid) is not int
            or selected_uid <= 0
            or selected_gid <= 0
        ):
            raise ContainerIsolationError("restricted-container requires non-root host UID/GID")
        self.image_identity = image_identity
        self.runner = runner or _default_runner
        self.environment = _docker_environment(environ or os.environ)
        self.uid = selected_uid
        self.gid = selected_gid

    def policy(self) -> dict[str, Any]:
        """Return the non-secret policy displayed by the dry-run CLI."""
        return {
            "schema": POLICY_VERSION,
            "image_identity": self.image_identity,
            "network": "none",
            "read_only_root": True,
            "capabilities": "none",
            "no_new_privileges": True,
            "workspace_mount": "/workspace",
            "fresh_home": "/home/evaluator",
            "controller_environment_inherited": False,
            "output_limit_bytes": MAX_OUTPUT_BYTES,
        }

    def execute(
        self,
        workspace: Path,
        command: Sequence[str],
    ) -> RestrictedContainerExecution:
        """Execute an argv vector in a bounded candidate workspace."""
        resolved = _resolved_workspace(workspace)
        argv = _command_vector(command)
        image_id = self._inspect_image()
        docker_command = self._docker_command(resolved, argv)
        code, output = self.runner(docker_command, self.environment)
        _require_bounded_output(output)
        return RestrictedContainerExecution(
            image_identity=self.image_identity,
            image_id=image_id,
            command=tuple(argv),
            exit_code=code,
            output=output,
        )

    def probe(self) -> EvaluatorIsolationEvidence:
        """Run and validate the disposable setup isolation probe."""
        with tempfile.TemporaryDirectory(prefix="daidala-evaluator-probe-") as root:
            execution = self.execute(
                Path(root).resolve(),
                ("/bin/sh", "-ceu", _PROBE_SCRIPT),
            )
        if execution.exit_code != 0:
            raise ContainerIsolationError(
                f"restricted-container probe exited with {execution.exit_code}"
            )
        observed = _parse_probe_output(execution.output)
        if observed["home"] != "/home/evaluator" or observed["hermes_home"] != (
            "/home/evaluator"
        ):
            raise ContainerIsolationError("restricted-container fresh HOME was not enforced")
        if observed["home_was_fresh"] != "true":
            raise ContainerIsolationError("restricted-container HOME was not fresh")
        if observed["workspace_writable"] != "true":
            raise ContainerIsolationError("restricted-container workspace mount is not usable")
        if observed["network_interfaces"] != "lo":
            raise ContainerIsolationError("restricted-container network isolation is incomplete")
        environment_keys = {
            key for key in observed["environment_keys"].split(",") if key
        }
        sensitive = sorted(key for key in environment_keys if _CREDENTIAL_KEY.search(key))
        if sensitive:
            raise ContainerIsolationError(
                "restricted-container exposed credential-like environment keys: "
                + ", ".join(sensitive)
            )
        receipt_payload = {
            "schema": POLICY_VERSION,
            "policy": self.policy(),
            "image_identity": execution.image_identity,
            "image_id": execution.image_id,
            "network_interfaces": observed["network_interfaces"],
            "environment_keys": sorted(environment_keys),
            "uid": self.uid,
            "gid": self.gid,
        }
        receipt = "sha256:" + hashlib.sha256(
            json.dumps(
                receipt_payload,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return EvaluatorIsolationEvidence(
            backend="restricted-container",
            network="denied-by-default",
            image_identity=self.image_identity,
            fresh_home=True,
            network_denied=True,
            controller_credentials_absent=True,
            bounded_mounts=True,
            receipt_id=receipt,
        )

    def _inspect_image(self) -> str:
        command = (
            "docker",
            "image",
            "inspect",
            self.image_identity,
            "--format",
            "{{json .}}",
        )
        code, output = self.runner(command, self.environment)
        _require_bounded_output(output)
        if code != 0:
            raise ContainerIsolationError(
                f"pinned evaluator image inspection failed with exit {code}"
            )
        try:
            raw = json.loads(output)
        except (json.JSONDecodeError, TypeError) as error:
            raise ContainerIsolationError("pinned evaluator image inspection is invalid") from error
        if not isinstance(raw, dict):
            raise ContainerIsolationError("pinned evaluator image inspection is invalid")
        image_id = raw.get("Id")
        repo_digests = raw.get("RepoDigests")
        config = raw.get("Config")
        if (
            not isinstance(image_id, str)
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id)
            or not isinstance(repo_digests, list)
            or self.image_identity not in repo_digests
            or not isinstance(config, dict)
        ):
            raise ContainerIsolationError("pinned evaluator image identity is not exact")
        volumes = config.get("Volumes")
        if volumes not in (None, {}):
            raise ContainerIsolationError("pinned evaluator image declares volumes")
        return image_id

    def _docker_command(self, workspace: Path, command: tuple[str, ...]) -> tuple[str, ...]:
        user = f"{self.uid}:{self.gid}"
        tmpfs_options = f"rw,nosuid,nodev,noexec,size=64m,uid={self.uid},gid={self.gid}"
        return (
            "docker",
            "run",
            "--rm",
            "--pull",
            "never",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            "128",
            "--memory",
            "1g",
            "--cpus",
            "1",
            "--user",
            user,
            "--workdir",
            "/workspace",
            "--entrypoint",
            "",
            "--env",
            "HOME=/home/evaluator",
            "--env",
            "HERMES_HOME=/home/evaluator",
            "--env",
            "DAIDALA_EVALUATOR_PROBE=1",
            "--env",
            "LANG=C.UTF-8",
            "--env",
            f"PATH={_CONTAINER_PATH}",
            "--tmpfs",
            f"/home/evaluator:{tmpfs_options}",
            "--tmpfs",
            f"/tmp:{tmpfs_options}",
            "--mount",
            f"type=bind,src={workspace},dst=/workspace",
            self.image_identity,
            *command,
        )


def probe_restricted_container(
    image_identity: str,
    *,
    runner: ContainerRunner | None = None,
    environ: Mapping[str, str] | None = None,
    uid: int | None = None,
    gid: int | None = None,
) -> EvaluatorIsolationEvidence:
    """Run one disposable probe and return strict non-secret evidence."""
    return RestrictedContainerExecutor(
        image_identity,
        runner=runner,
        environ=environ,
        uid=uid,
        gid=gid,
    ).probe()


def _docker_environment(environ: Mapping[str, str]) -> dict[str, str]:
    selected = {
        key: value
        for key, value in environ.items()
        if key in _ALLOWED_DOCKER_ENV and isinstance(value, str)
    }
    selected.setdefault("PATH", os.defpath)
    selected.setdefault("LANG", "C.UTF-8")
    return selected


def _resolved_workspace(workspace: Path) -> Path:
    if not isinstance(workspace, Path):
        raise ContainerIsolationError("restricted-container workspace must be a Path")
    try:
        resolved = workspace.resolve(strict=True)
    except OSError as error:
        raise ContainerIsolationError("restricted-container workspace does not exist") from error
    if not resolved.is_dir() or not resolved.is_absolute():
        raise ContainerIsolationError("restricted-container workspace must be a directory")
    return resolved


def _command_vector(command: Sequence[str]) -> tuple[str, ...]:
    if isinstance(command, (str, bytes)) or not command:
        raise ContainerIsolationError("restricted-container command must be a non-empty argv")
    values = tuple(command)
    if any(not isinstance(value, str) or not value or "\x00" in value for value in values):
        raise ContainerIsolationError("restricted-container command contains an invalid argument")
    return values


def _parse_probe_output(output: str) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in output.splitlines():
        key, separator, value = line.partition("=")
        if not separator or not key or key in rows:
            raise ContainerIsolationError("restricted-container probe output is malformed")
        rows[key] = value
    required = {
        "schema",
        "home",
        "hermes_home",
        "home_was_fresh",
        "workspace_writable",
        "network_interfaces",
        "environment_keys",
    }
    if set(rows) != required or rows.get("schema") != PROBE_SCHEMA:
        raise ContainerIsolationError("restricted-container probe output schema is invalid")
    return rows


def _require_bounded_output(output: str) -> None:
    if not isinstance(output, str):
        raise ContainerIsolationError("restricted-container output must be text")
    if len(output.encode("utf-8")) > MAX_OUTPUT_BYTES:
        raise ContainerIsolationError("restricted-container output exceeds 65536 bytes")


def _default_runner(
    command: tuple[str, ...], environment: Mapping[str, str]
) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=300,
            env=dict(environment),
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ContainerIsolationError("restricted-container command is unavailable") from error
    output = completed.stdout if completed.returncode == 0 else completed.stderr
    return completed.returncode, output.strip()
