#!/usr/bin/env python3
"""Run the exact-wheel Daidala compatibility matrix against isolated Hermes hosts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from probe_hermes_compatibility import HostIdentity, ProbeError, require_isolated_root

ROOT = Path(__file__).resolve().parents[1]
MAX_EVIDENCE_BYTES = 1_048_576
PROBES = (
    "probe_hermes_compatibility.py",
    "probe_hermes_plugin_compatibility.py",
    "probe_hermes_dashboard_compatibility.py",
)
_DIGEST = re.compile(r"[0-9a-f]{64}")
_LABEL = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")


class MatrixError(RuntimeError):
    """Raised when exact-wheel support evidence is incomplete or invalid."""


@dataclass(frozen=True)
class Host:
    label: str
    identity: HostIdentity
    python: Path
    port: int

    @classmethod
    def from_values(cls, values: list[str]) -> Host:
        label, semver, build, upstream, python_value, port_value = values
        if not _LABEL.fullmatch(label):
            raise MatrixError(f"invalid host label: {label!r}")
        identity = HostIdentity(semver=semver, build=build, upstream=upstream)
        python = Path(python_value).expanduser().absolute()
        if not python.is_file() or not os.access(python, os.X_OK):
            raise MatrixError(f"host Python is not executable: {python}")
        try:
            port = int(port_value)
        except ValueError as error:
            raise MatrixError(f"host port is not an integer: {port_value!r}") from error
        if not 1 <= port <= 65_534:
            raise MatrixError(f"host port is outside 1..65534: {port}")
        return cls(label=label, identity=identity, python=python, port=port)

    def to_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "semver": self.identity.semver,
            "build": self.identity.build,
            "upstream": self.identity.upstream,
            "python": str(self.python),
            "port": self.port,
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _run(command: list[str], *, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(command, capture_output=True, env=env, text=True)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "no diagnostic output"
        raise MatrixError(
            f"command failed ({result.returncode}): {' '.join(command)}\n{detail}"
        )
    return result.stdout


def preflight(wheel: Path, expected_digest: str) -> dict[str, object]:
    resolved = wheel.expanduser().resolve(strict=True)
    if resolved.suffix != ".whl":
        raise MatrixError("matrix input must be one wheel file")
    if not _DIGEST.fullmatch(expected_digest):
        raise MatrixError("expected wheel digest must be 64 lowercase hexadecimal characters")
    digest = _sha256(resolved)
    if digest != expected_digest:
        raise MatrixError(
            f"wheel digest mismatch: expected {expected_digest}, observed {digest}"
        )
    twine_output = _run([sys.executable, "-m", "twine", "check", str(resolved)])
    contents_output = _run(
        [
            sys.executable,
            str(ROOT / "scripts" / "check_release_contents.py"),
            str(ROOT),
            "--wheel",
            str(resolved),
        ]
    )
    return {
        "wheel": str(resolved),
        "wheel_sha256": digest,
        "twine_check": hashlib.sha256(twine_output.encode()).hexdigest(),
        "release_contents_check": hashlib.sha256(contents_output.encode()).hexdigest(),
    }


def _host_executable(host: Host, name: str) -> Path:
    executable = host.python.parent / name
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise MatrixError(f"{host.label} host is missing executable: {executable}")
    return executable


def _probe_command(host: Host, probe: str, repetition: int) -> list[str]:
    command = [
        str(host.python),
        str(ROOT / "scripts" / probe),
        "--hermes",
        str(_host_executable(host, "hermes")),
        "--expected-semver",
        host.identity.semver,
        "--expected-build",
        host.identity.build,
        "--expected-upstream",
        host.identity.upstream,
    ]
    if probe == "probe_hermes_plugin_compatibility.py":
        command.extend(("--daidala", str(_host_executable(host, "daidala"))))
    elif probe == "probe_hermes_dashboard_compatibility.py":
        command.extend(("--port", str(host.port + repetition)))
    return command


def _validate_probe(probe: str, payload: Any) -> None:
    if not isinstance(payload, dict) or payload.get("success") is not True:
        raise MatrixError(f"{probe} did not return successful JSON")
    if probe == "probe_hermes_plugin_compatibility.py":
        admission = payload.get("cli", {}).get("admission_preview")
        if not isinstance(admission, dict):
            raise MatrixError("plugin probe omitted admission-preview evidence")
        if (
            admission.get("byte_identical") is not True
            or admission.get("state_unchanged") is not True
            or admission.get("native_exit") != admission.get("standalone_exit")
        ):
            raise MatrixError("plugin admission preview evidence is incompatible")
    elif probe == "probe_hermes_dashboard_compatibility.py":
        setup = payload.get("setup")
        if not isinstance(setup, dict):
            raise MatrixError("dashboard probe omitted setup evidence")
        if setup != {
            "preview_confirmed": False,
            "unconfirmed_start_status": 400,
            "state_unchanged": True,
        }:
            raise MatrixError("dashboard literal-confirmation evidence is incompatible")


def _record_probe(
    host: Host,
    probe: str,
    repetition: int,
    env: dict[str, str],
    *,
    extra_args: tuple[str, ...] = (),
    evidence_name: str | None = None,
) -> dict[str, object]:
    output = _run(
        [*_probe_command(host, probe, repetition), *extra_args],
        env=env,
    )
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as error:
        raise MatrixError(f"{probe} returned invalid JSON") from error
    _validate_probe(probe, payload)
    return {
        "probe": evidence_name or probe,
        "exit_code": 0,
        "output_sha256": hashlib.sha256(output.encode()).hexdigest(),
        "evidence": payload,
    }


def _entry_points_file(host: Host) -> Path:
    output = _run(
        [
            str(host.python),
            "-c",
            (
                "from pathlib import Path;"
                "from sysconfig import get_path;"
                "print(next(Path(get_path('purelib')).glob("
                "'daidala-*.dist-info/entry_points.txt')))"
            ),
        ]
    )
    path = Path(output.strip())
    if not path.is_file():
        raise MatrixError(f"{host.label} Daidala entry-point metadata is missing")
    return path


def run_host(host: Host, wheel: Path, root: Path) -> dict[str, object]:
    active_home = os.environ.get("HERMES_HOME")
    if active_home is not None:
        active = Path(active_home).expanduser().resolve()
        try:
            host.python.relative_to(active)
        except ValueError:
            pass
        else:
            raise MatrixError(f"host Python is inside the active HERMES_HOME: {active}")
    _run(
        [
            str(host.python),
            "-m",
            "pip",
            "install",
            "--force-reinstall",
            "--no-deps",
            str(wheel),
        ]
    )
    host_root = root / host.label
    host_root.mkdir()
    repetitions: list[dict[str, object]] = []
    for repetition in range(2):
        temp_root = host_root / f"run-{repetition + 1}"
        temp_root.mkdir()
        env = os.environ.copy()
        env["TMPDIR"] = str(temp_root)
        env.pop("HERMES_HOME", None)
        env.pop("HERMES_PROFILE", None)
        probe_results: list[dict[str, object]] = []
        for probe in PROBES:
            probe_results.append(_record_probe(host, probe, repetition, env))
        repetitions.append({"run": repetition + 1, "probes": probe_results})

    entry_points = _entry_points_file(host)
    disabled_entry_points = entry_points.with_suffix(".txt.matrix-disabled")
    entry_points.rename(disabled_entry_points)
    try:
        for repetition, run in enumerate(repetitions):
            temp_root = host_root / f"run-{repetition + 1}"
            env = os.environ.copy()
            env["TMPDIR"] = str(temp_root)
            env.pop("HERMES_HOME", None)
            env.pop("HERMES_PROFILE", None)
            directory_result = _record_probe(
                host,
                "probe_hermes_plugin_compatibility.py",
                repetition,
                env,
                extra_args=("--plugin-directory", str(ROOT)),
                evidence_name="probe_hermes_plugin_directory_compatibility.py",
            )
            evidence = directory_result["evidence"]
            if not isinstance(evidence, dict):
                raise MatrixError("directory plugin probe returned invalid evidence")
            discovery = evidence.get("plugin", {}).get("discovery")
            if discovery != "directory":
                raise MatrixError("directory plugin probe did not use directory discovery")
            run_probes = run["probes"]
            if not isinstance(run_probes, list):
                raise MatrixError("support matrix repetition has invalid probe evidence")
            run_probes.append(directory_result)
    finally:
        disabled_entry_points.rename(entry_points)
    return {"host": host.to_dict(), "repetitions": repetitions}


def run_matrix(
    *,
    wheel: Path,
    expected_digest: str,
    hosts: list[Host],
    work_root: Path | None,
) -> dict[str, object]:
    if not hosts:
        raise MatrixError("at least one complete host tuple is required")
    if len({host.label for host in hosts}) != len(hosts):
        raise MatrixError("host labels must be unique")
    if len({host.port for host in hosts}) != len(hosts):
        raise MatrixError("host dashboard ports must be unique")
    root: Path | None = None
    if work_root is not None:
        root = work_root.expanduser().resolve()
        try:
            require_isolated_root(root)
        except ProbeError as error:
            raise MatrixError(str(error)) from error
        if root.exists():
            raise MatrixError("matrix work root must not already exist")
    checks = preflight(wheel, expected_digest)
    resolved_wheel = Path(str(checks["wheel"]))
    if root is None:
        root = Path(tempfile.mkdtemp(prefix="daidala-support-matrix-"))
    else:
        root.mkdir(parents=True)
    try:
        require_isolated_root(root)
        legs = [run_host(host, resolved_wheel, root) for host in hosts]
        result = {
            "schema": "daidala.hermes-support-matrix/v1",
            "success": True,
            "preflight": checks,
            "hosts": legs,
        }
        encoded = json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
        if len(encoded) > MAX_EVIDENCE_BYTES:
            raise MatrixError("support-matrix evidence exceeds 1 MiB")
        return result
    except ProbeError as error:
        raise MatrixError(str(error)) from error
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--expected-wheel-sha256", required=True)
    parser.add_argument(
        "--host",
        action="append",
        nargs=6,
        metavar=("LABEL", "SEMVER", "BUILD", "UPSTREAM", "PYTHON", "PORT"),
        help="Complete host tuple; repeat once per isolated Hermes environment",
    )
    parser.add_argument("--work-root", type=Path)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        hosts = [Host.from_values(values) for values in (args.host or [])]
        result = run_matrix(
            wheel=args.wheel,
            expected_digest=args.expected_wheel_sha256,
            hosts=hosts,
            work_root=args.work_root,
        )
        encoded = json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n"
        if args.output is not None:
            output = args.output.expanduser().resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(encoded, encoding="utf-8")
            output.chmod(0o600)
        sys.stdout.write(encoded)
        return 0
    except (MatrixError, OSError, ValueError) as error:
        print(f"Hermes support matrix failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
