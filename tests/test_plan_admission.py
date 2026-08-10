from __future__ import annotations

import subprocess
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from daidala.errors import PolicyViolationError
from daidala.plan_admission import (
    admit_plan_source,
    parse_plan_document,
    parse_plan_inventory,
    select_pending_phase,
)
from daidala.state import PlanSourcePacket

DONE_DIGEST = "a" * 64


def plan_document(
    *,
    plan_id: str,
    slot: str,
    status: str = "pending",
    dependencies: str = "none",
    phases: tuple[tuple[str, str], ...] = (("Admit the committed source", "pending"),),
) -> str:
    rows = "\n".join(
        f"| {number} | {title} | {phase_status} | `pytest -q tests/test_{number}.py` exits 0 |"
        for number, (title, phase_status) in enumerate(phases)
    )
    sections = "\n".join(
        "\n".join(
            (
                f"## Phase {number} — {title}",
                "",
                "Goal: keep the admission fixture deterministic.",
                "",
                f"Verification gate: `pytest -q tests/test_{number}.py` exits 0",
            )
        )
        for number, (title, _phase_status) in enumerate(phases)
    )
    return "\n".join(
        (
            f"# {plan_id}",
            "",
            f"**Plan ID:** {plan_id}",
            "",
            f"**Execution slot:** {slot}",
            "",
            "**Created:** 2026-08-10",
            "",
            f"**Depends on:** {dependencies}",
            "",
            f"**Status:** {status}",
            "",
            "## Phase table",
            "",
            "| # | Phase | Status | Verification gate |",
            "|---|---|---|---|",
            rows,
            "",
            sections,
            "",
        )
    )


def git(repository: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def commit(repository: Path, message: str) -> str:
    git(repository, "add", ".")
    subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "-c",
            "user.name=Daidala Tests",
            "-c",
            "user.email=daidala@example.invalid",
            "commit",
            "-qm",
            message,
        ],
        check=True,
    )
    return git(repository, "rev-parse", "HEAD")


def repository_with_plans(tmp_path: Path) -> tuple[Path, str]:
    repository = tmp_path / "target"
    plans = repository / "docs" / "plans"
    plans.mkdir(parents=True)
    (plans / "P0100-complete.md").write_text(
        plan_document(
            plan_id="completed-policy",
            slot="P0100",
            status="complete",
            phases=(("Record completed policy", f"done (daidala:workflow-1:{DONE_DIGEST})"),),
        ),
        encoding="utf-8",
    )
    (plans / "P0200-active.md").write_text(
        plan_document(
            plan_id="active-policy",
            slot="P0200",
            dependencies="completed-policy",
        ),
        encoding="utf-8",
    )
    (plans / "P0099-legacy.md").write_text(
        "\n".join(
            (
                "# Legacy plan",
                "",
                "**Plan ID:** legacy-plan",
                "",
                "**Execution slot:** P0099",
                "",
                "**Status:** complete — historic format",
                "",
                "No new-shape phase metadata exists here.",
                "",
            )
        ),
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    return repository, commit(repository, "plan fixture")


def test_admits_one_exact_committed_pending_phase(tmp_path: Path) -> None:
    repository, revision = repository_with_plans(tmp_path)

    packet = admit_plan_source(
        repository=repository,
        plan_path="docs/plans/P0200-active.md",
        source_revision=revision,
        baseline_commit=revision,
        phase_number=0,
    )

    assert packet.plan_id == "active-policy"
    assert packet.execution_slot == "P0200"
    assert packet.reference.source_revision == revision
    assert packet.reference.baseline_commit == revision
    assert packet.reference.plan_path == "docs/plans/P0200-active.md"
    assert len(packet.reference.plan_blob_id) == 40
    assert len(packet.reference.plan_digest) == len(packet.digest) == 64
    assert PlanSourcePacket.from_dict(packet.to_dict()) == packet
    assert packet.canonical_bytes().startswith(b'{"direct_dependencies":[')
    with pytest.raises(FrozenInstanceError):
        packet.phase_title = "changed"  # type: ignore[misc]
    assert git(repository, "status", "--porcelain") == ""


def test_admission_uses_the_injected_git_boundary(tmp_path: Path) -> None:
    repository, revision = repository_with_plans(tmp_path)
    calls: list[tuple[str, ...]] = []

    def runner(root: Path, args: tuple[str, ...]) -> bytes:
        calls.append(args)
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
        ).stdout

    packet = admit_plan_source(
        repository=repository,
        plan_path="docs/plans/P0200-active.md",
        source_revision=revision,
        baseline_commit=revision,
        phase_number=0,
        git_runner=runner,
    )

    assert packet.reference.plan_blob_id
    assert ("rev-parse", "--show-toplevel") in calls
    assert ("status", "--porcelain=v1", "--untracked-files=normal") in calls
    assert any(call[:2] == ("cat-file", "-p") for call in calls)


