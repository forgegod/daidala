# Daidala dashboard constraints and configuration verification

**Plan ID:** daidala-dashboard-constraints-and-verification

**Execution slot:** P0230

**Created:** 2026-07-23

**Depends on:** daidala-dashboard-checkouts-and-project-links

**Split from:** daidala-dashboard-user-config-packs-start-constraints-github-links

**Plan family:** daidala-dashboard

**Entry checkpoint:** P0220 completed with checkout/link state, mutation surfaces, and report-only status verification

**Context sources:** [shared goal and current state](daidala-dashboard-execution-contract.md#goal), [browser mutation allowlist and persisted configuration decisions](daidala-dashboard-execution-contract.md#operator-pinning), [implementer discipline](daidala-dashboard-execution-contract.md#implementer-discipline), and detailed [contract Phase 7](daidala-dashboard-execution-contract.md#phase-7-constraint-authoring-ui), [contract Phase 8](daidala-dashboard-execution-contract.md#phase-8-configuration-verification-panel), and [contract Phase 9](daidala-dashboard-execution-contract.md#phase-9-dox-pass-and-verification)

**Produces:** schema-aware constraint authoring, a read-only configuration verification panel, synchronized DOX/tool/route inventories, and complete repository/package/browser verification evidence for the dashboard family

**Status:** pending — blocked until P0220 completes and human implementation approval is recorded

## Goal

Finish the dashboard family with bounded constraint authoring, read-only configuration verification, and the full DOX, package, and browser gate without turning verification into a mutation surface.

## Current state

- P0220 produces the persisted checkout, registration-derived, and Projects-link state consumed by the verification panel.
- The existing constraints service owns parse, preview, digest, and replace semantics; this plan adds a guided presentation rather than a second constraints model.
- Every earlier unit performs same-commit DOX updates; the final phase checks cross-tree consistency rather than deferring ownership documentation.
- The shared contract pins the closed mutation allowlist and exact verification command order.

## Phase table

| # | Phase | Status | Verification gate |
|---|---|---|---|
| 0 | Add constraint authoring UI | pending | The modal provides a schema-validated YAML editor, live preview, error list, and digest impact through the existing preview endpoint; replace semantics remain unchanged |
| 1 | Add configuration verification panel | pending | The panel remains read-only and verifies persisted root, TTL, registration, checkout, and Projects-link state without exposing secrets/private destinations or supervising a workflow |
| 2 | Reconcile DOX and run full verification | pending | Owning AGENTS files and `plugin.yaml` are current; all root verification commands pass; the intended-path diff contains only approved implementation and plan-progress changes |

Mark a phase `in-progress` while running it, `done (<evidence>)` once its gate passes, `pending` otherwise.

## Phase 0 — Add constraint authoring UI

**Goal:** Add a guided schema-aware editor over the existing constraint preview and replace services.

Steps:

1. Read contract Phase 7, `dashboard/AGENTS.md`, `daidala/AGENTS.md`, and the linked constraint documentation.
2. Implement the schema-aware YAML editor, live preview, error rendering, and digest-impact display through the existing preview endpoint.
3. Keep replacement on the existing preview/confirm path and do not add a new parser or authority model.
4. Extend route inventory and same-commit DOX contracts.
5. Run the focused API, asset, constraint, and disposable-browser gates from the contract.

Verification gate: The Phase 0 table predicate and detailed Phase 7 contract gates pass.

## Phase 1 — Add the configuration verification panel

**Goal:** Render a read-only, profile-safe projection of the complete Daidala dashboard configuration and cross-object invariants.

Steps:

1. Read contract Phase 8 and the exact persisted-state decisions linked above.
2. Project root, TTL mode, registrations, checkout ownership/freshness, and Projects-link verification without returning credential values or private destinations.
3. Keep the panel read-only; it must not supervise workflows or provide a general mutation path.
4. Update route inventory and owning DOX contracts in the same change.
5. Run focused API, asset, and disposable-browser verification from the contract.

Verification gate: The Phase 1 table predicate passes and every failed invariant is visible without exposing protected values.

## Phase 2 — Reconcile DOX and run full verification

**Goal:** Prove the complete dashboard family is internally consistent, packaged, installable, and operational through supported Hermes browser boundaries.

Steps:

1. Read contract Phase 9 and re-check every changed path against its full AGENTS chain.
2. Remove stale ownership, route, tool, setup, and operator documentation; update `plugin.yaml` inventory where required.
3. Run the exact verification sequence pinned by contract Phase 9 without reordering it.
4. Exercise the registration-free host and fresh disposable fixture through the complete browser journey, then tear down fixture-owned state.
5. Record only durable gate evidence in this active plan; do not create temporary plan fragments, findings notes, or diff snapshots.

Verification gate: Every Phase 2 table predicate and exact contract Phase 9 check passes.

## Out of scope

- Do not add a second constraint schema, parser, or replacement authority.
- Do not expose tokens, credential values, notification targets, or arbitrary filesystem paths.
- Do not use the final DOX phase to postpone contract updates required by earlier implementation commits.
- Do not begin artifact review or curation; P0300 owns that plan family.
