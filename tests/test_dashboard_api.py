from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import threading
import time
import types
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from daidala.delivery import DeliveryPreview
from daidala.state import ReviewOutcome

ROOT = Path(__file__).parents[1]
MODULE = ROOT / "dashboard" / "plugin_api.py"


class FakeRouter:
    def get(self, _path: str):
        return lambda function: function

    def post(self, _path: str):
        return lambda function: function

    def put(self, _path: str):
        return lambda function: function

    def delete(self, _path: str):
        return lambda function: function


class FakeHTTPException(Exception):
    def __init__(self, status_code: int, detail: Any) -> None:
        self.status_code = status_code
        self.detail = detail


class FakeRequest:
    pass


class FakeResponse:
    def __init__(
        self,
        content: bytes,
        *,
        media_type: str,
        headers: dict[str, str],
    ) -> None:
        self.body = content
        self.media_type = media_type
        self.headers = headers


def load_api():
    fake = types.ModuleType("fastapi")
    fake.__dict__["APIRouter"] = FakeRouter
    fake.__dict__["HTTPException"] = FakeHTTPException
    fake.__dict__["Request"] = FakeRequest
    fake.__dict__["Response"] = FakeResponse
    original = sys.modules.get("fastapi")
    sys.modules["fastapi"] = fake
    try:
        spec = importlib.util.spec_from_file_location("daidala_dashboard_api_test", MODULE)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if original is None:
            sys.modules.pop("fastapi", None)
        else:
            sys.modules["fastapi"] = original


def test_router_exports_all_phase_two_routes() -> None:
    api = load_api()

    assert api.router is not None
    for name in (
        "health",
        "initialization",
        "initialize",
        "prerequisite_diagnosis",
        "prerequisites",
        "configuration",
        "artifacts",
        "setup_analysis",
        "artifact_text",
        "artifact_download",
        "artifact_curator_status",
        "artifact_curator_preview",
        "artifact_curator_apply",
        "registrations",
        "repository_registration_preview",
        "repository_registration_apply",
        "github_project_links",
        "github_project_link",
        "github_project_link_preview",
        "github_project_link_verify",
        "github_project_link_upsert",
        "github_project_link_delete",
        "checkout_root",
        "checkout_root_preview",
        "checkout_root_replace",
        "checkouts_status",
        "checkout_refresh_preview",
        "checkout_adopt_preview",
        "checkout_adopt_apply",
        "checkout_backups_prune_preview",
        "checkout_backups_prune_apply",
        "checkouts_policy_preview",
        "checkouts_policy_apply",
        "packs",
        "pack_validate",
        "pack_check",
        "pack_skill_content",
        "pack_install_preview",
        "pack_install",
        "workflows",
        "workflow_detail",
        "approval_review",
        "workflow_approve",
        "review_decision",
        "review_disposition_preview",
        "review_disposition",
        "delivery_preview",
        "delivery_apply",
        "workflow_card_comment",
        "workflow_card_unblock",
        "workflow_cancel_preview",
        "workflow_cancel",
        "decisions",
        "recommendations",
        "constraint_preview",
        "constraint_replace",
        "constraint_sources",
        "constraint_source_detail",
        "wizard_inventory",
        "wizard_board_preview",
        "wizard_create_board",
        "wizard_readiness",
        "wizard_preview",
        "wizard_start",
    ):
        assert callable(getattr(api, name))


def test_delivery_routes_require_exact_preview_confirmation_and_redact_authority() -> None:
    api = load_api()
    calls: list[tuple[object, ...]] = []
    expected_preview = DeliveryPreview(
        workflow_id="workflow-1",
        project_id="project-1",
        branch="daidala/workflow-1",
        baseline_commit="a" * 40,
        manifest_digest="b" * 64,
        registration_digest="c" * 64,
        credential_alias="github-repository-delivery",
        credential_available=True,
        review_digest="d" * 64,
        implementation_digest="e" * 64,
        verification_digests=("f" * 64,),
        plan_digest="0" * 64,
        plan_revision=1,
        changed_paths=("daidala/service.py",),
    )

    class Delivery:
        def preview(self, workflow_id: str) -> DeliveryPreview:
            calls.append(("preview", workflow_id))
            return expected_preview

        def apply(self, workflow_id: str, **kwargs: object) -> object:
            calls.append(("apply", workflow_id, kwargs))
            return types.SimpleNamespace(
                workflow_id=workflow_id,
                committed=True,
                pushed=True,
                delivery_authorization=types.SimpleNamespace(
                    branch="daidala/workflow-1",
                    commit="b" * 40,
                    credential_alias="github-repository-delivery",
                ),
            )

    api.__dict__["_delivery_service"] = Delivery

    preview = api.delivery_preview("workflow-1", {})
    applied = api.delivery_apply(
        "workflow-1", {"preview_digest": expected_preview.digest, "confirm": True}
    )

    assert preview["branch"] == "daidala/workflow-1"
    assert applied == {
        "workflow_id": "workflow-1",
        "branch": "daidala/workflow-1",
        "commit": "b" * 40,
        "committed": True,
        "pushed": True,
    }
    assert calls == [
        ("preview", "workflow-1"),
        (
            "apply",
            "workflow-1",
            {"expected_preview_digest": expected_preview.digest, "confirm": True},
        ),
    ]
    assert "credential_alias" not in json.dumps([preview, applied])


def test_delivery_routes_reject_noncanonical_payloads_before_service_dispatch() -> None:
    api = load_api()
    calls = 0

    def delivery_service() -> object:
        nonlocal calls
        calls += 1
        return object()

    api.__dict__["_delivery_service"] = delivery_service

    invalid_payloads = (
        (api.delivery_preview, {"confirm": True}),
        (api.delivery_apply, {}),
        (api.delivery_apply, {"preview_digest": "a" * 64, "confirm": False}),
        (api.delivery_apply, {"preview_digest": "not-a-digest", "confirm": True}),
        (api.delivery_apply, {"preview_digest": "a" * 64, "confirm": True, "extra": 1}),
    )
    for route, payload in invalid_payloads:
        with pytest.raises(FakeHTTPException) as raised:
            route("workflow-1", payload)
        assert raised.value.status_code == 400
    assert calls == 0


