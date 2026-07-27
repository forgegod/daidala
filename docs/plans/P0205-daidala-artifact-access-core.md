# Daidala ledger-bound artifact access core

**Plan ID:** daidala-artifact-access-core

**Execution slot:** P0205

**Created:** 2026-07-25

**Depends on:** none

**Split from:** daidala-artifact-review-access-and-curation

**Plan family:** daidala-artifact-review

**Entry checkpoint:** none — the current policy ledger and immutable active artifact references are sufficient inputs

**Context sources:** [artifact current state](daidala-artifact-review-execution-contract.md#current-state), [risk call-out](daidala-artifact-review-execution-contract.md#risk-call-out), [approval summary contract](daidala-dashboard-execution-contract.md#approval-summary-and-escaped-text-contract), detailed [contract Phase 0](daidala-artifact-review-execution-contract.md#phase-0-add-the-ledger-owned-artifact-catalog-and-resolver), plus `AGENTS.md`, `daidala/AGENTS.md`, and `tests/AGENTS.md`

**Produces:** a profile-safe exact-ID catalog, a strict source-bound plan approval summary, and a digest-verifying active text/export resolver consumed by dashboard plan approval and later CLI, archive, curation, and general artifact-review plans

**Status:** complete — Phase 0 implementation and verification gate passed

This plan produces one ledger-bound artifact catalog and resolver that can show the exact verified plan body plus its source-bound proposed-change summary before a human approval action without accepting arbitrary filesystem paths or exposing profile-local paths to the browser.

## Current state

- `hermes daidala status` returns artifact paths and digests, but no bounded artifact-read service exists (`daidala/cli.py:711-722`, `daidala/state.py:910-932`).
- The current dashboard pending-decision item renders rationale but not plan bytes or the complete approval tuple (`dashboard/dist/index.js:149-166`).
- The approval recommendation carries the current plan and constraint identity but has no Kanban card (`daidala/recommendations.py:175-190`).
- The dashboard must remain a Hermes-hosted plugin surface; Daidala must not add a server, daemon, direct Kanban-database read, or arbitrary-path endpoint.

## Risk call-out

Plan and evidence artifacts may contain credentials or private paths. The resolver must authorize only immutable ledger references, reject traversal and symlinks, verify the recorded digest before returning bytes, enforce the existing document bound, and keep content out of logs and errors. Approval must remain disabled when the exact plan bytes are missing, malformed, oversized, binary, stale, or digest-mismatched.

## Phase table

| # | Phase | Status | Verification gate |
|---|---|---|---|
| 0 | Add the active ledger-owned artifact catalog and resolver | done (`pytest tests/test_artifact_access.py tests/test_store.py tests/test_workflow.py tests/test_tools.py tests/test_worker_contract.py -q`; `lefthook validate`; `pytest`; `ruff check .`; both pack validations; build, Twine, and release-content checks all exited 0) | `pytest tests/test_artifact_access.py tests/test_store.py tests/test_workflow.py tests/test_tools.py tests/test_worker_contract.py -q` exits 0 and proves exact current-plan text and summary resolution, arbitrary-path rejection, digest verification, and no read-time ledger mutation |

Mark the phase `in-progress` while running it, `done (<evidence>)` once its gate passes, `pending` otherwise.

## Phase 0 — Add the active ledger-owned artifact catalog and resolver

**Goal:** Give every review surface one profile-safe service that resolves exact verified artifact bytes by opaque ledger identity, with the current plan as the required approval-gate vertical slice.

Steps:

1. Read contract Phase 0, the complete risk call-out, and the linked AGENTS files.
2. Implement the exact artifact identity, active catalog, path-containment, symlink, size, binary-text, and digest contracts in `daidala/artifact_access.py`.
3. Extend `daidala/state.py`, `daidala/service.py`, `daidala/schemas.py`, and `daidala/tools.py` so plan submission and `ArtifactReference` carry the shared contract's strict `approval_summary`. Canonicalize it, bind it to the server-computed `plan.md` digest, retain its SHA-256 digest, and record the plan reference plus summary in one ledger update after writing the immutable plan bytes. A failed ledger update may leave only an unreferenced file, never a partially authoritative packet. The existing plan worker may generate the summary; Daidala validates structure and identity but performs no model call.
   The public tool schema declares the exact bounded summary object; the service
   enforces that it is required only for `plan` and rejected for other stages so
   provider-dependent conditional JSON-Schema keywords are not part of the tool
   registration boundary.
4. Update `daidala/skills/orchestrate/SKILL.md` to require the plan worker to submit the evidence-derived summary with `plan.md`; invalid structured output blocks the handoff rather than falling back to server-generated prose.
5. Make `WorkflowService` expose metadata listing, bounded verified text reads, the bound summary, and verified export for active ledger artifacts without importing dashboard or Hermes internals and without changing unrelated status fields.
6. Pin a current-plan lookup to the exact workflow, policy revision, plan revision, stage, artifact digest, and summary digest; return a classified failure rather than an approval packet when any identity or verification check fails. New plan submission requires the summary. Historical summary-less artifacts remain readable but are not approvable and must use the normal plan-revision path.
7. Add focused tests for summary structure/bounds/canonical identity, source-digest binding, tool-schema rejection, worker handoff requirements, current and superseded plans, legacy summary-less plans, every active ledger reference kind, missing/corrupt bytes, traversal/symlink escape, stale or forged IDs, binary and size bounds, export collision/mode, and no read-time ledger mutation.
8. Update `daidala/AGENTS.md` ownership in the implementation change; do not add dashboard routes or approval mutation in this phase.

Verification gate: The table command exits 0; a synthetic current plan and its canonical summary can be read only through their exact bound identities, and every unverified path, summary, or byte stream fails closed without exposing content.

## Out of scope

- Do not add CLI commands; `P0300-daidala-artifact-access-and-cli.md` owns native and standalone review/export commands.
- Do not add dashboard rendering or approval mutation; `P0210-daidala-dashboard-setup-and-supervision.md` consumes this resolver.
- Do not archive, curate, delete, or restore artifact bytes.
