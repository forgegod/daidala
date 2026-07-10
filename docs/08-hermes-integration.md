# Hermes integration

Wingstaff 0.1.0 has been exercised against Hermes Agent v0.18.2
(`2026.7.7.2`, upstream `a9f3f087`) on Python 3.11.15. The proof used fresh
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
- tools `wingstaff_start`, `wingstaff_status`, `wingstaff_validate`,
  `wingstaff_approve`, `wingstaff_modify`, and `wingstaff_cancel`;
- skill `wingstaff:orchestrate`.

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
HERMES_HOME="$isolated_home" hermes plugins enable wingstaff --no-allow-tool-override
HERMES_HOME="$isolated_home" hermes plugins list --user --json
```

The list output must report `wingstaff` as enabled with source `git`. A fresh
Hermes process using the same `HERMES_HOME` must expose
`wingstaff_pack_info`; loading `wingstaff:orchestrate` must return the bundled
skill content.

Wingstaff does not override built-in tools, so enable it with
`--no-allow-tool-override`.

## Wheel and entry-point verification

Build and inspect the distribution with:

```bash
python -m build
python -m twine check dist/*
pytest tests/test_installation.py
```

`tests/test_installation.py` builds a wheel and checks that it contains the
Addyosmani pack, the orchestration skill, and the module-valued Hermes entry
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

- Hermes v0.18.2 is the only verified host version.
- Directory, entry-point, and public remote Git installation are verified.
- Plugin registration, deterministic workflow state, local persistence, and
  public lifecycle/gate tools are implemented. External-skill prerequisite
  enforcement, workflow execution, Kanban integration, and delivery remain
  unavailable.
- Compatibility with a newer Hermes release must be re-probed before widening
  the supported range.

Wingstaff does not declare Hermes as a Python package dependency. Hermes is the
plugin host, and its Git installation uses a separate managed environment;
adding it to `project.dependencies` would install a second host rather than
express the verified runtime boundary. Compatibility is therefore recorded and
tested as a host integration contract.

## First-release execution policy

The first executable Wingstaff release will support local target repositories
only. Later workflow phases must implement these already-fixed rules:

- reject dirty target repositories;
- implement in a fresh Wingstaff-owned worktree;
- return a reviewed working-tree diff without automatically committing or
  pushing target changes;
- require separate authorization for any target commit or push;
- bind one approval to the complete plan digest and invalidate that approval
  after any plan modification.

This policy is established for Phase 2 state design but is not yet executable.
