# Daidala clean-host pack CLI remediation

**Plan ID:** daidala-clean-host-pack-cli

**Execution slot:** P0215

**Created:** 2026-08-09

**Depends on:** daidala-dashboard-user-config-packs-start-constraints-github-links

**Plan family:** daidala-dashboard

**Entry checkpoint:** P0200 Phase 1 is complete; PR #17 CI reproduced that stateless `packs list` and `packs validate` resolve a profile data root before dispatching, so they fail in clean wheel installs without Hermes.

**Context sources:** [P0200 Phase 1](P0200-daidala-dashboard-profile-and-packs.md#phase-1-add-pack-browser-and-readiness-actions), `daidala/AGENTS.md`, `tests/AGENTS.md`, `daidala/cli.py`, `tests/test_cli.py`, and [release gate](../../.github/workflows/release.yml)

**Produces:** clean-host parity for bundled `packs list` and `packs validate` on standalone and native command paths, with profile-root resolution retained only for profile-backed pack operations.

**Status:** complete — Phase 0 is implemented at `cf143a3`; the local full gate passed (534 tests, release build, clean-wheel audit) and PR #17 passed Python 3.11, Python 3.12, and package-audit checks.

## Goal

Make bundled pack discovery and validation runnable from an installed wheel without a Hermes profile, while preserving strict profile-root resolution for operations that inspect or mutate installed skills.

## Current state

- `_run_pack_operation` dispatches bundled `list` and `validate` before constructing profile-backed inventory.
- A clean wheel virtual environment without Hermes validates both bundled packs; PR #17 confirms the same result on Python 3.11 and 3.12.
- `list` and `validate` consume bundled pack definitions only; `check`, `install`, and `update-plan` remain profile-backed.

## Phase table

| # | Phase | Status | Verification gate |
|---|---|---|---|
| 0 | Defer profile-root resolution for stateless pack operations | done (`cf143a3`; local 534-test/release gate and PR #17 Python 3.11, Python 3.12, and package-audit checks passed) | With root resolution forced to fail, standalone and native `packs list` and `packs validate` retain identical successful JSON results; profile-backed operations retain their existing root requirement; the full release gate passes on CI. |

Mark a phase `in-progress` while running it, `done (<evidence>)` once its gate passes, `pending` otherwise.

## Phase 0 — Defer profile-root resolution for stateless pack operations

**Goal:** Construct profile-backed inventory only after dispatching bundled `list` and `validate` operations.

Steps:

1. Add a regression test that makes `resolve_data_root` fail and asserts both command surfaces still list and validate bundled packs.
2. Move only the profile-backed registry/service construction behind the `check`, `install`, and `update-plan` path; do not add a fallback data root.
3. Preserve the shared parser and JSON boundary, then run focused CLI tests, the full repository gate, an isolated wheel command with `HERMES_HOME` unset, and PR CI.

Verification gate: Both Python 3.11 and Python 3.12 CI test jobs and the isolated-wheel package audit pass; no profile directory or fallback runtime state is created for stateless pack operations.

## Out of scope

- Do not weaken `resolve_data_root` or add a guessed default directory.
- Do not make profile-backed `check`, `install`, or `update-plan` succeed without a resolved profile root.
- Do not alter dashboard routes, pack schemas, or external-skill installation authority.
