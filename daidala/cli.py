"""Shared standalone and Hermes-native Daidala operator CLI."""

from __future__ import annotations

import argparse
import getpass
import json
import re
import shlex
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import NoReturn, cast

from .artifact_curator import CuratorPolicy
from .cycles import CycleMode
from .evaluation import EvaluatorIsolationEvidence
from .initialization import apply_initialization, preview_initialization
from .kanban import KanbanGraphAdapter
from .locations import resolve_data_root
from .pack_service import PackCheck, PackService
from .prerequisites import DoctorRunner, run_prerequisite_diagnosis
from .project_cycles import ProjectCycleOperator
from .reconciliation import ReconciliationPreview, ReconciliationResult
from .restricted_container import (
    RestrictedContainerEvidence,
    RestrictedContainerExecutor,
    RestrictedContainerRequest,
    load_restricted_container_request,
    probe_restricted_container,
    run_restricted_container_request,
)
from .revision import MAX_REVIEW_FEEDBACK_BYTES
from .service import WorkflowService
from .skills import ProfileSkillContentRegistry, SkillContentRegistry, SkillInventory
from .state import WorkflowStage
from .store import WorkflowStore

CommandRunner = Callable[[tuple[str, ...]], tuple[int, str]]
RevisionResolver = Callable[[str], str]
ServiceFactory = Callable[[], WorkflowService]
ContainerProbe = Callable[[str], EvaluatorIsolationEvidence]
ContainerRequestRunner = Callable[
    [RestrictedContainerRequest, Path], tuple[RestrictedContainerEvidence, Path]
]
ProjectCycleFactory = Callable[[], ProjectCycleOperator]


