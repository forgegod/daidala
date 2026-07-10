# wingstaff/

## Purpose

Implement the Hermes plugin boundary, deterministic workflow mechanism, workflow-pack adapters, and bundled orchestration skills.

## Ownership

| Path | Owns |
|---|---|
| `__init__.py` | Hermes plugin registration. |
| `errors.py` | Workflow-state and transition error hierarchy. |
| `state.py` | Immutable workflow state, artifact references, and serialization. |
| `workflow.py` | Deterministic workflow creation and state transitions. |
| `locations.py` | Profile-aware data-root resolution; never hard-codes `~/.hermes`. |
| `store.py` | SQLite-backed workflow persistence with optimistic concurrency. |
| `service.py` | Lifecycle operations, local Git validation, and state/store coordination. |
| `skills.py` | Exact installed-skill inventory, content-digest verification, and mutation-free install planning. |
| `execution.py` | Profile-local artifacts, detached worktrees, and diff capture. |
| `kanban.py` | Public `ctx.dispatch_tool` adapter for idempotent Hermes task creation. |
| `schemas.py` | Tool schemas exposed to the model. |
| `tools.py` | Strict JSON-returning plugin handlers; exceptions never cross into Hermes. |
| `packs.py` | Pack loading and deterministic validation. |
| `cli.py` | Standalone pack validation, install/check/update planning, and the subprocess mutation boundary; later backs `hermes wingstaff`. |
| `packs/` | Skill-set-specific lifecycle mappings. |
| `skills/` | Namespaced read-only skills bundled with the plugin. |

## Local Contracts

- `register(ctx)` imports no Hermes internals; it uses only the documented plugin context API.
- Tool handlers never raise across the plugin boundary and always return JSON strings.
- Packs reference external skills by fully qualified installation target.
- External packs pin a Git source revision, bounded Hermes version, and complete-directory digest per required skill.
- Standalone CLI inventory comes from the profile skill directory; it never imports Hermes runtime internals.
- Kanban integration uses only `ctx.dispatch_tool`; Wingstaff never imports or writes Hermes' Kanban database.
- The engine never substitutes guessed data when a model, skill, or verifier fails.
- No server, listening socket, or nested Hermes process is part of this package.

## Work Guidance

- Add mechanism to Python and subject-matter mappings to `packs/*.yaml`.
- Register bundled skills with `ctx.register_skill`; do not copy them into the user's mutable skill store.
- Use `importlib.resources` so wheel and Git installations behave consistently.

## Verification

```bash
pytest
ruff check wingstaff tests
wingstaff packs validate addyosmani
```

## Child DOX Index

*(empty — resource directories do not have independent work contracts.)*

See [`/AGENTS.md`](../AGENTS.md).