def test_setup_analysis_route_uses_server_derived_path_free_snapshot() -> None:
    api = load_api()
    captured: list[dict[str, object]] = []

    class Backend:
        def __init__(self, *, service_factory: object) -> None:
            self.service_factory = service_factory

        def configuration(self) -> dict[str, object]:
            return {
                "registrations": [
                    {
                        "checkout": {"status": "healthy", "path": "/private/checkout"},
                        "github_project": {"status": "not_configured"},
                    }
                ]
            }

        def list_workflows(self) -> dict[str, object]:
            return {
                "workflows": [
                    {
                        "requested_goal": "private request",
                        "target_repository": "/private/repository",
                        "approval": None,
                        "plan_source": {"mode": "generated"},
                    }
                ]
            }

        def artifacts(self) -> dict[str, object]:
            return {
                "artifacts": [
                    {"artifact_id": "private-artifact", "availability": "active"}
                ]
            }

    def analyze(snapshot: dict[str, object]) -> dict[str, object]:
        captured.append(snapshot)
        return {"analysis": {"summary": "Ready", "priorities": []}, "model": {}}

    class PackCheck:
        def to_dict(self) -> dict[str, object]:
            return {
                "ready": False,
                "installable": True,
                "blockers": ["disabled skill"],
                "validation": {
                    "stages": [
                        {"id": "define", "skills": [{"installed": True, "ready": False}]}
                    ]
                },
            }

    class PackService:
        def bundled_names(self) -> tuple[str, ...]:
            return ("test-pack",)

        def check(self, _name: str) -> PackCheck:
            return PackCheck()

    api.__dict__["DashboardBackend"] = Backend
    api.__dict__["pack_service_factory"] = PackService
    api.__dict__["request_setup_analysis"] = analyze

    assert api.setup_analysis({}) == {
        "analysis": {"summary": "Ready", "priorities": []},
        "model": {},
    }
    assert captured == [
        {
            "configuration": {
                "registration_count": 1,
                "readiness_counts": {
                    "checkout:healthy": 1,
                    "github_project:not_configured": 1,
                },
                "requirements": {"registered_github_project": {"minimum": 1, "observed": 0}},
            },
            "workflows": {
                "count": 1,
                "state_counts": {"approval:pending": 1, "plan_source:generated": 1},
            },
            "artifacts": {"count": 1, "availability_counts": {"availability:active": 1}},
            "packs": {
                "pack_count": 1,
                "ready_pack_count": 0,
                "blocked_pack_count": 1,
                "installable_pack_count": 1,
                "phase_counts": {
                    "define": {
                        "declared_pack_count": 1,
                        "packs_with_installed_skill": 1,
                        "packs_with_ready_skill": 0,
                    }
                },
                "requirements": {
                    "workflow_pack": {"minimum": 1, "observed": 1},
                    "operational_pack": {"minimum": 1, "observed": 0},
                    "unblocked_packs": {"maximum": 0, "observed": 1},
                    "installed_skill_per_phase": {"define": {"minimum": 1, "observed": 1}},
                },
            },
        }
    ]
    assert "/private" not in json.dumps(captured)

    with pytest.raises(FakeHTTPException) as malformed:
        api.setup_analysis({"workflow_id": "browser-controlled"})
    assert malformed.value.status_code == 400


