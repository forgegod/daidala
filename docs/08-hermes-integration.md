# Hermes integration

Daidala 0.2.0 has been exercised against Hermes Agent v0.18.2
(`2026.7.7.2`, upstream `4281151a`) on Python 3.11.15. The proof used fresh
`HERMES_HOME` directories and did not read or modify the active Hermes profile.

This document records observed behavior. The current Hermes
[plugin documentation](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins)
remains authoritative when later Hermes releases differ.

## Supported integration surfaces

Daidala supports both plugin discovery paths exposed by the tested Hermes
release:

| Source | Hermes source label | Result |
|---|---|---|
| Directory containing `plugin.yaml` and root `__init__.py` | `user` (`git` in `hermes plugins list`) | Explicit enablement, tool registration, and bundled skill loading passed |
| Python distribution entry point in `hermes_agent.plugins` | `entrypoint` | Explicit enablement, tool registration, and bundled skill loading passed |
| Public Git repository `forgegod/daidala` | `user` (`git` in `hermes plugins list`) | Pending the authorized Phase 6 destination push and fresh installation probe |

The verified directory and entry-point discovery paths register exactly:

- tool `daidala_pack_info`;
- tools `daidala_start`, `daidala_status`, `daidala_replace_constraints`,
  `daidala_approve`, and `daidala_cancel`;
- tools `daidala_submit_artifact`, `daidala_prepare_implementation`,
  `daidala_capture_implementation`, `daidala_record_skill_activation`,
  `daidala_record_verification`, and `daidala_deliver`;
- skills `daidala:aidlc-adapter`, `daidala:orchestrate`, and `daidala:setup`;
- operator command family `hermes daidala`.

The optional dashboard package registers `/daidala`, the `sessions:top` slot,
authenticated backend routes, and SDK `1.1.0` assets. Hermes v0.18.2 exposes no
`kanban:top` extension slot. Workflow polling is read-only; setup and constraint
writes are narrowly typed and confirmation-gated. Python entry points do not
materialize dashboard assets, so installation must retain the packaged
`dashboard/` subtree alongside the plugin manifest.

The root directory entry point must import the bundled package relatively.
The Python entry point must resolve to the `daidala` module, not directly to
`daidala:register`, because Hermes loads the entry point and then looks for a
module-level `register(ctx)` function.

## Isolated directory verification

The following development procedure is the directory-install path exercised in
Phase 1. Run it from the Daidala repository root:

```bash
isolated_home="$(mktemp -d)/home"
mkdir -p "$isolated_home/plugins"
ln -s "$PWD" "$isolated_home/plugins/daidala"
HERMES_HOME="$isolated_home" hermes plugins enable daidala
HERMES_HOME="$isolated_home" hermes plugins list --user --json
```

The list output must report `daidala` as enabled with source `git`. A fresh
Hermes process using the same `HERMES_HOME` must expose `hermes daidala` and
produce byte-equivalent native and standalone pack-validation JSON. The exact
12-tool and three-skill inventories are pinned against `register(ctx)` by
`tests/test_plugin.py`.

Daidala does not override built-in tools.

## Repeatable isolated verification

The host probes cover separate public boundaries:

- `probe_hermes_compatibility.py` verifies exact host identity, one complete
  policy-skill digest, public Kanban create/show/context/link/comment/complete/
  archive operations, and the 8,192/8,300 worker-context boundary.
- `probe_hermes_plugin_compatibility.py` verifies fresh-process Daidala loading,
  public enabled-plugin inventory when the host reports entry points, and exact
  native/standalone validation parity for both bundled packs. Passing
  `--plugin-directory` exercises directory discovery instead of the installed
  Python entry point.
- `probe_hermes_dashboard_compatibility.py` verifies dashboard manifest
  discovery, static assets, and authenticated API mounting against an isolated
  fixture plugin.

Run them from a Daidala checkout with the supported `hermes` and `daidala`
executables on `PATH`:

```bash
python scripts/probe_hermes_compatibility.py
python scripts/probe_hermes_plugin_compatibility.py
python scripts/probe_hermes_dashboard_compatibility.py
```

