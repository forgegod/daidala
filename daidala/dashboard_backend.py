"""Profile-safe read-only dashboard backend.

The dashboard backend is the thin adapter between the Hermes dashboard
process and the existing Daidala services. It constructs a
``WorkflowService`` with the same profile-aware location and public Kanban
boundary as the existing tool and CLI paths and exposes only the
machine-readable data the dashboard UI needs. It never imports Hermes
internals, never writes the Kanban database, never persists operational
status, and never reads arbitrary filesystem paths.

The pure derivation logic for pending decisions and recommendations lives
in :mod:`daidala.recommendations`. This module wires that logic to the
service boundary and translates host failures into the dashboard's
read-only error shape.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any, cast

from .constraints import (
    CONSTRAINTS_SCHEMA,
    MAX_CANONICAL_BYTES,
    MAX_CONSTRAINT_BYTES,
    MAX_CONSTRAINTS_PER_SCOPE,
)
from .locations import resolve_data_root
from .packs import load_pack
from .recommendations import (
    ConstraintView,
    KanbanSnapshot,
    derive_recommendations,
)
from .service import ServiceError, WorkflowService
from .skills import (
    ProfileSkillContentRegistry,
    SkillContentRegistry,
    pack_skill_digests,
)
from .state import (
    WorkflowConstraintsArtifact,
    WorkflowLedger,
)
from .store import StoreError, WorkflowStore


class DashboardBackendError(RuntimeError):
    """Base class for dashboard backend failures surfaced to the UI."""


class HostUnavailableError(DashboardBackendError):
    """Raised when the Kanban host state is unreadable on demand."""


class UnknownWorkflowError(DashboardBackendError):
    """Raised when the requested workflow ledger does not exist."""


ServiceFactory = Callable[[], WorkflowService]


class DashboardBackend:
    """Compose a ``WorkflowService`` with read-only dashboard projections."""

    def __init__(self, *, service_factory: ServiceFactory) -> None:
        self._service_factory = service_factory

    @property
    def service(self) -> WorkflowService:
        return self._service_factory()

    def service_factory(self) -> ServiceFactory:
        return self._service_factory

    @classmethod
    def from_default_profile(
        cls,
        *,
        dispatch_tool: Callable[[str, dict[str, object]], str] | None = None,
        clock: Callable[[], object] | None = None,
        skill_content_registry: SkillContentRegistry | None = None,
    ) -> DashboardBackend:
        """Build a backend that resolves the same profile root as the CLI."""

        if dispatch_tool is None and clock is None and skill_content_registry is None:
            from .cli import build_cli_service

            service = build_cli_service()
            return cls(service_factory=lambda: service)

        root = resolve_data_root() / "daidala"
        store = WorkflowStore(root)
        content_registry: SkillContentRegistry = (
            skill_content_registry
            if skill_content_registry is not None
            else ProfileSkillContentRegistry(root.parent / "skills")
        )
        kanban = None
        if dispatch_tool is not None:
            from .kanban import KanbanGraphAdapter, ToolDispatcher

            kanban = KanbanGraphAdapter(cast(ToolDispatcher, dispatch_tool))
        kwargs: dict[str, Any] = {
            "store": store,
            "skill_content_registry": content_registry,
            "kanban": kanban,
        }
        if clock is not None:
            kwargs["clock"] = clock
        service = WorkflowService(**kwargs)
        return cls(service_factory=lambda: service)

    # ---- endpoints ----------------------------------------------------

    def prerequisites(self) -> dict[str, Any]:
        """Return pack metadata and the profile-safe workflow inventory."""

        service = self.service
        packs = ("addyosmani", "aidlc")
        pack_payload: dict[str, Any] = {}
        for name in packs:
            pack = load_pack(name)
            digests = dict(pack_skill_digests(pack))
            pack_payload[name] = {
                "name": pack.name,
                "source": pack.source,
                "source_revision": pack.source_revision,
                "hermes_version_constraint": pack.hermes_version_constraint,
                "lifecycle": list(pack.lifecycle),
                "human_gate_after": pack.human_gate_after,
                "skills": {
                    stage.id: [
                        {
                            "name": skill.name,
                            "activation": skill.activation.value,
                            "bundled": skill.bundled,
                            "external": skill.is_external,
                            "install": skill.install,
                            "content_digest": digests[skill.name],
                        }
                        for skill in stage.skills
                    ]
                    for stage in pack.stages
                },
            }
        try:
            inventory = service.store.list_all()
        except StoreError as error:
            raise DashboardBackendError(str(error)) from error
        return {
            "packs": pack_payload,
            "default_pack": "addyosmani",
            "workflow_count": len(inventory),
            "workflow_ids": [row.workflow_id for row in inventory],
            "schema_limits": {
                "global_max": MAX_CONSTRAINTS_PER_SCOPE,
                "phase_max": MAX_CONSTRAINTS_PER_SCOPE,
                "constraint_bytes": MAX_CONSTRAINT_BYTES,
                "canonical_bytes": MAX_CANONICAL_BYTES,
                "schema": CONSTRAINTS_SCHEMA,
            },
        }

    def list_workflows(self) -> dict[str, Any]:
        """Return a snapshot of every workflow ledger known to the profile."""

        service = self.service
        ledgers = service.store.list_all()
        return {
            "snapshot": True,
            "workflows": [_workflow_summary(row) for row in ledgers],
        }

    def workflow_view(self, workflow_id: str) -> dict[str, Any]:
        """Return policy facts and a live, read-only Kanban snapshot."""

        service = self.service
        try:
            ledger = service.status(workflow_id)
        except StoreError as error:
            raise UnknownWorkflowError(str(error)) from error
        try:
            kanban_cards = service.combined_status(workflow_id)
        except Exception as error:  # noqa: BLE001 - host boundary
            raise HostUnavailableError(str(error)) from error
        snapshots = tuple(
            KanbanSnapshot(
                stage=row.stage,
                task_id=row.task_id,
                status=row.status,
                assignee=row.assignee,
            )
            for row in kanban_cards
        )
        return {
            "workflow_id": workflow_id,
            "workflow": _workflow_summary(ledger),
            "constraints": (
                _constraint_view_to_dict(view)
                if (view := self._read_current_constraint_view(ledger)) is not None
                else None
            ),
            "kanban": {
                "available": True,
                "cards": [snapshot.to_dict() for snapshot in snapshots],
            },
        }

    def decisions(self, workflow_id: str) -> dict[str, Any]:
        """Return only the human-action items for the workflow."""

        ledger, kanban_available, recommendations, error = self._collect(workflow_id)
        decisions_payload = [
            row.to_dict()
            for row in recommendations
            if row.action_kind
            not in {"wait_for_dispatch", "deliver_reviewed_diff"}
        ]
        result: dict[str, Any] = {
            "workflow_id": workflow_id,
            "kanban_available": kanban_available,
            "decisions": decisions_payload,
        }
        if error is not None:
            result["error"] = error
        return result

    def recommendations(self, workflow_id: str) -> dict[str, Any]:
        """Return the full finite recommendation set including dispatch/delivery."""

        ledger, kanban_available, recommendations, error = self._collect(workflow_id)
        result: dict[str, Any] = {
            "workflow_id": workflow_id,
            "kanban_available": kanban_available,
            "recommendations": [row.to_dict() for row in recommendations],
        }
        if error is not None:
            result["error"] = error
        return result

    def decisions_with_constraints(self, workflow_id: str) -> dict[str, Any]:
        """Decisions plus the current constraint view and revision history."""

        ledger, kanban_available, recommendations, error = self._collect(workflow_id)
        constraint_view = self._read_current_constraint_view(ledger)
        return {
            "workflow_id": workflow_id,
            "kanban_available": kanban_available,
            "decisions": [
                row.to_dict()
                for row in recommendations
                if row.action_kind
                not in {"wait_for_dispatch", "deliver_reviewed_diff"}
            ],
            "current_constraints": (
                _constraint_view_to_dict(constraint_view)
                if constraint_view is not None
                else None
            ),
            "constraint_revisions": [
                {
                    "revision": reference.identity.constraints_revision,
                    "policy_revision": reference.identity.policy_revision,
                    "digest": reference.identity.digest,
                    "path": reference.path,
                    "recorded_at": reference.recorded_at.isoformat(),
                    "source": (
                        {
                            "name": reference.source.name,
                            "digest": reference.source.digest,
                        }
                        if reference.source is not None
                        else None
                    ),
                }
                for reference in ledger.constraint_references
            ],
            "approvals": (
                [ledger.approval.to_dict()] if ledger.approval is not None else []
            ),
            "error": error,
        }

    def preview_constraints(
        self,
        *,
        workflow_id: str,
        constraints_content: str | None = None,
        constraints_skill: str | None = None,
        constraints_skill_digest: str | None = None,
        expected_current_digest: str | None = None,
    ) -> dict[str, Any]:
        """Validate the supplied constraints and return canonical identity.

        Non-mutating. Reports the workflow's current digest for the UI to
        pin a compare-and-swap replacement.
        """

        service = self.service
        try:
            ledger = service.status(workflow_id)
        except StoreError as error:
            raise UnknownWorkflowError(str(error)) from error

        if constraints_content is not None and constraints_skill is not None:
            return _preview_error(
                ledger,
                "constraint content and constraint skill are mutually exclusive",
            )
        if constraints_skill_digest is not None and constraints_skill is None:
            return _preview_error(
                ledger, "constraint skill digest requires a constraint skill"
            )
        if constraints_content is None and constraints_skill is None:
            return _preview_error(
                ledger,
                "constraint replacement requires content or a constraint skill",
            )

        try:
            resolved = service._resolve_constraint_input(  # type: ignore[attr-defined]
                content=constraints_content,
                skill_name=constraints_skill,
                skill_digest=constraints_skill_digest,
            )
        except ServiceError as error:
            return _preview_error(ledger, str(error))

        if resolved is None:
            return _preview_error(
                ledger,
                "constraint replacement requires content or a constraint skill",
            )

        parsed, source = resolved
        canonical_bytes = parsed.canonical_bytes()
        canonical_content = canonical_bytes.decode("utf-8")
        new_digest = hashlib.sha256(canonical_bytes).hexdigest()

        current_digest = ledger.current_constraints_digest
        no_change = current_digest == new_digest

        impact: dict[str, Any] = {
            "invalidation": "no_change" if no_change else "required",
            "policy_revision_delta": 0 if no_change else 1,
            "graph_recreated": not no_change,
            "worktree_released": not no_change,
            "approval_invalidated": not no_change,
        }
        if no_change:
            impact["rationale"] = (
                "Formatting-only change: canonical content and digest "
                "match the current constraint revision."
            )

        errors: list[str] = []
        if expected_current_digest is not None and expected_current_digest != current_digest:
            errors.append(
                "expected_current_digest does not match the current constraint digest"
            )

        return {
            "workflow_id": workflow_id,
            "valid": not errors,
            "errors": errors,
            "current_digest": current_digest,
            "current_revision": ledger.current_constraints_revision,
            "new_digest": new_digest,
            "canonical_size_bytes": len(canonical_bytes),
            "canonical_content": canonical_content,
            "source_skill": source.name if source else None,
            "source_skill_digest": source.digest if source else None,
            "impact": impact,
        }

    def replace_constraint_input(
        self,
        *,
        workflow_id: str,
        expected_current_digest: str | None,
        constraints_content: str | None,
        constraints_skill: str | None,
        constraints_skill_digest: str | None,
    ) -> dict[str, Any]:
        """Replace constraints through the existing compare-and-swap service path."""
        try:
            ledger = self.service.replace_constraint_input(
                workflow_id,
                expected_current_digest=expected_current_digest,
                content=constraints_content,
                skill_name=constraints_skill,
                skill_digest=constraints_skill_digest,
            )
        except (ServiceError, StoreError) as error:
            raise DashboardBackendError(str(error)) from error
        return {
            "workflow": _workflow_summary(ledger),
            "consequences": {
                "approval_required": ledger.approval is None,
                "policy_revision": ledger.policy_revision,
                "constraints_digest": ledger.current_constraints_digest,
            },
        }

    # ---- helpers ------------------------------------------------------

    def _collect(
        self, workflow_id: str
    ) -> tuple[WorkflowLedger, bool, tuple, str | None]:
        service = self.service
        try:
            ledger = service.status(workflow_id)
        except StoreError as error:
            raise UnknownWorkflowError(str(error)) from error

        try:
            cards = service.combined_status(workflow_id)
        except Exception as error:  # noqa: BLE001 - host boundary
            return ledger, False, (), str(error)

        snapshots = tuple(
            KanbanSnapshot(
                stage=row.stage,
                task_id=row.task_id,
                status=row.status,
                assignee=row.assignee,
            )
            for row in cards
        )
        try:
            recommendations = derive_recommendations(ledger, snapshots)
        except ValueError:
            recommendations = ()
        return ledger, True, recommendations, None

    def _read_current_constraint_view(
        self, ledger: WorkflowLedger
    ) -> ConstraintView | None:
        reference = ledger.current_constraints
        if reference is None:
            return None
        workspace_root = self.service.store.data_root.parent
        path = (
            workspace_root
            / "workflows"
            / ledger.workflow_id
            / "artifacts"
            / f"workflow-constraints-{reference.identity.constraints_revision}.json"
        )
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        try:
            artifact = WorkflowConstraintsArtifact.from_dict(payload)
        except Exception:  # noqa: BLE001 - boundary between IO and policy
            return None
        return ConstraintView.from_artifact(reference, artifact)


def _workflow_summary(ledger: WorkflowLedger) -> dict[str, Any]:
    return {
        "workflow_id": ledger.workflow_id,
        "board_slug": ledger.board_slug,
        "target_repository": ledger.target_repository,
        "requested_goal": ledger.requested_goal,
        "pack_name": ledger.pack_name,
        "pack_source_revision": ledger.pack_source_revision,
        "policy_revision": ledger.policy_revision,
        "plan_revision": ledger.plan_revision,
        "approval": ledger.approval.to_dict() if ledger.approval else None,
        "current_constraints_revision": ledger.current_constraints_revision,
        "current_constraints_digest": ledger.current_constraints_digest,
        "updated_at": ledger.updated_at.isoformat(),
        "created_at": ledger.created_at.isoformat(),
    }


def _constraint_view_to_dict(view: ConstraintView) -> dict[str, Any]:
    return {
        "revision": view.revision,
        "digest": view.digest,
        "path": view.path,
        "source_skill": view.source_skill,
        "source_digest": view.source_digest,
        "canonical_content": view.canonical_content,
    }


def _preview_error(ledger: WorkflowLedger, message: str) -> dict[str, Any]:
    return {
        "workflow_id": ledger.workflow_id,
        "valid": False,
        "errors": [message],
        "current_digest": ledger.current_constraints_digest,
        "current_revision": ledger.current_constraints_revision,
        "new_digest": None,
        "canonical_size_bytes": None,
        "canonical_content": None,
        "source_skill": None,
        "source_skill_digest": None,
        "impact": {"invalidation": "unknown"},
    }


__all__ = [
    "DashboardBackend",
    "DashboardBackendError",
    "HostUnavailableError",
    "UnknownWorkflowError",
    "ServiceFactory",
]