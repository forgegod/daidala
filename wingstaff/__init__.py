"""Wingstaff Hermes plugin registration."""

from __future__ import annotations

from pathlib import Path

from . import schemas, tools
from .packs import __version__


def register(ctx) -> None:
    """Register Wingstaff tools and bundled, namespaced skills with Hermes."""
    ctx.register_tool(
        name="wingstaff_pack_info",
        toolset="wingstaff",
        schema=schemas.PACK_INFO,
        handler=tools.pack_info,
        description="Inspect and validate an installed Wingstaff workflow pack.",
    )

    skills_dir = Path(__file__).parent / "skills"
    for child in sorted(skills_dir.iterdir()):
        skill_md = child / "SKILL.md"
        if child.is_dir() and skill_md.is_file():
            ctx.register_skill(child.name, skill_md)


__all__ = ["__version__", "register"]
