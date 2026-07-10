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

Both paths register exactly:

- tool `wingstaff_pack_info`;
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
identifier. It does not accept a local directory or wheel. This repository has
no configured Git remote, so Wingstaff does not yet publish an unverified
`hermes plugins install` command. Once a remote exists, that exact remote-based
command must be exercised in an isolated Hermes home before it is added here or
to the runbook.

## Compatibility limits

- Hermes v0.18.2 is the only verified host version.
- Directory and entry-point discovery are verified; remote Git installation is
  not yet verified.
- Plugin registration is verified. Workflow execution, persistence, approval
  tools, Kanban integration, and delivery remain unavailable.
- Compatibility with a newer Hermes release must be re-probed before widening
  the supported range.
