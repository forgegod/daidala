"""Bounded production adapters for GitHub issue intake and Hermes delivery."""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast

from .adapters import (
    ClaimIdentity,
    IntakeCancellationReceipt,
    IntakeCategory,
    IntakeCompletionReceipt,
    IntakeRecord,
    NotificationReceipt,
)
from .credentials import CredentialBindings
from .errors import PolicyViolationError
from .projects import _require_digest, _require_slug, _require_text

RuntimeRunner = Callable[[tuple[str, ...], Mapping[str, str]], tuple[int, str]]

MAX_ADAPTER_OUTPUT_BYTES = 1_048_576
MAX_NOTIFICATION_BYTES = 8_192
_CLAIM_MARKER = "<!-- daidala-claim/v1 -->"
_CLAIM_RELEASE_MARKER = "<!-- daidala-claim-release/v1 -->"
_DIGEST = re.compile(r"(?<![0-9a-fA-F])([0-9a-fA-F]{64})(?![0-9a-fA-F])")
_ISSUE_ID = re.compile(r"^[1-9][0-9]{0,19}$")
_HERMES_DESTINATION = re.compile(
    r"^[a-z][a-z0-9_-]{0,63}:[^\s\x00-\x1f\x7f]{1,447}$"
)
_SAFE_ENVIRONMENT_NAMES = {
    "HOME",
    "HERMES_HOME",
    "LANG",
    "LANGUAGE",
    "LC_ALL",
    "LOGNAME",
    "PATH",
    "TERM",
    "TMPDIR",
    "USER",
    "XDG_CACHE_HOME",
    "XDG_CONFIG_HOME",
    "XDG_DATA_HOME",
    "XDG_RUNTIME_DIR",
}
_REQUIRED_SECTIONS = {
    "Category",
    "Originating experiment, test case, or source identity",
    "Expected behavior",
    "Observed behavior",
    "Redacted evidence reference and SHA-256 digest",
    "Acceptance criteria",
    "Dependencies and risk",
    "Priority",
    "Publication state",
}
_CATEGORY_LABELS = {f"daidala-si:{category.value}" for category in IntakeCategory}
_PRIORITY_LABELS = {f"daidala-si:priority-{priority}" for priority in range(1, 6)}
_READY_LABEL = "daidala-si:ready"
_CLAIMED_LABEL = "daidala-si:claimed"


