"""Strict Git-object admission for one pending repository plan phase."""

from __future__ import annotations

import hashlib
import re
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath

from .errors import PolicyViolationError
from .state import PlanSourceReference
from .workflow import new_plan_source_packet

MAX_PLAN_DOCUMENT_BYTES = 1_048_576
_PLAN_PATH = re.compile(r"^P[0-9]{4}-.+\.md$")
_PLAN_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,127}$")
_SLOT = re.compile(r"^P[0-9]{4}$")
_REVISION = re.compile(r"^[0-9a-f]{40}$")
_DONE = re.compile(r"^done \(\S(?:[^()\r\n]*\S)?\)$")
_HEADER = re.compile(
    r"^\*\*(Plan ID|Execution slot|Created|Depends on|Status):\*\*\s*(\S(?:.*\S)?)\s*$"
)
_PHASE_HEADING = re.compile(r"^## Phase ([0-9]+) — (\S(?:.*\S)?)\s*$", re.MULTILINE)
_PHASE_GATE = re.compile(r"^Verification gate:\s*(\S(?:.*\S)?)\s*$", re.MULTILINE)

GitRunner = Callable[[Path, tuple[str, ...]], bytes]


@dataclass(frozen=True)
class ParsedPlanPhase:
    """The one phase table row and body section that may become a packet."""

    number: int
    title: str
    status: str
    verification_gate: str


@dataclass(frozen=True)
class ParsedPlan:
    """Strict active-plan metadata parsed from immutable Markdown bytes."""

    plan_id: str
    execution_slot: str
    status: str
    dependencies: tuple[str, ...]
    phases: tuple[ParsedPlanPhase, ...]


def admit_plan_source(
    *,
    repository: Path,
    plan_path: str,
    source_revision: str,
    baseline_commit: str,
    phase_number: int,
    predecessor_workflow_id: str | None = None,
    git_runner: GitRunner | None = None,
):
    """Read exactly one pending phase from a clean committed plan object."""
    _require_plan_path(plan_path)
    _require_revision(source_revision, "plan source revision")
    _require_revision(baseline_commit, "plan baseline commit")
    if source_revision != baseline_commit:
        raise PolicyViolationError("plan source revision must equal baseline commit")
    if (
        isinstance(phase_number, bool)
        or not isinstance(phase_number, int)
        or phase_number < 0
    ):
        raise PolicyViolationError("plan phase number must be a non-negative integer")

    target = _require_repository_root(repository)
    runner = git_runner or _run_git
    root = _git_text(runner, target, "rev-parse", "--show-toplevel")
    if Path(root).resolve() != target:
        raise PolicyViolationError("plan repository must name the repository root")
    head = _git_text(runner, target, "rev-parse", "HEAD")
    if head != source_revision:
        raise PolicyViolationError("plan source revision must equal clean repository HEAD")
    if _git_text(runner, target, "status", "--porcelain=v1", "--untracked-files=normal"):
        raise PolicyViolationError("plan repository must be clean")

    plan_blob_id, plan_bytes = _read_regular_blob(runner, target, source_revision, plan_path)
    plan_text = _decode_plan(plan_bytes, plan_path)
    documents = _read_active_plan_documents(runner, target, source_revision)
    if plan_path not in documents:
        raise PolicyViolationError("selected plan is not an active repository plan")
    documents[plan_path] = plan_text
    plans = parse_plan_inventory(documents)
    selected = plans[plan_path]
    _require_complete_dependencies(selected, plans)
    phase = select_pending_phase(selected, phase_number)
    reference = PlanSourceReference(
        schema="daidala.plan-source-reference/v1",
        repository=str(target),
        source_revision=source_revision,
        baseline_commit=baseline_commit,
        plan_path=plan_path,
        plan_blob_id=plan_blob_id,
        plan_digest=hashlib.sha256(plan_bytes).hexdigest(),
        byte_size=len(plan_bytes),
    )
    return new_plan_source_packet(
        reference=reference,
        plan_id=selected.plan_id,
        execution_slot=selected.execution_slot,
        phase_number=phase.number,
        phase_title=phase.title,
        verification_gate=phase.verification_gate,
        direct_dependencies=selected.dependencies,
        predecessor_workflow_id=predecessor_workflow_id,
    )


