# Daidala artifact CLI review

**Plan ID:** daidala-artifact-review-access-and-curation

**Execution slot:** P0300

**Created:** 2026-07-24

**Depends on:** daidala-dashboard-operator-runbook-parity, daidala-artifact-access-core, daidala-shared-archive-io

**Plan family:** daidala-artifact-review

**Entry checkpoint:** P0240 completed with dashboard operator-runbook parity; P0205 completed active exact-ID access; P0100 completed verified archive I/O

**Context sources:** [artifact current state](daidala-artifact-review-execution-contract.md#current-state), [risk call-out](daidala-artifact-review-execution-contract.md#risk-call-out), detailed [contract Phase 1](daidala-artifact-review-execution-contract.md#phase-1-add-native-and-standalone-cli-reviewexport-commands), [P0100 archive contract](P0100-daidala-shared-archive-io.md), P0205 and P0100 completion evidence, plus `AGENTS.md`, `daidala/AGENTS.md`, and `tests/AGENTS.md`

**Produces:** archive-aware exact-ID resolution plus byte-equivalent native and standalone list/show/export commands over the P0205 resolver

**Status:** complete

## Goal

Expose active and archived workflow evidence through bounded native and standalone CLI commands over exact ledger identity without arbitrary-path reads or changes to immutable ledger records.

## Current state

- P0205 provides the active exact-ID catalog and verified bounded text/export service.
- P0100 provides policy-neutral verified archive creation, manifest validation, and bounded reads.
- Workflow status exposes ledger artifact paths and SHA-256 digests, but no dedicated list/show/export command exists.
- Runtime data is profile-local and must resolve through the active Hermes home/profile.
- The shared artifact contract owns the CLI selector, output, export, and error semantics.

## Risk call-out

Artifact content may contain credentials or private paths. Selection is ledger-bound, content never enters logs or errors, and exported files use mode `0600`. The resolver must verify digests before returning bytes and must never treat a caller-supplied path as authority.

## Phase table

| # | Phase | Status | Verification gate |
|---|---|---|---|
| 0 | Add archive-aware resolution and native/standalone CLI review | done (`.venv/bin/python -m pytest tests/test_cli.py tests/test_artifact_access.py tests/test_archive_io.py -q`; full suite, lint, build, release checks, fresh-wheel list/show/export, and isolated native plugin probe pass) | `pytest tests/test_cli.py tests/test_artifact_access.py tests/test_archive_io.py -q` exits 0; active/archive bytes match and native/standalone commands return byte-identical JSON with equivalent exit codes |

Mark a phase `in-progress` while running it, `done (<evidence>)` once its gate passes, `pending` otherwise.

## Phase 0 — Add archive-aware resolution and native/standalone CLI commands

**Goal:** Let a local operator list, inspect, and export exact workflow evidence through equivalent native and standalone commands.

Steps:

1. Read contract Phase 1, P0205 and P0100 completion evidence, and the CLI conventions named there.
2. Add a bounded verified member-read primitive to `daidala.archive_io`, then extend the P0205 resolver with an injected exact-`artifact_id` archive lookup and read/export through that primitive; do not introduce a second tar implementation, pre-empt P0310's curator-state layout, or change ledger identity.
3. Add exact selectors and JSON projections for list/show/export without accepting a filesystem path.
4. Keep list JSON machine-readable and diagnostics content-free; keep text display at the 1 MiB document bound, permit digest-verified exports up to the shared archive per-file bound, and write exports atomically at mode `0600` without overwrite by default.
5. Prove active and archived bytes are equivalent and native/standalone commands have byte-identical JSON, equivalent exit codes, and matching error classes.
6. Update CLI documentation/DOX owned by the changed paths.

Verification gate: The Phase 0 table command exits 0 and export bytes match the resolver's verified bytes.

## Out of scope

- Do not archive, pin, restore, schedule, or delete artifact bytes.
- Do not duplicate or weaken P0205 resolver checks.
- Do not add dashboard review controls.
- Do not change historical ledger paths or digests.
