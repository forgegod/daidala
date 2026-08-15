# dashboard/

## Purpose

Provide the optional Daidala extension for the existing Hermes dashboard.

## Ownership

- `manifest.json` declares the `/daidala` tab, `sessions:top` slot, assets, and backend router.
- `plugin_api.py` mounts the profile-safe read model, bounded pack operations,
  narrowly scoped setup routes, bounded Kanban detail reads, exact-plan approval,
  exact attended review preview/apply routes, workflow-owned card comment/unblock,
  cancellation preview/apply routes, preview-confirmed repository registration,
  registration projections, checkout-root and
  checkout lifecycle preview/apply, and GitHub Projects v2 link read/verify/
  preview/apply routes, read-only reusable constraint-source list/detail routes,
  persisted-configuration verification, non-mutating initialization preview/confirmed apply,
  trusted-registration prerequisite diagnosis routes, ledger-bound artifact
  catalog/text/download reads, and digest-confirmed curator controls.
- `dist/index.js` renders Workflows, Artifacts, and Config primary views;
  workflow progress; the inventory-backed Start workflow
  wizard, Config → GitHub Repositories registration, the catalog-first Config →
  Packs readiness, lifecycle, inventory, and detail workspace,
  GitHub Projects v2 links,
  constraint source selection and schema-aware authoring, read-only configuration
  verification, initialization preview/apply, prerequisite diagnosis, operator-runbook
  guidance, and confirmed checkout refresh/adoption/backup-pruning/policy
  controls; decision-first supervision;
  exact-plan approval; literal source-bound review evidence/disposition;
  blocked-card remediation; previewed cancellation; and literal artifact review,
  verified download, filtering, and pin/unpin/archive/restore preview-confirm controls.
- `dist/style.css` adapts the extension to host themes and narrow layouts.

## Local Contracts

- Register only documented Hermes dashboard SDK surfaces.
- Browser JSON requests use the host SDK's authenticated `fetchJSON` helper;
  authenticated response streams and verified byte downloads use its
  `authedFetch` helper. Browser
  code calls only scoped Daidala routes and never reads the host session token.
- `plugin_api.py` imports the stable `daidala` package exposed by both pip and
  the repository-root directory entry point.
- Initialize the process-local dashboard service exactly once under concurrent
  first requests; route threads must not race SQLite schema initialization.
- Workflow polling is read-only. Mutations are limited to confirmed declared
  pack-skill install/enable/disable actions, board creation, confirmed setup, and compare-and-swap
  constraint replacement, plus exact current-plan approval through
  `POST /workflows/{workflow_id}/approve`, exact attended review disposition
  through `POST /workflows/{workflow_id}/review-disposition`, confirmed
  workflow-owned-card comment/unblock routes, digest-bound cancellation
  through `POST /workflows/{workflow_id}/cancel`, confirmed checkout-root
  replacement, confirmed GitHub Projects v2 link upsert/removal, and confirmed
  repository registration after a fresh digest. GitHub link preview/verification
  and registration/checkout previews are non-mutating; browser
  payloads never carry credential values, an environment-variable name, a
  repository checkout path, credential alias, credential-source detail, or a
  GitHub Project node ID. Repository-registration inventory returns every
  Hermes-validated profile name with that profile's path-free registrations
  and a finite `ready`/`unavailable` status. Preview accepts exactly
  `{github_url, controller_profile}` and returns a path-free classification:
  `registerable` (registration preview fields), `needs-bootstrap`,
  `already-registered`, or `blocked` with stable `reason`/`next_action`. Apply
  additionally requires a SHA-256 `preview_digest` and `confirm: true`. Every
  selected name is revalidated and re-resolved through Hermes before the
  deterministic registration service reads profile-local state; preview readiness
  exposes only boolean credential availability.
- Checkout lifecycle routes derive the registration and checkout from a project ID.
  Refresh, clean-unowned adoption, backup pruning, and policy replacement each
  recompute a preview and require its exact digest plus `confirm: true`; browser
  projections expose only statuses, counts, receipt age, recovery state, and backup
  filenames, never checkout paths, remotes, credentials, or node IDs.
- Exact-plan approval accepts only `{artifact_id, plan_digest, summary_digest,
  confirm: true}`, re-resolves the current verified plan and bound summary, and
  fails closed on stale or unavailable evidence. The browser renders the plan as
  literal text and never substitutes a summary or Kanban unblock for approval.