def register_cli(parser: argparse.ArgumentParser) -> None:
    """Register the command tree shared by ``daidala`` and ``hermes daidala``."""
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Preview or initialize the profile-local policy ledger")
    init.add_argument("--apply", action="store_true", help="Create the ledger directory and schema")
    init.add_argument(
        "--preview-digest", help="Fresh initialization preview digest required by --apply"
    )
    init.add_argument(
        "--confirm", action="store_true", help="Confirm the exact initialization preview"
    )

    doctor = sub.add_parser(
        "doctor", help="Diagnose self-improvement prerequisites without mutation"
    )
    doctor.add_argument("--project-manifest", required=True, type=Path)
    doctor.add_argument("--registration", type=Path)
    doctor.add_argument(
        "--live",
        action="store_true",
        help="Run bounded GitHub, gateway, and container availability probes",
    )

    evaluator = sub.add_parser(
        "evaluator", help="Inspect or exercise the restricted-container boundary"
    )
    evaluator_sub = evaluator.add_subparsers(dest="evaluator_command", required=True)
    evaluator_probe = evaluator_sub.add_parser(
        "probe", help="Plan or run one disposable evaluator-isolation probe"
    )
    evaluator_probe.add_argument(
        "--image",
        required=True,
        help="Existing immutable evaluator image as name@sha256:<digest>",
    )
    evaluator_probe.add_argument(
        "--apply",
        action="store_true",
        help="Create the disposable denied-network container and emit evidence",
    )
    evaluator_run = evaluator_sub.add_parser(
        "run", help="Plan or run one strict evaluator request and retain evidence"
    )
    evaluator_run.add_argument("--request", required=True, type=Path)
    evaluator_run.add_argument(
        "--apply",
        action="store_true",
        help="Run the request and retain immutable content-addressed evidence",
    )

    project_cycle = sub.add_parser(
        "project-cycle", help="Preview or admit one registered self-improvement cycle"
    )
    project_cycle_sub = project_cycle.add_subparsers(
        dest="project_cycle_command", required=True
    )
    project_cycle_admit = project_cycle_sub.add_parser(
        "admit", help="Validate exact admission identity; mutate only with --apply"
    )
    project_cycle_admit.add_argument("--project-manifest", required=True, type=Path)
    project_cycle_admit.add_argument("--registration", required=True, type=Path)
    project_cycle_admit.add_argument("--issue", required=True, dest="issue_id")
    project_cycle_admit.add_argument(
        "--default-profile", dest="profile", required=True
    )
    project_cycle_admit.add_argument(
        "--stage-profile",
        action="append",
        default=[],
        metavar="STAGE=PROFILE",
    )
    project_cycle_admit.add_argument("--pack")
    project_cycle_admit.add_argument(
        "--mode",
        type=CycleMode,
        choices=tuple(CycleMode),
        default=CycleMode.IMPROVE,
    )
    project_cycle_admit.add_argument("--candidate-identity")
    project_cycle_admit.add_argument(
        "--claim-lease-seconds", type=int, default=900
    )
    project_cycle_admit.add_argument("--apply", action="store_true")
    project_cycle_admit.add_argument("--expected-cycle-id")
    project_cycle_admit.add_argument("--expected-intake-digest")
    project_cycle_reconcile = project_cycle_sub.add_parser(
        "reconcile", help="Preview deterministic intake reconciliation; mutate only with --apply"
    )
    project_cycle_reconcile.add_argument("--project-manifest", required=True, type=Path)
    project_cycle_reconcile.add_argument("--registration", required=True, type=Path)
    project_cycle_reconcile.add_argument(
        "--default-profile", dest="profile", required=True
    )
    project_cycle_reconcile.add_argument(
        "--stage-profile",
        action="append",
        default=[],
        metavar="STAGE=PROFILE",
    )
    project_cycle_reconcile.add_argument("--pack")
    project_cycle_reconcile.add_argument("--candidate-limit", type=int, default=100)
    project_cycle_reconcile.add_argument(
        "--claim-lease-seconds", type=int, default=900
    )
    project_cycle_reconcile.add_argument("--apply", action="store_true")
    project_cycle_reconcile.add_argument("--expected-preview-digest")
    project_cycle_complete = project_cycle_sub.add_parser(
        "complete", help="Preview or complete one delivered cycle"
    )
    project_cycle_complete.add_argument("--project-manifest", required=True, type=Path)
    project_cycle_complete.add_argument("--registration", required=True, type=Path)
    project_cycle_complete.add_argument("--cycle-id", required=True)
    project_cycle_complete.add_argument("--apply", action="store_true")
    project_cycle_complete.add_argument("--expected-preview-digest")
    project_cycle_cancel = project_cycle_sub.add_parser(
        "cancel", help="Preview or cancel one claimed cycle without implementation"
    )
    project_cycle_cancel.add_argument("--project-manifest", required=True, type=Path)
    project_cycle_cancel.add_argument("--registration", required=True, type=Path)
    project_cycle_cancel.add_argument("--cycle-id", required=True)
    project_cycle_cancel.add_argument("--reason", required=True)
    project_cycle_cancel.add_argument("--apply", action="store_true")
    project_cycle_cancel.add_argument("--expected-preview-digest")

    start = sub.add_parser("start", help="Validate inputs and create the initial Kanban graph")
    start.add_argument("target_repository")
    start.add_argument("goal")
    start.add_argument("--board", required=True, dest="board_slug")
    start.add_argument(
        "--default-profile",
        dest="profile",
        required=True,
        help="Default existing Hermes profile for every executable stage",
    )
    start.add_argument(
        "--stage-profile",
        action="append",
        default=[],
        metavar="STAGE=PROFILE",
        help="Override the default profile for one executable stage (repeatable)",
    )
    start.add_argument("--pack", default="addyosmani")
    start.add_argument("--workflow-id", required=True)
    _add_constraint_source_arguments(start)

    status = sub.add_parser(
        "status", help="Show Daidala policy facts and live Kanban card status"
    )
    status.add_argument("workflow_id")

    artifacts = sub.add_parser(
        "artifacts", help="Review exact ledger-owned workflow artifacts"
    )
    artifacts_sub = artifacts.add_subparsers(dest="artifacts_command", required=True)
    artifacts_list = artifacts_sub.add_parser("list", help="List exact artifact metadata")
    artifacts_list.add_argument("workflow_id")
    artifacts_list.add_argument("--json", action="store_true", dest="as_json")
    artifacts_show = artifacts_sub.add_parser(
        "show", help="Write one verified text artifact"
    )
    artifacts_show.add_argument("workflow_id")
    artifacts_show.add_argument("artifact_id")
    artifacts_export = artifacts_sub.add_parser(
        "export", help="Export one verified artifact"
    )
    artifacts_export.add_argument("workflow_id")
    artifacts_export.add_argument("artifact_id")
    artifacts_export.add_argument("--output", required=True, type=Path)
    artifacts_export.add_argument("--overwrite", action="store_true")

    curator = sub.add_parser(
        "curator", help="Preview or apply profile-local artifact lifecycle operations"
    )
    curator_sub = curator.add_subparsers(dest="curator_command", required=True)
    curator_sub.add_parser("status", help="Show policy and classified curator state")
    curator_configure = curator_sub.add_parser(
        "configure", help="Preview or apply the profile-local curator policy"
    )
    enabled = curator_configure.add_mutually_exclusive_group(required=True)
    enabled.add_argument("--enabled", action="store_true", dest="curator_enabled")
    enabled.add_argument("--disabled", action="store_false", dest="curator_enabled")
    curator_configure.add_argument("--stale-after-days", required=True, type=int)
    curator_configure.add_argument("--archive-after-days", required=True, type=int)
    curator_configure.add_argument("--apply", action="store_true")
    curator_configure.add_argument("--expected-state-digest")
    curator_configure.add_argument("--confirm-policy-digest")
    curator_run = curator_sub.add_parser("run", help="Preview or run eligible transitions")
    curator_sub.add_parser(
        "tick",
        help="Run the registered script-only Cron tick and stay silent when no work is due",
    )
    curator_schedule = curator_sub.add_parser(
        "schedule", help="Preview or apply the profile-local Hermes Cron registration"
    )
    curator_schedule_sub = curator_schedule.add_subparsers(
        dest="curator_schedule_command", required=True
    )
    curator_schedule_sub.add_parser("status", help="Show the recorded exact Cron job")
    curator_schedule_setup = curator_schedule_sub.add_parser(
        "setup", help="Preview or create/update one script-only Cron job"
    )
    curator_schedule_setup.add_argument("interval")
    curator_schedule_remove = curator_schedule_sub.add_parser(
        "remove", help="Preview or remove the recorded exact Cron job"
    )
    for mutation in (curator_schedule_setup, curator_schedule_remove):
        mutation.add_argument("--apply", action="store_true")
        mutation.add_argument("--expected-preview-digest")
        mutation.add_argument("--confirm-controller-profile")
    curator_pin = curator_sub.add_parser("pin", help="Preview or pin one workflow")
    curator_pin.add_argument("workflow_id")
    curator_unpin = curator_sub.add_parser("unpin", help="Preview or unpin one workflow")
    curator_unpin.add_argument("workflow_id")
    curator_archive = curator_sub.add_parser(
        "archive", help="Preview or archive one safely terminal workflow"
    )
    curator_archive.add_argument("workflow_id")
    curator_sub.add_parser("list-archived", help="List path-free archive metadata")
    curator_restore = curator_sub.add_parser(
        "restore", help="Preview or restore one archive into its safe recovery root"
    )
    curator_restore.add_argument("workflow_id")
    curator_restore.add_argument("archive_id")
    for mutation in (
        curator_run,
        curator_pin,
        curator_unpin,
        curator_archive,
        curator_restore,
    ):
        mutation.add_argument("--apply", action="store_true")
        mutation.add_argument("--expected-preview-digest")

    replace_constraints = sub.add_parser(
        "replace-constraints",
        help="Replace workflow constraints from a file or exact installed policy skill",
    )
    replace_constraints.add_argument("workflow_id")
    replace_constraints.add_argument("expected_current_digest", nargs="?", default=None)
    _add_constraint_source_arguments(replace_constraints, required=True)

    approve = sub.add_parser("approve", help="Approve the exact current plan digest")
    approve.add_argument("workflow_id")
    approve.add_argument("plan_digest")

    review = sub.add_parser("review", help="Inspect or decide the attended review gate")
    review_sub = review.add_subparsers(dest="review_command", required=True)
    review_show = review_sub.add_parser("show", help="Show the bounded current review packet")
    review_show.add_argument("workflow_id")
    review_decide = review_sub.add_parser(
        "decide", help="Preview or apply one exact attended review action"
    )
    review_decide.add_argument("workflow_id")
    review_decide.add_argument(
        "action",
        choices=("accept-delivery", "request-revision", "reject-workflow"),
    )
    review_decide.add_argument("--rationale-file", required=True, type=Path)
    review_decide.add_argument("--apply", action="store_true")
    review_decide.add_argument("--expected-review-digest")
    review_decide.add_argument("--expected-preview-digest")

    cancel = sub.add_parser(
        "cancel", help="Archive workflow cards and clean the Daidala-owned worktree"
    )
    cancel.add_argument("workflow_id")
    cancel.add_argument("reason")

    packs = sub.add_parser("packs", help="Inspect or install workflow-pack dependencies")
    packs_sub = packs.add_subparsers(dest="packs_command", required=True)
    packs_sub.add_parser("list", help="List bundled workflow packs")

    validate = packs_sub.add_parser("validate", help="Validate a bundled pack")
    validate.add_argument("name")

    install = packs_sub.add_parser(
        "install", help="Plan or apply pinned external skill installation"
    )
    install.add_argument("name")
    install.add_argument(
        "--apply", action="store_true", help="Apply the displayed missing-skill mutations"
    )
    install.add_argument(
        "--recursive",
        action="store_true",
        help="Request recursive installation when the host supports it",
    )

    check = packs_sub.add_parser(
        "check", help="Check installed skill names, content, source, and host version"
    )
    check.add_argument("name")

    update_plan = packs_sub.add_parser(
        "update-plan", help="Plan controlled changes without mutating installed skills"
    )
    update_plan.add_argument("name")


