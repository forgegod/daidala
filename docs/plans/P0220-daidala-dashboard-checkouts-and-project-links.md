# Daidala dashboard checkouts and GitHub Projects links

**Plan ID:** daidala-dashboard-checkouts-and-project-links

**Execution slot:** P0220

**Created:** 2026-07-23

**Depends on:** daidala-dashboard-review-disposition, daidala-dashboard-recovery-and-cancellation, daidala-clean-host-pack-cli, daidala-shared-archive-io

**Split from:** daidala-dashboard-user-config-packs-start-constraints-github-links

**Plan family:** daidala-dashboard

**Entry checkpoint:** P0212, P0214, and P0215 completed the independently verified review-disposition, recovery/cancellation, and clean-host pack CLI slices; P0100 completed with policy-neutral safe archive I/O

**Context sources:** [UX concept and design contract](P0250-daidala-dashboard-ux-concept.md), [profile-local state and authority boundaries](daidala-dashboard-execution-contract.md#operator-pinning), [checkout location decision](daidala-dashboard-execution-contract.md#checkout-location-decision), [stale-checkout policy](daidala-dashboard-execution-contract.md#stale-checkout-policy), [filesystem risks](daidala-dashboard-execution-contract.md#risk-call-out), [implementer discipline](daidala-dashboard-execution-contract.md#implementer-discipline), and detailed [contract Phase 4](daidala-dashboard-execution-contract.md#phase-4-checkout-configuration-github-projects-v2-link-model), [contract Phase 5](daidala-dashboard-execution-contract.md#phase-5-github-projects-v2-link-ui), and [contract Phase 6](daidala-dashboard-execution-contract.md#phase-6-manual-checkout-refresh-ttl-policy-and-report-only-cron-hook)

**Produces:** strict profile-local checkout/link stores, verified Projects v2 link UI, collision-safe manual checkout refresh and backup/prune actions, and a report-only cron-compatible status tool

**Status:** Phase 0 done (2026-08-09: 542 tests, `ruff`, `lefthook validate`, pack validation, build and release-content checks); Phase 1 done (2026-08-09: 547 tests, the same repository gate, and an isolated Hermes browser fixture); Phase 2 done (2026-08-09: 568 tests via `python -m pytest`, `ruff`, `lefthook validate`, pack/build/release checks, and isolated Hermes dashboard and directory-plugin probes)

## Goal

Implement the profile-local checkout and GitHub Projects configuration vertical slice, including bounded manual refresh and backup operations, without mutating registration identity or permitting unattended checkout changes.

## Current state

- P0210, P0212, P0214, and P0215 establish the dashboard request/action patterns, clean-host pack boundary, and closed route inventory.
- P0100 owns verified tar/gzip creation, extraction, and manifest I/O; this plan consumes it and must not create another archive implementation.
- Registrations already own project identity, checkout path, verified remote, and intake credential alias.
- The shared contract pins strict mode-`0600` stores, root-change blocking, owner markers, freshness receipts, preview/confirmation, persistent backup retention, and report-only cron behavior.

## Risk call-out

Checkout replacement can destroy local work if ownership or Git status is classified incorrectly. Every mutating path must validate the registration-derived path, symlink-free containment, owner marker, origin, freshness receipt, and tracked/untracked/ignored state before confirmation. `backup-then-wipe` must verify the P0100 archive before swapping; failures leave the old checkout intact. Named backup pruning is explicit and never automatic.

## Phase table

| # | Phase | Status | Verification gate |
|---|---|---|---|
| 0 | Add checkout configuration and GitHub Projects v2 link model | done (2026-08-09; 542 tests, `ruff`, `lefthook validate`, pack validation, build/release checks) | Strict mode-`0600` stores enforce collision safety, root-change blocking, registration equality, and verified owner/number/node-ID links; focused model tests pass |
| 1 | Add GitHub Projects v2 link UI | done (2026-08-09; full repository gate; isolated browser fixture verified the path-free no-link state and bounded 409 preview block) | The UI manages one verified link per registered project; mutation requires a fresh bounded GitHub read, matching preview digest, and literal confirmation; token values never cross the boundary |
| 2 | Add manual checkout refresh, TTL policy, backup pruning, and report-only cron hook | done (2026-08-09; 568 tests via `python -m pytest`, repository gate, and isolated dashboard/directory-plugin probes) | Checkout inventory and confirmed actions validate path, marker, origin, receipt, and Git status; ignored-only files require backup mode; TTL defaults disabled; the cron-compatible tool is read-only |

Mark a phase `in-progress` while running it, `done (<evidence>)` once its gate passes, `pending` otherwise.

## Phase 0 — Add checkout and Projects link models

**Goal:** Add strict, independently locked profile-local stores and deterministic validation services for checkout policy and Projects v2 links.

Steps:

1. Read contract Phase 4; Q1, **Checkout location decision**; Q2, **Stale-checkout policy**; `daidala/AGENTS.md`; and `tests/AGENTS.md`.
2. Implement the strict stores and services exactly as specified, reusing `_require_slug`, `parse_strict_yaml`, and existing registration facts.
3. Reject root replacement while owned checkouts exist and reject registration/configuration path mismatches; never rewrite registration state.
4. Derive the intake alias and capability evidence during link verification without accepting or persisting token values.
5. Pre-register new module ownership in DOX and run all focused model/prerequisite tests named by the contract.

Verification gate: The Phase 0 table predicate and detailed contract gates pass.

## Phase 1 — Add the Projects v2 link UI

**Goal:** Expose bounded list, preview, verify, add, edit, and delete operations for one Projects v2 link per registered project, with path-free registration context.

Steps:

1. Read contract Phase 5, its mutation risk, and `dashboard/AGENTS.md`.
2. Map missing or malformed profile credential bindings to a bounded prerequisite response rather than an internal server failure, so the UI can distinguish a blocked GitHub read without exposing a credential value.
3. Implement the list/read model and fresh bounded GitHub verification before any mutation.
4. Require matching preview digest and literal `confirm: true`; keep repository identity, verified remote, intake alias, and checkout-configuration match display-only and registration-derived. Never render or return a checkout path; filesystem checkout state remains Phase 2 work.
5. Extend the closed route inventory and same-commit DOX contracts.
6. Run focused API, asset, and disposable-browser verification from the contract.

Atomicity: the dependency-free bundle's request helpers, configuration tab, link
panel, stylesheet, asset contract tests, and plan/contract wording land in one
checkpoint. Separating them would leave either an unreachable UI surface or an
unreviewed mutation route in the shipped browser asset.

Verification gate: The Phase 1 table predicate passes without exposing secrets, returning an internal server failure for a missing binding, or altering project-cycle admission.

## Phase 2 — Add manual refresh and report-only status

**Goal:** Add deterministic checkout inventory, adopt, refresh, backup/prune, policy, and report-only status surfaces with denied-by-default mutation.

Steps:

1. Read contract Phase 6, the complete filesystem risk section, P0100's completed `Produces` evidence, and linked AGENTS files.
2. Replace the Phase 0 provisional `manual`/`ttl` mode vocabulary with the exact `disabled`/`wipe-if-clean`/`backup-then-wipe` policy before exposing any Phase 2 surface; reject obsolete persisted values rather than translating them.
3. Replace the Phase 0 text owner-marker implementation with the contract's strict JSON witness before implementing freshness receipts, preflight, the three exact policy modes, clone/swap recovery, and named backup pruning.
4. Use `daidala.archive_io` for backup creation and verification; do not duplicate tar/gzip policy.
5. Register `daidala_checkouts_status` as report-only and ensure cron can invoke only that non-mutating surface.
6. Update route/tool inventories and DOX in the same commit, then run the complete focused tests and disposable-browser gates.

Verification gate: The Phase 2 table predicate passes, failed clone/archive paths preserve the original checkout, and report-only execution cannot mutate state.

## Out of scope

- Do not rewrite registrations, infer vault entries, or persist credential values.
- Do not auto-prune backups or perform unattended TTL refresh.
- Do not invoke `project-cycle admit` from link changes.
- Do not implement constraint/configuration or artifact-curation UI.
