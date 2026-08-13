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
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast

from .artifact_access import ArtifactDownload
from .checkout_root import CheckoutRootError, CheckoutRootStore
from .checkouts import CheckoutError, CheckoutManager
from .constraints import (
    CONSTRAINTS_SCHEMA,
    DEFAULT_CONSTRAINT_TEMPLATE,
    MAX_CANONICAL_BYTES,
    MAX_CONSTRAINT_BYTES,
    MAX_CONSTRAINTS_PER_SCOPE,
)
from .errors import PolicyViolationError
from .github_project_links import GitHubProjectLinkError, GitHubProjectLinksStore
from .locations import resolve_data_root
from .packs import load_pack
from .prerequisites import parse_prerequisite_evidence, prerequisite_evidence_path
from .profile_files import ProfileFileError, read_private_text
from .recommendations import (
    ConstraintView,
    KanbanSnapshot,
    derive_recommendations,
)
from .registrations import (
    ControllerRegistration,
    list_controller_registrations,
    registration_path,
)
from .revision import build_review_packet
from .service import ServiceError, WorkflowService
from .skills import (
    ProfileSkillContentRegistry,
    SkillContentRegistry,
    pack_skill_digests,
)
from .state import (
    ActivationReferenceState,
    WorkflowConstraintsArtifact,
    WorkflowLedger,
    WorkflowStage,
)
from .store import StoreError, WorkflowStore


class DashboardBackendError(RuntimeError):
    """Base class for dashboard backend failures surfaced to the UI."""


class HostUnavailableError(DashboardBackendError):
    """Raised when the Kanban host state is unreadable on demand."""


class UnknownWorkflowError(DashboardBackendError):
    """Raised when the requested workflow ledger does not exist."""


ServiceFactory = Callable[[], WorkflowService]
CardDetailProvider = Callable[[str, str], dict[str, Any]]
ConfigurationProvider = Callable[[], dict[str, Any]]


def _intake_configuration_status(
    registration: ControllerRegistration, data_root: Path
) -> dict[str, object]:
    evidence_path = prerequisite_evidence_path(
        registration_path(data_root, registration.project_id)
    )
    try:
        evidence = parse_prerequisite_evidence(
            read_private_text(
                evidence_path,
                maximum_bytes=65_536,
                label="prerequisite evidence",
            )
        )
    except FileNotFoundError:
        return {"status": "not_configured", "reason": "prerequisite evidence is missing"}
    except ProfileFileError:
        return {"status": "unavailable", "reason": "prerequisite evidence is unavailable"}
    except PolicyViolationError:
        return {"status": "blocked", "reason": "prerequisite evidence is malformed"}
    if evidence.project_id != registration.project_id:
        return {"status": "blocked", "reason": "prerequisite evidence project does not match"}
    capability = next(
        (
            row
            for row in evidence.credential_capabilities
            if row.alias == registration.intake_credential and row.capability == "github-intake"
        ),
        None,
    )
    if capability is None:
        return {"status": "blocked", "reason": "GitHub intake capability is not recorded"}
    required = {"read-organization", "read-project", "read-public-repository"}
    if required.issubset(set(capability.allowed)):
        return {"status": "healthy"}
    return {"status": "blocked", "reason": "GitHub intake capability is incomplete"}


def _configuration_projection() -> dict[str, Any]:
    """Build the one persisted, credential-minimal configuration snapshot."""

    data_root = resolve_data_root().resolve()
    try:
        registrations = list_controller_registrations(data_root)
        config = CheckoutRootStore(data_root).read()
        checkouts = {
            row.project_id: row.to_dict()
            for row in CheckoutManager(data_root).statuses(registrations)
        }
        links = {
            row.project_id: row
            for row in GitHubProjectLinksStore(data_root).read(registrations)
        }
    except (
        CheckoutError,
        CheckoutRootError,
        GitHubProjectLinkError,
        PolicyViolationError,
    ) as error:
        raise DashboardBackendError(str(error)) from error

    projected = []
    for registration in registrations:
        link = links.get(registration.project_id)
        github_project: dict[str, object] = (
            {"status": "not_configured"}
            if link is None
            else {
                "status": "healthy",
                "owner": link.owner,
                "project_number": link.project_number,
                "node_id_configured": bool(link.project_node_id),
            }
        )
        projected.append(
            {
                "project_id": registration.project_id,
                "checkout": checkouts.get(
                    registration.project_id,
                    {"state": "unavailable", "reason": "checkout status is unavailable"},
                ),
                "github_project": github_project,
                "intake": _intake_configuration_status(registration, data_root),
                "evaluator": {
                    "status": "healthy",
                    "backend": registration.evaluator_backend,
                    "network": registration.evaluator_network,
                },
                "notification": {
                    "status": (
                        "healthy" if registration.notification_destination else "not_configured"
                    ),
                    "adapter": registration.notification_adapter,
                    "destination_configured": bool(registration.notification_destination),
                },
            }
        )
    return {"checkouts": config.to_dict()["checkouts"], "registrations": projected}


