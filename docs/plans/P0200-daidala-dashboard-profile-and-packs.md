# Daidala dashboard profile and pack readiness

**Plan ID:** daidala-dashboard-user-config-packs-start-constraints-github-links

**Execution slot:** P0200

**Created:** 2026-07-23

**Depends on:** none

**Plan family:** daidala-dashboard

**Entry checkpoint:** none — this is the first dashboard-family execution unit

**Context sources:** [UX concept and design contract](P0250-daidala-dashboard-ux-concept.md), [shared goal and current state](daidala-dashboard-execution-contract.md#goal), [operator pinning](daidala-dashboard-execution-contract.md#operator-pinning), [operator runbook coverage](daidala-dashboard-execution-contract.md#operator-runbook-coverage), [operator-visible precondition](daidala-dashboard-execution-contract.md#operator-visible-precondition), [implementer discipline](daidala-dashboard-execution-contract.md#implementer-discipline), [risk call-out](daidala-dashboard-execution-contract.md#risk-call-out), [runbook install and enable](../07-runbook.md#install-and-enable), [runbook pack diagnosis](../07-runbook.md#diagnose-prerequisites), and detailed [contract Phase 0](daidala-dashboard-execution-contract.md#phase-0-create-daidala-dashboard-profile-install-daidala-verify-the-dashboard-mount) and [contract Phase 1](daidala-dashboard-execution-contract.md#phase-1-pack-browser-and-readiness-actions)

**Produces:** a verified registration-free `daidala-dashboard` host, a disposable stateful browser fixture recipe, and Config → Packs list/validate/readiness/external-skill-install UI backed by installed Daidala services

**Status:** pending — context split is complete; human approval is required before implementation

## Goal

Establish an isolated, verified dashboard host and implement the runbook's Config → Packs list, validate, check, and dry-run-first external-skill install surface so later dashboard units start from a known mounted plugin and supported Hermes React SDK boundary.

## Current state

- The `daidala-dashboard` host profile does not exist and must remain registration-free.
- Stateful browser verification uses a fresh `daidala-dashboard-fixture-<UTC timestamp>` profile and an isolated OS-assigned dashboard port.
- The existing dashboard has pack inventory routes but not the complete browser readiness and confirmed external-installation flow.
- The shared execution contract owns the exact CLI syntax, fixture teardown, SDK boundary, route allowlist, and detailed acceptance steps linked above.

## Phase table

| # | Phase | Status | Verification gate |
|---|---|---|---|
| 0 | Create the registration-free dashboard profile and disposable fixture, install Daidala, and verify both mounts | pending | SPA, manifest, and packaged asset checks pass; authenticated health identifies Daidala; the fixture has independent non-secret state, passes the stateful browser gate, and is deleted after its owned process stops |
| 1 | Add pack browser and readiness actions | pending | Both packs list and validate; readiness and check/install-plan actions use installed services; external installation requires preview and confirmation; focused dashboard tests pass |

Mark a phase `in-progress` while running it, `done (<evidence>)` once its gate passes, `pending` otherwise.

## Phase 0 — Create and verify the isolated dashboard profiles

**Goal:** Produce a mounted, registration-free dashboard host and a repeatable disposable fixture boundary without changing repository source.

Steps:

1. Read the exact Phase 0 contract and every linked AGENTS file before invoking Hermes.
2. Follow the pinned `hermes profile`, local-checkout symlink, isolated dashboard, authenticated health, and fixture seeding commands from the contract; do not substitute `hermes-vc` or `daidala-self-improvement`.
3. Capture operational evidence only under the contract's resolved state-directory location, never in the repository, `/tmp`, or a profile-private plan.
4. Stop the exact fixture-owned process before deleting the fixture profile; leave the registration-free host installed for Phase 1.
5. Record command evidence in this phase row only after every predicate passes.

Verification gate: The Phase 0 table predicate passes using the exact host/fixture recipe in the shared contract.

## Phase 1 — Add pack browser and readiness actions

**Goal:** Let the mounted dashboard render and validate both packs, explain readiness, run checks, and preview then confirm external skill installation through bounded installed services.

Steps:

1. Read the exact Phase 1 contract, `dashboard/AGENTS.md`, and `tests/AGENTS.md`.
2. Implement the contract's Config → Packs list projection, explicit validation, readiness details, check action, install-plan preview, and literal-confirmation apply path without adding a general dispatch endpoint.
3. Keep external-skill installation separate from bundled-skill readiness and preserve the closed route inventory.
4. Update the nearest AGENTS contracts in the same change when routes or ownership change.
5. Run the focused API, asset, and browser gates named by the contract.

Verification gate: The Phase 1 table predicate and its focused tests pass against the isolated dashboard host.

## Out of scope

- Do not create registrations or workflow state in the long-lived `daidala-dashboard` host.
- Do not start a Daidala workflow; the next plan owns setup and supervision.
- Do not add pack enable/disable state, arbitrary source entry, or uploaded pack
  archives. Workflow selection activates one installed ready definition; this
  phase installs only a definition's exact pinned external skills.
- Do not implement checkout, GitHub Projects, constraints, or artifact-review surfaces.
- Do not commit, push, or begin implementation without the mandatory human approval gate.
