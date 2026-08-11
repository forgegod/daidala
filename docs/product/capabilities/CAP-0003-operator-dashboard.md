# CAP-0003: Operator dashboard

**Status:** implemented
**Primary surface:** Hermes dashboard → Daidala

## Outcome

An authenticated operator can inspect workflow state and evidence, perform bounded attended decisions, review artifacts, and configure supported Daidala inputs inside the existing Hermes dashboard without exposing profile-local paths or credentials.

## Behavior

- Workflows is the default view and presents awaiting-attention work, recent terminal outcomes, exact workflow detail, live Kanban snapshots, and finite source-bound recommendations.
- Each primary view explains its operational purpose and the next missing or
  unavailable condition: workflow supervision, ledger-bound artifact evidence,
  or configuration readiness. Workflows can explicitly request one advisory
  readiness analysis from the configured host model. The request sends only
  aggregate path-free readiness counts, never runs while polling, returns only
  validated links to existing screens, and never replaces deterministic workflow
  recommendations or performs an action.
- Start workflow lists every bundled pack with its readiness state, links repository registration to path-safe operator guidance, and disables primary views that cannot preserve the open browser draft.
- Approval, review disposition, card remediation, cancellation, setup, and curator mutations use preview/confirm or exact-identity requests; the server derives authoritative workflow, board, repository, and worktree facts.
- Artifact views expose ledger-bound metadata, bounded literal text, digest-verified downloads, and closed curator actions without accepting filesystem paths.
- Config → Packs renders bounded literal skill text only for bundled or installed
  skills, identifies uninstalled external skills with their exact install targets,
  links every declaration to its source, and shows installed and enabled state.
  Individual and pack-wide install, enable, and disable actions require a fresh
  digest-bound preview plus explicit confirmation. Disable updates the active
  profile's Hermes availability state without removing shared skill content.
  Start workflow keeps packs selectable for inspection while naming
  installation-required, blocked, and unavailable readiness states explicitly.
- The dashboard includes explicit loading, empty, unavailable, validation, and destructive-confirmation states and uses the host Hermes theme and authenticated SDK boundaries.

## Evidence

### Runtime

- [`dashboard/plugin_api.py`](../../../dashboard/plugin_api.py) — authenticated path-safe route adapter and closed mutation surface.
- [`dashboard/dist/index.js`](../../../dashboard/dist/index.js) — Workflows, Artifacts, Config, evidence, and attended-decision rendering.
- [`dashboard/dist/style.css`](../../../dashboard/dist/style.css) — host-theme and narrow-layout behavior.
- [`daidala/dashboard_backend.py`](../../../daidala/dashboard_backend.py) — profile-safe workflow, recommendation, artifact, and configuration projections.
- [`daidala/dashboard_advice.py`](../../../daidala/dashboard_advice.py) — path-free readiness aggregation and bounded host-model advice normalization.

### Tests

- [`tests/test_dashboard_api.py`](../../../tests/test_dashboard_api.py) — exact identities, path-free responses, preview/apply gates, and bounded routes.
- [`tests/test_dashboard_assets.py`](../../../tests/test_dashboard_assets.py) — primary views, states, authenticated SDK use, and host-theme behavior.
- [`tests/test_dashboard_advice.py`](../../../tests/test_dashboard_advice.py) — aggregate snapshot minimization, host-model invocation, response bounds, and unavailable behavior.
- [`tests/test_dashboard.py`](../../../tests/test_dashboard.py) — read-model, timeline, recommendation, and artifact projections.

## Contracts

- [Architecture](../../01-architecture.md)
- [Workflow state and authority](../../02-workflow-state.md)
- [Operator runbook](../../07-runbook.md)
- [Hermes integration](../../08-hermes-integration.md)

## Links

- [Interactive wireframe](../wireframes/html/CAP-0003-operator-dashboard.html)
- [PNG wireframe](../wireframes/exports/CAP-0003-operator-dashboard.png)
- [Wireframe index](../wireframes/index.html)
- [Initial records-adoption receipt](../../changes/archive/CHG-0001-adopt-application-records.md)
