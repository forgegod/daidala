"""Directory-plugin entry point for Git-based Hermes installations."""

if __package__:
    from .daidala import register
else:
    from daidala import register

__all__ = ["register"]
