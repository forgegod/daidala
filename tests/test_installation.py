from __future__ import annotations

import importlib.util
import subprocess
import sys
import tomllib
from pathlib import Path
from zipfile import ZipFile

REPOSITORY = Path(__file__).parents[1]


def test_directory_plugin_entrypoint_uses_bundled_package() -> None:
    module_name = "wingstaff_directory_plugin_test"
    spec = importlib.util.spec_from_file_location(
        module_name,
        REPOSITORY / "__init__.py",
        submodule_search_locations=[str(REPOSITORY)],
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        assert module.register.__module__ == f"{module_name}.wingstaff"
    finally:
        for loaded_name in list(sys.modules):
            if loaded_name == module_name or loaded_name.startswith(f"{module_name}."):
                sys.modules.pop(loaded_name, None)


def test_directory_plugin_entrypoint_loads_in_fresh_isolated_process(
    tmp_path: Path,
) -> None:
    script = """
import importlib
import importlib.util
import pathlib
import sys

repository = pathlib.Path(sys.argv[1])
module_name = "wingstaff_isolated_directory_plugin"
spec = importlib.util.spec_from_file_location(
    module_name,
    repository / "__init__.py",
    submodule_search_locations=[str(repository)],
)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules[module_name] = module
spec.loader.exec_module(module)
assert module.register.__module__ == f"{module_name}.wingstaff"
packs = importlib.import_module(f"{module_name}.wingstaff.packs")
assert packs.load_pack("addyosmani").name == "addyosmani"
assert packs.load_pack("aidlc").name == "aidlc"
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", script, str(REPOSITORY)],
        cwd=tmp_path,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_pip_entrypoint_loads_plugin_module() -> None:
    project = tomllib.loads((REPOSITORY / "pyproject.toml").read_text(encoding="utf-8"))

    assert project["project"]["entry-points"]["hermes_agent.plugins"]["wingstaff"] == "wingstaff"


def test_wheel_contains_plugin_resources_and_module_entrypoint(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--outdir",
            str(tmp_path),
            str(REPOSITORY),
        ],
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    wheel = next(tmp_path.glob("wingstaff-*.whl"))
    with ZipFile(wheel) as archive:
        names = set(archive.namelist())
        assert "wingstaff/packs/addyosmani.yaml" in names
        assert "wingstaff/packs/aidlc.yaml" in names
        assert "wingstaff/skills/aidlc-adapter/SKILL.md" in names
        assert "wingstaff/skills/aidlc-adapter/references/LICENSE-AIDLC.txt" in names
        assert "wingstaff/skills/orchestrate/SKILL.md" in names
        entry_points_name = next(
            name for name in names if name.endswith(".dist-info/entry_points.txt")
        )
        entry_points = archive.read(entry_points_name).decode("utf-8")

    assert "wingstaff = wingstaff\n" in entry_points
    assert "wingstaff = wingstaff:register" not in entry_points
