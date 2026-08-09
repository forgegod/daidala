# Daidala dashboard operator runbook parity

**Plan ID:** daidala-dashboard-operator-runbook-parity

**Execution slot:** P0240

**Created:** 2026-07-25

**Depends on:** daidala-dashboard-constraints-and-verification

**Plan family:** daidala-dashboard

**Entry checkpoint:** P0230 completed with schema-aware constraint authoring and read-only configuration verification; its phase-local DOX and closed route inventory are current

**Context sources:** [UX concept and design contract](P0250-daidala-dashboard-ux-concept.md), [shared goal and current state](daidala-dashboard-execution-contract.md#goal), [browser mutation and credential boundaries](daidala-dashboard-execution-contract.md#operator-pinning), [operator runbook coverage](daidala-dashboard-execution-contract.md#operator-runbook-coverage), [implementer discipline](daidala-dashboard-execution-contract.md#implementer-discipline), [initialization/live-diagnosis risk](daidala-dashboard-execution-contract.md#risk-call-out), detailed [contract Phase 9](daidala-dashboard-execution-contract.md#phase-9-profile-initialization-and-prerequisite-diagnosis), [contract Phase 10](daidala-dashboard-execution-contract.md#phase-10-operator-runbook-parity-and-host-owned-lifecycle-guidance), and [contract Phase 11](daidala-dashboard-execution-contract.md#phase-11-dox-pass-and-full-verification), plus the runbook sections [Initialize](../07-runbook.md#initialize), [Diagnose prerequisites](../07-runbook.md#diagnose-prerequisites), [Upgrade](../07-runbook.md#upgrade), and [Standalone diagnostics](../07-runbook.md#standalone-diagnostics)

**Produces:** a non-eager profile initialization service and panel, strict local/live prerequisite diagnosis, complete operator-runbook navigation with host-owned lifecycle guidance, and full dashboard-family verification evidence

**Status:** in-progress — Phase 0 complete; Phase 1 pending

## Goal

Complete the dashboard family with dry-run-first profile initialization, strict prerequisite diagnosis, and discoverable equivalents for every `docs/07-runbook.md` operation while leaving plugin installation, enablement, upgrade, restart, and standalone execution on their native host-owned boundaries.

## Current state

- `daidala/cli.py:673-695` implements `init` as dry-run by default and constructs `WorkflowStore` only for `--apply`.
- `daidala/dashboard_backend.py:88-100` eagerly constructs `WorkflowStore`, while `dashboard/plugin_api.py:85-97` reaches that factory from `/health`; a fresh dashboard read can therefore bypass the runbook's explicit initialization boundary.
- `daidala/prerequisites.py:1-180` owns the strict checker, bounded local/live evidence, stable check IDs, and exit semantics already shared by native and standalone `doctor`.
- P0200 owns runbook pack list/validate/check/install; P0210 owns start, reopen/watch, and exact approval; P0212 owns review disposition/revision; P0214 owns recovery and cancellation; P0230 owns read-only configuration verification.
- The shared contract keeps install, enable, upgrade, gateway lifecycle, and standalone execution host-owned because a loaded plugin cannot safely replace or restart itself.

## Risk call-out

Confirmed initialization creates the profile-local Daidala directory and SQLite schema. Preview and health must create nothing; apply requires a fresh canonical digest and literal confirmation and is idempotent once initialized. If apply fails, leave the previous filesystem state visible and do not retry through a stale preview.

Live prerequisite diagnosis may read GitHub, gateway, container, and credential-backed readiness state. It is explicit, bounded, non-mutating, and sanitized; local diagnosis is the default. Never use the persistent self-improvement profile or real controller credentials in browser fixtures.

## Phase table

| # | Phase | Status | Verification gate |
|---|---|---|---|
| 0 | Add profile initialization and prerequisite diagnosis | done (`2026-08-09`: focused CLI/API/asset tests, Ruff, JavaScript syntax, Markdown links, and diff check passed) | `pytest tests/test_cli.py tests/test_dashboard_api.py tests/test_dashboard_assets.py -q` exits 0; health/preview create no schema, confirmed apply is idempotent, and local/live reports preserve strict checker semantics without browser paths or protected values |
| 1 | Add operator runbook parity and host-owned lifecycle guidance | pending | Focused CLI/API/asset tests and `python scripts/check_md_links.py .` exit 0; every runbook section has one dashboard-family owner; no route can install, enable, remove, update, restart, or dispatch arbitrary commands |
| 2 | Reconcile DOX and run full verification | pending | Every root AGENTS.md verification command exits 0; ownership, route, tool, runbook, package, and browser contracts are current; `git diff --check` exits 0 |

Mark a phase `in-progress` while running it, `done (<evidence>)` once its gate passes, `pending` otherwise.

## Phase 0 — Add profile initialization and prerequisite diagnosis

**Goal:** Preserve the runbook's explicit initialization and strict diagnosis semantics through bounded typed services and dashboard routes.

Steps:

1. Read contract Phase 9 and the linked AGENTS files before editing.
2. Extract the profile initialization service, preserve native/standalone `init` output and exit semantics, and remove eager schema creation from dashboard health/read paths.
3. Add preview and confirmed initialization routes/panel with a fresh digest,
   literal confirmation, concurrency safety, and explicit repeated-apply no-op.
   `Open initialization preview` opens a Config → Verification subview, retaining
   that tab context and a back control; its first render is the non-mutating
   preview of target, observed state, effects, digest, and native equivalent.
4. Add the strict prerequisite diagnosis route/panel keyed only by a validated
   registered `project_id`; derive trusted paths server-side and keep `live`
   explicit and bounded. Local is the default report scope rather than a saved
   setting: live-only rows are `not run` and incomplete. `Run live checks` is the
   sole explicit control that requests a bounded non-mutating live report.
5. Extend the closed route inventory, focused CLI/API/asset tests, and same-commit DOX ownership exactly as contract Phase 9 requires.

Verification gate: The Phase 0 table predicate passes, and a fresh fixture proves no read or preview creates profile state before confirmed apply. Browser evidence proves Local does not run live probes, live-only `not run` rows are not treated as passes, the explicit live rerun is sanitized and non-mutating, and initialization preview opens the dedicated subview without creating a schema.

## Phase 1 — Add operator runbook parity and host-owned lifecycle guidance

**Goal:** Make every runbook operation discoverable without turning host-owned plugin or Hermes lifecycle commands into browser mutations.

Steps:

1. Read contract Phase 10 and the complete operator-runbook coverage table.
2. Add the runbook panel and sanitized host/profile identity projection; link each operation to its owning dashboard surface.
3. Render exact install/enable and upgrade/post-upgrade commands as guidance only; add no execute, plugin-management, gateway-restart, or generic dispatch route.
4. Make resume reopen an exact existing workflow and continue read-only polling without invoking start.
5. Extend native/standalone parity and runbook-coverage tests, update `docs/07-runbook.md` with concise dashboard equivalence, and complete the disposable-fixture journey.

Verification gate: The Phase 1 table predicate passes; every `docs/07-runbook.md` section is covered or explicitly host-owned, and browser evidence proves the bounded lifecycle journey.

## Phase 2 — Reconcile DOX and run full verification

**Goal:** Close the dashboard family with current ownership contracts and complete deterministic, package, link, compatibility, and browser evidence.

Steps:

1. Read contract Phase 11 and re-check every changed path against its full AGENTS chain.
2. Remove stale ownership, route, tool, setup, runbook, and operator text; update `plugin.yaml` inventory only where runtime registration changed.
3. Run the exact root verification sequence pinned by contract Phase 11 without reordering it.
4. Review final status against the P0200 baseline and retain only durable evidence in this active plan; do not create temporary plan fragments or tracked browser artifacts.

Verification gate: The Phase 2 table predicate and every exact contract Phase 11 gate pass.

## Out of scope

- Executing plugin install, enable, remove, update, reload, Hermes restart, or gateway lifecycle commands from the dashboard.
- Accepting arbitrary project-manifest, registration, profile, data-root, database, command, or environment-variable input from the browser.
- Adding a second prerequisite checker, workflow engine, scheduler, model client, daemon, or general command/tool dispatcher.
- Mutating setup state from diagnosis or treating a local-mode `not-run` live check as passed.
- Beginning artifact review or curation; P0300 starts only after this plan completes.
