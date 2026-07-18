# DOX framework

- DOX is highly performant AGENTS.md hierarchy installed here
- Agent must follow DOX instructions across any edits

## Core Contract

- AGENTS.md files are binding work contracts for their subtrees
- Work products, source materials, instructions, records, assets, and durable docs must stay understandable from the nearest applicable AGENTS.md plus every parent AGENTS.md above it
- Daidala is a Hermes-native plugin plus bundled skills, not a standalone orchestration service.
- Do not add an MCP server, HTTP daemon, dashboard server, or nested `hermes chat` subprocess bridge.
- Use Hermes' existing plugin, delegation, Kanban, cron, gateway, and skill facilities.
- A human approval gate is mandatory before implementation work starts.
- Missing skills, invalid structured output, and failed verification stop the workflow. Never fabricate fallback plans or artifacts.
- Workflow-pack adapters contain skill-set-specific mappings. The engine remains pack-neutral.

## Read Before Editing

1. Read the root AGENTS.md
2. Identify every file or folder you expect to touch
3. Walk from the repository root to each target path
4. Read every AGENTS.md found along each route
5. If a parent AGENTS.md lists a child AGENTS.md whose scope contains the path, read that child and continue from there
6. Use the nearest AGENTS.md as the local contract and parent docs for repo-wide rules
7. If docs conflict, the closer doc controls local work details, but no child doc may weaken DOX

Do not rely on memory. Re-read the applicable DOX chain in the current session before editing.

Read the implementation plan under `docs/plans/` when changing architecture or scope.

## Update After Editing

Every meaningful change requires a DOX pass before the task is done.

Update the closest owning AGENTS.md when a change affects:

- purpose, scope, ownership, or responsibilities
- durable structure, contracts, workflows, or operating rules
- required inputs, outputs, permissions, constraints, side effects, or artifacts
- user preferences about behavior, communication, process, organization, or quality
- AGENTS.md creation, deletion, move, rename, or index contents

Update parent docs when parent-level structure, ownership, workflow, or child index changes. Update child docs when parent changes alter local rules. Remove stale or contradictory text immediately. Small edits that do not change behavior or contracts may leave docs unchanged, but the DOX pass still must happen.

## Hierarchy

- Root AGENTS.md is the DOX rail: project-wide instructions, global preferences, durable workflow rules, and the top-level Child DOX Index
- Child AGENTS.md files own domain-specific instructions and their own Child DOX Index
- Each parent explains what its direct children cover and what stays owned by the parent
- The closer a doc is to the work, the more specific and practical it must be

## Child Doc Shape

- Create a child AGENTS.md when a folder becomes a durable boundary with its own purpose, rules, responsibilities, workflow, materials, or quality standards
- Work Guidance must reflect the current standards of the project or user instructions; if there are no specific standards or instructions yet, leave it empty
- Verification must reflect an existing check; if no verification framework exists yet, leave it empty and update it when one exists

Default section order:
- Purpose
- Ownership
- Local Contracts
- Work Guidance
- Verification
- Child DOX Index

## Style

- Keep docs concise, current, and operational
- Document stable contracts, not diary entries
- Put broad rules in parent docs and concrete details in child docs
- Prefer direct bullets with explicit names
- Do not duplicate rules across many files unless each scope needs a local version
- Delete stale notes instead of explaining history
- Trim obvious statements, repeated rules, misplaced detail, and warnings for risks that no longer exist

## Closeout

1. Re-check changed paths against the DOX chain
2. Update nearest owning docs and any affected parents or children
3. Refresh every affected Child DOX Index
4. Remove stale or contradictory text
5. Run existing verification when relevant
6. Report any docs intentionally left unchanged and why

Project verification:

```bash
lefthook validate
pytest
ruff check .
daidala packs validate addyosmani
daidala packs validate aidlc
python -m build
python -m twine check dist/*
python scripts/check_release_contents.py . --wheel dist/*.whl
```

## User Preferences

When the user requests a durable behavior change, record it here or in the relevant child AGENTS.md.

Project-wide durable preferences (style, workflow, conventions) live in user memory; this section is reserved for contract-level rules that bind every child doc.

## Architectural decisions

