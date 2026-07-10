"""Directory-plugin entry point for Git-based Hermes installations."""

if __package__:
    from .wingstaff import register
else:
    from wingstaff import register

__all__ = ["register"]