def parse_plan_inventory(documents: Mapping[str, str]) -> dict[str, ParsedPlan]:
    """Parse every explicit active plan document and validate its dependency graph."""
    if not isinstance(documents, Mapping) or not documents:
        raise PolicyViolationError("active plan inventory must contain at least one document")
    parsed: dict[str, ParsedPlan] = {}
    plan_ids: dict[str, str] = {}
    slots: dict[str, str] = {}
    for path, content in sorted(documents.items()):
        _require_plan_path(path)
        plan = parse_plan_document(path, content)
        if plan.plan_id in plan_ids:
            raise PolicyViolationError("active plan inventory has duplicate Plan ID")
        if plan.execution_slot in slots:
            raise PolicyViolationError("active plan inventory has duplicate execution slot")
        parsed[path] = plan
        plan_ids[plan.plan_id] = path
        slots[plan.execution_slot] = path
    for plan in parsed.values():
        unknown = sorted(set(plan.dependencies) - set(plan_ids))
        if unknown:
            raise PolicyViolationError(
                f"plan {plan.plan_id!r} has unknown dependencies: {', '.join(unknown)}"
            )
    _require_acyclic_dependencies(parsed, plan_ids)
    return parsed


def parse_plan_document(path: str, content: str) -> ParsedPlan:
    """Parse one bounded new-shape active plan without repairing Markdown."""
    _require_plan_path(path)
    if not isinstance(content, str) or not content.strip():
        raise PolicyViolationError("plan document must be a non-empty UTF-8 string")
    if len(content.encode("utf-8")) > MAX_PLAN_DOCUMENT_BYTES:
        raise PolicyViolationError("plan document exceeds the bounded-document limit")
    if "\x00" in content or any(
        ord(character) < 32 and character not in "\n\r\t" for character in content
    ):
        raise PolicyViolationError("plan document contains control characters")

    preamble = content.split("\n## ", 1)[0]
    headers: dict[str, str] = {}
    for line in preamble.splitlines():
        match = _HEADER.fullmatch(line)
        if match is None:
            continue
        label, value = match.groups()
        if label in headers:
            raise PolicyViolationError(f"plan document has duplicate {label!r} header")
        headers[label] = value
    required = {"Plan ID", "Execution slot", "Created", "Depends on", "Status"}
    missing = sorted(required - set(headers))
    if missing:
        raise PolicyViolationError(f"plan document is missing headers: {', '.join(missing)}")
    if not _PLAN_ID.fullmatch(headers["Plan ID"]):
        raise PolicyViolationError("plan Plan ID must be canonical")
    if not _SLOT.fullmatch(headers["Execution slot"]):
        raise PolicyViolationError("plan Execution slot must be P plus four digits")
    if not Path(path).name.startswith(f"{headers['Execution slot']}-"):
        raise PolicyViolationError("plan filename slot does not match Execution slot")
    try:
        date.fromisoformat(headers["Created"])
    except ValueError as error:
        raise PolicyViolationError("plan Created must be an ISO date") from error
    dependencies = _parse_dependencies(headers["Depends on"])
    document_status = _parse_document_status(headers["Status"])
    table_rows = _parse_phase_table(content)
    sections = _parse_phase_sections(content)
    if set(table_rows) != set(sections):
        raise PolicyViolationError("plan phase table and headings do not match")
    if sorted(table_rows) != list(range(len(table_rows))):
        raise PolicyViolationError("plan phase numbers must start at zero and be contiguous")
    phases = []
    for number in sorted(table_rows):
        title, status, gate = table_rows[number]
        section_title, section_gates = sections[number]
        if title != section_title:
            raise PolicyViolationError("plan phase table title does not match its heading")
        if len(section_gates) != 1:
            raise PolicyViolationError(
                "plan phase section must declare exactly one verification gate"
            )
        phases.append(ParsedPlanPhase(number, title, status, gate))
    all_done = all(_DONE.fullmatch(phase.status) for phase in phases)
    if document_status == "complete" and not all_done:
        raise PolicyViolationError("complete plan documents require done phase evidence")
    if document_status == "pending" and all_done:
        raise PolicyViolationError("all-done plan documents must be marked complete")
    return ParsedPlan(
        plan_id=headers["Plan ID"],
        execution_slot=headers["Execution slot"],
        status=document_status,
        dependencies=dependencies,
        phases=tuple(phases),
    )


