"""Preview-confirmed GitHub repository registration for one Hermes profile."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

import yaml

from .checkout_root import CheckoutRootStore, checkout_path
from .credentials import CredentialBinding, CredentialBindings, credential_bindings_path
from .errors import PolicyViolationError
from .live_adapters import RuntimeRunner, run_runtime_command, safe_runtime_environment
from .profile_files import (
    ProfileFileError,
    atomic_write_private_text,
    read_private_text,
)
from .projects import (
    MAX_MANIFEST_BYTES,
    ProjectManifest,
    _as_list,
    _require_exact_fields,
    _require_slug,
    _require_text,
    parse_project_manifest,
    parse_strict_yaml,
)
from .registrations import (
    ControllerRegistration,
    RegistrationLimits,
    list_controller_registrations,
    registration_path,
)
from .setup_wizard import SetupWizardError, list_profiles

REGISTRATION_DEFAULTS_SCHEMA = "daidala.repository-registration-defaults/v1"
REGISTRATION_PREVIEW_SCHEMA = "daidala.repository-registration-preview/v1"
REGISTRATION_CLASSIFICATION_SCHEMA = "daidala.repository-registration-classification/v1"
REGISTRATION_DEFAULTS_FILENAME = "repository-registration-defaults.yaml"
DELIVERY_CREDENTIAL_ALIAS = "github-repository-delivery"
DELIVERY_ENVIRONMENT_VARIABLE = "DAIDALA_GITHUB_DELIVERY_TOKEN"
MAX_REGISTRATION_DEFAULTS_BYTES = 32_768
MAX_GITHUB_OUTPUT_BYTES = 1_048_576
_CONFIRMATION = "register-repository"
CLASSIFICATION_NEEDS_BOOTSTRAP = "needs-bootstrap"
CLASSIFICATION_REGISTERABLE = "registerable"
CLASSIFICATION_ALREADY_REGISTERED = "already-registered"
CLASSIFICATION_BLOCKED = "blocked"
MISSING_PROJECT_POLICY = "committed project policy is missing"
ALREADY_REGISTERED = "project ID is already registered in this profile"
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
_SCP_GITHUB = re.compile(
    r"^git@github\.com:(?P<owner>[A-Za-z0-9_.-]{1,100})/"
    r"(?P<repository>[A-Za-z0-9_.-]{1,104})$"
)
_HERMES_DESTINATION = re.compile(
    r"^[a-z][a-z0-9_-]{0,63}:[^\s\x00-\x1f\x7f]{1,447}$"
)
ProfileCommandRunner = Callable[[tuple[str, ...]], tuple[int, str]]


class RepositoryRegistrationError(PolicyViolationError):
    """A repository registration request cannot be previewed or applied safely."""


@dataclass(frozen=True)
class RegistrationDefaults:
    """Profile-local authority that a repository URL cannot provide."""

    intake_binding: CredentialBinding
    findings_binding: CredentialBinding
    maintainers: tuple[str, ...]
    notification_adapter: str
    notification_target: str
    notification_destination: str
    evaluator_backend: str
    evaluator_network: str
    limits: RegistrationLimits
    schema: str = REGISTRATION_DEFAULTS_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != REGISTRATION_DEFAULTS_SCHEMA:
            raise RepositoryRegistrationError(
                f"registration defaults schema must be {REGISTRATION_DEFAULTS_SCHEMA!r}"
            )

        if self.intake_binding.alias == self.findings_binding.alias:
            raise RepositoryRegistrationError(
                "registration defaults intake and findings aliases must differ"
            )
        if (
            self.intake_binding.environment_variable
            == self.findings_binding.environment_variable
        ):
            raise RepositoryRegistrationError(
                "registration defaults intake and findings variables must differ"
            )
        if not isinstance(self.maintainers, tuple) or not 1 <= len(self.maintainers) <= 32:
            raise RepositoryRegistrationError(
                "registration defaults maintainers must contain 1-32 identities"
            )
        if len(self.maintainers) != len(set(self.maintainers)):
            raise RepositoryRegistrationError(
                "registration defaults maintainers cannot contain duplicates"
            )
        for maintainer in self.maintainers:
            _require_text(maintainer, "registration defaults maintainer")
        if self.notification_adapter != "hermes-gateway":
            raise RepositoryRegistrationError(
                "registration defaults notification adapter must be 'hermes-gateway'"
            )
        _require_slug(self.notification_target, "registration defaults notification target")
        if (
            not isinstance(self.notification_destination, str)
            or not _HERMES_DESTINATION.fullmatch(self.notification_destination)
        ):
            raise RepositoryRegistrationError(
                "registration defaults notification destination must be an explicit non-home target"
            )
        if self.evaluator_backend != "restricted-container":
            raise RepositoryRegistrationError(
                "registration defaults evaluator backend must be 'restricted-container'"
            )
        if self.evaluator_network != "denied-by-default":
            raise RepositoryRegistrationError(
                "registration defaults evaluator network must be 'denied-by-default'"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "credentials": {
                "intake": self.intake_binding.to_dict(),
                "findings": self.findings_binding.to_dict(),
            },
            "approval": {"maintainers": list(self.maintainers)},
            "notifications": {
                "adapter": self.notification_adapter,
                "target": self.notification_target,
                "destination": self.notification_destination,
            },
            "evaluator": {
                "backend": self.evaluator_backend,
                "network": self.evaluator_network,
            },
            "limits": self.limits.to_dict(),
        }

    @property
    def digest(self) -> str:
        canonical = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, raw: object) -> RegistrationDefaults:
        _require_exact_fields(
            raw,
            {
                "schema",
                "credentials",
                "approval",
                "notifications",
                "evaluator",
                "limits",
            },
            "repository registration defaults",
        )
        assert isinstance(raw, dict)
        credentials = raw["credentials"]
        approval = raw["approval"]
        notifications = raw["notifications"]
        evaluator = raw["evaluator"]
        _require_exact_fields(credentials, {"intake", "findings"}, "default credentials")
        _require_exact_fields(approval, {"maintainers"}, "default approval")
        _require_exact_fields(
            notifications, {"adapter", "target", "destination"}, "default notifications"
        )
        _require_exact_fields(evaluator, {"backend", "network"}, "default evaluator")
        assert isinstance(credentials, dict)
        assert isinstance(approval, dict)
        assert isinstance(notifications, dict)
        assert isinstance(evaluator, dict)
        maintainers = _as_list(approval["maintainers"], "registration defaults maintainers")
        if any(not isinstance(row, str) for row in maintainers):
            raise RepositoryRegistrationError(
                "registration defaults maintainers must contain strings"
            )
        return cls(
            schema=raw["schema"],
            intake_binding=CredentialBinding.from_dict(credentials["intake"]),
            findings_binding=CredentialBinding.from_dict(credentials["findings"]),
            maintainers=tuple(maintainers),
            notification_adapter=notifications["adapter"],
            notification_target=notifications["target"],
            notification_destination=notifications["destination"],
            evaluator_backend=evaluator["backend"],
            evaluator_network=evaluator["network"],
            limits=RegistrationLimits.from_dict(raw["limits"]),
        )


@dataclass(frozen=True)
class RepositoryClassification:
    """Path-free inspect outcome before registration or bootstrap apply."""

    status: str
    controller_profile: str
    reason: str
    next_action: str
    repository: str | None = None
    project_id: str | None = None
    preview: RegistrationPreview | None = field(default=None, repr=False)
    schema: str = REGISTRATION_CLASSIFICATION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != REGISTRATION_CLASSIFICATION_SCHEMA:
            raise RepositoryRegistrationError(
                f"registration classification schema must be {REGISTRATION_CLASSIFICATION_SCHEMA!r}"
            )
        if self.status not in {
            CLASSIFICATION_NEEDS_BOOTSTRAP,
            CLASSIFICATION_REGISTERABLE,
            CLASSIFICATION_ALREADY_REGISTERED,
            CLASSIFICATION_BLOCKED,
        }:
            raise RepositoryRegistrationError("registration classification status is invalid")
        expected_next = {
            CLASSIFICATION_NEEDS_BOOTSTRAP: "bootstrap",
            CLASSIFICATION_REGISTERABLE: "register",
            CLASSIFICATION_ALREADY_REGISTERED: "none",
            CLASSIFICATION_BLOCKED: "none",
        }[self.status]
        if self.next_action != expected_next:
            raise RepositoryRegistrationError("registration classification next action is invalid")
        if self.status == CLASSIFICATION_REGISTERABLE and self.preview is None:
            raise RepositoryRegistrationError("registerable classification requires a preview")
        if self.status != CLASSIFICATION_REGISTERABLE and self.preview is not None:
            raise RepositoryRegistrationError(
                "non-registerable classification cannot carry a preview"
            )

    def to_dict(self) -> dict[str, object]:
        if self.status == CLASSIFICATION_REGISTERABLE:
            assert self.preview is not None
            payload = self.preview.to_dict()
            payload["classification"] = self.status
            payload["next_action"] = self.next_action
            payload["reason"] = self.reason
            return payload
        return {
            "schema": self.schema,
            "valid": False,
            "status": self.status,
            "classification": self.status,
            "controller_profile": self.controller_profile,
            "repository": self.repository,
            "project_id": self.project_id,
            "reason": self.reason,
            "next_action": self.next_action,
        }


@dataclass(frozen=True)
class RegistrationPreview:
    """Safe public projection plus the exact private records bound by its digest."""

    repository_canonical: str
    project_id: str
    controller_profile: str
    board: str
    board_action: str
    manifest_digest: str
    allow_commit: bool
    allow_push: bool
    allow_publish: bool
    registration: ControllerRegistration = field(repr=False)
    credential_bindings: CredentialBindings = field(repr=False)
    defaults_digest: str = field(repr=False)
    schema: str = REGISTRATION_PREVIEW_SCHEMA

    @property
    def digest(self) -> str:
        content = json.dumps(
            {
                "schema": self.schema,
                "repository": self.repository_canonical,
                "project_id": self.project_id,
                "controller_profile": self.controller_profile,
                "board": self.board,
                "board_action": self.board_action,
                "manifest_digest": self.manifest_digest,
                "registration_digest": self.registration.digest,
                "credential_bindings": self.credential_bindings.to_dict(),
                "defaults_digest": self.defaults_digest,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "valid": True,
            "repository": self.repository_canonical,
            "project_id": self.project_id,
            "controller_profile": self.controller_profile,
            "board": self.board,
            "board_action": self.board_action,
            "manifest_digest": self.manifest_digest,
            "release": {
                "allow_commit": self.allow_commit,
                "allow_push": self.allow_push,
                "allow_publish": self.allow_publish,
            },
            "readiness": {
                "board_selected": bool(self.board),
                "attended_target_configured": True,
                "credential_available": False,
            },
            "writes": {
                "record_count": 2,
                "registration": True,
                "credential_bindings": True,
                "board": self.board_action,
            },
            "preview_digest": self.digest,
        }


@dataclass
class RepositoryRegistrationService:
    """Inspect GitHub policy and atomically publish one trusted registration marker."""

    data_root: Path
    controller_profile: str
    runner: RuntimeRunner = field(default_factory=lambda: run_runtime_command)
    environ: Mapping[str, str] = field(default_factory=lambda: dict(os.environ))

    def __post_init__(self) -> None:
        if not isinstance(self.data_root, Path) or not self.data_root.is_absolute():
            raise RepositoryRegistrationError(
                "repository registration data root must be an absolute path"
            )
        self.data_root = self.data_root.resolve()
        _require_slug(self.controller_profile, "repository registration profile")

    def classify(
        self, github_url: str, *, board: str | None = None
    ) -> RepositoryClassification:
        """Classify one GitHub URL without writing profile-local registration state."""

        try:
            claimed_repository = parse_github_repository_url(github_url)
        except RepositoryRegistrationError as error:
            return self._blocked(str(error))
        try:
            metadata = self._github_json(
                ("gh", "api", f"repos/{claimed_repository}"), "metadata"
            )
            canonical, ssh_url, clone_url = _repository_metadata(metadata)
        except RepositoryRegistrationError as error:
            return self._blocked(str(error), repository=claimed_repository)
        try:
            manifest = self._fetch_manifest(canonical)
        except RepositoryRegistrationError as error:
            if str(error) == MISSING_PROJECT_POLICY:
                return RepositoryClassification(
                    status=CLASSIFICATION_NEEDS_BOOTSTRAP,
                    controller_profile=self.controller_profile,
                    repository=canonical,
                    reason=MISSING_PROJECT_POLICY,
                    next_action="bootstrap",
                )
            return self._blocked(str(error), repository=canonical)
        try:
            if manifest.repository.canonical != canonical:
                raise RepositoryRegistrationError(
                    "committed project manifest canonical identity does not match GitHub"
                )
            allowed = set(manifest.repository.allowed_remote_urls)
            verified_remote = (
                ssh_url
                if ssh_url in allowed
                else clone_url
                if clone_url in allowed
                else None
            )
            if verified_remote is None:
                raise RepositoryRegistrationError(
                    "GitHub clone URLs are not allowed by the committed project manifest"
                )
            registrations = list_controller_registrations(self.data_root)
            if any(row.project_id == manifest.project_id for row in registrations):
                raise RepositoryRegistrationError(ALREADY_REGISTERED)
            defaults = load_registration_defaults(self.data_root)
            checkout = checkout_path(
                CheckoutRootStore(self.data_root).read().root, manifest.project_id
            )
            selected_board = board or f"daidala-{manifest.project_id}"
            _require_slug(selected_board, "registration board")
            if self._board_is_registered(selected_board):
                raise RepositoryRegistrationError(
                    "board is already registered by a Daidala project"
                )
            board_action = self._board_action(selected_board, checkout)
            registration = ControllerRegistration(
                project_id=manifest.project_id,
                checkout=str(checkout),
                controller_profile=self.controller_profile,
                board=selected_board,
                repository_canonical=canonical,
                verified_remote=verified_remote,
                intake_credential=defaults.intake_binding.alias,
                findings_credential=defaults.findings_binding.alias,
                maintainers=defaults.maintainers,
                notification_adapter=defaults.notification_adapter,
                notification_target=defaults.notification_target,
                notification_destination=defaults.notification_destination,
                evaluator_backend=defaults.evaluator_backend,
                evaluator_network=defaults.evaluator_network,
                limits=defaults.limits,
            )
            registration.validate_manifest(manifest)
            bindings = CredentialBindings(
                project_id=manifest.project_id,
                bindings=(
                    defaults.intake_binding,
                    defaults.findings_binding,
                    CredentialBinding(
                        alias=DELIVERY_CREDENTIAL_ALIAS,
                        resolver="environment",
                        environment_variable=DELIVERY_ENVIRONMENT_VARIABLE,
                    ),
                ),
            )
            preview = RegistrationPreview(
                repository_canonical=canonical,
                project_id=manifest.project_id,
                controller_profile=self.controller_profile,
                board=selected_board,
                board_action=board_action,
                manifest_digest=manifest.digest,
                allow_commit=manifest.allow_commit,
                allow_push=manifest.allow_push,
                allow_publish=manifest.allow_publish,
                registration=registration,
                credential_bindings=bindings,
                defaults_digest=defaults.digest,
            )
        except RepositoryRegistrationError as error:
            if str(error) == ALREADY_REGISTERED:
                return RepositoryClassification(
                    status=CLASSIFICATION_ALREADY_REGISTERED,
                    controller_profile=self.controller_profile,
                    repository=canonical,
                    project_id=manifest.project_id,
                    reason="repository is already registered for selected profile",
                    next_action="none",
                )
            return self._blocked(
                str(error),
                repository=canonical,
                project_id=manifest.project_id,
            )
        except PolicyViolationError as error:
            return self._blocked(
                str(error),
                repository=canonical,
                project_id=getattr(manifest, "project_id", None),
            )
        return RepositoryClassification(
            status=CLASSIFICATION_REGISTERABLE,
            controller_profile=self.controller_profile,
            repository=canonical,
            project_id=manifest.project_id,
            reason="committed project policy is ready to register",
            next_action="register",
            preview=preview,
        )

    def preview(self, github_url: str, *, board: str | None = None) -> RegistrationPreview:
        classification = self.classify(github_url, board=board)
        if classification.status != CLASSIFICATION_REGISTERABLE or classification.preview is None:
            raise RepositoryRegistrationError(classification.reason)
        return classification.preview

    def apply(
        self,
        github_url: str,
        *,
        board: str | None = None,
        expected_preview_digest: str,
        confirmation: str,
    ) -> RegistrationPreview:
        if confirmation != _CONFIRMATION:
            raise RepositoryRegistrationError(
                f"registration requires literal confirmation {_CONFIRMATION!r}"
            )
        preview = self.preview(github_url, board=board)
        if expected_preview_digest != preview.digest:
            raise RepositoryRegistrationError("repository registration preview is stale")
        self._apply_board(preview)
        registration_file = registration_path(self.data_root, preview.project_id)
        bindings_file = credential_bindings_path(registration_file)
        project_root = registration_file.parent
        _ensure_private_directory(self.data_root / "projects")
        _ensure_private_directory(project_root)
        registration_content = yaml.safe_dump(
            preview.registration.to_dict(),
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )
        bindings_content = yaml.safe_dump(
            preview.credential_bindings.to_dict(),
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )
        bindings_created = False
        if bindings_file.exists():
            try:
                current = read_private_text(
                    bindings_file,
                    maximum_bytes=16_384,
                    label="credential bindings",
                )
            except ProfileFileError as error:
                raise RepositoryRegistrationError(str(error)) from error
            if current != bindings_content:
                raise RepositoryRegistrationError(
                    "existing credential bindings do not match the preview"
                )
        else:
            atomic_write_private_text(
                bindings_file, bindings_content, label="credential bindings"
            )
            bindings_created = True
        try:
            atomic_write_private_text(
                registration_file, registration_content, label="controller registration"
            )
        except ProfileFileError:
            if not bindings_created:
                raise
            try:
                bindings_file.unlink()
            except OSError as error:
                raise RepositoryRegistrationError(
                    "registration failed and new credential bindings could not be removed"
                ) from error
            raise
        return preview

    def _board_action(self, board: str, checkout: Path) -> str:
        code, output = self.runner(
            ("hermes", "kanban", "boards", "list", "--json"),
            safe_runtime_environment(self.environ),
        )
        if code != 0 or not isinstance(output, str):
            raise RepositoryRegistrationError("Hermes board inventory is unavailable")
        try:
            rows = json.loads(output)
        except json.JSONDecodeError as error:
            raise RepositoryRegistrationError("Hermes board inventory is invalid") from error
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise RepositoryRegistrationError("Hermes board inventory is invalid")
        selected = next((row for row in rows if row.get("slug") == board), None)
        if selected is None:
            return "create"
        if selected.get("archived") is True:
            raise RepositoryRegistrationError("selected board is archived")
        workdir = selected.get("default_workdir")
        if workdir in {None, ""}:
            return "bind-and-set-workdir"
        if workdir == str(checkout):
            return "bind"
        raise RepositoryRegistrationError(
            "selected board workdir does not match the derived checkout"
        )

    def _board_is_registered(self, board: str) -> bool:
        """Reject a board slug already bound by any profile-local registration."""

        environment = safe_runtime_environment(self.environ)

        def run(command: tuple[str, ...]) -> tuple[int, str]:
            return self.runner(command, environment)

        try:
            profiles = list_profiles(run)
        except SetupWizardError as error:
            raise RepositoryRegistrationError("Hermes profile inventory is unavailable") from error
        for profile in profiles:
            if profile == self.controller_profile:
                continue
            try:
                root = resolve_profile_root(profile, run)
                registrations = list_controller_registrations(root)
            except (RepositoryRegistrationError, ValueError) as error:
                raise RepositoryRegistrationError(
                    "Daidala registration inventory is unavailable"
                ) from error
            if any(row.board == board for row in registrations):
                return True
        return False

    def _apply_board(self, preview: RegistrationPreview) -> None:
        checkout = preview.registration.checkout
        if preview.board_action == "create":
            command = (
                "hermes",
                "kanban",
                "boards",
                "create",
                preview.board,
                "--default-workdir",
                checkout,
            )
        elif preview.board_action == "bind-and-set-workdir":
            command = (
                "hermes",
                "kanban",
                "boards",
                "set-default-workdir",
                preview.board,
                checkout,
            )
        elif preview.board_action == "bind":
            return
        else:
            raise RepositoryRegistrationError("registration board action is invalid")
        code, _output = self.runner(command, safe_runtime_environment(self.environ))
        if code != 0:
            raise RepositoryRegistrationError("Hermes board could not be configured")

    def _blocked(
        self,
        reason: str,
        *,
        repository: str | None = None,
        project_id: str | None = None,
    ) -> RepositoryClassification:
        return RepositoryClassification(
            status=CLASSIFICATION_BLOCKED,
            controller_profile=self.controller_profile,
            repository=repository,
            project_id=project_id,
            reason=reason,
            next_action="none",
        )

    def _fetch_manifest(self, canonical: str) -> ProjectManifest:
        payload = self._github_json(
            ("gh", "api", f"repos/{canonical}/contents/.daidala/project.yaml"),
            "manifest",
        )
        encoded_content = payload.get("content")
        declared_size = payload.get("size")
        if (
            payload.get("type") != "file"
            or payload.get("encoding") != "base64"
            or not isinstance(encoded_content, str)
            or isinstance(declared_size, bool)
            or not isinstance(declared_size, int)
            or not 0 < declared_size <= MAX_MANIFEST_BYTES
        ):
            raise RepositoryRegistrationError("committed project manifest response is invalid")
        try:
            content = base64.b64decode(encoded_content.replace("\n", ""), validate=True)
        except (ValueError, binascii.Error) as error:
            raise RepositoryRegistrationError(
                "committed project manifest encoding is invalid"
            ) from error
        if len(content) != declared_size:
            raise RepositoryRegistrationError("committed project manifest size is invalid")
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise RepositoryRegistrationError(
                "committed project manifest is not UTF-8"
            ) from error
        return parse_project_manifest(text)

    def _github_json(self, command: tuple[str, ...], label: str) -> dict[str, object]:
        environment = safe_runtime_environment(self.environ)
        environment.update({"GH_PROMPT_DISABLED": "1", "GIT_TERMINAL_PROMPT": "0"})
        code, output = self.runner(command, environment)
        if (
            isinstance(code, bool)
            or not isinstance(code, int)
            or not isinstance(output, str)
            or len(output.encode("utf-8")) > MAX_GITHUB_OUTPUT_BYTES
            or code != 0
        ):
            if (
                label == "manifest"
                and isinstance(output, str)
                and _github_output_is_not_found(output)
            ):
                raise RepositoryRegistrationError(MISSING_PROJECT_POLICY)
            raise RepositoryRegistrationError(
                f"GitHub repository {label} is unavailable through the host authentication"
            )
        try:
            payload = json.loads(output)
        except json.JSONDecodeError as error:
            raise RepositoryRegistrationError(
                f"GitHub repository {label} response is invalid"
            ) from error
        if not isinstance(payload, dict):
            raise RepositoryRegistrationError(
                f"GitHub repository {label} response must be an object"
            )
        return payload


def parse_registration_defaults(content: str) -> RegistrationDefaults:
    raw = parse_strict_yaml(
        content,
        label="repository registration defaults",
        maximum_bytes=MAX_REGISTRATION_DEFAULTS_BYTES,
    )
    return RegistrationDefaults.from_dict(raw)


def load_registration_defaults(data_root: Path) -> RegistrationDefaults:
    path = data_root / REGISTRATION_DEFAULTS_FILENAME
    try:
        content = read_private_text(
            path,
            maximum_bytes=MAX_REGISTRATION_DEFAULTS_BYTES,
            label="repository registration defaults",
        )
    except FileNotFoundError as error:
        raise RepositoryRegistrationError(
            "repository registration defaults are not configured for this profile"
        ) from error
    except ProfileFileError as error:
        raise RepositoryRegistrationError(str(error)) from error
    return parse_registration_defaults(content)


def parse_github_repository_url(value: str) -> str:
    """Normalize one page or clone URL without treating it as authority."""

    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise RepositoryRegistrationError("GitHub repository URL must be non-empty text")
    candidate = value
    if candidate.startswith("github.com/"):
        candidate = "https://" + candidate
    scp_match = _SCP_GITHUB.fullmatch(candidate)
    if scp_match is not None:
        return _normalized_repository(
            scp_match.group("owner"), scp_match.group("repository")
        )
    parsed = urlsplit(candidate)
    if parsed.scheme not in {"https", "ssh"}:
        raise RepositoryRegistrationError("GitHub repository URL must use HTTPS or SSH")
    if parsed.query or parsed.fragment:
        raise RepositoryRegistrationError(
            "GitHub repository URL cannot contain a query or fragment"
        )
    if parsed.hostname is None or parsed.hostname.lower() != "github.com" or parsed.port:
        raise RepositoryRegistrationError("GitHub repository URL must use github.com")
    if parsed.scheme == "https" and (parsed.username is not None or parsed.password is not None):
        raise RepositoryRegistrationError("GitHub repository URL cannot contain credentials")
    if parsed.scheme == "ssh" and (parsed.username != "git" or parsed.password is not None):
        raise RepositoryRegistrationError("GitHub SSH URL must use the git user")
    parts = parsed.path.strip("/").split("/")
    if len(parts) != 2 or any(not part for part in parts):
        raise RepositoryRegistrationError(
            "GitHub repository URL must identify one owner and repository"
        )
    return _normalized_repository(parts[0], parts[1])


def resolve_profile_root(profile: str, run: ProfileCommandRunner) -> Path:
    """Resolve an existing profile through Hermes' documented profile surface."""

    _require_slug(profile, "repository registration profile")
    code, output = run(("hermes", "profile", "show", profile))
    if code != 0 or not isinstance(output, str):
        raise RepositoryRegistrationError("selected Hermes profile is unavailable")
    paths = [
        line.split(":", 1)[1].strip()
        for line in output.splitlines()
        if line.strip().startswith("Path:") and ":" in line
    ]
    if len(paths) != 1 or not paths[0]:
        raise RepositoryRegistrationError("Hermes profile path response is invalid")
    root = Path(paths[0]).expanduser().resolve()
    if not root.is_dir():
        raise RepositoryRegistrationError("selected Hermes profile root is unavailable")
    return root


