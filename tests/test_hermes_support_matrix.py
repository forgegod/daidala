from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "run_hermes_support_matrix.py"


def load_matrix() -> ModuleType:
    scripts = str(SCRIPT.parent)
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    name = "daidala_support_matrix_test"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def wheel_file(tmp_path: Path) -> tuple[Path, str]:
    wheel = tmp_path / "daidala-0.2.0-py3-none-any.whl"
    wheel.write_bytes(b"exact wheel fixture")
    return wheel, hashlib.sha256(wheel.read_bytes()).hexdigest()


def host(module: ModuleType, label: str = "baseline", port: str = "9120"):
    return module.Host.from_values(
        [label, "0.18.2", "2026.7.7.2", "4281151a", sys.executable, port]
    )


def test_matrix_rejects_partial_host_identity() -> None:
    module = load_matrix()

    with pytest.raises(SystemExit) as raised:
        module._parser().parse_args(
            [
                "--wheel",
                "candidate.whl",
                "--expected-wheel-sha256",
                "0" * 64,
                "--host",
                "baseline",
                "0.18.2",
            ]
        )

    assert raised.value.code == 2


def test_host_tuple_preserves_virtual_environment_python_symlink(tmp_path: Path) -> None:
    module = load_matrix()
    executable = tmp_path / "venv" / "bin" / "python"
    executable.parent.mkdir(parents=True)
    executable.symlink_to(sys.executable)

    selected = module.Host.from_values(
        ["baseline", "0.18.2", "2026.7.7.2", "4281151a", str(executable), "9120"]
    )

    assert selected.python == executable.absolute()
    assert selected.python != executable.resolve()


def test_matrix_rejects_wrong_wheel_digest_before_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_matrix()
    wheel, _ = wheel_file(tmp_path)
    called = False

    def unexpected(*_args: object, **_kwargs: object) -> str:
        nonlocal called
        called = True
        return ""

    monkeypatch.setattr(module, "_run", unexpected)

    with pytest.raises(module.MatrixError, match="wheel digest mismatch"):
        module.preflight(wheel, "0" * 64)

    assert called is False


@pytest.mark.parametrize("failed_check", ["twine", "contents"])
def test_matrix_rejects_preflight_check_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failed_check: str,
) -> None:
    module = load_matrix()
    wheel, digest = wheel_file(tmp_path)
    calls = 0

    def run(command: list[str], **_kwargs: object) -> str:
        nonlocal calls
        calls += 1
        is_twine = command[1:4] == ["-m", "twine", "check"]
        if (failed_check == "twine" and is_twine) or (
            failed_check == "contents" and not is_twine
        ):
            raise module.MatrixError(f"{failed_check} failed")
        return "passed"

    monkeypatch.setattr(module, "_run", run)

    with pytest.raises(module.MatrixError, match=f"{failed_check} failed"):
        module.preflight(wheel, digest)

    assert calls == (1 if failed_check == "twine" else 2)


def test_matrix_rejects_preview_mutation() -> None:
    module = load_matrix()
    payload = {
        "success": True,
        "cli": {
            "admission_preview": {
                "byte_identical": True,
                "state_unchanged": False,
                "native_exit": 0,
                "standalone_exit": 0,
            }
        },
    }

    with pytest.raises(module.MatrixError, match="admission preview evidence"):
        module._validate_probe("probe_hermes_plugin_compatibility.py", payload)


def test_matrix_rejects_native_standalone_mismatch() -> None:
    module = load_matrix()
    payload = {
        "success": True,
        "cli": {
            "admission_preview": {
                "byte_identical": False,
                "state_unchanged": True,
                "native_exit": 0,
                "standalone_exit": 0,
            }
        },
    }

    with pytest.raises(module.MatrixError, match="admission preview evidence"):
        module._validate_probe("probe_hermes_plugin_compatibility.py", payload)


def test_matrix_accepts_directory_discovery_without_duplicate_admission() -> None:
    module = load_matrix()
    payload = {
        "success": True,
        "plugin": {"discovery": "directory"},
        "cli": {"admission_preview": None},
    }

    module._validate_probe("probe_hermes_plugin_compatibility.py", payload)


def test_matrix_rejects_missing_literal_confirmation() -> None:
    module = load_matrix()
    payload = {
        "success": True,
        "setup": {
            "preview_confirmed": False,
            "unconfirmed_start_status": 200,
            "state_unchanged": False,
        },
    }

    with pytest.raises(module.MatrixError, match="literal-confirmation"):
        module._validate_probe("probe_hermes_dashboard_compatibility.py", payload)


