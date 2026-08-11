from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from daidala.dashboard_advice import (
    SetupAnalysisUnavailable,
    build_setup_analysis_snapshot,
    configure_setup_analysis,
    request_setup_analysis,
)


class FakeHostModel:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def complete_structured(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return SimpleNamespace(
            parsed={
                "summary": "One repository is ready; verify its checkout before starting work.",
                "priorities": [
                    {
                        "screen": "config",
                        "title": "Verify configuration",
                        "advice": "Use Verification to resolve the remaining checkout state.",
                    }
                ],
            },
            provider="test-provider",
            model="test-model",
        )


def test_setup_analysis_uses_only_aggregate_path_free_snapshot() -> None:
    snapshot = build_setup_analysis_snapshot(
        {
            "registrations": [
                {
                    "project_id": "private-project",
                    "checkout": {"status": "healthy", "path": "/private/checkout"},
                    "github_project": {"status": "not_configured"},
                    "intake": {"status": "blocked"},
                    "evaluator": {"status": "healthy"},
                    "notification": {"status": "not_configured"},
                }
            ]
        },
        {
            "workflows": [
                {
                    "workflow_id": "private-workflow",
                    "requested_goal": "do not send this private goal",
                    "target_repository": "/private/repository",
                    "approval": None,
                    "plan_source": {"mode": "generated"},
                }
            ]
        },
        {
            "artifacts": [
                {
                    "artifact_id": "private-artifact",
                    "availability": "active",
                    "path": "/private/artifact",
                }
            ]
        },
    )

    assert snapshot == {
        "configuration": {
            "registration_count": 1,
            "readiness_counts": {
                "checkout:healthy": 1,
                "evaluator:healthy": 1,
                "github_project:not_configured": 1,
                "intake:blocked": 1,
                "notification:not_configured": 1,
            },
        },
        "workflows": {
            "count": 1,
            "state_counts": {"approval:pending": 1, "plan_source:generated": 1},
        },
        "artifacts": {"count": 1, "availability_counts": {"availability:active": 1}},
    }
    assert "/private" not in json.dumps(snapshot)
    assert "private goal" not in json.dumps(snapshot)


def test_setup_analysis_uses_the_configured_host_model_and_validates_response() -> None:
    provider = FakeHostModel()
    configure_setup_analysis(provider)
    try:
        result = request_setup_analysis(
            {"configuration": {}, "workflows": {}, "artifacts": {}}
        )
    finally:
        configure_setup_analysis(None)

    assert result == {
        "analysis": {
            "summary": "One repository is ready; verify its checkout before starting work.",
            "priorities": [
                {
                    "screen": "config",
                    "title": "Verify configuration",
                    "advice": "Use Verification to resolve the remaining checkout state.",
                }
            ],
        },
        "model": {"provider": "test-provider", "model": "test-model"},
    }
    assert len(provider.calls) == 1
    call = provider.calls[0]
    assert call["schema_name"] == "daidala.setup_advice"
    assert call["purpose"] == "daidala.dashboard.setup_advice"
    assert call["temperature"] == 0.2
    assert call["max_tokens"] == 700


def test_setup_analysis_fails_closed_without_a_host_model() -> None:
    configure_setup_analysis(None)

    with pytest.raises(SetupAnalysisUnavailable):
        request_setup_analysis({"configuration": {}, "workflows": {}, "artifacts": {}})
