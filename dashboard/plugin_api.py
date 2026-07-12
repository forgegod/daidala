"""Read-only Wingstaff routes mounted by the Hermes dashboard host.

This module is the dashboard backend proven by Phase 0. It exports the
``router`` symbol the Hermes dashboard process mounts under
``/api/plugins/wingstaff/``. The implementation is profile-safe, read-only,
and never imports Hermes internals or writes the Kanban database. Live
card data is read on demand through the same public
``KanbanGraphAdapter`` boundary the existing ``wingstaff_status`` tool
already uses.

The pure deterministic recommendation logic lives in
:mod:`wingstaff.recommendations`. The factory below only wires those pure
projections to FastAPI.

Phase 2 endpoints (all read-only):

- ``GET  /api/plugins/wingstaff/health``
- ``GET  /api/plugins/wingstaff/prerequisites``
- ``GET  /api/plugins/wingstaff/workflows``
- ``GET  /api/plugins/wingstaff/workflows/{workflow_id}``
- ``GET  /api/plugins/wingstaff/workflows/{workflow_id}/decisions``
- ``GET  /api/plugins/wingstaff/workflows/{workflow_id}/recommendations``
- ``POST /api/plugins/wingstaff/constraints/preview``
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from wingstaff.dashboard_backend import (
    DashboardBackend,
    DashboardBackendError,
    HostUnavailableError,
    UnknownWorkflowError,
)
from wingstaff.service import WorkflowService

router = APIRouter()


ServiceFactory = Callable[[], WorkflowService]


def _default_service() -> WorkflowService:
    backend = DashboardBackend.from_default_profile()
    return backend.service


service_factory: ServiceFactory = _default_service


def configure_backend(backend: DashboardBackend) -> None:
    """Inject a pre-built backend (used by tests and setup wiring)."""

    global service_factory

    service_factory = backend.service_factory()


@router.get("/health")
def health() -> dict[str, Any]:
    """Report whether the dashboard backend can resolve its profile data."""

    try:
        service_factory()
    except DashboardBackendError as error:
        return {"success": False, "error": str(error)}
    return {
        "success": True,
        "plugin": "wingstaff",
        "read_only": True,
    }


@router.get("/prerequisites")
def prerequisites() -> dict[str, Any]:
    """Expose pack info and required skills for the setup wizard."""

    backend = DashboardBackend(service_factory=service_factory)
    return backend.prerequisites()


@router.get("/workflows")
def workflows() -> dict[str, Any]:
    """List every workflow ledger known to the active profile."""

    backend = DashboardBackend(service_factory=service_factory)
    return backend.list_workflows()


@router.get("/workflows/{workflow_id}")
def workflow_detail(workflow_id: str) -> dict[str, Any]:
    """Return policy facts and a live, read-only Kanban snapshot."""

    backend = DashboardBackend(service_factory=service_factory)
    try:
        return backend.workflow_view(workflow_id)
    except UnknownWorkflowError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except HostUnavailableError as error:
        return {
            "workflow_id": workflow_id,
            "workflow": None,
            "kanban": {"available": False, "cards": [], "error": str(error)},
        }


@router.get("/workflows/{workflow_id}/decisions")
def decisions(workflow_id: str) -> dict[str, Any]:
    """Human-action items only: approval, blocked, stale, replacement impact."""

    backend = DashboardBackend(service_factory=service_factory)
    try:
        return backend.decisions(workflow_id)
    except UnknownWorkflowError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/workflows/{workflow_id}/recommendations")
def recommendations(workflow_id: str) -> dict[str, Any]:
    """Full finite recommendation set including dispatch and delivery."""

    backend = DashboardBackend(service_factory=service_factory)
    try:
        return backend.recommendations(workflow_id)
    except UnknownWorkflowError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/constraints/preview")
def constraint_preview(request: Request) -> dict[str, Any]:
    """Return validation errors, canonical content, digest, and impact.

    Non-mutating: never touches the ledger, the worktree, the Kanban
    database, or any host state. Accepts a JSON body with one of
    ``constraints_content`` or ``constraints_skill`` plus
    ``constraints_skill_digest``.
    """

    try:
        payload = request.json() if hasattr(request, "json") else _read_json_body(request)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="request body must be a JSON object")

    workflow_id = payload.get("workflow_id")
    if not isinstance(workflow_id, str) or not workflow_id.strip():
        raise HTTPException(status_code=400, detail="workflow_id is required")

    backend = DashboardBackend(service_factory=service_factory)
    try:
        return backend.preview_constraints(
            workflow_id=workflow_id,
            constraints_content=_optional_str(payload.get("constraints_content")),
            constraints_skill=_optional_str(payload.get("constraints_skill")),
            constraints_skill_digest=_optional_str(
                payload.get("constraints_skill_digest")
            ),
            expected_current_digest=_optional_str(
                payload.get("expected_current_digest")
            ),
        )
    except UnknownWorkflowError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


def _read_json_body(request: Request) -> dict[str, Any]:
    import json

    body = request.body()
    if not body:
        return {}
    return json.loads(body.decode("utf-8"))


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    raise HTTPException(status_code=400, detail="string fields must be strings")


__all__ = ["router", "configure_backend", "ServiceFactory"]