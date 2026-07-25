# Daidala deterministic artifact curation

**Plan ID:** daidala-artifact-curation

**Execution slot:** P0310

**Created:** 2026-07-24

**Depends on:** daidala-artifact-review-access-and-curation

**Split from:** daidala-artifact-review-access-and-curation

**Plan family:** daidala-artifact-review

**Entry checkpoint:** P0300 completed with exact-ID active/archive resolution and equivalent native/standalone review commands; P0100 archive I/O is available

**Context sources:** [artifact current state](daidala-artifact-review-execution-contract.md#current-state), [risk call-out](daidala-artifact-review-execution-contract.md#risk-call-out), detailed [contract Phase 2](daidala-artifact-review-execution-contract.md#phase-2-add-deterministic-artifact-curator-archive-pin-and-restore), [P0100 archive contract](P0100-daidala-shared-archive-io.md), plus `AGENTS.md`, `daidala/AGENTS.md`, and `tests/AGENTS.md`

**Produces:** deterministic active/stale/archived classification, pin/unpin, verified archive-before-remove, safe restore, and idempotent recovery without automatic deletion

**Status:** pending — blocked until P0300 completes and human implementation approval is recorded

## Goal

Move eligible terminal-workflow artifact bytes into verified recoverable profile-local archives while preserving immutable ledger identity and ensuring interruption can never remove the last verified copy.

## Current state

- P0300 provides ledger-owned exact-ID resolution across active and archived storage.
- P0100 provides policy-neutral safe archive creation, manifest verification, and extraction.
- The policy ledger's historical artifact paths and digests remain immutable.
- No artifact-specific eligibility, pinning, restore, or curation state exists.

## Risk call-out

The mandatory mutation order is classify, archive, verify manifest and bytes, publish archive state, then remove eligible source bytes. Failures must leave verified active bytes, a verified archive, or both. Restore writes only to a bounded profile-local restore root, never the historical source path. No policy may automatically delete archives.

## Phase table

| # | Phase | Status | Verification gate |
|---|---|---|---|
| 0 | Add deterministic artifact curator, archive, pin, and restore | pending | `pytest tests/test_artifact_curator.py tests/test_archive_io.py tests/test_store.py -q` exits 0; failure injection proves verified archive-before-remove and idempotent recovery |

Mark the phase `in-progress` while running it, `done (<evidence>)` once its gate passes, `pending` otherwise.

## Phase 0 — Add deterministic artifact curation

**Goal:** Implement deterministic eligibility, pinning, archive, restore, and recovery policy over the verified resolver and shared archive helper.

Steps:

1. Read contract Phase 2, the entire risk call-out, P0100's completion evidence, and linked AGENTS files.
2. Implement the strict profile-local curator policy/state schemas, deterministic `active → stale → archived` classification, and pin/unpin behavior.
3. Use only `daidala.archive_io` for archive and restore mechanics; keep eligibility, retention, roots, and authorization in the curator.
4. Enforce archive/manifest verification before source removal and bounded restore without ledger mutation.
5. Add failure-injection, interrupted-retry, tamper, pin, terminal-state, idempotency, and mode tests; update DOX ownership in the same change.

Verification gate: The table command exits 0 and injected interruption at every mutation boundary preserves at least one verified copy.

## Out of scope

- Do not automatically delete archives or infer eligibility with an LLM.
- Do not rewrite historical ledger paths or restore into them.
- Do not add dashboard controls or cron scheduling; P0320 owns those integration surfaces.
