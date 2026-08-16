"""Bounded Daidala routes mounted by the Hermes dashboard host.

This module is the dashboard backend proven by Phase 0. It exports the
``router`` symbol the Hermes dashboard process mounts under
``/api/plugins/daidala/``. The implementation is profile-safe, exposes only
closed pack/setup/constraint/approval/review/card-remediation/cancellation mutations,
never imports Hermes internals, and never writes the Kanban database. Live card
detail is read on demand through bounded public ``hermes kanban`` commands.

The pure deterministic recommendation logic lives in
:mod:`daidala.recommendations`. The factory below only wires those pure
projections to FastAPI.

Supervision endpoints include:

- ``GET  /api/plugins/daidala/health``
- ``GET  /api/plugins/daidala/initialization``
- ``POST /api/plugins/daidala/initialization``
- ``POST /api/plugins/daidala/diagnostics/prerequisites``
- ``GET  /api/plugins/daidala/prerequisites``
- ``GET /api/plugins/daidala/workflows``
- ``GET /api/plugins/daidala/dispatcher-readiness``
- ``GET /api/plugins/daidala/workflows/{workflow_id}``
- ``GET /api/plugins/daidala/artifacts`` and exact artifact text/download
- ``GET/POST /api/plugins/daidala/artifact-curator[...]``
- ``GET  /api/plugins/daidala/workflows/{workflow_id}/approval-review``
- ``GET  /api/plugins/daidala/workflows/{workflow_id}/review-decision``
- ``GET  /api/plugins/daidala/workflows/{workflow_id}/decisions``
- ``GET  /api/plugins/daidala/workflows/{workflow_id}/recommendations``
- ``POST /api/plugins/daidala/workflows/{workflow_id}/approve``
- ``POST /api/plugins/daidala/workflows/{workflow_id}/review-disposition/preview``
- ``POST /api/plugins/daidala/workflows/{workflow_id}/review-disposition``
- ``POST /api/plugins/daidala/workflows/{workflow_id}/delivery/preview``
- ``POST /api/plugins/daidala/workflows/{workflow_id}/delivery``
- ``POST /api/plugins/daidala/workflows/{workflow_id}/cards/{card_id}/comment``
- ``POST /api/plugins/daidala/workflows/{workflow_id}/cards/{card_id}/unblock``
- ``POST /api/plugins/daidala/workflows/{workflow_id}/cancel/preview``
- ``POST /api/plugins/daidala/workflows/{workflow_id}/cancel``
- ``POST /api/plugins/daidala/constraints/preview``
- ``GET  /api/plugins/daidala/constraints/sources``
- ``GET  /api/plugins/daidala/constraints/sources/{source_name}``
- ``GET  /api/plugins/daidala/configuration``
- ``GET  /api/plugins/daidala/registrations``
- ``GET  /api/plugins/daidala/github-project-links``
- ``GET  /api/plugins/daidala/github-project-links/{project_id}``
- ``POST /api/plugins/daidala/github-project-links/preview``
- ``POST /api/plugins/daidala/github-project-links/{project_id}/verify``
- ``PUT  /api/plugins/daidala/github-project-links/{project_id}``
- ``DELETE /api/plugins/daidala/github-project-links/{project_id}``
- ``GET  /api/plugins/daidala/checkout-root``
- ``POST /api/plugins/daidala/checkout-root/preview``
- ``PUT  /api/plugins/daidala/checkout-root``
- ``GET  /api/plugins/daidala/checkouts``
- ``POST /api/plugins/daidala/checkouts/{project_id}/refresh/preview``
- ``POST /api/plugins/daidala/checkouts/{project_id}/refresh``
- ``POST /api/plugins/daidala/checkouts/{project_id}/adopt/preview``
- ``POST /api/plugins/daidala/checkouts/{project_id}/adopt``
- ``POST /api/plugins/daidala/checkouts/_backups/prune/preview``
- ``POST /api/plugins/daidala/checkouts/_backups/prune``
- ``POST /api/plugins/daidala/checkouts/policy/preview``
- ``PUT  /api/plugins/daidala/checkouts/policy``
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
from collections.abc import Callable, Iterator
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from threading import Lock
from typing import Any, NoReturn

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse

from daidala.artifact_access import ArtifactAccessError, ArtifactFailureReason
from daidala.artifact_curator import CuratorError
from daidala.checkout_root import (
    CheckoutConfig,
    CheckoutRootError,
    CheckoutRootStore,
    discover_owned_checkouts,
)
from daidala.checkouts import CheckoutError, CheckoutManager
from daidala.constraints import extract_policy_skill_constraints, parse_workflow_constraints
from daidala.dashboard_advice import (
    SetupAnalysisError,
    SetupAnalysisUnavailable,
    build_setup_analysis_snapshot,
    request_setup_analysis,
)
from daidala.dashboard_backend import (
    DashboardBackend,
    DashboardBackendError,
    HostUnavailableError,
    UnknownWorkflowError,
)
from daidala.delivery import BranchDeliveryService, DeliveryError
from daidala.errors import PolicyViolationError, WorkflowError
from daidala.gateway import (
    probe_profile_gateways,
    stopped_worker_gateways,
    validate_profile_name,
)
from daidala.github_project_links import (
    GitHubProjectLink,
    GitHubProjectLinkError,
    GitHubProjectLinksStore,
    GitHubProjectVerifier,
)
from daidala.initialization import (
    InitializationError,
    apply_initialization,
    preview_initialization,
)
from daidala.kanban import KanbanError
from daidala.locations import resolve_data_root
from daidala.pack_service import (
    MAX_SKILL_DOCUMENT_BYTES,
    PackActionError,
    PackConfirmationError,
    PackInstallError,
    PackInstallEvent,
    PackService,
    PackServiceError,
    SkillAction,
    StalePackPreviewError,
    UnknownPackSkillError,
)
from daidala.packs import PackError
from daidala.prerequisites import run_prerequisite_diagnosis
from daidala.registrations import (
    ControllerRegistration,
    list_controller_registrations,
    registration_path,
)
from daidala.repository_bootstrap import (
    RepositoryBootstrapError,
    RepositoryBootstrapService,
)
from daidala.repository_registration import (
    RepositoryRegistrationError,
    RepositoryRegistrationService,
    resolve_profile_root,
)
from daidala.revision import MAX_REVIEW_FEEDBACK_BYTES
from daidala.service import ServiceError, assignee_stage_mismatches, live_card_statuses
from daidala.setup_wizard import (
    LocalProjectInitializer,
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
from daidala.state import ReviewDispositionAction
from daidala.store import StoreError

router = APIRouter()


def _raise_artifact_error(error: ArtifactAccessError) -> NoReturn:
    status = (
        404
        if error.reason
        in {
            ArtifactFailureReason.ARTIFACT_NOT_FOUND,
            ArtifactFailureReason.WORKFLOW_UNAVAILABLE,
        }
        else 413
        if error.reason is ArtifactFailureReason.OVERSIZED
        else 409
    )
    raise HTTPException(
        status_code=status,
        detail={"message": "Artifact unavailable", "reason": error.reason.value},
    ) from error


def _curator_request(
    payload: dict[str, object], *, apply: bool
) -> tuple[str, str | None, str | None]:
    operation = payload.get("operation")
    if operation not in {"pin", "unpin", "archive", "restore"}:
        raise HTTPException(status_code=400, detail="Curator operation is invalid")
    expected = {"operation", "archive_id"} if operation == "restore" else {"operation"}
    if apply:
        expected |= {"preview_digest", "confirm"}
    if set(payload) != expected or (apply and payload.get("confirm") is not True):
        raise HTTPException(status_code=400, detail="Curator request is malformed")
    archive_id = payload.get("archive_id")
    preview_digest = payload.get("preview_digest")
    for value, label in ((archive_id, "archive ID"), (preview_digest, "preview digest")):
        if value is not None and (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise HTTPException(status_code=400, detail=f"{label} is invalid")
    assert isinstance(operation, str)
    assert archive_id is None or isinstance(archive_id, str)
    assert preview_digest is None or isinstance(preview_digest, str)
    return operation, archive_id, preview_digest


ServiceFactory = Callable[[], Any]
PackServiceFactory = Callable[[], PackService]
_default_service_lock = Lock()
_DASHBOARD_REVIEW_ACTOR = "dashboard:attended-operator"
_SUPPORTED_HERMES_RANGE = ">=0.18.2,<0.21.0"


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
card_detail_provider: Callable[[str, str], dict[str, Any]]


@lru_cache(maxsize=1)
def _cached_default_pack_service() -> PackService:
    return PackService.from_default_profile()


def _default_pack_service() -> PackService:
    return _cached_default_pack_service()


pack_service_factory: PackServiceFactory = _default_pack_service
github_project_verifier_factory: Callable[[], GitHubProjectVerifier] = GitHubProjectVerifier


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
        "identity": _dashboard_identity(),
        "bounded_mutations": [
            "initialization",
            "pack_install",
            "pack_skill_availability",
            "workflow_setup",
            "constraints_replace",
            "workflow_approve",
            "review_disposition_preview",
            "review_disposition",
            "branch_delivery",
            "artifact_curator",
        ],
    }


def _dashboard_identity() -> dict[str, str]:
    """Return bounded runtime identity without making missing host metadata fatal."""

    try:
        profile = active_profile(_run_command)
    except (SetupWizardError, OSError):
        profile = "unavailable"
    try:
        package_version = version("daidala")
    except PackageNotFoundError:
        package_version = "unavailable"
    code, output = _run_command(("hermes", "--version"))
    match = re.search(r"Hermes Agent v(\d+\.\d+\.\d+)", output)
    hermes_version = match.group(1) if code == 0 and match is not None else "unavailable"
    return {
        "profile": profile,
        "daidala_version": package_version,
        "install_source": "unavailable",
        "hermes_version": hermes_version,
        "supported_hermes_range": _SUPPORTED_HERMES_RANGE,
    }


@router.get("/initialization")
def initialization() -> dict[str, Any]:
    """Preview profile-local policy-ledger initialization without mutation."""

    return preview_initialization(resolve_data_root()).to_dict()


@router.post("/initialization")
def initialize(payload: dict[str, Any]) -> dict[str, Any]:
    """Create the schema only for one fresh, literally confirmed preview."""

    if set(payload) != {"preview_digest", "confirm"}:
        raise HTTPException(
            status_code=400, detail="exact initialization apply fields are required"
        )
    try:
        preview, created = apply_initialization(
            resolve_data_root(),
            preview_digest=payload["preview_digest"],
            confirm=payload["confirm"],
        )
    except InitializationError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if created:
        _reset_default_service()
    return {"created": created, "initialization": preview.to_dict()}


@router.get("/prerequisites")
def prerequisites() -> dict[str, Any]:
    """Expose pack info and required skills for the setup wizard."""

    backend = DashboardBackend(service_factory=service_factory)
    return backend.prerequisites()


def _current_registrations() -> tuple[ControllerRegistration, ...]:
    try:
        return list_controller_registrations(resolve_data_root().resolve())
    except ValueError as error:
        raise HTTPException(status_code=409, detail="registered projects are invalid") from error


def _repository_registration_profile_root(controller_profile: str) -> Path:
    """Resolve one browser-named profile through Hermes before any profile read."""

    try:
        if controller_profile not in list_profiles(_run_command):
            raise RepositoryRegistrationError("selected Hermes profile is unavailable")
        return resolve_profile_root(controller_profile, _run_command)
    except (RepositoryRegistrationError, SetupWizardError) as error:
        raise HTTPException(
            status_code=409, detail="selected Hermes profile is unavailable"
        ) from error


def _repository_registration_service(
    controller_profile: str,
) -> RepositoryRegistrationService:
    """Bind a registration preview to one validated existing Hermes profile."""

    return RepositoryRegistrationService(
        _repository_registration_profile_root(controller_profile), controller_profile
    )


def _repository_bootstrap_service(
    controller_profile: str,
) -> RepositoryBootstrapService:
    """Bind a bootstrap preview to one validated existing Hermes profile."""

    return RepositoryBootstrapService(
        _repository_registration_profile_root(controller_profile), controller_profile
    )


def _delivery_service() -> BranchDeliveryService:
    """Resolve branch-delivery authority only for the mounted controller profile."""

    return BranchDeliveryService(service_factory(), profile_root=resolve_data_root())


def _registered_project(project_id: str) -> ControllerRegistration:
    registration = next(
        (row for row in _current_registrations() if row.project_id == project_id), None
    )
    if registration is None:
        raise HTTPException(status_code=404, detail="unknown registered project")
    return registration


@router.post("/diagnostics/prerequisites")
def prerequisite_diagnosis(payload: dict[str, Any]) -> dict[str, Any]:
    """Run strict prerequisite diagnosis for one trusted registration."""

    if set(payload) != {"project_id", "live"} or not isinstance(payload["live"], bool):
        raise HTTPException(
            status_code=400, detail="exact prerequisite diagnosis fields are required"
        )
    project_id = payload["project_id"]
    if not isinstance(project_id, str):
        raise HTTPException(status_code=400, detail="project ID must be a string")
    data_root = resolve_data_root().resolve()
    try:
        trusted_registration_path = registration_path(data_root, project_id)
    except PolicyViolationError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    registration = _registered_project(project_id)
    report = run_prerequisite_diagnosis(
        project_manifest=Path(registration.checkout) / ".daidala" / "project.yaml",
        registration=trusted_registration_path,
        live=payload["live"],
    )
    return {"report": report.to_dict(), "exit_code": report.exit_code}


def _project_link_store() -> GitHubProjectLinksStore:
    return GitHubProjectLinksStore(resolve_data_root().resolve())


def _checkout_manager() -> CheckoutManager:
    return CheckoutManager(resolve_data_root().resolve())


@router.get("/configuration")
def configuration() -> dict[str, Any]:
    """Return one read-only persisted-configuration verification snapshot."""

    try:
        return DashboardBackend(service_factory=service_factory).configuration()
    except DashboardBackendError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/artifacts")
def artifacts(workflow_id: str | None = None) -> dict[str, object]:
    """Return path-free artifact metadata for all or one exact workflow."""
    try:
        return DashboardBackend(service_factory=service_factory).artifacts(workflow_id)
    except StoreError as error:
        raise HTTPException(status_code=404, detail="Workflow unavailable") from error
    except ArtifactAccessError as error:
        _raise_artifact_error(error)


@router.post("/setup-analysis")
def setup_analysis(payload: dict[str, object]) -> dict[str, object]:
    """Generate one explicit, bounded, advisory-only readiness analysis."""

    if payload:
        raise HTTPException(status_code=400, detail="setup analysis does not accept browser data")
    backend = DashboardBackend(service_factory=service_factory)
    try:
        pack_service = pack_service_factory()
        packs = {
            "packs": [
                pack_service.check(name).to_dict() for name in pack_service.bundled_names()
            ]
        }
        snapshot = build_setup_analysis_snapshot(
            {**backend.configuration(), "dispatcher": _dispatcher_readiness()},
            backend.list_workflows(),
            backend.artifacts(),
            packs,
        )
    except (
        DashboardBackendError,
        StoreError,
        ArtifactAccessError,
        PackError,
        PackServiceError,
    ) as error:
        raise HTTPException(status_code=409, detail="Setup readiness is unavailable") from error
    try:
        return request_setup_analysis(snapshot)
    except SetupAnalysisUnavailable as error:
        raise HTTPException(status_code=503, detail="Host-model advice is unavailable") from error
    except SetupAnalysisError as error:
        raise HTTPException(
            status_code=502, detail="Host-model advice could not be generated"
        ) from error


@router.get("/artifacts/{workflow_id}/{artifact_id}/text")
def artifact_text(workflow_id: str, artifact_id: str) -> dict[str, object]:
    """Return one verified bounded literal-text projection."""
    try:
        return DashboardBackend(service_factory=service_factory).artifact_text(
            workflow_id, artifact_id
        )
    except StoreError as error:
        raise HTTPException(status_code=404, detail="Workflow unavailable") from error
    except ArtifactAccessError as error:
        _raise_artifact_error(error)


@router.get("/artifacts/{workflow_id}/{artifact_id}/download")
def artifact_download(workflow_id: str, artifact_id: str) -> Response:
    """Return verified bytes through the authenticated plugin transport."""
    try:
        download = DashboardBackend(service_factory=service_factory).artifact_download(
            workflow_id, artifact_id
        )
    except StoreError as error:
        raise HTTPException(status_code=404, detail="Workflow unavailable") from error
    except ArtifactAccessError as error:
        _raise_artifact_error(error)
    opaque_id = download.entry.artifact_id
    return Response(
        content=download.content,
        media_type="application/octet-stream",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'attachment; filename="artifact-{opaque_id}.bin"',
            "X-Content-Type-Options": "nosniff",
            "X-Daidala-Artifact-SHA256": download.entry.digest,
        },
    )


@router.get("/artifact-curator")
def artifact_curator_status() -> dict[str, object]:
    """Return curator policy, state counts, pins, and transition times."""
    try:
        return DashboardBackend(service_factory=service_factory).curator_status()
    except (CuratorError, StoreError) as error:
        raise HTTPException(status_code=409, detail="Curator status unavailable") from error


@router.post("/artifact-curator/{workflow_id}/preview")
def artifact_curator_preview(
    workflow_id: str, payload: dict[str, object]
) -> dict[str, object]:
    """Preview one closed curator operation without mutation."""
    operation, archive_id, _ = _curator_request(payload, apply=False)
    try:
        return DashboardBackend(service_factory=service_factory).curator_preview(
            workflow_id, operation, archive_id
        )
    except StoreError as error:
        raise HTTPException(status_code=404, detail="Workflow unavailable") from error
    except CuratorError as error:
        raise HTTPException(status_code=409, detail="Curator preview unavailable") from error


@router.post("/artifact-curator/{workflow_id}")
def artifact_curator_apply(
    workflow_id: str, payload: dict[str, object]
) -> dict[str, object]:
    """Apply one exact preview-confirmed curator operation."""
    operation, archive_id, preview_digest = _curator_request(payload, apply=True)
    assert preview_digest is not None
    try:
        return DashboardBackend(service_factory=service_factory).curator_apply(
            workflow_id, operation, preview_digest, archive_id
        )
    except StoreError as error:
        raise HTTPException(status_code=404, detail="Workflow unavailable") from error
    except CuratorError as error:
        raise HTTPException(status_code=409, detail="Curator operation unavailable") from error


def _link_preview_digest(link: GitHubProjectLink, store_digest: str) -> str:
    content = json.dumps(
        {"link": link.to_dict(), "store_digest": store_digest},
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@router.get("/registrations")
def registrations() -> dict[str, Any]:
    """Return the safe, registration-derived selector projection only."""

    rows = _current_registrations()
    root = CheckoutRootStore(resolve_data_root().resolve()).read().root
    return {
        "registrations": [
            {
                "project_id": row.project_id,
                "controller_profile": row.controller_profile,
                "board": row.board,
                "repository_canonical": row.repository_canonical,
                "verified_remote": row.verified_remote,
                "notification_adapter": row.notification_adapter,
                "notification_target": row.notification_target,
                "evaluator_backend": row.evaluator_backend,
                "evaluator_network": row.evaluator_network,
                "checkout_match": row.checkout == str(root / row.project_id),
            }
            for row in rows
        ]
    }


@router.get("/repository-registration/profiles")
def repository_registration_profiles() -> dict[str, object]:
    """List safe existing profile names and the dashboard-profile default."""

    try:
        selected_profile = active_profile(
            _run_command, fallback_name=resolve_data_root().name
        )
        return {
            "selected_profile": selected_profile,
            "profiles": list_profiles(_run_command),
        }
    except SetupWizardError as error:
        raise HTTPException(
            status_code=502, detail="Hermes profile inventory is unavailable"
        ) from error


def _repository_registration_rows(controller_profile: str) -> list[dict[str, str]]:
    """Project path-free registration identities for one Hermes-validated profile."""

    root = _repository_registration_profile_root(controller_profile)
    try:
        rows = list_controller_registrations(root)
    except ValueError as error:
        raise HTTPException(status_code=409, detail="registered projects are invalid") from error
    return [
        {
            "project_id": row.project_id,
            "repository_canonical": row.repository_canonical,
        }
        for row in rows
    ]


_WIZARD_INELIGIBILITY = {
    "duplicate-repository": (
        "This GitHub repository is registered twice on the same profile.",
        "One profile cannot register the same repository twice.",
    ),
    "in-use": (
        "Two GitHub repositories share this Hermes board.",
        "Never. Each GitHub repository needs its own board.",
    ),
    "missing": (
        "The stored board is missing or archived.",
        "Restore the board in Hermes or register the repository again.",
    ),
    "workdir-mismatch": (
        "The board workdir does not match the registered checkout.",
        "Fix the board default workdir or register the repository again.",
    ),
}


def _registration_board_status(
    registration: ControllerRegistration,
    *,
    board: dict[str, Any] | None,
    board_count: int,
) -> str:
    """Return the path-free board bind state used by Config and Start."""
    if board is None or board.get("archived") is True:
        return "missing"
    if board_count != 1:
        return "in-use"
    if board.get("default_workdir") != registration.checkout:
        return "workdir-mismatch"
    return "bound"


def _registered_project_rows(
    registrations: tuple[ControllerRegistration, ...],
    *,
    boards: list[dict[str, Any]],
    board_counts: dict[str, int],
    linked_project_ids: set[str],
) -> list[dict[str, str]]:
    """Project Config workspace state without exposing local paths."""

    boards_by_slug = {
        row.get("slug"): row for row in boards if isinstance(row.get("slug"), str)
    }
    result: list[dict[str, str]] = []
    for registration in registrations:
        board = boards_by_slug.get(registration.board)
        board_status = _registration_board_status(
            registration,
            board=board if isinstance(board, dict) else None,
            board_count=board_counts.get(registration.board, 0),
        )
        result.append(
            {
                "project_id": registration.project_id,
                "repository_canonical": registration.repository_canonical,
                "board": registration.board,
                "board_status": board_status,
                "github_project_status": (
                    "linked" if registration.project_id in linked_project_ids else "not-linked"
                ),
            }
        )
    return result


@router.get("/repository-registration/registrations")
def repository_registrations(controller_profile: str) -> dict[str, object]:
    """Project only selected-profile repository identity facts for Config."""

    return {
        "controller_profile": controller_profile,
        "registrations": _repository_registration_rows(controller_profile),
    }


@router.get("/repository-registration/inventory")
def repository_registration_inventory() -> dict[str, object]:
    """Project every Hermes-validated profile and its path-free registrations."""

    try:
        selected_profile = active_profile(
            _run_command, fallback_name=resolve_data_root().name
        )
        names = list_profiles(_run_command)
    except SetupWizardError as error:
        raise HTTPException(
            status_code=502, detail="Hermes profile inventory is unavailable"
        ) from error

    try:
        boards = list_boards(_run_command)
    except SetupWizardError as error:
        raise HTTPException(
            status_code=502, detail="Hermes board inventory is unavailable"
        ) from error

    resolved: list[tuple[str, Path, tuple[ControllerRegistration, ...]]] = []
    profiles: list[dict[str, object]] = []
    for controller_profile in names:
        try:
            root = _repository_registration_profile_root(controller_profile)
            resolved.append((controller_profile, root, list_controller_registrations(root)))
        except (HTTPException, ValueError):
            profiles.append(
                {
                    "controller_profile": controller_profile,
                    "status": "unavailable",
                    "registrations": [],
                }
            )
    board_counts: dict[str, int] = {}
    for _profile, _root, registrations in resolved:
        for registration in registrations:
            board_counts[registration.board] = board_counts.get(registration.board, 0) + 1
    for controller_profile, root, registrations in resolved:
        try:
            links = GitHubProjectLinksStore(root).read(registrations)
            rows = _registered_project_rows(
                registrations,
                boards=boards,
                board_counts=board_counts,
                linked_project_ids={link.project_id for link in links},
            )
        except GitHubProjectLinkError:
            profiles.append(
                {
                    "controller_profile": controller_profile,
                    "status": "unavailable",
                    "registrations": [],
                }
            )
            continue
        profiles.append(
            {
                "controller_profile": controller_profile,
                "status": "ready",
                "registrations": rows,
            }
        )
    return {"selected_profile": selected_profile, "profiles": profiles}


def _repository_registration_request(
    payload: dict[str, object], *, apply: bool, include_board: bool = False
) -> tuple[str, str, str | None, str | None]:
    fields = {"github_url", "controller_profile"}
    if include_board:
        fields.add("board")
    if apply:
        fields |= {"preview_digest", "confirm"}
    if set(payload) != fields or (apply and payload.get("confirm") is not True):
        raise HTTPException(
            status_code=400, detail="exact repository registration fields are required"
        )
    github_url = payload.get("github_url")
    controller_profile = payload.get("controller_profile")
    if not isinstance(github_url, str) or not isinstance(controller_profile, str):
        raise HTTPException(
            status_code=400,
            detail="GitHub repository link and controller profile are required",
        )
    digest = payload.get("preview_digest")
    if digest is not None and not _is_sha256(digest):
        raise HTTPException(status_code=400, detail="preview_digest must be a SHA-256 identity")
    board = payload.get("board")
    if include_board and board is not None and not isinstance(board, str):
        raise HTTPException(status_code=400, detail="board must be text or null")
    return (
        github_url,
        controller_profile,
        digest if isinstance(digest, str) else None,
        board if isinstance(board, str) else None,
    )


@router.post("/repository-registration/preview")
def repository_registration_preview(payload: dict[str, object]) -> dict[str, object]:
    """Inspect one GitHub repository without creating profile-local records."""

    github_url, controller_profile, _, board = _repository_registration_request(
        payload, apply=False, include_board=True
    )
    return _repository_registration_service(controller_profile).classify(
        github_url, board=board
    ).to_dict()


@router.post("/repository-registration/bootstrap/preview")
def repository_bootstrap_preview(payload: dict[str, object]) -> dict[str, object]:
    """Preview conservative Daidala policy on a non-default branch without writing."""

    github_url, controller_profile, _, _ = _repository_registration_request(payload, apply=False)
    try:
        return _repository_bootstrap_service(controller_profile).preview(github_url).to_dict()
    except (RepositoryBootstrapError, RepositoryRegistrationError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/repository-registration/bootstrap")
def repository_bootstrap_apply(payload: dict[str, object]) -> dict[str, object]:
    """Publish conservative Daidala policy on a non-default branch after confirmation."""

    github_url, controller_profile, digest, _ = _repository_registration_request(
        payload, apply=True
    )
    assert digest is not None
    try:
        return _repository_bootstrap_service(controller_profile).apply(
            github_url,
            expected_preview_digest=digest,
            confirmation="bootstrap-repository",
        ).to_dict()
    except (RepositoryBootstrapError, RepositoryRegistrationError) as error:
        raise HTTPException(
            status_code=409, detail="repository bootstrap could not be applied"
        ) from error


@router.post("/repository-registration")
def repository_registration_apply(payload: dict[str, object]) -> dict[str, object]:
    """Create only the fresh preview-confirmed profile-local registration records."""

    github_url, controller_profile, digest, board = _repository_registration_request(
        payload, apply=True, include_board=True
    )
    assert digest is not None
    try:
        return _repository_registration_service(controller_profile).apply(
            github_url,
            board=board,
            expected_preview_digest=digest,
            confirmation="register-repository",
        ).to_dict()
    except RepositoryRegistrationError as error:
        raise HTTPException(
            status_code=409, detail="repository registration could not be applied"
        ) from error


@router.get("/github-project-links")
def github_project_links() -> dict[str, Any]:
    """List the active profile's local GitHub Projects v2 links."""

    rows = _current_registrations()
    try:
        links = _project_link_store().read(rows)
    except GitHubProjectLinkError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"links": [link.to_dict() for link in links]}


