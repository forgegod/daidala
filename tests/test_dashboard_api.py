from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

MODULE = Path(__file__).parents[1] / "dashboard" / "plugin_api.py"


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
        spec = importlib.util.spec_from_file_location("wingstaff_dashboard_api_test", MODULE)
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
    ):
        assert callable(getattr(api, name))


def test_router_source_has_only_read_routes_and_nonmutating_preview() -> None:
    source = MODULE.read_text(encoding="utf-8")

    assert "@router.put" not in source
    assert "@router.delete" not in source
    assert '@router.post("/constraints/preview")' in source
    assert "sqlite3" not in source
    assert "kanban.db" not in source
    assert "DashboardBackend" in source
