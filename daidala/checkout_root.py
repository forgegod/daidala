"""Strict profile-local checkout-root configuration and collision safety."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import yaml

from .errors import PolicyViolationError
from .live_adapters import RuntimeRunner
from .profile_files import ProfileFileError, atomic_write_private_text, read_private_text
from .projects import _require_slug, parse_strict_yaml
from .registrations import ControllerRegistration

CHECKOUTS_SCHEMA = "daidala.checkouts/v1"
CHECKOUTS_FILENAME = "checkouts.yaml"
OWNER_FILENAME = ".daidala-owner"
MAX_CHECKOUTS_BYTES = 16 * 1024
MAX_ROOT_BYTES = 4096
MAX_DISCOVERED_CHECKOUTS = 1024
_VALID_MODES = frozenset({"disabled", "manual", "ttl"})


class CheckoutRootError(PolicyViolationError):
    """Raised when checkout-root configuration or a checkout witness is unsafe."""


@dataclass(frozen=True)
class CheckoutConfig:
    """The complete, forward-compatible checkout configuration record."""

    root: Path
    mode: str = "disabled"
    ttl_hours: int = 0

    def __post_init__(self) -> None:
        _require_checkout_root(self.root)
        if self.mode not in _VALID_MODES:
            raise CheckoutRootError("checkout mode must be disabled, manual, or ttl")
        if (
            isinstance(self.ttl_hours, bool)
            or not isinstance(self.ttl_hours, int)
            or not 0 <= self.ttl_hours <= 8760
        ):
            raise CheckoutRootError("checkout ttl_hours must be an integer from 0 to 8760")
        if (self.mode == "ttl") != (self.ttl_hours > 0):
            raise CheckoutRootError("checkout ttl mode and ttl_hours must agree")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": CHECKOUTS_SCHEMA,
            "checkouts": {
                "root": str(self.root),
                "mode": self.mode,
                "ttl_hours": self.ttl_hours,
            },
        }


class CheckoutRootStore:
    """Read and atomically replace the one profile-local checkout configuration."""

    def __init__(self, data_root: Path) -> None:
        if (
            not isinstance(data_root, Path)
            or not data_root.is_absolute()
            or data_root.resolve() != data_root
        ):
            raise CheckoutRootError("checkout data root must be an absolute resolved path")
        self.data_root = data_root
        self.path = data_root / CHECKOUTS_FILENAME

    def default(self) -> CheckoutConfig:
        return CheckoutConfig(root=self.data_root / "work")

    def read(self) -> CheckoutConfig:
        try:
            content = read_private_text(
                self.path, maximum_bytes=MAX_CHECKOUTS_BYTES, label="checkout configuration"
            )
        except FileNotFoundError:
            return self.default()
        except ProfileFileError as error:
            raise CheckoutRootError(str(error)) from error
        return parse_checkout_config(content)

    def write(
        self, config: CheckoutConfig, registrations: tuple[ControllerRegistration, ...]
    ) -> bool:
        """Persist a validated configuration; identical content is a no-op."""

        self.validate_configuration(config, registrations)
        canonical = yaml.safe_dump(
            config.to_dict(), allow_unicode=True, default_flow_style=False, sort_keys=False
        )
        try:
            current = self.path.read_text(encoding="utf-8") if self.path.exists() else None
        except OSError as error:
            raise CheckoutRootError("cannot read checkout configuration") from error
        if current == canonical:
            return False
        try:
            atomic_write_private_text(self.path, canonical, label="checkout configuration")
        except ProfileFileError as error:
            raise CheckoutRootError(str(error)) from error
        return True

    def validate_configuration(
        self, config: CheckoutConfig, registrations: tuple[ControllerRegistration, ...]
    ) -> tuple[str, ...]:
        """Return mismatching IDs or reject a replacement that could orphan work."""

        current = self.read()
        owned = discover_owned_checkouts(current.root, registrations)
        if current.root != config.root and owned:
            raise CheckoutRootError(
                "checkout root replacement is blocked while owned checkouts exist"
            )
        mismatches = self.mismatching_project_ids(config, registrations)
        if mismatches:
            raise CheckoutRootError(
                "checkout root does not match registrations: " + ", ".join(mismatches)
            )
        return mismatches

    @staticmethod
    def mismatching_project_ids(
        config: CheckoutConfig, registrations: tuple[ControllerRegistration, ...]
    ) -> tuple[str, ...]:
        return tuple(
            registration.project_id
            for registration in registrations
            if checkout_path(config.root, registration.project_id) != Path(registration.checkout)
        )


def parse_checkout_config(content: str) -> CheckoutConfig:
    raw = parse_strict_yaml(
        content, label="checkout configuration", maximum_bytes=MAX_CHECKOUTS_BYTES
    )
    if set(raw) != {"schema", "checkouts"} or raw.get("schema") != CHECKOUTS_SCHEMA:
        raise CheckoutRootError("checkout configuration schema is invalid")
    checkouts = raw["checkouts"]
    if not isinstance(checkouts, dict) or set(checkouts) != {"root", "mode", "ttl_hours"}:
        raise CheckoutRootError("checkout configuration fields are invalid")
    root, mode, ttl_hours = checkouts["root"], checkouts["mode"], checkouts["ttl_hours"]
    if not isinstance(root, str):
        raise CheckoutRootError("checkout root must be a string")
    return CheckoutConfig(root=Path(root), mode=mode, ttl_hours=ttl_hours)


def checkout_path(root: Path, project_id: str) -> Path:
    _require_checkout_root(root)
    _require_slug(project_id, "checkout project ID")
    return root / project_id


def discover_owned_checkouts(
    root: Path, registrations: tuple[ControllerRegistration, ...]
) -> tuple[Path, ...]:
    """Find owned child directories without following links or silently skipping errors."""

    _require_checkout_root(root)
    if not root.exists():
        return ()
    if root.is_symlink() or not root.is_dir():
        raise CheckoutRootError("checkout root must be a real directory")
    try:
        children = list(os.scandir(root))
    except OSError as error:
        raise CheckoutRootError("cannot scan checkout root") from error
    if len(children) > MAX_DISCOVERED_CHECKOUTS:
        raise CheckoutRootError("checkout root exceeds the ownership scan bound")
    by_path = {
        checkout_path(root, registration.project_id): registration
        for registration in registrations
    }
    owned: list[Path] = []
    for entry in children:
        path = Path(entry.path)
        try:
            if entry.is_symlink() or not entry.is_dir(follow_symlinks=False):
                continue
        except OSError as error:
            raise CheckoutRootError("cannot inspect checkout root entry") from error
        registration = by_path.get(path)
        if registration is None:
            continue
        marker = path / OWNER_FILENAME
        if not marker.exists() and not marker.is_symlink():
            continue
        if _owner_marker_matches(marker, registration.project_id):
            owned.append(path)
    return tuple(sorted(owned))


def validate_reusable_checkout(
    path: Path, registration: ControllerRegistration, runner: RuntimeRunner
) -> None:
    """Require an existing checkout to carry the exact Daidala ownership witness."""

    expected = checkout_path(path.parent, registration.project_id)
    if path != expected or Path(registration.checkout) != expected:
        raise CheckoutRootError("checkout path does not match the registration-derived path")
    if not path.exists():
        return
    if path.is_symlink() or not path.is_dir():
        raise CheckoutRootError("existing checkout must be a real directory")
    if not _owner_marker_matches(path / OWNER_FILENAME, registration.project_id):
        raise CheckoutRootError("existing checkout is not owned by this project")
    for command, label in (
        (("git", "-C", str(path), "config", "--get", "remote.origin.url"), "origin"),
        (
            ("git", "-C", str(path), "ls-files", "--error-unmatch", OWNER_FILENAME),
            "tracked owner marker",
        ),
        (
            ("git", "-C", str(path), "check-ignore", "--quiet", OWNER_FILENAME),
            "ignored owner marker",
        ),
    ):
        code, output = runner(command, {})
        if label == "origin":
            if code != 0 or output.strip() != registration.verified_remote:
                raise CheckoutRootError(
                    "existing checkout origin does not match trusted registration"
                )
        elif code == 0:
            raise CheckoutRootError(f"{label} is invalid")


def _owner_marker_matches(path: Path, project_id: str) -> bool:
    try:
        content = read_private_text(path, maximum_bytes=256, label="checkout owner marker")
    except (FileNotFoundError, ProfileFileError):
        return False
    return content.strip() == project_id


def _require_checkout_root(path: Path) -> None:
    if not isinstance(path, Path):
        raise CheckoutRootError("checkout root must be a path")
    raw = str(path)
    if len(raw.encode("utf-8")) > MAX_ROOT_BYTES:
        raise CheckoutRootError("checkout root exceeds 4096 bytes")
    pure = PurePosixPath(raw)
    if not pure.is_absolute() or "." in pure.parts or ".." in pure.parts or raw != str(pure):
        raise CheckoutRootError("checkout root must be a normalized absolute POSIX path")
    for parent in reversed(path.parents):
        if parent.exists() and parent.is_symlink():
            raise CheckoutRootError("checkout root cannot traverse a symlink")
