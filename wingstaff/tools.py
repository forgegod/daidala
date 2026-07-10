"""Hermes plugin tool handlers."""

from __future__ import annotations

import json
from typing import Any

from .packs import PackError, load_pack


def pack_info(args: dict[str, Any], **kwargs: Any) -> str:
    """Return validated pack metadata as a Hermes-compatible JSON string."""
    del kwargs
    name = str(args.get("pack") or "addyosmani")
    try:
        pack = load_pack(name)
    except PackError as exc:
        return json.dumps({"success": False, "error": str(exc)})

    return json.dumps(
        {
            "success": True,
            "pack": pack.name,
            "source": pack.source,
            "lifecycle": list(pack.lifecycle),
            "human_gate_after": pack.human_gate_after,
            "skills": {
                stage.id: [skill.install for skill in stage.skills]
                for stage in pack.stages
            },
        }
    )
