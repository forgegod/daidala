"""Read-only Daidala routes mounted by the Hermes dashboard host.

This module is the dashboard backend proven by Phase 0. It exports the
``router`` symbol the Hermes dashboard process mounts under
``/api/plugins/daidala/``. The implementation is profile-safe, read-only,
and never imports Hermes internals or writes the Kanban database. Live
card data is read on demand through the same public
``KanbanGraphAdapter`` boundary the existing ``daidala_status`` tool
already uses.

The pure deterministic recommendation logic lives in
:mod:`daidala.recommendations`. The factory below only wires those pure
projections to FastAPI.

Phase 2 endpoints (all read-only):

- ``GET  /api/plugins/daidala/health``
- ``GET  /api/plugins/daidala/prerequisites``
- ``GET  /api/plugins/daidala/workflows``
- ``GET  /api/plugins/daidala/workflows/{workflow_id}``
- ``GET  /api/plugins/daidala/workflows/{workflow_id}/decisions``
- ``GET  /api/plugins/daidala/workflows/{workflow_id}/recommendations``
- ``POST /api/plugins/daidala/constraints/preview``
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from functools import lru_cache
from threading import Lock
from typing import Any

from fastapi import APIRouter, HTTPException

from daidala.dashboard_backend import (
    DashboardBackend,
    DashboardBackendError,
    HostUnavailableError,
    UnknownWorkflowError,
)
from daidala.setup_wizard import (
    SetupRequest,
    SetupWizardError,
    confirmed_start,
    create_board,
    list_boards,
    list_profiles,
)

router = APIRouter()


ServiceFactory = Callable[[], Any]
_default_service_lock = Lock()


@lru_cache(maxsize=1)
def _cached_default_service() -> Any:
    backend = DashboardBackend.from_default_profile()
    return backend.service


def _default_service() -> Any:
    with _default_service_lock:
        return _cached_default_service()


def _reset_default_service() -> None:
    with _default_service_lock:
        _cached_default_service.cache_clear()


service_factory: ServiceFactory = _default_service


def configure_backend(backend: Any) -> None:
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
        "plugin": "daidala",
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
def constraint_preview(payload: dict[str, Any]) -> dict[str, Any]:
    """Return canonical identity and replacement impact without mutating."""
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


@router.post("/constraints/replace")
def constraint_replace(payload: dict[str, Any]) -> dict[str, Any]:
    """Replace constraints after compare-and-swap and explicit confirmation."""
    if payload.get("confirm") is not True:
        raise HTTPException(status_code=400, detail="explicit confirmation is required")
    workflow_id = payload.get("workflow_id")
    if not isinstance(workflow_id, str) or not workflow_id.strip():
        raise HTTPException(status_code=400, detail="workflow_id is required")
    backend = DashboardBackend(service_factory=service_factory)
    try:
        return backend.replace_constraint_input(
            workflow_id=workflow_id,
            expected_current_digest=_optional_str(
                payload.get("expected_current_digest")
            ),
            constraints_content=_optional_str(payload.get("constraints_content")),
            constraints_skill=_optional_str(payload.get("constraints_skill")),
            constraints_skill_digest=_optional_str(
                payload.get("constraints_skill_digest")
            ),
        )
    except DashboardBackendError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/wizard/inventory")
def wizard_inventory() -> dict[str, Any]:
    """List existing boards, profiles, and supported workflow packs."""
    try:
        return {
            "boards": list_boards(_run_command),
            "profiles": list_profiles(_run_command),
            "packs": ["addyosmani", "aidlc"],
        }
    except SetupWizardError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.post("/wizard/boards")
def wizard_create_board(payload: dict[str, Any]) -> dict[str, Any]:
    """Create one explicitly requested board through the public Hermes CLI."""
    try:
        create_board(
            _run_command,
            slug=str(payload.get("slug", "")),
            name=_optional_str(payload.get("name")),
        )
    except SetupWizardError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"created": True, "slug": payload["slug"]}


@router.post("/wizard/preview")
def wizard_preview(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and display the exact start request without mutating."""
    try:
        return SetupRequest.from_payload(payload).preview()
    except SetupWizardError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/wizard/start")
def wizard_start(payload: dict[str, Any]) -> dict[str, Any]:
    """Invoke the existing service path after explicit confirmation."""
    try:
        ledger = confirmed_start(payload, service_factory().start)
    except SetupWizardError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"workflow": ledger.to_dict()}


def _run_command(command: tuple[str, ...]) -> tuple[int, str]:
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    return completed.returncode, completed.stdout or completed.stderr


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    raise HTTPException(status_code=400, detail="string fields must be strings")


__all__ = ["router", "configure_backend", "ServiceFactory"]