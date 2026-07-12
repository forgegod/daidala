# Hermes integration

Wingstaff 0.1.0 has been exercised against Hermes Agent v0.18.2
(`2026.7.7.2`, upstream `4281151a`) on Python 3.11.15. The proof used fresh
`HERMES_HOME` directories and did not read or modify the active Hermes profile.

This document records observed behavior. The current Hermes
[plugin documentation](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins)
remains authoritative when later Hermes releases differ.

## Supported integration surfaces

Wingstaff supports both plugin discovery paths exposed by the tested Hermes
release:

| Source | Hermes source label | Result |
|---|---|---|
| Directory containing `plugin.yaml` and root `__init__.py` | `user` (`git` in `hermes plugins list`) | Explicit enablement, tool registration, and bundled skill loading passed |
| Python distribution entry point in `hermes_agent.plugins` | `entrypoint` | Explicit enablement, tool registration, and bundled skill loading passed |
| Public Git repository `forgegod/hermes-wingstaff` | `user` (`git` in `hermes plugins list`) | Clone, enablement, fresh-process tool registration, and bundled skill loading passed |

All verified discovery paths register exactly:

- tool `wingstaff_pack_info`;
- tools `wingstaff_start`, `wingstaff_status`, `wingstaff_replace_constraints`,
  `wingstaff_approve`, and `wingstaff_cancel`;
- tools `wingstaff_submit_artifact`, `wingstaff_prepare_implementation`,
  `wingstaff_capture_implementation`, `wingstaff_record_skill_activation`,
  `wingstaff_record_verification`, and `wingstaff_deliver`;
- skills `wingstaff:orchestrate` and `wingstaff:aidlc-adapter`;
- operator command family `hermes wingstaff`.

The root directory entry point must import the bundled package relatively.
The Python entry point must resolve to the `wingstaff` module, not directly to
`wingstaff:register`, because Hermes loads the entry point and then looks for a
module-level `register(ctx)` function.

## Isolated directory verification

The following development procedure is the directory-install path exercised in
Phase 1. Run it from the Wingstaff repository root:

```bash
isolated_home="$(mktemp -d)/home"
mkdir -p "$isolated_home/plugins"
ln -s "$PWD" "$isolated_home/plugins/wingstaff"
HERMES_HOME="$isolated_home" hermes plugins enable wingstaff
HERMES_HOME="$isolated_home" hermes plugins list --user --json
```

The list output must report `wingstaff` as enabled with source `git`. A fresh
Hermes process using the same `HERMES_HOME` must expose
`wingstaff_pack_info`; loading `wingstaff:orchestrate` must return the bundled
skill content.

Wingstaff does not override built-in tools.

## Workflow-constraint host verification

Phase 7 repeated the constraint integration against a fresh isolated
`HERMES_HOME` on the supported host. The probe:

- loaded the directory plugin with exactly 12 registered tools and no plugin
  error;
- created an isolated named board and clean local Git target;
- resolved one exact `policy-probe` skill, verified its complete-directory
  digest, and materialized its sole fenced YAML document;
- started an AI-DLC workflow through `hermes wingstaff`, producing two cards
  whose bodies contained full constraint text but no policy-skill activation;
- removed the installed source and successfully read the self-contained
  materialized workflow;
- replaced constraints from an explicit UTF-8 file, preserving the historical
  sourced artifact while creating policy revision 2 and distinct define/plan
  card IDs and idempotency keys;
- rejected evidence submitted with the archived definition card identity.

No gateway, model, active profile, private Hermes import, or direct Kanban
database access was used. The probe root was temporary and isolated from the
operator's configured Hermes home.

Hermes v0.18.2 profile creation is not fully `HERMES_HOME`-isolated: it creates a
launcher under `~/.local/bin`. The exploratory launcher was removed immediately,
and the successful probe used the host-visible `default` assignee instead. The
repeatable release probe must not call `hermes profile create`; it should use an
already discoverable assignee or exercise Kanban without assignment.

## Operator CLI registration

The plugin registers `hermes wingstaff` through the documented
`ctx.register_cli_command` API. Its setup callback and the standalone
`wingstaff` executable share one argparse tree and one service dispatcher.

Hermes v0.18.2 invokes plugin command callbacks but discards their integer
return values. The native callback therefore raises `SystemExit` with the
shared dispatcher's code. This narrow host-compatibility boundary keeps success
and failure process codes equivalent across native and standalone invocations.
Directory-loaded plugins run under a host-generated module namespace, so
package resources resolve through the current `__package__`, not a hard-coded
top-level `wingstaff` import.

