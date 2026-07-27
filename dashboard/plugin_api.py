"""Bounded Daidala routes mounted by the Hermes dashboard host.

This module is the dashboard backend proven by Phase 0. It exports the
``router`` symbol the Hermes dashboard process mounts under
``/api/plugins/daidala/``. The implementation is profile-safe, exposes only
closed pack/setup/constraint mutations, never imports Hermes internals, and
never writes the Kanban database. Live card data is read on demand through the same public
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

import hashlib
import json
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
from daidala.locations import resolve_data_root
from daidala.pack_service import (
    PackConfirmationError,
    PackInstallError,
    PackService,
    PackServiceError,
    StalePackPreviewError,
    UnknownPackSkillError,
)
from daidala.packs import PackError
from daidala.registrations import (
    ControllerRegistration,
    list_controller_registrations,
)
from daidala.service import ServiceError
from daidala.setup_wizard import (
    SetupRequest,
    SetupWizardError,
    active_profile,
    create_board,
    list_boards,
    list_profiles,
)
from daidala.skills import (
    MissingSkillsError,
    ProfileSkillContentRegistry,
    SkillRevisionError,
)
from daidala.store import StoreError

router = APIRouter()


ServiceFactory = Callable[[], Any]
PackServiceFactory = Callable[[], PackService]
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


@lru_cache(maxsize=1)
def _cached_default_pack_service() -> PackService:
    return PackService.from_default_profile()


def _default_pack_service() -> PackService:
    return _cached_default_pack_service()


pack_service_factory: PackServiceFactory = _default_pack_service


def configure_backend(backend: Any, *, pack_service: PackService | None = None) -> None:
    """Inject a pre-built backend (used by tests and setup wiring)."""

    global pack_service_factory, service_factory

    service_factory = backend.service_factory()
    if pack_service is not None:
        def configured_pack_service() -> PackService:
            return pack_service

        pack_service_factory = configured_pack_service


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
        "read_model": True,
        "bounded_mutations": ["pack_install", "workflow_setup", "constraints_replace"],
    }


@router.get("/prerequisites")
def prerequisites() -> dict[str, Any]:
    """Expose pack info and required skills for the setup wizard."""

    backend = DashboardBackend(service_factory=service_factory)
    return backend.prerequisites()


@router.get("/packs")
def packs() -> dict[str, Any]:
    """List bundled packs with their validated six-stage declarations."""

    service = pack_service_factory()
    return {
        "packs": [service.validate(name).to_dict() for name in service.bundled_names()]
    }


@router.post("/packs/{pack_name}/validate")
def pack_validate(pack_name: str) -> dict[str, Any]:
    """Explicitly validate one bundled pack through the shared service."""

    try:
        return {"valid": True, "pack": pack_service_factory().validate(pack_name).to_dict()}
    except PackError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/packs/{pack_name}/check")
def pack_check(pack_name: str) -> dict[str, Any]:
    """Resolve current host, source, and exact installed-skill readiness."""

    try:
        return pack_service_factory().check(pack_name).to_dict()
    except (PackError, PackServiceError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/packs/{pack_name}/skills/{skill_name}")
def pack_skill_content(pack_name: str, skill_name: str) -> dict[str, Any]:
    """Return one declared, path-free, bounded installed SKILL.md document."""

    try:
        return pack_service_factory().skill_content(pack_name, skill_name).to_dict()
    except UnknownPackSkillError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except PackError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/packs/{pack_name}/install/preview")
def pack_install_preview(pack_name: str) -> dict[str, Any]:
    """Return the complete canonical installation preview without mutation."""

    return pack_check(pack_name)


@router.post("/packs/{pack_name}/install")
def pack_install(pack_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Apply only the exact reviewed preview after literal confirmation."""

    if payload.get("confirm") is not True:
        raise HTTPException(status_code=400, detail="explicit confirmation is required")
    preview_digest = payload.get("preview_digest")
    if not isinstance(preview_digest, str) or not preview_digest.strip():
        raise HTTPException(status_code=400, detail="preview_digest is required")
    try:
        return pack_service_factory().install(
            pack_name,
            expected_preview_digest=preview_digest,
            confirm=True,
        ).to_dict()
    except PackConfirmationError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except StalePackPreviewError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except (PackInstallError, PackError, PackServiceError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


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
    """List the profile-safe identities eligible for setup selection."""
    try:
        controller_profile = active_profile(
            _run_command,
            fallback_name=resolve_data_root().name,
        )
        return {
            "controller_profile": controller_profile,
            "boards": list_boards(_run_command),
            "profiles": list_profiles(_run_command),
            "packs": ["addyosmani", "aidlc"],
            "policy_sources": _profile_policy_sources(),
            "projects": [
                {
                    "project_id": registration.project_id,
                    "repository": registration.verified_remote,
                }
                for registration in _registered_projects(controller_profile).values()
            ],
        }
    except SetupWizardError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.post("/wizard/boards/preview")
def wizard_board_preview(payload: dict[str, Any]) -> dict[str, Any]:
    """Preview an explicit board creation against the current inventory."""
    slug, name = _board_request(payload)
    try:
        boards = list_boards(_run_command)
    except SetupWizardError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    if any(row.get("slug") == slug for row in boards):
        raise HTTPException(status_code=409, detail="board slug already exists")
    command = ["hermes", "kanban", "boards", "create", slug]
    if name:
        command.extend(("--name", name))
    preview = {"command": command, "boards": boards, "slug": slug, "name": name}
    return {"preview": preview, "preview_digest": _digest(preview)}


@router.post("/wizard/boards")
def wizard_create_board(payload: dict[str, Any]) -> dict[str, Any]:
    """Create one board only from the exact current preview and confirmation."""
    if payload.get("confirm") is not True:
        raise HTTPException(status_code=400, detail="explicit confirmation is required")
    expected = payload.get("preview_digest")
    if not isinstance(expected, str) or len(expected) != 64:
        raise HTTPException(status_code=400, detail="preview_digest is required")
    slug, name = _board_request(payload)
    preview = wizard_board_preview({"slug": slug, "name": name})
    if preview["preview_digest"] != expected:
        raise HTTPException(status_code=409, detail="board inputs changed after preview")
    try:
        create_board(_run_command, slug=slug, name=name)
    except SetupWizardError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"created": True, "slug": slug}


