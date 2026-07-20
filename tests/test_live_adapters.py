from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from daidala.adapters import ClaimIdentity, IntakeCategory
from daidala.credentials import CredentialBinding, CredentialBindings
from daidala.errors import PolicyViolationError
from daidala.live_adapters import (
    GitHubIssueIntakeAdapter,
    HermesGatewayNotificationAdapter,
)

NOW = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)
READY = "daidala-si:ready"
CLAIMED = "daidala-si:claimed"


def issue_body() -> str:
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

docs/evaluation-results/v1/uc-01.json sha256:"""
        + "a" * 64
        + """

### Acceptance criteria

- The failing test passes.
- The adjacent arithmetic behavior remains covered.

### Dependencies and risk

Temporary fixture only; no production API change.

### Priority

1

### Publication state

local
"""
    )


def bindings() -> CredentialBindings:
    return CredentialBindings(
        project_id="forgegod-daidala",
        bindings=(
            CredentialBinding("github-read", "environment", "GH_READ_TOKEN"),
            CredentialBinding("github-write", "environment", "GH_WRITE_TOKEN"),
        ),
    )


class GitHubRunner:
    def __init__(self) -> None:
        self.labels = {
            "daidala-si",
            READY,
            "daidala-si:regression",
            "daidala-si:priority-1",
        }
        self.comments: list[dict[str, Any]] = []
        self.state = "OPEN"
        self.commands: list[tuple[tuple[str, ...], dict[str, str]]] = []

    def __call__(
        self, command: tuple[str, ...], environment: Mapping[str, str]
    ) -> tuple[int, str]:
        env = dict(environment)
        self.commands.append((command, env))
        assert "GH_READ_TOKEN" not in env
        assert "GH_WRITE_TOKEN" not in env
        if command[:3] == ("gh", "issue", "view"):
            if command[-1] == "labels":
                return 0, json.dumps(
                    {
                        "labels": [
                            {
                                "color": "ffffff",
                                "description": "",
                                "id": f"LA_{label}",
                                "name": label,
                            }
                            for label in sorted(self.labels)
                        ]
                    }
                )
            payload = {
                "number": 42,
                "url": "https://github.com/forgegod/daidala/issues/42",
                "title": "[Daidala SI] Fix temporary calculator",
                "body": issue_body(),
                "state": self.state,
                "labels": [
                    {
                        "color": "ffffff",
                        "description": "",
                        "id": f"LA_{label}",
                        "name": label,
                    }
                    for label in sorted(self.labels)
                ],
            }
            return 0, json.dumps(payload)
        if command[:3] == ("gh", "api", "--paginate") and command[-1].endswith(
            "/events?per_page=100"
        ):
            return 0, json.dumps(
                [
                    [
                        {
                            "event": "labeled",
                            "label": {"name": READY},
                            "actor": {"login": "forgegod"},
                            "created_at": "2026-07-20T10:00:00Z",
                        }
                    ]
                ]
            )
        if command[:3] == ("gh", "api", "--paginate") and command[-1].endswith(
            "/comments?per_page=100"
        ):
            return 0, json.dumps([self.comments])
        if command[:3] == ("gh", "issue", "comment"):
            body = command[command.index("--body") + 1]
            self.comments.append({"body": body, "user": {"login": "forgegod"}})
            return 0, "https://github.com/forgegod/daidala/issues/42#issuecomment-1"
        if command[:3] == ("gh", "issue", "edit"):
            self.labels.discard(READY)
            self.labels.add(CLAIMED)
            return 0, "https://github.com/forgegod/daidala/issues/42"
        raise AssertionError(f"unexpected command: {command}")


def github_adapter(runner: GitHubRunner) -> GitHubIssueIntakeAdapter:
    return GitHubIssueIntakeAdapter(
        repository="forgegod/daidala",
        read_credential_alias="github-read",
        write_credential_alias="github-write",
        credential_bindings=bindings(),
        authorized_actors=("forgegod",),
        runner=runner,
        environ={
            "PATH": "/usr/bin",
            "HOME": "/tmp/home",
            "GH_READ_TOKEN": "read-secret",
            "GH_WRITE_TOKEN": "write-secret",
        },
    )


def test_github_intake_normalizes_structured_issue_and_ready_actor() -> None:
    runner = GitHubRunner()

    intake = github_adapter(runner).fetch("42")

    assert intake.adapter == "github-issues"
    assert intake.item_id == "42"
    assert intake.category is IntakeCategory.REGRESSION
    assert intake.priority == 1
    assert intake.admission_actor == "forgegod"
    assert intake.ready is True
    assert intake.claim is None
    assert intake.evidence_digests == ("a" * 64,)
    assert intake.acceptance_criteria == (
        "The failing test passes.",
        "The adjacent arithmetic behavior remains covered.",
    )
    assert all(env["GH_TOKEN"] == "read-secret" for _, env in runner.commands)


def test_github_claim_is_replay_safe_and_uses_only_write_binding_for_mutation() -> None:
    runner = GitHubRunner()
    adapter = github_adapter(runner)
    claim = ClaimIdentity(
        "cycle-" + "b" * 64,
        NOW,
        NOW + timedelta(minutes=15),
    )

    first = adapter.claim("42", claim)
    second = adapter.claim("42", claim)

    assert first.claim == second.claim == claim
    assert first.ready is second.ready is True
    assert READY not in runner.labels
    assert CLAIMED in runner.labels
    mutation_calls = [
        (command, env)
        for command, env in runner.commands
        if command[:3] in {("gh", "issue", "comment"), ("gh", "issue", "edit")}
    ]
    assert [command[2] for command, _ in mutation_calls] == ["comment", "edit"]
    assert all(env["GH_TOKEN"] == "write-secret" for _, env in mutation_calls)
    assert len(runner.comments) == 1
    assert claim.claimant in runner.comments[0]["body"]


def test_github_intake_rejects_missing_separate_ready_actor() -> None:
    runner = GitHubRunner()

    def no_events(
        command: tuple[str, ...], environment: Mapping[str, str]
    ) -> tuple[int, str]:
        if command[-1].endswith("/events?per_page=100"):
            return 0, "[[]]"
        return runner(command, environment)

    adapter = GitHubIssueIntakeAdapter(
        repository="forgegod/daidala",
        read_credential_alias="github-read",
        write_credential_alias="github-write",
        credential_bindings=bindings(),
        authorized_actors=("forgegod",),
        runner=no_events,
        environ={"PATH": "/usr/bin", "GH_READ_TOKEN": "r", "GH_WRITE_TOKEN": "w"},
    )

    with pytest.raises(PolicyViolationError, match="ready label actor"):
        adapter.fetch("42")


def test_github_closed_issue_fails_closed() -> None:
    run = GitHubRunner()
    run.state = "CLOSED"
    adapter = github_adapter(run)

    with pytest.raises(PolicyViolationError, match="must be open"):
        adapter.fetch("42")


def test_gateway_notification_returns_only_event_bound_non_private_receipt() -> None:
    calls: list[tuple[tuple[str, ...], dict[str, str]]] = []

    def run(
        command: tuple[str, ...], environment: Mapping[str, str]
    ) -> tuple[int, str]:
        calls.append((command, dict(environment)))
        return 0, json.dumps(
            {
                "success": True,
                "platform": "telegram",
                "message_id": 10,
                "chat_id": "private-chat-id",
            }
        )

    adapter = HermesGatewayNotificationAdapter(
        profile="daidala-self-improvement",
        target_alias="attended-daidala",
        destination="telegram:-1001234567890:17585",
        runner=run,
        environ={"PATH": "/usr/bin", "HOME": "/tmp/home", "GH_TOKEN": "must-not-leak"},
        clock=lambda: NOW,
    )
    payload = {
        "event_id": "cycle-" + "c" * 64 + ":admitted",
        "event": "cycle-admitted",
        "cycle_id": "cycle-" + "c" * 64,
        "workflow_id": "cycle-" + "c" * 64,
        "project_id": "forgegod-daidala",
        "intake_item_id": "42",
        "manifest_digest": "d" * 64,
    }

    receipt = adapter.deliver(payload)

    assert receipt.event_id == payload["event_id"]
    assert receipt.target_alias == "attended-daidala"
    assert receipt.receipt_id == "telegram:10"
    assert "private-chat-id" not in json.dumps(receipt.to_dict())
    assert calls[0][0][:6] == (
        "hermes",
        "-p",
        "daidala-self-improvement",
        "send",
        "--to",
        "telegram:-1001234567890:17585",
    )
    assert calls[0][0][-1] == "--json"
    assert "GH_TOKEN" not in calls[0][1]


def test_hermes_notification_rejects_mutable_home_destination() -> None:
    with pytest.raises(PolicyViolationError, match="non-home"):
        HermesGatewayNotificationAdapter(
            profile="daidala-self-improvement",
            target_alias="attended-daidala",
            destination="telegram",
        )
