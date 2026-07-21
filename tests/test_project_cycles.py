from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from daidala.adapters import (
    ClaimIdentity,
    IntakeCancellationReceipt,
    IntakeCategory,
    IntakeRecord,
    NotificationReceipt,
)
from daidala.cycles import CycleMode
from daidala.errors import PolicyViolationError
from daidala.packs import load_pack
from daidala.prerequisites import CheckStatus, PrerequisiteReport, active_admission_paths
from daidala.project_cycles import ProjectCycleOperator, _diagnosis_allows_replay
from daidala.reconciliation import ReconciliationOutcome
from daidala.state import SkillDigest, StageProfile, WorkflowLedger, WorkflowStage
from daidala.store import WorkflowStore
from daidala.workflow import new_workflow

ROOT = Path(__file__).parents[1]
BASELINE = "b" * 40


def _issue_body() -> str:
    return (
        """\
### Category

regression

### Originating experiment, test case, or source identity

UC-01 / TC-F04-01

### Expected behavior

The temporary calculator returns 2.

### Observed behavior

The temporary calculator returns 1.

### Redacted evidence reference and SHA-256 digest

uc-01 sha256:"""
        + "a" * 64
        + """

### Acceptance criteria

- The failing test passes.

### Dependencies and risk

Temporary fixture only.

### Priority

1

### Publication state

local
"""
    )


class Runtime:
    def __init__(self, checkout: Path) -> None:
        self.checkout = checkout
        self.calls: list[tuple[tuple[str, ...], dict[str, str]]] = []

    def __call__(
        self, command: tuple[str, ...], environment: Mapping[str, str]
    ) -> tuple[int, str]:
        env = dict(environment)
        self.calls.append((command, env))
        if command[:4] == ("git", "-C", str(self.checkout), "rev-parse"):
            return 0, BASELINE
        if command[:4] == ("git", "-C", str(self.checkout), "status"):
            return 0, ""
        if command[:4] == ("git", "-C", str(self.checkout), "remote"):
            return 0, "git@github.com:forgegod/daidala.git"
        if command[:3] == ("gh", "issue", "view"):
            assert env["GH_TOKEN"] == "read-token"
            return 0, json.dumps(
                {
                    "number": 42,
                    "url": "https://github.com/forgegod/daidala/issues/42",
                    "title": "[Daidala SI] Fix temporary calculator",
                    "body": _issue_body(),
                    "state": "OPEN",
                    "labels": [
                        {"name": "daidala-si"},
                        {"name": "daidala-si:ready"},
                        {"name": "daidala-si:regression"},
                        {"name": "daidala-si:priority-1"},
                    ],
                }
            )
        if command[:3] == ("gh", "api", "--paginate"):
            assert env["GH_TOKEN"] == "read-token"
            assert command[-2:] == ("--jq", ".[]")
            if command[3].endswith("/events?per_page=100"):
                return 0, json.dumps(
                    {
                        "event": "labeled",
                        "label": {"name": "daidala-si:ready"},
                        "actor": {"login": "forgegod"},
                    }
                )
            if command[3].endswith("/comments?per_page=100"):
                return 0, ""
        raise AssertionError(f"unexpected command: {command}")


def _stage_profiles() -> dict[str, str]:
    return {
        stage.value: "daidala-self-improvement"
        for stage in WorkflowStage
        if stage is not WorkflowStage.APPROVAL
    }


