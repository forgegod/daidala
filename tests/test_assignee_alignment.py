from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from daidala.kanban import KanbanCardStatus, KanbanError
from daidala.packs import load_pack
from daidala.service import (
    ServiceError,
    WorkflowService,
    assignee_stage_mismatches,
    require_assignee_stage_alignment,
)
from daidala.skills import content_registry_from_digests, inventory_from_names, required_skills
from daidala.state import SkillDigest, StageProfile, WorkflowStage
from daidala.store import WorkflowStore
from daidala.workflow import new_workflow

NOW = datetime(2026, 8, 16, tzinfo=UTC)
STAGE_PROFILES = {
    "define": "daidala-self-improvement",
    "plan": "daidala-self-improvement",
    "implement": "daidala-self-improvement",
    "verify": "daidala-self-improvement",
    "review": "daidala-self-improvement",
    "deliver": "daidala-self-improvement",
}


def _ledger():
    return new_workflow(
        workflow_id="7af035cc-4a16-42c3-8f89-56d32be050e5",
        board_slug="daidala-forgegod-daidala",
        target_repository="/tmp/daidala-target",
        baseline_commit="a" * 40,
        requested_goal="Change VALUE to 2",
        pack_name="addyosmani",
        pack_source_revision="source@revision",
        skill_digests=(SkillDigest(name="interview-me", digest="digest-1"),),
        stage_profiles=tuple(
            StageProfile(stage=WorkflowStage(stage), profile=profile)
            for stage, profile in STAGE_PROFILES.items()
        ),
        created_at=NOW,
    )


def test_assignee_stage_mismatch_uses_activation_wording() -> None:
    ledger = _ledger()
    statuses = (
        KanbanCardStatus(
            stage=WorkflowStage.DEFINE,
            task_id="t_22e3ef72",
            status="ready",
            assignee="default",
        ),
    )

    mismatches = assignee_stage_mismatches(ledger, statuses)

    assert mismatches == (
        {
            "workflow_id": ledger.workflow_id,
            "stage": "define",
            "assignee": "default",
            "bound_profile": "daidala-self-improvement",
        },
    )
    with pytest.raises(
        ServiceError,
        match=(
            "Cannot record required skill activation: the active card is assigned "
            "to default but the workflow binds define to daidala-self-improvement. "
            "Align the card assignee/stage profile and retry."
        ),
    ):
        require_assignee_stage_alignment(ledger, statuses)


def test_matching_assignee_is_aligned() -> None:
    ledger = _ledger()
    statuses = (
        KanbanCardStatus(
            stage=WorkflowStage.DEFINE,
            task_id="t_22e3ef72",
            status="ready",
            assignee="daidala-self-improvement",
        ),
    )

    require_assignee_stage_alignment(ledger, statuses)
    assert assignee_stage_mismatches(ledger, statuses) == ()


def test_start_preflight_rejects_existing_workflow_assignee_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack = load_pack("addyosmani")
    requirements = required_skills(pack)
    digests = {
        skill.name: skill.content_digest
        for skill in requirements
        if skill.content_digest is not None
    }
    target = tmp_path / "target"
    target.mkdir()
    store = WorkflowStore(tmp_path / "data")
    store.create(_ledger())

    class FakeKanban:
        def validate_assignees(self, board_slug: str, profiles: list[str]) -> None:
            assert board_slug == "daidala-forgegod-daidala"
            assert profiles

        def validate_assignee_gateways(self, profiles: list[str]) -> None:
            assert profiles

        def combined_status(self, ledger) -> tuple[KanbanCardStatus, ...]:
            return (
                KanbanCardStatus(
                    stage=WorkflowStage.DEFINE,
                    task_id="t_22e3ef72",
                    status="ready",
                    assignee="default",
                ),
            )

    monkeypatch.setattr(
        "daidala.service._inspect_repository",
        lambda _target: ("a" * 40, True),
    )
    service = WorkflowService(
        store,
        skill_inventory=inventory_from_names(skill.name for skill in requirements),
        skill_content_registry=content_registry_from_digests(digests),
        kanban=FakeKanban(),  # type: ignore[arg-type]
    )

    with pytest.raises(ServiceError, match="Align the card assignee/stage profile and retry"):
        service.validate_start_preflight(
            board_slug="daidala-forgegod-daidala",
            target_repository=str(target),
            stage_profiles=STAGE_PROFILES,
            workflow_id="7af035cc-4a16-42c3-8f89-56d32be050e5",
        )


def test_evaluate_start_readiness_reports_stopped_gateway(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack = load_pack("addyosmani")
    requirements = required_skills(pack)
    digests = {
        skill.name: skill.content_digest
        for skill in requirements
        if skill.content_digest is not None
    }
    target = tmp_path / "target"
    target.mkdir()

    class FakeKanban:
        def validate_assignees(self, board_slug: str, profiles: list[str]) -> None:
            assert profiles

        def validate_assignee_gateways(self, profiles: list[str]) -> None:
            raise KanbanError("worker gateway is not running for profile(s): architect")

    monkeypatch.setattr(
        "daidala.service._inspect_repository",
        lambda _target: ("a" * 40, True),
    )
    service = WorkflowService(
        WorkflowStore(tmp_path / "data"),
        skill_inventory=inventory_from_names(skill.name for skill in requirements),
        skill_content_registry=content_registry_from_digests(digests),
        kanban=FakeKanban(),  # type: ignore[arg-type]
    )

    result = service.evaluate_start_readiness(
        board_slug="daidala-forgegod-daidala",
        target_repository=str(target),
        stage_profiles=STAGE_PROFILES,
    )

    assert result["ready"] is False
    failed = [row for row in result["checks"] if not row["passed"]]
    assert failed == [
        {
            "id": "worker-gateway-running",
            "passed": False,
            "detail": "worker gateway is not running for profile(s): architect",
        }
    ]
