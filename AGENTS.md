# Wingstaff work contract

## Core Contract

- Wingstaff is a Hermes-native plugin plus bundled skills, not a standalone orchestration service.
- Do not add an MCP server, HTTP daemon, dashboard server, or nested `hermes chat` subprocess bridge.
- Use Hermes' existing plugin, delegation, Kanban, cron, gateway, and skill facilities.
- A human approval gate is mandatory before implementation work starts.
- Missing skills, invalid structured output, and failed verification stop the workflow. Never fabricate fallback plans or artifacts.
- Workflow-pack adapters contain skill-set-specific mappings. The engine remains pack-neutral.

## Read Before Editing

1. Read this file.
2. Identify each path to be changed.
3. Read every child `AGENTS.md` on the route to those paths.
4. Read the implementation plan under `docs/plans/` when changing architecture or scope.

## Update After Editing

Update the nearest `AGENTS.md` when a change affects ownership, contracts, workflow, verification, or durable structure. Keep current-state rules only; Git carries history.

## Work Guidance

- Prefer one vertical slice that runs over broad scaffolding that does not.
- Keep deterministic state transitions and validation in Python; keep judgment in skills or host-owned structured LLM calls.
- External skills are referenced by fully qualified install target and validated by exact name.
- Plugin tool handlers accept `args: dict, **kwargs` and always return a JSON string.
- Runtime files belong under a Hermes-resolved home/profile path; never hard-code `~/.hermes`.
- Do not commit credentials, live workflow state, SQLite databases, or generated workspaces.
- Do not commit, push, or publish unless explicitly requested.

## Verification

```bash
pytest
ruff check .
wingstaff packs validate addyosmani
python -m build
python -m twine check dist/*
```

## Child DOX Index

| Child | Owns | Read when editing… |
|---|---|---|
| [`assets/AGENTS.md`](assets/AGENTS.md) | Brand source, generated visual assets, and bundled font licensing. | Logos, social cards, asset generation, or brand narrative. |
| [`wingstaff/AGENTS.md`](wingstaff/AGENTS.md) | Plugin registration, deterministic engine, pack resources, bundled skills. | Runtime Python, tool schemas/handlers, packs, bundled skills. |
| [`tests/AGENTS.md`](tests/AGENTS.md) | Unit, package, and plugin-contract verification. | Tests or fixtures. |
| [`docs/AGENTS.md`](docs/AGENTS.md) | Architecture and implementation plans. | Plans, decisions, roadmap, operator documentation. |
| [`scripts/AGENTS.md`](scripts/AGENTS.md) | Dependency-free development and repository verification utilities. | Verification scripts or durable development automation. |