@dataclass
class GitHubIssueIntakeAdapter:
    """Normalize and replay-safely claim one structured GitHub issue."""

    repository: str
    read_credential_alias: str
    write_credential_alias: str
    credential_bindings: CredentialBindings
    authorized_actors: tuple[str, ...]
    runner: RuntimeRunner = field(default_factory=lambda: run_runtime_command)
    environ: Mapping[str, str] = field(default_factory=lambda: dict(os.environ))
    clock: Callable[[], datetime] = field(default_factory=lambda: lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not re.fullmatch(
            r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}", self.repository
        ):
            raise PolicyViolationError("GitHub intake repository must be owner/repository")
        _require_slug(self.read_credential_alias, "GitHub read credential alias")
        _require_slug(self.write_credential_alias, "GitHub write credential alias")
        if self.read_credential_alias == self.write_credential_alias:
            raise PolicyViolationError("GitHub read and write credential aliases must differ")
        if (
            not isinstance(self.authorized_actors, tuple)
            or not self.authorized_actors
            or len(self.authorized_actors) > 32
        ):
            raise PolicyViolationError("GitHub intake requires authorized actors")
        for actor in self.authorized_actors:
            _require_text(actor, "GitHub authorized actor", 256)

    def fetch_ready(self, *, limit: int) -> tuple[IntakeRecord, ...]:
        return self._fetch_inventory(_READY_LABEL, limit)

    def fetch_claimed(self, *, limit: int) -> tuple[IntakeRecord, ...]:
        return self._fetch_inventory(_CLAIMED_LABEL, limit)

    def _fetch_inventory(self, label_name: str, limit: int) -> tuple[IntakeRecord, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise PolicyViolationError("GitHub issue inventory limit must be between 1 and 100")
        payload = self._run_json(
            (
                "gh",
                "issue",
                "list",
                "--repo",
                self.repository,
                "--state",
                "open",
                "--label",
                "daidala-si",
                "--label",
                label_name,
                "--limit",
                str(limit),
                "--json",
                "number",
            ),
            alias=self.read_credential_alias,
            label="GitHub issue inventory",
        )
        if not isinstance(payload, list):
            raise PolicyViolationError("GitHub issue inventory must be a JSON list")
        item_ids: list[str] = []
        for row in payload:
            if not isinstance(row, dict) or isinstance(row.get("number"), bool):
                raise PolicyViolationError("GitHub issue inventory is invalid")
            item_ids.append(str(row["number"]))
        if len(set(item_ids)) != len(item_ids):
            raise PolicyViolationError("GitHub issue inventory contains duplicate identities")
        return tuple(self.fetch(item_id) for item_id in item_ids)

    def fetch(self, item_id: str) -> IntakeRecord:
        _require_issue_id(item_id)
        issue = self._run_json(
            (
                "gh",
                "issue",
                "view",
                item_id,
                "--repo",
                self.repository,
                "--json",
                "number,url,title,body,labels,state",
            ),
            alias=self.read_credential_alias,
            label="GitHub issue",
        )
        if not isinstance(issue, dict):
            raise PolicyViolationError("GitHub issue must be a JSON object")
        return self._normalize_issue(item_id, cast(dict[str, Any], issue))

    def claim(self, item_id: str, claim: ClaimIdentity) -> IntakeRecord:
        _require_issue_id(item_id)
        if not isinstance(claim, ClaimIdentity):
            raise PolicyViolationError("GitHub claim must use a normalized claim identity")
        current = self.fetch(item_id)
        if current.claim is not None and current.claim != claim:
            raise PolicyViolationError("GitHub issue is claimed by another owner")
        if current.claim is None:
            body = (
                f"{_CLAIM_MARKER}\n"
                "```json\n"
                + json.dumps(claim.to_dict(), sort_keys=True, separators=(",", ":"))
                + "\n```"
            )
            self._run_text(
                (
                    "gh",
                    "issue",
                    "comment",
                    item_id,
                    "--repo",
                    self.repository,
                    "--body",
                    body,
                ),
                alias=self.write_credential_alias,
                label="GitHub claim comment",
            )
        if current.claim is None or not self._has_claimed_label(item_id):
            self._run_text(
                (
                    "gh",
                    "issue",
                    "edit",
                    item_id,
                    "--repo",
                    self.repository,
                    "--add-label",
                    _CLAIMED_LABEL,
                    "--remove-label",
                    _READY_LABEL,
                ),
                alias=self.write_credential_alias,
                label="GitHub claim labels",
            )
        claimed = self.fetch(item_id)
        if claimed.claim != claim:
            raise PolicyViolationError("GitHub claim did not converge on the requested identity")
        return claimed

    def release_claim(self, item_id: str, claim: ClaimIdentity) -> IntakeRecord:
        _require_issue_id(item_id)
        if not isinstance(claim, ClaimIdentity):
            raise PolicyViolationError("GitHub claim release requires a normalized claim")
        current = self.fetch(item_id)
        if current.claim is None and current.ready:
            return current
        if current.claim != claim:
            raise PolicyViolationError("GitHub claim release owner does not match")
        self._run_text(
            (
                "gh",
                "issue",
                "edit",
                item_id,
                "--repo",
                self.repository,
                "--add-label",
                _READY_LABEL,
                "--remove-label",
                _CLAIMED_LABEL,
            ),
            alias=self.write_credential_alias,
            label="GitHub claim release labels",
        )
        body = (
            f"{_CLAIM_RELEASE_MARKER}\n"
            "```json\n"
            + json.dumps(claim.to_dict(), sort_keys=True, separators=(",", ":"))
            + "\n```"
        )
        self._run_text(
            (
                "gh",
                "issue",
                "comment",
                item_id,
                "--repo",
                self.repository,
                "--body",
                body,
            ),
            alias=self.write_credential_alias,
            label="GitHub claim release comment",
        )
        released = self.fetch(item_id)
        if released.claim is not None or not released.ready:
            raise PolicyViolationError("GitHub claim release did not converge")
        return released

    def complete(self, item_id: str, cycle_id: str) -> IntakeCompletionReceipt:
        _require_issue_id(item_id)
        _require_text(cycle_id, "completion cycle ID", 256)
        issue, labels, claim = self._completion_issue(item_id)
        self._validate_completion_state(issue, labels, claim, cycle_id)
        state = issue["state"]
        reason = issue["stateReason"]
        if state == "OPEN":
            self._run_text(
                (
                    "gh",
                    "issue",
                    "close",
                    item_id,
                    "--repo",
                    self.repository,
                    "--reason",
                    "completed",
                ),
                alias=self.write_credential_alias,
                label="GitHub issue completion",
            )
        elif state != "CLOSED" or reason != "COMPLETED":
            raise PolicyViolationError("GitHub issue is not eligible for completed closure")
        if _CLAIMED_LABEL in labels:
            self._run_text(
                (
                    "gh",
                    "issue",
                    "edit",
                    item_id,
                    "--repo",
                    self.repository,
                    "--remove-label",
                    _CLAIMED_LABEL,
                ),
                alias=self.write_credential_alias,
                label="GitHub completion claim release",
            )
        completed, final_labels, final_claim = self._completion_issue(item_id)
        if (
            completed["state"] != "CLOSED"
            or completed["stateReason"] != "COMPLETED"
            or _CLAIMED_LABEL in final_labels
            or final_claim is None
            or final_claim.claimant != cycle_id
        ):
            raise PolicyViolationError("GitHub issue completion did not converge")
        return IntakeCompletionReceipt(
            adapter="github-issues",
            item_id=item_id,
            cycle_id=cycle_id,
            source_url=f"https://github.com/{self.repository}/issues/{item_id}",
            state="closed",
            state_reason="completed",
            claim_released=True,
            completed_at=self.clock(),
        )

    def validate_completion(self, item_id: str, cycle_id: str) -> None:
        _require_issue_id(item_id)
        _require_text(cycle_id, "completion cycle ID", 256)
        issue, labels, claim = self._completion_issue(item_id)
        self._validate_completion_state(issue, labels, claim, cycle_id)

    def cancel(
        self, item_id: str, cycle_id: str, reason_digest: str
    ) -> IntakeCancellationReceipt:
        _require_issue_id(item_id)
        _require_text(cycle_id, "cancellation cycle ID", 256)
        _require_digest(reason_digest, "cancellation reason digest")
        issue, labels, claim = self._completion_issue(item_id)
        self._validate_cancellation_state(issue, labels, claim, cycle_id)
        if issue["state"] == "OPEN":
            self._run_text(
                (
                    "gh",
                    "issue",
                    "close",
                    item_id,
                    "--repo",
                    self.repository,
                    "--reason",
                    "not planned",
                ),
                alias=self.write_credential_alias,
                label="GitHub issue cancellation",
            )
        removable = tuple(
            label for label in (_CLAIMED_LABEL, _READY_LABEL) if label in labels
        )
        if removable:
            command = (
                "gh",
                "issue",
                "edit",
                item_id,
                "--repo",
                self.repository,
            ) + tuple(part for label in removable for part in ("--remove-label", label))
            self._run_text(
                command,
                alias=self.write_credential_alias,
                label="GitHub cancellation claim release",
            )
        canceled, final_labels, final_claim = self._completion_issue(item_id)
        if (
            canceled["state"] != "CLOSED"
            or canceled["stateReason"] != "NOT_PLANNED"
            or _CLAIMED_LABEL in final_labels
            or _READY_LABEL in final_labels
            or final_claim is None
            or final_claim.claimant != cycle_id
        ):
            raise PolicyViolationError("GitHub issue cancellation did not converge")
        return IntakeCancellationReceipt(
            adapter="github-issues",
            item_id=item_id,
            cycle_id=cycle_id,
            reason_digest=reason_digest,
            source_url=f"https://github.com/{self.repository}/issues/{item_id}",
            state="closed",
            state_reason="not_planned",
            claim_released=True,
            canceled_at=self.clock(),
        )

    def validate_cancellation(self, item_id: str, cycle_id: str) -> None:
        _require_issue_id(item_id)
        _require_text(cycle_id, "cancellation cycle ID", 256)
        issue, labels, claim = self._completion_issue(item_id)
        self._validate_cancellation_state(issue, labels, claim, cycle_id)

    @staticmethod
    def _validate_completion_state(
        issue: dict[str, Any],
        labels: set[str],
        claim: ClaimIdentity | None,
        cycle_id: str,
    ) -> None:
        if claim is None or claim.claimant != cycle_id:
            raise PolicyViolationError("GitHub completion claim owner does not match cycle")
        if issue["state"] == "OPEN" and _CLAIMED_LABEL not in labels:
            raise PolicyViolationError("open GitHub completion issue must retain its claim")
        if issue["state"] == "OPEN":
            return
        if issue["state"] != "CLOSED" or issue["stateReason"] != "COMPLETED":
            raise PolicyViolationError("GitHub issue is not eligible for completed closure")

    @staticmethod
    def _validate_cancellation_state(
        issue: dict[str, Any],
        labels: set[str],
        claim: ClaimIdentity | None,
        cycle_id: str,
    ) -> None:
        if claim is None or claim.claimant != cycle_id:
            raise PolicyViolationError("GitHub cancellation claim owner does not match cycle")
        if issue["state"] == "OPEN":
            if _CLAIMED_LABEL not in labels:
                raise PolicyViolationError("open GitHub cancellation issue must retain its claim")
            return
        if issue["state"] != "CLOSED" or issue["stateReason"] != "NOT_PLANNED":
            raise PolicyViolationError("GitHub issue is not eligible for cancellation")
        if _CLAIMED_LABEL in labels or _READY_LABEL in labels:
            raise PolicyViolationError("closed GitHub cancellation issue retains active labels")

    def _completion_issue(
        self, item_id: str
    ) -> tuple[dict[str, Any], set[str], ClaimIdentity | None]:
        issue = self._run_json(
            (
                "gh",
                "api",
                "--method",
                "GET",
                f"repos/{self.repository}/issues/{item_id}",
            ),
            alias=self.read_credential_alias,
            label="GitHub completion issue",
        )
        fields = {"number", "html_url", "labels", "state", "state_reason"}
        if not isinstance(issue, dict) or not fields.issubset(issue):
            raise PolicyViolationError("GitHub completion issue fields are invalid")
        if str(issue["number"]) != item_id:
            raise PolicyViolationError("GitHub completion issue number is invalid")
        expected_url = f"https://github.com/{self.repository}/issues/{item_id}"
        if issue["html_url"] != expected_url:
            raise PolicyViolationError("GitHub completion issue URL is invalid")
        labels = _parse_labels(issue["labels"])
        if "daidala-si" not in labels:
            raise PolicyViolationError("GitHub completion issue is missing the base label")
        state = issue["state"]
        state_reason = issue["state_reason"]
        if not isinstance(state, str) or not (
            state_reason is None or isinstance(state_reason, str)
        ):
            raise PolicyViolationError("GitHub completion issue state is invalid")
        normalized_issue = {
            "number": issue["number"],
            "url": issue["html_url"],
            "labels": issue["labels"],
            "state": state.upper(),
            "stateReason": None if state_reason is None else state_reason.upper(),
        }
        claim = _claim_from_comments(
            self._api_pages(item_id, "comments"), self.authorized_actors
        )
        return normalized_issue, labels, claim

    def _normalize_issue(self, item_id: str, issue: dict[str, Any]) -> IntakeRecord:
        expected_fields = {"number", "url", "title", "body", "labels", "state"}
        if set(issue) != expected_fields:
            raise PolicyViolationError("GitHub issue fields are invalid")
        if str(issue["number"]) != item_id:
            raise PolicyViolationError("GitHub issue number does not match the requested item")
        expected_url = f"https://github.com/{self.repository}/issues/{item_id}"
        if issue["url"] != expected_url:
            raise PolicyViolationError("GitHub issue URL does not match the trusted repository")
        if issue["state"] != "OPEN":
            raise PolicyViolationError("GitHub issue must be open for admission")
        if not isinstance(issue["title"], str) or not isinstance(issue["body"], str):
            raise PolicyViolationError("GitHub issue title and body must be strings")
        labels = _parse_labels(issue["labels"])
        if "daidala-si" not in labels:
            raise PolicyViolationError("GitHub issue is missing the Daidala base label")
        category_labels = labels & _CATEGORY_LABELS
        priority_labels = labels & _PRIORITY_LABELS
        if len(category_labels) != 1:
            raise PolicyViolationError("GitHub issue must have exactly one Daidala category label")
        if len(priority_labels) != 1:
            raise PolicyViolationError("GitHub issue must have exactly one Daidala priority label")
        sections = _parse_issue_sections(issue["body"])
        category = IntakeCategory(sections["Category"])
        priority_text = sections["Priority"]
        if not re.fullmatch(r"[1-5]", priority_text):
            raise PolicyViolationError("GitHub issue priority field is invalid")
        priority = int(priority_text)
        if category_labels != {f"daidala-si:{category.value}"}:
            raise PolicyViolationError("GitHub issue category field and label disagree")
        if priority_labels != {f"daidala-si:priority-{priority}"}:
            raise PolicyViolationError("GitHub issue priority field and label disagree")
        if sections["Publication state"] not in {"local", "pending", "published"}:
            raise PolicyViolationError("GitHub issue publication state is invalid")
        digests = tuple(
            digest.lower()
            for digest in _DIGEST.findall(
                sections["Redacted evidence reference and SHA-256 digest"]
            )
        )
        if len(digests) != 1:
            raise PolicyViolationError(
                "GitHub issue evidence must contain exactly one SHA-256 digest"
            )
        acceptance = _parse_list(sections["Acceptance criteria"], "acceptance criteria")
        events = self._api_pages(item_id, "events")
        admission_actor = _ready_actor(events)
        comments = self._api_pages(item_id, "comments")
        claim = _claim_from_comments(comments, self.authorized_actors)
        if _CLAIMED_LABEL in labels and claim is None:
            raise PolicyViolationError("GitHub claimed label has no valid claim record")
        if claim is not None and not ({_READY_LABEL, _CLAIMED_LABEL} & labels):
            raise PolicyViolationError("GitHub claim has no ready or claimed label")
        ready = _READY_LABEL in labels or claim is not None
        goal = (
            f"{issue['title'].strip()}\n\n"
            f"Expected behavior: {sections['Expected behavior']}\n\n"
            f"Observed behavior: {sections['Observed behavior']}"
        )
        return IntakeRecord(
            adapter="github-issues",
            item_id=item_id,
            source_url=expected_url,
            category=category,
            priority=priority,
            goal=goal,
            acceptance_criteria=acceptance,
            evidence_digests=digests,
            dependencies=(),
            risk=sections["Dependencies and risk"],
            admission_actor=admission_actor,
            ready=ready,
            claim=claim,
        )

    def _has_claimed_label(self, item_id: str) -> bool:
        issue = self._run_json(
            (
                "gh",
                "issue",
                "view",
                item_id,
                "--repo",
                self.repository,
                "--json",
                "labels",
            ),
            alias=self.read_credential_alias,
            label="GitHub issue labels",
        )
        if not isinstance(issue, dict) or set(issue) != {"labels"}:
            raise PolicyViolationError("GitHub issue labels response is invalid")
        return _CLAIMED_LABEL in _parse_labels(issue["labels"])

    def _api_pages(self, item_id: str, resource: str) -> list[dict[str, Any]]:
        output = self._run_text(
            (
                "gh",
                "api",
                "--paginate",
                f"repos/{self.repository}/issues/{item_id}/{resource}?per_page=100",
                "--jq",
                ".[]",
            ),
            alias=self.read_credential_alias,
            label=f"GitHub issue {resource}",
        )
        rows: list[dict[str, Any]] = []
        for line in output.splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise PolicyViolationError(
                    f"GitHub issue {resource} returned invalid paginated JSON"
                ) from error
            if not isinstance(row, dict):
                raise PolicyViolationError(f"GitHub issue {resource} row is invalid")
            rows.append(cast(dict[str, Any], row))
        return rows

    def _run_json(self, command: tuple[str, ...], *, alias: str, label: str) -> Any:
        output = self._run_text(command, alias=alias, label=label)
        try:
            return json.loads(output)
        except json.JSONDecodeError as error:
            raise PolicyViolationError(f"{label} returned invalid JSON") from error

    def _run_text(self, command: tuple[str, ...], *, alias: str, label: str) -> str:
        token = self.credential_bindings.resolve(alias, self.environ)
        environment = safe_runtime_environment(self.environ)
        if "GH_HOST" in self.environ:
            environment["GH_HOST"] = self.environ["GH_HOST"]
        environment["GH_TOKEN"] = token
        code, output = self.runner(command, environment)
        _validate_runner_output(code, output, label)
        return output


@dataclass
class HermesGatewayNotificationAdapter:
    """Deliver one event through an exact profile-local Hermes destination."""

    profile: str
    target_alias: str
    destination: str
    runner: RuntimeRunner = field(default_factory=lambda: run_runtime_command)
    environ: Mapping[str, str] = field(default_factory=lambda: dict(os.environ))
    clock: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        _require_slug(self.profile, "notification profile")
        _require_slug(self.target_alias, "notification target alias")
        if not isinstance(self.destination, str) or not _HERMES_DESTINATION.fullmatch(
            self.destination
        ):
            raise PolicyViolationError(
                "notification destination is not an explicit non-home Hermes send target"
            )

    def deliver(self, payload: dict[str, object]) -> NotificationReceipt:
        if not isinstance(payload, dict):
            raise PolicyViolationError("notification payload must be an object")
        event_id = payload.get("event_id")
        if not isinstance(event_id, str):
            raise PolicyViolationError("notification payload requires an event ID")
        _require_text(event_id, "notification event ID", 512)
        message = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if len(message.encode("utf-8")) > MAX_NOTIFICATION_BYTES:
            raise PolicyViolationError("notification payload exceeds its byte bound")
        code, output = self.runner(
            (
                "hermes",
                "-p",
                self.profile,
                "send",
                "--to",
                self.destination,
                message,
                "--json",
            ),
            safe_runtime_environment(self.environ),
        )
        _validate_runner_output(code, output, "Hermes notification delivery")
        try:
            result = json.loads(output)
        except json.JSONDecodeError as error:
            raise PolicyViolationError(
                "Hermes notification delivery returned invalid JSON"
            ) from error
        if not isinstance(result, dict) or result.get("success") is not True:
            raise PolicyViolationError("Hermes notification delivery did not succeed")
        platform = result.get("platform")
        message_id = result.get("message_id")
        if not isinstance(platform, str) or not platform:
            raise PolicyViolationError("Hermes notification receipt omitted platform")
        if isinstance(message_id, bool) or not isinstance(message_id, (str, int)):
            raise PolicyViolationError("Hermes notification receipt omitted message ID")
        receipt_id = f"{platform}:{message_id}"
        return NotificationReceipt(
            event_id=event_id,
            adapter="hermes-gateway",
            target_alias=self.target_alias,
            receipt_id=receipt_id,
            delivered_at=self.clock(),
        )


def _parse_labels(raw: Any) -> set[str]:
    if not isinstance(raw, list):
        raise PolicyViolationError("GitHub issue labels must be a list")
    labels: set[str] = set()
    for row in raw:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("name"), str)
            or not row["name"]
        ):
            raise PolicyViolationError("GitHub issue label entry is invalid")
        labels.add(row["name"])
    return labels


