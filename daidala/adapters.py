"""Normalized, side-effect-free adapter records for self-improvement intake."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

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


@dataclass(frozen=True)
class NotificationReceipt:
    adapter: str
    target_alias: str
    receipt_id: str
    delivered_at: datetime

    def __post_init__(self) -> None:
        _require_slug(self.adapter, "notification adapter")
        _require_slug(self.target_alias, "notification target alias")
        _require_text(self.receipt_id, "notification receipt ID", 256)
        if not isinstance(self.delivered_at, datetime) or self.delivered_at.tzinfo is None:
            raise PolicyViolationError("notification delivery time must be timezone-aware")


class IntakeAdapter(Protocol):
    def fetch_ready(self, *, limit: int) -> tuple[IntakeRecord, ...]: ...


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
