# Daidala dashboard profile and pack readiness

**Plan ID:** daidala-dashboard-user-config-packs-start-constraints-github-links

**Execution slot:** P0200

**Created:** 2026-07-23

**Depends on:** none

**Plan family:** daidala-dashboard

**Entry checkpoint:** none — this is the first dashboard-family execution unit

**Context sources:** UX design contract identity and approved status (`P0250-daidala-dashboard-ux-concept.md:1-19`), operator-pinned navigation and pack-readiness decisions (`P0250-daidala-dashboard-ux-concept.md:29-103`), P0200 use cases and cross-cutting invariants (`P0250-daidala-dashboard-ux-concept.md:105-124,172-180`), Config → Packs information architecture and content patterns (`P0250-daidala-dashboard-ux-concept.md:249-269,274-329`), [shared goal and current state](daidala-dashboard-execution-contract.md#goal), [operator pinning](daidala-dashboard-execution-contract.md#operator-pinning), [operator runbook coverage](daidala-dashboard-execution-contract.md#operator-runbook-coverage), [operator-visible precondition](daidala-dashboard-execution-contract.md#operator-visible-precondition), [implementer discipline](daidala-dashboard-execution-contract.md#implementer-discipline), [risk call-out](daidala-dashboard-execution-contract.md#risk-call-out), [runbook install and enable](../07-runbook.md#install-and-enable), [runbook pack diagnosis](../07-runbook.md#diagnose-prerequisites), and detailed [contract Phase 1](daidala-dashboard-execution-contract.md#phase-1-pack-browser-and-readiness-actions)

**Produces:** a verified registration-free `daidala-dashboard` host, a disposable stateful browser fixture recipe, and Config → Packs list/validate/readiness/read-only per-stage skill-content/external-skill-install UI backed by installed Daidala services

**Status:** Phase 0 done; Phase 1 done at feat/dashboard-constraint-revisions (pytest 443 passed, ruff clean, lefthook/build/twine/release-content gates passed, live dashboard render verified)

## Goal

Establish an isolated, verified dashboard host and implement the runbook's Config → Packs list, validate, check, read-only declared-skill content, and dry-run-first external-skill install surface so later dashboard units start from a known mounted plugin and supported Hermes React SDK boundary.

## Current state

- The `daidala-dashboard` host profile does not exist and must remain registration-free.
- Stateful browser verification uses a fresh `daidala-dashboard-fixture-<UTC timestamp>` profile and an isolated OS-assigned dashboard port.
- The existing dashboard has pack inventory routes but not the complete browser readiness and confirmed external-installation flow.
- The shared execution contract owns the exact CLI syntax, fixture teardown, SDK boundary, route allowlist, and detailed acceptance steps linked above.

## Phase table

| # | Phase | Status | Verification gate |
|---|---|---|---|
| 0 | Create the registration-free dashboard profile and disposable fixture, install Daidala, and verify both mounts | done (Hermes v0.19.0/`3ef6bbd2`; compatibility, host/fixture browser, authority, teardown, and repository-status gates passed) | An exact supported Hermes identity hosts both processes; SPA GET, manifest, and packaged asset checks pass; authenticated health identifies Daidala; the registration-free host has no workflow records, registrations, credentials, or notification authority; the fixture has independent non-secret state, passes the stateful browser gate, and is deleted after its owned process stops |
| 1 | Add pack browser and readiness actions | done (Hermes v0.19.0; both packs list/validate via CLI and dashboard; six-stage declared-skill content, readiness, and preview/confirm install surface behind `daidala/pack_service.py`; `tests/test_pack_service.py`, `tests/test_dashboard_api.py`, `tests/test_dashboard_assets.py` green; live isolated dashboard rendered both packs and all six stages with no console errors) | Both packs list and validate; every lifecycle stage exposes its declared skill metadata and exact installed content through a bounded read-only detail; readiness and check/install-plan actions use installed services; external installation requires preview and confirmation; focused dashboard tests pass |

Mark a phase `in-progress` while running it, `done (<evidence>)` once its gate passes, `pending` otherwise.

## Phase 0 — Create and verify the isolated dashboard profiles

**Goal:** Produce a mounted, registration-free dashboard host and a repeatable disposable fixture boundary without changing runtime source.

Steps:

1. Read the exact Phase 0 contract and every linked AGENTS file before invoking Hermes.
2. Follow the pinned exact-host resolution, `hermes profile`, local-checkout symlink, isolated dashboard, authenticated health, and fixture seeding commands from the contract; do not substitute `hermes-vc` or `daidala-self-improvement`, and do not downgrade or mutate the active global Hermes installation.
3. Capture operational evidence only under the contract's resolved state-directory location, never in the repository, `/tmp`, or a profile-private plan.
4. Stop the exact fixture-owned process before deleting the fixture profile; leave the registration-free host installed for Phase 1.
5. Record command evidence in this phase row only after every predicate passes.

Verification gate: The Phase 0 table predicate passes using the exact host/fixture recipe in the shared contract.

## Phase 1 — Add pack browser and readiness actions

**Goal:** Let the mounted dashboard render and validate both packs, explain readiness, read every declared lifecycle skill's exact installed content, run checks, and preview then confirm external skill installation through bounded installed services.

Steps:

1. Read the exact Phase 1 contract, `dashboard/AGENTS.md`, and `tests/AGENTS.md`.
2. Implement the contract's Config → Packs list projection, explicit validation,
   readiness details, all-six-stage read-only detail with declared-skill metadata
   and selected installed `SKILL.md` content, check action, install-plan preview,
   and literal-confirmation apply path without adding a general dispatch endpoint.
   Put the shared typed validation, readiness, bounded-content, preview-digest,
   and confirmed-install boundary in `daidala/pack_service.py`; keep
   `daidala/cli.py` and `dashboard/plugin_api.py` as adapters over it. Cover the
   service in `tests/test_pack_service.py` and the closed browser boundary in
   `tests/test_dashboard_api.py` and `tests/test_dashboard_assets.py`.
   A content request accepts only a selected bundled pack and one of its declared
   skill names, renders literal escaped text within the contract's document bound,
   and returns an unavailable external skill's pinned target/digest instead of a
   path or invented content.
3. Keep external-skill installation separate from bundled-skill readiness and preserve the closed route inventory.
4. Update the nearest AGENTS contracts in the same change when routes or ownership change.
5. Run the focused API, asset, and browser gates named by the contract.

Verification gate: The Phase 1 table predicate and its focused tests pass against the isolated dashboard host. Browser evidence proves each of the six stage rows remains visible, declared-skill selection cannot address an undeclared skill, installed content and observed digest agree, and unavailable external skills do not expose paths or fabricated content.

## Out of scope

- Do not create registrations or workflow state in the long-lived `daidala-dashboard` host.
- Do not start a Daidala workflow; the next plan owns setup and supervision.
- Do not add pack enable/disable state, arbitrary source entry, or uploaded pack
  archives. Workflow selection activates one installed ready definition; this
  phase installs only a definition's exact pinned external skills.
- Do not implement checkout, GitHub Projects, constraints, or artifact-review surfaces.
- Do not push or begin Phase 1 before the approved Phase 0 gate and its plan-status checkpoint hold.
