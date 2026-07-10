# Wingstaff

![Wingstaff](assets/logo.svg)

Wingstaff is a Hermes-native staff of specialist agents that moves software work through interchangeable workflow packs and one explicit human approval gate—without introducing a second orchestration server.

It uses Hermes' existing plugin, skills, delegation, Kanban, cron, and gateway facilities. It does not run a separate MCP, HTTP, dashboard, or orchestration server.

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

## Hermes integration

Directory and Python entry-point discovery are verified against Hermes v0.18.2.
See the [Hermes integration guide](docs/08-hermes-integration.md) for the exact
tested development procedure and compatibility limits. A remote
`hermes plugins install` command will be published only after this repository
has a real remote and that command has been exercised.

The standalone `wingstaff` executable is a development and diagnostics surface. The canonical operator interface will be `hermes wingstaff ...` once the plugin CLI is implemented.

## Architecture

The stable lifecycle is pack-neutral:

```text
discover -> define -> plan -> HUMAN GATE -> implement -> verify -> review -> deliver
```

Workflow packs map external skills onto that lifecycle. External skill repositories remain dependencies; their content is not vendored into Wingstaff.

Start with [`docs/README.md`](docs/README.md) for the source-grounded documentation set and support status. The [implementation roadmap](docs/plans/2026-07-10-wingstaff-bootstrap-and-roadmap.md) owns future phases.

## License

MIT
