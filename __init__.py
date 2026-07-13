"""Directory-plugin entry point for Git-based Hermes installations."""

import sys

if __package__:
    from . import daidala as _implementation

    sys.modules.setdefault("daidala", _implementation)
    register = _implementation.register
else:
    from daidala import register

__all__ = ["register"]
