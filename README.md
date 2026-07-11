# Wingstaff

![Wingstaff](assets/logo.svg)

Wingstaff is a Hermes-native staff of specialist agents that moves software work through interchangeable workflow packs and one explicit human approval gate—without introducing a second orchestration server.

It uses Hermes' existing plugin, skills, delegation, Kanban, cron, and gateway facilities. It does not run a separate MCP, HTTP, dashboard, or orchestration server.

## Status

Pre-alpha. The repository currently provides:

- a native Hermes plugin registration;
- a bundled `wingstaff:orchestrate` skill;
- a validated workflow-pack format;
- an Addy Osmani `agent-skills` lifecycle adapter;
- a pinned AI-DLC v1.0.1 adapter packaged as a licensed Wingstaff skill;
- durable workflow state, approval-gated detached-worktree execution,
  verification evidence, review, and uncommitted delivery;
- exact external-skill name and pinned-content gates;
- standalone pack validation, dry-run installation, dependency checks, and
  controlled update planning;
- worktree cleanup/rollback and a two-version release gate with dependency and
  package-content auditing.

Hermes Kanban mapping and `hermes wingstaff` registration are implemented.
Target commit/push remains outside the current delivery contract.

## Development

```bash
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/lefthook install
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/wingstaff packs validate addyosmani
.venv/bin/wingstaff packs validate aidlc
python -m build
.venv/bin/python scripts/check_release_contents.py . --wheel dist/*.whl
```

The tracked Lefthook `post-commit` hook runs `code-review-graph update`. Install
`code-review-graph` separately and keep it available on `PATH` when committing.

Preview profile-local dependency mutations without applying them:

```bash
.venv/bin/wingstaff packs install addyosmani
```

Use `packs check` only after installation; it exits nonzero for missing or
digest-mismatched skills.

## Hermes integration

Install and enable the public plugin with the command verified against Hermes
v0.18.2:

```bash
hermes plugins install forgegod/hermes-wingstaff --enable
```

See the [Hermes integration guide](docs/08-hermes-integration.md) for the
isolated verification procedure and compatibility limits.

The standalone `wingstaff` executable is a development and diagnostics surface. The canonical operator interface will be `hermes wingstaff ...` once the plugin CLI is implemented.

## Architecture

The stable lifecycle is pack-neutral:

```text
discover -> define -> plan -> HUMAN GATE -> implement -> verify -> review -> deliver
```

Workflow packs map external or plugin-bundled skills onto that lifecycle.
External Hermes skills remain dependencies pinned by commit and complete
directory digest. Upstream rule sets that are not Hermes skills require a
licensed, reviewable bundled adapter rather than a fabricated install target.

Start with [`docs/README.md`](docs/README.md) for the source-grounded documentation set and support status. The [implementation roadmap](docs/plans/2026-07-10-wingstaff-bootstrap-and-roadmap.md) owns future phases.

## License

MIT
