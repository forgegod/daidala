"""Attended, preview-confirmed delivery of one reviewed worktree branch."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from .credentials import CredentialBindings, credential_bindings_path, parse_credential_bindings
from .errors import PolicyViolationError
from .execution import ExecutionError, ExecutionWorkspace
from .live_adapters import RuntimeRunner, run_runtime_command, safe_runtime_environment
from .profile_files import ProfileFileError, read_private_text
from .projects import ProjectManifest, parse_project_manifest
from .registrations import ControllerRegistration, list_controller_registrations, registration_path
from .repository_registration import DELIVERY_CREDENTIAL_ALIAS
from .state import DeliveryAuthorization, WorkflowLedger, WorkflowStage

if TYPE_CHECKING:
    from .service import WorkflowService

_DELIVERY_PREVIEW_SCHEMA = "daidala.delivery-preview/v1"
_BRANCH_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_REVISION = re.compile(r"^[0-9a-f]{40}$")
_MAX_OUTPUT_BYTES = 1_048_576


class DeliveryError(PolicyViolationError):
    """Raised when attended branch delivery cannot prove its authority."""


@dataclass(frozen=True)
class DeliveryPreview:
    """Path-free, non-secret facts bound to one branch-delivery transaction."""

    workflow_id: str
    project_id: str
    branch: str
    baseline_commit: str
    manifest_digest: str
    registration_digest: str
    credential_alias: str
    credential_available: bool
    review_digest: str
    implementation_digest: str
    verification_digests: tuple[str, ...]
    plan_digest: str
    plan_revision: int
    changed_paths: tuple[str, ...]
    schema: str = _DELIVERY_PREVIEW_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != _DELIVERY_PREVIEW_SCHEMA:
            raise DeliveryError("delivery preview schema is invalid")
        if not isinstance(self.workflow_id, str) or not self.workflow_id:
            raise DeliveryError("delivery preview workflow ID is invalid")
        if not isinstance(self.project_id, str) or not self.project_id:
            raise DeliveryError("delivery preview project ID is invalid")
        if not isinstance(self.branch, str) or not self.branch.startswith("daidala/"):
            raise DeliveryError("delivery preview branch is invalid")
        for value, label in (
            (self.baseline_commit, "baseline commit"),
            (self.manifest_digest, "manifest digest"),
            (self.registration_digest, "registration digest"),
            (self.review_digest, "review digest"),
            (self.implementation_digest, "implementation digest"),
            (self.plan_digest, "plan digest"),
        ):
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value):
                raise DeliveryError(f"delivery preview {label} is invalid")
        if not isinstance(self.credential_alias, str) or not self.credential_alias:
            raise DeliveryError("delivery preview credential alias is invalid")
        if not isinstance(self.credential_available, bool):
            raise DeliveryError("delivery credential availability is invalid")
        if not isinstance(self.verification_digests, tuple) or not self.verification_digests:
            raise DeliveryError("delivery preview requires verification evidence")
        if tuple(sorted(set(self.verification_digests))) != self.verification_digests:
            raise DeliveryError("delivery verification identities must be sorted and unique")
        if any(
            not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
            for value in self.verification_digests
        ):
            raise DeliveryError("delivery verification identity is invalid")
        if (
            isinstance(self.plan_revision, bool)
            or not isinstance(self.plan_revision, int)
            or self.plan_revision < 0
        ):
            raise DeliveryError("delivery plan revision is invalid")
        if not isinstance(self.changed_paths, tuple) or not self.changed_paths:
            raise DeliveryError("delivery preview requires reviewed changed paths")
        if tuple(sorted(set(self.changed_paths))) != self.changed_paths:
            raise DeliveryError("delivery changed paths must be sorted and unique")
        for path in self.changed_paths:
            if (
                not isinstance(path, str)
                or not path
                or path.startswith("/")
                or "\\" in path
                or "\x00" in path
                or any(part in {"", ".", ".."} for part in path.split("/"))
            ):
                raise DeliveryError("delivery changed path is invalid")

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            {
                "schema": self.schema,
                "workflow_id": self.workflow_id,
                "project_id": self.project_id,
                "branch": self.branch,
                "baseline_commit": self.baseline_commit,
                "manifest_digest": self.manifest_digest,
                "registration_digest": self.registration_digest,
                "credential_alias": self.credential_alias,
                "credential_available": self.credential_available,
                "review_digest": self.review_digest,
                "implementation_digest": self.implementation_digest,
                "verification_digests": list(self.verification_digests),
                "plan_digest": self.plan_digest,
                "plan_revision": self.plan_revision,
                "changed_paths": list(self.changed_paths),
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

    def to_dict(self) -> dict[str, object]:
        """Return the operator-safe preview projection.

        ``credential_alias`` remains bound into ``canonical_bytes()`` and the
        durable delivery authorization, but profile-local binding names are not
        browser or CLI response data.
        """
        return {
            "schema": self.schema,
            "workflow_id": self.workflow_id,
            "project_id": self.project_id,
            "branch": self.branch,
            "baseline_commit": self.baseline_commit,
            "manifest_digest": self.manifest_digest,
            "registration_digest": self.registration_digest,
            "credential_available": self.credential_available,
            "review_digest": self.review_digest,
            "implementation_digest": self.implementation_digest,
            "verification_digests": list(self.verification_digests),
            "plan_digest": self.plan_digest,
            "plan_revision": self.plan_revision,
            "changed_paths": list(self.changed_paths),
            "preview_digest": self.digest,
        }


class BranchDeliveryService:
    """Perform only an exact reviewed branch commit and push after preview."""

    def __init__(
        self,
        workflow_service: WorkflowService,
        *,
        profile_root: Path,
        runner: RuntimeRunner | None = None,
        environ: Mapping[str, str] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.workflow_service = workflow_service
        self.profile_root = Path(profile_root).resolve()
        self.runner = runner or run_runtime_command
        self.environ = dict(os.environ if environ is None else environ)
        self.clock = clock or (lambda: datetime.now(UTC))
        self.workspace = ExecutionWorkspace(workflow_service.store.data_root)

    def preview(self, workflow_id: str) -> DeliveryPreview:
        ledger = self.workflow_service.status(workflow_id)
        registration = self._registration_for(ledger)
        self._assert_registered_target_remote(ledger, registration)
        manifest = self._committed_manifest(ledger, registration)
        bindings = self._credential_bindings(registration)
        self._require_reviewed_delivery(ledger)
        changed_paths = self.workflow_service.current_implementation_changed_paths(
            ledger.workflow_id, ledger=ledger
        )
        credential_available = self._credential_available(bindings)
        preview = DeliveryPreview(
            workflow_id=ledger.workflow_id,
            project_id=registration.project_id,
            branch=_delivery_branch(ledger.workflow_id),
            baseline_commit=ledger.baseline_commit,
            manifest_digest=manifest.digest,
            registration_digest=registration.digest,
            credential_alias=DELIVERY_CREDENTIAL_ALIAS,
            credential_available=credential_available,
            review_digest=ledger.review.digest,
            implementation_digest=ledger.review.implementation_digest,
            verification_digests=ledger.review.verification_digests,
            plan_digest=ledger.review.plan_digest,
            plan_revision=ledger.plan_revision,
            changed_paths=changed_paths,
        )
        authorization = ledger.delivery_authorization
        if authorization is not None and authorization.commit is not None:
            if authorization.preview_digest != preview.digest:
                raise DeliveryError(
                "recorded delivery authorization no longer matches current evidence"
            )
            self._assert_recorded_commit(ledger, preview, authorization.commit)
        elif authorization is not None and self._existing_reviewed_commit(ledger, preview):
            pass
        else:
            self._assert_live_reviewed_diff(ledger)
        return preview

    def apply(
        self, workflow_id: str, *, expected_preview_digest: str, confirm: bool
    ) -> WorkflowLedger:
        if confirm is not True:
            raise DeliveryError("explicit branch delivery confirmation is required")
        existing = self.workflow_service.status(workflow_id)
        if existing.committed or existing.pushed:
            authorization = existing.delivery_authorization
            if (
                not existing.committed
                or not existing.pushed
                or authorization is None
                or authorization.preview_digest != expected_preview_digest
            ):
                raise DeliveryError("completed delivery does not match the confirmed preview")
            card = existing.card_for(WorkflowStage.DELIVER)
            if card is None:
                raise DeliveryError("delivery card is unavailable")
            return self.workflow_service.finalize_branch_delivery(
                workflow_id,
                authorization=authorization,
                board_slug=existing.board_slug,
                task_id=card.task_id,
            )
        preview = self.preview(workflow_id)
        if expected_preview_digest != preview.digest:
            raise DeliveryError("delivery preview changed after review")
        if not preview.credential_available:
            raise DeliveryError("delivery credential unavailable")

        ledger = self.workflow_service.status(workflow_id)
        self._assert_remote_preflight(preview, ledger)
        authorization = ledger.delivery_authorization
        if authorization is None:
            authorization = self._authorization_for(preview, commit=None)
            ledger = self.workflow_service.record_delivery_authorization(
                workflow_id, authorization=authorization
            )
            authorization = ledger.delivery_authorization
            assert authorization is not None
        elif authorization.preview_digest != preview.digest:
            raise DeliveryError(
                "recorded delivery authorization no longer matches current evidence"
            )

        if authorization.commit is None:
            commit = self._commit_reviewed_diff(ledger, preview)
            authorization = replace(authorization, commit=commit)
            ledger = self.workflow_service.record_delivery_authorization(
                workflow_id, authorization=authorization
            )
        else:
            self._assert_recorded_commit(ledger, preview, authorization.commit)

        self._push_exact_branch(preview, ledger)
        card = ledger.card_for(WorkflowStage.DELIVER)
        if card is None:
            raise DeliveryError("delivery card is unavailable")
        completed = self.workflow_service.finalize_branch_delivery(
            workflow_id,
            authorization=authorization,
            board_slug=ledger.board_slug,
            task_id=card.task_id,
        )
        return completed

    def _registration_for(self, ledger: WorkflowLedger) -> ControllerRegistration:
        matches = [
            registration
            for registration in list_controller_registrations(self.profile_root)
            if Path(registration.checkout).resolve() == Path(ledger.target_repository).resolve()
        ]
        if len(matches) != 1:
            raise DeliveryError("workflow target has no unique trusted delivery registration")
        return matches[0]

    def _committed_manifest(
        self, ledger: WorkflowLedger, registration: ControllerRegistration
    ) -> ProjectManifest:
        content = self._git(
            (
                "git",
                "-C",
                ledger.target_repository,
                "show",
                f"{ledger.baseline_commit}:.daidala/project.yaml",
            ),
            label="committed project manifest",
        )
        try:
            manifest = parse_project_manifest(content)
        except PolicyViolationError as error:
            raise DeliveryError("committed project manifest is invalid") from error
        registration.validate_manifest(manifest)
        if not manifest.allow_commit or not manifest.allow_push:
            raise DeliveryError("committed release policy does not allow branch delivery")
        return manifest

    def _assert_registered_target_remote(
        self, ledger: WorkflowLedger, registration: ControllerRegistration
    ) -> None:
        remote = self._git(
            ("git", "-C", ledger.target_repository, "remote", "get-url", "origin"),
            label="registered target remote",
        )
        if remote != registration.verified_remote:
            raise DeliveryError("workflow target remote no longer matches its trusted registration")

    def _credential_bindings(self, registration: ControllerRegistration) -> CredentialBindings:
        path = credential_bindings_path(
            registration_path(self.profile_root, registration.project_id)
        )
        try:
            content = read_private_text(
                path,
                maximum_bytes=16_384,
                label="delivery credential bindings",
            )
            bindings = parse_credential_bindings(content)
        except (FileNotFoundError, ProfileFileError, PolicyViolationError) as error:
            raise DeliveryError("delivery credential binding is unavailable") from error
        if bindings.project_id != registration.project_id:
            raise DeliveryError("delivery credential binding project does not match registration")
        try:
            bindings.binding_for(DELIVERY_CREDENTIAL_ALIAS)
        except PolicyViolationError as error:
            raise DeliveryError("delivery credential binding is unavailable") from error
        return bindings

    def _require_reviewed_delivery(self, ledger: WorkflowLedger) -> None:
        review = ledger.review
        disposition = ledger.review_disposition
        deliver_card = ledger.card_for(WorkflowStage.DELIVER)
        if (
            review is None
            or review.outcome.value != "accepted"
            or any(finding.blocking for finding in review.findings)
            or disposition is None
            or disposition.action.value != "accept_delivery"
            or deliver_card is None
            or ledger.activation_for(WorkflowStage.DELIVER) is None
            or not ledger.worktree_owned
            or not ledger.worktree_path
        ):
            raise DeliveryError("delivery requires an accepted reviewed activated delivery stage")

    def _assert_live_reviewed_diff(self, ledger: WorkflowLedger) -> tuple[str, ...]:
        if not ledger.worktree_path:
            raise DeliveryError("delivery worktree is unavailable")
        implementation = ledger.artifact_for(WorkflowStage.IMPLEMENT)
        if implementation is None:
            raise DeliveryError("reviewed implementation artifact is unavailable")
        try:
            captured = self.workspace.read_artifact_bytes(
                ledger.workflow_id,
                implementation.path,
                expected_digest=implementation.digest,
            ).decode("utf-8")
            try:
                live = self.workspace.capture_diff(ledger.worktree_path)
                changed_paths = self.workspace.changed_paths(ledger.worktree_path)
            except ExecutionError:
                live = self._git(
                    ("git", "-C", ledger.worktree_path, "diff", "--cached", "--binary", "HEAD"),
                    label="staged delivery diff",
                )
                if live:
                    live += "\n"
                changed_paths = tuple(
                    sorted(
                        path
                        for path in self._git(
                            (
                                "git",
                                "-C",
                                ledger.worktree_path,
                                "diff",
                                "--cached",
                                "--name-only",
                                "-z",
                                "HEAD",
                            ),
                            label="staged delivery changed paths",
                        ).split("\0")
                        if path
                    )
                )
        except (ExecutionError, UnicodeDecodeError) as error:
            raise DeliveryError("reviewed worktree evidence is unavailable") from error
        if live != captured:
            raise DeliveryError("worktree diff changed after review")
        expected_paths = self.workflow_service.current_implementation_changed_paths(
            ledger.workflow_id, ledger=ledger
        )
        if changed_paths != expected_paths:
            raise DeliveryError("worktree changed paths differ from reviewed evidence")
        return expected_paths

    def _credential_available(self, bindings: CredentialBindings) -> bool:
        try:
            bindings.resolve(DELIVERY_CREDENTIAL_ALIAS, self.environ)
        except PolicyViolationError:
            return False
        return True

    def _authorization_for(
        self, preview: DeliveryPreview, *, commit: str | None
    ) -> DeliveryAuthorization:
        return DeliveryAuthorization(
            workflow_id=preview.workflow_id,
            project_id=preview.project_id,
            branch=preview.branch,
            baseline_commit=preview.baseline_commit,
            manifest_digest=preview.manifest_digest,
            registration_digest=preview.registration_digest,
            credential_alias=preview.credential_alias,
            review_digest=preview.review_digest,
            implementation_digest=preview.implementation_digest,
            verification_digests=preview.verification_digests,
            plan_digest=preview.plan_digest,
            plan_revision=preview.plan_revision,
            preview_digest=preview.digest,
            commit=commit,
            authorized_at=self.clock(),
        )

    def _commit_reviewed_diff(self, ledger: WorkflowLedger, preview: DeliveryPreview) -> str:
        if not ledger.worktree_path:
            raise DeliveryError("delivery worktree is unavailable")
        current_branch = self._git(
            ("git", "-C", ledger.worktree_path, "branch", "--show-current"),
            label="delivery branch",
        )
        if current_branch:
            if current_branch != preview.branch:
                raise DeliveryError("delivery worktree is already attached to a different branch")
            head = self._git(
                ("git", "-C", ledger.worktree_path, "rev-parse", "HEAD"),
                label="existing delivery commit identity",
            )
            if head != preview.baseline_commit:
                parent = self._git(
                    ("git", "-C", ledger.worktree_path, "rev-parse", "HEAD^"),
                    label="existing delivery commit parent",
                )
                if parent == preview.baseline_commit and self._commit_matches_reviewed_diff(
                    ledger, head
                ) and not self._git(
                    ("git", "-C", ledger.worktree_path, "status", "--porcelain=v1"),
                    label="existing delivery worktree status",
                ):
                    return head
                raise DeliveryError("delivery branch does not contain the exact reviewed commit")
        else:
            head = self._git(
                ("git", "-C", ledger.worktree_path, "rev-parse", "HEAD"),
                label="delivery worktree baseline",
            )
            if head != preview.baseline_commit:
                raise DeliveryError("delivery worktree no longer matches its baseline")
            existing_branch = self._git(
                (
                    "git",
                    "-C",
                    ledger.worktree_path,
                    "branch",
                    "--list",
                    "--format=%(refname:short)",
                    preview.branch,
                ),
                label="delivery branch lookup",
            )
            if existing_branch == preview.branch:
                raise DeliveryError("delivery branch already exists locally")
            self._git(
                ("git", "-C", ledger.worktree_path, "switch", "--create", preview.branch),
                label="delivery branch creation",
            )
        self._assert_live_reviewed_diff(ledger)
        self._git(
            ("git", "-C", ledger.worktree_path, "add", "-A", "--", *preview.changed_paths),
            label="reviewed delivery staging",
        )
        staged = self._git(
            ("git", "-C", ledger.worktree_path, "diff", "--cached", "--binary", "HEAD"),
            label="reviewed delivery staging verification",
        )
        implementation = ledger.artifact_for(WorkflowStage.IMPLEMENT)
        assert implementation is not None
        captured = self.workspace.read_artifact_bytes(
            ledger.workflow_id,
            implementation.path,
            expected_digest=implementation.digest,
        ).decode("utf-8")
        if staged + "\n" != captured:
            raise DeliveryError("staged delivery diff differs from reviewed evidence")
        message = (
            "chore(delivery): apply reviewed diff\n\n"
            f"Daidala-Workflow: {ledger.workflow_id}\n"
            f"Daidala-Delivery-Preview: {preview.digest}\n"
        )
        try:
            self._git(
                (
                    "git",
                    "-C",
                    ledger.worktree_path,
                    "-c",
                    "core.hooksPath=/dev/null",
                    "commit",
                    "--no-gpg-sign",
                    "-m",
                    message,
                ),
                label="reviewed delivery commit",
            )
        except DeliveryError:
            if self._git(
                ("git", "-C", ledger.worktree_path, "rev-parse", "HEAD"),
                label="failed delivery commit identity",
            ) == preview.baseline_commit:
                self._git(
                    ("git", "-C", ledger.worktree_path, "reset", "--"),
                    label="failed delivery staging rollback",
                )
            raise
        commit = self._git(
            ("git", "-C", ledger.worktree_path, "rev-parse", "HEAD"),
            label="reviewed delivery commit identity",
        )
        if not _REVISION.fullmatch(commit):
            raise DeliveryError("delivery commit identity is invalid")
        return commit

    def _existing_reviewed_commit(
        self, ledger: WorkflowLedger, preview: DeliveryPreview
    ) -> str | None:
        if not ledger.worktree_path:
            return None
        branch = self._git(
            ("git", "-C", ledger.worktree_path, "branch", "--show-current"),
            label="existing delivery branch",
        )
        if branch != preview.branch:
            return None
        head = self._git(
            ("git", "-C", ledger.worktree_path, "rev-parse", "HEAD"),
            label="existing delivery commit identity",
        )
        if head == preview.baseline_commit:
            return None
        parent = self._git(
            ("git", "-C", ledger.worktree_path, "rev-parse", "HEAD^"),
            label="existing delivery commit parent",
        )
        if (
            parent != preview.baseline_commit
            or not self._commit_matches_reviewed_diff(ledger, head)
            or self._git(
                ("git", "-C", ledger.worktree_path, "status", "--porcelain=v1"),
                label="existing delivery worktree status",
            )
        ):
            return None
        return head

    def _commit_matches_reviewed_diff(self, ledger: WorkflowLedger, commit: str) -> bool:
        if not ledger.worktree_path or not _REVISION.fullmatch(commit):
            return False
        implementation = ledger.artifact_for(WorkflowStage.IMPLEMENT)
        if implementation is None:
            return False
        captured = self.workspace.read_artifact_bytes(
            ledger.workflow_id,
            implementation.path,
            expected_digest=implementation.digest,
        ).decode("utf-8")
        diff = self._git(
            ("git", "-C", ledger.worktree_path, "diff", "--binary", "HEAD^", "HEAD"),
            label="existing delivery commit diff",
        )
        return diff + "\n" == captured

    def _assert_recorded_commit(
        self, ledger: WorkflowLedger, preview: DeliveryPreview, commit: str
    ) -> None:
        if not ledger.worktree_path:
            raise DeliveryError("delivery worktree is unavailable")
        branch = self._git(
            ("git", "-C", ledger.worktree_path, "branch", "--show-current"),
            label="recorded delivery branch",
        )
        head = self._git(
            ("git", "-C", ledger.worktree_path, "rev-parse", "HEAD"),
            label="recorded delivery commit identity",
        )
        if branch != preview.branch or head != commit:
            raise DeliveryError("recorded delivery commit no longer matches the worktree")
        parent = self._git(
            ("git", "-C", ledger.worktree_path, "rev-parse", "HEAD^"),
            label="recorded delivery commit parent",
        )
        if parent != preview.baseline_commit or not self._commit_matches_reviewed_diff(
            ledger, commit
        ):
            raise DeliveryError("recorded delivery commit no longer matches reviewed evidence")
        if self._git(
            ("git", "-C", ledger.worktree_path, "status", "--porcelain=v1"),
            label="recorded delivery worktree status",
        ):
            raise DeliveryError("recorded delivery worktree is no longer clean")

    def _assert_remote_preflight(
        self, preview: DeliveryPreview, ledger: WorkflowLedger
    ) -> None:
        registration = self._registration_for(ledger)
        bindings = self._credential_bindings(registration)
        try:
            token = bindings.resolve(DELIVERY_CREDENTIAL_ALIAS, self.environ)
        except PolicyViolationError as error:
            raise DeliveryError("delivery credential unavailable") from error
        remote = f"https://github.com/{registration.repository_canonical}.git"
        expected_ref = f"refs/heads/{preview.branch}"
        remote_commit = self._remote_branch_commit(remote, expected_ref, token)
        recorded = (
            ledger.delivery_authorization.commit
            if ledger.delivery_authorization is not None
            else None
        )
        if remote_commit is not None and remote_commit != recorded:
            raise DeliveryError("delivery branch already exists on the remote")

    def _push_exact_branch(self, preview: DeliveryPreview, ledger: WorkflowLedger) -> None:
        if not ledger.delivery_authorization or not ledger.delivery_authorization.commit:
            raise DeliveryError("delivery commit has not been recorded")
        registration = self._registration_for(ledger)
        bindings = self._credential_bindings(registration)
        try:
            token = bindings.resolve(DELIVERY_CREDENTIAL_ALIAS, self.environ)
        except PolicyViolationError as error:
            raise DeliveryError("delivery credential unavailable") from error
        remote = f"https://github.com/{registration.repository_canonical}.git"
        expected_ref = f"refs/heads/{preview.branch}"
        remote_commit = self._remote_branch_commit(remote, expected_ref, token)
        if remote_commit is not None and remote_commit != ledger.delivery_authorization.commit:
            raise DeliveryError("delivery branch already exists on the remote")
        if remote_commit is None:
            self._git(
                (
                    "git",
                    "-C",
                    str(ledger.worktree_path),
                    "push",
                    remote,
                    f"{ledger.delivery_authorization.commit}:{expected_ref}",
                ),
                label="delivery branch push",
                token=token,
            )
        confirmed = self._remote_branch_commit(remote, expected_ref, token)
        if confirmed != ledger.delivery_authorization.commit:
            raise DeliveryError("delivery branch push did not converge")

    def _remote_branch_commit(self, remote: str, ref: str, token: str) -> str | None:
        output = self._git(
            ("git", "ls-remote", "--heads", remote, ref),
            label="delivery branch inspection",
            token=token,
        )
        if not output:
            return None
        rows = [line.split("\t", 1) for line in output.splitlines()]
        if (
            len(rows) != 1
            or len(rows[0]) != 2
            or rows[0][1] != ref
            or not _REVISION.fullmatch(rows[0][0])
        ):
            raise DeliveryError("delivery branch inspection returned an invalid identity")
        return rows[0][0]

    def _git(self, command: tuple[str, ...], *, label: str, token: str | None = None) -> str:
        environment = safe_runtime_environment(self.environ)
        environment.update({"GIT_TERMINAL_PROMPT": "0", "GH_PROMPT_DISABLED": "1"})
        askpass: Path | None = None
        try:
            if token is not None:
                askpass = _askpass_script()
                environment.update(
                    {
                        "DAIDALA_DELIVERY_TOKEN": token,
                        "GIT_ASKPASS": str(askpass),
                        "GIT_ASKPASS_REQUIRE": "force",
                    }
                )
            code, output = self.runner(command, environment)
        finally:
            if askpass is not None:
                askpass.unlink(missing_ok=True)
        if (
            isinstance(code, bool)
            or not isinstance(code, int)
            or not isinstance(output, str)
            or len(output.encode("utf-8")) > _MAX_OUTPUT_BYTES
            or code != 0
        ):
            raise DeliveryError(f"{label} failed")
        return output.strip()


def _delivery_branch(workflow_id: str) -> str:
    if not isinstance(workflow_id, str) or not _BRANCH_COMPONENT.fullmatch(workflow_id):
        raise DeliveryError("workflow ID cannot form a delivery branch")
    return f"daidala/{workflow_id}"


def _askpass_script() -> Path:
    descriptor, raw_path = tempfile.mkstemp(prefix="daidala-git-askpass-", text=True)
    path = Path(raw_path)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(
                "#!/bin/sh\n"
                "case \"$1\" in\n"
                "  *Username*) printf '%s\\n' x-access-token ;;\n"
                "  *) printf '%s\\n' \"$DAIDALA_DELIVERY_TOKEN\" ;;\n"
                "esac\n"
            )
        path.chmod(0o700)
    except OSError:
        path.unlink(missing_ok=True)
        raise DeliveryError("delivery credential helper is unavailable") from None
    return path


__all__ = ["BranchDeliveryService", "DeliveryError", "DeliveryPreview"]