class DashboardBackend:
    """Compose a ``WorkflowService`` with read-only dashboard projections."""

    def __init__(
        self,
        *,
        service_factory: ServiceFactory,
        card_detail_provider: CardDetailProvider | None = None,
        configuration_provider: ConfigurationProvider | None = None,
    ) -> None:
        self._service_factory = service_factory
        self._card_detail_provider = card_detail_provider
        self._configuration_provider = configuration_provider

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

            service = build_cli_service(defer_store_initialization=True)
            return cls(service_factory=lambda: service)

        root = resolve_data_root() / "daidala"
        store = WorkflowStore(root, defer_initialization=True)
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

    def configuration(self) -> dict[str, Any]:
        """Return the profile-safe persisted-configuration projection."""

        provider = self._configuration_provider or _configuration_projection
        return provider()

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
            "constraint_template": {
                "kind": "yaml-template",
                "source": "docs/14-workflow-constraints.md#starter-template",
                "content": DEFAULT_CONSTRAINT_TEMPLATE,
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
        recommendations = derive_recommendations(ledger, snapshots)
        card_details: dict[str, dict[str, Any]] = {}
        if self._card_detail_provider is not None:
            for row in kanban_cards:
                try:
                    card_details[row.task_id] = self._card_detail_provider(
                        ledger.board_slug, row.task_id
                    )
                except DashboardBackendError as error:
                    card_details[row.task_id] = {
                        "detail_available": False,
                        "detail_error": str(error),
                        "comments": [],
                        "events": [],
                        "runs": [],
                    }
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
                "cards": [
                    {
                        **snapshot.to_dict(),
                        **card_details.get(snapshot.task_id, {}),
                    }
                    for snapshot in snapshots
                ],
            },
            "recommendations": [row.to_dict() for row in recommendations],
            "timeline": _workflow_timeline(ledger, snapshots),
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

    def approval_review(self, workflow_id: str) -> dict[str, Any]:
        """Return the verified exact-plan decision packet without profile paths."""

        service = self.service
        try:
            ledger = service.status(workflow_id)
        except StoreError as error:
            raise UnknownWorkflowError(str(error)) from error
        current_plan = service.current_plan_evidence(
            workflow_id, ledger=ledger
        ).to_dict()
        return _approval_review_packet(ledger, current_plan)

    def artifacts(self, workflow_id: str | None = None) -> dict[str, object]:
        """Project path-free artifact metadata from captured ledger snapshots."""
        service = self.service
        ledgers = (
            (service.status(workflow_id),)
            if workflow_id is not None
            else tuple(service.store.list_all())
        )
        entries = []
        for ledger in ledgers:
            entries.extend(
                entry.to_dict()
                for entry in service.list_artifacts(
                    ledger.workflow_id, ledger=ledger
                )
            )
        entries.sort(
            key=lambda row: (
                cast(str | None, row["recorded_at"]) or "",
                str(row["workflow_id"]),
                str(row["artifact_id"]),
            ),
            reverse=True,
        )
        return {"workflow_id": workflow_id, "artifacts": entries}

    def artifact_text(self, workflow_id: str, artifact_id: str) -> dict[str, object]:
        """Project one digest-verified bounded text artifact."""
        service = self.service
        ledger = service.status(workflow_id)
        return service.read_artifact_text(
            workflow_id, artifact_id, ledger=ledger
        ).to_dict()

    def artifact_download(self, workflow_id: str, artifact_id: str) -> ArtifactDownload:
        """Resolve digest-verified bytes without accepting a filesystem path."""
        service = self.service
        ledger = service.status(workflow_id)
        return service.download_artifact(
            workflow_id, artifact_id, ledger=ledger
        )

    def curator_status(self) -> dict[str, object]:
        """Project curator policy, counts, rows, and deterministic transition times."""
        payload = self.service.curator_status().to_dict()
        policy = cast(dict[str, object], payload["policy"])
        rows = cast(list[dict[str, object]], payload["rows"])
        for row in rows:
            first_terminal = row["first_terminal_observed_at"]
            next_transition = None
            if first_terminal and not row["pinned"]:
                age_days = (
                    policy["stale_after_days"]
                    if row["state"] == "active"
                    else policy["archive_after_days"]
                    if row["state"] == "stale"
                    else None
                )
                if age_days is not None:
                    next_transition = (
                        datetime.fromisoformat(cast(str, first_terminal))
                        + timedelta(days=cast(int, age_days))
                    ).isoformat()
            row["next_transition_at"] = next_transition
        return payload

    def curator_preview(
        self, workflow_id: str, operation: str, archive_id: str | None = None
    ) -> dict[str, object]:
        """Preview one closed curator operation."""
        service = self.service
        if operation == "pin":
            preview = service.preview_curator_pin(workflow_id, pinned=True)
        elif operation == "unpin":
            preview = service.preview_curator_pin(workflow_id, pinned=False)
        elif operation == "archive":
            preview = service.preview_curator_archive(workflow_id)
        elif operation == "restore" and archive_id is not None:
            preview = service.preview_curator_restore(workflow_id, archive_id)
        else:
            raise ValueError("unsupported curator operation")
        return preview.to_dict()

    def curator_apply(
        self,
        workflow_id: str,
        operation: str,
        preview_digest: str,
        archive_id: str | None = None,
    ) -> dict[str, object]:
        """Apply one exact preview-confirmed curator operation."""
        service = self.service
        if operation == "pin":
            result = service.apply_curator_pin(
                workflow_id,
                pinned=True,
                expected_preview_digest=preview_digest,
            )
        elif operation == "unpin":
            result = service.apply_curator_pin(
                workflow_id,
                pinned=False,
                expected_preview_digest=preview_digest,
            )
        elif operation == "archive":
            result = service.apply_curator_archive(
                workflow_id, expected_preview_digest=preview_digest
            )
        elif operation == "restore" and archive_id is not None:
            result = service.apply_curator_restore(
                workflow_id,
                archive_id,
                expected_preview_digest=preview_digest,
            )
        else:
            raise ValueError("unsupported curator operation")
        return result.to_dict()

    def review_decision(self, workflow_id: str) -> dict[str, Any]:
        """Return exact reviewed evidence and attended disposition state."""

        service = self.service
        try:
            ledger = service.status(workflow_id)
        except StoreError as error:
            raise UnknownWorkflowError(str(error)) from error
        packet = build_review_packet(ledger)
        review = ledger.review
        if review is None:
            return {**packet, "available": True, "evidence": None}

        implementation_entry = next(
            (
                entry
                for entry in service.list_artifacts(
                    workflow_id,
                    kinds=("stage",),
                    revisions=(ledger.plan_revision,),
                    ledger=ledger,
                )
                if entry.stage == WorkflowStage.IMPLEMENT.value
                and entry.digest == review.implementation_digest
            ),
            None,
        )
        if implementation_entry is None:
            raise ServiceError("reviewed implementation artifact is unavailable")
        implementation = service.read_artifact_text(
            workflow_id, implementation_entry.artifact_id, ledger=ledger
        )
        verification = [
            {
                "command": row.command,
                "exit_code": row.exit_code,
                "output_digest": row.output_digest,
                "recorded_at": row.recorded_at.isoformat(),
            }
            for row in ledger.verification_evidence
            if row.output_digest in review.verification_digests
        ]
        if sorted(row["output_digest"] for row in verification) != list(
            review.verification_digests
        ):
            raise ServiceError("review verification evidence is incomplete")
        return {
            **packet,
            "available": True,
            "evidence": {
                "change_summary": review.summary.to_dict(),
                "summary_digest": review.summary_digest,
                "implementation": {
                    "artifact_id": str(implementation_entry.artifact_id),
                    "digest": implementation_entry.digest,
                    "content": implementation.content,
                    "changed_paths": list(
                        service.current_implementation_changed_paths(
                            workflow_id, ledger=ledger
                        )
                    ),
                },
                "verification": verification,
            },
            "consequences": {
                "accept_delivery": (
                    "Record the exact attended disposition and create one delivery card."
                ),
                "request_revision": (
                    "Preserve the rejected evidence, archive current post-gate cards, "
                    "release the owned worktree, and create one successor Plan card."
                ),
                "reject_workflow": (
                    "Preserve the exact evidence and reject the workflow without delivery."
                ),
            },
        }

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
    authorization = ledger.delivery_authorization
    delivery = (
        {
            "branch": authorization.branch,
            "commit": authorization.commit,
        }
        if ledger.committed and ledger.pushed and authorization is not None
        else None
    )
    return {
        "workflow_id": ledger.workflow_id,
        "board_slug": ledger.board_slug,
        "target_repository": ledger.target_repository,
        "requested_goal": ledger.requested_goal,
        "pack_name": ledger.pack_name,
        "pack_source_revision": ledger.pack_source_revision,
        "policy_revision": ledger.policy_revision,
        "plan_revision": ledger.plan_revision,
        "plan_source": _plan_source_summary(ledger),
        "approval": ledger.approval.to_dict() if ledger.approval else None,
        "current_constraints_revision": ledger.current_constraints_revision,
        "current_constraints_digest": ledger.current_constraints_digest,
        "committed": ledger.committed,
        "pushed": ledger.pushed,
        "delivery_authorization": delivery,
        "updated_at": ledger.updated_at.isoformat(),
        "created_at": ledger.created_at.isoformat(),
    }


