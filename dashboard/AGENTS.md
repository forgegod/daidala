# dashboard/

## Purpose

Provide the optional Daidala extension for the existing Hermes dashboard.

## Ownership

- `manifest.json` declares the `/daidala` tab, `sessions:top` slot, assets, and backend router.
- `plugin_api.py` mounts the profile-safe read model, bounded pack operations,
  narrowly scoped setup routes, bounded Kanban detail reads, exact-plan approval,
  exact attended review preview/apply routes, workflow-owned card comment/unblock,
  cancellation preview/apply routes, registration projections, checkout-root and
  checkout lifecycle preview/apply, and GitHub Projects v2 link read/verify/
  preview/apply routes, read-only reusable constraint-source list/detail routes,
  and one read-only persisted-configuration verification route.
- `dist/index.js` renders workflow progress, the inventory-backed Start workflow
  wizard, Config → Packs readiness/content, GitHub Projects v2 links,
  constraint source selection and schema-aware authoring, read-only configuration
  verification, and confirmed checkout refresh/adoption/backup-pruning/policy
  controls; decision-first supervision;
  exact-plan approval; literal source-bound review evidence/disposition;
  blocked-card remediation; and previewed cancellation.
- `dist/style.css` adapts the extension to host themes and narrow layouts.

## Local Contracts

- Register only documented Hermes dashboard SDK surfaces.
- Browser requests use the host SDK's authenticated `fetchJSON` helper and call
  only scoped Daidala routes; never read the host session token directly.
- `plugin_api.py` imports the stable `daidala` package exposed by both pip and
  the repository-root directory entry point.
- Initialize the process-local dashboard service exactly once under concurrent
  first requests; route threads must not race SQLite schema initialization.
- Workflow polling is read-only. Mutations are limited to confirmed external
  pack-skill installation, board creation, confirmed setup, and compare-and-swap
  constraint replacement, plus exact current-plan approval through
  `POST /workflows/{workflow_id}/approve`, exact attended review disposition
  through `POST /workflows/{workflow_id}/review-disposition`, confirmed
  workflow-owned-card comment/unblock routes, digest-bound cancellation
  through `POST /workflows/{workflow_id}/cancel`, confirmed checkout-root
  replacement, and confirmed GitHub Projects v2 link upsert/removal. GitHub link
  preview/verification and registration/checkout reads are non-mutating; browser
  payloads never carry credential values, an environment-variable name, a
  repository checkout path, or a GitHub Project node ID.
- Checkout lifecycle routes derive the registration and checkout from a project ID.
  Refresh, clean-unowned adoption, backup pruning, and policy replacement each
  recompute a preview and require its exact digest plus `confirm: true`; browser
  projections expose only statuses, counts, receipt age, recovery state, and backup
  filenames, never checkout paths, remotes, credentials, or node IDs.
- Exact-plan approval accepts only `{artifact_id, plan_digest, summary_digest,
  confirm: true}`, re-resolves the current verified plan and bound summary, and
  fails closed on stale or unavailable evidence. The browser renders the plan as
  literal text and never substitutes a summary or Kanban unblock for approval.
- Review preview accepts only `{action, rationale}`; apply accepts only `{action,
  review_digest, preview_digest, rationale, confirm: true}`. The server derives
  the attended actor and every workflow/artifact/card/worktree identity, recomputes
  the current preview, and fails closed on stale evidence. Browser responses expose
  only whether an owned worktree will be released, never its profile-local path.
- Card comment accepts only `{comment, confirm: true}` and unblock accepts only
  `{reason, confirm: true}` after the server validates the card against the current
  workflow ledger and derives its board. Cancellation preview accepts only
  `{reason}`; apply accepts only `{reason, preview_digest, confirm: true}` and
  recomputes the current cards, ledger token, owned-worktree identity, and
  normalized reason before delegating to `WorkflowService.cancel`.
- Captured implementation diffs, paths, verification outcomes, findings, and
  successor packets render as literal source-bound facts. Delivery authority is
  shown only when the service allows `accept_delivery`; revision requires feedback
  plus preview and literal confirmation before one successor Plan card is created.
- Workflow card detail uses only bounded `hermes kanban --board <derived-board>
  show <card_id> --json` and `runs <card_id> --json` reads. Each card is derived
  from the workflow ledger; output is capped at 64 KiB, execution at ten seconds,
  and only allowlisted fields enter the detail snapshot.
- Pack routes accept only bundled pack names and declared skill names. Content is
  literal, path-free, and bounded to 1 MiB; install apply requires a fresh
  matching preview digest and literal confirmation.
- Preview and declined setup must not mutate; start requires a literal checked confirmation.
- Wizard inventory derives the mounted controller profile from Hermes' documented
  profile inventory and exposes only registrations bound to that profile. The
  runtime-root identity takes precedence only after exact inventory validation;
  the dashboard's management-profile query never selects the backend controller.
  The browser selects only a project ID and never sends a controller profile,
  checkout, credential, or filesystem path.
- Constraint preview is non-mutating; replacement requires the displayed current
  digest and explicit invalidation confirmation.
- Constraint-source list/detail routes accept only exact inventory names. They
  expose only installed skills with a complete valid reusable-policy document;
  details render literal `SKILL.md` content only up to 1 MiB and otherwise return
  a sanitized unavailable state. Source selection copies only into a browser draft
  or explicit Start return context and cannot mutate a source.
- `GET /configuration` projects only the persisted checkout root/policy, derived
  registration checkout status, GitHub Project metadata state, bounded intake
  evidence health, evaluator state, and notification destination presence. It
  never returns aliases, credentials, raw probe output, private destinations,
  registration checkout paths, or GitHub Project node IDs.
- Poll no faster than every five seconds while visible, stop while hidden, and retain manual refresh.
- Treat API responses as snapshots; never authorize workflow operations from client state.
- After setup or exact-ID reopen, render the selected workflow from its fresh
  detail summary and exclude that ID from the ordinary workflow list so the UI
  never presents an incomplete or duplicate card.

## Work Guidance

- Keep the JavaScript dependency-free and compatible with the React instance exposed by the Hermes plugin SDK.
- Keep the backend router thin; deterministic policy remains under `daidala/`.

## Verification

```bash
pytest tests/test_dashboard_assets.py tests/test_dashboard_api.py
```

Browser verification uses an isolated supported Hermes dashboard and desktop plus narrow Chromium screenshots.

## Child DOX Index

*(empty — `dist/` contains generated browser assets governed here.)*

See [`/AGENTS.md`](../AGENTS.md).