- Workflow summaries expose generated versus Git-pinned plan mode and imported
  packet identity only as Plan ID, execution slot, phase, source revision,
  packet digest, and verified packet state. They never expose source paths or
  bytes, and the dashboard has no admission or checkpoint mutation control.
- Review preview accepts only `{action, rationale}`; apply accepts only `{action,
  review_digest, preview_digest, rationale, confirm: true}`. The server derives
  the attended actor and every workflow/artifact/card/worktree identity, recomputes
  the current preview, and fails closed on stale evidence. Browser responses expose
  only whether an owned worktree will be released, never its profile-local path.
- Artifact reads accept only an optional exact workflow ID or exact workflow plus
  opaque artifact ID. Text remains literal and bounded; download bytes are
  digest-verified and served as non-sniffable attachments with path-free errors.
  Curator preview/apply accepts only the closed pin, unpin, archive, and restore
  operations. Restore additionally carries one opaque archive ID; apply requires
  the exact preview digest and `confirm: true`. No route accepts a filesystem path.
- Artifact archive/restore delegates to the profile-local curator through the
  policy-neutral `daidala/archive_io.py` primitive. Workflow archives and recovery
  copies remain below the resolved Daidala data root; checkout backups remain
  below `<checkouts.root>/_backups/`. The browser never combines those stores.
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
  literal, path-free, and bounded to 1 MiB. Config → Packs renders `SKILL.md`
  content only for bundled or installed skills; uninstalled external skills show
  their installation requirement, exact install target, and pinned source link.
  The browser exposes installation only as one complete-pack action; partial
  failure receipts lead to a fresh retry over the remaining missing catalog
  entries. Confirmed apply streams ordered NDJSON progress containing only the
  one-based position, total, and declared skill name, followed by one bounded
  success or error event; command output and filesystem paths never enter the
  browser stream. Individual and pack-wide enable and disable apply require a fresh
  matching action preview digest, literal confirmation, and post-action
  verification. Digest mismatches render as warnings and do not block skill use
  or install actions. Selecting a skill opens a keyboard-focused detail drawer;
  narrow inventory renders four rows before explicit progressive disclosure.
  Disable is never presented as uninstall or deletion.
- Preview and declined setup must not mutate; start requires a literal checked confirmation.
- Start-workflow management links preserve the browser-local draft while opening
  their exact Config tab above it. After a routed tab renders, the Config section
  receives keyboard focus and scrolls to the viewport start so the navigation
  result is immediately visible.
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
- `POST /setup-analysis` accepts exactly an empty object. The server derives
  aggregate, path-free configuration/workflow/artifact readiness counts plus
  registered GitHub Project and pack-check phase coverage. Pack facts include
  only counts for packs, blocked/ready state, and installed/ready skill coverage;
  they exclude pack names, skill names, sources, blockers, and install commands.
  It uses only the documented `ctx.llm` facade registered by Daidala; it does not
  read Hermes model configuration or internals. The request is explicit, never
  polled, non-mutating, and returns only validated advisory text plus closed exact
  dashboard destinations. Model failures remain explicit and never replace
  deterministic workflow recommendations. Pack and phase-skill remediation
  targets Config → Packs rather than a generic workflow screen.
- Initialization preview exposes only the resolved profile-local ledger target and
  observed schema state; apply accepts exactly `{preview_digest, confirm: true}`
  and resets the cached service only after creation. Prerequisite diagnosis accepts
  exactly `{project_id, live}`, derives all paths from the trusted registration,
  and returns the bounded existing report without protected values.
- Health identity exposes only the observed profile, Daidala and Hermes versions,
  supported Hermes range, and an unavailable install source. The runbook renders
  exact host-owned install/upgrade commands as copyable guidance and resumes only
  an exact existing workflow through ordinary read-only polling.
- The operator-runbook panel maps every runbook operation to an existing browser
  surface or native CLI guidance. It never renders an execute control for plugin,
  gateway, or Hermes lifecycle commands.
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
pytest tests/test_dashboard_assets.py tests/test_dashboard_api.py tests/test_dashboard.py tests/test_artifact_access.py tests/test_artifact_curator.py
```

Artifact browser verification uses
`tests/fixtures/dashboard_phase0_browser_probe.html` in isolated Chromium and
checks archived-diff listing, literal escaped text, digest-equivalent download,
and confirmed restore without a real Hermes profile.

## Child DOX Index

*(empty — `dist/` contains generated browser assets governed here.)*

See [`/AGENTS.md`](../AGENTS.md).