def select_pending_phase(plan: ParsedPlan, phase_number: int) -> ParsedPlanPhase:
    """Require one pending phase with completed predecessors and pending successors."""
    if plan.status != "pending":
        raise PolicyViolationError("selected plan document must be pending")
    if isinstance(phase_number, bool) or not isinstance(phase_number, int):
        raise PolicyViolationError("selected plan phase number is invalid")
    try:
        selected = plan.phases[phase_number]
    except IndexError as error:
        raise PolicyViolationError("selected plan phase does not exist") from error
    if selected.status != "pending":
        raise PolicyViolationError("selected plan phase must be pending")
    if any(not _DONE.fullmatch(phase.status) for phase in plan.phases[:phase_number]):
        raise PolicyViolationError("preceding plan phases must have well-formed done evidence")
    if any(phase.status != "pending" for phase in plan.phases[phase_number + 1 :]):
        raise PolicyViolationError("following plan phases must remain pending")
    return selected


def _parse_dependencies(value: str) -> tuple[str, ...]:
    if value == "none":
        return ()
    dependencies = tuple(part.strip() for part in value.split(","))
    if not dependencies or any(not _PLAN_ID.fullmatch(part) for part in dependencies):
        raise PolicyViolationError("plan dependencies must be canonical Plan IDs or none")
    if len(dependencies) != len(set(dependencies)):
        raise PolicyViolationError("plan dependencies cannot contain duplicates")
    return dependencies


def _parse_document_status(value: str) -> str:
    token = value.split(" —", 1)[0]
    if token not in {"pending", "complete"}:
        raise PolicyViolationError("plan document status must be pending or complete")
    return token


def _parse_phase_table(content: str) -> dict[int, tuple[str, str, str]]:
    lines = content.splitlines()
    try:
        index = lines.index("| # | Phase | Status | Verification gate |")
    except ValueError as error:
        raise PolicyViolationError("plan must contain one exact phase table header") from error
    if index + 1 >= len(lines) or lines[index + 1] != "|---|---|---|---|":
        raise PolicyViolationError("plan phase table separator is invalid")
    rows: dict[int, tuple[str, str, str]] = {}
    for line in lines[index + 2 :]:
        if not line.startswith("|"):
            break
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if len(cells) != 4:
            raise PolicyViolationError("plan phase table row must have four cells")
        number_text, title, status, gate = cells
        if not number_text.isdecimal() or not title or not gate:
            raise PolicyViolationError("plan phase table row is malformed")
        number = int(number_text)
        if number in rows:
            raise PolicyViolationError("plan phase table has duplicate phase numbers")
        if not gate.startswith("`") or " exits 0" not in gate:
            raise PolicyViolationError(
                "plan phase verification gate must name an executable command"
            )
        rows[number] = (title, _parse_phase_status(status), gate)
    if not rows:
        raise PolicyViolationError("plan phase table must contain at least one phase")
    return rows