def _parse_issue_sections(body: str) -> dict[str, str]:
    if len(body.encode("utf-8")) > MAX_ADAPTER_OUTPUT_BYTES:
        raise PolicyViolationError("GitHub issue body exceeds its byte bound")
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in body.splitlines():
        if line.startswith("### "):
            heading = line[4:].strip()
            if heading in sections:
                raise PolicyViolationError("GitHub issue body contains a duplicate section")
            sections[heading] = []
            current = heading
        elif current is not None:
            sections[current].append(line)
    if set(sections) != _REQUIRED_SECTIONS:
        raise PolicyViolationError("GitHub issue body sections are invalid")
    normalized = {heading: "\n".join(lines).strip() for heading, lines in sections.items()}
    if any(not value or value == "_No response_" for value in normalized.values()):
        raise PolicyViolationError("GitHub issue body contains an empty required section")
    return normalized


def _parse_list(value: str, label: str) -> tuple[str, ...]:
    rows: list[str] = []
    for line in value.splitlines():
        text = re.sub(r"^\s*(?:[-*]|\d+[.)])\s+", "", line).strip()
        if text:
            rows.append(text)
    if not rows:
        raise PolicyViolationError(f"GitHub issue {label} is empty")
    return tuple(rows)


def _ready_actor(events: list[dict[str, Any]]) -> str:
    actors: list[str] = []
    for event in events:
        label = event.get("label")
        actor = event.get("actor")
        if (
            event.get("event") == "labeled"
            and isinstance(label, dict)
            and label.get("name") == _READY_LABEL
            and isinstance(actor, dict)
            and isinstance(actor.get("login"), str)
            and actor["login"]
        ):
            actors.append(actor["login"])
    if not actors:
        raise PolicyViolationError("GitHub issue ready label actor is unavailable")
    return actors[-1]