def _add_constraint_source_arguments(
    parser: argparse.ArgumentParser, *, required: bool = False
) -> None:
    source = parser.add_mutually_exclusive_group(required=required)
    source.add_argument(
        "--constraints-file",
        type=Path,
        help="Read one workflow-constraint YAML document from this UTF-8 file",
    )
    source.add_argument(
        "--constraints-skill",
        help="Resolve an exact installed policy skill containing one fenced YAML document",
    )
    parser.add_argument(
        "--constraints-skill-digest",
        help="Expected SHA-256 digest of the complete installed policy-skill directory",
    )


def _constraint_source_values(args: argparse.Namespace) -> dict[str, str | None]:
    path = getattr(args, "constraints_file", None)
    skill = getattr(args, "constraints_skill", None)
    digest = getattr(args, "constraints_skill_digest", None)
    if path is not None:
        if digest is not None:
            raise ValueError("--constraints-skill-digest requires --constraints-skill")
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise ValueError(f"cannot read constraint file: {path}") from error
        return {
            "constraints_content": content,
            "constraints_skill": None,
            "constraints_skill_digest": None,
        }
    if skill is not None and digest is None:
        raise ValueError("--constraints-skill requires --constraints-skill-digest")
    if skill is None and digest is not None:
        raise ValueError("--constraints-skill-digest requires --constraints-skill")
    return {
        "constraints_content": None,
        "constraints_skill": skill,
        "constraints_skill_digest": digest,
    }


def build_parser(*, prog: str = "daidala") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog)
    register_cli(parser)
    return parser


def dispatch_cli(args: argparse.Namespace) -> NoReturn:
    """Hermes callback that preserves process exit codes on the v0.18.2 host."""
    # Hermes v0.18.2 invokes plugin callbacks but discards their return values.
    # SystemExit is therefore the only argparse-compatible process-code boundary.
    raise SystemExit(run_command(args))


