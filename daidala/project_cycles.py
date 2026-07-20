"""Dry-run-first operator service for one self-improvement project cycle."""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from .adapters import IntakeRecord, NotificationReceipt
from .controller import (
    AdmissionCoordinator,
    AdmissionPreview,
    CycleAdmission,
    CycleArtifactStore,
    WorkflowStarter,
)
from .credentials import (
    MAX_CREDENTIAL_BINDINGS_BYTES,
    credential_bindings_path,
    parse_credential_bindings,
)
from .errors import PolicyViolationError
from .live_adapters import (
    GitHubIssueIntakeAdapter,
    HermesGatewayNotificationAdapter,
    RuntimeRunner,
    run_runtime_command,
    safe_runtime_environment,
)
from .prerequisites import CheckStatus, PrerequisiteReport, run_prerequisite_diagnosis
from .projects import MAX_MANIFEST_BYTES, ProjectManifest, parse_project_manifest
from .registrations import (
    MAX_REGISTRATION_BYTES,
    ControllerRegistration,
    parse_controller_registration,
    registration_path,
)
from .state import WorkflowLedger

MAX_CONSTRAINTS_BYTES = 1_048_576
_REVISION = re.compile(r"^[0-9a-f]{40}$")

DiagnosisRunner = Callable[..., PrerequisiteReport]
WorkflowFactory = Callable[
    [Path, RuntimeRunner, Mapping[str, str]], WorkflowStarter
]


@dataclass(frozen=True)
class ProjectCycleResult:
    preview: AdmissionPreview
    admission: CycleAdmission
    workflow: WorkflowLedger
    receipt: NotificationReceipt

    def to_dict(self) -> dict[str, object]:
        return {
            "dry_run": False,
            "preview": self.preview.to_dict(),
            "admission": {
                "cycle_id": self.admission.cycle.cycle_id,
                "workflow_id": self.admission.workflow_id,
                "board": self.admission.board,
                "checkout": self.admission.checkout,
                "intake_item_id": self.admission.intake.item_id,
                "intake_digest": self.admission.intake.digest,
                "claim": self.admission.claim.to_dict(),
            },
            "workflow": {
                "workflow_id": self.workflow.workflow_id,
            },
            "receipt": self.receipt.to_dict(),
        }


@dataclass(frozen=True)
class _PreparedProjectCycle:
    profile_root: Path
    manifest: ProjectManifest
    registration: ControllerRegistration
    intake: IntakeRecord
    baseline_revision: str
    stage_profiles: dict[str, str]
    constraints_content: str
    pack_name: str | None
    claim_lease_seconds: int
    intake_adapter: GitHubIssueIntakeAdapter
    notification_adapter: HermesGatewayNotificationAdapter
    preview: AdmissionPreview