def _parse_phase_sections(content: str) -> dict[int, tuple[str, tuple[str, ...]]]:
    headings = tuple(_PHASE_HEADING.finditer(content))
    if not headings:
        raise PolicyViolationError("plan must contain phase sections")
    sections: dict[int, tuple[str, tuple[str, ...]]] = {}
    for index, heading in enumerate(headings):
        number = int(heading.group(1))
        if number in sections:
            raise PolicyViolationError("plan has duplicate phase headings")
        end = headings[index + 1].start() if index + 1 < len(headings) else len(content)
        gates = tuple(
            match.group(1) for match in _PHASE_GATE.finditer(content[heading.end() : end])
        )
        sections[number] = (heading.group(2), gates)
    return sections


def _parse_phase_status(value: str) -> str:
    if value == "pending":
        return value
    if _DONE.fullmatch(value):
        return value
    raise PolicyViolationError("plan phase status must be pending or done with evidence")


def _require_complete_dependencies(selected: ParsedPlan, plans: Mapping[str, ParsedPlan]) -> None:
    by_id = {plan.plan_id: plan for plan in plans.values()}
    incomplete = [
        dependency
        for dependency in selected.dependencies
        if by_id[dependency].status != "complete"
    ]
    if incomplete:
        raise PolicyViolationError(
            f"selected plan has incomplete dependencies: {', '.join(incomplete)}"
        )


def _require_acyclic_dependencies(
    plans: Mapping[str, ParsedPlan], plan_ids: Mapping[str, str]
) -> None:
    visiting: set[str] = set()
    complete: set[str] = set()

    def visit(plan_id: str) -> None:
        if plan_id in complete:
            return
        if plan_id in visiting:
            raise PolicyViolationError("active plan dependencies contain a cycle")
        visiting.add(plan_id)
        for dependency in plans[plan_ids[plan_id]].dependencies:
            visit(dependency)
        visiting.remove(plan_id)
        complete.add(plan_id)

    for plan_id in plan_ids:
        visit(plan_id)


def _read_active_plan_documents(
    runner: GitRunner, repository: Path, revision: str
) -> dict[str, str]:
    names = _git(
        runner,
        repository,
        "ls-tree",
        "-r",
        "-z",
        "--name-only",
        revision,
        "--",
        "docs/plans",
    )
    raw_documents: dict[str, bytes] = {}
    for raw_name in names.split(b"\0"):
        if not raw_name:
            continue
        try:
            path = raw_name.decode("utf-8")
        except UnicodeDecodeError as error:
            raise PolicyViolationError("repository plan path is not UTF-8") from error
        if not _PLAN_PATH.fullmatch(PurePosixPath(path).name):
            continue
        _blob_id, content = _read_regular_blob(runner, repository, revision, path)
        if b"**Plan ID:**" not in content or b"**Execution slot:**" not in content:
            continue
        raw_documents[path] = content

    headers = {path: _source_headers(content) for path, content in raw_documents.items()}
    selected_paths = {
        path for path, values in headers.items() if _is_pending_source_plan(values)
    }
    by_plan_id: dict[str, list[str]] = {}
    for path, values in headers.items():
        plan_id = values.get("Plan ID")
        if plan_id is not None:
            by_plan_id.setdefault(plan_id, []).append(path)
    pending = list(selected_paths)
    while pending:
        path = pending.pop()
        for dependency in _source_dependencies(headers[path]):
            for dependency_path in by_plan_id.get(dependency, []):
                if dependency_path not in selected_paths:
                    selected_paths.add(dependency_path)
                    pending.append(dependency_path)
    return {
        path: _decode_plan(raw_documents[path], path)
        for path in sorted(selected_paths)
    }


def _source_headers(content: bytes) -> dict[str, str]:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return {}
    values: dict[str, str] = {}
    for line in text.split("\n## ", 1)[0].splitlines():
        match = _HEADER.fullmatch(line)
        if match is not None and match.group(1) not in values:
            values[match.group(1)] = match.group(2)
    return values


def _is_pending_source_plan(headers: Mapping[str, str]) -> bool:
    status = headers.get("Status")
    return status == "pending" or (status is not None and status.startswith("pending —"))


