from __future__ import annotations

from pathlib import Path

import pytest

import wingstaff
from wingstaff.kanban import KanbanGraphAdapter
from wingstaff.packs import load_pack
from wingstaff.state import WorkflowStage


def worker_contract() -> str:
    return (
        Path(wingstaff.__file__).parent / "skills" / "orchestrate" / "SKILL.md"
    ).read_text(encoding="utf-8")


@pytest.mark.parametrize("pack_name", ("addyosmani", "aidlc"))
@pytest.mark.parametrize(
    "stage",
    tuple(stage for stage in WorkflowStage if stage is not WorkflowStage.APPROVAL),
)
def test_every_executable_card_pins_worker_contract_and_exact_pack_skills(
    pack_name: str,
    stage: WorkflowStage,
) -> None:
    pack = load_pack(pack_name)
    selected = next(row for row in pack.stages if row.id == stage.value)

    assert KanbanGraphAdapter._stage_skills(pack, stage) == [
        "wingstaff:orchestrate",
        *(
            f"wingstaff:{skill.name}" if skill.bundled else skill.name
            for skill in selected.skills
        ),
    ]


def test_approval_card_has_no_worker_skills() -> None:
    assert (
        KanbanGraphAdapter._stage_skills(load_pack("addyosmani"), WorkflowStage.APPROVAL)
        == []
    )


@pytest.mark.parametrize(
    ("stage", "operation"),
    (
        ("define", 'wingstaff_submit_artifact(stage: "define")'),
        ("plan", 'wingstaff_submit_artifact(stage: "plan")'),
        ("implement", "wingstaff_capture_implementation"),
        ("verify", "wingstaff_record_verification"),
        ("review", 'wingstaff_submit_artifact(stage: "review")'),
        ("deliver", "wingstaff_deliver"),
    ),
)
def test_worker_contract_maps_every_stage_to_policy_evidence_operation(
    stage: str,
    operation: str,
) -> None:
    instructions = worker_contract()

    assert f"| `{stage}` |" in instructions
    assert operation in instructions


def test_worker_contract_requires_kanban_handoff_and_recovery_protocol() -> None:
    instructions = worker_contract()

    required = (
        "Call `kanban_show` before any file, terminal, or Wingstaff tool",
        "every other skill pinned",
        "wingstaff_record_skill_activation",
        "wingstaff.handoff/v1",
        "`skill_activation_digest`, and `active_skills`",
        "`workspace_path` and `baseline_commit`",
        "Before `kanban_block`, call `kanban_comment`",
        "`dependency` for an unfinished prerequisite",
        "`capability` for missing tools",
        "`needs_input` with a `verification-failed:` or `review-required:` reason",
        "`transient` only for genuinely flaky host failures",
        "approval from a generic unblock",
        "exactly one `kanban_complete` or `kanban_block` call",
        "policy revision, constraint revision and digest",
        "current Wingstaff status before applying methodology",
        "never continue from a superseded card",
        "Apply every global constraint and only the current stage's phase constraints",
        "`constraints_revision`, `constraints_digest`",
    )
    for statement in required:
        assert statement in instructions


def test_worker_contract_requires_pre_work_activation_and_blocked_protocol() -> None:
    instructions = worker_contract()

    required = (
        "before applying stage methodology",
        "producing evidence. Loaded candidates are not automatically active",
        "`required` means the pack requires the skill",
        "`conditional` means the worker chooses",
        "`applicable` skills are active now",
        "`deferred` skills are inactive",
        "`not_applicable` means current task evidence",
        "`blocked` means a required or relevant skill cannot be applied",
        "unique contiguous ranks",
        "at 1 in attention order",
        "non-empty matched criteria, task evidence, and rationale",
        "comment with its digest and every blocked skill",
        '`kanban_block(kind: "capability")`',
        "Do not fabricate a successful handoff",
        "wingstaff:orchestrate` as always required",
        "discover replacement skills",
    )
    for statement in required:
        assert statement in instructions


def test_worker_contract_forbids_post_capture_mutation_and_target_delivery() -> None:
    instructions = worker_contract()

    assert "Implementation scope is immutable" in instructions
    assert "must not modify it" in instructions
    assert "new approved graph revision" in instructions
    assert "`committed: false` and `pushed: false`" in instructions
