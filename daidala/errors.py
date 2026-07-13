"""Wingstaff policy-ledger errors."""


class WorkflowError(ValueError):
    """Base class for deterministic Wingstaff policy failures."""


class PolicyViolationError(WorkflowError):
    """Raised when policy-ledger data or an update violates an invariant."""