@router.get("/github-project-links/{project_id}")
def github_project_link(project_id: str) -> dict[str, Any]:
    """Read one local link and its delete compare-and-swap identity."""

    _registered_project(project_id)
    rows = _current_registrations()
    store = _project_link_store()
    try:
        link = next((row for row in store.read(rows) if row.project_id == project_id), None)
        if link is None:
            raise HTTPException(status_code=404, detail="GitHub Project link is not configured")
        return {
            "link": link.to_dict(),
            "delete_preview_digest": _link_preview_digest(link, store.digest(rows)),
        }
    except GitHubProjectLinkError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


def _preview_link(payload: dict[str, Any]) -> tuple[GitHubProjectLink, dict[str, str], str]:
    if set(payload) != {"project_id", "owner", "project_number"}:
        raise HTTPException(
            status_code=400, detail="exact GitHub Project preview fields are required"
        )
    project_id = payload["project_id"]
    owner = payload["owner"]
    number = payload["project_number"]
    if not isinstance(project_id, str) or not isinstance(owner, str) or isinstance(number, bool):
        raise HTTPException(status_code=400, detail="GitHub Project preview fields are invalid")
    registration = _registered_project(project_id)
    try:
        link, project = github_project_verifier_factory().verify(
            registration=registration,
            registration_file=registration_path(resolve_data_root().resolve(), project_id),
            owner=owner,
            project_number=number,
        )
        digest = _link_preview_digest(
            link, _project_link_store().digest(_current_registrations())
        )
    except (GitHubProjectLinkError, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return link, project, digest


@router.post("/github-project-links/preview")
def github_project_link_preview(payload: dict[str, Any]) -> dict[str, Any]:
    """Resolve one bounded live Project read without mutating local state."""

    link, project, digest = _preview_link(payload)
    return {"link": link.to_dict(), "project": project, "preview_digest": digest}


@router.post("/github-project-links/{project_id}/verify")
def github_project_link_verify(project_id: str) -> dict[str, Any]:
    """Verify a persisted row and retain no credential or raw command output."""

    try:
        links = _project_link_store().read(_current_registrations())
        link = next(row for row in links if row.project_id == project_id)
    except StopIteration:
        raise HTTPException(
            status_code=404, detail="GitHub Project link is not configured"
        ) from None
    except GitHubProjectLinkError as error:
        return {"healthy": False, "reason": str(error)}
    try:
        verified, project = github_project_verifier_factory().verify(
            registration=_registered_project(project_id),
            registration_file=registration_path(resolve_data_root().resolve(), project_id),
            owner=link.owner,
            project_number=link.project_number,
        )
    except (GitHubProjectLinkError, ValueError) as error:
        return {"healthy": False, "reason": str(error)}
    return {"healthy": verified == link, "link": verified.to_dict(), "project": project}


@router.put("/github-project-links/{project_id}")
def github_project_link_upsert(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Replace one link only after a fresh matching live preview."""

    if set(payload) != {"owner", "project_number", "preview_digest", "confirm"}:
        raise HTTPException(
            status_code=400, detail="exact GitHub Project apply fields are required"
        )
    if payload["confirm"] is not True:
        raise HTTPException(status_code=400, detail="explicit confirmation is required")
    link, project, digest = _preview_link(
        {
            "project_id": project_id,
            "owner": payload["owner"],
            "project_number": payload["project_number"],
        }
    )
    if payload["preview_digest"] != digest:
        raise HTTPException(status_code=409, detail="GitHub Project preview changed after review")
    rows = _current_registrations()
    store = _project_link_store()
    try:
        current = tuple(row for row in store.read(rows) if row.project_id != project_id)
        updated = tuple(sorted((*current, link), key=lambda row: row.project_id))
        changed = store.replace(updated, rows)
    except GitHubProjectLinkError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"changed": changed, "link": link.to_dict(), "project": project}


@router.delete("/github-project-links/{project_id}")
def github_project_link_delete(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Remove one local link with a row-and-store-bound confirmation digest."""

    if set(payload) != {"delete_preview_digest", "confirm"} or payload["confirm"] is not True:
        raise HTTPException(status_code=400, detail="exact confirmed deletion fields are required")
    rows = _current_registrations()
    store = _project_link_store()
    try:
        links = store.read(rows)
        link = next(row for row in links if row.project_id == project_id)
    except StopIteration:
        raise HTTPException(
            status_code=404, detail="GitHub Project link is not configured"
        ) from None
    except GitHubProjectLinkError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if payload["delete_preview_digest"] != _link_preview_digest(link, store.digest(rows)):
        raise HTTPException(status_code=409, detail="GitHub Project link changed after review")
    try:
        changed = store.replace(tuple(row for row in links if row != link), rows)
    except GitHubProjectLinkError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"changed": changed, "project_id": project_id}


def _checkout_root_preview(root: object) -> dict[str, Any]:
    if not isinstance(root, str):
        raise HTTPException(status_code=400, detail="checkout root must be a string")
    rows = _current_registrations()
    store = CheckoutRootStore(resolve_data_root().resolve())
    current = store.read()
    try:
        proposed = CheckoutConfig(root=Path(root), mode=current.mode, ttl_hours=current.ttl_hours)
        mismatches = store.mismatching_project_ids(proposed, rows)
        owned = [str(path) for path in discover_owned_checkouts(current.root, rows)]
    except CheckoutRootError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    identity = json.dumps(
        {
            "old": current.to_dict(),
            "new": proposed.to_dict(),
            "owned": owned,
            "mismatches": mismatches,
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    return {
        "old": current.to_dict()["checkouts"],
        "new": proposed.to_dict()["checkouts"],
        "owned_paths": owned,
        "mismatching_project_ids": list(mismatches),
        "blocked": bool(mismatches or (current.root != proposed.root and owned)),
        "preview_digest": hashlib.sha256(identity.encode("utf-8")).hexdigest(),
    }


@router.get("/checkout-root")
def checkout_root() -> dict[str, Any]:
    """Read the full persisted root/policy record and any registration mismatch."""

    store = CheckoutRootStore(resolve_data_root().resolve())
    config = store.read()
    return {
        "checkouts": config.to_dict()["checkouts"],
        "mismatching_project_ids": list(
            store.mismatching_project_ids(config, _current_registrations())
        ),
    }


@router.post("/checkout-root/preview")
def checkout_root_preview(payload: dict[str, Any]) -> dict[str, Any]:
    if set(payload) != {"root"}:
        raise HTTPException(status_code=400, detail="checkout root preview requires only root")
    return _checkout_root_preview(payload["root"])


@router.put("/checkout-root")
def checkout_root_replace(payload: dict[str, Any]) -> dict[str, Any]:
    if set(payload) != {"root", "preview_digest", "confirm"} or payload["confirm"] is not True:
        raise HTTPException(
            status_code=400, detail="exact confirmed checkout root fields are required"
        )
    preview = _checkout_root_preview(payload["root"])
    if payload["preview_digest"] != preview["preview_digest"] or preview["blocked"]:
        raise HTTPException(status_code=409, detail="checkout root preview changed or is blocked")
    store = CheckoutRootStore(resolve_data_root().resolve())
    current = store.read()
    try:
        changed = store.write(
            CheckoutConfig(
                root=Path(payload["root"]), mode=current.mode, ttl_hours=current.ttl_hours
            ),
            _current_registrations(),
        )
    except CheckoutRootError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"changed": changed, "checkouts": store.read().to_dict()["checkouts"]}


@router.get("/checkouts")
def checkouts_status() -> dict[str, Any]:
    """Return only server-derived checkout state and policy projections."""

    try:
        manager = _checkout_manager()
        return {
            "policy": manager.policy().to_dict(),
            "checkouts": [row.to_dict() for row in manager.statuses(_current_registrations())],
            "backups": list(manager.backups()),
        }
    except CheckoutError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/checkouts/{project_id}/refresh/preview")
def checkout_refresh_preview(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if payload:
        raise HTTPException(status_code=400, detail="checkout refresh preview accepts no fields")
    try:
        return _checkout_manager().preview_refresh(_registered_project(project_id))
    except CheckoutError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/checkouts/{project_id}/adopt/preview")
def checkout_adopt_preview(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if payload:
        raise HTTPException(status_code=400, detail="checkout adoption preview accepts no fields")
    try:
        return _checkout_manager().preview_adopt(_registered_project(project_id))
    except CheckoutError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/checkouts/{project_id}/adopt")
def checkout_adopt_apply(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if set(payload) != {"preview_digest", "confirm"}:
        raise HTTPException(status_code=400, detail="exact checkout adoption fields are required")
    try:
        return _checkout_manager().apply_adopt(
            _registered_project(project_id),
            preview_digest=payload["preview_digest"],
            confirm=payload["confirm"],
        )
    except CheckoutError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/checkouts/{project_id}/refresh")
def checkout_refresh_apply(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if set(payload) != {"preview_digest", "confirm"}:
        raise HTTPException(status_code=400, detail="exact checkout refresh fields are required")
    try:
        return _checkout_manager().apply_refresh(
            _registered_project(project_id),
            preview_digest=payload["preview_digest"],
            confirm=payload["confirm"],
        )
    except CheckoutError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/checkouts/_backups/prune/preview")
def checkout_backups_prune_preview(payload: dict[str, Any]) -> dict[str, Any]:
    if set(payload) != {"filenames"}:
        raise HTTPException(status_code=400, detail="checkout backup prune fields are invalid")
    try:
        return _checkout_manager().preview_backup_prune(payload["filenames"])
    except CheckoutError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/checkouts/_backups/prune")
def checkout_backups_prune_apply(payload: dict[str, Any]) -> dict[str, Any]:
    if set(payload) != {"filenames", "preview_digest", "confirm"}:
        raise HTTPException(
            status_code=400, detail="exact checkout backup prune fields are required"
        )
    try:
        return _checkout_manager().apply_backup_prune(
            filenames=payload["filenames"],
            preview_digest=payload["preview_digest"],
            confirm=payload["confirm"],
        )
    except CheckoutError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/checkouts/policy/preview")
def checkouts_policy_preview(payload: dict[str, Any]) -> dict[str, Any]:
    if set(payload) != {"mode", "ttl_hours"}:
        raise HTTPException(status_code=400, detail="checkout policy preview fields are invalid")
    try:
        return _checkout_manager().preview_policy(
            mode=payload["mode"], ttl_hours=payload["ttl_hours"]
        )
    except CheckoutError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.put("/checkouts/policy")
def checkouts_policy_apply(payload: dict[str, Any]) -> dict[str, Any]:
    if set(payload) != {"mode", "ttl_hours", "preview_digest", "confirm"}:
        raise HTTPException(
            status_code=400, detail="exact checkout policy apply fields are required"
        )
    try:
        return _checkout_manager().apply_policy(
            mode=payload["mode"],
            ttl_hours=payload["ttl_hours"],
            preview_digest=payload["preview_digest"],
            confirm=payload["confirm"],
        )
    except CheckoutError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


def _pack_skill_action_request(
    payload: dict[str, Any], *, apply: bool
) -> tuple[SkillAction, str | None]:
    required = {"action", "preview_digest", "confirm"} if apply else {"action"}
    allowed = required | {"skill"}
    if not required.issubset(payload) or not set(payload).issubset(allowed):
        raise HTTPException(status_code=400, detail="exact pack skill action fields are required")
    if apply and payload.get("confirm") is not True:
        raise HTTPException(status_code=400, detail="explicit confirmation is required")
    if apply and not _is_sha256(payload.get("preview_digest")):
        raise HTTPException(status_code=400, detail="valid preview_digest is required")
    try:
        action = SkillAction(payload.get("action"))
    except (TypeError, ValueError) as error:
        raise HTTPException(
            status_code=400, detail="action must be install, enable, or disable"
        ) from error
    if action is SkillAction.INSTALL:
        raise HTTPException(
            status_code=400,
            detail="skill installation is pack-wide; use the pack install preview",
        )
    skill_name = payload.get("skill")
    if skill_name is not None and (
        not isinstance(skill_name, str) or not skill_name.strip()
    ):
        raise HTTPException(status_code=400, detail="skill must be a non-empty string")
    return action, skill_name.strip() if skill_name is not None else None


@router.get("/packs")
def packs() -> dict[str, Any]:
    """List bundled catalogs with lifecycle bindings and safe profile identity."""

    service = pack_service_factory()
    return {
        "profile": _dashboard_identity()["profile"],
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


def _pack_install_request(payload: dict[str, Any]) -> str:
    if payload.get("confirm") is not True:
        raise HTTPException(status_code=400, detail="explicit confirmation is required")
    preview_digest = payload.get("preview_digest")
    if not isinstance(preview_digest, str) or not preview_digest.strip():
        raise HTTPException(status_code=400, detail="preview_digest is required")
    return preview_digest.strip()


@router.post("/packs/{pack_name}/install")
def pack_install(pack_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Apply only the exact reviewed preview after literal confirmation."""

    preview_digest = _pack_install_request(payload)
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
    except PackInstallError as error:
        raise HTTPException(status_code=409, detail=error.to_dict()) from error
    except (PackError, PackServiceError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


def _pack_install_line(payload: dict[str, object]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"


def _pack_install_failure(error: PackInstallError) -> dict[str, object]:
    failure = error.to_dict()
    receipt = failure.get("receipt")
    if isinstance(receipt, dict):
        failure["receipt"] = {key: value for key, value in receipt.items() if key != "executed"}
    return failure


def _pack_install_stream(
    service: PackService,
    pack_name: str,
    preview_digest: str,
) -> Iterator[str]:
    try:
        events: Iterator[PackInstallEvent] = service.install_events(
            pack_name,
            expected_preview_digest=preview_digest,
            confirm=True,
        )
        for event in events:
            if event.event == "progress":
                yield _pack_install_line(
                    {
                        "event": "progress",
                        "position": event.position,
                        "total": event.total,
                        "skill": event.skill,
                    }
                )
                continue
            if event.event != "complete" or event.result is None:
                raise PackServiceError("pack installation emitted an invalid terminal event")
            yield _pack_install_line(
                {
                    "event": "complete",
                    "result": {
                        "success": True,
                        "applied_preview_digest": event.result.applied_preview_digest,
                        "pack": event.result.pack.to_dict(),
                    },
                }
            )
    except PackInstallError as error:
        yield _pack_install_line({"event": "error", "error": _pack_install_failure(error)})
    except StalePackPreviewError as error:
        yield _pack_install_line(
            {
                "event": "error",
                "error": {"code": "stale_preview", "message": str(error)},
            }
        )
    except PackConfirmationError as error:
        yield _pack_install_line(
            {
                "event": "error",
                "error": {"code": "confirmation_required", "message": str(error)},
            }
        )
    except (PackError, PackServiceError) as error:
        yield _pack_install_line(
            {
                "event": "error",
                "error": {"code": "pack_install_unavailable", "message": str(error)},
            }
        )


@router.post("/packs/{pack_name}/install/stream")
def pack_install_stream(pack_name: str, payload: dict[str, Any]) -> StreamingResponse:
    """Apply one pack action while streaming bounded per-skill progress."""

    preview_digest = _pack_install_request(payload)
    return StreamingResponse(
        _pack_install_stream(pack_service_factory(), pack_name, preview_digest),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/packs/{pack_name}/skills/action/preview")
def pack_skill_action_preview(
    pack_name: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Preview one individual or pack-wide install/enable/disable action."""

    action, skill_name = _pack_skill_action_request(payload, apply=False)
    try:
        return pack_service_factory().preview_action(
            pack_name, action, skill_name=skill_name
        ).to_dict()
    except UnknownPackSkillError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (PackActionError, PackError, PackServiceError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/packs/{pack_name}/skills/action")
def pack_skill_action_apply(
    pack_name: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Apply one exact freshly previewed pack skill action."""

    action, skill_name = _pack_skill_action_request(payload, apply=True)
    try:
        return pack_service_factory().apply_action(
            pack_name,
            action,
            skill_name=skill_name,
            expected_preview_digest=payload["preview_digest"],
            confirm=True,
        ).to_dict()
    except PackConfirmationError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except UnknownPackSkillError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except StalePackPreviewError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except (PackActionError, PackError, PackServiceError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/workflows")
def workflows() -> dict[str, Any]:
    """List every workflow ledger known to the active profile."""

    backend = DashboardBackend(service_factory=service_factory)
    return backend.list_workflows()


@router.get("/workflows/{workflow_id}")
def workflow_detail(workflow_id: str) -> dict[str, Any]:
    """Return policy facts and a live, read-only Kanban snapshot."""

    backend = DashboardBackend(
        service_factory=service_factory,
        card_detail_provider=card_detail_provider,
    )
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


@router.get("/workflows/{workflow_id}/approval-review")
def approval_review(workflow_id: str) -> dict[str, Any]:
    """Return server-resolved, verified evidence for the current plan only."""

    backend = DashboardBackend(service_factory=service_factory)
    try:
        return backend.approval_review(workflow_id)
    except UnknownWorkflowError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ArtifactAccessError as error:
        raise HTTPException(
            status_code=409,
            detail={"message": "Plan unavailable", "reason": error.reason.value},
        ) from error


@router.post("/workflows/{workflow_id}/approve")
def workflow_approve(workflow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Approve only the exact current plan evidence reviewed by the operator."""

    expected_fields = {"artifact_id", "plan_digest", "summary_digest", "confirm"}
    if set(payload) != expected_fields:
        raise HTTPException(status_code=400, detail="exact approval fields are required")
    if payload.get("confirm") is not True:
        raise HTTPException(status_code=400, detail="explicit confirmation is required")
    for field in ("artifact_id", "plan_digest", "summary_digest"):
        if not _is_sha256(payload.get(field)):
            raise HTTPException(status_code=400, detail=f"{field} must be a SHA-256 identity")

    service = service_factory()
    try:
        evidence = service.current_plan_evidence(workflow_id).to_dict()
        current_identity = {
            "artifact_id": evidence["artifact_id"],
            "plan_digest": evidence["plan_digest"],
            "summary_digest": evidence["approval_summary_digest"],
            "confirm": True,
        }
        if payload != current_identity:
            raise HTTPException(
                status_code=409,
                detail="plan identity changed after review; refresh approval evidence",
            )
        service.approve(workflow_id, plan_digest=evidence["plan_digest"])
        return DashboardBackend(service_factory=lambda: service).approval_review(workflow_id)
    except HTTPException:
        raise
    except ArtifactAccessError as error:
        raise HTTPException(
            status_code=409,
            detail={"message": "Plan unavailable", "reason": error.reason.value},
        ) from error
    except (ServiceError, StoreError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/workflows/{workflow_id}/review-decision")
def review_decision(workflow_id: str) -> dict[str, Any]:
    """Return exact source-bound review evidence and attended decision state."""

    backend = DashboardBackend(service_factory=service_factory)
    try:
        return backend.review_decision(workflow_id)
    except UnknownWorkflowError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ArtifactAccessError as error:
        raise HTTPException(
            status_code=409,
            detail={"message": "Review evidence unavailable", "reason": error.reason.value},
        ) from error
    except WorkflowError as error:
        raise HTTPException(status_code=409, detail="Review evidence unavailable") from error


@router.post("/workflows/{workflow_id}/review-disposition/preview")
def review_disposition_preview(
    workflow_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Preview one exact attended review action without mutation."""

    action, rationale = _review_action_payload(
        payload,
        expected_fields={"action", "rationale"},
    )
    try:
        preview = service_factory().preview_review_decision(
            workflow_id,
            action=action,
            actor=_DASHBOARD_REVIEW_ACTOR,
            rationale=rationale,
        )
        return _browser_review_preview(preview.to_dict())
    except StoreError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except WorkflowError as error:
        raise HTTPException(
            status_code=409, detail="Review disposition preview unavailable"
        ) from error


@router.post("/workflows/{workflow_id}/review-disposition")
def review_disposition(workflow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Apply only the exact freshly previewed attended review action."""

    action, rationale = _review_action_payload(
        payload,
        expected_fields={
            "action",
            "review_digest",
            "preview_digest",
            "rationale",
            "confirm",
        },
    )
    if payload.get("confirm") is not True:
        raise HTTPException(status_code=400, detail="explicit review confirmation is required")
    for field in ("review_digest", "preview_digest"):
        if not _is_sha256(payload.get(field)):
            raise HTTPException(status_code=400, detail=f"{field} must be a SHA-256 identity")
    try:
        result = service_factory().apply_review_decision(
            workflow_id,
            action=action,
            actor=_DASHBOARD_REVIEW_ACTOR,
            rationale=rationale,
            expected_review_digest=payload["review_digest"],
            expected_preview_digest=payload["preview_digest"],
            confirm=True,
        )
    except StoreError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except WorkflowError as error:
        raise HTTPException(
            status_code=409, detail="Review disposition could not be applied"
        ) from error
    preview = result.get("preview")
    if isinstance(preview, dict):
        result = {**result, "preview": _browser_review_preview(preview)}
    return result


def _delivery_request(payload: dict[str, Any], *, apply: bool) -> str | None:
    expected = {"preview_digest", "confirm"} if apply else set()
    if set(payload) != expected:
        raise HTTPException(status_code=400, detail="exact delivery fields are required")
    if not apply:
        return None
    if payload.get("confirm") is not True:
        raise HTTPException(status_code=400, detail="explicit delivery confirmation is required")
    digest = payload.get("preview_digest")
    if not _is_sha256(digest):
        raise HTTPException(status_code=400, detail="preview_digest must be a SHA-256 identity")
    assert isinstance(digest, str)
    return digest


@router.post("/workflows/{workflow_id}/delivery/preview")
def delivery_preview(workflow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Return one path-free, credential-free branch-delivery preview."""

    _delivery_request(payload, apply=False)
    try:
        return _delivery_service().preview(workflow_id).to_dict()
    except StoreError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (DeliveryError, WorkflowError):
        raise HTTPException(status_code=409, detail="branch delivery preview unavailable") from None


@router.post("/workflows/{workflow_id}/delivery")
def delivery_apply(workflow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Commit and push only the exact confirmed reviewed branch preview."""

    preview_digest = _delivery_request(payload, apply=True)
    assert preview_digest is not None
    try:
        ledger = _delivery_service().apply(
            workflow_id,
            expected_preview_digest=preview_digest,
            confirm=True,
        )
    except StoreError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (DeliveryError, WorkflowError):
        raise HTTPException(
            status_code=409, detail="branch delivery could not be applied"
        ) from None
    authorization = ledger.delivery_authorization
    if authorization is None or authorization.commit is None:
        raise HTTPException(status_code=409, detail="branch delivery receipt unavailable")
    return {
        "workflow_id": ledger.workflow_id,
        "branch": authorization.branch,
        "commit": authorization.commit,
        "committed": ledger.committed,
        "pushed": ledger.pushed,
    }


@router.post("/workflows/{workflow_id}/cards/{card_id}/comment")
def workflow_card_comment(
    workflow_id: str, card_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Add one confirmed bounded remediation comment to a ledger-owned card."""

    comment = _confirmed_operator_text(payload, field="comment")
    board_slug = _workflow_card_board(workflow_id, card_id)
    try:
        kanban_comment(board_slug, card_id, comment)
    except DashboardBackendError as error:
        raise HTTPException(status_code=409, detail="Card comment could not be recorded") from error
    return {"commented": True, "card_id": card_id}


@router.post("/workflows/{workflow_id}/cards/{card_id}/unblock")
def workflow_card_unblock(
    workflow_id: str, card_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Unblock one confirmed workflow-owned card through the public CLI."""

    reason = _confirmed_operator_text(payload, field="reason")
    board_slug = _workflow_card_board(workflow_id, card_id)
    try:
        kanban_unblock(board_slug, card_id, reason)
    except DashboardBackendError as error:
        raise HTTPException(status_code=409, detail="Card could not be unblocked") from error
    return {"unblocked": True, "card_id": card_id}


@router.post("/workflows/{workflow_id}/cancel/preview")
def workflow_cancel_preview(workflow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Project the current cancellation impact without exposing a worktree path."""

    reason = _operator_text(payload, expected_fields={"reason"}, field="reason")
    try:
        return _cancellation_preview(service_factory(), workflow_id, reason)
    except StoreError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/workflows/{workflow_id}/cancel")
def workflow_cancel(workflow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Cancel only when the current canonical cancellation preview still matches."""

    reason = _operator_text(
        payload,
        expected_fields={"reason", "preview_digest", "confirm"},
        field="reason",
    )
    if payload.get("confirm") is not True:
        raise HTTPException(
            status_code=400, detail="explicit cancellation confirmation is required"
        )
    expected_digest = payload.get("preview_digest")
    if not _is_sha256(expected_digest):
        raise HTTPException(status_code=400, detail="preview_digest must be a SHA-256 identity")
    service = service_factory()
    try:
        preview = _cancellation_preview(service, workflow_id, reason)
    except StoreError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    if preview["preview_digest"] != expected_digest:
        raise HTTPException(status_code=409, detail="cancellation inputs changed after preview")
    try:
        service.cancel(workflow_id, reason)
    except (ServiceError, StoreError, WorkflowError) as error:
        raise HTTPException(
            status_code=409, detail="Workflow cancellation could not be applied"
        ) from error
    return {"cancelled": True, "workflow_id": workflow_id}


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


@router.get("/constraints/sources")
def constraint_sources() -> dict[str, Any]:
    """List only installed skills that validate as reusable policy sources."""

    return {"sources": _profile_policy_sources()}


@router.get("/constraints/sources/{name}")
def constraint_source_detail(name: str) -> dict[str, Any]:
    """Read one listed policy source without accepting paths or mutations."""

    registry = ProfileSkillContentRegistry(resolve_data_root() / "skills")
    sources = {source["name"]: source for source in _profile_policy_sources()}
    source = sources.get(name)
    if source is None:
        raise HTTPException(status_code=404, detail="unknown reusable policy source")
    try:
        detail = _policy_source_detail(registry, name)
    except (SkillRevisionError, WorkflowError) as error:
        raise HTTPException(status_code=409, detail="policy source is unavailable") from error
    if detail is None:
        return {
            "available": False,
            "source": source,
            "reason": "policy source document exceeds the 1 MiB response bound",
        }
    return {"available": True, **detail}


@router.get("/wizard/inventory")
def wizard_inventory() -> dict[str, Any]:
    """List the profile-safe identities eligible for setup selection."""
    try:
        controller_profile = active_profile(
            _run_command,
            fallback_name=resolve_data_root().name,
        )
        boards = list_boards(_run_command)
        selectable, ineligible = _wizard_repository_rows(_wizard_registrations(), boards)
        profiles = list_profiles(_run_command)
        return {
            "controller_profile": controller_profile,
            "boards": boards,
            "profiles": profiles,
            "worker_gateways": _worker_gateway_rows(profiles),
            "packs": ["addyosmani", "aidlc"],
            "policy_sources": _profile_policy_sources(),
            "projects": selectable,
            "ineligible_repositories": ineligible,
            "unregistered_boards": _unregistered_boards(),
            "checkouts_root": _mounted_checkouts_root(),
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


@router.get("/dispatcher-readiness")
def dispatcher_readiness() -> dict[str, Any]:
    """Report path-free worker-gateway liveness for current workflows."""

    return _dispatcher_readiness()


@router.post("/wizard/readiness")
def wizard_readiness(payload: dict[str, Any]) -> dict[str, Any]:
    """Return informative start checks. Failures do not block preview."""
    request, service = _resolved_setup_request(payload, apply=False)
    readiness = service.evaluate_start_readiness(**_preflight_kwargs(request))
    projection = {
        key: value
        for key, value in request.start_kwargs().items()
        if key != "target_repository"
    }
    return {
        "confirmed": False,
        "request": projection,
        "readiness": readiness,
        "ready": bool(readiness.get("ready")),
    }


@router.post("/wizard/preview")
def wizard_preview(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the safe request projection and exact fresh start digest."""
    request, service = _resolved_setup_request(payload, apply=False)
    try:
        preflight = service.validate_start_preflight(
            **_preflight_kwargs(request),
            enforce_start_blockers=False,
        )
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


@router.post("/wizard/local/preview")
def wizard_local_preview(payload: dict[str, Any]) -> dict[str, Any]:
    """Preview a new local workspace and its subsequent ordinary workflow start."""
    local_preview, request, _service = _local_setup_request(payload, apply=False)
    return _local_setup_preview(local_preview, request)


@router.post("/wizard/local/start")
def wizard_local_start(payload: dict[str, Any]) -> dict[str, Any]:
    """Initialize a fresh local workspace, then delegate to the standard start service."""
    local_preview, request, service = _local_setup_request(payload, apply=True)
    preview = _local_setup_preview(local_preview, request)
    if payload["preview_digest"] != preview["preview_digest"]:
        raise HTTPException(status_code=409, detail="local project inputs changed after preview")
    initializer = LocalProjectInitializer(resolve_data_root().resolve(), _run_command)
    try:
        initializer.apply(
            local_preview.project_id,
            local_preview.board_name,
            local_preview.digest,
        )
        service.validate_start_preflight(**_preflight_kwargs(request))
        ledger = service.start(**request.start_kwargs())
    except (ServiceError, MissingSkillsError, SetupWizardError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"workflow": ledger.to_dict(), "local_project": local_preview.to_dict()}


_SETUP_REQUEST_FIELDS = frozenset(
    {
        "goal",
        "pack",
        "workflow_id",
        "stage_profiles",
        "constraints_content",
        "constraints_skill",
        "constraints_skill_digest",
    }
)


def _local_setup_request(
    payload: dict[str, Any], *, apply: bool
) -> tuple[Any, SetupRequest, Any]:
    required_fields = {"project_id", "board_name", "request"}
    if apply:
        if payload.get("confirm") is not True:
            raise HTTPException(status_code=400, detail="explicit confirmation is required")
        digest = payload.get("preview_digest")
        if not isinstance(digest, str) or len(digest) != 64:
            raise HTTPException(status_code=400, detail="preview_digest is required")
        required_fields.update({"preview_digest", "confirm"})
    if set(payload) != required_fields:
        raise HTTPException(status_code=400, detail="unknown local-project wizard fields")
    request_payload = payload.get("request")
    if not isinstance(request_payload, dict) or set(request_payload) - _SETUP_REQUEST_FIELDS:
        raise HTTPException(status_code=400, detail="unknown setup request fields")
    initializer = LocalProjectInitializer(resolve_data_root().resolve(), _run_command)
    try:
        local_preview = initializer.preview(payload.get("project_id"), payload.get("board_name"))
        request = SetupRequest.from_payload(
            {
                **request_payload,
                "board_slug": local_preview.board_slug,
                "target_repository": local_preview.target_repository,
            }
        )
    except SetupWizardError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return local_preview, request, service_factory()


def _local_setup_preview(local_preview: Any, request: SetupRequest) -> dict[str, Any]:
    """Bind hidden derived paths into the digest without exposing them to the browser."""
    request_projection = {
        key: value for key, value in request.start_kwargs().items() if key != "target_repository"
    }
    return {
        "confirmed": False,
        "local_project": local_preview.to_dict(),
        "request": request_projection,
        "preview_digest": _digest(
            {
                "local_preview_digest": local_preview.digest,
                "request": request.start_kwargs(),
            }
        ),
    }


def _mounted_checkouts_root() -> str | None:
    """Return the mounted profile checkout root, or None when unset."""
    try:
        return str(CheckoutRootStore(resolve_data_root().resolve()).read().root)
    except CheckoutRootError:
        return None


def _wizard_registrations() -> tuple[ControllerRegistration, ...]:
    """Read every Hermes-validated profile's path-free workspace registrations."""
    rows: list[ControllerRegistration] = []
    try:
        profiles = list_profiles(_run_command)
    except SetupWizardError as error:
        raise SetupWizardError("registered repository inventory is unavailable") from error
    for profile in profiles:
        try:
            root = resolve_profile_root(profile, _run_command)
            for registration in list_controller_registrations(root):
                if registration.controller_profile == profile:
                    rows.append(registration)
        except (RepositoryRegistrationError, SetupWizardError, ValueError):
            continue
    return tuple(rows)


def _wizard_ineligibility(
    registration: ControllerRegistration,
    *,
    board: dict[str, Any] | None,
    board_count: int,
    repo_count: int,
) -> str | None:
    """Return a finite uniqueness/bind reason, or None when Start may select it."""
    if repo_count != 1:
        return "duplicate-repository"
    status = _registration_board_status(
        registration, board=board, board_count=board_count
    )
    return None if status == "bound" else status


def _wizard_repository_projection(registration: ControllerRegistration) -> dict[str, str]:
    return {
        "project_id": registration.project_id,
        "controller_profile": registration.controller_profile,
        "repository": registration.repository_canonical,
        "board": registration.board,
        "workdir": registration.checkout,
    }


def _wizard_repository_rows(
    registrations: tuple[ControllerRegistration, ...],
    boards: list[dict[str, Any]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Split registrations into selectable Start rows and explained ineligible rows."""
    boards_by_slug = {
        row.get("slug"): row for row in boards if isinstance(row.get("slug"), str)
    }
    board_counts: dict[str, int] = {}
    repo_counts: dict[tuple[str, str], int] = {}
    for registration in registrations:
        board_counts[registration.board] = board_counts.get(registration.board, 0) + 1
        repo_key = (registration.controller_profile, registration.repository_canonical)
        repo_counts[repo_key] = repo_counts.get(repo_key, 0) + 1
    selectable: list[dict[str, str]] = []
    ineligible: list[dict[str, str]] = []
    for registration in registrations:
        board = boards_by_slug.get(registration.board)
        reason = _wizard_ineligibility(
            registration,
            board=board if isinstance(board, dict) else None,
            board_count=board_counts.get(registration.board, 0),
            repo_count=repo_counts.get(
                (registration.controller_profile, registration.repository_canonical), 0
            ),
        )
        row = _wizard_repository_projection(registration)
        if reason is None:
            selectable.append(row)
            continue
        explanation = _WIZARD_INELIGIBILITY[reason]
        ineligible.append(
            {**row, "reason": reason, "detail": explanation[0], "conclusion": explanation[1]}
        )
    return selectable, ineligible


def _reject_ineligible_registration(registration: ControllerRegistration) -> None:
    """Refuse Start against a uniqueness or board-bind failure."""
    selectable, _ineligible = _wizard_repository_rows(
        _wizard_registrations(), list_boards(_run_command)
    )
    if any(
        row["project_id"] == registration.project_id
        and row["controller_profile"] == registration.controller_profile
        for row in selectable
    ):
        return
    raise SetupWizardError("registered repository is not selectable")


def _registration_for_start(
    controller_profile: object, project_id: object
) -> ControllerRegistration:
    """Resolve one registration after revalidating the named Hermes profile."""
    if not isinstance(controller_profile, str) or not controller_profile:
        raise SetupWizardError("controller_profile is required")
    if not isinstance(project_id, str) or not project_id:
        raise SetupWizardError("project_id is required")
    try:
        if controller_profile not in list_profiles(_run_command):
            raise SetupWizardError("unknown registered repository")
        root = resolve_profile_root(controller_profile, _run_command)
        registrations = list_controller_registrations(root)
    except (RepositoryRegistrationError, SetupWizardError, ValueError) as error:
        raise SetupWizardError("unknown registered repository") from error
    for registration in registrations:
        if (
            registration.project_id == project_id
            and registration.controller_profile == controller_profile
        ):
            return registration
    raise SetupWizardError("unknown registered repository")


def _all_registered_board_slugs() -> frozenset[str]:
    """Read every profile because board slugs are installation-global."""
    try:
        slugs: set[str] = set()
        for profile in list_profiles(_run_command):
            data_root = resolve_profile_root(profile, _run_command)
            slugs.update(row.board for row in list_controller_registrations(data_root))
        return frozenset(slugs)
    except (RepositoryRegistrationError, SetupWizardError, ValueError) as error:
        raise SetupWizardError("registered board inventory is unavailable") from error


def _unregistered_boards() -> list[dict[str, str]]:
    """Return only clean-git boards with a non-private browser projection."""
    registered = _all_registered_board_slugs()
    eligible: list[dict[str, str]] = []
    for board in list_boards(_run_command):
        slug = board.get("slug")
        workdir = board.get("default_workdir")
        if (
            not isinstance(slug, str)
            or slug in registered
            or board.get("archived") is True
            or not isinstance(workdir, str)
            or not workdir.startswith("/")
        ):
            continue
        worktree = Path(workdir)
        if worktree.is_symlink() or not worktree.is_dir() or str(worktree.resolve()) != workdir:
            continue
        code, top_level = _run_command(("git", "-C", workdir, "rev-parse", "--show-toplevel"))
        if code != 0 or top_level.strip() != workdir:
            continue
        code, status = _run_command(("git", "-C", workdir, "status", "--porcelain"))
        if code != 0 or status:
            continue
        name = board.get("name")
        eligible.append(
            {
                "slug": slug,
                "name": name if isinstance(name, str) else slug,
                "workdir": workdir,
            }
        )
    return eligible


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
    if not isinstance(selection, dict) or not isinstance(selection.get("mode"), str):
        raise HTTPException(status_code=400, detail="workspace selection mode is required")
    if not isinstance(request, dict) or set(request) - _SETUP_REQUEST_FIELDS:
        raise HTTPException(status_code=400, detail="unknown setup request fields")
    mode = selection["mode"]
    try:
        if mode == "registered" and set(selection) == {
            "mode",
            "project_id",
            "controller_profile",
        }:
            registration = _registration_for_start(
                selection.get("controller_profile"),
                selection.get("project_id"),
            )
            _reject_ineligible_registration(registration)
            resolved = SetupRequest.from_payload(
                {
                    **request,
                    "board_slug": registration.board,
                    "target_repository": registration.checkout,
                }
            )
        elif mode == "unregistered" and set(selection) == {"mode", "board_slug"}:
            board_slug = selection["board_slug"]
            if not isinstance(board_slug, str):
                raise SetupWizardError("board_slug is required")
            board = next((row for row in _unregistered_boards() if row["slug"] == board_slug), None)
            if board is None:
                raise SetupWizardError("selected unregistered board is unavailable")
            raw_boards = list_boards(_run_command)
            workdir = next(
                row.get("default_workdir")
                for row in raw_boards
                if row.get("slug") == board_slug
            )
            assert isinstance(workdir, str)
            resolved = SetupRequest.from_payload(
                {**request, "board_slug": board_slug, "target_repository": workdir}
            )
        else:
            raise SetupWizardError("workspace selection is invalid")
    except SetupWizardError as error:
        status = {
            "unknown registered repository": 404,
            "registered repository is not selectable": 409,
        }.get(str(error), 400)
        raise HTTPException(status_code=status, detail=str(error)) from error
    return resolved, service_factory()


def _worker_gateway_rows(profiles: list[str]) -> list[dict[str, str]]:
    """Probe named worker profiles without exposing host command output."""

    valid = _valid_worker_profiles(profiles)
    return [row.to_dict() for row in probe_profile_gateways(valid, _run_command)]


def _valid_worker_profiles(profiles: list[str]) -> list[str]:
    valid: list[str] = []
    for name in profiles:
        try:
            valid.append(validate_profile_name(name))
        except ValueError:
            continue
    return valid


def _dispatcher_readiness() -> dict[str, Any]:
    """Derive worker-gateway, Ready-card dispatch, and assignee readiness."""

    profiles: list[str] = []
    mismatches: list[dict[str, str]] = []
    ready_cards: list[dict[str, str]] = []
    try:
        service = service_factory()
        ledgers = service.store.list_all()
        for ledger in ledgers:
            try:
                cards = service.combined_status(ledger.workflow_id)
            except (KanbanError, ServiceError, StoreError):
                continue
            live = live_card_statuses(cards)
            if not live:
                continue
            profiles.extend(row.profile for row in ledger.stage_profiles)
            profiles.extend(row.assignee for row in live)
            mismatches.extend(assignee_stage_mismatches(ledger, live))
            ready_cards.extend(
                {
                    "workflow_id": ledger.workflow_id,
                    "task_id": row.task_id,
                    "stage": row.stage.value,
                    "profile": row.assignee,
                }
                for row in live
                if row.status == "ready"
            )
    except StoreError:
        profiles = []
        mismatches = []
        ready_cards = []
    if not profiles:
        try:
            profiles = [
                active_profile(_run_command, fallback_name=resolve_data_root().name)
            ]
        except SetupWizardError:
            profiles = []
    statuses = probe_profile_gateways(_valid_worker_profiles(profiles), _run_command)
    blocked = stopped_worker_gateways(statuses)
    gateway_statuses = {row.profile: row.status for row in statuses}
    gateway_blocked_cards = [
        {**card, "gateway_status": gateway_statuses[card["profile"]]}
        for card in ready_cards
        if gateway_statuses.get(card["profile"]) in {"stopped", "unavailable"}
    ]
    return {
        "gateways": [row.to_dict() for row in statuses],
        "ready": not blocked and not mismatches,
        "blocked_profiles": list(blocked),
        "assignee_mismatches": mismatches,
        "gateway_blocked_cards": gateway_blocked_cards,
    }


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
            {"id": "worker-gateway-running", "passed": True},
            {"id": "assignee-stage-aligned", "passed": True},
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
    """Return verified reusable sources only; unrelated skills stay private."""

    registry = ProfileSkillContentRegistry(resolve_data_root() / "skills")
    try:
        sources = []
        for name in sorted(registry.installed_names()):
            try:
                source = _policy_source_projection(registry, name)
            except (SkillRevisionError, WorkflowError):
                continue
            sources.append(source)
        return sources
    except SkillRevisionError as error:
        raise SetupWizardError("installed policy source inventory is invalid") from error


def _policy_source_detail(
    registry: ProfileSkillContentRegistry, name: str
) -> dict[str, object] | None:
    """Return a bounded literal document plus its canonical policy projection."""

    source = _policy_source_projection(registry, name)
    markdown = registry.skill_markdown(name)
    assert markdown is not None
    if len(markdown.encode("utf-8")) > MAX_SKILL_DOCUMENT_BYTES:
        return None
    content = extract_policy_skill_constraints(markdown)
    return {
        "source": source,
        "skill_markdown": markdown,
        "canonical_content": parse_workflow_constraints(content).canonical_bytes().decode(
            "utf-8"
        ),
    }


def _policy_source_projection(
    registry: ProfileSkillContentRegistry, name: str
) -> dict[str, str]:
    """Validate one exact installed source through the shared parser path."""

    digest = registry.content_digest(name)
    markdown = registry.skill_markdown(name)
    if digest is None or markdown is None:
        raise SkillRevisionError(f"policy source is unavailable: {name!r}")
    content = extract_policy_skill_constraints(markdown)
    parse_workflow_constraints(content)
    return {"name": name, "digest": digest}


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


def _review_action_payload(
    payload: dict[str, Any], *, expected_fields: set[str]
) -> tuple[str, str]:
    if set(payload) != expected_fields:
        raise HTTPException(status_code=400, detail="exact review decision fields are required")
    action = payload.get("action")
    try:
        selected = ReviewDispositionAction(action)
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=400, detail="invalid review disposition action") from error
    rationale = payload.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        raise HTTPException(status_code=400, detail="review rationale is required")
    normalized = rationale.strip()
    if "\x00" in normalized or len(normalized.encode("utf-8")) > MAX_REVIEW_FEEDBACK_BYTES:
        raise HTTPException(status_code=400, detail="review rationale exceeds its text bounds")
    return selected.value, normalized


def _browser_review_preview(preview: dict[str, Any]) -> dict[str, Any]:
    """Remove the profile-local worktree path while preserving preview identity."""
    result = dict(preview)
    worktree = result.pop("worktree_to_release", None)
    result["owned_worktree_release"] = worktree is not None
    return result


def _operator_text(
    payload: dict[str, Any], *, expected_fields: set[str], field: str
) -> str:
    if set(payload) != expected_fields:
        raise HTTPException(status_code=400, detail=f"exact {field} fields are required")
    value = payload.get(field)
    if not isinstance(value, str):
        raise HTTPException(status_code=400, detail=f"{field} is required")
    normalized = value.strip()
    if (
        not normalized
        or any(ord(character) < 32 or ord(character) == 127 for character in normalized)
        or len(normalized.encode("utf-8")) > 4000
    ):
        raise HTTPException(status_code=400, detail=f"{field} exceeds its text bounds")
    return normalized


def _confirmed_operator_text(payload: dict[str, Any], *, field: str) -> str:
    value = _operator_text(payload, expected_fields={field, "confirm"}, field=field)
    if payload.get("confirm") is not True:
        raise HTTPException(status_code=400, detail="explicit confirmation is required")
    return value


def _workflow_card_board(workflow_id: str, card_id: str) -> str:
    try:
        ledger = service_factory().status(workflow_id)
    except StoreError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    if not any(card.task_id == card_id for card in ledger.card_references):
        raise HTTPException(status_code=400, detail="card is not recorded for this workflow")
    return ledger.board_slug


def _cancellation_preview(service: Any, workflow_id: str, reason: str) -> dict[str, Any]:
    observed = service.store.get_with_token(workflow_id)
    ledger = observed.ledger
    cards = [
        {
            "task_id": card.task_id,
            "stage": getattr(card.stage, "value", card.stage),
        }
        for card in ledger.card_references
    ]
    projection = {
        "workflow_id": workflow_id,
        "ledger_token": observed.updated_at,
        "cards": cards,
        "owned_worktree_release": bool(ledger.worktree_owned and ledger.worktree_path),
        "reason": reason,
    }
    return {
        "workflow_id": workflow_id,
        "cards": cards,
        "owned_worktree_release": projection["owned_worktree_release"],
        "reason": reason,
        "preview_digest": _digest(projection),
    }


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _run_command(command: tuple[str, ...]) -> tuple[int, str]:
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    return completed.returncode, completed.stdout or completed.stderr


def _bounded_kanban_json(command: tuple[str, ...], label: str) -> Any:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired as error:
        raise DashboardBackendError(f"Kanban {label} timed out") from error
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    if len(stdout.encode("utf-8")) + len(stderr.encode("utf-8")) > 64 * 1024:
        raise DashboardBackendError(f"Kanban {label} exceeded the 64 KiB output limit")
    if completed.returncode != 0:
        raise DashboardBackendError(f"Kanban {label} is unavailable")
    try:
        return json.loads(stdout)
    except (TypeError, ValueError) as error:
        raise DashboardBackendError(f"Kanban {label} returned invalid JSON") from error


def _bounded_kanban_mutation(command: tuple[str, ...], label: str) -> None:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired as error:
        raise DashboardBackendError(f"Kanban {label} timed out") from error
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    if len(stdout.encode("utf-8")) + len(stderr.encode("utf-8")) > 64 * 1024:
        raise DashboardBackendError(f"Kanban {label} exceeded the 64 KiB output limit")
    if completed.returncode != 0:
        raise DashboardBackendError(f"Kanban {label} is unavailable")


def kanban_comment(board_slug: str, task_id: str, comment: str) -> None:
    _bounded_kanban_mutation(
        ("hermes", "kanban", "--board", board_slug, "comment", task_id, comment),
        "card comment",
    )


def kanban_unblock(board_slug: str, task_id: str, reason: str) -> None:
    _bounded_kanban_mutation(
        ("hermes", "kanban", "--board", board_slug, "unblock", task_id, "--reason", reason),
        "card unblock",
    )


def kanban_show(board_slug: str, task_id: str) -> dict[str, Any]:
    payload = _bounded_kanban_json(
        ("hermes", "kanban", "--board", board_slug, "show", task_id, "--json"),
        "card detail",
    )
    if not isinstance(payload, dict):
        raise DashboardBackendError("Kanban card detail has an invalid shape")
    return payload


def kanban_runs(board_slug: str, task_id: str) -> list[Any]:
    payload = _bounded_kanban_json(
        ("hermes", "kanban", "--board", board_slug, "runs", task_id, "--json"),
        "run history",
    )
    if not isinstance(payload, list):
        raise DashboardBackendError("Kanban run history has an invalid shape")
    return payload


def _bounded_text(value: Any, *, limit: int = 4000) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise DashboardBackendError("Kanban detail contains invalid text")
    return value[:limit]


def _bounded_timestamp(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if math.isfinite(value) else None


def _kanban_card_detail(board_slug: str, task_id: str) -> dict[str, Any]:
    """Read one ledger-bound card through bounded public Hermes CLI adapters."""

    show = kanban_show(board_slug, task_id)
    runs = kanban_runs(board_slug, task_id)
    task = show.get("task")
    if not isinstance(task, dict) or task.get("id") != task_id:
        raise DashboardBackendError("Kanban card identity does not match the ledger")
    comments = show.get("comments", [])
    events = show.get("events", [])
    if not isinstance(comments, list) or not isinstance(events, list):
        raise DashboardBackendError("Kanban card history has an invalid shape")
    return {
        "detail_available": True,
        "title": _bounded_text(task.get("title"), limit=300),
        "priority": task.get("priority") if isinstance(task.get("priority"), int) else None,
        "created_at": _bounded_timestamp(task.get("created_at")),
        "started_at": _bounded_timestamp(task.get("started_at")),
        "completed_at": _bounded_timestamp(task.get("completed_at")),
        "comments": [
            {
                "author": _bounded_text(row.get("author"), limit=100),
                "body": _bounded_text(row.get("body")),
                "created_at": _bounded_timestamp(row.get("created_at")),
            }
            for row in comments[-20:]
            if isinstance(row, dict)
        ],
        "events": [
            {
                "kind": _bounded_text(row.get("kind"), limit=100),
                "created_at": _bounded_timestamp(row.get("created_at")),
                "run_id": row.get("run_id") if isinstance(row.get("run_id"), int) else None,
            }
            for row in events[-50:]
            if isinstance(row, dict)
        ],
        "runs": [
            {
                "id": row.get("id") if isinstance(row.get("id"), int) else None,
                "profile": _bounded_text(row.get("profile"), limit=100),
                "status": _bounded_text(row.get("status"), limit=100),
                "outcome": _bounded_text(row.get("outcome"), limit=100),
                "started_at": _bounded_timestamp(row.get("started_at")),
                "ended_at": _bounded_timestamp(row.get("ended_at")),
                "summary": _bounded_text(row.get("summary")),
                "error": _bounded_text(row.get("error")),
            }
            for row in runs[-20:]
            if isinstance(row, dict)
        ],
    }


card_detail_provider = _kanban_card_detail


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