- **Agent harness protected by tirith.sh.** Reading passwords or access tokens is prohibited. Extract variables from `.env` / config files without relaying their values; use environment variables by importing them for Bash execution. `***` in output is a tirith redaction marker, not a literal value — never "fix" it to a variable ref.
- Prefer one vertical slice that runs over broad scaffolding that does not.
- Keep deterministic policy checks and validation in Python; keep operational
  lifecycle state in Hermes Kanban and judgment in skills or host-owned
  structured LLM calls.
- External skills are referenced by fully qualified install target and validated by exact name.
- Plugin tool handlers accept `args: dict, **kwargs` and always return a JSON string.
- The directory-plugin entry point exposes its implementation package as
  `daidala` so dashboard backend imports match pip installations.
- Runtime files belong under a Hermes-resolved home/profile path; never hard-code `~/.hermes`.
- Registered projects commit strict `.daidala/project.yaml` policy, while trusted
  checkout, remote, profile, board, credential aliases, attended target, and
  evaluator authority remain profile-local registration data.
- Credential aliases are logical names, not password-manager integrations. The
  planned V1 resolver uses explicit profile-local alias-to-environment bindings;
  it does not infer vault entries or invoke Bitwarden/KeePass CLIs.
- Self-improvement v1 uses one active cycle, one mutable repository,
  `restricted-container` evaluators with denied-by-default network, 1 MiB
  document bounds, and no external semantic-memory dependency.
- Self-improvement admission uses the deterministic cycle ID as the Daidala
  workflow ID, writes the canonical manifest snapshot before dispatch, binds the
  expected baseline, constraints, and stage profiles, and validates adapter
  claims and event-specific notification receipts before Kanban mutation.
- The persistent self-improvement controller loads Daidala from an exact detached
  committed revision installed through verified Git or a detached local clone;
  never from a mutable symlink, editable checkout, or uncommitted working tree.
- `docs/16-self-improvement-setup.md` is the normative prerequisite guide. The
  shared `daidala doctor` command may mirror its stable check IDs and report
  evidence, but never mutates setup state or replaces human approval.
- Do not commit credentials, live workflow state, SQLite databases, or generated workspaces.
- Do not commit, push, or publish unless explicitly requested.

## Codebase Knowledge Graph (codebase-memory-mcp)

This project uses codebase-memory-mcp to maintain a knowledge graph of the codebase.
ALWAYS prefer MCP graph tools over grep/glob/file-search for code discovery.

### Priority Order
1. `search_graph` — find functions, classes, routes, variables by pattern
2. `trace_path` — trace who calls a function or what it calls
3. `get_code_snippet` — read specific function/class source code
4. `query_graph` — run Cypher queries for complex patterns
5. `get_architecture` — high-level project summary

### When to fall back to grep/glob
- Searching for string literals, error messages, config values
- Searching non-code files (Dockerfiles, shell scripts, configs)
- When MCP tools return insufficient results

### Examples
- Find a handler: `search_graph(name_pattern=".*OrderHandler.*")`
- Who calls it: `trace_path(function_name="OrderHandler", direction="inbound")`
- Read source: `get_code_snippet(qualified_name="pkg/orders.OrderHandler")`

## Child DOX Index

| Child | Owns | Read when editing… |
|---|---|---|
| [`assets/AGENTS.md`](assets/AGENTS.md) | Brand source, generated visual assets, and bundled font licensing. | Logos, social cards, asset generation, or brand narrative. |
| [`dashboard/AGENTS.md`](dashboard/AGENTS.md) | Optional Hermes dashboard manifest, backend router, browser assets, and UI contracts. | Dashboard routes, registration, JavaScript, CSS, or browser verification. |
| [`docs/AGENTS.md`](docs/AGENTS.md) | Architecture and implementation plans. | Plans, decisions, roadmap, or operator documentation. |
| [`scripts/AGENTS.md`](scripts/AGENTS.md) | Dependency-free development and repository verification utilities. | Verification scripts or durable development automation. |
| [`tests/AGENTS.md`](tests/AGENTS.md) | Unit, package, and plugin-contract verification. | Tests or fixtures. |
| [`daidala/AGENTS.md`](daidala/AGENTS.md) | Plugin registration, deterministic engine, pack resources, and bundled skills. | Runtime Python, tool schemas or handlers, packs, or bundled skills. |
