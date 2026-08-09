# Daidala deterministic artifact curation

**Plan ID:** daidala-artifact-curation

**Execution slot:** P0310

**Created:** 2026-07-24

**Depends on:** daidala-artifact-review-access-and-curation

**Split from:** daidala-artifact-review-access-and-curation

**Plan family:** daidala-artifact-review

**Entry checkpoint:** P0205 completed active exact-ID resolution; P0300 completed archive-aware resolution and equivalent native/standalone review commands; P0100 archive I/O is available transitively

**Context sources:** [artifact current state](daidala-artifact-review-execution-contract.md#current-state), [risk call-out](daidala-artifact-review-execution-contract.md#risk-call-out), detailed [contract Phase 2](daidala-artifact-review-execution-contract.md#phase-2-add-deterministic-artifact-curator-archive-pin-and-restore), [P0100 archive contract](P0100-daidala-shared-archive-io.md), plus `AGENTS.md`, `daidala/AGENTS.md`, and `tests/AGENTS.md`

**Produces:** deterministic active/stale/archived classification, pin/unpin, verified archive-before-remove, safe restore, and idempotent recovery without automatic deletion

**Status:** complete — Phase 0 implementation and verification gate passed

## Goal

Move eligible terminal-workflow artifact bytes into verified recoverable profile-local archives while preserving immutable ledger identity and ensuring interruption can never remove the last verified copy.

## Current state

- The profile-local curator defaults to disabled and records strict compare-and-swap lifecycle, pin, and archive state.
- Terminal eligibility fails closed over ledger evidence, worktree ownership, pending revision and approval state, and all persisted Kanban card references.
- Archive publication, curator-manifest publication, state publication, and source cleanup are retry-safe and covered by failure injection.
- Exact artifact access resolves verified archived members while preserving immutable ledger paths and digests.
- Restore publishes verified bytes only under the bounded profile-local recovery root and pins the workflow without mutating historical ledger paths.

## Risk call-out

The mandatory mutation order is classify, archive, verify manifest and bytes, publish archive state, then remove eligible source bytes. Failures must leave verified active bytes, a verified archive, or both. Restore writes only to a bounded profile-local restore root, never the historical source path. No policy may automatically delete archives.

## Phase table

| # | Phase | Status | Verification gate |
|---|---|---|---|
| 0 | Add deterministic artifact curator, archive, pin, and restore | done (gate passed; every curator publication/cleanup boundary converges without losing the last verified copy) | `pytest tests/test_artifact_curator.py tests/test_archive_io.py tests/test_store.py -q` exits 0; failure injection proves verified archive-before-remove and idempotent recovery |

Mark the phase `in-progress` while running it, `done (<evidence>)` once its gate passes, `pending` otherwise.

## Phase 0 — Add deterministic artifact curation

**Goal:** Implement deterministic eligibility, pinning, archive, restore, and recovery policy over the verified resolver and shared archive helper.

Steps:

1. Read contract Phase 2, the entire risk call-out, P0100's completion evidence, and linked AGENTS files.
2. Implement the strict profile-local curator policy/state schemas, deterministic `active → stale → archived` classification, and pin/unpin behavior.
3. Use only `daidala.archive_io` for archive and restore mechanics; keep eligibility, retention, roots, and authorization in the curator.
4. Enforce archive/manifest verification before source removal and restore only below `<resolved-data-root>/daidala/artifact-restores/<workflow-id>/<archive-id>/`, never into an immutable historical ledger path or by mutating the ledger.
5. Add failure-injection, interrupted-retry, tamper, pin, terminal-state, idempotency, and mode tests; update DOX ownership in the same change.

Verification gate: The table command exits 0 and injected interruption at every mutation boundary preserves at least one verified copy.

## Changes

| Date | From | To | Reason |
|---|---|---|---|
| 2026-08-10 | Phase 0 pending | Phase 0 done | Implemented deterministic curation and archive-aware access; the focused gate and failure-injection recovery checks pass. |

## Out of scope

- Do not automatically delete archives or infer eligibility with an LLM.
- Do not rewrite historical ledger paths or restore into them.
- Do not add dashboard controls or cron scheduling; P0320 owns those integration surfaces.
