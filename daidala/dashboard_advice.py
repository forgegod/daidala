"""Bounded host-model advice for the operator dashboard.

The dashboard adapter owns transport. This module reduces its input to a
path-free readiness snapshot and accepts only a small, validated response from
the host-owned plugin LLM facade.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from threading import Lock
from typing import Any


class SetupAnalysisError(RuntimeError):
    """The host model did not provide a usable advisory response."""


class SetupAnalysisUnavailable(SetupAnalysisError):
    """No supported host-model facade was registered for this process."""


_ANALYSIS_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "priorities"],
    "properties": {
        "summary": {"type": "string", "minLength": 1, "maxLength": 600},
        "priorities": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["screen", "title", "advice"],
                "properties": {
                    "screen": {
                        "type": "string",
                        "enum": ["workflows", "artifacts", "config", "runbook"],
                    },
                    "title": {"type": "string", "minLength": 1, "maxLength": 100},
                    "advice": {"type": "string", "minLength": 1, "maxLength": 400},
                },
            },
        },
    },
}

_ANALYSIS_INSTRUCTIONS = """You advise an operator using the Daidala workflow dashboard.
Use only the supplied readiness snapshot. Give concise, non-authoritative advice.
Do not claim to have inspected files, credentials, artifacts, repositories, or
Kanban cards. Do not invent status. Do not propose commands, configuration keys,
or product capabilities that are not explicitly represented in the snapshot.
Prioritize the next one to three actions that help the operator configure Daidala
or make an informed workflow decision. A priority screen must be one of the
provided dashboard screens. This analysis cannot make changes and never replaces
the dashboard's deterministic workflow recommendations."""

_provider_lock = Lock()
_provider: Any | None = None


def configure_setup_analysis(provider: Any | None) -> None:
    """Register the documented host LLM facade during plugin startup."""

    global _provider
    with _provider_lock:
        _provider = provider


def build_setup_analysis_snapshot(
    configuration: Mapping[str, Any],
    workflows: Mapping[str, Any],
    artifacts: Mapping[str, Any],
) -> dict[str, object]:
    """Reduce existing read projections to model-safe aggregate readiness facts."""

    registration_rows = configuration.get("registrations")
    registrations = registration_rows if isinstance(registration_rows, list) else []
    readiness: Counter[str] = Counter()
    for registration in registrations[:50]:
        if not isinstance(registration, Mapping):
            continue
        for name in ("checkout", "github_project", "intake", "evaluator", "notification"):
            value = registration.get(name)
            status = value.get("status") if isinstance(value, Mapping) else None
            if isinstance(status, str):
                readiness[f"{name}:{status}"] += 1

    workflow_rows = workflows.get("workflows")
    workflow_items = workflow_rows if isinstance(workflow_rows, list) else []
    workflow_states: Counter[str] = Counter()
    for workflow in workflow_items[:100]:
        if not isinstance(workflow, Mapping):
            continue
        approval_state = "approval:recorded" if workflow.get("approval") else "approval:pending"
        workflow_states[approval_state] += 1
        plan_source = workflow.get("plan_source")
        mode = plan_source.get("mode") if isinstance(plan_source, Mapping) else "unknown"
        workflow_states[f"plan_source:{mode if isinstance(mode, str) else 'unknown'}"] += 1

    artifact_rows = artifacts.get("artifacts")
    artifact_items = artifact_rows if isinstance(artifact_rows, list) else []
    artifact_states: Counter[str] = Counter()
    for artifact in artifact_items[:500]:
        if not isinstance(artifact, Mapping):
            continue
        availability = artifact.get("availability")
        if isinstance(availability, str):
            artifact_states[f"availability:{availability}"] += 1

    return {
        "configuration": {
            "registration_count": len(registrations),
            "readiness_counts": dict(sorted(readiness.items())),
        },
        "workflows": {
            "count": len(workflow_items),
            "state_counts": dict(sorted(workflow_states.items())),
        },
        "artifacts": {
            "count": len(artifact_items),
            "availability_counts": dict(sorted(artifact_states.items())),
        },
    }


def request_setup_analysis(snapshot: Mapping[str, object]) -> dict[str, object]:
    """Request one bounded structured response from the registered host model."""

    with _provider_lock:
        provider = _provider
    if provider is None:
        raise SetupAnalysisUnavailable("Host-model advice is unavailable in this dashboard host.")

    try:
        response = provider.complete_structured(
            instructions=_ANALYSIS_INSTRUCTIONS,
            input=[
                {
                    "type": "text",
                    "text": json.dumps(snapshot, sort_keys=True, separators=(",", ":")),
                }
            ],
            json_schema=_ANALYSIS_SCHEMA,
            schema_name="daidala.setup_advice",
            temperature=0.2,
            max_tokens=700,
            timeout=45,
            purpose="daidala.dashboard.setup_advice",
        )
    except Exception as error:  # host boundary; never expose provider details to the browser
        raise SetupAnalysisError("Host-model advice could not be generated.") from error

    parsed = getattr(response, "parsed", None)
    analysis = _normalize_analysis(parsed)
    return {
        "analysis": analysis,
        "model": {
            "provider": _bounded_text(getattr(response, "provider", ""), "provider", 100),
            "model": _bounded_text(getattr(response, "model", ""), "model", 200),
        },
    }


def _normalize_analysis(value: Any) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise SetupAnalysisError("Host model returned no valid structured advice.")
    priorities_value = value.get("priorities")
    if not isinstance(priorities_value, list) or len(priorities_value) > 3:
        raise SetupAnalysisError("Host model returned invalid advice priorities.")

    priorities: list[dict[str, str]] = []
    for priority in priorities_value:
        if not isinstance(priority, Mapping):
            raise SetupAnalysisError("Host model returned invalid advice priorities.")
        screen = priority.get("screen")
        if screen not in {"workflows", "artifacts", "config", "runbook"}:
            raise SetupAnalysisError("Host model returned an invalid advice target.")
        priorities.append(
            {
                "screen": screen,
                "title": _bounded_text(priority.get("title"), "priority title", 100),
                "advice": _bounded_text(priority.get("advice"), "priority advice", 400),
            }
        )

    return {
        "summary": _bounded_text(value.get("summary"), "summary", 600),
        "priorities": priorities,
    }


def _bounded_text(value: Any, label: str, maximum: int) -> str:
    if not isinstance(value, str) or not (text := value.strip()) or len(text) > maximum:
        raise SetupAnalysisError(f"Host model returned an invalid {label}.")
    return text
