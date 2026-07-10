"""Workflow-state validation and transition errors."""


class WorkflowError(ValueError):
    """Base class for deterministic workflow contract failures."""


class InvalidWorkflowError(WorkflowError):
    """Raised when workflow data violates a state invariant."""


class InvalidTransitionError(WorkflowError):
    """Raised when an event is invalid for the current workflow state."""