def test_entrypoint_metadata_lookup_is_anchored_to_host_purelib(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_matrix()
    entry_points = tmp_path / "daidala-0.2.0.dist-info" / "entry_points.txt"
    entry_points.parent.mkdir()
    entry_points.write_text("[hermes_agent.plugins]\ndaidala = daidala\n")
    commands: list[list[str]] = []

    def run(command: list[str], **_kwargs: object) -> str:
        commands.append(command)
        return f"{entry_points}\n"

    monkeypatch.setattr(module, "_run", run)

    assert module._entry_points_file(host(module)) == entry_points
    assert "get_path('purelib')" in commands[0][2]
    assert "importlib.metadata" not in commands[0][2]


def test_matrix_cleans_owned_root_on_host_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_matrix()
    wheel, digest = wheel_file(tmp_path)
    work_root = tmp_path / "matrix-root"
    monkeypatch.setattr(
        module,
        "preflight",
        lambda *_args, **_kwargs: {"wheel": str(wheel), "wheel_sha256": digest},
    )

    def fail(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise module.MatrixError("host failed")

    monkeypatch.setattr(module, "run_host", fail)

    with pytest.raises(module.MatrixError, match="host failed"):
        module.run_matrix(
            wheel=wheel,
            expected_digest=digest,
            hosts=[host(module)],
            work_root=work_root,
        )

    assert not work_root.exists()


def test_matrix_rejects_root_inside_active_hermes_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_matrix()
    active = tmp_path / "active"
    active.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(active))

    with pytest.raises(module.MatrixError, match="inside the active HERMES_HOME"):
        module.run_matrix(
            wheel=tmp_path / "missing.whl",
            expected_digest="0" * 64,
            hosts=[host(module)],
            work_root=active / "nested",
        )


def test_matrix_runs_entrypoint_and_directory_probes_twice_per_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_matrix()
    wheel, _ = wheel_file(tmp_path)
    selected = host(module)
    root = tmp_path / "root"
    root.mkdir()
    entry_points = tmp_path / "entry_points.txt"
    entry_points.write_text("[hermes_agent.plugins]\ndaidala = daidala\n")
    monkeypatch.delenv("HERMES_HOME", raising=False)
    monkeypatch.setattr(module, "_host_executable", lambda *_args: Path("/bin/true"))
    monkeypatch.setattr(module, "_entry_points_file", lambda _host: entry_points)

    def run(command: list[str], **_kwargs: object) -> str:
        probe = Path(command[1]).name if len(command) > 1 else ""
        if probe == "probe_hermes_plugin_compatibility.py":
            discovery = "directory" if "--plugin-directory" in command else "entrypoint"
            admission = None if discovery == "directory" else {
                "byte_identical": True,
                "state_unchanged": True,
                "native_exit": 0,
                "standalone_exit": 0,
            }
            return json.dumps(
                {
                    "success": True,
                    "plugin": {"discovery": discovery},
                    "cli": {"admission_preview": admission},
                },
                sort_keys=True,
            )
        if probe == "probe_hermes_dashboard_compatibility.py":
            return json.dumps(
                {
                    "success": True,
                    "setup": {
                        "preview_confirmed": False,
                        "unconfirmed_start_status": 400,
                        "state_unchanged": True,
                    },
                },
                sort_keys=True,
            )
        return json.dumps({"success": True}, sort_keys=True)

    monkeypatch.setattr(module, "_run", run)

    evidence = module.run_host(selected, wheel, root)

    repetitions = evidence["repetitions"]
    assert len(repetitions) == 2
    assert [len(row["probes"]) for row in repetitions] == [4, 4]
    assert {
        probe["probe"]
        for repetition in repetitions
        for probe in repetition["probes"]
    } == {*module.PROBES, "probe_hermes_plugin_directory_compatibility.py"}
    assert entry_points.is_file()
    assert not entry_points.with_suffix(".txt.matrix-disabled").exists()


def test_matrix_restores_entrypoint_metadata_when_directory_probe_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_matrix()
    wheel, _ = wheel_file(tmp_path)
    root = tmp_path / "root"
    root.mkdir()
    entry_points = tmp_path / "entry_points.txt"
    entry_points.write_text("[hermes_agent.plugins]\ndaidala = daidala\n")
    monkeypatch.delenv("HERMES_HOME", raising=False)
    monkeypatch.setattr(module, "_host_executable", lambda *_args: Path("/bin/true"))
    monkeypatch.setattr(module, "_entry_points_file", lambda _host: entry_points)

    def record(
        _host: object,
        probe: str,
        _repetition: int,
        _env: dict[str, str],
        *,
        extra_args: tuple[str, ...] = (),
        evidence_name: str | None = None,
    ) -> dict[str, object]:
        if extra_args:
            raise module.MatrixError("directory failed")
        return {
            "probe": evidence_name or probe,
            "evidence": {"success": True},
        }

    monkeypatch.setattr(module, "_record_probe", record)
    monkeypatch.setattr(module, "_run", lambda *_args, **_kwargs: "")

    with pytest.raises(module.MatrixError, match="directory failed"):
        module.run_host(host(module), wheel, root)

    assert entry_points.is_file()
    assert not entry_points.with_suffix(".txt.matrix-disabled").exists()


def test_matrix_output_is_canonical_and_private(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = load_matrix()
    output = tmp_path / "evidence.json"
    evidence = {"schema": "test/v1", "success": True}
    monkeypatch.setattr(module, "run_matrix", lambda **_kwargs: evidence)

    result = module.main(
        [
            "--wheel",
            str(tmp_path / "candidate.whl"),
            "--expected-wheel-sha256",
            "0" * 64,
            "--host",
            "baseline",
            "0.18.2",
            "2026.7.7.2",
            "4281151a",
            sys.executable,
            "9120",
            "--output",
            str(output),
        ]
    )

    assert result == 0
    assert output.read_text(encoding="utf-8") == json.dumps(
        evidence, sort_keys=True, separators=(",", ":")
    ) + "\n"
    assert os.stat(output).st_mode & 0o777 == 0o600
    assert capsys.readouterr().out == output.read_text(encoding="utf-8")