def _plan_source_summary(ledger: WorkflowLedger) -> dict[str, object]:
    packet = ledger.plan_source_packet
    if packet is None:
        return {"mode": "generated"}
    return {
        "mode": "git-pinned",
        "plan_id": packet.plan_id,
        "execution_slot": packet.execution_slot,
        "phase": {
            "number": packet.phase_number,
            "title": packet.phase_title,
        },
        "source_revision": packet.reference.source_revision,
        "packet": {
            "digest": packet.digest,
            "verification_state": "verified",
        },
    }


def _workflow_timeline(
    ledger: WorkflowLedger, snapshots: tuple[KanbanSnapshot, ...]
) -> list[dict[str, Any]]:
    cards = {snapshot.stage: snapshot for snapshot in snapshots}
    rows: list[dict[str, Any]] = []
    for stage in WorkflowStage:
        if stage is WorkflowStage.APPROVAL:
            approval = ledger.approval
            rows.append(
                {
                    "kind": "approval_gate",
                    "stage": stage.value,
                    "label": "Human approval — Daidala policy gate",
                    "status": "recorded" if approval is not None else "pending",
                    "card_id": None,
                    "assignee": None,
                    "occurred_at": (
                        approval.decided_at.isoformat() if approval is not None else None
                    ),
                    "approval": approval.to_dict() if approval is not None else None,
                }
            )
            continue
        snapshot = cards.get(stage)
        artifact = ledger.artifact_for(stage)
        rows.append(
            {
                "kind": "stage",
                "stage": stage.value,
                "label": stage.value,
                "status": (
                    snapshot.status
                    if snapshot is not None
                    else "recorded"
                    if artifact is not None
                    else "pending"
                ),
                "card_id": snapshot.task_id if snapshot is not None else None,
                "assignee": snapshot.assignee if snapshot is not None else None,
                "occurred_at": (
                    artifact.recorded_at.isoformat() if artifact is not None else None
                ),
            }
        )
        if stage is WorkflowStage.REVIEW:
            disposition = ledger.review_disposition
            review = ledger.review
            rows.append(
                {
                    "kind": "review_gate",
                    "stage": "review_disposition",
                    "label": "Human review disposition — Daidala policy gate",
                    "status": (
                        "recorded"
                        if disposition is not None
                        else "pending"
                        if review is not None
                        else "waiting"
                    ),
                    "card_id": None,
                    "assignee": None,
                    "occurred_at": (
                        disposition.decided_at.isoformat()
                        if disposition is not None
                        else None
                    ),
                    "review_digest": review.digest if review is not None else None,
                    "disposition": disposition.to_dict() if disposition else None,
                }
            )
    return rows