@router.post("/wizard/readiness")
def wizard_readiness(payload: dict[str, Any]) -> dict[str, Any]:
    """Run the same mutation-free preflight used by confirmed start."""
    request, service = _resolved_setup_request(payload, apply=False)
    try:
        preflight = service.validate_start_preflight(**_preflight_kwargs(request))
    except (ServiceError, MissingSkillsError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return _setup_preview(request, preflight)


@router.post("/wizard/preview")
def wizard_preview(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the safe request projection and exact fresh start digest."""
    request, service = _resolved_setup_request(payload, apply=False)
    try:
        preflight = service.validate_start_preflight(**_preflight_kwargs(request))
    except (ServiceError, MissingSkillsError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return _setup_preview(request, preflight)


@router.post("/wizard/start")
def wizard_start(payload: dict[str, Any]) -> dict[str, Any]:
    """Apply only the exact, revalidated selected-registration preview."""
    request, service = _resolved_setup_request(payload, apply=True)
    try:
        preflight = service.validate_start_preflight(**_preflight_kwargs(request))
    except (ServiceError, MissingSkillsError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    preview = _setup_preview(request, preflight)
    if payload["preview_digest"] != preview["preview_digest"]:
        raise HTTPException(status_code=409, detail="setup inputs changed after preview")
    if request.workflow_id is not None:
        try:
            service.store.get(request.workflow_id)
        except StoreError as error:
            if not str(error).startswith("unknown workflow:"):
                raise HTTPException(status_code=409, detail=str(error)) from error
        else:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "workflow_exists",
                    "workflow_id": request.workflow_id,
                },
            )
    try:
        ledger = service.start(**request.start_kwargs())
    except (ServiceError, MissingSkillsError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"workflow": ledger.to_dict()}


_SETUP_REQUEST_FIELDS = frozenset(
    {
        "board_slug",
        "goal",
        "pack",
        "workflow_id",
        "stage_profiles",
        "constraints_content",
        "constraints_skill",
        "constraints_skill_digest",
    }
)


def _registered_projects(
    controller_profile: str | None = None,
) -> dict[str, ControllerRegistration]:
    """Read only registrations bound to the mounted controller profile."""
    try:
        registrations = list_controller_registrations(resolve_data_root().resolve())
    except ValueError as error:
        raise SetupWizardError("registered project is invalid") from error
    if controller_profile is not None:
        registrations = tuple(
            registration
            for registration in registrations
            if registration.controller_profile == controller_profile
        )
    return {registration.project_id: registration for registration in registrations}


def _resolved_setup_request(payload: dict[str, Any], *, apply: bool) -> tuple[SetupRequest, Any]:
    required_fields = {"selection", "request"}
    if apply:
        if payload.get("confirm") is not True:
            raise HTTPException(status_code=400, detail="explicit confirmation is required")
        digest = payload.get("preview_digest")
        if not isinstance(digest, str) or len(digest) != 64:
            raise HTTPException(status_code=400, detail="preview_digest is required")
        required_fields.update({"preview_digest", "confirm"})
    if set(payload) != required_fields:
        raise HTTPException(status_code=400, detail="unknown wizard envelope fields")
    selection = payload.get("selection")
    request = payload.get("request")
    if not isinstance(selection, dict) or set(selection) != {"project_id"}:
        raise HTTPException(status_code=400, detail="selection must contain only project_id")
    project_id = selection.get("project_id")
    if not isinstance(project_id, str) or not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")
    if not isinstance(request, dict) or set(request) - _SETUP_REQUEST_FIELDS:
        raise HTTPException(status_code=400, detail="unknown setup request fields")
    try:
        registration = _registered_projects(active_profile(_run_command)).get(project_id)
    except SetupWizardError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    if registration is None:
        raise HTTPException(status_code=404, detail="unknown registered project")
    try:
        resolved = SetupRequest.from_payload(
            {**request, "target_repository": registration.checkout}
        )
    except SetupWizardError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return resolved, service_factory()


def _setup_preview(request: SetupRequest, preflight: Any) -> dict[str, Any]:
    """Return path-free UI facts while binding the full trusted request."""
    private_request = request.start_kwargs()
    projection = {
        key: value for key, value in private_request.items() if key != "target_repository"
    }
    readiness = {
        "checks": [
            {"id": "pack-ready", "passed": True},
            {"id": "repository-clean", "passed": True},
            {"id": "board-available", "passed": True},
            {"id": "stage-profiles-available", "passed": True},
        ],
        "baseline_commit": preflight.baseline_commit,
    }
    digest_source = {"request": private_request, "readiness": readiness}
    return {
        "confirmed": False,
        "request": projection,
        "readiness": readiness,
        "preview_digest": _digest(digest_source),
    }


def _preflight_kwargs(request: SetupRequest) -> dict[str, Any]:
    """Project the complete setup request onto the shared readiness contract."""
    values = request.start_kwargs()
    values.pop("goal")
    return values


def _profile_policy_sources() -> list[dict[str, str]]:
    registry = ProfileSkillContentRegistry(resolve_data_root() / "skills")
    try:
        sources = []
        for name in sorted(registry.installed_names()):
            digest = registry.content_digest(name)
            if digest is not None:
                sources.append({"name": name, "digest": digest})
        return sources
    except SkillRevisionError as error:
        raise SetupWizardError("installed policy source inventory is invalid") from error


def _board_request(payload: dict[str, Any]) -> tuple[str, str]:
    allowed = {"slug", "name", "preview_digest", "confirm"}
    if set(payload) - allowed:
        raise HTTPException(status_code=400, detail="unknown board request fields")
    slug = payload.get("slug")
    if not isinstance(slug, str):
        raise HTTPException(status_code=400, detail="board slug is required")
    try:
        create_board(lambda _command: (0, ""), slug=slug, name=None)
    except SetupWizardError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        raise HTTPException(status_code=400, detail="board display name is required")
    return slug, name.strip()


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _run_command(command: tuple[str, ...]) -> tuple[int, str]:
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    return completed.returncode, completed.stdout or completed.stderr


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    raise HTTPException(status_code=400, detail="string fields must be strings")


__all__ = [
    "router",
    "configure_backend",
    "ServiceFactory",
    "PackServiceFactory",
]