def _source_dependencies(headers: Mapping[str, str]) -> tuple[str, ...]:
    value = headers.get("Depends on")
    if value is None or value == "none":
        return ()
    dependencies = tuple(part.strip() for part in value.split(","))
    if any(not _PLAN_ID.fullmatch(dependency) for dependency in dependencies):
        return ()
    return dependencies


def _read_regular_blob(
    runner: GitRunner, repository: Path, revision: str, path: str
) -> tuple[str, bytes]:
    tree = _git(runner, repository, "ls-tree", "-z", revision, "--", path)
    entries = tuple(row for row in tree.split(b"\0") if row)
    if len(entries) != 1 or b"\t" not in entries[0]:
        raise PolicyViolationError("plan source must resolve to exactly one tree entry")
    metadata, encoded_path = entries[0].split(b"\t", 1)
    fields = metadata.split(b" ")
    if len(fields) != 3:
        raise PolicyViolationError("plan source tree entry is malformed")
    mode, object_type, encoded_blob = fields
    try:
        tree_path = encoded_path.decode("utf-8")
        blob_id = encoded_blob.decode("ascii")
    except UnicodeDecodeError as error:
        raise PolicyViolationError("plan source tree entry is not canonical text") from error
    if tree_path != path or mode not in {b"100644", b"100755"} or object_type != b"blob":
        raise PolicyViolationError("plan source must be a regular non-symlinked blob")
    if not re.fullmatch(r"[0-9a-f]{40,64}", blob_id):
        raise PolicyViolationError("plan source blob ID is invalid")
    return blob_id, _git(runner, repository, "cat-file", "-p", blob_id)


def _decode_plan(content: bytes, path: str) -> str:
    if not 1 <= len(content) <= MAX_PLAN_DOCUMENT_BYTES:
        raise PolicyViolationError("plan document exceeds the bounded-document limit")
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise PolicyViolationError(f"plan document {path!r} is not UTF-8") from error


def _require_plan_path(value: str) -> None:
    if not isinstance(value, str) or not value:
        raise PolicyViolationError("plan path must be a repository-relative string")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or "." in path.parts
        or ".." in path.parts
        or path.as_posix() != value
        or not _PLAN_PATH.fullmatch(path.name)
    ):
        raise PolicyViolationError("plan path must name a normalized Pnnnn Markdown document")


def _require_revision(value: str, label: str) -> None:
    if not isinstance(value, str) or not _REVISION.fullmatch(value):
        raise PolicyViolationError(f"{label} must be a full 40-character lowercase revision")


def _require_repository_root(value: Path) -> Path:
    if not isinstance(value, Path) or not value.is_absolute():
        raise PolicyViolationError("plan repository must be an absolute local path")
    try:
        root = value.resolve(strict=True)
    except OSError as error:
        raise PolicyViolationError("plan repository is unavailable") from error
    if not root.is_dir():
        raise PolicyViolationError("plan repository must be a directory")
    return root


def _git_text(runner: GitRunner, repository: Path, *args: str) -> str:
    raw = _git(runner, repository, *args)
    try:
        return raw.decode("utf-8").strip()
    except UnicodeDecodeError as error:
        raise PolicyViolationError("Git metadata is not UTF-8") from error


def _git(runner: GitRunner, repository: Path, *args: str) -> bytes:
    try:
        return runner(repository, tuple(args))
    except PolicyViolationError:
        raise
    except Exception as error:
        raise PolicyViolationError(f"cannot inspect plan repository: {error}") from error


def _run_git(repository: Path, args: tuple[str, ...]) -> bytes:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repository), *args],
            check=False,
            capture_output=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise PolicyViolationError(f"cannot inspect plan repository: {error}") from error
    if completed.returncode != 0:
        message = completed.stderr.decode("utf-8", errors="replace").strip()
        raise PolicyViolationError(
            f"cannot inspect plan repository: {message or 'Git command failed'}"
        )
    return completed.stdout
