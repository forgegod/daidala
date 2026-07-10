"""Wingstaff Hermes plugin registration."""

from __future__ import annotations

from pathlib import Path

from . import cli, schemas, tools
from .packs import __version__


def register(ctx) -> None:
    """Register Wingstaff tools and bundled, namespaced skills with Hermes."""
    tools.configure_context(ctx)
    ctx.register_cli_command(
        name="wingstaff",
        help="Operate Wingstaff workflows and workflow packs",
        setup_fn=cli.register_cli,
        handler_fn=cli.dispatch_cli,
        description="Initialize, diagnose, start, inspect, approve, or cancel workflows.",
    )
    handlers = {
        "wingstaff_pack_info": tools.pack_info,
        "wingstaff_start": tools.start,
        "wingstaff_status": tools.status,
        "wingstaff_validate": tools.validate,
        "wingstaff_approve": tools.approve,
        "wingstaff_modify": tools.modify,
        "wingstaff_cancel": tools.cancel,
        "wingstaff_submit_artifact": tools.submit_artifact,
        "wingstaff_prepare_implementation": tools.prepare_implementation,
        "wingstaff_capture_implementation": tools.capture_implementation,
        "wingstaff_record_verification": tools.record_verification,
        "wingstaff_deliver": tools.deliver,
    }
    for schema in schemas.ALL_TOOLS:
        ctx.register_tool(
            name=schema["name"],
            toolset="wingstaff",
            schema=schema,
            handler=handlers[schema["name"]],
            description=schema["description"],
        )

    skills_dir = Path(__file__).parent / "skills"
    for child in sorted(skills_dir.iterdir()):
        skill_md = child / "SKILL.md"
        if child.is_dir() and skill_md.is_file():
            ctx.register_skill(child.name, skill_md)


__all__ = ["__version__", "register"]
