from __future__ import annotations

import importlib.util
import subprocess
import sys
import threading
import time
import types
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
MODULE = ROOT / "dashboard" / "plugin_api.py"


class FakeRouter:
    def get(self, _path: str):
        return lambda function: function

    def post(self, _path: str):
        return lambda function: function


class FakeHTTPException(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail


class FakeRequest:
    pass


def load_api():
    fake = types.ModuleType("fastapi")
    fake.__dict__["APIRouter"] = FakeRouter
    fake.__dict__["HTTPException"] = FakeHTTPException
    fake.__dict__["Request"] = FakeRequest
    original = sys.modules.get("fastapi")
    sys.modules["fastapi"] = fake
    try:
        spec = importlib.util.spec_from_file_location("daidala_dashboard_api_test", MODULE)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if original is None:
            sys.modules.pop("fastapi", None)
        else:
            sys.modules["fastapi"] = original


def test_router_exports_all_phase_two_routes() -> None:
    api = load_api()

    assert api.router is not None
    for name in (
        "health",
        "prerequisites",
        "packs",
        "pack_validate",
        "pack_check",
        "pack_skill_content",
        "pack_install_preview",
        "pack_install",
        "workflows",
        "workflow_detail",
        "decisions",
        "recommendations",
        "constraint_preview",
        "constraint_replace",
        "wizard_inventory",
        "wizard_board_preview",
        "wizard_create_board",
        "wizard_readiness",
        "wizard_preview",
        "wizard_start",
    ):
        assert callable(getattr(api, name))


def test_router_imports_after_directory_plugin_registration(tmp_path: Path) -> None:
    script = f"""
import importlib.util
import sys
import types
from pathlib import Path

root = Path({str(ROOT)!r})

class APIRouter:
    def get(self, *_args, **_kwargs):
        return lambda function: function
    def post(self, *_args, **_kwargs):
        return lambda function: function

fake_fastapi = types.ModuleType("fastapi")
fake_fastapi.APIRouter = APIRouter
fake_fastapi.HTTPException = type("HTTPException", (Exception,), {{}})
sys.modules["fastapi"] = fake_fastapi

root_spec = importlib.util.spec_from_file_location(
    "daidala_directory_plugin_test",
    root / "__init__.py",
    submodule_search_locations=[str(root)],
)
root_module = importlib.util.module_from_spec(root_spec)
sys.modules["daidala_directory_plugin_test"] = root_module
root_spec.loader.exec_module(root_module)
assert sys.modules["daidala"] is sys.modules["daidala_directory_plugin_test.daidala"]

api_spec = importlib.util.spec_from_file_location(
    "directory_dashboard_api", root / "dashboard" / "plugin_api.py"
)
api_module = importlib.util.module_from_spec(api_spec)
api_spec.loader.exec_module(api_module)
assert api_module.router is not None
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_router_source_exposes_only_closed_mutation_routes() -> None:
    source = MODULE.read_text(encoding="utf-8")

    assert "@router.put" not in source
    assert "@router.delete" not in source
    assert '@router.post("/constraints/preview")' in source
    assert "sqlite3" not in source
    assert "kanban.db" not in source
    assert "DashboardBackend" in source
    assert '@router.post("/packs/{pack_name}/install")' in source
    assert '@router.post("/constraints/replace")' in source
    assert 'payload.get("confirm") is not True' in source


def test_health_distinguishes_the_read_model_from_bounded_mutations() -> None:
    api = load_api()
    api.__dict__["service_factory"] = lambda: object()

    payload = api.health()

    assert payload["read_model"] is True
    assert "read_only" not in payload


def test_pack_routes_use_one_typed_service_projection() -> None:
    api = load_api()
    calls: list[object] = []

    class Result:
        def __init__(self, payload: dict[str, object]) -> None:
            self.payload = payload

        def to_dict(self) -> dict[str, object]:
            return self.payload

    class PackService:
        def bundled_names(self) -> tuple[str, ...]:
            return ("addyosmani", "aidlc")

        def validate(self, name: str) -> Result:
            calls.append(("validate", name))
            return Result({"name": name, "stages": [{"id": "define"}]})

        def check(self, name: str) -> Result:
            calls.append(("check", name))
            return Result({"name": name, "preview_digest": "a" * 64})

        def skill_content(self, pack: str, skill: str) -> Result:
            calls.append(("content", pack, skill))
            return Result({"pack": pack, "skill": skill, "content": "# exact\n"})

        def install(self, name: str, *, expected_preview_digest: str, confirm: bool) -> Result:
            calls.append(("install", name, expected_preview_digest, confirm))
            return Result({"success": True})

    api.__dict__["pack_service_factory"] = PackService

    assert [row["name"] for row in api.packs()["packs"]] == ["addyosmani", "aidlc"]
    assert api.pack_validate("aidlc")["valid"] is True
    assert api.pack_check("addyosmani")["preview_digest"] == "a" * 64
    assert api.pack_skill_content("aidlc", "aidlc-adapter")["content"] == "# exact\n"
    assert api.pack_install_preview("aidlc")["name"] == "aidlc"
    assert api.pack_install(
        "addyosmani", {"preview_digest": "a" * 64, "confirm": True}
    ) == {"success": True}
    assert ("install", "addyosmani", "a" * 64, True) in calls


def test_unconfirmed_pack_install_does_not_construct_service() -> None:
    api = load_api()
    calls = 0

    def pack_service_factory() -> object:
        nonlocal calls
        calls += 1
        return object()

    api.__dict__["pack_service_factory"] = pack_service_factory

    with pytest.raises(FakeHTTPException) as raised:
        api.pack_install("addyosmani", {"preview_digest": "a" * 64})

    assert raised.value.status_code == 400
    assert "explicit confirmation is required" in raised.value.detail
    assert calls == 0


def test_stale_pack_preview_maps_to_conflict_without_retry() -> None:
    api = load_api()

    class PackService:
        def install(self, *_args, **_kwargs):
            raise api.StalePackPreviewError("pack installation inputs changed after preview")

    api.__dict__["pack_service_factory"] = PackService

    with pytest.raises(FakeHTTPException) as raised:
        api.pack_install(
            "addyosmani", {"preview_digest": "a" * 64, "confirm": True}
        )

    assert raised.value.status_code == 409
    assert "changed after preview" in raised.value.detail


def test_unconfirmed_wizard_start_does_not_construct_service() -> None:
    api = load_api()
    calls = 0

    def service_factory() -> object:
        nonlocal calls
        calls += 1
        return object()

    api.__dict__["service_factory"] = service_factory

    with pytest.raises(FakeHTTPException) as raised:
        api.wizard_start({})

    assert raised.value.status_code == 400
    assert "explicit confirmation is required" in raised.value.detail
    assert calls == 0


def test_wizard_preview_rejects_browser_paths_and_unknown_fields_before_service() -> None:
    api = load_api()
    calls = 0

    def service_factory() -> object:
        nonlocal calls
        calls += 1
        return object()

    api.__dict__["service_factory"] = service_factory

    with pytest.raises(FakeHTTPException) as raised:
        api.wizard_preview(
            {
                "selection": {"project_id": "project"},
                "request": {"target_repository": "/browser/path"},
            }
        )

    assert raised.value.status_code == 400
    assert "unknown setup request fields" in raised.value.detail
    assert calls == 0


def test_default_service_is_process_cached_to_avoid_concurrent_store_initialization() -> None:
    api = load_api()
    service = object()
    calls = 0
    worker_count = 8
    start = threading.Barrier(worker_count)

    class Backend:
        @classmethod
        def from_default_profile(cls):
            nonlocal calls
            calls += 1
            time.sleep(0.05)
            return types.SimpleNamespace(service=service)

    api.__dict__["DashboardBackend"] = Backend
    api._reset_default_service()

    def resolve_service() -> object:
        start.wait()
        return api._default_service()

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        services = list(executor.map(lambda _index: resolve_service(), range(worker_count)))

    assert services == [service] * worker_count
    assert calls == 1
