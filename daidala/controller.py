"""Replay-safe self-improvement admission coordination."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from .adapters import (
    ClaimIdentity,
    IntakeAdapter,
    IntakeRecord,
    NotificationAdapter,
    NotificationReceipt,
)
from .constraints import parse_workflow_constraints
from .cycles import CycleIdentity, CycleMode
from .errors import PolicyViolationError
from .packs import load_pack, pack_content_digest
from .projects import (
    MAX_MANIFEST_BYTES,
    ProjectManifest,
    _require_digest,
    _require_exact_fields,
    _require_slug,
    _require_text,
)
from .registrations import ControllerRegistration
from .state import StageProfile, WorkflowLedger, WorkflowStage

MANIFEST_SNAPSHOT_SCHEMA = "daidala.manifest-snapshot/v1"
ADMISSION_SCHEMA = "daidala.cycle-admission/v1"
ADMISSION_PREVIEW_SCHEMA = "daidala.admission-preview/v1"
_CYCLE_ID = re.compile(r"^cycle-[0-9a-f]{64}$")


class WorkflowStarter(Protocol):
    def start(
        self,
        *,
        board_slug: str,
        target_repository: str,
        goal: str,
        stage_profiles: dict[str, str],
        pack_name: str = "addyosmani",
        workflow_id: str | None = None,
        constraints_content: str | None = None,
        constraints_skill: str | None = None,
        constraints_skill_digest: str | None = None,
        expected_baseline_commit: str | None = None,
    ) -> WorkflowLedger: ...


@dataclass(frozen=True)
class ManifestSnapshot:
    cycle_id: str
    workflow_id: str
    project_id: str
    manifest_digest: str
    canonical_content: str
    schema: str = MANIFEST_SNAPSHOT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != MANIFEST_SNAPSHOT_SCHEMA:
            raise PolicyViolationError(
                f"manifest snapshot schema must be {MANIFEST_SNAPSHOT_SCHEMA!r}"
            )
        _require_cycle_id(self.cycle_id)
        if self.workflow_id != self.cycle_id:
            raise PolicyViolationError("self-improvement workflow ID must equal its cycle ID")
        _require_slug(self.project_id, "manifest snapshot project ID")
        _require_digest(self.manifest_digest, "manifest snapshot digest")
        _require_text(
            self.canonical_content,
            "manifest snapshot canonical content",
            MAX_MANIFEST_BYTES,
        )
        content = self.canonical_content.encode("utf-8")
        if len(content) > MAX_MANIFEST_BYTES:
            raise PolicyViolationError("manifest snapshot exceeds its byte bound")
        if hashlib.sha256(content).hexdigest() != self.manifest_digest:
            raise PolicyViolationError("manifest snapshot digest does not match its content")
        try:
            manifest = ProjectManifest.from_dict(json.loads(self.canonical_content))
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            raise PolicyViolationError("manifest snapshot content is not canonical JSON") from error
        if manifest.project_id != self.project_id or manifest.digest != self.manifest_digest:
            raise PolicyViolationError("manifest snapshot identity does not match its manifest")
        if manifest.canonical_bytes().decode("utf-8") != self.canonical_content:
            raise PolicyViolationError("manifest snapshot content is not canonically serialized")

    def to_dict(self) -> dict[str, str]:
        return {
            "schema": self.schema,
            "cycle_id": self.cycle_id,
            "workflow_id": self.workflow_id,
            "project_id": self.project_id,
            "manifest_digest": self.manifest_digest,
            "canonical_content": self.canonical_content,
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")

    @classmethod
    def from_dict(cls, raw: Any) -> ManifestSnapshot:
        _require_exact_fields(
            raw,
            {
                "schema",
                "cycle_id",
                "workflow_id",
                "project_id",
                "manifest_digest",
                "canonical_content",
            },
            "manifest snapshot",
        )
        return cls(**raw)


@dataclass(frozen=True)
class CycleAdmission:
    cycle: CycleIdentity
    workflow_id: str
    board: str
    checkout: str
    registration_digest: str
    constraints_digest: str
    stage_profiles: tuple[StageProfile, ...]
    intake: IntakeRecord
    claim: ClaimIdentity
    snapshot: ManifestSnapshot
    created_at: datetime
    schema: str = ADMISSION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != ADMISSION_SCHEMA:
            raise PolicyViolationError(f"cycle admission schema must be {ADMISSION_SCHEMA!r}")
        if self.workflow_id != self.cycle.cycle_id:
            raise PolicyViolationError("cycle admission workflow ID must equal the cycle ID")
        _require_slug(self.board, "cycle admission board")
        if not Path(self.checkout).is_absolute() or str(Path(self.checkout)) != self.checkout:
            raise PolicyViolationError(
                "cycle admission checkout must be a normalized absolute path"
            )
        _require_digest(self.registration_digest, "cycle admission registration digest")
        _require_digest(self.constraints_digest, "cycle admission constraints digest")
        if not isinstance(self.stage_profiles, tuple) or any(
            not isinstance(row, StageProfile) for row in self.stage_profiles
        ):
            raise PolicyViolationError("cycle admission stage profiles must be a tuple")
        if self.stage_profiles != _normalize_stage_profiles(
            {row.stage.value: row.profile for row in self.stage_profiles}
        ):
            raise PolicyViolationError("cycle admission stage profiles are not canonical")
        if self.intake.claim != self.claim:
            raise PolicyViolationError("cycle admission intake claim does not match its claim")
        if self.claim.claimant != self.cycle.cycle_id:
            raise PolicyViolationError("cycle admission claim owner must equal the cycle ID")
        if self.intake.adapter != self.cycle.intake_adapter:
            raise PolicyViolationError("cycle admission intake adapter does not match the cycle")
        if self.intake.item_id != self.cycle.intake_item_id:
            raise PolicyViolationError("cycle admission intake item does not match the cycle")
        if self.snapshot.cycle_id != self.cycle.cycle_id:
            raise PolicyViolationError("cycle admission snapshot does not match the cycle")
        if self.snapshot.manifest_digest != self.cycle.manifest_digest:
            raise PolicyViolationError("cycle admission manifest digest does not match the cycle")
        if not isinstance(self.created_at, datetime) or self.created_at.tzinfo is None:
            raise PolicyViolationError("cycle admission timestamp must be timezone-aware")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "cycle": self.cycle.to_dict(),
            "workflow_id": self.workflow_id,
            "board": self.board,
            "checkout": self.checkout,
            "registration_digest": self.registration_digest,
            "constraints_digest": self.constraints_digest,
            "stage_profiles": [row.to_dict() for row in self.stage_profiles],
            "intake": self.intake.to_dict(),
            "claim": self.claim.to_dict(),
            "snapshot": self.snapshot.to_dict(),
            "created_at": self.created_at.isoformat(),
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")

    @classmethod
    def from_dict(cls, raw: Any) -> CycleAdmission:
        fields = {
            "schema",
            "cycle",
            "workflow_id",
            "board",
            "checkout",
            "registration_digest",
            "constraints_digest",
            "stage_profiles",
            "intake",
            "claim",
            "snapshot",
            "created_at",
        }
        _require_exact_fields(raw, fields, "cycle admission")
        try:
            created_at = datetime.fromisoformat(raw["created_at"])
        except (TypeError, ValueError) as error:
            raise PolicyViolationError("cycle admission timestamp must be ISO-8601") from error
        stage_profiles_raw = raw["stage_profiles"]
        if not isinstance(stage_profiles_raw, list):
            raise PolicyViolationError("cycle admission stage profiles must be a list")
        stage_profiles: list[StageProfile] = []
        for row in stage_profiles_raw:
            _require_exact_fields(row, {"stage", "profile"}, "cycle admission stage profile")
            try:
                stage_profiles.append(StageProfile.from_dict(row))
            except (KeyError, TypeError, ValueError) as error:
                raise PolicyViolationError("cycle admission stage profile is invalid") from error
        return cls(
            schema=raw["schema"],
            cycle=CycleIdentity.from_dict(raw["cycle"]),
            workflow_id=raw["workflow_id"],
            board=raw["board"],
            checkout=raw["checkout"],
            registration_digest=raw["registration_digest"],
            constraints_digest=raw["constraints_digest"],
            stage_profiles=tuple(stage_profiles),
            intake=IntakeRecord.from_dict(raw["intake"]),
            claim=ClaimIdentity.from_dict(raw["claim"]),
            snapshot=ManifestSnapshot.from_dict(raw["snapshot"]),
            created_at=created_at,
        )


@dataclass(frozen=True)
class AdmissionPreview:
    cycle: CycleIdentity
    workflow_id: str
    board: str
    checkout: str
    registration_digest: str
    constraints_digest: str
    stage_profiles: tuple[StageProfile, ...]
    intake_digest: str
    schema: str = ADMISSION_PREVIEW_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != ADMISSION_PREVIEW_SCHEMA:
            raise PolicyViolationError(
                f"admission preview schema must be {ADMISSION_PREVIEW_SCHEMA!r}"
            )
        if self.workflow_id != self.cycle.cycle_id:
            raise PolicyViolationError("admission preview workflow ID must equal the cycle ID")
        _require_slug(self.board, "admission preview board")
        if not Path(self.checkout).is_absolute() or str(Path(self.checkout)) != self.checkout:
            raise PolicyViolationError(
                "admission preview checkout must be a normalized absolute path"
            )
        _require_digest(self.registration_digest, "admission preview registration digest")
        _require_digest(self.constraints_digest, "admission preview constraints digest")
        _require_digest(self.intake_digest, "admission preview intake digest")
        if not isinstance(self.stage_profiles, tuple) or any(
            not isinstance(row, StageProfile) for row in self.stage_profiles
        ):
            raise PolicyViolationError("admission preview stage profiles must be a tuple")
        if self.stage_profiles != _normalize_stage_profiles(
            {row.stage.value: row.profile for row in self.stage_profiles}
        ):
            raise PolicyViolationError("admission preview stage profiles are not canonical")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "dry_run": True,
            "cycle": self.cycle.to_dict(),
            "workflow_id": self.workflow_id,
            "board": self.board,
            "checkout": self.checkout,
            "registration_digest": self.registration_digest,
            "constraints_digest": self.constraints_digest,
            "stage_profiles": [row.to_dict() for row in self.stage_profiles],
            "intake_digest": self.intake_digest,
        }


class CycleArtifactStore:
    """Write immutable cycle admission artifacts below a trusted profile data root."""

    def __init__(self, data_root: Path) -> None:
        if (
            not isinstance(data_root, Path)
            or not data_root.is_absolute()
            or ".." in data_root.parts
            or "." in data_root.parts
        ):
            raise PolicyViolationError("cycle data root must be an absolute resolved path")
        self.data_root = data_root

    def materialize_snapshot(
        self, cycle: CycleIdentity, manifest: ProjectManifest
    ) -> ManifestSnapshot:
        if cycle.manifest_digest != manifest.digest or cycle.project_id != manifest.project_id:
            raise PolicyViolationError("cycle identity does not match the admitted manifest")
        snapshot = ManifestSnapshot(
            cycle_id=cycle.cycle_id,
            workflow_id=cycle.cycle_id,
            project_id=manifest.project_id,
            manifest_digest=manifest.digest,
            canonical_content=manifest.canonical_bytes().decode("utf-8"),
        )
        self._write_once(
            self._cycle_root(cycle) / "manifest-snapshot.json",
            snapshot.canonical_bytes(),
        )
        return snapshot

    def load_admission(self, cycle: CycleIdentity) -> CycleAdmission | None:
        path = self._cycle_root(cycle) / "admission.json"
        if not path.exists():
            return None
        try:
            return CycleAdmission.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as error:
            raise PolicyViolationError("stored cycle admission is unreadable") from error

    def save_admission(self, admission: CycleAdmission) -> None:
        self._write_once(
            self._cycle_root(admission.cycle) / "admission.json",
            admission.canonical_bytes(),
        )

    def load_notification(
        self, cycle: CycleIdentity, event: str
    ) -> NotificationReceipt | None:
        _require_slug(event, "notification event")
        path = self._cycle_root(cycle) / "notifications" / f"{event}.json"
        if not path.exists():
            return None
        try:
            return NotificationReceipt.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as error:
            raise PolicyViolationError("stored notification receipt is unreadable") from error

    def save_notification(
        self, cycle: CycleIdentity, event: str, receipt: NotificationReceipt
    ) -> None:
        _require_slug(event, "notification event")
        content = json.dumps(
            receipt.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        self._write_once(
            self._cycle_root(cycle) / "notifications" / f"{event}.json",
            content,
        )

    def _cycle_root(self, cycle: CycleIdentity) -> Path:
        _require_cycle_id(cycle.cycle_id)
        path = self.data_root / "projects" / cycle.project_id / "cycles" / cycle.cycle_id
        if self.data_root not in path.parents:
            raise PolicyViolationError("cycle artifact path escapes the data root")
        return path

    @staticmethod
    def _write_once(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_bytes() != content:
                raise PolicyViolationError(f"immutable cycle artifact conflicts at {path.name!r}")
            return
        try:
            with path.open("xb") as handle:
                handle.write(content)
        except FileExistsError as error:
            if path.read_bytes() != content:
                raise PolicyViolationError(
                    f"immutable cycle artifact conflicts at {path.name!r}"
                ) from error


class AdmissionCoordinator:
    """Validate, claim, materialize, bind, and notify one deterministic cycle."""

    def __init__(
        self,
        *,
        store: CycleArtifactStore,
        workflow: WorkflowStarter,
        intake_adapter: IntakeAdapter,
        notification_adapter: NotificationAdapter,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self.workflow = workflow
        self.intake_adapter = intake_adapter
        self.notification_adapter = notification_adapter
        self.clock = clock or (lambda: datetime.now(UTC))

    def preview(
        self,
        *,
        manifest: ProjectManifest,
        registration: ControllerRegistration,
        intake: IntakeRecord,
        baseline_revision: str,
        stage_profiles: dict[str, str],
        constraints_content: str,
        mode: CycleMode = CycleMode.IMPROVE,
        pack_name: str | None = None,
        candidate_identity: str | None = None,
        claim_lease_seconds: int = 900,
    ) -> AdmissionPreview:
        """Validate and identify one admission without durable or external mutation."""
        return self._preview(
            manifest=manifest,
            registration=registration,
            intake=intake,
            baseline_revision=baseline_revision,
            stage_profiles=stage_profiles,
            constraints_content=constraints_content,
            mode=mode,
            pack_name=pack_name,
            candidate_identity=candidate_identity,
            claim_lease_seconds=claim_lease_seconds,
            observed_at=self.clock(),
        )

    def _preview(
        self,
        *,
        manifest: ProjectManifest,
        registration: ControllerRegistration,
        intake: IntakeRecord,
        baseline_revision: str,
        stage_profiles: dict[str, str],
        constraints_content: str,
        mode: CycleMode,
        pack_name: str | None,
        candidate_identity: str | None,
        claim_lease_seconds: int,
        observed_at: datetime,
    ) -> AdmissionPreview:
        registration.validate_manifest(manifest)
        constraints = parse_workflow_constraints(constraints_content)
        profiles = _normalize_stage_profiles(stage_profiles)
        if claim_lease_seconds < 60 or claim_lease_seconds > 86_400:
            raise PolicyViolationError("claim lease must be between 60 and 86400 seconds")
        if intake.adapter != manifest.intake_adapter:
            raise PolicyViolationError("intake adapter is not authorized by the manifest")
        if intake.category.value not in manifest.eligible_categories:
            raise PolicyViolationError("intake category is not eligible for this project")
        if intake.admission_actor not in registration.maintainers:
            raise PolicyViolationError("intake admission actor is not an authorized maintainer")
        if not intake.ready:
            raise PolicyViolationError("intake item is not ready for admission")
        selected_pack = pack_name or manifest.default_pack
        pack = next((row for row in manifest.allowed_packs if row.name == selected_pack), None)
        if pack is None:
            raise PolicyViolationError("selected pack is not authorized by the manifest")
        installed_pack = load_pack(selected_pack)
        if (
            installed_pack.source_revision != pack.source_revision
            or pack_content_digest(selected_pack) != pack.content_digest
        ):
            raise PolicyViolationError("selected pack identity does not match the manifest")
        cycle = CycleIdentity(
            project_id=manifest.project_id,
            mode=mode,
            intake_adapter=intake.adapter,
            intake_item_id=intake.item_id,
            manifest_digest=manifest.digest,
            baseline_revision=baseline_revision,
            pack_name=pack.name,
            pack_source_revision=pack.source_revision,
            pack_content_digest=pack.content_digest,
            candidate_identity=candidate_identity,
        )
        if intake.claim is not None:
            if intake.claim.claimant != cycle.cycle_id:
                raise PolicyViolationError("intake item is claimed by another owner")
            if intake.claim.claimed_at > observed_at:
                raise PolicyViolationError("intake item has a future claim timestamp")
            if intake.claim.lease_expires_at <= observed_at:
                raise PolicyViolationError(
                    "expired intake claim requires two-authority reconciliation"
                )
            lease_seconds = (
                intake.claim.lease_expires_at - intake.claim.claimed_at
            ).total_seconds()
            if lease_seconds < 60 or lease_seconds > 86_400:
                raise PolicyViolationError("intake item has an invalid claim lease")
        return AdmissionPreview(
            cycle=cycle,
            workflow_id=cycle.cycle_id,
            board=registration.board,
            checkout=registration.checkout,
            registration_digest=registration.digest,
            constraints_digest=constraints.digest,
            stage_profiles=profiles,
            intake_digest=intake.digest,
        )

    def admit(
        self,
        *,
        manifest: ProjectManifest,
        registration: ControllerRegistration,
        intake: IntakeRecord,
        baseline_revision: str,
        stage_profiles: dict[str, str],
        constraints_content: str,
        mode: CycleMode = CycleMode.IMPROVE,
        pack_name: str | None = None,
        candidate_identity: str | None = None,
        claim_lease_seconds: int = 900,
    ) -> tuple[CycleAdmission, WorkflowLedger, NotificationReceipt]:
        now = self.clock()
        preview = self._preview(
            manifest=manifest,
            registration=registration,
            intake=intake,
            baseline_revision=baseline_revision,
            stage_profiles=stage_profiles,
            constraints_content=constraints_content,
            mode=mode,
            pack_name=pack_name,
            candidate_identity=candidate_identity,
            claim_lease_seconds=claim_lease_seconds,
            observed_at=now,
        )
        constraints = parse_workflow_constraints(constraints_content)
        profiles = preview.stage_profiles
        cycle = preview.cycle
        snapshot = self.store.materialize_snapshot(cycle, manifest)
        admission = self.store.load_admission(cycle)
        if admission is None:
            requested_claim = ClaimIdentity(
                claimant=cycle.cycle_id,
                claimed_at=now,
                lease_expires_at=now + timedelta(seconds=claim_lease_seconds),
            )
            claimed = self.intake_adapter.claim(intake.item_id, requested_claim)
            _validate_claimed_intake(intake, claimed, cycle.cycle_id, now)
            claim = claimed.claim
            if claim is None:
                raise PolicyViolationError("intake adapter did not return a claim")
            admission = CycleAdmission(
                cycle=cycle,
                workflow_id=cycle.cycle_id,
                board=registration.board,
                checkout=registration.checkout,
                registration_digest=registration.digest,
                constraints_digest=constraints.digest,
                stage_profiles=profiles,
                intake=claimed,
                claim=claim,
                snapshot=snapshot,
                created_at=claim.claimed_at,
            )
            self.store.save_admission(admission)
        else:
            _validate_replay(
                admission,
                cycle,
                registration,
                intake,
                snapshot,
                constraints.digest,
                profiles,
                now,
            )
        receipt = self.store.load_notification(cycle, "admitted")
        event_id = f"{cycle.cycle_id}:admitted"
        if receipt is None:
            payload: dict[str, object] = {
                "event_id": event_id,
                "event": "cycle-admitted",
                "cycle_id": cycle.cycle_id,
                "workflow_id": cycle.cycle_id,
                "project_id": cycle.project_id,
                "intake_item_id": cycle.intake_item_id,
                "manifest_digest": cycle.manifest_digest,
            }
            receipt = self.notification_adapter.deliver(payload)
            if not isinstance(receipt, NotificationReceipt):
                raise PolicyViolationError(
                    "notification adapter returned an invalid receipt type"
                )
            validate_notification_receipt(receipt, registration, event_id)
            self.store.save_notification(cycle, "admitted", receipt)
        else:
            validate_notification_receipt(receipt, registration, event_id)
        ledger = self.workflow.start(
            board_slug=registration.board,
            target_repository=registration.checkout,
            goal=intake.goal,
            stage_profiles={row.stage.value: row.profile for row in profiles},
            pack_name=cycle.pack_name,
            workflow_id=cycle.cycle_id,
            constraints_content=constraints_content,
            expected_baseline_commit=baseline_revision,
        )
        if not isinstance(ledger, WorkflowLedger):
            raise PolicyViolationError("workflow adapter returned an invalid ledger type")
        _validate_workflow_binding(ledger, admission)
        return admission, ledger, receipt


def validate_notification_receipt(
    receipt: NotificationReceipt,
    registration: ControllerRegistration,
    expected_event_id: str,
) -> None:
    if receipt.event_id != expected_event_id:
        raise PolicyViolationError("notification receipt event does not match delivery")
    if receipt.adapter != registration.notification_adapter:
        raise PolicyViolationError("notification receipt adapter does not match registration")
    if receipt.target_alias != registration.notification_target:
        raise PolicyViolationError("notification receipt target does not match registration")


def _validate_claimed_intake(
    original: IntakeRecord,
    claimed: IntakeRecord,
    claimant: str,
    observed_at: datetime,
) -> None:
    if not isinstance(claimed, IntakeRecord):
        raise PolicyViolationError("intake adapter returned an invalid record type")
    original_without_claim = {**original.to_dict(), "claim": None}
    claimed_without_claim = {**claimed.to_dict(), "claim": None}
    if original_without_claim != claimed_without_claim:
        raise PolicyViolationError("intake adapter changed immutable admission fields")
    if claimed.claim is None or claimed.claim.claimant != claimant:
        raise PolicyViolationError("intake adapter returned the wrong claim owner")
    if claimed.claim.claimed_at > observed_at:
        raise PolicyViolationError("intake adapter returned a future claim timestamp")
    if claimed.claim.lease_expires_at <= observed_at:
        raise PolicyViolationError("intake adapter returned an expired claim")
    lease_seconds = (claimed.claim.lease_expires_at - claimed.claim.claimed_at).total_seconds()
    if lease_seconds < 60 or lease_seconds > 86_400:
        raise PolicyViolationError("intake adapter returned an invalid claim lease")


def _validate_replay(
    admission: CycleAdmission,
    cycle: CycleIdentity,
    registration: ControllerRegistration,
    intake: IntakeRecord,
    snapshot: ManifestSnapshot,
    constraints_digest: str,
    stage_profiles: tuple[StageProfile, ...],
    observed_at: datetime,
) -> None:
    if admission.cycle != cycle or admission.snapshot != snapshot:
        raise PolicyViolationError("replayed admission identity conflicts with stored admission")
    if (
        admission.board != registration.board
        or admission.checkout != registration.checkout
        or admission.registration_digest != registration.digest
    ):
        raise PolicyViolationError(
            "replayed admission registration conflicts with stored admission"
        )
    expected_intake = {**intake.to_dict(), "claim": None}
    stored_intake = {**admission.intake.to_dict(), "claim": None}
    if expected_intake != stored_intake:
        raise PolicyViolationError("replayed intake conflicts with stored admission")
    if admission.constraints_digest != constraints_digest:
        raise PolicyViolationError("replayed constraints conflict with stored admission")
    if admission.stage_profiles != stage_profiles:
        raise PolicyViolationError("replayed stage profiles conflict with stored admission")
    if admission.claim.lease_expires_at <= observed_at:
        raise PolicyViolationError("stored admission claim expired before reconciliation")


def _validate_workflow_binding(ledger: WorkflowLedger, admission: CycleAdmission) -> None:
    cycle = admission.cycle
    if ledger.workflow_id != admission.workflow_id:
        raise PolicyViolationError("workflow did not preserve the deterministic cycle identity")
    if ledger.board_slug != admission.board or ledger.target_repository != admission.checkout:
        raise PolicyViolationError("workflow board or repository does not match admission")
    if ledger.baseline_commit != cycle.baseline_revision:
        raise PolicyViolationError("workflow baseline does not match admission")
    if (
        ledger.pack_name != cycle.pack_name
        or ledger.pack_source_revision != cycle.pack_source_revision
    ):
        raise PolicyViolationError("workflow pack identity does not match admission")
    if ledger.stage_profiles != admission.stage_profiles:
        raise PolicyViolationError("workflow stage profiles do not match admission")


def _normalize_stage_profiles(values: dict[str, str]) -> tuple[StageProfile, ...]:
    if not isinstance(values, dict):
        raise PolicyViolationError("stage profiles must be an object")
    if any(
        not isinstance(stage, str) or not isinstance(profile, str)
        for stage, profile in values.items()
    ):
        raise PolicyViolationError("stage profiles must map strings to strings")
    expected = {stage.value for stage in WorkflowStage if stage is not WorkflowStage.APPROVAL}
    if set(values) != expected:
        missing = sorted(expected - set(values))
        unknown = sorted(set(values) - expected)
        raise PolicyViolationError(
            f"stage profiles must map every executable stage; missing={missing!r}, "
            f"unknown={unknown!r}"
        )
    return tuple(
        StageProfile(stage=stage, profile=values[stage.value])
        for stage in WorkflowStage
        if stage is not WorkflowStage.APPROVAL
    )


def _require_cycle_id(value: Any) -> None:
    if not isinstance(value, str) or not _CYCLE_ID.fullmatch(value):
        raise PolicyViolationError("cycle ID must be cycle- followed by 64 lowercase hex digits")
