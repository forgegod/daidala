# wingstaff/

## Purpose

Implement the Hermes plugin boundary, deterministic policy and artifact ledger,
workflow-pack adapters, and bundled orchestration skills.

## Ownership

| Path | Owns |
|---|---|
| `__init__.py` | Hermes tool, skill, and operator CLI registration. |
| `errors.py` | Policy-ledger, persistence, and host-boundary error hierarchy. |
| `state.py` | Immutable policy ledger, artifact evidence, Kanban identifiers, and serialization. |
| `workflow.py` | Deterministic policy checks and ledger updates; no operational status transitions. |
| `locations.py` | Profile-aware data-root resolution; never hard-codes `~/.hermes`. |
| `store.py` | SQLite-backed policy-ledger persistence with optimistic concurrency. |
| `service.py` | Repository preflight, approval, artifact, worktree, and ledger coordination. |
| `skills.py` | Exact installed-skill inventory, content-digest verification, and mutation-free install planning. |
| `execution.py` | Profile-local artifacts, detached worktrees, and diff capture. |
| `kanban.py` | Public `ctx.dispatch_tool` adapter for idempotent Hermes task creation. |
| `schemas.py` | Tool schemas exposed to the model. |
| `tools.py` | Strict JSON-returning plugin handlers; exceptions never cross into Hermes. |
| `packs.py` | Pack loading and deterministic validation. |
| `cli.py` | Shared `hermes wingstaff` and standalone operator command tree, lifecycle dispatch, pack operations, and subprocess mutation boundary. |
| `packs/` | Skill-set-specific lifecycle mappings. |
| `skills/` | Namespaced read-only skills bundled with the plugin. |

## Local Contracts

- `register(ctx)` imports no Hermes internals; it uses only the documented plugin context API.
- Tool handlers never raise across the plugin boundary and always return JSON strings.
- Pack skills declare exactly one provider: a fully qualified external install
  target or a plugin-bundled skill with the same exact name.
- External packs pin a Git source revision, bounded Hermes version, and complete-directory digest per required skill.
- Standalone CLI inventory comes from the profile skill directory; it never imports Hermes runtime internals.
- Native and standalone operator commands share one parser and dispatch layer; setup and external installation remain dry-run by default.
- Hermes Kanban owns every operational status; Wingstaff persists no mirrored
  ready, running, blocked, done, or archived field.
- Kanban integration uses only `ctx.dispatch_tool`; Wingstaff never imports or writes Hermes' Kanban database.
- The policy store uses one fresh schema and does not inspect or migrate the
  unreleased workflow-state database.
- The engine never substitutes guessed data when a model, skill, or verifier fails.
- Delivery and operator cancellation remove only their Wingstaff-owned detached
  worktree; captured artifacts remain durable.
- No server, listening socket, or nested Hermes process is part of this package.

## Work Guidance

- Add mechanism to Python and subject-matter mappings to `packs/*.yaml`.
- Register bundled skills with `ctx.register_skill`; do not copy them into the user's mutable skill store.
- Keep third-party attribution and license text beside derived bundled adapters.
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