def main(
    argv: list[str] | None = None,
    *,
    inventory: SkillInventory | None = None,
    registry: SkillContentRegistry | None = None,
    revision_resolver: RevisionResolver | None = None,
    hermes_version: str | None = None,
    command_runner: CommandRunner | None = None,
    service_factory: ServiceFactory | None = None,
    doctor_runner: DoctorRunner | None = None,
    doctor_environ: Mapping[str, str] | None = None,
    container_probe: ContainerProbe | None = None,
    container_request_runner: ContainerRequestRunner | None = None,
    project_cycle_factory: ProjectCycleFactory | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    return run_command(
        args,
        inventory=inventory,
        registry=registry,
        revision_resolver=revision_resolver,
        hermes_version=hermes_version,
        command_runner=command_runner,
        service_factory=service_factory,
        doctor_runner=doctor_runner,
        doctor_environ=doctor_environ,
        container_probe=container_probe,
        container_request_runner=container_request_runner,
        project_cycle_factory=project_cycle_factory,
    )


def run_command(
    args: argparse.Namespace,
    *,
    inventory: SkillInventory | None = None,
    registry: SkillContentRegistry | None = None,
    revision_resolver: RevisionResolver | None = None,
    hermes_version: str | None = None,
    command_runner: CommandRunner | None = None,
    service_factory: ServiceFactory | None = None,
    doctor_runner: DoctorRunner | None = None,
    doctor_environ: Mapping[str, str] | None = None,
    container_probe: ContainerProbe | None = None,
    container_request_runner: ContainerRequestRunner | None = None,
    project_cycle_factory: ProjectCycleFactory | None = None,
) -> int:
    """Execute one parsed command and return its process exit code."""
    try:
        if args.command == "init":
            return _run_init(args)
        if args.command == "doctor":
            report = run_prerequisite_diagnosis(
                project_manifest=args.project_manifest,
                registration=args.registration,
                live=args.live,
                runner=doctor_runner,
                environ=doctor_environ,
            )
            _print(report.to_dict())
            return report.exit_code
        if args.command == "evaluator":
            return _run_evaluator(
                args,
                container_probe=container_probe,
                container_request_runner=container_request_runner,
            )
        if args.command == "project-cycle":
            selected_project_cycle_factory = (
                project_cycle_factory or ProjectCycleOperator
            )
            return _run_project_cycle(args, selected_project_cycle_factory)
        if args.command in {
            "start",
            "status",
            "artifacts",
            "curator",
            "replace-constraints",
            "approve",
            "review",
            "cancel",
        }:
            selected_factory = service_factory or (
                lambda: _default_service(command_runner=command_runner)
            )
            return _run_lifecycle(args, selected_factory)
        if args.command == "packs":
            return _run_pack_operation(
                args,
                inventory=inventory,
                registry=registry,
                revision_resolver=revision_resolver,
                hermes_version=hermes_version,
                command_runner=command_runner,
            )
        raise ValueError(f"unsupported command: {args.command}")
    except Exception as exc:  # noqa: BLE001 - process boundary
        _print({"success": False, "error": type(exc).__name__, "message": str(exc)})
        return 1


def _run_evaluator(
    args: argparse.Namespace,
    *,
    container_probe: ContainerProbe | None,
    container_request_runner: ContainerRequestRunner | None,
) -> int:
    if args.evaluator_command == "run":
        request = load_restricted_container_request(args.request)
        if not args.apply:
            _print(
                {
                    "success": True,
                    "operation": "evaluator-run",
                    "dry_run": True,
                    "request_digest": request.digest,
                    "request": request.to_dict(),
                    "policy": RestrictedContainerExecutor(
                        request.image_identity
                    ).policy(),
                }
            )
            return 0
        selected_runner = container_request_runner or run_restricted_container_request
        evidence, path = selected_runner(request, resolve_data_root() / "daidala")
        matched = evidence.exit_code == evidence.expected_exit_code
        _print(
            {
                "success": matched,
                "operation": "evaluator-run",
                "dry_run": False,
                "evidence_digest": evidence.digest,
                "evidence_path": str(path),
                "evidence": evidence.to_dict(),
            }
        )
        return 0 if matched else 1
    if args.evaluator_command != "probe":
        raise ValueError(f"unsupported evaluator command: {args.evaluator_command}")
    if not args.apply:
        policy = RestrictedContainerExecutor(args.image).policy()
        _print(
            {
                "success": True,
                "operation": "evaluator-probe",
                "dry_run": True,
                "policy": policy,
            }
        )
        return 0
    selected_probe = container_probe or probe_restricted_container
    evidence = selected_probe(args.image)
    _print(
        {
            "success": True,
            "operation": "evaluator-probe",
            "dry_run": False,
            "evidence": evidence.to_dict(),
        }
    )
    return 0


def _run_project_cycle(
    args: argparse.Namespace, project_cycle_factory: ProjectCycleFactory
) -> int:
    if args.project_cycle_command == "reconcile":
        operator = project_cycle_factory()
        common = {
            "project_manifest": args.project_manifest,
            "registration": args.registration,
            "stage_profiles": _parse_stage_profiles(args.profile, args.stage_profile),
            "pack_name": args.pack,
            "candidate_limit": args.candidate_limit,
            "claim_lease_seconds": args.claim_lease_seconds,
        }
        if not args.apply:
            if args.expected_preview_digest is not None:
                raise ValueError("expected reconciliation preview digest requires --apply")
            preview = operator.preview_reconciliation(**common)
            _print(
                _reconciliation_output(
                    preview=preview,
                    result=None,
                    project_manifest=args.project_manifest,
                    registration=args.registration,
                )
            )
            return 0
        if args.expected_preview_digest is None:
            raise ValueError("--apply requires --expected-preview-digest")
        result = operator.reconcile(
            **common,
            expected_preview_digest=args.expected_preview_digest,
        )
        _print(
            _reconciliation_output(
                preview=result.preview,
                result=result,
                project_manifest=args.project_manifest,
                registration=args.registration,
            )
        )
        return 0
    if args.project_cycle_command == "cancel":
        operator = project_cycle_factory()
        common = {
            "project_manifest": args.project_manifest,
            "registration": args.registration,
            "cycle_id": args.cycle_id,
            "reason": args.reason,
        }
        if not args.apply:
            if args.expected_preview_digest is not None:
                raise ValueError("expected cancellation preview digest requires --apply")
            preview = operator.preview_cancellation(**common)
            _print(
                {
                    "success": True,
                    "operation": "project-cycle-cancel",
                    "dry_run": True,
                    "preview_digest": preview.digest,
                    "preview": preview.to_dict(),
                }
            )
            return 0
        if args.expected_preview_digest is None:
            raise ValueError("--apply requires --expected-preview-digest")
        result = operator.cancel_cycle(
            **common,
            expected_preview_digest=args.expected_preview_digest,
        )
        _print(
            {
                "success": True,
                "operation": "project-cycle-cancel",
                **result.to_dict(),
            }
        )
        return 0
    if args.project_cycle_command == "complete":
        operator = project_cycle_factory()
        common = {
            "project_manifest": args.project_manifest,
            "registration": args.registration,
            "cycle_id": args.cycle_id,
        }
        if not args.apply:
            if args.expected_preview_digest is not None:
                raise ValueError("expected completion preview digest requires --apply")
            preview = operator.preview_completion(**common)
            _print(
                {
                    "success": True,
                    "operation": "project-cycle-complete",
                    "dry_run": True,
                    "preview_digest": preview.digest,
                    "preview": preview.to_dict(),
                }
            )
            return 0
        if args.expected_preview_digest is None:
            raise ValueError("--apply requires --expected-preview-digest")
        result = operator.complete(
            **common,
            expected_preview_digest=args.expected_preview_digest,
        )
        _print(
            {
                "success": True,
                "operation": "project-cycle-complete",
                **result.to_dict(),
            }
        )
        return 0
    if args.project_cycle_command != "admit":
        raise ValueError(f"unsupported project-cycle command: {args.project_cycle_command}")
    if args.mode is CycleMode.IMPROVE and args.candidate_identity is not None:
        raise ValueError("--candidate-identity requires a comparison mode")
    if args.mode is not CycleMode.IMPROVE and args.candidate_identity is None:
        raise ValueError(f"--mode {args.mode.value} requires --candidate-identity")
    operator = project_cycle_factory()
    common = {
        "project_manifest": args.project_manifest,
        "registration": args.registration,
        "issue_id": args.issue_id,
        "stage_profiles": _parse_stage_profiles(args.profile, args.stage_profile),
        "mode": args.mode,
        "pack_name": args.pack,
        "candidate_identity": args.candidate_identity,
        "claim_lease_seconds": args.claim_lease_seconds,
    }
    if not args.apply:
        if args.expected_cycle_id is not None or args.expected_intake_digest is not None:
            raise ValueError("expected admission identity arguments require --apply")
        preview = operator.preview(**common)
        _print(
            {
                "success": True,
                "operation": "project-cycle-admit",
                "dry_run": True,
                "preview": preview.to_dict(),
            }
        )
        return 0
    if args.expected_cycle_id is None or args.expected_intake_digest is None:
        raise ValueError(
            "--apply requires --expected-cycle-id and --expected-intake-digest"
        )
    result = operator.admit(
        **common,
        expected_cycle_id=args.expected_cycle_id,
        expected_intake_digest=args.expected_intake_digest,
    )
    _print(
        {
            "success": True,
            "operation": "project-cycle-admit",
            **result.to_dict(),
        }
    )
    return 0


def _reconciliation_output(
    *,
    preview: ReconciliationPreview,
    result: ReconciliationResult | None,
    project_manifest: Path,
    registration: Path,
) -> dict[str, object]:
    workflow_id = preview.workflow_id
    if workflow_id is None:
        inspection = shlex.join(
            (
                "hermes",
                "-p",
                preview.controller_profile,
                "daidala",
                "doctor",
                "--project-manifest",
                str(project_manifest),
                "--registration",
                str(registration),
                "--live",
            )
        )
    else:
        inspection = shlex.join(
            (
                "hermes",
                "-p",
                preview.controller_profile,
                "daidala",
                "status",
                workflow_id,
            )
        )
    return {
        "success": True,
        "operation": "project-cycle-reconcile",
        "dry_run": result is None,
        "preview_digest": preview.digest,
        "outcome": preview.outcome.value if result is None else result.outcome.value,
        "selected_issue_id": preview.intake_item_id,
        "cycle_id": preview.cycle_id,
        "workflow_id": workflow_id,
        "board": preview.board,
        "current_stage": None,
        "receipt_ids": (
            [] if result is None else [row.receipt_id for row in result.notification_receipts]
        ),
        "inspection_command": inspection,
        "preview": preview.to_dict(),
    }


def _run_init(args: argparse.Namespace) -> int:
    profile_root = resolve_data_root()
    preview = preview_initialization(profile_root)
    if not args.apply:
        _print(
            {
                "success": True,
                "operation": "init",
                "dry_run": True,
                "data_root": str(preview.data_root),
                "preview": preview.to_dict(),
            }
        )
        return 0
    if args.preview_digest is None:
        raise ValueError("--apply requires --preview-digest")
    applied, created = apply_initialization(
        profile_root,
        preview_digest=args.preview_digest,
        confirm=args.confirm,
    )
    _print(
        {
            "success": True,
            "operation": "init",
            "dry_run": False,
            "data_root": str(applied.data_root),
            "database": str(applied.database),
            "created": created,
            "preview": applied.to_dict(),
        }
    )
    return 0


def _run_lifecycle(args: argparse.Namespace, service_factory: ServiceFactory) -> int:
    service = service_factory()
    if args.command == "artifacts":
        return _run_artifact_operation(args, service)
    if args.command == "curator":
        return _run_curator_operation(args, service)
    if args.command == "start":
        state = service.start(
            board_slug=args.board_slug,
            target_repository=args.target_repository,
            goal=args.goal,
            stage_profiles=_parse_stage_profiles(args.profile, args.stage_profile),
            pack_name=args.pack,
            workflow_id=args.workflow_id,
            **_constraint_source_values(args),
        )

    elif args.command == "status":
        state = service.status(args.workflow_id)
        _print(
            {
                "success": True,
                "operation": args.command,
                "workflow": state.to_dict(),
                "kanban": [
                    row.to_dict() for row in service.combined_status(args.workflow_id)
                ],
            }
        )
        return 0
    elif args.command == "replace-constraints":
        source = _constraint_source_values(args)
        state = service.replace_constraint_input(
            args.workflow_id,
            expected_current_digest=args.expected_current_digest,
            content=source["constraints_content"],
            skill_name=source["constraints_skill"],
            skill_digest=source["constraints_skill_digest"],
        )
    elif args.command == "approve":
        state = service.approve(args.workflow_id, plan_digest=args.plan_digest)
    elif args.command == "review":
        if args.review_command == "show":
            _print(
                {
                    "success": True,
                    "operation": "review-show",
                    "review": service.review_packet(args.workflow_id),
                }
            )
            return 0
        rationale = _read_review_rationale(args.rationale_file)
        action = args.action.replace("-", "_")
        actor = f"cli:{getpass.getuser()}"
        if not args.apply:
            preview = service.preview_review_decision(
                args.workflow_id,
                action=action,
                actor=actor,
                rationale=rationale,
            )
            _print(
                {
                    "success": True,
                    "operation": "review-decide",
                    "dry_run": True,
                    "preview": preview.to_dict(),
                }
            )
            return 0
        if args.expected_review_digest is None:
            raise ValueError("--apply requires --expected-review-digest")
        if args.expected_preview_digest is None:
            raise ValueError("--apply requires --expected-preview-digest")
        result = service.apply_review_decision(
            args.workflow_id,
            action=action,
            actor=actor,
            rationale=rationale,
            expected_review_digest=args.expected_review_digest,
            expected_preview_digest=args.expected_preview_digest,
            confirm=True,
        )
        _print(
            {
                "success": True,
                "operation": "review-decide",
                "dry_run": False,
                **result,
            }
        )
        return 0
    else:
        state = service.cancel(args.workflow_id, reason=args.reason)
    _print({"success": True, "operation": args.command, "workflow": state.to_dict()})
    return 0


def _run_artifact_operation(args: argparse.Namespace, service: WorkflowService) -> int:
    if args.artifacts_command == "list":
        rows = [entry.to_dict() for entry in service.list_artifacts(args.workflow_id)]
        if args.as_json:
            _print(
                {
                    "success": True,
                    "operation": "artifacts-list",
                    "artifacts": rows,
                }
            )
        else:
            columns = (
                "artifact_id",
                "kind",
                "stage",
                "policy_revision",
                "plan_revision",
                "digest",
                "recorded_at",
                "size",
                "availability",
            )
            print("\t".join(columns))
            for row in rows:
                print(
                    "\t".join(
                        "-" if row[column] is None else str(row[column])
                        for column in columns
                    )
                )
        return 0
    if args.artifacts_command == "show":
        artifact = service.read_artifact_text(args.workflow_id, args.artifact_id)
        print(artifact.content, end="")
        return 0
    if args.artifacts_command == "export":
        exported = service.export_artifact(
            args.workflow_id,
            args.artifact_id,
            args.output,
            overwrite=args.overwrite,
        )
        _print(
            {
                "success": True,
                "operation": "artifacts-export",
                "artifact": exported.to_dict(),
            }
        )
        return 0
    raise ValueError(f"unsupported artifacts command: {args.artifacts_command}")


def _run_curator_operation(args: argparse.Namespace, service: WorkflowService) -> int:
    command = args.curator_command
    operation = f"curator-{command}"
    if command == "status":
        _print(
            {
                "success": True,
                "operation": operation,
                "curator": service.curator_status().to_dict(),
            }
        )
        return 0
    if command == "tick":
        result = service.run_curator_cron_tick()
        if result is not None:
            _print(
                {
                    "success": True,
                    "operation": operation,
                    "curator": result.to_dict(),
                }
            )
        return 0
    if command == "configure":
        return _run_curator_configure(args, service)
    if command == "schedule":
        return _run_curator_schedule(args, service)
    if command == "list-archived":
        _print(
            {
                "success": True,
                "operation": operation,
                "archives": list(service.list_curator_archives()),
            }
        )
        return 0
    if args.apply and args.expected_preview_digest is None:
        raise ValueError("--apply requires --expected-preview-digest")
    if command == "run":
        value = (
            service.apply_curator_run(
                expected_preview_digest=args.expected_preview_digest
            )
            if args.apply
            else service.preview_curator_run()
        )
    elif command in {"pin", "unpin"}:
        pinned = command == "pin"
        value = (
            service.apply_curator_pin(
                args.workflow_id,
                pinned=pinned,
                expected_preview_digest=args.expected_preview_digest,
            )
            if args.apply
            else service.preview_curator_pin(args.workflow_id, pinned=pinned)
        )
    elif command == "archive":
        value = (
            service.apply_curator_archive(
                args.workflow_id,
                expected_preview_digest=args.expected_preview_digest,
            )
            if args.apply
            else service.preview_curator_archive(args.workflow_id)
        )
    elif command == "restore":
        value = (
            service.apply_curator_restore(
                args.workflow_id,
                args.archive_id,
                expected_preview_digest=args.expected_preview_digest,
            )
            if args.apply
            else service.preview_curator_restore(args.workflow_id, args.archive_id)
        )
    else:
        raise ValueError(f"unsupported curator command: {command}")
    _print(
        {
            "success": True,
            "operation": operation,
            "dry_run": not args.apply,
            "curator": value.to_dict(),
        }
    )
    return 0


def _run_curator_configure(args: argparse.Namespace, service: WorkflowService) -> int:
    policy = CuratorPolicy(
        enabled=args.curator_enabled,
        stale_after_days=args.stale_after_days,
        archive_after_days=args.archive_after_days,
    )
    current = service.curator_status()
    if not args.apply:
        _print(
            {
                "success": True,
                "operation": "curator-configure",
                "dry_run": True,
                "state_digest": current.state_digest,
                "policy_digest": policy.digest,
                "policy": policy.to_dict(),
            }
        )
        return 0
    if args.expected_state_digest is None:
        raise ValueError("--apply requires --expected-state-digest")
    if args.confirm_policy_digest is None:
        raise ValueError("--apply requires --confirm-policy-digest")
    if args.confirm_policy_digest != policy.digest:
        raise ValueError("--confirm-policy-digest does not match the requested policy")
    updated = service.configure_curator(
        enabled=policy.enabled,
        stale_after_days=policy.stale_after_days,
        archive_after_days=policy.archive_after_days,
        expected_state_digest=args.expected_state_digest,
    )
    _print(
        {
            "success": True,
            "operation": "curator-configure",
            "dry_run": False,
            "curator": updated.to_dict(),
        }
    )
    return 0


def _run_curator_schedule(args: argparse.Namespace, service: WorkflowService) -> int:
    command = args.curator_schedule_command
    operation = f"curator-schedule-{command}"
    if command == "status":
        document = service.curator_cron_status()
        _print(
            {
                "success": True,
                "operation": operation,
                "state_digest": document.digest,
                "schedule": document.to_dict(),
            }
        )
        return 0
    if args.apply and args.expected_preview_digest is None:
        raise ValueError("--apply requires --expected-preview-digest")
    if args.apply and args.confirm_controller_profile is None:
        raise ValueError("--apply requires --confirm-controller-profile")
    if command == "setup":
        value = (
            service.apply_curator_cron_setup(
                args.interval,
                expected_preview_digest=args.expected_preview_digest,
                confirmed_controller_profile=args.confirm_controller_profile,
            )
            if args.apply
            else service.preview_curator_cron_setup(args.interval)
        )
    elif command == "remove":
        value = (
            service.apply_curator_cron_remove(
                expected_preview_digest=args.expected_preview_digest,
                confirmed_controller_profile=args.confirm_controller_profile,
            )
            if args.apply
            else service.preview_curator_cron_remove()
        )
    else:
        raise ValueError(f"unsupported curator schedule command: {command}")
    _print(
        {
            "success": True,
            "operation": operation,
            "dry_run": not args.apply,
            "schedule": value.to_dict(),
        }
    )
    return 0


def _read_review_rationale(path: Path) -> str:
    if not isinstance(path, Path) or path.is_symlink() or not path.is_file():
        raise ValueError("--rationale-file must name a direct regular file")
    if path.stat().st_size > MAX_REVIEW_FEEDBACK_BYTES:
        raise ValueError(
            f"--rationale-file must be at most {MAX_REVIEW_FEEDBACK_BYTES} bytes"
        )
    try:
        rationale = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("--rationale-file must be UTF-8 text") from error
    if len(rationale.encode("utf-8")) > MAX_REVIEW_FEEDBACK_BYTES:
        raise ValueError(
            f"--rationale-file must be at most {MAX_REVIEW_FEEDBACK_BYTES} bytes"
        )
    if not rationale.strip():
        raise ValueError("--rationale-file must not be empty")
    return rationale


def _parse_stage_profiles(default_profile: str, values: list[str]) -> dict[str, str]:
    executable = {
        stage.value for stage in WorkflowStage if stage is not WorkflowStage.APPROVAL
    }
    mapping = {stage: default_profile for stage in executable}
    overridden: set[str] = set()
    for value in values:
        stage, separator, profile = value.partition("=")
        if not separator or not stage.strip() or not profile.strip():
            raise ValueError("--stage-profile must use STAGE=PROFILE")
        if stage not in executable:
            raise ValueError(f"unknown --stage-profile stage: {stage}")
        if stage in overridden:
            raise ValueError(f"duplicate --stage-profile stage: {stage}")
        mapping[stage] = profile
        overridden.add(stage)
    return mapping


def _run_pack_operation(
    args: argparse.Namespace,
    *,
    inventory: SkillInventory | None,
    registry: SkillContentRegistry | None,
    revision_resolver: RevisionResolver | None,
    hermes_version: str | None,
    command_runner: CommandRunner | None,
    operation: str | None = None,
) -> int:
    if args.packs_command == "list":
        _print(
            {
                "success": True,
                "operation": "list",
                "packs": list(PackService.bundled_names()),
            }
        )
        return 0

    if args.packs_command == "validate":
        validation = PackService.validate(args.name).to_dict()
        _print({"success": True, "operation": "validate", **validation})
        return 0

    selected_registry = registry or ProfileSkillContentRegistry(resolve_data_root() / "skills")
    selected_inventory = inventory or cast(SkillInventory, selected_registry)
    resolver = revision_resolver or _resolve_revision
    runner = command_runner or _run_command
    service = PackService(
        inventory=selected_inventory,
        registry=selected_registry,
        revision_resolver=lambda pack: resolver(pack.source),
        hermes_version_resolver=lambda: hermes_version or _resolve_hermes_version(),
        command_runner=runner,
    )
    selected_operation = operation or args.packs_command
    check = service.check(args.name, recursive=getattr(args, "recursive", False))
    if args.packs_command == "install":
        if not args.apply:
            payload = _check_payload(
                check,
                operation=selected_operation,
                dry_run=True,
                success=check.installable,
            )
            _print(payload)
            return 0 if check.installable else 1
        result = service.install(
            args.name,
            expected_preview_digest=check.preview_digest,
            confirm=True,
        )
        payload = _check_payload(
            result.pack,
            operation=selected_operation,
            dry_run=False,
            success=True,
        )
        payload["applied_preview_digest"] = result.applied_preview_digest
        payload["executed"] = [row.to_dict() for row in result.executed]
        _print(payload)
        return 0

    success = check.ready
    _print(
        _check_payload(
            check,
            operation=selected_operation,
            dry_run=True,
            success=True if args.packs_command == "update-plan" else success,
        )
    )
    if args.packs_command == "update-plan":
        return 0
    return 0 if success else 1


def _default_service(*, command_runner: CommandRunner | None = None) -> WorkflowService:
    return build_cli_service(command_runner=command_runner)


def build_cli_service(
    *,
    command_runner: CommandRunner | None = None,
    data_root: Path | None = None,
    defer_store_initialization: bool = False,
) -> WorkflowService:
    """Build a profile-safe service over documented ``hermes kanban`` commands."""
    selected_data_root = data_root or resolve_data_root()
    registry = ProfileSkillContentRegistry(selected_data_root / "skills")
    runner = command_runner or _run_command
    return WorkflowService(
        WorkflowStore(
            selected_data_root / "daidala",
            defer_initialization=defer_store_initialization,
        ),
        skill_inventory=registry,
        skill_content_registry=registry,
        kanban=KanbanGraphAdapter(
            lambda name, args: _dispatch_kanban_cli(runner, name, args)
        ),
        cron_command_runner=runner,
    )


def _dispatch_kanban_cli(
    runner: CommandRunner,
    name: str,
    args: dict[str, object],
) -> str:
    """Translate the narrow graph adapter boundary to public Hermes CLI calls."""
    if name == "terminal":
        command = tuple(shlex.split(str(args["command"])))
        if command[:2] != ("hermes", "kanban"):
            return json.dumps(
                {"exit_code": 1, "output": "refused non-Kanban host command"}
            )
        code, output = runner(command)
        return json.dumps({"exit_code": code, "output": output})

    board = str(args["board"])
    prefix = ("hermes", "kanban", "--board", board)
    if name == "kanban_create":
        command = [*prefix, "create", str(args["title"])]
        command.extend(("--body", str(args["body"])))
        assignee = args.get("assignee")
        if assignee is not None:
            command.extend(("--assignee", str(assignee)))
        for parent in cast(list[object], args.get("parents", [])):
            command.extend(("--parent", str(parent)))
        workspace_path = args.get("workspace_path")
        if workspace_path is not None:
            command.extend(("--workspace", f"dir:{workspace_path}"))
        command.extend(("--idempotency-key", str(args["idempotency_key"])))
        for skill in cast(list[object], args.get("skills", [])):
            command.extend(("--skill", str(skill)))
        initial_status = args.get("initial_status")
        if initial_status is not None:
            command.extend(("--initial-status", str(initial_status)))
        command.append("--json")
        code, output = runner(tuple(command))
        if code != 0:
            return json.dumps({"ok": False, "error": output})
        payload = _parse_cli_json(output)
        return json.dumps(
            {
                "ok": True,
                "task_id": payload.get("id"),
                "status": payload.get("status"),
            }
        )

    task_id = str(args["task_id"])
    if name == "kanban_show":
        code, output = runner((*prefix, "show", task_id, "--json"))
        if code != 0:
            return json.dumps({"ok": False, "error": output})
        payload = _parse_cli_json(output)
        return json.dumps({"ok": True, "task": payload.get("task")})

    if name == "kanban_complete":
        command = [*prefix, "complete", task_id]
        summary = args.get("summary")
        if summary is not None:
            command.extend(("--summary", str(summary)))
        metadata = args.get("metadata")
        if metadata is not None:
            command.extend(("--metadata", json.dumps(metadata, sort_keys=True)))
        code, output = runner(tuple(command))
        return json.dumps(
            {"ok": code == 0, "task_id": task_id, "error": output if code else None}
        )

    if name == "kanban_comment":
        code, output = runner(
            (*prefix, "comment", task_id, str(args["body"]))
        )
        return json.dumps(
            {"ok": code == 0, "task_id": task_id, "error": output if code else None}
        )

    if name == "kanban_unblock":
        command = [*prefix, "unblock", task_id]
        reason = args.get("reason")
        if reason is not None:
            command.extend(("--reason", str(reason)))
        code, output = runner(tuple(command))
        return json.dumps(
            {"ok": code == 0, "task_id": task_id, "error": output if code else None}
        )

    return json.dumps({"ok": False, "error": f"unsupported Kanban operation: {name}"})


def _parse_cli_json(output: str) -> dict[str, object]:
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as error:
        raise RuntimeError("Hermes Kanban CLI returned invalid JSON") from error
    if not isinstance(payload, dict):
        raise RuntimeError("Hermes Kanban CLI returned a non-object JSON payload")
    return cast(dict[str, object], payload)


def _check_payload(
    check: PackCheck, *, operation: str, dry_run: bool, success: bool
) -> dict[str, object]:
    payload = check.to_dict()
    return {
        "success": success,
        "operation": operation,
        "dry_run": dry_run,
        "pack": check.validation.name,
        "source": check.validation.source,
        "pinned_revision": check.validation.source_revision,
        **payload,
        "ready_to_apply": check.installable,
    }


def _resolve_revision(source: str) -> str:
    completed = subprocess.run(
        ["git", "ls-remote", source, "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    revision = completed.stdout.strip().split("\t", 1)[0]
    if completed.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", revision):
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown error"
        raise RuntimeError(f"could not resolve {source} HEAD: {detail}")
    return revision


def _resolve_hermes_version() -> str:
    code, output = _run_command(("hermes", "--version"))
    match = re.search(r"Hermes Agent v(\d+\.\d+\.\d+)", output)
    if code != 0 or match is None:
        raise RuntimeError("could not resolve Hermes semantic version")
    return match.group(1)


def _run_command(command: tuple[str, ...]) -> tuple[int, str]:
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    output = completed.stdout
    if completed.stderr:
        output += completed.stderr
    return completed.returncode, output.strip()


def _print(payload: dict[str, object]) -> None:
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