def _approval_review_packet(
    ledger: WorkflowLedger, current_plan: dict[str, Any]
) -> dict[str, Any]:
    approval = ledger.approval
    approved = approval is not None
    activations = _current_activation_identities(ledger)
    artifacts = _current_artifact_identities(ledger)
    return {
        "workflow_id": ledger.workflow_id,
        "available": True,
        "plan": {
            "artifact_id": current_plan["artifact_id"],
            "policy_revision": current_plan["policy_revision"],
            "plan_revision": current_plan["plan_revision"],
            "plan_digest": current_plan["plan_digest"],
            "summary": current_plan["approval_summary"],
            "summary_digest": current_plan["approval_summary_digest"],
            "content": current_plan["content"],
            "verification_state": "verified",
        },
        "tuple": {
            "workflow_id": ledger.workflow_id,
            "policy_revision": ledger.policy_revision,
            "plan_revision": ledger.plan_revision,
            "plan_digest": current_plan["plan_digest"],
            "constraints_revision": ledger.current_constraints_revision,
            "constraints_digest": ledger.current_constraints_digest,
        },
        "goal": ledger.requested_goal,
        "pack_identity": {
            "name": ledger.pack_name,
            "source_revision": ledger.pack_source_revision,
            "activations": activations,
        },
        "consequences": {
            "worktree": "one detached worktree after approval",
            "next_cards": ["implement", "verify", "review"],
            "committed": False,
            "pushed": False,
        },
        "approval": approval.to_dict() if approval is not None else None,
        "successor_packet": {
            "workflow_id": ledger.workflow_id,
            "stage": WorkflowStage.IMPLEMENT.value,
            "policy_revision": ledger.policy_revision,
            "plan_revision": ledger.plan_revision,
            "plan_digest": current_plan["plan_digest"],
            "constraints_revision": ledger.current_constraints_revision,
            "constraints_digest": ledger.current_constraints_digest,
            "pack_name": ledger.pack_name,
            "pack_source_revision": ledger.pack_source_revision,
            "activations": activations,
            "artifacts": artifacts,
            "baseline_commit": ledger.baseline_commit if approved else None,
            "worktree": (
                {"present": ledger.worktree_path is not None, "owned": ledger.worktree_owned}
                if approved
                else None
            ),
        },
    }


