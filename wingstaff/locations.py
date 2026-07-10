"""Resolve the profile-aware data root for Wingstaff runtime files.

Wingstaff never hard-codes ``~/.hermes``. The data root resolves in this order:

1. an explicit argument (used by tests);
2. the active Hermes profile's data root, exposed through the plugin context
   when Hermes provides one;
3. the ``HERMES_HOME`` environment variable that Hermes sets per profile;
4. a per-profile default discovered through the supported Hermes path helper
   ``hermes_cli.config.get_hermes_home`` (only if the dependency is present
   in the running host);
5. otherwise the function refuses to guess — the operator must set
   ``HERMES_HOME`` or pass a root explicitly.
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path

ENV_OVERRIDE = "HERMES_HOME"
PLUGIN_DATA_DIR_ATTR = "data_dir"


class DataRootError(RuntimeError):
    """Raised when the profile-aware data root cannot be resolved."""


def resolve_data_root(
    *,
    env: dict[str, str] | None = None,
    context: object | None = None,
    explicit: Path | None = None,
) -> Path:
    """Return the directory under which Wingstaff keeps durable state.

    ``env`` defaults to :data:`os.environ` and is exposed for tests. ``context``
    is the optional Hermes plugin context whose ``data_dir`` attribute
    resolves the data root for the active profile.
    """
    if explicit is not None:
        return Path(explicit).expanduser().resolve()

    if context is not None:
        candidate = getattr(context, PLUGIN_DATA_DIR_ATTR, None)
        if isinstance(candidate, (str, Path)) and str(candidate).strip():
            return Path(candidate).expanduser().resolve()

    environ = env if env is not None else dict(os.environ)
    env_root = environ.get(ENV_OVERRIDE)
    if env_root and env_root.strip():
        return Path(env_root).expanduser().resolve()

    helper = _hermes_home_helper()
    if helper is not None:
        return helper

    raise DataRootError(
        "cannot resolve Wingstaff data root: pass an explicit root, set "
        f"{ENV_OVERRIDE}, or install hermes-cli to use its path helper"
    )


def _hermes_home_helper() -> Path | None:
    """Return Hermes' canonical home directory if its config helper is importable."""
    try:
        module = importlib.import_module("hermes_cli.config")
    except ModuleNotFoundError:
        return None
    get_home = getattr(module, "get_hermes_home", None)
    if get_home is None:
        return None
    try:
        home = get_home()
    except Exception as error:  # noqa: BLE001 - import boundary
        raise DataRootError(f"hermes_cli.config.get_hermes_home failed: {error}") from error
    if not home:
        return None
    return Path(home).expanduser().resolve()