def _operator(tmp_path: Path) -> tuple[ProjectCycleOperator, Path, Path, Runtime, list[Path]]:
    checkout = tmp_path / "checkout"
    policy = checkout / ".daidala"
    policy.mkdir(parents=True)
    (policy / "project.yaml").write_text(
        (ROOT / ".daidala/project.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (policy / "constraints.yaml").write_text(
        (ROOT / ".daidala/constraints.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    profile_root = tmp_path / "profile"
    project_root = profile_root / "projects" / "forgegod-daidala"
    project_root.mkdir(parents=True)
    registration = project_root / "registration.yaml"
    registration.write_text(
        f"""\
schema: daidala.controller-registration/v2
project_id: forgegod-daidala
checkout: {checkout}
controller_profile: daidala-self-improvement
board: daidala-forgegod-daidala
repository_identity:
  canonical: forgegod/daidala
  verified_remote: git@github.com:forgegod/daidala.git
credentials:
  intake: github-read
  findings: github-write
approval:
  maintainers: [forgegod]
notifications:
  adapter: hermes-gateway
  target: attended-daidala
  destination: telegram:-1001234567890:17585
evaluator:
  backend: restricted-container
  network: denied-by-default
limits:
  active_cycles: 1
  goal_turns: 12
  delegated_workers: 3
  research_query_batches: 3
  extracted_sources: 3
  wall_clock_seconds: 3600
""",
        encoding="utf-8",
    )
    (project_root / "credential-bindings.yaml").write_text(
        """\
schema: daidala.credential-bindings/v1
project_id: forgegod-daidala
bindings:
  - alias: github-read
    resolver: environment
    environment_variable: GH_READ_TOKEN
  - alias: github-write
    resolver: environment
    environment_variable: GH_WRITE_TOKEN
""",
        encoding="utf-8",
    )
    runtime = Runtime(checkout)
    workflow_roots: list[Path] = []

    def build_workflow(
        root: Path, runner: object, environ: object
    ) -> object:
        workflow_roots.append(root)
        raise AssertionError("workflow factory must not run before exact identity matches")

    operator = ProjectCycleOperator(
        runner=runtime,
        environ={
            "PATH": "/usr/bin",
            "HOME": str(tmp_path / "home"),
            "GH_READ_TOKEN": "read-token",
            "GH_WRITE_TOKEN": "write-token",
        },
        diagnose=lambda **kwargs: SimpleNamespace(status=CheckStatus.PASS),
        workflow_factory=build_workflow,  # type: ignore[arg-type]
    )
    return operator, policy / "project.yaml", registration, runtime, workflow_roots


def test_project_cycle_preview_composes_live_inputs_without_runtime_mutation(
    tmp_path: Path,
) -> None:
    operator, manifest, registration, runtime, workflow_roots = _operator(tmp_path)

    preview = operator.preview(
        project_manifest=manifest,
        registration=registration,
        issue_id="42",
        stage_profiles=_stage_profiles(),
        pack_name="addyosmani",
    )

    profile_root = registration.parents[2]
    assert preview.cycle.cycle_id.startswith("cycle-")
    assert preview.intake_digest
    assert preview.checkout == str(manifest.parents[1])
    assert workflow_roots == []
    assert not (profile_root / "daidala").exists()
    assert not (registration.parent / "cycles").exists()
    assert not any(call[0][:3] == ("gh", "issue", "comment") for call in runtime.calls)


def test_project_cycle_preview_binds_exact_comparison_mode_and_candidate(
    tmp_path: Path,
) -> None:
    operator, manifest, registration, runtime, workflow_roots = _operator(tmp_path)
    candidate = "pack:aidlc:e49341dbeb8af82758dd85e96ed7fe9bcf38a447"

    preview = operator.preview(
        project_manifest=manifest,
        registration=registration,
        issue_id="42",
        stage_profiles=_stage_profiles(),
        mode=CycleMode.EVALUATE_PACK,
        pack_name="addyosmani",
        candidate_identity=candidate,
    )

    assert preview.cycle.mode is CycleMode.EVALUATE_PACK
    assert preview.cycle.candidate_identity == candidate
    assert workflow_roots == []
    assert not any(
        call[0][:3] in {("gh", "issue", "comment"), ("gh", "issue", "edit")}
        for call in runtime.calls
    )


def test_project_cycle_comparison_requires_candidate_before_mutation(tmp_path: Path) -> None:
    operator, manifest, registration, runtime, workflow_roots = _operator(tmp_path)

    with pytest.raises(PolicyViolationError, match="require a candidate"):
        operator.preview(
            project_manifest=manifest,
            registration=registration,
            issue_id="42",
            stage_profiles=_stage_profiles(),
            mode=CycleMode.EVALUATE_PACK,
            pack_name="addyosmani",
        )

    assert workflow_roots == []
    assert not any(
        call[0][:3] in {("gh", "issue", "comment"), ("gh", "issue", "edit")}
        for call in runtime.calls
    )


def test_project_cycle_apply_rejects_stale_preview_before_workflow_or_claim(
    tmp_path: Path,
) -> None:
    operator, manifest, registration, runtime, workflow_roots = _operator(tmp_path)
    preview = operator.preview(
        project_manifest=manifest,
        registration=registration,
        issue_id="42",
        stage_profiles=_stage_profiles(),
    )

    with pytest.raises(PolicyViolationError, match="expected cycle ID"):
        operator.admit(
            project_manifest=manifest,
            registration=registration,
            issue_id="42",
            stage_profiles=_stage_profiles(),
            expected_cycle_id="cycle-" + "0" * 64,
            expected_intake_digest=preview.intake_digest,
        )

    assert workflow_roots == []
    assert not any(
        call[0][:3] in {("gh", "issue", "comment"), ("gh", "issue", "edit")}
        for call in runtime.calls
    )


def test_prerequisites_allow_only_matching_admission_replay() -> None:
    active_admission = SimpleNamespace(
        check_id="SI-ACTIVE-CYCLE",
        status=CheckStatus.BLOCKED,
        blocker="Daidala cycle admission ownership exists",
    )
    report = cast(
        PrerequisiteReport,
        SimpleNamespace(status=CheckStatus.BLOCKED, checks=(active_admission,)),
    )

    assert _diagnosis_allows_replay(report, has_matching_replay=True)
    assert not _diagnosis_allows_replay(report, has_matching_replay=False)

    active_board = SimpleNamespace(
        check_id="SI-ACTIVE-CYCLE",
        status=CheckStatus.BLOCKED,
        blocker="registered board has active task ownership",
    )
    board_report = cast(
        PrerequisiteReport,
        SimpleNamespace(status=CheckStatus.BLOCKED, checks=(active_board,)),
    )
    assert not _diagnosis_allows_replay(board_report, has_matching_replay=True)


def _inventory_item(item_id: str) -> IntakeRecord:
    return IntakeRecord(
        adapter="github-issues",
        item_id=item_id,
        source_url=f"https://github.com/forgegod/daidala/issues/{item_id}",
        category=IntakeCategory.REGRESSION,
        priority=1,
        goal="Fix deterministic reconciliation ordering.",
        acceptance_criteria=("The lowest stable issue ID is selected.",),
        evidence_digests=("a" * 64,),
        dependencies=(),
        risk="Fixture only.",
        admission_actor="forgegod",
        ready=True,
    )


class InventoryAdapter:
    ready: tuple[IntakeRecord, ...] = ()
    claimed: tuple[IntakeRecord, ...] = ()
    canceled: tuple[IntakeRecord, ...] = ()
    fail = False
    release_calls = 0
    cancel_calls = 0

    def __init__(self, **kwargs: object) -> None:
        pass

    def fetch_ready(self, *, limit: int) -> tuple[IntakeRecord, ...]:
        if self.fail:
            raise PolicyViolationError("inventory unavailable")
        return self.ready[:limit]

    def fetch_claimed(self, *, limit: int) -> tuple[IntakeRecord, ...]:
        if self.fail:
            raise PolicyViolationError("inventory unavailable")
        return self.claimed[:limit]

    def fetch(self, item_id: str) -> IntakeRecord:
        return next(
            row
            for row in self.ready + self.claimed + self.canceled
            if row.item_id == item_id
        )

    def claim(self, item_id: str, claim: ClaimIdentity) -> IntakeRecord:
        current = self.fetch(item_id)
        if current.claim is not None and current.claim != claim:
            raise PolicyViolationError("claimed by another owner")
        claimed = replace(current, claim=claim)
        type(self).ready = tuple(row for row in self.ready if row.item_id != item_id)
        type(self).claimed = tuple(
            claimed if row.item_id == item_id else row for row in self.claimed
        ) or (claimed,)
        return claimed

    def release_claim(self, item_id: str, claim: ClaimIdentity) -> IntakeRecord:
        current = self.fetch(item_id)
        if current.claim != claim:
            raise PolicyViolationError("claim release owner does not match")
        type(self).release_calls += 1
        released = replace(current, claim=None)
        type(self).claimed = tuple(row for row in self.claimed if row.item_id != item_id)
        type(self).ready = (released,)
        return released

    def validate_cancellation(self, item_id: str, cycle_id: str) -> None:
        current = self.fetch(item_id)
        if current.claim is None or current.claim.claimant != cycle_id:
            raise PolicyViolationError("cancellation claim owner does not match")

    def cancel(
        self, item_id: str, cycle_id: str, reason_digest: str
    ) -> IntakeCancellationReceipt:
        self.validate_cancellation(item_id, cycle_id)
        type(self).cancel_calls += 1
        current = self.fetch(item_id)
        type(self).claimed = tuple(row for row in self.claimed if row.item_id != item_id)
        type(self).canceled = (current,)
        return IntakeCancellationReceipt(
            adapter="github-issues",
            item_id=item_id,
            cycle_id=cycle_id,
            reason_digest=reason_digest,
            source_url=f"https://github.com/forgegod/daidala/issues/{item_id}",
            state="closed",
            state_reason="not_planned",
            claim_released=True,
            canceled_at=datetime.now(UTC),
        )


class ReconciliationNotifications:
    calls: list[dict[str, object]] = []
    fail = False

    def __init__(self, **kwargs: object) -> None:
        pass

    def deliver(self, payload: dict[str, object]) -> NotificationReceipt:
        type(self).calls.append(payload)
        if self.fail:
            raise PolicyViolationError("notification delivery failed")
        return NotificationReceipt(
            event_id=str(payload["event_id"]),
            adapter="hermes-gateway",
            target_alias="attended-daidala",
            receipt_id=f"telegram:{len(self.calls)}",
            delivered_at=datetime.now(UTC),
        )


class ReconciliationWorkflow:
    def __init__(self) -> None:
        self.ledgers: dict[str, object] = {}
        self.cancel_calls = 0

    def start(self, **kwargs: object) -> object:
        workflow_id = str(kwargs["workflow_id"])
        if workflow_id not in self.ledgers:
            pack = load_pack(str(kwargs["pack_name"]))
            profiles = cast(dict[str, str], kwargs["stage_profiles"])
            self.ledgers[workflow_id] = new_workflow(
                workflow_id=workflow_id,
                board_slug=str(kwargs["board_slug"]),
                target_repository=str(kwargs["target_repository"]),
                baseline_commit=str(kwargs["expected_baseline_commit"]),
                requested_goal=str(kwargs["goal"]),
                pack_name=pack.name,
                pack_source_revision=pack.source_revision,
                skill_digests=(SkillDigest("fixture-skill", "c" * 64),),
                stage_profiles=tuple(
                    StageProfile(stage, profiles[stage.value])
                    for stage in WorkflowStage
                    if stage is not WorkflowStage.APPROVAL
                ),
                created_at=datetime.now(UTC),
            )
        return self.ledgers[workflow_id]

    def cancel(self, workflow_id: str, reason: str) -> object:
        assert reason
        self.cancel_calls += 1
        return self.ledgers[workflow_id]


def test_reconciliation_preview_selects_lowest_stable_issue_without_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    operator, manifest, registration, _runtime, workflow_roots = _operator(tmp_path)
    InventoryAdapter.ready = (_inventory_item("43"), _inventory_item("42"))
    InventoryAdapter.claimed = ()
    InventoryAdapter.fail = False
    monkeypatch.setattr(
        "daidala.project_cycles.GitHubIssueIntakeAdapter", InventoryAdapter
    )

    preview = operator.preview_reconciliation(
        project_manifest=manifest,
        registration=registration,
        stage_profiles=_stage_profiles(),
    )

    assert preview.outcome is ReconciliationOutcome.ADMISSION_PREVIEW
    assert preview.intake_item_id == "42"
    assert preview.candidate_count == 2
    assert workflow_roots == []
    assert not (registration.parents[2] / "daidala").exists()


def test_reconciliation_idle_apply_is_replay_safe_and_content_addressed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    operator, manifest, registration, _runtime, workflow_roots = _operator(tmp_path)
    InventoryAdapter.ready = ()
    InventoryAdapter.claimed = ()
    InventoryAdapter.fail = False
    monkeypatch.setattr(
        "daidala.project_cycles.GitHubIssueIntakeAdapter", InventoryAdapter
    )
    preview = operator.preview_reconciliation(
        project_manifest=manifest,
        registration=registration,
        stage_profiles=_stage_profiles(),
    )

    first = operator.reconcile(
        project_manifest=manifest,
        registration=registration,
        stage_profiles=_stage_profiles(),
        expected_preview_digest=preview.digest,
    )
    second = operator.reconcile(
        project_manifest=manifest,
        registration=registration,
        stage_profiles=_stage_profiles(),
        expected_preview_digest=preview.digest,
    )

    assert first == second
    assert first.outcome is ReconciliationOutcome.IDLE
    assert workflow_roots == []
    ticks = list((registration.parent / "reconciliation/ticks").glob("*.json"))
    assert len(ticks) == 1


def test_reconciliation_unexpired_claim_blocks_and_inventory_outage_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    operator, manifest, registration, _runtime, _workflow_roots = _operator(tmp_path)
    claim = ClaimIdentity(
        "cycle-" + "c" * 64,
        datetime.now(UTC),
        datetime.now(UTC) + timedelta(hours=1),
    )
    InventoryAdapter.ready = ()
    InventoryAdapter.claimed = (replace(_inventory_item("42"), claim=claim),)
    InventoryAdapter.fail = False
    monkeypatch.setattr(
        "daidala.project_cycles.GitHubIssueIntakeAdapter", InventoryAdapter
    )

    preview = operator.preview_reconciliation(
        project_manifest=manifest,
        registration=registration,
        stage_profiles=_stage_profiles(),
    )
    assert preview.outcome is ReconciliationOutcome.BLOCKED
    assert "unexpired claim" in str(preview.blocker)

    InventoryAdapter.fail = True
    with pytest.raises(PolicyViolationError, match="inventory unavailable"):
        operator.preview_reconciliation(
            project_manifest=manifest,
            registration=registration,
            stage_profiles=_stage_profiles(),
        )


def test_reconciliation_admission_and_duplicate_tick_converge_on_one_workflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    operator, manifest, registration, _runtime, _roots = _operator(tmp_path)
    workflow = ReconciliationWorkflow()
    operator.workflow_factory = lambda *_args: workflow  # type: ignore[assignment]
    InventoryAdapter.ready = (_inventory_item("42"),)
    InventoryAdapter.claimed = ()
    InventoryAdapter.fail = False
    ReconciliationNotifications.calls = []
    ReconciliationNotifications.fail = False
    monkeypatch.setattr(
        "daidala.project_cycles.GitHubIssueIntakeAdapter", InventoryAdapter
    )
    monkeypatch.setattr(
        "daidala.project_cycles.HermesGatewayNotificationAdapter",
        ReconciliationNotifications,
    )

    preview = operator.preview_reconciliation(
        project_manifest=manifest,
        registration=registration,
        stage_profiles=_stage_profiles(),
    )
    admitted = operator.reconcile(
        project_manifest=manifest,
        registration=registration,
        stage_profiles=_stage_profiles(),
        expected_preview_digest=preview.digest,
    )
    active = operator.preview_reconciliation(
        project_manifest=manifest,
        registration=registration,
        stage_profiles=_stage_profiles(),
    )
    replayed = operator.reconcile(
        project_manifest=manifest,
        registration=registration,
        stage_profiles=_stage_profiles(),
        expected_preview_digest=active.digest,
    )

    assert admitted.outcome is ReconciliationOutcome.ADMITTED
    assert active.outcome is ReconciliationOutcome.ACTIVE_CYCLE
    assert replayed.outcome is ReconciliationOutcome.REPLAYED
    assert admitted.preview.cycle_id == active.cycle_id == replayed.preview.cycle_id
    assert list(workflow.ledgers) == [active.cycle_id]
    assert len(ReconciliationNotifications.calls) == 1


def test_project_cycle_cancellation_is_digest_bound_and_releases_ownership(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    operator, manifest, registration, _runtime, _roots = _operator(tmp_path)
    workflow = ReconciliationWorkflow()
    operator.workflow_factory = lambda *_args: workflow  # type: ignore[assignment]
    InventoryAdapter.ready = (_inventory_item("42"),)
    InventoryAdapter.claimed = ()
    InventoryAdapter.canceled = ()
    InventoryAdapter.cancel_calls = 0
    InventoryAdapter.fail = False
    ReconciliationNotifications.calls = []
    ReconciliationNotifications.fail = False
    monkeypatch.setattr(
        "daidala.project_cycles.GitHubIssueIntakeAdapter", InventoryAdapter
    )
    monkeypatch.setattr(
        "daidala.project_cycles.HermesGatewayNotificationAdapter",
        ReconciliationNotifications,
    )
    admission_preview = operator.preview_reconciliation(
        project_manifest=manifest,
        registration=registration,
        stage_profiles=_stage_profiles(),
    )
    admitted = operator.reconcile(
        project_manifest=manifest,
        registration=registration,
        stage_profiles=_stage_profiles(),
        expected_preview_digest=admission_preview.digest,
    )
    cycle_id = str(admitted.preview.cycle_id)
    profile_root = registration.parents[2]
    store = WorkflowStore(profile_root / "daidala")
    store.create(
        cast(WorkflowLedger, workflow.ledgers[cycle_id])
    )
    reason = "Controlled reconciliation replay completed without implementation."

    observed = store.get_with_token(cycle_id)
    store.update(
        replace(
            observed.ledger,
            requested_goal="Drifted goal.",
            updated_at=datetime.now(UTC),
        ),
        expected_updated_at=observed.updated_at,
    )
    with pytest.raises(PolicyViolationError, match="goal does not match"):
        operator.preview_cancellation(
            project_manifest=manifest,
            registration=registration,
            cycle_id=cycle_id,
            reason=reason,
        )
    drifted = store.get_with_token(cycle_id)
    store.update(
        replace(observed.ledger, updated_at=datetime.now(UTC)),
        expected_updated_at=drifted.updated_at,
    )

    preview = operator.preview_cancellation(
        project_manifest=manifest,
        registration=registration,
        cycle_id=cycle_id,
        reason=reason,
    )

    assert preview.cycle_id == cycle_id
    assert preview.reason == reason
    assert InventoryAdapter.cancel_calls == workflow.cancel_calls == 0
    with pytest.raises(PolicyViolationError, match="preview digest"):
        operator.cancel_cycle(
            project_manifest=manifest,
            registration=registration,
            cycle_id=cycle_id,
            reason=reason,
            expected_preview_digest="f" * 64,
        )
    first = operator.cancel_cycle(
        project_manifest=manifest,
        registration=registration,
        cycle_id=cycle_id,
        reason=reason,
        expected_preview_digest=preview.digest,
    )
    second = operator.cancel_cycle(
        project_manifest=manifest,
        registration=registration,
        cycle_id=cycle_id,
        reason=reason,
        expected_preview_digest=preview.digest,
    )

    assert first == second
    assert first.cancellation.remote_receipt.state_reason == "not_planned"
    assert InventoryAdapter.cancel_calls == workflow.cancel_calls == 1
    assert [row["event"] for row in ReconciliationNotifications.calls] == [
        "cycle-admitted",
        "cycle-cancelled",
    ]
    assert active_admission_paths(registration.parent / "cycles") == ()
    cycle_root = registration.parent / "cycles" / cycle_id
    assert (cycle_root / "cancellation-remote.json").is_file()
    assert (cycle_root / "cancellation-workflow.json").is_file()
    assert (cycle_root / "cancellation-notification.json").is_file()
    assert (cycle_root / "cancellation.json").is_file()


def test_reconciliation_notification_failure_is_not_recorded_as_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    operator, manifest, registration, _runtime, _roots = _operator(tmp_path)
    operator.workflow_factory = lambda *_args: ReconciliationWorkflow()  # type: ignore[assignment]
    InventoryAdapter.ready = (_inventory_item("42"),)
    InventoryAdapter.claimed = ()
    InventoryAdapter.fail = False
    ReconciliationNotifications.calls = []
    ReconciliationNotifications.fail = True
    monkeypatch.setattr(
        "daidala.project_cycles.GitHubIssueIntakeAdapter", InventoryAdapter
    )
    monkeypatch.setattr(
        "daidala.project_cycles.HermesGatewayNotificationAdapter",
        ReconciliationNotifications,
    )
    preview = operator.preview_reconciliation(
        project_manifest=manifest,
        registration=registration,
        stage_profiles=_stage_profiles(),
    )

    with pytest.raises(PolicyViolationError, match="notification delivery failed"):
        operator.reconcile(
            project_manifest=manifest,
            registration=registration,
            stage_profiles=_stage_profiles(),
            expected_preview_digest=preview.digest,
        )

    assert list((registration.parent / "cycles").glob("cycle-*/admission.json"))
    assert not list((registration.parent / "reconciliation/ticks").glob("*.json"))


def test_reconciliation_recovers_expired_claim_after_both_no_owner_proofs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    operator, manifest, registration, _runtime, _roots = _operator(tmp_path)
    workflow = ReconciliationWorkflow()
    operator.workflow_factory = lambda *_args: workflow  # type: ignore[assignment]
    expired = ClaimIdentity(
        "cycle-" + "c" * 64,
        datetime.now(UTC) - timedelta(hours=2),
        datetime.now(UTC) - timedelta(hours=1),
    )
    InventoryAdapter.ready = ()
    InventoryAdapter.claimed = (replace(_inventory_item("42"), claim=expired),)
    InventoryAdapter.fail = False
    InventoryAdapter.release_calls = 0
    ReconciliationNotifications.calls = []
    ReconciliationNotifications.fail = False
    monkeypatch.setattr(
        "daidala.project_cycles.GitHubIssueIntakeAdapter", InventoryAdapter
    )
    monkeypatch.setattr(
        "daidala.project_cycles.HermesGatewayNotificationAdapter",
        ReconciliationNotifications,
    )

    preview = operator.preview_reconciliation(
        project_manifest=manifest,
        registration=registration,
        stage_profiles=_stage_profiles(),
    )
    result = operator.reconcile(
        project_manifest=manifest,
        registration=registration,
        stage_profiles=_stage_profiles(),
        expected_preview_digest=preview.digest,
    )

    assert preview.recovery is not None
    assert result.outcome is ReconciliationOutcome.ADMITTED
    assert InventoryAdapter.release_calls == 1
    assert [row["event"] for row in ReconciliationNotifications.calls] == [
        "claim-recovered",
        "cycle-admitted",
    ]


def test_reconciliation_board_ownership_blocks_before_claim_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    operator, manifest, registration, _runtime, _roots = _operator(tmp_path)
    board_owner = SimpleNamespace(
        check_id="SI-ACTIVE-CYCLE",
        status=CheckStatus.BLOCKED,
        blocker="registered board has active task ownership",
    )
    operator.diagnose = lambda **_kwargs: SimpleNamespace(  # type: ignore[assignment]
        status=CheckStatus.BLOCKED,
        checks=(board_owner,),
    )
    InventoryAdapter.ready = ()
    InventoryAdapter.claimed = ()
    InventoryAdapter.release_calls = 0
    monkeypatch.setattr(
        "daidala.project_cycles.GitHubIssueIntakeAdapter", InventoryAdapter
    )

    preview = operator.preview_reconciliation(
        project_manifest=manifest,
        registration=registration,
        stage_profiles=_stage_profiles(),
    )

    assert preview.outcome is ReconciliationOutcome.BLOCKED
    assert preview.blocker == "registered board has active task ownership"
    assert InventoryAdapter.release_calls == 0
