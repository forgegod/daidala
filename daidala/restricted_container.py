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
REQUEST_SCHEMA = "daidala.restricted-container-request/v2"
EXECUTION_SCHEMA = "daidala.restricted-container-execution/v2"
MAX_OUTPUT_BYTES = 65_536
MAX_REQUEST_BYTES = 1_048_576
MAX_FIXTURE_FILES = 64
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


@dataclass(frozen=True)
class RestrictedContainerRequest:
    workflow_id: str
    role: str
    repository_revision: str
    controller_revision: str
    image_identity: str
    files: tuple[tuple[str, str], ...]
    command: tuple[str, ...]
    expected_exit_code: int
    schema: str = REQUEST_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != REQUEST_SCHEMA:
            raise ContainerIsolationError(
                f"restricted-container request schema must be {REQUEST_SCHEMA!r}"
            )
        if not re.fullmatch(r"cycle-[0-9a-f]{64}", self.workflow_id):
            raise ContainerIsolationError("restricted-container workflow ID is invalid")
        if self.role not in {"baseline", "candidate"}:
            raise ContainerIsolationError(
                "restricted-container request role must be baseline or candidate"
            )
        if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", self.repository_revision):
            raise ContainerIsolationError(
                "restricted-container repository revision is invalid"
            )
        if not isinstance(self.controller_revision, str) or not re.fullmatch(
            r"[0-9a-f]{40}", self.controller_revision
        ):
            raise ContainerIsolationError(
                "restricted-container controller revision is invalid"
            )
        try:
            validate_pinned_image_identity(self.image_identity)
        except PolicyViolationError as error:
            raise ContainerIsolationError(
                "restricted-container request image is not canonical"
            ) from error
        if not isinstance(self.files, tuple) or not 1 <= len(self.files) <= MAX_FIXTURE_FILES:
            raise ContainerIsolationError(
                f"restricted-container request requires 1-{MAX_FIXTURE_FILES} fixture files"
            )
        names = [name for name, _content in self.files]
        if names != sorted(names) or len(names) != len(set(names)):
            raise ContainerIsolationError(
                "restricted-container fixture paths must be unique canonical order"
            )
        total = 0
        for name, content in self.files:
            _fixture_path(name)
            if not isinstance(content, str):
                raise ContainerIsolationError(
                    "restricted-container fixture content must be text"
                )
            total += len(content.encode("utf-8"))
        if total > MAX_REQUEST_BYTES:
            raise ContainerIsolationError(
                "restricted-container fixture content exceeds 1048576 bytes"
            )
        _command_vector(self.command)
        if (
            isinstance(self.expected_exit_code, bool)
            or not isinstance(self.expected_exit_code, int)
            or not 0 <= self.expected_exit_code <= 255
        ):
            raise ContainerIsolationError(
                "restricted-container expected exit code must be 0-255"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "workflow_id": self.workflow_id,
            "role": self.role,
            "repository_revision": self.repository_revision,
            "controller_revision": self.controller_revision,
            "image_identity": self.image_identity,
            "files": {name: content for name, content in self.files},
            "command": list(self.command),
            "expected_exit_code": self.expected_exit_code,
        }

    @property
    def digest(self) -> str:
        return hashlib.sha256(_canonical_json(self.to_dict())).hexdigest()

    @classmethod
    def from_dict(cls, raw: Any) -> RestrictedContainerRequest:
        required = {
            "schema",
            "workflow_id",
            "role",
            "repository_revision",
            "controller_revision",
            "image_identity",
            "files",
            "command",
            "expected_exit_code",
        }
        if not isinstance(raw, dict) or set(raw) != required:
            raise ContainerIsolationError(
                "restricted-container request fields are invalid"
            )
        files = raw["files"]
        command = raw["command"]
        if not isinstance(files, dict) or not isinstance(command, list):
            raise ContainerIsolationError(
                "restricted-container request files or command are invalid"
            )
        return cls(
            schema=raw["schema"],
            workflow_id=raw["workflow_id"],
            role=raw["role"],
            repository_revision=raw["repository_revision"],
            controller_revision=raw["controller_revision"],
            image_identity=raw["image_identity"],
            files=tuple(sorted(files.items())),
            command=tuple(command),
            expected_exit_code=raw["expected_exit_code"],
        )


