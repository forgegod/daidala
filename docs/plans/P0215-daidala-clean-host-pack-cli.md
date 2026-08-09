# Daidala clean-host pack CLI remediation

**Plan ID:** daidala-clean-host-pack-cli

**Execution slot:** P0215

**Created:** 2026-08-09

**Depends on:** daidala-dashboard-user-config-packs-start-constraints-github-links

**Plan family:** daidala-dashboard

**Entry checkpoint:** P0200 Phase 1 is complete; PR #17 CI reproduced that stateless `packs list` and `packs validate` resolve a profile data root before dispatching, so they fail in clean wheel installs without Hermes.

**Context sources:** [P0200 Phase 1](P0200-daidala-dashboard-profile-and-packs.md#phase-1-add-pack-browser-and-readiness-actions), `daidala/AGENTS.md`, `tests/AGENTS.md`, `daidala/cli.py`, `tests/test_cli.py`, and [release gate](../../.github/workflows/release.yml)

**Produces:** clean-host parity for bundled `packs list` and `packs validate` on standalone and native command paths, with profile-root resolution retained only for profile-backed pack operations.

**Status:** in-progress — human implementation approval is recorded for the branch-integration remediation.

## Goal

Make bundled pack discovery and validation runnable from an installed wheel without a Hermes profile, while preserving strict profile-root resolution for operations that inspect or mutate installed skills.

## Current state

- PR #17 failed on Python 3.11 and 3.12 because `_run_pack_operation` constructs `ProfileSkillContentRegistry(resolve_data_root() / "skills")` before branching for `list` or `validate`.
- The package audit independently reproduces the same defect from a clean wheel virtual environment with no Hermes installation.
- `list` and `validate` consume bundled pack definitions only; `check`, `install`, and `update-plan` remain profile-backed.

## Phase table

| # | Phase | Status | Verification gate |
|---|---|---|---|
| 0 | Defer profile-root resolution for stateless pack operations | in-progress | With root resolution forced to fail, standalone and native `packs list` and `packs validate` retain identical successful JSON results; profile-backed operations retain their existing root requirement; the full release gate passes on CI. |

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
