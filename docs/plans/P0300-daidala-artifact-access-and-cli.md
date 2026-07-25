# Daidala artifact access and CLI review

**Plan ID:** daidala-artifact-review-access-and-curation

**Execution slot:** P0300

**Created:** 2026-07-24

**Depends on:** daidala-dashboard-operator-runbook-parity

**Plan family:** daidala-artifact-review

**Entry checkpoint:** P0240 completed with dashboard operator-runbook parity and full route, package, configuration, and browser gates verified; P0100 archive I/O is available transitively through P0220

**Context sources:** [artifact current state](daidala-artifact-review-execution-contract.md#current-state), [risk call-out](daidala-artifact-review-execution-contract.md#risk-call-out), detailed [contract Phase 0](daidala-artifact-review-execution-contract.md#phase-0-add-the-ledger-owned-artifact-catalog-and-resolver), and [contract Phase 1](daidala-artifact-review-execution-contract.md#phase-1-add-native-and-standalone-cli-reviewexport-commands), plus `AGENTS.md`, `daidala/AGENTS.md`, and `tests/AGENTS.md`

**Produces:** a ledger-owned exact-ID artifact catalog/resolver and byte-equivalent native and standalone list/show/export commands

**Status:** pending — blocked until P0240 completes and human implementation approval is recorded

## Goal

Expose active and archived workflow evidence through exact ledger identity and bounded CLI commands without arbitrary-path reads or changes to immutable ledger records.

## Current state

- Workflow status exposes ledger artifact paths and SHA-256 digests, but no list/show/export command exists.
- Runtime data is profile-local and must resolve through the active Hermes home/profile.
- The dashboard deliberately refuses arbitrary filesystem reads.
- The shared artifact contract owns the exact resolver, selector, output, export, and error semantics.

## Risk call-out

Artifact content may contain credentials or private paths. Selection is ledger-bound, content never enters logs or errors, and exported files use mode `0600`. The resolver must verify digests before returning bytes and must never treat a caller-supplied path as authority.

## Phase table

| # | Phase | Status | Verification gate |
|---|---|---|---|
| 0 | Add the ledger-owned artifact catalog and resolver | pending | `pytest tests/test_artifact_access.py tests/test_store.py tests/test_workflow.py -q` exits 0 and proves exact-ID active/archive resolution without arbitrary-path reads |
| 1 | Add native and standalone CLI review/export commands | pending | `pytest tests/test_cli.py tests/test_artifact_access.py -q` exits 0 and native/standalone commands return byte-identical JSON and equivalent exit codes |

Mark a phase `in-progress` while running it, `done (<evidence>)` once its gate passes, `pending` otherwise.

## Phase 0 — Add the artifact catalog and resolver

**Goal:** Add one profile-safe service that enumerates only ledger-owned evidence and resolves verified active or archived bytes by stable artifact identity.

Steps:

1. Read contract Phase 0, the complete risk call-out, and the linked AGENTS files.
2. Implement the exact identity, catalog, archive-manifest, digest, size-bound, and error contracts from the shared specification.
3. Keep the policy ledger immutable and reject arbitrary paths, traversal, symlinks, malformed manifests, and digest mismatches.
4. Add focused active/archive, duplicate, tamper, and boundary tests.
5. Update `daidala/AGENTS.md` ownership in the same change.

Verification gate: The Phase 0 table command exits 0 and every failure remains metadata-only.

## Phase 1 — Add native and standalone CLI commands

**Goal:** Let a local operator list, inspect, and export exact workflow evidence through equivalent native and standalone commands.

Steps:

1. Read contract Phase 1 and the CLI conventions named there.
2. Add exact selectors and JSON projections for list/show/export without accepting a filesystem path.
3. Keep stdout machine-readable and diagnostics content-free; write exports atomically at mode `0600` without overwrite by default.
4. Prove native and standalone commands have byte-identical JSON, equivalent exit codes, and matching error classes.
5. Update CLI documentation/DOX owned by the changed paths.

Verification gate: The Phase 1 table command exits 0 and export bytes match the resolver's verified bytes.

## Out of scope

- Do not archive, pin, restore, schedule, or delete artifact bytes.
- Do not add dashboard review controls.
- Do not change historical ledger paths or digests.
