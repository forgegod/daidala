"""Artifact and Git-worktree operations for executable workflows."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .errors import WorkflowError
from .state import ActivationManifest, WorkflowConstraintsArtifact, WorkflowStage

_WORKFLOW_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_ARTIFACT_RELATIVE_PATH_MAX = 512


class ExecutionError(WorkflowError):
    """Raised when an artifact or worktree operation fails."""


@dataclass(frozen=True)
class StoredArtifact:
    path: str
    digest: str


class ExecutionWorkspace:
    """Own profile-local artifacts and detached target worktrees."""

    def __init__(self, data_root: Path) -> None:
        self.data_root = Path(data_root).resolve()

    def validate_workflow_id(self, workflow_id: str) -> str:
        """Validate an ID before it can influence a runtime path."""
        return self._safe_id(workflow_id)

    def write_artifact(
        self,
        workflow_id: str,
        relative_path: str,
        content: str,
    ) -> StoredArtifact:
        if not isinstance(content, str):
            raise ExecutionError("workflow artifact content must be text")
        path = self._artifact_path(workflow_id, relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        encoded = content.encode("utf-8")
        temporary_path: Path | None = None
        try:
            descriptor, temporary = tempfile.mkstemp(
                dir=path.parent,
                prefix=".daidala-artifact-",
            )
            temporary_path = Path(temporary)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(encoded)
            try:
                os.link(temporary_path, path)
            except FileExistsError as exists_error:
                self._verify_existing_artifact(
                    path,
                    relative_path=relative_path,
                    expected=encoded,
                    exists_error=exists_error,
                )
        except OSError as error:
            raise ExecutionError(
                f"cannot create workflow artifact {relative_path!r}"
            ) from error
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
        return StoredArtifact(
            path=str(path),
            digest=hashlib.sha256(encoded).hexdigest(),
        )

    def write_json_artifact(
        self,
        workflow_id: str,
        relative_path: str,
        payload: dict[str, Any],
    ) -> StoredArtifact:
        content = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        return self.write_artifact(workflow_id, relative_path, content)

    def stage_artifact_relative_path(
        self,
        *,
        stage: WorkflowStage,
        policy_revision: int,
        plan_revision: int,
        filename: str,
    ) -> str:
        """Return one validated policy/plan-scoped stage artifact path."""
        if not isinstance(stage, WorkflowStage) or stage is WorkflowStage.APPROVAL:
            raise ExecutionError("workflow artifact stage is not executable")
        for name, revision in (
            ("policy", policy_revision),
            ("plan", plan_revision),
        ):
            if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
                raise ExecutionError(f"workflow artifact {name} revision must be non-negative")
        leaf = self._safe_artifact_relative_path(filename)
        if len(leaf.parts) != 1:
            raise ExecutionError("workflow artifact filename must be one relative path segment")
        policy = f"policy-{policy_revision:04d}"
        relative = (
            PurePosixPath(policy, filename)
            if stage is WorkflowStage.DEFINE
            else PurePosixPath(policy, f"plan-{plan_revision:04d}", filename)
        )
        return self._safe_artifact_relative_path(relative.as_posix()).as_posix()

    def artifact_path(self, workflow_id: str, relative_path: str) -> str:
        """Return the validated absolute path for one workflow artifact."""
        return str(self._artifact_path(workflow_id, relative_path))

    def write_activation_manifest(
        self,
        workflow_id: str,
        manifest: ActivationManifest,
    ) -> StoredArtifact:
        """Create one canonical activation artifact without overwriting collisions."""
        if workflow_id != manifest.workflow_id:
            raise ExecutionError("activation manifest workflow ID does not match artifact root")
        filename = (
            f"skill-activation-{manifest.stage.value}-r{manifest.plan_revision}"
            f"-p{manifest.policy_revision}-{manifest.sequence}.json"
        )
        directory = self._workflow_root(workflow_id) / "artifacts"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / filename
        content = manifest.canonical_bytes()
        try:
            with path.open("xb") as stream:
                stream.write(content)
        except FileExistsError as error:
            raise ExecutionError(f"workflow artifact already exists: {filename!r}") from error
        except OSError as error:
            raise ExecutionError(f"cannot create workflow artifact {filename!r}") from error
        return StoredArtifact(
            path=str(path),
            digest=hashlib.sha256(content).hexdigest(),
        )

    def activation_manifest_path(
        self,
        workflow_id: str,
        manifest: ActivationManifest,
    ) -> str:
        """Return the deterministic path reserved for an activation manifest."""
        if workflow_id != manifest.workflow_id:
            raise ExecutionError("activation manifest workflow ID does not match artifact root")
        filename = (
            f"skill-activation-{manifest.stage.value}-r{manifest.plan_revision}"
            f"-p{manifest.policy_revision}-{manifest.sequence}.json"
        )
        return str(self._workflow_root(workflow_id) / "artifacts" / filename)

    def write_constraints_artifact(
        self, workflow_id: str, artifact: WorkflowConstraintsArtifact
    ) -> StoredArtifact:
        """Create and read back one immutable workflow constraint artifact."""
        if workflow_id != artifact.workflow_id:
            raise ExecutionError("constraint artifact workflow ID does not match artifact root")
        filename = f"workflow-constraints-{artifact.identity.constraints_revision}.json"
        directory = self._workflow_root(workflow_id) / "artifacts" / "constraints"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / filename
        try:
            with path.open("xb") as stream:
                stream.write(artifact.canonical_bytes())
        except FileExistsError as error:
            raise ExecutionError(f"workflow artifact already exists: {filename!r}") from error
        except OSError as error:
            raise ExecutionError(f"cannot create workflow artifact {filename!r}") from error
        if self.read_constraints_artifact(workflow_id, str(path)) != artifact:
            raise ExecutionError("constraint artifact read-back verification failed")
        return StoredArtifact(path=str(path), digest=artifact.identity.digest)

    def constraints_artifact_path(self, workflow_id: str, revision: int) -> str:
        """Return the deterministic path for one immutable constraint revision."""
        return str(
            self._workflow_root(workflow_id)
            / "artifacts"
            / "constraints"
            / f"workflow-constraints-{revision}.json"
        )

    def read_constraints_artifact(
        self, workflow_id: str, path: str
    ) -> WorkflowConstraintsArtifact:
        artifact_path = Path(path).resolve()
        expected = (self._workflow_root(workflow_id) / "artifacts" / "constraints").resolve()
        if artifact_path.parent != expected:
            raise ExecutionError("constraint artifact path is outside its workflow root")
        try:
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ExecutionError("cannot read constraint artifact") from error
        return WorkflowConstraintsArtifact.from_dict(payload)

    def read_activation_manifest(self, workflow_id: str, path: str) -> ActivationManifest:
        """Read one activation manifest only from its Daidala-owned artifact root."""
        artifact = Path(path).resolve()
        expected_parent = (self._workflow_root(workflow_id) / "artifacts").resolve()
        if artifact.parent != expected_parent:
            raise ExecutionError("activation manifest path is outside the workflow artifact root")
        try:
            payload = json.loads(artifact.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ExecutionError("cannot read activation manifest") from error
        return ActivationManifest.from_dict(payload)

    def read_json_artifact(self, workflow_id: str, path: str) -> dict[str, Any]:
        """Read a JSON sidecar through its authoritative absolute artifact path."""
        artifact_path = self._referenced_artifact_path(workflow_id, path)
        try:
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ExecutionError(f"cannot read workflow artifact {path!r}") from error
        if not isinstance(payload, dict):
            raise ExecutionError(f"workflow artifact {path!r} must be an object")
        return payload

    def create_worktree(
        self,
        workflow_id: str,
        target_repository: str,
        baseline_commit: str,
    ) -> str:
        worktree = self.data_root / "worktrees" / self._safe_id(workflow_id)
        if worktree.exists():
            head = _git(worktree, "rev-parse", "HEAD")
            status = _git(worktree, "status", "--porcelain=v1")
            if head == baseline_commit and not status:
                return str(worktree)
            raise ExecutionError(f"workflow worktree already exists: {worktree}")
        worktree.parent.mkdir(parents=True, exist_ok=True)
        _git(
            Path(target_repository),
            "worktree",
            "add",
            "--detach",
            str(worktree),
            baseline_commit,
        )
        return str(worktree)

    def capture_diff(self, worktree_path: str) -> str:
        worktree = Path(worktree_path)
        tracked = _git(worktree, "diff", "--binary", "--no-ext-diff", "HEAD")
        parts = [tracked] if tracked else []
        for relative in self._untracked_paths(worktree):
            completed = _run_git(
                worktree,
                "diff",
                "--no-index",
                "--binary",
                "--",
                "/dev/null",
                relative,
            )
            if completed.returncode not in {0, 1}:
                raise ExecutionError(_git_error(completed))
            if completed.stdout:
                parts.append(completed.stdout.rstrip())
        diff = "\n".join(parts).strip()
        if not diff:
            raise ExecutionError("implementation produced no working-tree diff")
        return diff + "\n"

    def changed_paths(self, worktree_path: str) -> tuple[str, ...]:
        worktree = Path(worktree_path)
        tracked = _git(worktree, "diff", "--name-only", "-z", "HEAD").split("\0")
        tracked = [path for path in tracked if path]
        return tuple(sorted(set(tracked) | set(self._untracked_paths(worktree))))

    def remove_worktree(self, target_repository: str, worktree_path: str) -> None:
        """Remove only a worktree owned by this Daidala data root."""
        worktree = Path(worktree_path).resolve()
        owned_root = (self.data_root / "worktrees").resolve()
        if worktree.parent != owned_root:
            raise ExecutionError(f"refusing to remove non-Daidala worktree: {worktree}")
        if not worktree.exists():
            return
        _git(Path(target_repository), "worktree", "remove", "--force", str(worktree))

    def _untracked_paths(self, worktree: Path) -> tuple[str, ...]:
        raw = _git(worktree, "ls-files", "--others", "--exclude-standard", "-z")
        return tuple(path for path in raw.split("\0") if path)

    def _workflow_root(self, workflow_id: str) -> Path:
        return self.data_root / "workflows" / self._safe_id(workflow_id)

    def _artifact_path(self, workflow_id: str, relative_path: str) -> Path:
        relative = self._safe_artifact_relative_path(relative_path)
        root = self._artifact_root(workflow_id)
        path = root.joinpath(*relative.parts)
        current = path
        while current != root:
            if current.is_symlink():
                raise ExecutionError("workflow artifact relative path contains a symlink")
            current = current.parent
        resolved = path.resolve(strict=False)
        if resolved != root and root not in resolved.parents:
            raise ExecutionError("workflow artifact relative path escapes its workflow root")
        return path

    def _artifact_root(self, workflow_id: str) -> Path:
        unresolved_root = self._workflow_root(workflow_id) / "artifacts"
        current = unresolved_root
        while current != self.data_root:
            if current.is_symlink():
                raise ExecutionError("workflow artifact root contains a symlink")
            current = current.parent
        return unresolved_root.resolve()

    def _referenced_artifact_path(self, workflow_id: str, path: str) -> Path:
        if not isinstance(path, str) or not path or not Path(path).is_absolute():
            raise ExecutionError("workflow artifact reference must be an absolute path")
        root = self._artifact_root(workflow_id)
        artifact = Path(path)
        resolved = artifact.resolve(strict=False)
        if artifact != resolved:
            raise ExecutionError("workflow artifact reference must be normalized")
        if resolved != root and root not in resolved.parents:
            raise ExecutionError("workflow artifact reference is outside its workflow root")
        current = artifact
        while current != root:
            if current == current.parent:
                raise ExecutionError("workflow artifact reference is outside its workflow root")
            if current.is_symlink():
                raise ExecutionError("workflow artifact reference contains a symlink")
            current = current.parent
        return artifact

    @staticmethod
    def _verify_existing_artifact(
        path: Path,
        *,
        relative_path: str,
        expected: bytes,
        exists_error: FileExistsError,
    ) -> None:
        try:
            existing = path.read_bytes()
        except OSError as read_error:
            raise ExecutionError(
                f"cannot verify workflow artifact {relative_path!r}"
            ) from read_error
        if existing != expected:
            raise ExecutionError(
                f"workflow artifact content conflicts: {relative_path!r}"
            ) from exists_error

    @staticmethod
    def _safe_artifact_relative_path(relative_path: str) -> PurePosixPath:
        if (
            not isinstance(relative_path, str)
            or not relative_path
            or len(relative_path) > _ARTIFACT_RELATIVE_PATH_MAX
            or "\\" in relative_path
            or "\x00" in relative_path
        ):
            raise ExecutionError("workflow artifact relative path is malformed or oversized")
        path = PurePosixPath(relative_path)
        if (
            path.is_absolute()
            or path.as_posix() != relative_path
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise ExecutionError("workflow artifact relative path is malformed or unsafe")
        return path

    @staticmethod
    def _safe_id(workflow_id: str) -> str:
        if not isinstance(workflow_id, str) or not _WORKFLOW_ID.fullmatch(workflow_id):
            raise ExecutionError(
                "workflow_id must use 1-128 letters, digits, dots, underscores, or hyphens"
            )
        return workflow_id


def _git(target: Path, *args: str) -> str:
    completed = _run_git(target, *args)
    if completed.returncode != 0:
        raise ExecutionError(_git_error(completed))
    return completed.stdout.strip()


def _run_git(target: Path, *args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(target), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ExecutionError(f"git operation failed: {error}") from error


def _git_error(completed: subprocess.CompletedProcess[str]) -> str:
    message = completed.stderr.strip() or completed.stdout.strip() or "git operation failed"
    return f"git operation failed: {message}"