def _claim_from_comments(
    comments: list[dict[str, Any]], authorized_actors: tuple[str, ...]
) -> ClaimIdentity | None:
    active: ClaimIdentity | None = None
    for comment in comments:
        body = comment.get("body")
        if not isinstance(body, str):
            continue
        marker = next(
            (
                row
                for row in (_CLAIM_MARKER, _CLAIM_RELEASE_MARKER)
                if row in body
            ),
            None,
        )
        if marker is None:
            continue
        user = comment.get("user")
        actor = user.get("login") if isinstance(user, dict) else None
        if actor not in authorized_actors:
            raise PolicyViolationError("GitHub claim comment actor is not authorized")
        match = re.fullmatch(
            rf"{re.escape(marker)}\n```json\n(.+)\n```", body, re.DOTALL
        )
        if match is None:
            raise PolicyViolationError("GitHub claim comment is malformed")
        try:
            raw = json.loads(match.group(1))
        except json.JSONDecodeError as error:
            raise PolicyViolationError("GitHub claim comment contains invalid JSON") from error
        claim = ClaimIdentity.from_dict(raw)
        if marker == _CLAIM_MARKER:
            if active is not None and active != claim:
                raise PolicyViolationError("GitHub issue contains conflicting claims")
            active = claim
        else:
            if active != claim:
                raise PolicyViolationError("GitHub claim release does not match active claim")
            active = None
    return active


def safe_runtime_environment(environ: Mapping[str, str]) -> dict[str, str]:
    return {
        name: value
        for name, value in environ.items()
        if name in _SAFE_ENVIRONMENT_NAMES
    }


def _validate_runner_output(code: int, output: str, label: str) -> None:
    if isinstance(code, bool) or not isinstance(code, int):
        raise PolicyViolationError(f"{label} runner returned an invalid exit code")
    if not isinstance(output, str):
        raise PolicyViolationError(f"{label} runner returned invalid output")
    if len(output.encode("utf-8")) > MAX_ADAPTER_OUTPUT_BYTES:
        raise PolicyViolationError(f"{label} output exceeds its byte bound")
    if code != 0:
        raise PolicyViolationError(f"{label} failed with exit code {code}")


def _require_issue_id(item_id: str) -> None:
    if not isinstance(item_id, str) or not _ISSUE_ID.fullmatch(item_id):
        raise PolicyViolationError("GitHub issue ID must be a positive decimal number")


def run_runtime_command(
    command: tuple[str, ...], environment: Mapping[str, str]
) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            env=dict(environment),
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return 127, "adapter command unavailable"
    output = completed.stdout
    if completed.stderr:
        output += completed.stderr
    return completed.returncode, output.strip()
