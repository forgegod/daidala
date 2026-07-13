from __future__ import annotations

import importlib.util
import subprocess
import sys
import types
from pathlib import Path

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
        "workflows",
        "workflow_detail",
        "decisions",
        "recommendations",
        "constraint_preview",
        "constraint_replace",
        "wizard_inventory",
        "wizard_create_board",
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


def test_router_source_has_only_read_routes_and_nonmutating_preview() -> None:
    source = MODULE.read_text(encoding="utf-8")

    assert "@router.put" not in source
    assert "@router.delete" not in source
    assert '@router.post("/constraints/preview")' in source
    assert "sqlite3" not in source
    assert "kanban.db" not in source
    assert "DashboardBackend" in source
    assert '@router.post("/constraints/replace")' in source
    assert 'payload.get("confirm") is not True' in source


def test_default_service_is_process_cached_to_avoid_concurrent_store_initialization() -> None:
    api = load_api()
    service = object()
    calls = 0

    class Backend:
        @classmethod
        def from_default_profile(cls):
            nonlocal calls
            calls += 1
            return types.SimpleNamespace(service=service)

    api.__dict__["DashboardBackend"] = Backend
    api._default_service.cache_clear()

    assert api._default_service() is service
    assert api._default_service() is service
    assert calls == 1