@dataclass(frozen=True)
class RestrictedContainerEvidence:
    request_digest: str
    workflow_id: str
    role: str
    repository_revision: str
    controller_revision: str
    image_identity: str
    image_id: str
    fixture_digest: str
    command: tuple[str, ...]
    expected_exit_code: int
    exit_code: int
    output: str
    output_digest: str
    schema: str = EXECUTION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != EXECUTION_SCHEMA:
            raise ContainerIsolationError(
                f"restricted-container execution schema must be {EXECUTION_SCHEMA!r}"
            )
        if not isinstance(self.controller_revision, str) or not re.fullmatch(
            r"[0-9a-f]{40}", self.controller_revision
        ):
            raise ContainerIsolationError(
                "restricted-container controller revision is invalid"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "request_digest": self.request_digest,
            "workflow_id": self.workflow_id,
            "role": self.role,
            "repository_revision": self.repository_revision,
            "controller_revision": self.controller_revision,
            "image_identity": self.image_identity,
            "image_id": self.image_id,
            "fixture_digest": self.fixture_digest,
            "command": list(self.command),
            "expected_exit_code": self.expected_exit_code,
            "exit_code": self.exit_code,
            "output": self.output,
            "output_digest": self.output_digest,
        }

    @property
    def digest(self) -> str:
        return hashlib.sha256(_canonical_json(self.to_dict())).hexdigest()


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


def load_restricted_container_request(path: Path) -> RestrictedContainerRequest:
    """Load one bounded, strict evaluator execution request."""
    if not isinstance(path, Path):
        raise ContainerIsolationError("restricted-container request path must be a Path")
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise ContainerIsolationError("restricted-container request is unavailable") from error
    if len(payload) > MAX_REQUEST_BYTES:
        raise ContainerIsolationError("restricted-container request exceeds 1048576 bytes")
    try:
        raw = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ContainerIsolationError("restricted-container request JSON is invalid") from error
    return RestrictedContainerRequest.from_dict(raw)


def run_restricted_container_request(
    request: RestrictedContainerRequest,
    data_root: Path,
    *,
    executor: RestrictedContainerExecutor | None = None,
) -> tuple[RestrictedContainerEvidence, Path]:
    """Execute one request and retain immutable content-addressed evidence."""
    if not isinstance(request, RestrictedContainerRequest):
        raise ContainerIsolationError("restricted-container request is invalid")
    if not isinstance(data_root, Path) or not data_root.is_absolute():
        raise ContainerIsolationError("restricted-container data root must be absolute")
    resolved_root = data_root.resolve()
    selected = executor or RestrictedContainerExecutor(request.image_identity)
    if selected.image_identity != request.image_identity:
        raise ContainerIsolationError(
            "restricted-container executor image does not match request"
        )
    with tempfile.TemporaryDirectory(prefix="daidala-evaluator-request-") as root:
        workspace = Path(root).resolve()
        for name, content in request.files:
            relative = _fixture_path(name)
            target = workspace / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        execution = selected.execute(workspace, request.command)
    fixture_digest = hashlib.sha256(
        _canonical_json({"files": {name: content for name, content in request.files}})
    ).hexdigest()
    evidence = RestrictedContainerEvidence(
        request_digest=request.digest,
        workflow_id=request.workflow_id,
        role=request.role,
        repository_revision=request.repository_revision,
        controller_revision=request.controller_revision,
        image_identity=execution.image_identity,
        image_id=execution.image_id,
        fixture_digest=fixture_digest,
        command=execution.command,
        expected_exit_code=request.expected_exit_code,
        exit_code=execution.exit_code,
        output=execution.output,
        output_digest=hashlib.sha256(execution.output.encode("utf-8")).hexdigest(),
    )
    payload = _canonical_json(evidence.to_dict())
    path = (
        resolved_root
        / "workflows"
        / request.workflow_id
        / "artifacts"
        / f"evaluator-{request.role}-{evidence.digest}.json"
    )
    _write_once(path, payload)
    return evidence, path


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


def _fixture_path(value: object) -> Path:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ContainerIsolationError("restricted-container fixture path is invalid")
    path = Path(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ContainerIsolationError("restricted-container fixture path is invalid")
    return path


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _write_once(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        if path.read_bytes() != payload:
            raise ContainerIsolationError(
                "restricted-container evidence path conflicts with existing content"
            ) from error
        return
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise


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
    output = completed.stdout
    if completed.stderr:
        output = output + ("\n" if output else "") + completed.stderr
    return completed.returncode, output.strip()
