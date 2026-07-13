"""Daidala Hermes plugin registration."""

from __future__ import annotations

from pathlib import Path

from . import cli, schemas, tools
from .packs import __version__


def register(ctx) -> None:
    """Register Daidala tools and bundled, namespaced skills with Hermes."""
    tools.configure_host(ctx.dispatch_tool)
    ctx.register_cli_command(
        name="daidala",
        help="Operate Daidala workflows and workflow packs",
        setup_fn=cli.register_cli,
        handler_fn=cli.dispatch_cli,
        description="Initialize, diagnose, start, inspect, approve, or cancel workflows.",
    )
    handlers = {
        "daidala_pack_info": tools.pack_info,
        "daidala_start": tools.start,
        "daidala_status": tools.status,
        "daidala_replace_constraints": tools.replace_constraints,
        "daidala_approve": tools.approve,
        "daidala_cancel": tools.cancel,
        "daidala_submit_artifact": tools.submit_artifact,
        "daidala_prepare_implementation": tools.prepare_implementation,
        "daidala_capture_implementation": tools.capture_implementation,
        "daidala_record_skill_activation": tools.record_skill_activation,
        "daidala_record_verification": tools.record_verification,
        "daidala_deliver": tools.deliver,
    }
    for schema in schemas.ALL_TOOLS:
        ctx.register_tool(
            name=schema["name"],
            toolset="daidala",
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