Each success returns one bounded JSON object. A failure is non-zero and names the
missing or changed contract. Temporary homes are removed unless `--keep-temp` is
explicitly selected for diagnosis. Every probe rejects a generated root inside
an inherited active `HERMES_HOME`.

All three probes accept `--expected-semver`, `--expected-build`, and
`--expected-upstream` only as one complete identity override. Omitting all three
retains the supported v0.18.2 defaults. An entry point omitted from v0.18.2's
public plugin inventory is retained as `reported: false`; native command loading
must still pass. A reported plugin error or any native/standalone mismatch fails.

`.github/workflows/release.yml` installs Hermes at full revision
`4281151ae859241351ba14d8c7682dc67ff4c126` and runs
the probe only for `v*` tags or explicit `workflow_dispatch`, after normal test
and package jobs pass. Ordinary branch pushes and pull requests do not pay the
live-host cost. The release job pins the temporary checkout's local
`origin/main` tracking ref to that revision and disables network fetches from
the temporary clone so Hermes's background update check cannot change identity
evidence between probes. It also builds the pinned host's `web` workspace with
Node 22 before the dashboard probe uses `--skip-build`.

## Operator CLI registration

The plugin registers `hermes daidala` through the documented
`ctx.register_cli_command` API. Its setup callback and the standalone
`daidala` executable share one argparse tree and one service dispatcher.

Hermes v0.18.2 invokes plugin command callbacks but discards their integer
return values. The native callback therefore raises `SystemExit` with the
shared dispatcher's code. This narrow host-compatibility boundary keeps success
and failure process codes equivalent across native and standalone invocations.
Directory-loaded plugins run under a host-generated module namespace, so
package resources resolve through the current `__package__`, not a hard-coded
top-level `daidala` import.

`PluginContext.dispatch_tool` resolves built-in Kanban tools in an agent process.
A standalone plugin CLI invocation does not load the agent tool registry and
returned `Unknown tool: kanban_create` in the Phase 0 probe. Agent-facing
Daidala tools therefore use `ctx.dispatch_tool`, while native and standalone
operator commands translate the same narrow graph-adapter calls into documented
`hermes kanban` subprocess commands. Both paths use public host operations;
Daidala never imports Hermes Kanban modules or accesses its SQLite database.

## Kanban-native workflow boundary

Hermes v0.18.2 exposes the required public operations for the complete graph,
and Daidala's graph adapter uses these surfaces:

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
default Hermes profile with optional per-stage overrides; Daidala expands and
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
hermes plugins install forgegod/daidala --enable
```

Phase 7 exercised this exact command in a fresh `HERMES_HOME`, then used a
separate Hermes process to confirm that the plugin is enabled without errors,
registers all 12 tools, loads all three bundled skills, exposes the native CLI
and dashboard manifest, validates both packs, and creates only the Daidala
runtime root. A desktop and narrow browser pass exercised the untouched public
clone on the pinned host.

## Compatibility limits

| Hermes host | Directory plugin | Python entry point | Public Git install | Native CLI | Kanban restart/idempotency | Status |
|---|---|---|---|---|---|---|
| v0.18.2 (`2026.7.7.2`, `4281151a`) | Passed | Passed | Passed | Passed | Passed | Supported through public Git installation |
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

Daidala does not declare Hermes as a Python package dependency. Hermes is the
plugin host, and its Git installation uses a separate managed environment;
adding it to `project.dependencies` would install a second host rather than
express the verified runtime boundary. Compatibility is therefore recorded and
tested as a host integration contract.

## First-release execution policy

The first executable Daidala release supports local target repositories only
and enforces these rules:

- reject dirty target repositories;
- implement in a fresh Daidala-owned worktree;
- return a reviewed working-tree diff without automatically committing or
  pushing target changes;
- require separate authorization for any target commit or push;
- bind one approval to the complete plan digest and invalidate that approval
  after any plan modification.

Repository tests and the isolated compatibility probe verify this policy against
temporary repositories with both passing and deliberately failing workflow
slices.
