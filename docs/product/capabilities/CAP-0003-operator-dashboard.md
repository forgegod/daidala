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
  aggregate path-free readiness counts, including a registered GitHub Project,
  workflow-pack presence, per-phase installed and ready skill coverage, and
  blocked-pack counts. It never runs while polling, returns only validated links
  to closed exact dashboard destinations, including Config → Packs for blocked
  packs and missing phase skill coverage, and never replaces deterministic
  workflow recommendations or performs an action.
- Start workflow lists every bundled pack with its readiness state and offers
  three explicit workspace modes: a registered GitHub repository (whose bound
  board is derived server-side from that registration, including registrations
  owned by other Hermes profiles), an unregistered board with a clean local Git
  root, or a fresh local project. Local initialization previews and then creates
  the Git root, strict default policy, initial commit, and unbound board without a
  GitHub identity. The browser never receives a checkout path or selects a
  board for a registered GitHub repository. Registrations that violate uniqueness
  or board bind state stay visible outside the dropdown with a reason and
  conclusion. Start shows the working directory for the selected workspace.
  Manage packs, Register repository,
  and Manage sources preserve the browser draft while moving visual and keyboard
  focus to their exact Config destination.
- Approval, review disposition, card remediation, cancellation, setup, and curator mutations use preview/confirm or exact-identity requests; the server derives authoritative workflow, board, repository, and worktree facts.
- Artifact views expose ledger-bound metadata, bounded literal text, digest-verified downloads, and closed curator actions without accepting filesystem paths.
- Config → Packs is a pack-first workspace that separates complete immutable
  catalog installation from lifecycle-stage activation. Its summary shows source
  revision, Hermes range, catalog/installed/enabled/warning counts, lifecycle
  bindings, and active profile; its searchable inventory labels stage roles and
  catalog-only members without assigning them invented lifecycle ownership.
- The browser exposes installation only through one complete-pack preview and
  confirmation. During apply, an authenticated request-scoped stream shows the
  current declared skill name and one-based `position / total`; progress is a
  polite live status and exposes no command output or filesystem path. A partial
  Hermes failure remains explicit and the next fresh preview retries only missing
  catalog entries. Individual skill details expose
  status, source, expected and observed digests, literal bounded `SKILL.md`
  content when available, and profile-local enable or disable actions, but no
  individual installation control.
- External installation uses Hermes only. Readiness hashes the complete bundle
  Hermes installs and excludes unsupported upstream files. An observed digest
  mismatch is an explicit warning rather than an installation or workflow
  blocker; missing and disabled exact skills remain blocking. Enable and disable
  confirmations name the active profile and do not remove shared skill content.
- Skill details open in a keyboard-focused drawer. Confirmation dialogs trap
  focus, Escape returns focus to the invoking control, and narrow inventory shows
  four rows before explicit **Show all** disclosure.
- Start workflow keeps packs selectable for inspection while naming
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

- [`tests/test_dashboard_api.py`](../../../tests/test_dashboard_api.py) — exact identities, path-free responses, preview/apply gates, and bounded routes including installation-progress terminal events.
- [`tests/test_dashboard_assets.py`](../../../tests/test_dashboard_assets.py) — primary views, states, authenticated SDK and stream use, accessible installation progress, and host-theme behavior.
- [`tests/test_dashboard_advice.py`](../../../tests/test_dashboard_advice.py) — aggregate snapshot minimization, GitHub and pack-phase readiness requirements, host-model invocation, response bounds, and unavailable behavior.
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
- [Pinned Hermes pack installation receipt](../../changes/archive/CHG-0012-pin-hermes-pack-skill-installation.md)
- [Start repository wording receipt](../../changes/archive/CHG-0017-start-repository-wording-and-inventory.md)