`PluginContext.dispatch_tool` resolves built-in Kanban tools in an agent process.
A standalone plugin CLI invocation does not load the agent tool registry and
returned `Unknown tool: kanban_create` in the Phase 0 probe. Agent-facing
Wingstaff tools therefore use `ctx.dispatch_tool`, while native and standalone
operator commands translate the same narrow graph-adapter calls into documented
`hermes kanban` subprocess commands. Both paths use public host operations;
Wingstaff never imports Hermes Kanban modules or accesses its SQLite database.

## Kanban-native workflow boundary

Hermes v0.18.2 exposes the required public operations for the complete graph,
and Wingstaff's graph adapter uses these surfaces:

| Capability | Verified surface |
|---|---|
| Named board | explicit `--board` and tool `board` argument |
| Assignee validation | `hermes kanban assignees --json` |
| Exact stage skills | repeated `--skill` and `kanban_create.skills` |
| Dependencies | `--parent`, `kanban_create.parents`, and `kanban_link` |
| Human gate | blocked initial status, comments, unblock, and completion |
| Shared workspace | absolute `dir:<path>` / worktree path preserved across cards |
| Idempotency | one key per workflow, plan revision, and stage |
| Worker handoff | `kanban_complete(summary, metadata)` |
| Recovery | comment, block kind, reassign, unblock, and run history |

The caller selects one existing named board per workflow. It also supplies one
default Hermes profile with optional per-stage overrides; Wingstaff expands and
validates the complete mapping before card creation. The gateway's embedded
dispatcher remains the only unattended runtime.

## Wheel and entry-point verification

Build and inspect the distribution with:

```bash
python -m build
python -m twine check dist/*
pytest tests/test_installation.py
```

`tests/test_installation.py` builds a wheel and checks that it contains both
packs, both bundled skills, AI-DLC attribution, and the module-valued Hermes entry
point. Phase 1 additionally installed that wheel into an isolated target
directory, exposed it to a fresh Hermes process through `PYTHONPATH`, enabled
it through `hermes plugins enable`, and loaded the tool and skill successfully.
This target-directory injection is a compatibility probe, not a recommended
operator installation method.

## Installation CLI boundary

On Hermes v0.18.2, `hermes plugins install` accepts a Git URL or `owner/repo`
identifier. It does not accept a local directory or wheel. The verified public
installation command is:

```bash
hermes plugins install forgegod/hermes-wingstaff --enable
```

Phase 1B exercised this command in a fresh `HERMES_HOME`, then used a separate
Hermes process to confirm that the plugin was enabled without errors, registered
`wingstaff_pack_info`, and loaded `wingstaff:orchestrate`.

## Compatibility limits

| Hermes host | Directory plugin | Python entry point | Public Git install | Native CLI | Kanban restart/idempotency | Status |
|---|---|---|---|---|---|---|
| v0.18.2 (`2026.7.7.2`, `4281151a`) | Passed | Passed | Passed | Passed | Passed | Supported |
| Other versions | Not probed | Not probed | Not probed | Not probed | Not probed | Unsupported until the full matrix passes |

- Hermes v0.18.2 is the only verified host version.
- Directory, entry-point, and public remote Git installation are verified.
- Plugin registration, approval-gated Kanban graph mapping, policy-ledger persistence,
  exact-skill and pinned-content gates, fresh worktrees, artifact capture,
  verification evidence, review, uncommitted delivery, shared native/standalone
  operator commands, dry-run/apply/check/update planning, and approval-gated
  idempotent Kanban graph dispatch, operator CLI graph creation, and worker
  recovery are implemented. Target commit/push remains unavailable.
- Compatibility with a newer Hermes release must be re-probed before widening
  the supported range.

Wingstaff does not declare Hermes as a Python package dependency. Hermes is the
plugin host, and its Git installation uses a separate managed environment;
adding it to `project.dependencies` would install a second host rather than
express the verified runtime boundary. Compatibility is therefore recorded and
tested as a host integration contract.

## First-release execution policy

The first executable Wingstaff release supports local target repositories only
and enforces these rules:

- reject dirty target repositories;
- implement in a fresh Wingstaff-owned worktree;
- return a reviewed working-tree diff without automatically committing or
  pushing target changes;
- require separate authorization for any target commit or push;
- bind one approval to the complete plan digest and invalidate that approval
  after any plan modification.

Phase 5 verifies this policy against a temporary repository with both passing
and deliberately failing workflow slices.