def test_router_imports_after_directory_plugin_registration(tmp_path: Path) -> None:
    script = f"""
import importlib.util
import sys
import types
from pathlib import Path

root = Path({str(ROOT)!r})

class APIRouter:
    def get(self, *_args, **_kwargs):
        return lambda function: function
    def post(self, *_args, **_kwargs):
        return lambda function: function
    def put(self, *_args, **_kwargs):
        return lambda function: function
    def delete(self, *_args, **_kwargs):
        return lambda function: function

fake_fastapi = types.ModuleType("fastapi")
fake_fastapi.APIRouter = APIRouter
fake_fastapi.HTTPException = type("HTTPException", (Exception,), {{}})
fake_fastapi.Response = type("Response", (), {{}})
sys.modules["fastapi"] = fake_fastapi

root_spec = importlib.util.spec_from_file_location(
    "daidala_directory_plugin_test",
    root / "__init__.py",
    submodule_search_locations=[str(root)],
)
root_module = importlib.util.module_from_spec(root_spec)
sys.modules["daidala_directory_plugin_test"] = root_module
root_spec.loader.exec_module(root_module)
assert sys.modules["daidala"] is sys.modules["daidala_directory_plugin_test.daidala"]

api_spec = importlib.util.spec_from_file_location(
    "directory_dashboard_api", root / "dashboard" / "plugin_api.py"
)
api_module = importlib.util.module_from_spec(api_spec)
api_spec.loader.exec_module(api_module)
assert api_module.router is not None
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_router_source_exposes_only_closed_mutation_routes() -> None:
    source = MODULE.read_text(encoding="utf-8")

    assert '@router.get("/configuration")' in source
    assert '@router.put("/github-project-links/{project_id}")' in source
    assert '@router.delete("/github-project-links/{project_id}")' in source
    assert '@router.put("/checkout-root")' in source
    assert '@router.post("/constraints/preview")' in source
    assert "sqlite3" not in source
    assert "kanban.db" not in source
    assert "DashboardBackend" in source
    assert '@router.post("/packs/{pack_name}/install")' in source
    assert '@router.post("/constraints/replace")' in source
    assert '@router.get("/workflows/{workflow_id}/approval-review")' in source
    assert '@router.post("/workflows/{workflow_id}/approve")' in source
    assert '@router.get("/workflows/{workflow_id}/review-decision")' in source
    assert '@router.post("/workflows/{workflow_id}/review-disposition/preview")' in source
    assert '@router.post("/workflows/{workflow_id}/review-disposition")' in source
    assert 'payload.get("confirm") is not True' in source


def test_health_distinguishes_the_read_model_from_bounded_mutations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = load_api()
    api.__dict__["service_factory"] = lambda: object()
    monkeypatch.setattr(api, "_dashboard_identity", lambda: {"profile": "test"})

    payload = api.health()

    assert payload["read_model"] is True
    assert "read_only" not in payload
    assert payload["identity"] == {"profile": "test"}


def test_dashboard_identity_sanitizes_missing_or_observed_host_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = load_api()
    monkeypatch.setattr(api, "active_profile", lambda _run: "operator")
    monkeypatch.setattr(api, "version", lambda _name: "0.2.0")
    monkeypatch.setattr(
        api, "_run_command", lambda command: (0, "Hermes Agent v0.19.0")
    )

    assert api._dashboard_identity() == {
        "profile": "operator",
        "daidala_version": "0.2.0",
        "install_source": "unavailable",
        "hermes_version": "0.19.0",
        "supported_hermes_range": ">=0.18.2,<0.21.0",
    }


def test_initialization_routes_preview_then_apply_one_fresh_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    api = load_api()
    monkeypatch.setattr(api, "resolve_data_root", lambda: tmp_path)

    preview = api.initialization()

    assert preview["initialized"] is False
    assert not (tmp_path / "daidala").exists()
    applied = api.initialize({"preview_digest": preview["preview_digest"], "confirm": True})
    repeated = api.initialize(
        {
            "preview_digest": applied["initialization"]["preview_digest"],
            "confirm": True,
        }
    )

    assert applied["created"] is True
    assert repeated["created"] is False
    assert (tmp_path / "daidala" / "policy-ledger.sqlite3").is_file()


def test_initialization_route_rejects_extra_or_stale_browser_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    api = load_api()
    monkeypatch.setattr(api, "resolve_data_root", lambda: tmp_path)

    with pytest.raises(FakeHTTPException) as malformed:
        api.initialize({"preview_digest": "a" * 64, "confirm": True, "path": "/tmp"})
    with pytest.raises(FakeHTTPException) as stale:
        api.initialize({"preview_digest": "a" * 64, "confirm": True})

    assert malformed.value.status_code == 400
    assert stale.value.status_code == 409
    assert not (tmp_path / "daidala").exists()


def test_prerequisite_diagnosis_uses_only_trusted_registration_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    api = load_api()
    registration = types.SimpleNamespace(project_id="example", checkout="/trusted/checkout")
    calls: dict[str, object] = {}

    class Report:
        exit_code = 2

        def to_dict(self) -> dict[str, object]:
            return {"status": "blocked", "checks": []}

    monkeypatch.setattr(api, "resolve_data_root", lambda: tmp_path)
    monkeypatch.setattr(api, "_registered_project", lambda project_id: registration)
    monkeypatch.setattr(api, "registration_path", lambda *_args: tmp_path / "registration.yaml")

    def diagnose(**kwargs: object) -> Report:
        calls.update(kwargs)
        return Report()

    monkeypatch.setattr(api, "run_prerequisite_diagnosis", diagnose)

    payload = api.prerequisite_diagnosis({"project_id": "example", "live": False})

    assert payload == {"report": {"status": "blocked", "checks": []}, "exit_code": 2}
    assert calls["project_manifest"] == Path("/trusted/checkout/.daidala/project.yaml")
    assert calls["live"] is False
    with pytest.raises(FakeHTTPException) as malformed:
        api.prerequisite_diagnosis({"project_id": "example", "live": False, "path": "/tmp"})
    assert malformed.value.status_code == 400


def _approval_identity(**overrides: object) -> dict[str, object]:
    identity: dict[str, object] = {
        "artifact_id": "a" * 64,
        "plan_digest": "b" * 64,
        "summary_digest": "c" * 64,
        "confirm": True,
    }
    identity.update(overrides)
    return identity


def test_exact_plan_approval_rejects_malformed_identity_before_service() -> None:
    api = load_api()
    calls = 0

    def service_factory() -> object:
        nonlocal calls
        calls += 1
        return object()

    api.__dict__["service_factory"] = service_factory

    with pytest.raises(FakeHTTPException) as raised:
        api.workflow_approve("workflow-1", {"confirm": True})

    assert raised.value.status_code == 400
    assert calls == 0


def test_approval_review_uses_server_resolved_backend_packet() -> None:
    api = load_api()

    class Backend:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def approval_review(self, workflow_id: str) -> dict[str, object]:
            return {
                "workflow_id": workflow_id,
                "available": True,
                "plan": {"artifact_id": "a" * 64},
            }

    api.__dict__["DashboardBackend"] = Backend

    assert api.approval_review("workflow-1") == {
        "workflow_id": "workflow-1",
        "available": True,
        "plan": {"artifact_id": "a" * 64},
    }


def test_exact_plan_approval_rejects_stale_identity_without_mutation() -> None:
    api = load_api()
    approvals: list[str] = []

    class Evidence:
        def to_dict(self) -> dict[str, object]:
            return {
                "artifact_id": "a" * 64,
                "plan_digest": "b" * 64,
                "approval_summary_digest": "c" * 64,
                "approval_summary": {"headline": "Exact plan"},
                "content": "# Exact plan\n",
            }

    class Service:
        def current_plan_evidence(self, _workflow_id: str) -> Evidence:
            return Evidence()

        def approve(self, _workflow_id: str, *, plan_digest: str) -> None:
            approvals.append(plan_digest)

    api.__dict__["service_factory"] = Service

    with pytest.raises(FakeHTTPException) as raised:
        api.workflow_approve("workflow-1", _approval_identity(plan_digest="e" * 64))

    assert raised.value.status_code == 409
    assert "changed after review" in raised.value.detail
    assert approvals == []


def test_exact_plan_approval_mutates_only_after_full_identity_match() -> None:
    api = load_api()
    approvals: list[tuple[str, str]] = []

    class Evidence:
        def to_dict(self) -> dict[str, object]:
            return {
                "artifact_id": "a" * 64,
                "plan_digest": "b" * 64,
                "approval_summary_digest": "c" * 64,
                "approval_summary": {"headline": "Exact plan"},
                "content": "# Exact plan\n",
            }

    class Service:
        def current_plan_evidence(self, _workflow_id: str) -> Evidence:
            return Evidence()

        def approve(self, workflow_id: str, *, plan_digest: str) -> None:
            approvals.append((workflow_id, plan_digest))

    class Backend:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def approval_review(self, workflow_id: str) -> dict[str, object]:
            return {"workflow_id": workflow_id, "approval": {"plan_digest": "b" * 64}}

    api.__dict__["service_factory"] = Service
    api.__dict__["DashboardBackend"] = Backend

    result = api.workflow_approve("workflow-1", _approval_identity())

    assert approvals == [("workflow-1", "b" * 64)]
    assert result == {
        "workflow_id": "workflow-1",
        "approval": {"plan_digest": "b" * 64},
    }


def test_review_decision_returns_verified_path_free_evidence() -> None:
    api = load_api()
    implementation_digest = "d" * 64
    verification_digest = "e" * 64

    class Summary:
        def to_dict(self) -> dict[str, object]:
            return {
                "headline": "Review <script>literal</script>",
                "changes": ["Keep the diff literal."],
                "affected_areas": ["dashboard"],
                "risks": [],
                "verification": ["pytest passed"],
            }

    review = types.SimpleNamespace(
        implementation_digest=implementation_digest,
        verification_digests=(verification_digest,),
        summary=Summary(),
        summary_digest="f" * 64,
        outcome=ReviewOutcome.ACCEPTED,
        findings=(),
        plan_digest="c" * 64,
        plan_revision=2,
        policy_revision=1,
        constraints_revision=0,
        constraints_digest="1" * 64,
        activation_digest="2" * 64,
        digest="a" * 64,
        to_dict=lambda: {"outcome": "accepted", "findings": []},
    )
    captured_ledger = types.SimpleNamespace(
        workflow_id="workflow-1",
        board_slug="board-1",
        review=review,
        review_disposition=None,
        pending_revision_request=None,
        plan_revision=2,
        card_for=lambda _stage: None,
        verification_evidence=(
            types.SimpleNamespace(
                command="pytest -q",
                exit_code=0,
                output_digest=verification_digest,
                output_reference="/must/not/escape",
                recorded_at=types.SimpleNamespace(isoformat=lambda: "2026-07-27T20:00:00+00:00"),
            ),
        ),
    )
    snapshot_reads: list[str] = []

    class Service:
        def status(self, _workflow_id: str) -> object:
            return captured_ledger

        def review_packet(self, _workflow_id: str) -> dict[str, object]:
            raise AssertionError("review packet must use the captured ledger snapshot")

        def list_artifacts(
            self, *_args: object, ledger: object | None = None, **_kwargs: object
        ) -> tuple[object, ...]:
            assert ledger is captured_ledger
            snapshot_reads.append("list")
            return (
                types.SimpleNamespace(
                    stage="implement",
                    digest=implementation_digest,
                    artifact_id="b" * 64,
                ),
            )

        def read_artifact_text(
            self, *_args: object, ledger: object | None = None
        ) -> object:
            assert ledger is captured_ledger
            snapshot_reads.append("read")
            return types.SimpleNamespace(content="diff --git a/a b/a\n+<script>literal</script>\n")

        def current_implementation_changed_paths(
            self, _workflow_id: str, *, ledger: object | None = None
        ) -> tuple[str, ...]:
            assert ledger is captured_ledger
            snapshot_reads.append("paths")
            return ("a",)

    api.__dict__["service_factory"] = Service

    result = api.review_decision("workflow-1")

    assert snapshot_reads == ["list", "read", "paths"]
    assert result["evidence"]["implementation"] == {
        "artifact_id": "b" * 64,
        "digest": implementation_digest,
        "content": "diff --git a/a b/a\n+<script>literal</script>\n",
        "changed_paths": ["a"],
    }
    assert result["evidence"]["verification"] == [
        {
            "command": "pytest -q",
            "exit_code": 0,
            "output_digest": verification_digest,
            "recorded_at": "2026-07-27T20:00:00+00:00",
        }
    ]
    serialized = json.dumps(result)
    assert "/must/not/escape" not in serialized
    assert "target_repository" not in serialized

    captured_ledger.verification_evidence = ()
    with pytest.raises(FakeHTTPException) as incomplete:
        api.review_decision("workflow-1")
    assert incomplete.value.status_code == 409
    assert incomplete.value.detail == "Review evidence unavailable"


def test_review_preview_and_apply_use_server_actor_and_hide_worktree_path() -> None:
    api = load_api()
    calls: list[tuple[object, ...]] = []

    class Preview:
        def to_dict(self) -> dict[str, object]:
            return {
                "action": "request_revision",
                "review_digest": "a" * 64,
                "preview_digest": "b" * 64,
                "cards_to_archive": [],
                "worktree_to_release": "/profile/private/worktree",
                "successor_packet": {"target_plan_revision": 2},
            }

    class Service:
        def preview_review_decision(self, workflow_id: str, **kwargs: object) -> Preview:
            calls.append(("preview", workflow_id, kwargs))
            return Preview()

        def apply_review_decision(self, workflow_id: str, **kwargs: object) -> dict[str, object]:
            calls.append(("apply", workflow_id, kwargs))
            return {
                "preview": Preview().to_dict(),
                "workflow": {"workflow_id": workflow_id, "plan_revision": 2},
            }

    api.__dict__["service_factory"] = Service
    rationale = "Address the exact findings and rerun pytest."

    preview = api.review_disposition_preview(
        "workflow-1", {"action": "request_revision", "rationale": rationale}
    )
    applied = api.review_disposition(
        "workflow-1",
        {
            "action": "request_revision",
            "review_digest": "a" * 64,
            "preview_digest": "b" * 64,
            "rationale": rationale,
            "confirm": True,
        },
    )

    assert preview["owned_worktree_release"] is True
    applied_preview = applied["preview"]
    assert isinstance(applied_preview, dict)
    assert applied_preview["owned_worktree_release"] is True
    assert "/profile/private/worktree" not in json.dumps([preview, applied])
    for _, _, kwargs in calls:
        assert kwargs["actor"] == "dashboard:attended-operator"


def test_review_route_errors_redact_profile_local_paths() -> None:
    api = load_api()
    private_path = "/profile/private/worktree"

    class Backend:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def review_decision(self, _workflow_id: str) -> object:
            raise api.ServiceError(f"cannot read review artifact at {private_path}")

    api.__dict__["DashboardBackend"] = Backend
    with pytest.raises(FakeHTTPException) as evidence_error:
        api.review_decision("workflow-1")
    assert evidence_error.value.status_code == 409
    assert evidence_error.value.detail == "Review evidence unavailable"

    class Service:
        def preview_review_decision(self, *_args: object, **_kwargs: object) -> object:
            raise api.ServiceError(f"cannot inspect worktree {private_path}")

        def apply_review_decision(self, *_args: object, **_kwargs: object) -> object:
            raise api.ServiceError(f"cannot release worktree {private_path}")

    api.__dict__["service_factory"] = Service
    rationale = "Apply the exact attended decision."
    with pytest.raises(FakeHTTPException) as preview_error:
        api.review_disposition_preview(
            "workflow-1", {"action": "accept_delivery", "rationale": rationale}
        )
    assert preview_error.value.status_code == 409
    assert preview_error.value.detail == "Review disposition preview unavailable"

    with pytest.raises(FakeHTTPException) as apply_error:
        api.review_disposition(
            "workflow-1",
            {
                "action": "accept_delivery",
                "review_digest": "a" * 64,
                "preview_digest": "b" * 64,
                "rationale": rationale,
                "confirm": True,
            },
        )
    assert apply_error.value.status_code == 409
    assert apply_error.value.detail == "Review disposition could not be applied"
    assert private_path not in json.dumps(
        [evidence_error.value.detail, preview_error.value.detail, apply_error.value.detail]
    )


def test_review_preview_rejects_noncanonical_inputs_before_service_dispatch() -> None:
    api = load_api()

    class Service:
        def preview_review_decision(self, *_args: object, **_kwargs: object) -> object:
            raise AssertionError("invalid review input reached the service")

    api.__dict__["service_factory"] = Service
    invalid_payloads = (
        {"action": "request_revision", "rationale": "feedback", "actor": "browser"},
        {"action": "challenge_reviewer", "rationale": "feedback"},
        {"action": "request_revision", "rationale": "   "},
        {"action": "request_revision", "rationale": "bad\x00feedback"},
        {"action": "request_revision", "rationale": "é" * 2049},
    )

    for payload in invalid_payloads:
        with pytest.raises(FakeHTTPException) as invalid:
            api.review_disposition_preview("workflow-1", payload)
        assert invalid.value.status_code == 400


def test_review_disposition_rejects_unchecked_or_stale_requests() -> None:
    api = load_api()
    calls = 0

    class Service:
        def apply_review_decision(self, *_args: object, **_kwargs: object) -> object:
            nonlocal calls
            calls += 1
            raise api.ServiceError("review decision inputs changed after preview")

    api.__dict__["service_factory"] = Service
    payload = {
        "action": "accept_delivery",
        "review_digest": "a" * 64,
        "preview_digest": "b" * 64,
        "rationale": "Accept the exact reviewed evidence.",
        "confirm": False,
    }
    with pytest.raises(FakeHTTPException) as unchecked:
        api.review_disposition("workflow-1", payload)
    assert unchecked.value.status_code == 400
    assert calls == 0

    payload["confirm"] = True
    with pytest.raises(FakeHTTPException) as stale:
        api.review_disposition("workflow-1", payload)
    assert stale.value.status_code == 409
    assert calls == 1


def test_card_detail_uses_bounded_show_and_runs_adapters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = load_api()
    commands: list[tuple[str, ...]] = []
    show = {
        "task": {
            "id": "t_plan",
            "title": "Plan card",
            "priority": 4,
            "created_at": 10.5,
            "workspace_path": "/must/not/escape",
        },
        "comments": [
            {"author": "operator", "body": "<b>literal</b>", "created_at": index}
            for index in range(25)
        ],
        "events": [
            {"kind": "heartbeat", "payload": {"path": "/hidden"}, "created_at": index}
            for index in range(55)
        ],
    }
    runs = [
        {
            "id": index,
            "profile": "planner",
            "status": "closed",
            "outcome": "completed",
            "started_at": index,
            "ended_at": index + 1,
            "summary": "handoff",
            "error": None,
            "metadata": {"path": "/hidden"},
        }
        for index in range(25)
    ]

    def run_command(command: tuple[str, ...], **kwargs: object) -> object:
        commands.append(command)
        assert kwargs["timeout"] == 10
        return types.SimpleNamespace(
            returncode=0,
            stdout=json.dumps(show if "show" in command else runs),
            stderr="",
        )

    monkeypatch.setattr(api.subprocess, "run", run_command)

    detail = api._kanban_card_detail("board", "t_plan")

    assert commands == [
        ("hermes", "kanban", "--board", "board", "show", "t_plan", "--json"),
        ("hermes", "kanban", "--board", "board", "runs", "t_plan", "--json"),
    ]
    assert len(detail["comments"]) == len(detail["runs"]) == 20
    assert len(detail["events"]) == 50
    assert detail["created_at"] == 10.5
    assert detail["comments"][0]["body"] == "<b>literal</b>"
    serialized = json.dumps(detail)
    assert "workspace_path" not in serialized
    assert "metadata" not in serialized
    assert "/hidden" not in serialized


def test_card_remediation_routes_require_confirmed_bounded_workflow_owned_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = load_api()
    ledger = types.SimpleNamespace(
        board_slug="board-1",
        card_references=(types.SimpleNamespace(task_id="card-1", stage="verify"),),
    )
    api.__dict__["service_factory"] = lambda: types.SimpleNamespace(
        status=lambda workflow_id: ledger if workflow_id == "workflow-1" else None
    )
    commands: list[tuple[str, ...]] = []

    def run(command: tuple[str, ...], **kwargs: object) -> object:
        commands.append(command)
        assert kwargs["timeout"] == 10
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(api.subprocess, "run", run)

    assert api.workflow_card_comment(
        "workflow-1",
        "card-1",
        {"comment": "Provide the missing verification evidence.", "confirm": True},
    ) == {"commented": True, "card_id": "card-1"}
    assert api.workflow_card_unblock(
        "workflow-1", "card-1", {"reason": "Evidence is now available.", "confirm": True}
    ) == {"unblocked": True, "card_id": "card-1"}
    assert commands == [
        (
            "hermes", "kanban", "--board", "board-1", "comment", "card-1",
            "Provide the missing verification evidence.",
        ),
        (
            "hermes", "kanban", "--board", "board-1", "unblock", "card-1",
            "--reason", "Evidence is now available.",
        ),
    ]

    with pytest.raises(FakeHTTPException) as invalid:
        api.workflow_card_comment(
            "workflow-1", "unknown", {"comment": "bad\x01text", "confirm": True}
        )
    assert invalid.value.status_code == 400
    assert len(commands) == 2


def test_cancellation_routes_bind_the_current_ledger_token_and_hide_worktree_path() -> None:
    api = load_api()
    ledger = types.SimpleNamespace(
        workflow_id="workflow-1",
        card_references=(
            types.SimpleNamespace(task_id="card-1", stage="verify"),
            types.SimpleNamespace(task_id="card-2", stage="review"),
        ),
        worktree_owned=True,
        worktree_path="/profile/private/worktree",
    )
    observed = types.SimpleNamespace(ledger=ledger, updated_at="token-1")
    cancelled: list[tuple[str, str]] = []

    class Service:
        store = types.SimpleNamespace(get_with_token=lambda _workflow_id: observed)

        def cancel(self, workflow_id: str, reason: str) -> object:
            cancelled.append((workflow_id, reason))
            return ledger

    api.__dict__["service_factory"] = Service
    preview = api.workflow_cancel_preview("workflow-1", {"reason": "  Superseded.  "})

    assert preview["cards"] == [
        {"task_id": "card-1", "stage": "verify"},
        {"task_id": "card-2", "stage": "review"},
    ]
    assert preview["owned_worktree_release"] is True
    assert preview["reason"] == "Superseded."
    assert "/profile/private/worktree" not in json.dumps(preview)

    result = api.workflow_cancel(
        "workflow-1",
        {"reason": "  Superseded.  ", "preview_digest": preview["preview_digest"], "confirm": True},
    )
    assert result == {"cancelled": True, "workflow_id": "workflow-1"}
    assert cancelled == [("workflow-1", "Superseded.")]

    stale = types.SimpleNamespace(ledger=ledger, updated_at="token-2")
    api.__dict__["service_factory"] = lambda: types.SimpleNamespace(
        store=types.SimpleNamespace(get_with_token=lambda _workflow_id: stale),
        cancel=lambda *_args: pytest.fail("stale preview reached cancellation"),
    )
    with pytest.raises(FakeHTTPException) as stale_error:
        api.workflow_cancel(
            "workflow-1",
            {"reason": "Superseded.", "preview_digest": preview["preview_digest"], "confirm": True},
        )
    assert stale_error.value.status_code == 409


def test_kanban_detail_rejects_mismatched_card_identity() -> None:
    api = load_api()
    api.__dict__["kanban_show"] = lambda _board, _task: {"task": {"id": "other"}}
    api.__dict__["kanban_runs"] = lambda _board, _task: []

    with pytest.raises(api.DashboardBackendError, match="does not match"):
        api._kanban_card_detail("board", "t_plan")


def test_kanban_read_enforces_output_and_timeout_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = load_api()

    def oversized(*_args: object, **_kwargs: object) -> object:
        return types.SimpleNamespace(returncode=0, stdout="x" * (64 * 1024 + 1), stderr="")

    monkeypatch.setattr(api.subprocess, "run", oversized)
    with pytest.raises(api.DashboardBackendError, match="64 KiB"):
        api.kanban_show("board", "t_plan")

    def timed_out(command: tuple[str, ...], **_kwargs: object) -> object:
        raise api.subprocess.TimeoutExpired(command, 10)

    monkeypatch.setattr(api.subprocess, "run", timed_out)
    with pytest.raises(api.DashboardBackendError, match="timed out"):
        api.kanban_runs("board", "t_plan")


def test_pack_routes_use_one_typed_service_projection() -> None:
    api = load_api()
    calls: list[object] = []

    class Result:
        def __init__(self, payload: dict[str, object]) -> None:
            self.payload = payload

        def to_dict(self) -> dict[str, object]:
            return self.payload

    class PackService:
        def bundled_names(self) -> tuple[str, ...]:
            return ("addyosmani", "aidlc")

        def validate(self, name: str) -> Result:
            calls.append(("validate", name))
            return Result({"name": name, "stages": [{"id": "define"}]})

        def check(self, name: str) -> Result:
            calls.append(("check", name))
            return Result({"name": name, "preview_digest": "a" * 64})

        def skill_content(self, pack: str, skill: str) -> Result:
            calls.append(("content", pack, skill))
            return Result({"pack": pack, "skill": skill, "content": "# exact\n"})

        def install(self, name: str, *, expected_preview_digest: str, confirm: bool) -> Result:
            calls.append(("install", name, expected_preview_digest, confirm))
            return Result({"success": True})

        def preview_action(self, name: str, action: object, *, skill_name=None) -> Result:
            calls.append(("preview_action", name, str(action), skill_name))
            return Result({"action": str(action), "skills": [skill_name] if skill_name else []})

        def apply_action(
            self,
            name: str,
            action: object,
            *,
            skill_name=None,
            expected_preview_digest: str,
            confirm: bool,
        ) -> Result:
            calls.append(
                (
                    "apply_action",
                    name,
                    str(action),
                    skill_name,
                    expected_preview_digest,
                    confirm,
                )
            )
            return Result({"success": True, "affected": [skill_name] if skill_name else []})

    api.__dict__["pack_service_factory"] = PackService

    assert [row["name"] for row in api.packs()["packs"]] == ["addyosmani", "aidlc"]
    assert api.pack_validate("aidlc")["valid"] is True
    assert api.pack_check("addyosmani")["preview_digest"] == "a" * 64
    assert api.pack_skill_content("aidlc", "aidlc-adapter")["content"] == "# exact\n"
    assert api.pack_install_preview("aidlc")["name"] == "aidlc"
    assert api.pack_install(
        "addyosmani", {"preview_digest": "a" * 64, "confirm": True}
    ) == {"success": True}
    assert ("install", "addyosmani", "a" * 64, True) in calls
    assert api.pack_skill_action_preview(
        "aidlc", {"action": "disable", "skill": "aidlc-adapter"}
    )["skills"] == ["aidlc-adapter"]
    assert api.pack_skill_action_apply(
        "aidlc",
        {
            "action": "enable",
            "skill": "aidlc-adapter",
            "preview_digest": "b" * 64,
            "confirm": True,
        },
    ) == {"success": True, "affected": ["aidlc-adapter"]}
    assert (
        "apply_action",
        "aidlc",
        "enable",
        "aidlc-adapter",
        "b" * 64,
        True,
    ) in calls


def test_pack_skill_action_routes_reject_unknown_fields_and_unconfirmed_apply() -> None:
    api = load_api()
    calls = 0

    def pack_service_factory() -> object:
        nonlocal calls
        calls += 1
        return object()

    api.__dict__["pack_service_factory"] = pack_service_factory

    with pytest.raises(FakeHTTPException) as unknown:
        api.pack_skill_action_preview("aidlc", {"action": "enable", "unexpected": True})
    assert unknown.value.status_code == 400

    with pytest.raises(FakeHTTPException) as unconfirmed:
        api.pack_skill_action_apply(
            "aidlc", {"action": "disable", "preview_digest": "a" * 64}
        )
    assert unconfirmed.value.status_code == 400
    assert calls == 0


def test_unconfirmed_pack_install_does_not_construct_service() -> None:
    api = load_api()
    calls = 0

    def pack_service_factory() -> object:
        nonlocal calls
        calls += 1
        return object()

    api.__dict__["pack_service_factory"] = pack_service_factory

    with pytest.raises(FakeHTTPException) as raised:
        api.pack_install("addyosmani", {"preview_digest": "a" * 64})

    assert raised.value.status_code == 400
    assert "explicit confirmation is required" in raised.value.detail
    assert calls == 0


def test_stale_pack_preview_maps_to_conflict_without_retry() -> None:
    api = load_api()

    class PackService:
        def install(self, *_args, **_kwargs):
            raise api.StalePackPreviewError("pack installation inputs changed after preview")

    api.__dict__["pack_service_factory"] = PackService

    with pytest.raises(FakeHTTPException) as raised:
        api.pack_install(
            "addyosmani", {"preview_digest": "a" * 64, "confirm": True}
        )

    assert raised.value.status_code == 409
    assert "changed after preview" in raised.value.detail


def test_unconfirmed_wizard_start_does_not_construct_service() -> None:
    api = load_api()
    calls = 0

    def service_factory() -> object:
        nonlocal calls
        calls += 1
        return object()

    api.__dict__["service_factory"] = service_factory

    with pytest.raises(FakeHTTPException) as raised:
        api.wizard_start({})

    assert raised.value.status_code == 400
    assert "explicit confirmation is required" in raised.value.detail
    assert calls == 0


def test_existing_explicit_workflow_returns_safe_open_reference_without_start() -> None:
    api = load_api()
    starts = 0

    class Service:
        store = types.SimpleNamespace(get=lambda workflow_id: object())

        def validate_start_preflight(self, **_kwargs):
            return object()

        def start(self, **_kwargs):
            nonlocal starts
            starts += 1

    request = types.SimpleNamespace(
        workflow_id="existing-workflow",
        start_kwargs=lambda: {},
    )
    api.__dict__["_resolved_setup_request"] = lambda payload, apply: (request, Service())
    api.__dict__["_preflight_kwargs"] = lambda resolved: {}
    api.__dict__["_setup_preview"] = lambda resolved, preflight: {
        "preview_digest": "a" * 64
    }

    with pytest.raises(FakeHTTPException) as raised:
        api.wizard_start({"preview_digest": "a" * 64})

    assert raised.value.status_code == 409
    assert raised.value.detail == {
        "code": "workflow_exists",
        "workflow_id": "existing-workflow",
    }
    assert starts == 0


def test_wizard_preview_rejects_browser_paths_and_unknown_fields_before_service() -> None:
    api = load_api()
    calls = 0

    def service_factory() -> object:
        nonlocal calls
        calls += 1
        return object()

    api.__dict__["service_factory"] = service_factory

    with pytest.raises(FakeHTTPException) as raised:
        api.wizard_preview(
            {
                "selection": {"project_id": "project"},
                "request": {"target_repository": "/browser/path"},
            }
        )

    assert raised.value.status_code == 400
    assert "unknown setup request fields" in raised.value.detail
    assert calls == 0


def test_wizard_inventory_exposes_profile_policy_sources_and_only_mounted_registrations(
    tmp_path: Path,
) -> None:
    api = load_api()
    matching = types.SimpleNamespace(
        project_id="matching",
        verified_remote="git@github.com:forgegod/daidala.git",
        controller_profile="controller",
    )
    foreign = types.SimpleNamespace(
        project_id="foreign",
        verified_remote="git@github.com:forgegod/other.git",
        controller_profile="other",
    )

    def run_command(command: tuple[str, ...]) -> tuple[int, str]:
        if command == ("hermes", "kanban", "boards", "list", "--json"):
            return 0, '[{"slug": "existing"}]'
        return 0, " ◆controller      model      stopped\n  worker           model      stopped"

    api.__dict__["_run_command"] = run_command
    skills = tmp_path / "skills"
    (skills / "policy-source").mkdir(parents=True)
    (skills / "policy-source" / "SKILL.md").write_text(
        "---\nname: policy-source\n---\n```yaml\n"
        "schema: daidala.workflow-constraints/v1\n"
        "global: [Preserve approved scope.]\n"
        "```\n",
        encoding="utf-8",
    )
    api.__dict__["resolve_data_root"] = lambda: tmp_path
    api.__dict__["_registered_projects"] = lambda controller_profile=None: {
        item.project_id: item
        for item in (matching, foreign)
        if controller_profile is None or item.controller_profile == controller_profile
    }

    payload = api.wizard_inventory()

    assert payload["controller_profile"] == "controller"
    assert payload["projects"] == [
        {"project_id": "matching", "repository": "git@github.com:forgegod/daidala.git"}
    ]
    assert payload["policy_sources"] == [
        {"name": "policy-source", "digest": payload["policy_sources"][0]["digest"]}
    ]
    assert len(payload["policy_sources"][0]["digest"]) == 64


def test_constraint_source_routes_expose_only_valid_bounded_policy_skills(
    tmp_path: Path,
) -> None:
    api = load_api()
    skills = tmp_path / "skills"
    policy = skills / "policy-source"
    policy.mkdir(parents=True)
    markdown = (
        "---\nname: policy-source\n---\n```yaml\n"
        "schema: daidala.workflow-constraints/v1\n"
        "global: [Preserve approved scope.]\n"
        "```\n"
    )
    (policy / "SKILL.md").write_text(markdown, encoding="utf-8")
    non_policy = skills / "non-policy"
    non_policy.mkdir()
    (non_policy / "SKILL.md").write_text("---\nname: non-policy\n---\n", encoding="utf-8")
    api.__dict__["resolve_data_root"] = lambda: tmp_path

    listed = api.constraint_sources()
    detail = api.constraint_source_detail("policy-source")

    assert listed["sources"] == [{"name": "policy-source", "digest": detail["source"]["digest"]}]
    assert detail == {
        "available": True,
        "source": listed["sources"][0],
        "skill_markdown": markdown,
        "canonical_content": (
            '{"global":["Preserve approved scope."],'
            '"schema":"daidala.workflow-constraints/v1"}'
        ),
    }
    with pytest.raises(FakeHTTPException) as raised:
        api.constraint_source_detail("non-policy")
    assert raised.value.status_code == 404


def test_oversized_constraint_source_detail_is_sanitized(tmp_path: Path) -> None:
    api = load_api()
    source = tmp_path / "skills" / "oversized-policy"
    source.mkdir(parents=True)
    source.joinpath("SKILL.md").write_text(
        "---\n" + ("x" * api.MAX_SKILL_DOCUMENT_BYTES) + "\n---\n```yaml\n"
        "schema: daidala.workflow-constraints/v1\n"
        "global: [Preserve approved scope.]\n"
        "```\n",
        encoding="utf-8",
    )
    api.__dict__["resolve_data_root"] = lambda: tmp_path

    detail = api.constraint_source_detail("oversized-policy")

    assert detail["available"] is False
    assert detail["source"]["name"] == "oversized-policy"
    assert detail["reason"] == "policy source document exceeds the 1 MiB response bound"
    assert "skill_markdown" not in detail


def test_board_creation_requires_explicit_slug_and_display_name() -> None:
    api = load_api()
    commands: list[tuple[str, ...]] = []
    api.__dict__["_run_command"] = lambda command: (
        commands.append(command) or 0,
        "[]",
    )

    with pytest.raises(FakeHTTPException) as raised:
        api.wizard_board_preview({"slug": "new-board", "name": ""})

    assert raised.value.status_code == 400
    assert "display name is required" in raised.value.detail

    preview = api.wizard_board_preview(
        {"slug": "new-board", "name": "New Board"}
    )

    assert preview["preview"]["command"] == [
        "hermes",
        "kanban",
        "boards",
        "create",
        "new-board",
        "--name",
        "New Board",
    ]


def test_default_service_is_process_cached_to_avoid_concurrent_store_initialization() -> None:
    api = load_api()
    service = object()
    calls = 0
    worker_count = 8
    start = threading.Barrier(worker_count)

    class Backend:
        @classmethod
        def from_default_profile(cls):
            nonlocal calls
            calls += 1
            time.sleep(0.05)
            return types.SimpleNamespace(service=service)

    api.__dict__["DashboardBackend"] = Backend
    api._reset_default_service()

    def resolve_service() -> object:
        start.wait()
        return api._default_service()

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        services = list(executor.map(lambda _index: resolve_service(), range(worker_count)))

    assert services == [service] * worker_count
    assert calls == 1


def test_registration_projection_is_path_free_for_project_link_ui(
    tmp_path: Path,
) -> None:
    api = load_api()
    registration = types.SimpleNamespace(
        project_id="forgegod-daidala",
        controller_profile="controller",
        board="daidala",
        repository_canonical="forgegod/daidala",
        verified_remote="git@github.com:forgegod/daidala.git",
        intake_credential="github-daidala-read",
        notification_adapter="hermes-gateway",
        notification_target="attended-daidala",
        evaluator_backend="restricted-container",
        evaluator_network="denied-by-default",
        checkout="/private/checkouts/forgegod-daidala",
    )

    class CheckoutRoot:
        def __init__(self, _data_root: Path) -> None:
            pass

        def read(self) -> object:
            return types.SimpleNamespace(root=Path("/private/checkouts"))

    api.__dict__["_current_registrations"] = lambda: (registration,)
    api.__dict__["CheckoutRootStore"] = CheckoutRoot
    api.__dict__["resolve_data_root"] = lambda: tmp_path

    payload = api.registrations()

    assert payload["registrations"] == [
        {
            "project_id": "forgegod-daidala",
            "controller_profile": "controller",
            "board": "daidala",
            "repository_canonical": "forgegod/daidala",
            "verified_remote": "git@github.com:forgegod/daidala.git",
            "intake_credential": "github-daidala-read",
            "notification_adapter": "hermes-gateway",
            "notification_target": "attended-daidala",
            "evaluator_backend": "restricted-container",
            "evaluator_network": "denied-by-default",
            "checkout_match": True,
        }
    ]
    assert registration.checkout not in json.dumps(payload)


def test_configuration_route_delegates_to_the_profile_safe_backend() -> None:
    api = load_api()
    expected = {
        "checkouts": {"root": "/safe/checkouts", "mode": "wipe-if-clean", "ttl_hours": 24},
        "registrations": [
            {
                "project_id": "forgegod-daidala",
                "checkout": {
                    "project_id": "forgegod-daidala",
                    "state": "ok",
                    "path_exists": True,
                },
                "github_project": {
                    "status": "healthy",
                    "owner": "forgegod",
                    "project_number": 3,
                    "node_id_configured": True,
                },
                "intake": {"status": "healthy"},
                "evaluator": {
                    "status": "healthy",
                    "backend": "restricted-container",
                    "network": "denied-by-default",
                },
                "notification": {
                    "status": "healthy",
                    "adapter": "hermes-gateway",
                    "destination_configured": True,
                },
            }
        ],
    }

    class Backend:
        def __init__(self, *, service_factory: object) -> None:
            self.service_factory = service_factory

        def configuration(self) -> dict[str, object]:
            return expected

    api.__dict__["DashboardBackend"] = Backend
    payload = api.configuration()

    assert payload == expected


def test_repository_registration_routes_use_one_profile_bound_preview_and_apply_service() -> None:
    api = load_api()
    preview = types.SimpleNamespace(
        to_dict=lambda: {
            "valid": True,
            "repository": "forgegod/daidala",
            "project_id": "forgegod-daidala",
            "controller_profile": "controller",
            "preview_digest": "f" * 64,
            "readiness": {"board_selected": True, "delivery_secret_value_checked": False},
            "writes": {"record_count": 2},
        }
    )
    calls: list[tuple[object, ...]] = []

    class Service:
        def preview(self, github_url: str) -> object:
            calls.append(("preview", github_url))
            return preview

        def apply(self, github_url: str, **kwargs: object) -> object:
            calls.append(("apply", github_url, kwargs))
            return preview

    api.__dict__["_repository_registration_service"] = lambda: Service()

    inspected = api.repository_registration_preview(
        {"github_url": "https://github.com/forgegod/daidala"}
    )
    applied = api.repository_registration_apply(
        {
            "github_url": "https://github.com/forgegod/daidala",
            "preview_digest": "f" * 64,
            "confirm": True,
        }
    )

    assert inspected == preview.to_dict()
    assert applied == preview.to_dict()
    assert calls == [
        ("preview", "https://github.com/forgegod/daidala"),
        (
            "apply",
            "https://github.com/forgegod/daidala",
            {"expected_preview_digest": "f" * 64, "confirmation": "register-repository"},
        ),
    ]
    assert "token" not in json.dumps(applied).lower()


def test_project_link_verify_returns_only_sanitized_session_result(tmp_path: Path) -> None:
    api = load_api()
    registration = types.SimpleNamespace(project_id="forgegod-daidala")
    link = api.GitHubProjectLink(
        project_id="forgegod-daidala",
        owner="forgegod",
        project_number=3,
        project_node_id="PVT_kwDOB7_R_5m",
    )

    class Store:
        def read(self, _registrations: object) -> tuple[object, ...]:
            return (link,)

    verifier = types.SimpleNamespace(
        verify=lambda **_kwargs: (
            link,
            {
                "owner": "forgegod",
                "project_number": 3,
                "project_node_id": "PVT_kwDOB7_R_5m",
                "title": "Daidala delivery",
                "url": "https://github.com/orgs/forgegod/projects/3",
            },
        )
    )
    api.__dict__["_current_registrations"] = lambda: (registration,)
    api.__dict__["_registered_project"] = lambda _project_id: registration
    api.__dict__["_project_link_store"] = Store
    api.__dict__["github_project_verifier_factory"] = lambda: verifier
    api.__dict__["registration_path"] = lambda _root, _project_id: tmp_path / "registration.yaml"
    api.__dict__["resolve_data_root"] = lambda: tmp_path

    payload = api.github_project_link_verify("forgegod-daidala")

    assert payload == {
        "healthy": True,
        "link": link.to_dict(),
        "project": {
            "owner": "forgegod",
            "project_number": 3,
            "project_node_id": "PVT_kwDOB7_R_5m",
            "title": "Daidala delivery",
            "url": "https://github.com/orgs/forgegod/projects/3",
        },
    }
    assert "token" not in json.dumps(payload).lower()


def test_artifact_routes_project_metadata_text_and_digest_verified_download() -> None:
    api = load_api()
    artifact_id = "a" * 64
    digest = "b" * 64
    entry = types.SimpleNamespace(artifact_id=artifact_id, digest=digest)

    class Backend:
        def __init__(self, *, service_factory: object) -> None:
            self.service_factory = service_factory

        def artifacts(self, workflow_id: str | None) -> dict[str, object]:
            return {"workflow_id": workflow_id, "artifacts": [{"artifact_id": artifact_id}]}

        def artifact_text(self, workflow_id: str, selected: str) -> dict[str, object]:
            return {"workflow_id": workflow_id, "artifact_id": selected, "content": "<literal>"}

        def artifact_download(self, workflow_id: str, selected: str) -> object:
            assert (workflow_id, selected) == ("workflow-1", artifact_id)
            return types.SimpleNamespace(entry=entry, content=b"exact-bytes")

    api.__dict__["DashboardBackend"] = Backend

    assert api.artifacts("workflow-1")["artifacts"] == [{"artifact_id": artifact_id}]
    assert api.artifact_text("workflow-1", artifact_id)["content"] == "<literal>"
    response = api.artifact_download("workflow-1", artifact_id)
    assert response.body == b"exact-bytes"
    assert response.media_type == "application/octet-stream"
    assert response.headers["X-Daidala-Artifact-SHA256"] == digest
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert artifact_id in response.headers["Content-Disposition"]


def test_artifact_route_errors_are_typed_and_path_free() -> None:
    api = load_api()
    private_path = "/profile/private/artifact.md"

    class Backend:
        def __init__(self, *, service_factory: object) -> None:
            self.service_factory = service_factory

        def artifact_text(self, _workflow_id: str, _artifact_id: str) -> object:
            raise api.ArtifactAccessError(
                f"digest mismatch at {private_path}",
                reason=api.ArtifactFailureReason.DIGEST_MISMATCH,
            )

    api.__dict__["DashboardBackend"] = Backend
    with pytest.raises(FakeHTTPException) as raised:
        api.artifact_text("workflow-1", "a" * 64)

    assert raised.value.status_code == 409
    assert raised.value.detail == {
        "message": "Artifact unavailable",
        "reason": "digest_mismatch",
    }
    assert private_path not in json.dumps(raised.value.detail)


def test_curator_routes_require_exact_preview_confirmation() -> None:
    api = load_api()
    calls: list[tuple[object, ...]] = []

    class Backend:
        def __init__(self, *, service_factory: object) -> None:
            self.service_factory = service_factory

        def curator_status(self) -> dict[str, object]:
            return {"counts": {"active": 1, "stale": 0, "archived": 0}}

        def curator_preview(
            self, workflow_id: str, operation: str, archive_id: str | None
        ) -> dict[str, object]:
            calls.append(("preview", workflow_id, operation, archive_id))
            return {"operation": operation, "preview_digest": "c" * 64}

        def curator_apply(
            self,
            workflow_id: str,
            operation: str,
            preview_digest: str,
            archive_id: str | None,
        ) -> dict[str, object]:
            calls.append(("apply", workflow_id, operation, preview_digest, archive_id))
            return {"operation": operation, "transitioned": 1}

    api.__dict__["DashboardBackend"] = Backend
    assert api.artifact_curator_status()["counts"]["active"] == 1
    preview = api.artifact_curator_preview("workflow-1", {"operation": "archive"})
    result = api.artifact_curator_apply(
        "workflow-1",
        {"operation": "archive", "preview_digest": preview["preview_digest"], "confirm": True},
    )
    assert result == {"operation": "archive", "transitioned": 1}
    assert calls == [
        ("preview", "workflow-1", "archive", None),
        ("apply", "workflow-1", "archive", "c" * 64, None),
    ]

    with pytest.raises(FakeHTTPException) as malformed:
        api.artifact_curator_apply(
            "workflow-1",
            {
                "operation": "archive",
                "preview_digest": "c" * 64,
                "confirm": True,
                "path": "/tmp/private",
            },
        )
    assert malformed.value.status_code == 400
