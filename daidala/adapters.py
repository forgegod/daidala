"""Normalized, side-effect-free adapter records for self-improvement intake."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from .errors import PolicyViolationError
from .projects import _require_digest, _require_int, _require_slug, _require_text


class IntakeCategory(StrEnum):
    REGRESSION = "regression"
    IMPROVEMENT = "improvement"
    COMPATIBILITY = "compatibility"
    SKILL_GAP = "skill-gap"
    RESEARCH_CANDIDATE = "research-candidate"


class PublicationState(StrEnum):
    LOCAL = "local"
    PENDING = "pending"
    PUBLISHED = "published"


@dataclass(frozen=True)
class ClaimIdentity:
    claimant: str
    claimed_at: datetime
    lease_expires_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.claimant, "claimant identity", 256)
        for value, label in (
            (self.claimed_at, "claim timestamp"),
            (self.lease_expires_at, "claim lease expiry"),
        ):
            if not isinstance(value, datetime) or value.tzinfo is None:
                raise PolicyViolationError(f"{label} must be timezone-aware")
        if self.lease_expires_at <= self.claimed_at:
            raise PolicyViolationError("claim lease must expire after its claim timestamp")

    def to_dict(self) -> dict[str, str]:
        return {
            "claimant": self.claimant,
            "claimed_at": self.claimed_at.isoformat(),
            "lease_expires_at": self.lease_expires_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, raw: Any) -> ClaimIdentity:
        _require_fields(raw, {"claimant", "claimed_at", "lease_expires_at"}, "claim")
        try:
            claimed_at = datetime.fromisoformat(raw["claimed_at"])
            lease_expires_at = datetime.fromisoformat(raw["lease_expires_at"])
        except (TypeError, ValueError) as error:
            raise PolicyViolationError("claim timestamps must be ISO-8601 strings") from error
        return cls(raw["claimant"], claimed_at, lease_expires_at)


@dataclass(frozen=True)
class IntakeRecord:
    adapter: str
    item_id: str
    source_url: str | None
    category: IntakeCategory
    priority: int
    goal: str
    acceptance_criteria: tuple[str, ...]
    evidence_digests: tuple[str, ...]
    dependencies: tuple[str, ...]
    risk: str
    admission_actor: str
    ready: bool
    claim: ClaimIdentity | None = None

    def __post_init__(self) -> None:
        _require_slug(self.adapter, "intake adapter")
        _require_text(self.item_id, "intake item ID", 256)
        if self.source_url is not None:
            _require_text(self.source_url, "intake source URL", 1_024)
            if not self.source_url.startswith("https://"):
                raise PolicyViolationError("intake source URL must use HTTPS")
        if not isinstance(self.category, IntakeCategory):
            raise PolicyViolationError("intake category is invalid")
        _require_int(self.priority, "intake priority", 1, 5)
        _require_text(self.goal, "intake goal", 4_000)
        _require_nonempty_text_tuple(self.acceptance_criteria, "acceptance criteria", 32)
        if not isinstance(self.evidence_digests, tuple) or len(self.evidence_digests) > 32:
            raise PolicyViolationError("intake evidence must contain at most 32 digests")
        for digest in self.evidence_digests:
            _require_digest(digest, "intake evidence digest")
        if not isinstance(self.dependencies, tuple) or len(self.dependencies) > 32:
            raise PolicyViolationError("intake dependencies must contain at most 32 identities")
        for dependency in self.dependencies:
            _require_text(dependency, "intake dependency", 256)
        _require_text(self.risk, "intake risk", 2_000)
        _require_text(self.admission_actor, "intake admission actor", 256)
        if not isinstance(self.ready, bool):
            raise PolicyViolationError("intake readiness must be a boolean")
        if self.claim is not None and not self.ready:
            raise PolicyViolationError("an unready intake item cannot be claimed")

    def to_dict(self) -> dict[str, object]:
        return {
            "adapter": self.adapter,
            "item_id": self.item_id,
            "source_url": self.source_url,
            "category": self.category.value,
            "priority": self.priority,
            "goal": self.goal,
            "acceptance_criteria": list(self.acceptance_criteria),
            "evidence_digests": list(self.evidence_digests),
            "dependencies": list(self.dependencies),
            "risk": self.risk,
            "admission_actor": self.admission_actor,
            "ready": self.ready,
            "claim": None if self.claim is None else self.claim.to_dict(),
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    @classmethod
    def from_dict(cls, raw: Any) -> IntakeRecord:
        fields = {
            "adapter",
            "item_id",
            "source_url",
            "category",
            "priority",
            "goal",
            "acceptance_criteria",
            "evidence_digests",
            "dependencies",
            "risk",
            "admission_actor",
            "ready",
            "claim",
        }
        _require_fields(raw, fields, "intake record")
        try:
            category = IntakeCategory(raw["category"])
        except (TypeError, ValueError) as error:
            raise PolicyViolationError("intake category is invalid") from error
        return cls(
            adapter=raw["adapter"],
            item_id=raw["item_id"],
            source_url=raw["source_url"],
            category=category,
            priority=raw["priority"],
            goal=raw["goal"],
            acceptance_criteria=_string_tuple(raw["acceptance_criteria"], "acceptance criteria"),
            evidence_digests=_string_tuple(raw["evidence_digests"], "intake evidence"),
            dependencies=_string_tuple(raw["dependencies"], "intake dependencies"),
            risk=raw["risk"],
            admission_actor=raw["admission_actor"],
            ready=raw["ready"],
            claim=None if raw["claim"] is None else ClaimIdentity.from_dict(raw["claim"]),
        )


@dataclass(frozen=True)
class FindingRecord:
    finding_id: str
    project_id: str
    category: IntakeCategory
    title: str
    evidence_digest: str
    acceptance_criteria: tuple[str, ...]
    publication_state: PublicationState
    remote_identity: str | None = None
    remote_url: str | None = None

    def __post_init__(self) -> None:
        _require_slug(self.finding_id, "finding ID")
        _require_slug(self.project_id, "finding project ID")
        if not isinstance(self.category, IntakeCategory):
            raise PolicyViolationError("finding category is invalid")
        _require_text(self.title, "finding title", 256)
        _require_digest(self.evidence_digest, "finding evidence digest")
        expected_identity = stable_finding_id(
            self.project_id, self.category, self.title, self.evidence_digest
        )
        if self.finding_id != expected_identity:
            raise PolicyViolationError("finding ID does not match its canonical inputs")
        _require_nonempty_text_tuple(self.acceptance_criteria, "finding acceptance criteria", 32)
        if not isinstance(self.publication_state, PublicationState):
            raise PolicyViolationError("finding publication state is invalid")
        published = self.publication_state is PublicationState.PUBLISHED
        if published and (self.remote_identity is None or self.remote_url is None):
            raise PolicyViolationError(
                "published findings require both a returned remote identity and URL"
            )
        if not published and (self.remote_identity is not None or self.remote_url is not None):
            raise PolicyViolationError("unpublished findings cannot claim remote identity")
        if self.remote_identity is not None:
            _require_text(self.remote_identity, "finding remote identity", 256)
        if self.remote_url is not None:
            _require_text(self.remote_url, "finding remote URL", 1_024)
            if not self.remote_url.startswith("https://"):
                raise PolicyViolationError("finding remote URL must use HTTPS")

    def to_dict(self) -> dict[str, object]:
        return {
            "finding_id": self.finding_id,
            "project_id": self.project_id,
            "category": self.category.value,
            "title": self.title,
            "evidence_digest": self.evidence_digest,
            "acceptance_criteria": list(self.acceptance_criteria),
            "publication_state": self.publication_state.value,
            "remote_identity": self.remote_identity,
            "remote_url": self.remote_url,
        }

    @classmethod
    def from_dict(cls, raw: Any) -> FindingRecord:
        fields = {
            "finding_id",
            "project_id",
            "category",
            "title",
            "evidence_digest",
            "acceptance_criteria",
            "publication_state",
            "remote_identity",
            "remote_url",
        }
        _require_fields(raw, fields, "finding record")
        try:
            category = IntakeCategory(raw["category"])
            publication_state = PublicationState(raw["publication_state"])
        except (TypeError, ValueError) as error:
            raise PolicyViolationError("finding enum value is invalid") from error
        return cls(
            finding_id=raw["finding_id"],
            project_id=raw["project_id"],
            category=category,
            title=raw["title"],
            evidence_digest=raw["evidence_digest"],
            acceptance_criteria=_string_tuple(
                raw["acceptance_criteria"], "finding acceptance criteria"
            ),
            publication_state=publication_state,
            remote_identity=raw["remote_identity"],
            remote_url=raw["remote_url"],
        )


@dataclass(frozen=True)
class NotificationReceipt:
    event_id: str
    adapter: str
    target_alias: str
    receipt_id: str
    delivered_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.event_id, "notification event ID", 512)
        _require_slug(self.adapter, "notification adapter")
        _require_slug(self.target_alias, "notification target alias")
        _require_text(self.receipt_id, "notification receipt ID", 256)
        if not isinstance(self.delivered_at, datetime) or self.delivered_at.tzinfo is None:
            raise PolicyViolationError("notification delivery time must be timezone-aware")

    def to_dict(self) -> dict[str, str]:
        return {
            "event_id": self.event_id,
            "adapter": self.adapter,
            "target_alias": self.target_alias,
            "receipt_id": self.receipt_id,
            "delivered_at": self.delivered_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, raw: Any) -> NotificationReceipt:
        _require_fields(
            raw,
            {"event_id", "adapter", "target_alias", "receipt_id", "delivered_at"},
            "notification receipt",
        )
        try:
            delivered_at = datetime.fromisoformat(raw["delivered_at"])
        except (TypeError, ValueError) as error:
            raise PolicyViolationError(
                "notification delivery time must be an ISO-8601 string"
            ) from error
        return cls(
            raw["event_id"],
            raw["adapter"],
            raw["target_alias"],
            raw["receipt_id"],
            delivered_at,
        )


@dataclass(frozen=True)
class IntakeCompletionReceipt:
    adapter: str
    item_id: str
    cycle_id: str
    source_url: str
    state: str
    state_reason: str
    claim_released: bool
    completed_at: datetime

    def __post_init__(self) -> None:
        _require_slug(self.adapter, "completion adapter")
        _require_text(self.item_id, "completion item ID", 256)
        _require_text(self.cycle_id, "completion cycle ID", 256)
        _require_text(self.source_url, "completion source URL", 1_024)
        if not self.source_url.startswith("https://"):
            raise PolicyViolationError("completion source URL must use HTTPS")
        if self.state != "closed" or self.state_reason != "completed":
            raise PolicyViolationError("completion receipt must close the item as completed")
        if self.claim_released is not True:
            raise PolicyViolationError("completion receipt must release the claim")
        if not isinstance(self.completed_at, datetime) or self.completed_at.tzinfo is None:
            raise PolicyViolationError("completion timestamp must be timezone-aware")

    def to_dict(self) -> dict[str, object]:
        return {
            "adapter": self.adapter,
            "item_id": self.item_id,
            "cycle_id": self.cycle_id,
            "source_url": self.source_url,
            "state": self.state,
            "state_reason": self.state_reason,
            "claim_released": self.claim_released,
            "completed_at": self.completed_at.isoformat(),
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    @classmethod
    def from_dict(cls, raw: Any) -> IntakeCompletionReceipt:
        _require_fields(
            raw,
            {
                "adapter",
                "item_id",
                "cycle_id",
                "source_url",
                "state",
                "state_reason",
                "claim_released",
                "completed_at",
            },
            "intake completion receipt",
        )
        try:
            completed_at = datetime.fromisoformat(raw["completed_at"])
        except (TypeError, ValueError) as error:
            raise PolicyViolationError(
                "completion timestamp must be an ISO-8601 string"
            ) from error
        return cls(
            adapter=raw["adapter"],
            item_id=raw["item_id"],
            cycle_id=raw["cycle_id"],
            source_url=raw["source_url"],
            state=raw["state"],
            state_reason=raw["state_reason"],
            claim_released=raw["claim_released"],
            completed_at=completed_at,
        )


class IntakeAdapter(Protocol):
    def fetch_ready(self, *, limit: int) -> tuple[IntakeRecord, ...]: ...

    def fetch_claimed(self, *, limit: int) -> tuple[IntakeRecord, ...]: ...

    def claim(self, item_id: str, claim: ClaimIdentity) -> IntakeRecord: ...

    def release_claim(self, item_id: str, claim: ClaimIdentity) -> IntakeRecord: ...

    def validate_completion(self, item_id: str, cycle_id: str) -> None: ...

    def complete(self, item_id: str, cycle_id: str) -> IntakeCompletionReceipt: ...


class FindingsAdapter(Protocol):
    def synchronize(self, finding: FindingRecord) -> FindingRecord: ...


class NotificationAdapter(Protocol):
    def deliver(self, payload: dict[str, object]) -> NotificationReceipt: ...


def stable_finding_id(
    project_id: str,
    category: IntakeCategory,
    title: str,
    evidence_digest: str,
) -> str:
    _require_slug(project_id, "finding project ID")
    if not isinstance(category, IntakeCategory):
        raise PolicyViolationError("finding category is invalid")
    _require_text(title, "finding title", 256)
    _require_digest(evidence_digest, "finding evidence digest")
    payload = {
        "project_id": project_id,
        "category": category.value,
        "title": title.strip(),
        "evidence_digest": evidence_digest,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"finding-{hashlib.sha256(canonical).hexdigest()}"


def _require_nonempty_text_tuple(values: tuple[str, ...], label: str, maximum: int) -> None:
    if not isinstance(values, tuple) or not 1 <= len(values) <= maximum:
        raise PolicyViolationError(f"{label} must contain 1-{maximum} values")
    for value in values:
        _require_text(value, label, 1_000)


def _require_fields(raw: Any, expected: set[str], label: str) -> None:
    if not isinstance(raw, dict):
        raise PolicyViolationError(f"{label} must be an object")
    actual = set(raw)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise PolicyViolationError(
            f"{label} fields mismatch; missing={missing!r}, unknown={unknown!r}"
        )


def _string_tuple(raw: Any, label: str) -> tuple[str, ...]:
    if not isinstance(raw, list) or any(not isinstance(value, str) for value in raw):
        raise PolicyViolationError(f"{label} must be a list of strings")
    return tuple(raw)