def _normalized_repository(owner: str, repository: str) -> str:
    name = repository[:-4] if repository.endswith(".git") else repository
    canonical = f"{owner}/{name}"
    if not _REPOSITORY.fullmatch(canonical):
        raise RepositoryRegistrationError("GitHub repository identity is invalid")
    return canonical


def _repository_metadata(payload: dict[str, object]) -> tuple[str, str, str]:
    canonical = payload.get("full_name")
    ssh_url = payload.get("ssh_url")
    clone_url = payload.get("clone_url")
    if (
        not isinstance(canonical, str)
        or not _REPOSITORY.fullmatch(canonical)
        or not isinstance(ssh_url, str)
        or not isinstance(clone_url, str)
        or ssh_url != f"git@github.com:{canonical}.git"
        or clone_url != f"https://github.com/{canonical}.git"
    ):
        raise RepositoryRegistrationError("GitHub repository metadata response is invalid")
    return canonical, ssh_url, clone_url


def _github_output_is_not_found(output: str) -> bool:
    """Return True when host gh reports a missing GitHub object without private detail."""

    stripped = output.strip()
    if not stripped:
        return False
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        lowered = stripped.lower()
        return "404" in lowered and "not found" in lowered
    if not isinstance(payload, dict):
        return False
    message = payload.get("message")
    status = payload.get("status")
    if isinstance(status, str) and status == "404":
        return True
    if isinstance(status, int) and status == 404:
        return True
    return isinstance(message, str) and message.lower() == "not found"


def _ensure_private_directory(path: Path) -> None:
    try:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        if path.is_symlink() or not path.is_dir() or path.resolve() != path:
            raise RepositoryRegistrationError("registration directory is unsafe")
        path.chmod(0o700)
    except OSError as error:
        raise RepositoryRegistrationError("registration directory is unavailable") from error
