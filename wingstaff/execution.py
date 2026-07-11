"""Artifact and Git-worktree operations for executable workflows."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import WorkflowError
from .state import ActivationManifest

_WORKFLOW_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


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
        filename: str,
        content: str,
    ) -> StoredArtifact:
        directory = self._workflow_root(workflow_id) / "artifacts"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / filename
        path.write_text(content, encoding="utf-8")
        return StoredArtifact(
            path=str(path),
            digest=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        )

    def write_json_artifact(
        self,
        workflow_id: str,
        filename: str,
        payload: dict[str, Any],
    ) -> StoredArtifact:
        content = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        return self.write_artifact(workflow_id, filename, content)

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
            f"-{manifest.sequence}.json"
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

    def read_json_artifact(self, workflow_id: str, filename: str) -> dict[str, Any]:
        """Read a Wingstaff-owned JSON sidecar from the workflow artifact root."""
        path = self._workflow_root(workflow_id) / "artifacts" / filename
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ExecutionError(f"cannot read workflow artifact {filename!r}") from error
        if not isinstance(payload, dict):
            raise ExecutionError(f"workflow artifact {filename!r} must be an object")
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
        """Remove only a worktree owned by this Wingstaff data root."""
        worktree = Path(worktree_path).resolve()
        owned_root = (self.data_root / "worktrees").resolve()
        if worktree.parent != owned_root:
            raise ExecutionError(f"refusing to remove non-Wingstaff worktree: {worktree}")
        if not worktree.exists():
            return
        _git(Path(target_repository), "worktree", "remove", "--force", str(worktree))

    def _untracked_paths(self, worktree: Path) -> tuple[str, ...]:
        raw = _git(worktree, "ls-files", "--others", "--exclude-standard", "-z")
        return tuple(path for path in raw.split("\0") if path)

    def _workflow_root(self, workflow_id: str) -> Path:
        return self.data_root / "workflows" / self._safe_id(workflow_id)

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
