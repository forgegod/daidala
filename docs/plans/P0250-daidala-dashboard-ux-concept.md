# Daidala dashboard UX concept and design contract

**Plan ID:** daidala-dashboard-ux-concept

**Execution slot:** P0250

**Created:** 2026-07-25

**Depends on:** none

**Plan family:** daidala-dashboard

**Entry checkpoint:** none — design contract; consumes only the shared execution contract and current `dashboard/` implementation

**Context sources:** [shared goal and current state](daidala-dashboard-execution-contract.md#goal), [operator pinning](daidala-dashboard-execution-contract.md#operator-pinning), [operator runbook coverage](daidala-dashboard-execution-contract.md#operator-runbook-coverage), [implementer discipline](daidala-dashboard-execution-contract.md#implementer-discipline), [P0210 supervision scope](P0210-daidala-dashboard-setup-and-supervision.md), [P0220 checkouts/links scope](P0220-daidala-dashboard-checkouts-and-project-links.md), [P0230 constraints/config scope](P0230-daidala-dashboard-constraints-and-verification.md), [P0240 runbook parity scope](P0240-daidala-dashboard-operator-runbook-parity.md), [P0320 artifact browser scope](P0320-daidala-artifact-dashboard-cron-and-verification.md), and the current `../dashboard/` assets

**Produces:** a single UX concept and design contract (information architecture, decision-card pattern, preview-confirm envelope, status semantics) that P0200–P0240 and P0320 cite for all dashboard presentation work

**Status:** revision proposed — Start workflow selectors, readiness, defaults, and host handoffs require fresh human approval before implementation

## Goal

Define one UX concept for the single `/daidala` dashboard tab so every presentation
phase (P0200–P0240, P0320) renders the same decision-first, read-mostly,
exact-digest surface in the canonical Hermes Teal identity — instead of each plan
inventing its own layout. This document is a **design contract**: it owns the IA and
component patterns; it has no implementation phases and grants no approval authority.

## Design decisions (operator-pinned)

1. **Single tab, internal views.** The manifest keeps one `/daidala` tab
   (`../dashboard/manifest.json`). All navigation is internal to the tab and
   follows workflow-result order: Workflows / Artifacts / Config. Workflows is
   the default view. Starting a workflow is its primary page action and opens a
   Workflows subpage; attended decisions open workflow-specific detail subpages.
   No manifest change. Config intentionally uses the same concise label
   as Hermes' host `/config` surface while remaining scoped to Daidala.
   Every wireframe and implemented view preserves the same three-layer frame:
   the Hermes-owned profile banner/sidebar shell; the Daidala-owned page header
   and three-view navigation; and one use-case-specific content workspace. A
   workflow detail, review, revision, or confirmation flow replaces only the
   content workspace—it never redraws, abbreviates, or bypasses the first two
   layers.
2. **Workflow-first attention queue.** Workflows begins with only workflows that
   currently need attended input, followed by autonomous and recently finished
   workflows. `Recently finished workflows` means the latest five terminal
   workflows matching the current filters, ordered by terminal timestamp
   descending with stable workflow-ID tie-breaking. It includes completed,
   failed, and cancelled states; these are workflow outcomes, not artifacts.
   Each compact awaiting-action row includes one source-bound sentence describing
   the next operator action and opens a workflow detail subpage. The sentence is
   orientation copy, never a substitute for evidence or authority. Decision gates
   live in their workflow detail page, where identity, stage timeline, an
   expanded-by-default artifact browser, and exact evidence remain visible before
   the human action. The `Awaiting action` group is sorted oldest actionable
   decision first (the time its current gate became actionable), with stable
   workflow-ID tie-breaking. Urgency indicators remain visible but never reorder
   the approval queue.
3. **Config as in-tab tabs.** Packs, Checkouts/TTL, GitHub Projects, Constraints,
   and Verification are tabs inside the Config view, not separate manifest tabs
   or a single merged settings panel.
4. **Artifact browser in IA.** The Artifacts view (P0320) is part of this concept's
   IA from the start so its navigation and patterns land consistently.
5. **Requested outcome terminology.** The Start workflow subpage labels the user-authored
   change description **Requested outcome / Prompt**, not Goal. The browser still maps it
   to the existing `SetupRequest.goal` payload field; it does not invoke or imply
   Hermes' `/goal` session feature.
6. **One controller profile, six worker assignments.** The Hermes profile and
   dashboard lifecycle is the only controller-profile switch. The Start workflow
   page shows
   the mounted controller profile as read-only because the dashboard backend,
   ledger, registrations, and credentials are process/profile scoped. A separate
   **Worker profile default** selector is a UI convenience over existing Hermes
   profiles: it fills all six executable stage selectors, while Advanced exposes
   per-stage overrides. Only the resolved six-stage mapping reaches
   `SetupRequest`; there is no seventh profile field.
7. **Inventory-backed selections.** Pack, registered repository, worker profiles,
   and board are selectors, never free-form identity fields. Pack offers only
   installed, validated definitions that are ready for the mounted profile;
   `Manage` opens Config → Packs. Board offers existing installation-global
   Kanban boards; `Create` opens the preview-confirm board-creation flow. A
   registered repository selection displays its canonical verified remote URI
   while the server resolves its trusted checkout without returning that path.
8. **Readiness before authority.** Preview and Start rerun the same server-owned
   preflight over mounted profile identity, pack digests, repository identity and
   clean baseline, required repository capabilities, six worker assignments,
   board existence, and gateway reachability. The browser shows capability
   results, never credential names or values. A GitHub repository does not imply
   that `GH_TOKEN` is always the credential: HTTPS/token, SSH, and registration
   alias bindings are checked according to the actual remote and required
   operation.
9. **Defaults and scheduling stay non-authoritative.** `Save as default` stores a
   browser-local, mounted-profile-scoped preset containing only project ID, pack,
   board, and six worker assignments. It never stores requested outcome,
   workflow ID, checkout path, raw constraints, credential aliases, or values.
   Applying a preset only repopulates selectors and always reruns inventory and
   readiness; missing/stale identities are shown and left unselected. Delayed or
   recurring admission links to Hermes Cron. Pausing that cron prevents future
   admissions; it does not suspend already dispatched cards. Daidala adds no
   scheduler or timed in-flight pause.

## Use-case catalog

Actor is always an attended human operator. Legend: ✅ implemented · 🟡 planned.

### Surface A — Onboard & verify (P0200, P0240)
1. **Verify mounted plugin/identity** 🟡 — show host/profile identity; install/enable commands displayed, never executed.
2. **Browse & validate packs** 🟡 — Config → Packs lists and validates both definitions and readiness.
3. **Preview/confirm external skill install** 🟡 — dry-run-first; apply needs confirmation. Selecting a pack activates it for one workflow; v1 has no pack enable/disable or arbitrary archive upload.
4. **Initialize profile (dry-run-first)** 🟡 — preview data root without creating schema; confirmed apply idempotent; health/preview create nothing.
5. **Run prerequisite diagnosis** 🟡 — strict `doctor` with stable check IDs; local default + explicit bounded live; validated `project_id`; no credential values.

### Surface B — Start a workflow (P0210 Phase 0)
6. **Guided setup wizard** 🟡 — read-only mounted controller profile, optional browser-local start preset, ready installed pack, registered repository, requested outcome / prompt, worker-profile default plus stage overrides, constraints, and existing/create board; the UI maps requested outcome / prompt to the existing `request.goal` field, the server resolves the selected registration to the trusted target, and only the resolved setup request reaches `SetupRequest.from_payload`; readiness → preview → literal confirm → start now. Delayed/recurring admission hands off to Hermes Cron.

### Surface C — Supervise & decide (P0210 Phase 1) ✅/🟡
7. **Watch workflows (read-only)** ✅ — poll ≥5s while visible; manual refresh.
8. **Approve the exact plan** 🟡 — decision-first panel; source-bound AI-assisted summary then verified bounded plan body, plan/constraint tuple, checklist, consequences, and a read-only next-stage packet; bound to verified artifact identity + literal "I reviewed this exact plan"; disabled on stale/mismatched identity; literal escaped text.
9. **Review disposition before delivery** 🟡 — source-bound AI-assisted summary + exact escaped diff + verification + findings + ledger-owned gate and a read-only successor packet; accept-and-deliver only for accepted non-blocking review.
10. **Request revision** 🟡 — previewed immutable-evidence/cards/worktree consequences, a visible successor packet, required feedback, literal confirm, then navigate to new revisioned plan approval.
11. **Recover a blocked card** 🟡 — requested decision + latest relevant evidence + targeted comment/unblock.
12. **Cancel a workflow** 🟡 — preview cards/worktree/reason, digest + confirm, name affected worktree first.
13. **Reopen/resume by exact ID** 🟡 — reopen and continue read-only watch, not a new workflow.
14. **Inspect workflow artifacts** 🟡 — each actionable workflow detail expands its ledger-bound artifacts by default, reusing the Artifacts view's list/selected-detail pattern for the exact workflow; `View all` opens the Artifacts view filtered to that workflow ID without exposing a filesystem path.

### Surface D — Config: checkouts & GitHub links (P0220)
15. **Config: checkout root + TTL** 🟡 — disabled / wipe-if-clean / backup-then-wipe, default disabled; root change 409 while owned checkouts exist; `.daidala-owner` marker.
16. **Manual checkout refresh** 🟡 — validate path/marker/origin/receipt/Git status; dry-run-first + confirm.
17. **Prune named backups** 🟡 — explicit named payload + literal confirm; never auto-prune.
18. **Manage one GitHub Projects v2 link per project** 🟡 — fresh bounded read + matching preview digest + literal confirm; tokens never cross; remote/alias display-only.

### Surface E — Author constraints & verify config (P0230)
19. **Author constraints** 🟡 — schema-aware YAML editor, live preview, error list, digest impact; replace stays preview/confirm compare-and-swap.
20. **Verify configuration (read-only)** 🟡 — root, TTL, registrations, checkout ownership/freshness, link verification; no secrets; not a supervisor.

### Surface F — Browse artifacts & curate (P0320)
21. **Browse artifact history** 🟡 — authenticated ledger-bound list/detail/bounded-text/download; literal text; binary/oversized download-only.
22. **Curate artifacts** 🟡 — pin/unpin/archive/restore via preview digest + literal confirm.
23. **Schedule curation (opt-in cron)** 🟡 — Hermes Cron; IDs/counts/digests/states only; disabled = no mutation.

### Cross-cutting runbook parity (P0240)
24. **Runbook navigation + lifecycle guidance** 🟡 — every runbook section has one dashboard owner; install/enable/upgrade/restart/standalone shown as commands, never executed.

## UX tensions (invariants every view respects)

- Exact-digest, artifact-bound approval; no summary-only consent.
- Preview-then-confirm; fresh digest; literal `confirm: true`.
- Read-mostly; mutations explicit, scoped, confirmation-gated.
- Fail-closed; unavailable/stale/mismatched identity disables the action.
- No self-modification; install/enable/upgrade/restart are host-owned guidance.
- Literal escaped text for Markdown/JSON/YAML/HTML/diff/source in v1.
- Closed route inventory; no general command-dispatch endpoint.
- Canonical Hermes Teal identity.

## Information architecture

Three primary views, all inside the single tab and ordered by workflow result:

- **Workflows (default)** — complete lifecycle inventory, independent of whether
  attended input is required. Its page header exposes the single primary `Start
  workflow` action. Show summary counts and filters, then awaiting-action rows,
  active workflows with stage progress, and the latest five terminal workflows
  under **Recently finished workflows**. That section includes completed, failed,
  and cancelled states matching the current filters, ordered by terminal
  timestamp descending with stable workflow-ID tie-breaking. It contains workflow
  outcomes, never artifacts; selecting a row opens workflow detail, where its
  ledger-bound artifacts remain available through the embedded browser and
  filtered Artifacts view. Each
  awaiting-action row names the current finite action—such as `Request revision`
  or `Review plan`—and adds one source-bound `Next action` sentence so the operator
  can triage without opening every workflow. The sentence is list-level orientation
  only; exact evidence, identities, and controls remain in the workflow detail
  subpage. Rows are oldest-actionable first, with urgency displayed but not used
  for ordering. An active workflow without a gate is labelled `Running without
  operator input`. Empty inventory uses a dashed `No workflows yet` state with the
  same `Start workflow` action. Selecting a row opens the workflow detail workspace.
- **Workflow detail** — decision-first when a gate exists: the active decision panel (plan approval /
  review disposition / blocked-card / cancel-preview) occupies the top ~60% with
  source-bound summary + verified evidence; below it a lower-noise stage timeline and
  card list; raw run/event detail behind progressive disclosure. It remains inside
  the standard Hermes shell and Daidala header with **Workflows** selected; only
  the content workspace changes for review, revision, or other workflow actions.
  An actionable detail shows workflow identity and stage state, then an
  expanded-by-default workflow-scoped artifact browser and selected literal
  evidence before its action-specific summary, successor packet (when applicable),
  preview, confirmation, and authority controls.
  Because the selected Workflows tab already establishes both Daidala and list
  context, detail screens do not repeat `Daidala / Workflows` as a breadcrumb.
  They show a distinct `← Back to Workflows` control followed by the exact
  workflow ID, so returning to inventory does not depend on re-clicking the
  already-selected tab.
- **Terminal workflow detail** — completed, failed, and cancelled rows open the
  same read-only detail template with their terminal outcome kept distinct. It
  shows exact workflow identity, final stage timeline, ledger-bound artifacts,
  verification and review disposition, and delivery state including explicit
  commit/push results. It exposes read-only artifact download/filter actions but
  no approval, revision, cancellation, or other authority controls.
- **Start workflow subpage** — opened by the Workflows page's primary action,
  keeps Workflows selected, and begins with `← Back to Workflows`. Its compact
  flow is mounted-profile/default preset → pack + board → registered repository
  → requested outcome / prompt → worker default + stage overrides → policy → readiness →
  preview → literal confirm → start now. `Requested outcome / Prompt` maps to
  `SetupRequest.goal` only at the request boundary and is not Hermes `/goal`.
  The registered-repository selector shows the canonical remote (e.g.
  `git@github.com:forgegod/daidala.git`) while the server resolves the trusted
  local checkout; the URI is an identity label, not a writable path. Start is
  disabled until the selected profile's required repository capabilities and all
  other stable readiness checks pass. Host-owned links route pack management to
  Config → Packs, full board management to Kanban, and delayed/recurring
  admission to Cron.
- **Start workflow advanced settings** — expanding Advanced renders exactly six
  inventory-backed stage assignments. Inherited assignments name the worker
  default; explicit overrides expose `Reset`. The section separately renders a
  reusable constraint-source selector and optional workflow ID. Any change
  invalidates the current preview and reruns readiness. Blank workflow ID uses
  the server factory; an existing explicit ID resolves to `Open existing`.
- **Config (secondary, tabbed)** — Packs, Checkouts/TTL, GitHub Projects,
  Constraints, Verification (read-only).
- **Artifacts (secondary)** — workflow/kind/state filters; ledger-bound artifact
  list and selected-artifact detail/escaped preview; download plus
  preview-confirm curator controls; cron opt-in guidance.

## Core component patterns

- **Awaiting-action row** — the scalable Workflows triage unit. It names and links
  the exact workflow, current status, finite action, and one source-bound `Next
  action` sentence. The row never contains authority controls or substitutes its
  sentence for exact evidence.
- **Actionable workflow detail** — names the exact workflow, pack/board, current
  status, and artifact count. A compact stage timeline is followed by an
  expanded-by-default artifact browser and then the action-specific decision card.
- **Decision card** — one component for every authority action, always embedded
  in its owning workflow context: action-kind title, source-bound AI-assisted
  change summary, verified evidence (escaped text), identity tuple
  (plan/constraint/digest), consequence preview, literal-confirm checkbox, and an
  action button disabled until identity is verified. Actions that dispatch a
  successor card additionally show a read-only **What the next card receives**
  packet as a separately labelled projection of durable identities and references;
  actions without a successor card show only their operation-specific mutation
  preview and must not fabricate a handoff. The summary is an aid, not hidden
  authority. Operators can inspect the packet but cannot edit deterministic fields.
  A revision request additionally requires editable feedback; its normalized value
  is shown inside the packet before apply.
  Used for plan approval, review disposition, revision, cancel, checkout refresh,
  backup prune, link edit, constraint replace, pack install, profile init.
- **Embedded artifact browser** — a foldable, expanded-by-default workflow-scoped
  count/header above a compact artifact list and selected-artifact metadata plus
  literal escaped preview. `View all` opens the Artifacts view with a
  server-validated workflow filter; no client path is sent. Download remains
  read-only; pin/archive/restore stay in the full Artifacts view so the attention
  card does not combine evidence review with unrelated curation mutations.
- **Preview → confirm envelope** — every mutating form renders the exact strict
  payload + digest on Preview, then a disabled-until-confirmed apply button.
- **Inventory selector** — selected value plus dropdown affordance, readiness
  state, and one contextual management link. Selector options carry stable IDs;
  labels and helper text may show names/remotes, but no path or credential value
  becomes browser authority.
- **Start readiness panel** — six grouped server results: mounted profile/host,
  pack, repository identity/baseline, repository capabilities, worker-profile
  mapping, and Kanban board/gateway. A failed stable check ID disables Preview
  and Start and links to Config, Kanban, or host guidance as appropriate.
- **Start preset** — reversible browser-local preference scoped by mounted
  controller profile. Saving and applying a preset never authorizes start; stale
  IDs fail closed and requested outcome remains blank for every new workflow.
- **Read-only by default** — Verification and all lists are read-only; mutations are
  separated behind explicit actions.
- **Status semantics** — reuse the dashboard's gateway-status color language
  (running=success, starting=warning, failed=destructive, stopped=muted) for
  workflow/card/decision states.
- **Progressive disclosure** — summaries first; full diffs, raw logs, audit threads
  collapsed by default.

## Artifacts view concept

The Artifacts tab is not a file manager. It is an authenticated projection of
ledger-owned artifact identities and bounded content from P0320. The default
layout is a filter/summary bar above a two-pane browser:

- **Filters:** exact workflow, artifact kind, lifecycle state
  (current/pinned/archived), and bounded text search over returned metadata.
- **Summary:** total results, pinned, archived, and download-only counts.
- **Artifact list (left):** kind, revision, workflow ID, digest prefix, byte size,
  creation time, and state badge. Selection is by ledger artifact ID, never path.
- **Artifact detail (right):** full identity/digest metadata, media type, size,
  provenance, related workflow/stage, and escaped bounded text preview. Markdown,
  JSON, YAML, HTML, source, and unified diffs remain literal text. Binary or
  oversized content is download-only.
- **Actions:** Download is read-only. Pin/unpin/archive/restore use the common
  preview-digest/literal-confirm envelope over P0310 services. Error surfaces are
  metadata-only.
- **Entry from workflow detail:** `View all` carries only the exact workflow ID and lands
  on the filtered artifact list; the server resolves ledger identities. The
  detail page's expanded browser uses the same list/detail semantics but remains
  scoped to one workflow and exposes no curator mutations.

## Hermes dashboard design system

This is the design source of truth for Daidala dashboard work. It combines the
theme definitions in source with a computed-style capture of the live Hermes
v0.19.0 dashboard on `http://127.0.0.1:9119` at a 1280×720 viewport. The live
profile used the **Hermes Teal (Large)** preset. Source defaults and live scaled
values are deliberately recorded separately so implementation does not hard-code
one viewport or confuse the normal and Large presets.

### Source theme contract

From `web/src/themes/presets.ts:41-240` and `web/src/index.css:50-89`, canonical
Hermes Teal uses background `#041c1c`, midground `#ffe6cb`, foreground
`#ffffff`, warm glow `rgba(255,189,56,0.35)`, radius `0.5rem`, comfortable
density, system sans/mono, base `15px`, line-height `1.55`, and spacing multiplier
`1`. Hermes Teal (Large) retains the palette/radius but changes base size to
`18px`, line-height to `1.65`, density to spacious, and spacing multiplier to
`1.2`.

Semantic tokens consumed by the shell and pages are `--color-card`,
`--color-primary`, `--color-secondary`, `--color-muted`,
`--color-muted-foreground`, `--color-accent`, `--color-destructive`,
`--color-success`, `--color-warning`, `--color-border`, `--color-input`,
`--color-ring`, `--color-popover`, plus Tailwind aliases
`text-primary/secondary/tertiary/disabled` and `bg-card`/`bg-background`
(`index.css:149-186`). `colorOverrides` can re-skin `card`, `primary`,
`secondary`, `muted`, `accent`, `destructive`, `success`, `warning`, `border`,
`input`, and `ring` (`types.ts:132-154`). Daidala must consume these host tokens;
the resolved colors below are reference values for Pen and browser regression
review, not a parallel CSS palette.

### Live Hermes Teal (Large) reference

| Role | Token / computed value | Use |
|---|---|---|
| Shell background | `--background-base: #041c1c` | Viewport, sidebar, page background |
| Primary text/action | `--midground-base`, `--color-primary: #ffe6cb` | Text, selected tab, primary button |
| Card | `--color-card: #0e2423` | Decision and preview cards |
| Secondary | `--color-secondary: #132826` | Secondary controls and badges |
| Muted | `--color-muted: #182c2a` | Evidence blocks and subdued rows |
| Accent surface | `--color-accent: #1d302d` | Selected secondary tabs and active plugin row |
| Muted foreground | `--color-muted-foreground: rgba(255,230,203,0.8)` | Secondary labels and metadata |
| Success | `--color-success: #4ade80` | Running, verified, done |
| Warning | `--color-warning: #ffbd38` | Pending decisions, confirmation, profile banner |
| Destructive | `--color-destructive: #fb2c36` | Blocked, reject, destructive consequences |
| Border/input | `--color-border`, `--color-input: rgba(255,230,203,0.15)` | Panels, fields, rows, secondary buttons |
| Focus ring | `--color-ring: #ffe6cb` | Keyboard focus |

Typography observed live:

- Body: system sans, `18px`, line-height `29.7px` (`1.65`).
- Page title: Rules Expanded, `15.75px`, weight `700`, tracking `1.26px`.
- Sidebar navigation: uppercase system sans, `15.75px`, tracking `1.89px`.
- Segmented controls: Mondwest, `13.5px`, tracking `1.35px`.
- Technical identifiers, values, hashes, and command guidance: Courier Prime or
  the host mono stack.

Live shell geometry at 1280×720:

- Profile-scope banner: 36px high above the application shell.
- Expanded sidebar: approximately 345px wide under Large scaling; source class
  remains `w-64` and collapses to `w-14`.
- Page header: approximately 76px high; content begins below it.
- Main content padding: approximately `32.4px` (`lg:px-6` under spacing 1.2).
- Nav row: `49.5px` high with approximately `27px` horizontal and `13.5px`
  vertical padding.
- Source layout remains full-viewport flex, `px-3 sm:px-6`,
  `pt-2 sm:pt-4 lg:pt-6`, and `lg:pb-8` (`App.tsx:482-737`).

Gap scale observed on the live Plugins page (spacing multiplier 1.2):

- Between major page sections: `gap-8` = `43.2px`
- Card header block padding: `21.6px`, internal gap `8.1px`
- Two-column split: `gap-6` = `32.4px`
- Column stack: `gap-4` = `21.6px`
- Label group / rows / buttons / inline inputs: `gap-2` = `10.8px`
- Field label to input: `10.8px`; input to helper text: `10.8–21.6px`
- Inputs: height `48.6px`, padding `5.4px 16.2px`, square corners
- Two-part subgroups: `gap-2` = `10.8px`

Shape and interaction rules derived from the live Sessions and Kanban pages:

- Primary segmented tabs use square corners; selected tabs invert to cream
  background with dark-teal text.
- Primary actions use the same cream fill; secondary actions are transparent with
  a low-contrast border. Destructive actions use destructive text/border.
- Theme-radius (`0.5rem`, 9px under the Large preset) is reserved for content
  cards, grouped previews, and board-switcher panels. Compact list rows use about
  4.5px. Do not round structural tabs or the shell.
- Status badges pair a colored dot, text, dark surface, and same-color border.
- Configuration controls use uppercase metadata labels, monospace values, thin
  fieldset-like borders, and aligned action rows.
- Empty/drop states use a dashed bounded region and explicit text rather than an
  unframed blank area.
- Summaries come first; evidence, raw logs, and audit detail use progressive
  disclosure.

Plugin mount contract: routes mount `<PluginPage name>`; the bundle calls
`window.__HERMES_PLUGINS__.register(name, Component)`. The SDK
(`window.__HERMES_PLUGIN_SDK__`) exposes shared React + hooks, `api`, authenticated
`fetchJSON`, `authedFetch`, WebSocket helpers, Nous UI components (`Button`, `Card`,
`Badge`, `Tabs`, `Input`, `Select`, …), `cn`, `timeAgo`, and `useI18n`
(`registry.ts:110-167`, `sdk.d.ts:94-150`). Shell slots via
`window.__HERMES_PLUGINS__.registerSlot`: `backdrop`, `header-left/right`,
`header-banner`, `sidebar`, `pre-main`, `post-main`, footer slots, `overlay`
(`slots.ts:18-59,174-200`). Daidala uses `sessions:top` today and a `/daidala` tab.

## Pen design source and canonical renders

The host-derived visual constraints are codified in this document and the
owning `AGENTS.md`. The Pen source is an open-format `.pen` file with eight 1280×720 frames and three
1280×1000 workflow/start-detail frames. Every frame preserves the same Hermes shell and Daidala
navigation; only the use-case workspace changes. The Request plan revision frame
incorporates the former attention view's workflow identity, stage state, and
expanded artifact evidence before exposing immutable review evidence, the
read-only successor packet, required operator feedback, and non-mutating preview
before literal confirmation. The source is layout-checked and exported with the
headless Pen CLI; Pen Desktop remains available through Irigate for interactive
editing.

| File | Purpose |
|---|---|
| [`hermes-dashboard-ux-live.pen`](hermes-dashboard-ux-live.pen) | Editable Pen source with Workflows, collapsed/expanded Start workflow, completed/revision workflow details, Artifacts, Checkouts/TTL, Packs, GitHub Projects, Constraints, and Verification frames |
| [`dashboard-ux-workflows.png`](dashboard-ux-workflows.png) | Default workflow inventory with `Start workflow`, source-bound awaiting-action summaries, autonomous progress, and the latest five recently finished workflows |
| [`dashboard-ux-wizard.png`](dashboard-ux-wizard.png) | Workflows subpage for Start workflow with mounted-profile scope, inventory selectors, repository capability readiness, browser-local preset, Cron handoff, and back → preview → confirm → start |
| [`dashboard-ux-wizard-advanced.png`](dashboard-ux-wizard-advanced.png) | Expanded Start workflow Advanced settings with six stage assignments, reusable workflow constraints, optional workflow identity, readiness, and preview invalidation semantics |
| [`dashboard-ux-configure.png`](dashboard-ux-configure.png) | Config tabs including Packs, with Checkouts/TTL selected and read-only verification visible |
| [`dashboard-ux-config-packs.png`](dashboard-ux-config-packs.png) | Config → Packs inventory, exact source/compatibility/readiness, and dry-run-first external-skill installation entry |
| [`dashboard-ux-config-github-projects.png`](dashboard-ux-config-github-projects.png) | Config → GitHub Projects registration-derived identity, verified link, and fresh preview-confirm mutation flow |
| [`dashboard-ux-config-constraints.png`](dashboard-ux-config-constraints.png) | Config → Constraints reusable-source editor, YAML validation, digest impact, and compare-and-swap replacement preview |
| [`dashboard-ux-config-verification.png`](dashboard-ux-config-verification.png) | Config → Verification read-only local/live checks with stable IDs and separate initialization handoff |
| [`dashboard-ux-artifacts.png`](dashboard-ux-artifacts.png) | Ledger-bound artifact browser, detail/escaped preview, and curator actions |
| [`dashboard-ux-revision.png`](dashboard-ux-revision.png) | Workflows detail for request plan revision, with explicit inventory back-navigation, stage state, expanded artifacts/evidence, successor packet, feedback, preview, and confirmation |
| [`dashboard-ux-workflow-completed.png`](dashboard-ux-workflow-completed.png) | Read-only completed-workflow detail with final timeline, verified artifacts/evidence, review disposition, and explicit non-commit/non-push delivery result |

The concepts reproduce the profile-scope banner and Large-scaled sidebar, use host segmented tabs and primary
buttons; use bordered metrics and fieldset-like controls; reserve rounding for
content cards; and separate the non-mutating preview result from confirmation to
apply the displayed mutations. Config subtabs use an accent surface rather
than competing with primary navigation's cream selected state.

The information model uses `Requested outcome / Prompt` rather than `Goal`. Every screen
keeps the Hermes workspace and Daidala navigation invariant while changing only
the use-case content. Workflows lists waiting approvals oldest first and adds a bounded next-action
sentence to each row. Exact decision gates live in workflow details, where the
ledger-bound artifacts are expanded above the action; every
AI-assisted approval/disposition summary has a separately visible read-only
next-card packet; and Artifacts has a complete two-pane concept rather than
navigation-only scope.

### Reproducible Pen workflow

Use the headless Pen CLI for authoritative layout checks and exports because it
loads the current `.pen` bytes into a fresh editor. Start the shell with:

```bash
pen version
pen status
pen interactive \
  --in docs/plans/hermes-dashboard-ux-live.pen \
  --out /tmp/hermes-dashboard-ux-checked.pen
```

Inside the interactive shell, use `snapshot_layout` before export and save:

```text
snapshot_layout({ parentId: "BUbxE", maxDepth: 8, problemsOnly: true })
snapshot_layout({ parentId: "Wi001", maxDepth: 8, problemsOnly: true })
snapshot_layout({ parentId: "Cf001", maxDepth: 8, problemsOnly: true })
snapshot_layout({ parentId: "Ar001", maxDepth: 8, problemsOnly: true })
snapshot_layout({ parentId: "G1ryL", maxDepth: 8, problemsOnly: true })
export_nodes({ nodeIds: ["BUbxE", "Wi001", "Cf001", "Ar001", "G1ryL"], outputDir: "/tmp/daidala-ux-export", format: "png", scale: 1 })
save()
exit()
```

Irigate remains the persistent MCP boundary for Pen Desktop. Its user profile
config declares the Windows Pencil bridge as isolated upstream `pencil`; Hermes
connects to `http://127.0.0.1:8765/mcp`. Desktop documents are in-memory editor
state: after an external file rewrite, close/reopen the document or use a fresh
filename before trusting `pencil__snapshot_layout` or `pencil__export_nodes`.
Headless CLI verification avoids that stale-document boundary.

## Use-case → view map

| Surface | Use cases | View |
|---|---|---|
| A Onboard/verify | 1–5 | Config → Verification |
| B Start | 6 | Workflows → Start workflow subpage |
| C Supervise/decide | 7–14 | Workflows inventory + workflow detail |
| D Checkouts/links | 15–18 | Config → Checkouts & GitHub |
| E Constraints/config | 19–20 | Config → Constraints & Verification |
| F Artifacts | 21–23 | Artifacts view; workflow-filtered entry from workflow detail |
| Runbook parity | 24 | Config → Verification guidance (host-owned commands) |

## Out of scope

- No implementation phases, routes, or code — P0200–P0240 and P0320 own those.
- No manifest change; the single `/daidala` tab is preserved.
- No workflow engine, scheduler, timed in-flight pause, or command-dispatch route.
- No change to `SetupRequest`, registration storage, review/revision semantics,
  Kanban authority, or the closed route inventory.
- No wizard-local controller-profile switch. Change the mounted profile only by
  opening/restarting Hermes Dashboard under that profile, then reload and
  revalidate.
- No arbitrary repository URI/path entry, pack archive upload, or pack
  enable/disable state. Selecting a ready pack activates it only for that
  workflow; Config → Packs owns validation and bounded external-skill install.
- No credential names/values, checkout paths, requested outcomes, workflow IDs,
  or raw constraint content in saved defaults.

## Risks & open questions

- The concept is a design contract; implementation plans must cite it for
  presentation decisions rather than re-deriving layout. If a phase needs a deviation,
  it amends this document first.
- The live baseline is the currently supported Hermes v0.19.0 Hermes Teal (Large)
  presentation at 1280×720. Other themes and responsive breakpoints must continue
  to derive from host tokens and layout primitives rather than these resolved values.