class ProjectCycleOperator:
    """Run prerequisite diagnosis, preview exact identity, then admit on apply."""

    def __init__(
        self,
        *,
        runner: RuntimeRunner | None = None,
        environ: Mapping[str, str] | None = None,
        diagnose: DiagnosisRunner = run_prerequisite_diagnosis,
        workflow_factory: WorkflowFactory | None = None,
    ) -> None:
        self.runner = runner or run_runtime_command
        self.environ = dict(os.environ if environ is None else environ)
        self.diagnose = diagnose
        self.workflow_factory = workflow_factory or _default_workflow_factory

    def preview(
        self,
        *,
        project_manifest: Path,
        registration: Path,
        issue_id: str,
        stage_profiles: dict[str, str],
        pack_name: str | None = None,
        claim_lease_seconds: int = 900,
    ) -> AdmissionPreview:
        return self._prepare(
            project_manifest=project_manifest,
            registration_file=registration,
            issue_id=issue_id,
            stage_profiles=stage_profiles,
            pack_name=pack_name,
            claim_lease_seconds=claim_lease_seconds,
        ).preview

    def admit(
        self,
        *,
        project_manifest: Path,
        registration: Path,
        issue_id: str,
        stage_profiles: dict[str, str],
        expected_cycle_id: str,
        expected_intake_digest: str,
        pack_name: str | None = None,
        claim_lease_seconds: int = 900,
    ) -> ProjectCycleResult:
        prepared = self._prepare(
            project_manifest=project_manifest,
            registration_file=registration,
            issue_id=issue_id,
            stage_profiles=stage_profiles,
            pack_name=pack_name,
            claim_lease_seconds=claim_lease_seconds,
        )
        if prepared.preview.cycle.cycle_id != expected_cycle_id:
            raise PolicyViolationError(
                "expected cycle ID does not match the current dry-run preview"
            )
        if prepared.preview.intake_digest != expected_intake_digest:
            raise PolicyViolationError(
                "expected intake digest does not match the current dry-run preview"
            )
        workflow = self.workflow_factory(prepared.profile_root, self.runner, self.environ)
        coordinator = AdmissionCoordinator(
            store=CycleArtifactStore(prepared.profile_root),
            workflow=workflow,
            intake_adapter=prepared.intake_adapter,
            notification_adapter=prepared.notification_adapter,
        )
        admission, ledger, receipt = coordinator.admit(
            manifest=prepared.manifest,
            registration=prepared.registration,
            intake=prepared.intake,
            baseline_revision=prepared.baseline_revision,
            stage_profiles=prepared.stage_profiles,
            constraints_content=prepared.constraints_content,
            pack_name=prepared.pack_name,
            claim_lease_seconds=prepared.claim_lease_seconds,
        )
        return ProjectCycleResult(prepared.preview, admission, ledger, receipt)

    def _prepare(
        self,
        *,
        project_manifest: Path,
        registration_file: Path,
        issue_id: str,
        stage_profiles: dict[str, str],
        pack_name: str | None,
        claim_lease_seconds: int,
    ) -> _PreparedProjectCycle:
        manifest_path = project_manifest.expanduser().resolve(strict=True)
        registration_file = registration_file.expanduser().resolve(strict=True)
        manifest = parse_project_manifest(
            _read_bounded(manifest_path, "project manifest", MAX_MANIFEST_BYTES)
        )
        registration = parse_controller_registration(
            _read_bounded(
                registration_file, "controller registration", MAX_REGISTRATION_BYTES
            )
        )
        registration.validate_manifest(manifest)
        profile_root = registration_file.parents[2]
        if registration_path(profile_root, registration.project_id) != registration_file:
            raise PolicyViolationError(
                "controller registration is outside its profile-local project path"
            )
        bindings_file = credential_bindings_path(registration_file)
        bindings = parse_credential_bindings(
            _read_bounded(
                bindings_file,
                "credential bindings",
                MAX_CREDENTIAL_BINDINGS_BYTES,
            )
        )
        if bindings.project_id != manifest.project_id:
            raise PolicyViolationError("credential bindings project ID does not match manifest")
        report = self.diagnose(
            project_manifest=manifest_path,
            registration=registration_file,
            live=True,
            runner=self.runner,
            environ=self.environ,
        )
        if report.status is not CheckStatus.PASS:
            raise PolicyViolationError(
                "live prerequisite diagnosis must pass before project-cycle admission"
            )
        baseline_revision = self._baseline(registration)
        checkout = Path(registration.checkout).resolve(strict=True)
        constraints_path = (checkout / manifest.default_constraints_source).resolve(strict=True)
        try:
            constraints_path.relative_to(checkout)
        except ValueError as error:
            raise PolicyViolationError(
                "default constraints path escapes the registered checkout"
            ) from error
        constraints_content = _read_bounded(
            constraints_path, "workflow constraints", MAX_CONSTRAINTS_BYTES
        )
        intake_adapter = GitHubIssueIntakeAdapter(
            repository=registration.repository_canonical,
            read_credential_alias=registration.intake_credential,
            write_credential_alias=registration.findings_credential,
            credential_bindings=bindings,
            authorized_actors=registration.maintainers,
            runner=self.runner,
            environ=self.environ,
        )
        notification_adapter = HermesGatewayNotificationAdapter(
            profile=registration.controller_profile,
            target_alias=registration.notification_target,
            destination=registration.notification_destination,
            runner=self.runner,
            environ=self.environ,
        )
        intake = intake_adapter.fetch(issue_id)
        coordinator = AdmissionCoordinator(
            store=CycleArtifactStore(profile_root),
            workflow=_PreviewOnlyWorkflow(),
            intake_adapter=intake_adapter,
            notification_adapter=notification_adapter,
        )
        preview = coordinator.preview(
            manifest=manifest,
            registration=registration,
            intake=intake,
            baseline_revision=baseline_revision,
            stage_profiles=stage_profiles,
            constraints_content=constraints_content,
            pack_name=pack_name,
            claim_lease_seconds=claim_lease_seconds,
        )
        return _PreparedProjectCycle(
            profile_root=profile_root,
            manifest=manifest,
            registration=registration,
            intake=intake,
            baseline_revision=baseline_revision,
            stage_profiles=stage_profiles,
            constraints_content=constraints_content,
            pack_name=pack_name,
            claim_lease_seconds=claim_lease_seconds,
            intake_adapter=intake_adapter,
            notification_adapter=notification_adapter,
            preview=preview,
        )

    def _baseline(self, registration: ControllerRegistration) -> str:
        environment = safe_runtime_environment(self.environ)
        revision = self._run(
            ("git", "-C", registration.checkout, "rev-parse", "HEAD"),
            environment,
            "repository baseline",
        ).strip()
        if not _REVISION.fullmatch(revision):
            raise PolicyViolationError("repository baseline is not a full Git revision")
        status = self._run(
            ("git", "-C", registration.checkout, "status", "--short"),
            environment,
            "repository status",
        )
        if status.strip():
            raise PolicyViolationError("registered checkout must be clean before admission")
        remote = self._run(
            ("git", "-C", registration.checkout, "remote", "get-url", "origin"),
            environment,
            "repository remote",
        ).strip()
        if remote != registration.verified_remote:
            raise PolicyViolationError("repository remote does not match trusted registration")
        return revision

    def _run(
        self,
        command: tuple[str, ...],
        environment: Mapping[str, str],
        label: str,
    ) -> str:
        code, output = self.runner(command, environment)
        if isinstance(code, bool) or not isinstance(code, int) or not isinstance(output, str):
            raise PolicyViolationError(f"{label} runner returned invalid output")
        if len(output.encode("utf-8")) > MAX_CONSTRAINTS_BYTES:
            raise PolicyViolationError(f"{label} output exceeds its byte bound")
        if code != 0:
            raise PolicyViolationError(f"{label} failed with exit code {code}")
        return output


class _PreviewOnlyWorkflow:
    def start(self, **kwargs: object) -> WorkflowLedger:
        raise AssertionError("dry-run preview must not create a workflow")


def _default_workflow_factory(
    profile_root: Path,
    runner: RuntimeRunner,
    environ: Mapping[str, str],
) -> WorkflowStarter:
    # Imported lazily to avoid a module cycle: cli dispatch imports this operator.
    from .cli import build_cli_service

    environment = safe_runtime_environment(environ)
    return build_cli_service(
        command_runner=lambda command: runner(command, environment),
        data_root=profile_root,
    )


def _read_bounded(path: Path, label: str, maximum_bytes: int) -> str:
    try:
        content = path.read_bytes()
    except OSError as error:
        raise PolicyViolationError(f"cannot read {label}") from error
    if len(content) > maximum_bytes:
        raise PolicyViolationError(f"{label} exceeds {maximum_bytes} bytes")
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise PolicyViolationError(f"{label} is not UTF-8") from error
