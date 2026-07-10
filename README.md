# Wingstaff

Wingstaff is a Hermes Agent plugin for autonomous software-development workflows with an explicit human approval gate.

It is designed to use Hermes' existing plugin, skills, delegation, Kanban, cron, and gateway facilities. It does not run a separate MCP, HTTP, dashboard, or orchestration server.

## Status

Pre-alpha bootstrap. The repository currently provides:

- a native Hermes plugin registration;
- a bundled `wingstaff:orchestrate` skill;
- a validated workflow-pack format;
- an Addy Osmani `agent-skills` lifecycle adapter;
- a standalone pack-validation command.

Workflow execution, durable state transitions, approval tools, and the AI-DLC adapter are planned but not implemented.

## Development

```bash
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/wingstaff packs validate addyosmani
python -m build
```

## Intended installation

From a published Git repository:

```bash
hermes plugins install <owner>/wingstaff --enable
```

The standalone `wingstaff` executable is a development and diagnostics surface. The canonical operator interface will be `hermes wingstaff ...` once the plugin CLI is implemented.

## Architecture

The stable lifecycle is pack-neutral:

```text
discover -> define -> plan -> HUMAN GATE -> implement -> verify -> review -> deliver
```

Workflow packs map external skills onto that lifecycle. External skill repositories remain dependencies; their content is not vendored into Wingstaff.

See `docs/plans/2026-07-10-wingstaff-bootstrap-and-roadmap.md` for the implementation plan.

## License

MIT
