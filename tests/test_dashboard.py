"""Tests for bounded dashboard supervision projections."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

from daidala import dashboard_backend
from daidala.constraints import DEFAULT_CONSTRAINT_TEMPLATE
from daidala.dashboard_backend import (
    DashboardBackend,
    _approval_review_packet,
    _workflow_summary,
    _workflow_timeline,
)
from daidala.recommendations import KanbanSnapshot
from daidala.state import WorkflowLedger, WorkflowStage


def _ledger(**overrides: object) -> WorkflowLedger:
    values: dict[str, object] = {
        "workflow_id": "workflow-1",
        "board_slug": "project-board",
        "target_repository": "/repository",
        "requested_goal": "Ship the bounded dashboard",
        "policy_revision": 2,
        "plan_revision": 3,
        "current_constraints_revision": 4,
        "current_constraints_digest": "d" * 64,
        "current_constraints": None,
        "pack_name": "addyosmani",
        "pack_source_revision": "pack-v1",
        "approval": None,
        "review": None,
        "review_disposition": None,
        "committed": False,
        "pushed": False,
        "delivery_authorization": None,
        "baseline_commit": "f" * 40,
        "worktree_path": "/profile/workflows/workflow-1/worktree",
        "worktree_owned": True,
        "plan_source_packet": None,
        "updated_at": datetime(2026, 8, 10, tzinfo=UTC),
        "created_at": datetime(2026, 8, 9, tzinfo=UTC),
        "card_references": (),
        "card_for": lambda _stage: None,
        "artifact_for": lambda _stage: None,
        "activation_for": lambda _stage: None,
    }
    values.update(overrides)
    return cast(WorkflowLedger, SimpleNamespace(**values))


def test_workflow_summary_projects_verified_git_pinned_plan_identity_without_path() -> None:
    summary = _workflow_summary(
        _ledger(
            plan_source_packet=SimpleNamespace(
                plan_id="phased-fixture",
                execution_slot="P0440",
                phase_number=1,
                phase_title="Admit the checkpoint",
                digest="a" * 64,
                reference=SimpleNamespace(source_revision="b" * 40),
            )
        )
    )

    assert summary["plan_source"] == {
        "mode": "git-pinned",
        "plan_id": "phased-fixture",
        "execution_slot": "P0440",
        "phase": {"number": 1, "title": "Admit the checkpoint"},
        "source_revision": "b" * 40,
        "packet": {"digest": "a" * 64, "verification_state": "verified"},
    }
    assert "/profile/" not in json.dumps(summary)


def test_workflow_summary_exposes_only_completed_branch_delivery_receipt() -> None:
    summary = _workflow_summary(
        _ledger(
            committed=True,
            pushed=True,
            delivery_authorization=SimpleNamespace(
                branch="daidala/workflow-1",
                commit="a" * 40,
                credential_alias="github-repository-delivery",
                preview_digest="b" * 64,
            ),
        )
    )

    assert summary["committed"] is True
    assert summary["pushed"] is True
    assert summary["delivery_authorization"] == {
        "branch": "daidala/workflow-1",
        "commit": "a" * 40,
    }
    assert "credential_alias" not in json.dumps(summary)
    assert "preview_digest" not in json.dumps(summary)


def test_approval_review_packet_is_exact_bounded_and_path_free() -> None:
    packet = _approval_review_packet(
        _ledger(),
        {
            "artifact_id": "a" * 64,
            "policy_revision": 2,
            "plan_revision": 3,
            "plan_digest": "b" * 64,
            "approval_summary": {
                "headline": "Exact plan",
                "changes": ["Add approval"],
                "risks": [],
                "verification": ["Run pytest"],
            },
            "approval_summary_digest": "c" * 64,
            "content": "# Exact plan\n<script>literal</script>\n",
        },
    )

    assert packet["plan"]["verification_state"] == "verified"
    assert packet["plan"]["content"] == "# Exact plan\n<script>literal</script>\n"
    assert packet["tuple"] == {
        "workflow_id": "workflow-1",
        "policy_revision": 2,
        "plan_revision": 3,
        "plan_digest": "b" * 64,
        "constraints_revision": 4,
        "constraints_digest": "d" * 64,
    }
    assert packet["successor_packet"]["stage"] == "implement"
    assert packet["successor_packet"]["baseline_commit"] is None
    assert packet["successor_packet"]["worktree"] is None
    assert packet["consequences"]["next_cards"] == ["implement", "verify", "review"]
    assert "/profile/" not in json.dumps(packet)


def test_approval_review_resolves_plan_from_captured_ledger_snapshot() -> None:
    captured_ledger = _ledger()
    snapshots: list[WorkflowLedger] = []

    class Evidence:
        def to_dict(self) -> dict[str, object]:
            return {
                "artifact_id": "a" * 64,
                "policy_revision": 2,
                "plan_revision": 3,
                "plan_digest": "b" * 64,
                "approval_summary": {"headline": "Exact plan"},
                "approval_summary_digest": "c" * 64,
                "content": "# Exact plan\n",
            }

    class Service:
        def status(self, _workflow_id: str) -> WorkflowLedger:
            return captured_ledger

        def current_plan_evidence(
            self, _workflow_id: str, *, ledger: WorkflowLedger | None = None
        ) -> Evidence:
            assert ledger is captured_ledger
            assert ledger is not None
            snapshots.append(ledger)
            return Evidence()

    backend = DashboardBackend(service_factory=cast(Any, Service))

    packet = backend.approval_review("workflow-1")

    assert snapshots == [captured_ledger]
    assert packet["tuple"]["plan_digest"] == "b" * 64


def test_timeline_inserts_distinct_non_kanban_approval_gate() -> None:
    rows = _workflow_timeline(
        _ledger(),
        (
            KanbanSnapshot(
                stage=WorkflowStage.PLAN,
                task_id="t_plan",
                status="done",
                assignee="planner",
            ),
            KanbanSnapshot(
                stage=WorkflowStage.IMPLEMENT,
                task_id="t_implement",
                status="todo",
                assignee="implementer",
            ),
        ),
    )

    plan_index = next(index for index, row in enumerate(rows) if row["stage"] == "plan")
    gate = rows[plan_index + 1]
    assert gate == {
        "kind": "approval_gate",
        "stage": "approval",
        "label": "Human approval — Daidala policy gate",
        "status": "pending",
        "card_id": None,
        "assignee": None,
        "occurred_at": None,
        "approval": None,
    }
    assert rows[plan_index + 2]["stage"] == "implement"
    assert rows[plan_index]["card_id"] == "t_plan"


def test_fully_archived_workflow_projects_terminal_history_without_pending_stages() -> None:
    ledger = _ledger(card_references=(object(), object()))
    snapshots = (
        KanbanSnapshot(
            stage=WorkflowStage.DEFINE,
            task_id="t_define",
            status="archived",
            assignee="author",
        ),
        KanbanSnapshot(
            stage=WorkflowStage.PLAN,
            task_id="t_plan",
            status="archived",
            assignee="planner",
        ),
    )

    class Store:
        def list_all(self) -> tuple[WorkflowLedger, ...]:
            return (ledger,)

    class Service:
        store = Store()

        def status(self, _workflow_id: str) -> WorkflowLedger:
            return ledger

        def combined_status(self, _workflow_id: str) -> tuple[KanbanSnapshot, ...]:
            return snapshots

    backend = DashboardBackend(service_factory=cast(Any, Service))

    assert backend.list_workflows()["workflows"][0]["lifecycle_status"] == "archived"
    detail = backend.workflow_view("workflow-1")
    assert detail["workflow"]["lifecycle_status"] == "archived"
    assert [
        (row["kind"], row["stage"], row["status"])
        for row in detail["timeline"]
    ] == [
        ("stage", "define", "archived"),
        ("stage", "plan", "archived"),
        ("workflow_terminal", "archived", "archived"),
    ]
    assert all(row["status"] != "pending" for row in detail["timeline"])


def test_prerequisites_project_the_exact_runtime_constraint_template() -> None:
    class Store:
        def list_all(self) -> list[object]:
            return []

    service = SimpleNamespace(store=Store())
    backend = DashboardBackend(service_factory=cast(Any, lambda: service))

    payload = backend.prerequisites()

    assert payload["constraint_template"] == {
        "kind": "yaml-template",
        "source": "docs/14-workflow-constraints.md#starter-template",
        "content": DEFAULT_CONSTRAINT_TEMPLATE,
    }


def test_configuration_delegates_only_to_the_profile_safe_provider() -> None:
    expected = {"checkouts": {"root": "/safe/root"}, "registrations": []}
    backend = DashboardBackend(
        service_factory=cast(
            Any,
            lambda: (_ for _ in ()).throw(
                AssertionError("configuration must not resolve a service")
            ),
        ),
        configuration_provider=lambda: expected,
    )

    assert backend.configuration() is expected


def test_configuration_projects_persisted_state_without_private_values(
    tmp_path: Any, monkeypatch: Any
) -> None:
    registration = SimpleNamespace(
        project_id="forgegod-daidala",
        checkout="/private/checkouts/forgegod-daidala",
        intake_credential="github-daidala-read",
        evaluator_backend="restricted-container",
        evaluator_network="denied-by-default",
        notification_adapter="hermes-gateway",
        notification_target="attended-daidala",
        notification_destination="telegram:operator:delivery",
    )
    status = SimpleNamespace(
        project_id="forgegod-daidala",
        to_dict=lambda: {"project_id": "forgegod-daidala", "state": "ok"},
    )

    class CheckoutRoot:
        def __init__(self, _data_root: object) -> None:
            pass

        def read(self) -> object:
            return SimpleNamespace(
                to_dict=lambda: {
                    "checkouts": {
                        "root": "/safe/checkouts",
                        "mode": "disabled",
                        "ttl_hours": 0,
                    }
                }
            )

    monkeypatch.setattr(dashboard_backend, "resolve_data_root", lambda: tmp_path)
    monkeypatch.setattr(
        dashboard_backend, "list_controller_registrations", lambda _root: (registration,)
    )
    monkeypatch.setattr(dashboard_backend, "CheckoutRootStore", CheckoutRoot)
    monkeypatch.setattr(
        dashboard_backend,
        "CheckoutManager",
        lambda _root: SimpleNamespace(statuses=lambda _rows: (status,)),
    )
    monkeypatch.setattr(
        dashboard_backend,
        "GitHubProjectLinksStore",
        lambda _root: SimpleNamespace(read=lambda _rows: ()),
    )
    monkeypatch.setattr(dashboard_backend, "read_private_text", lambda *_args, **_kwargs: "{}")
    monkeypatch.setattr(
        dashboard_backend,
        "parse_prerequisite_evidence",
        lambda _text: SimpleNamespace(
            project_id="forgegod-daidala",
            credential_capabilities=(
                SimpleNamespace(
                    alias="github-daidala-read",
                    capability="github-intake",
                    allowed=("read-organization", "read-project", "read-public-repository"),
                ),
            ),
        ),
    )

    payload = DashboardBackend(service_factory=cast(Any, lambda: None)).configuration()

    assert payload["checkouts"] == {
        "root": "/safe/checkouts",
        "mode": "disabled",
        "ttl_hours": 0,
    }
    row = payload["registrations"][0]
    assert row["checkout"] == {"project_id": "forgegod-daidala", "state": "ok"}
    assert row["github_project"] == {"status": "not_configured"}
    assert row["intake"] == {"status": "healthy"}
    assert row["notification"] == {
        "status": "healthy",
        "adapter": "hermes-gateway",
        "destination_configured": True,
    }
    rendered = json.dumps(payload)
    assert registration.checkout not in rendered
    assert registration.notification_target not in rendered
    assert registration.notification_destination not in rendered

    monkeypatch.setattr(dashboard_backend, "list_controller_registrations", lambda _root: ())
    assert DashboardBackend(service_factory=cast(Any, lambda: None)).configuration()[
        "registrations"
    ] == []


def test_timeline_inserts_distinct_non_kanban_review_gate() -> None:
    rows = _workflow_timeline(
        _ledger(review=SimpleNamespace(digest="a" * 64)),
        (),
    )

    review_index = next(index for index, row in enumerate(rows) if row["stage"] == "review")
    gate = rows[review_index + 1]
    assert gate == {
        "kind": "review_gate",
        "stage": "review_disposition",
        "label": "Human review disposition — Daidala policy gate",
        "status": "pending",
        "card_id": None,
        "assignee": None,
        "occurred_at": None,
        "review_digest": "a" * 64,
        "disposition": None,
    }


def test_artifact_catalog_uses_captured_ledgers_and_exposes_no_paths() -> None:
    ledger = SimpleNamespace(workflow_id="workflow-1")
    captured: list[object] = []
    entry = SimpleNamespace(
        to_dict=lambda: {
            "artifact_id": "a" * 64,
            "workflow_id": "workflow-1",
            "kind": "stage",
            "recorded_at": "2026-08-10T10:00:00+00:00",
        }
    )

    class Store:
        def list_all(self) -> tuple[object, ...]:
            return (ledger,)

    class Service:
        store = Store()

        def list_artifacts(self, workflow_id: str, *, ledger: object) -> tuple[object, ...]:
            assert workflow_id == "workflow-1"
            captured.append(ledger)
            return (entry,)

    payload = DashboardBackend(service_factory=cast(Any, Service)).artifacts()

    assert captured == [ledger]
    assert payload["artifacts"] == [entry.to_dict()]
    assert "path" not in json.dumps(payload)


def test_curator_status_projects_next_transition_times_and_apply_dispatch() -> None:
    calls: list[tuple[object, ...]] = []
    status = SimpleNamespace(
        to_dict=lambda: {
            "policy": {"enabled": True, "stale_after_days": 30, "archive_after_days": 90},
            "state_digest": "a" * 64,
            "counts": {"active": 1, "stale": 0, "archived": 0},
            "pinned": 0,
            "rows": [
                {
                    "workflow_id": "workflow-1",
                    "state": "active",
                    "first_terminal_observed_at": "2026-08-01T00:00:00+00:00",
                    "last_transition_at": "2026-08-01T00:00:00+00:00",
                    "pinned": False,
                    "archive_ids": [],
                }
            ],
        }
    )

    class Service:
        def curator_status(self) -> object:
            return status

        def preview_curator_archive(self, workflow_id: str) -> object:
            calls.append(("preview", workflow_id))
            return SimpleNamespace(to_dict=lambda: {"preview_digest": "b" * 64})

        def apply_curator_archive(
            self, workflow_id: str, *, expected_preview_digest: str
        ) -> object:
            calls.append(("apply", workflow_id, expected_preview_digest))
            return SimpleNamespace(to_dict=lambda: {"transitioned": 1})

    backend = DashboardBackend(service_factory=cast(Any, Service))
    payload = backend.curator_status()
    preview = backend.curator_preview("workflow-1", "archive")
    result = backend.curator_apply(
        "workflow-1", "archive", cast(str, preview["preview_digest"])
    )

    rows = cast(list[dict[str, object]], payload["rows"])
    assert rows[0]["next_transition_at"] == "2026-08-31T00:00:00+00:00"
    assert result == {"transitioned": 1}
    assert calls == [
        ("preview", "workflow-1"),
        ("apply", "workflow-1", "b" * 64),
    ]