def _current_artifact_identities(ledger: WorkflowLedger) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for stage in WorkflowStage:
        if stage is WorkflowStage.APPROVAL:
            continue
        reference = ledger.artifact_for(stage)
        if reference is None:
            continue
        result.append(
            {
                "stage": stage.value,
                "policy_revision": reference.policy_revision,
                "plan_revision": reference.plan_revision,
                "digest": reference.digest,
                "recorded_at": reference.recorded_at.isoformat(),
                "approval_summary_digest": reference.approval_summary_digest,
            }
        )
    return result


def _current_activation_identities(ledger: WorkflowLedger) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for stage in WorkflowStage:
        if stage is WorkflowStage.APPROVAL:
            continue
        reference = ledger.activation_for(stage)
        if (
            reference is None
            or reference.state is not ActivationReferenceState.FINALIZED
        ):
            continue
        result.append(
            {
                "stage": stage.value,
                "policy_revision": reference.policy_revision,
                "plan_revision": reference.plan_revision,
                "constraints_digest": reference.constraints_digest,
                "sequence": reference.sequence,
                "digest": reference.digest,
                "blocked": reference.blocked,
                "supersedes_digest": reference.supersedes_digest,
            }
        )
    return result


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
    "CardDetailProvider",
    "DashboardBackend",
    "DashboardBackendError",
    "HostUnavailableError",
    "UnknownWorkflowError",
    "ServiceFactory",
]