def test_packet_rejects_unknown_fields_and_stale_reference_identity(tmp_path: Path) -> None:
    repository, revision = repository_with_plans(tmp_path)
    packet = admit_plan_source(
        repository=repository,
        plan_path="docs/plans/P0200-active.md",
        source_revision=revision,
        baseline_commit=revision,
        phase_number=0,
    )

    unknown = packet.to_dict() | {"unexpected": "field"}
    with pytest.raises(PolicyViolationError, match="unknown"):
        PlanSourcePacket.from_dict(unknown)

    stale = packet.to_dict()
    stale["reference"]["baseline_commit"] = "b" * 40
    with pytest.raises(PolicyViolationError, match="baseline"):
        PlanSourcePacket.from_dict(stale)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (
            plan_document(plan_id="policy", slot="P0200").replace(
                "**Plan ID:** policy",
                "**Plan ID:** policy\n**Plan ID:** duplicate-policy",
            ),
            "duplicate",
        ),
        (
            plan_document(plan_id="policy", slot="P0200").replace(
                "## Phase 0 — Admit the committed source",
                "## Phase 0 — Different heading",
            ),
            "does not match",
        ),
        (
            plan_document(
                plan_id="policy",
                slot="P0200",
                phases=(
                    ("Completed", "done ()"),
                    ("Pending", "pending"),
                ),
            ),
            "status",
        ),
        (
            plan_document(plan_id="policy", slot="P0200").replace(
                "`pytest -q tests/test_0.py` exits 0",
                "a prose test gate",
                1,
            ),
            "executable command",
        ),
        (
            plan_document(plan_id="policy", slot="P0200", status="complete"),
            "complete plan documents",
        ),
    ],
)
def test_plan_parser_rejects_ambiguous_or_malformed_markdown(
    content: str, message: str
) -> None:
    with pytest.raises(PolicyViolationError, match=message):
        parse_plan_document("docs/plans/P0200-policy.md", content)


def test_inventory_rejects_duplicate_unknown_and_cyclic_dependencies() -> None:
    first = plan_document(plan_id="first", slot="P0100", dependencies="second")
    second = plan_document(plan_id="second", slot="P0200", dependencies="first")
    with pytest.raises(PolicyViolationError, match="cycle"):
        parse_plan_inventory(
            {
                "docs/plans/P0100-first.md": first,
                "docs/plans/P0200-second.md": second,
            }
        )

    with pytest.raises(PolicyViolationError, match="unknown"):
        parse_plan_inventory(
            {
                "docs/plans/P0100-first.md": plan_document(
                    plan_id="first", slot="P0100", dependencies="missing"
                )
            }
        )

    with pytest.raises(PolicyViolationError, match="duplicate"):
        parse_plan_inventory(
            {
                "docs/plans/P0100-first.md": plan_document(plan_id="same", slot="P0100"),
                "docs/plans/P0200-second.md": plan_document(plan_id="same", slot="P0200"),
            }
        )


def test_pending_selection_requires_complete_predecessors_and_pending_successors() -> None:
    plan = parse_plan_document(
        "docs/plans/P0200-policy.md",
        plan_document(
            plan_id="policy",
            slot="P0200",
            phases=(
                ("Completed", f"done (daidala:workflow-1:{DONE_DIGEST})"),
                ("Pending", "pending"),
                ("Later", "pending"),
            ),
        ),
    )

    assert select_pending_phase(plan, 1).title == "Pending"
    with pytest.raises(PolicyViolationError, match="must be pending"):
        select_pending_phase(plan, 0)
    with pytest.raises(PolicyViolationError, match="does not exist"):
        select_pending_phase(plan, 3)


def test_admission_rejects_dirty_drifted_and_traversal_inputs(tmp_path: Path) -> None:
    repository, revision = repository_with_plans(tmp_path)
    selected = repository / "docs" / "plans" / "P0200-active.md"
    selected.write_text("working-tree rewrite\n", encoding="utf-8")

    with pytest.raises(PolicyViolationError, match="clean"):
        admit_plan_source(
            repository=repository,
            plan_path="docs/plans/P0200-active.md",
            source_revision=revision,
            baseline_commit=revision,
            phase_number=0,
        )
    with pytest.raises(PolicyViolationError, match="normalized"):
        admit_plan_source(
            repository=repository,
            plan_path="../P0200-active.md",
            source_revision=revision,
            baseline_commit=revision,
            phase_number=0,
        )
    with pytest.raises(PolicyViolationError, match="full 40-character"):
        admit_plan_source(
            repository=repository,
            plan_path="docs/plans/P0200-active.md",
            source_revision=revision[:12],
            baseline_commit=revision[:12],
            phase_number=0,
        )


def test_admission_rejects_symlink_and_non_utf8_plan_objects(tmp_path: Path) -> None:
    repository, _revision = repository_with_plans(tmp_path)
    plans = repository / "docs" / "plans"
    (plans / "P0200-active.md").unlink()
    (plans / "P0200-active.md").symlink_to("P0100-complete.md")
    revision = commit(repository, "symlink plan")

    with pytest.raises(PolicyViolationError, match="regular non-symlinked"):
        admit_plan_source(
            repository=repository,
            plan_path="docs/plans/P0200-active.md",
            source_revision=revision,
            baseline_commit=revision,
            phase_number=0,
        )

    (plans / "P0200-active.md").unlink()
    (plans / "P0200-active.md").write_bytes(b"\xff\xfe")
    revision = commit(repository, "binary plan")
    with pytest.raises(PolicyViolationError, match="not UTF-8"):
        admit_plan_source(
            repository=repository,
            plan_path="docs/plans/P0200-active.md",
            source_revision=revision,
            baseline_commit=revision,
            phase_number=0,
        )
