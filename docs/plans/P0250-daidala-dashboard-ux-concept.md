# Daidala dashboard UX concept and design contract

**Plan ID:** daidala-dashboard-ux-concept

**Execution slot:** P0250

**Created:** 2026-07-25

**Depends on:** none

**Plan family:** daidala-dashboard

**Entry checkpoint:** none — design contract; consumes only the shared execution contract and current `dashboard/` implementation

**Context sources:** [shared goal and current state](daidala-dashboard-execution-contract.md#goal), [operator pinning](daidala-dashboard-execution-contract.md#operator-pinning), [operator runbook coverage](daidala-dashboard-execution-contract.md#operator-runbook-coverage), [implementer discipline](daidala-dashboard-execution-contract.md#implementer-discipline), [P0210 supervision scope](P0210-daidala-dashboard-setup-and-supervision.md), [P0220 checkouts/links scope](P0220-daidala-dashboard-checkouts-and-project-links.md), [P0230 constraints/config scope](P0230-daidala-dashboard-constraints-and-verification.md), [P0240 runbook parity scope](P0240-daidala-dashboard-operator-runbook-parity.md), [P0320 artifact browser scope](P0320-daidala-artifact-dashboard-cron-and-verification.md), and the current `../dashboard/` assets

**Produces:** a single UX concept and design contract (information architecture, decision-card pattern, preview-confirm envelope, status semantics) that P0200–P0240 and P0320 cite for all dashboard presentation work

**Status:** pending — live-baseline concept drafted and preview-rendered; awaiting human design approval before implementation

## Goal

Define one UX concept for the single `/daidala` dashboard tab so every presentation
phase (P0200–P0240, P0320) renders the same decision-first, read-mostly,
exact-digest surface in the canonical Hermes Teal identity — instead of each plan
inventing its own layout. This document is a **design contract**: it owns the IA and
component patterns; it has no implementation phases and grants no approval authority.

## Design decisions (operator-pinned)

1. **Single tab, internal views.** The manifest keeps one `/daidala` tab
   (`../dashboard/manifest.json`). All navigation is internal to the tab:
   Overview / Workflow / Start / Configure / Artifacts. No manifest change.
2. **Workflow-grouped attention queue.** The Overview groups workflows by
   `Needs your decision`, `Active`, and `Recent`. Decision gates are embedded in
   their owning workflow card rather than detached into a global card, so the
   workflow identity, stage timeline, and artifacts remain visible beside every
   human action. Each attention card places an expanded-by-default, foldable
   artifact browser above the gate so the evidence is inspected before the
   authority action. The `Needs your decision` group is sorted by urgency.
3. **Configure as in-tab tabs.** Checkouts/TTL, GitHub Projects, Constraints, and
   Verification are tabs inside the Configure view, not separate manifest tabs or a
   single merged settings panel.
4. **Artifact browser in IA.** The Artifacts view (P0320) is part of this concept's
   IA from the start so its navigation and patterns land consistently.
5. **Requested outcome terminology.** The Start view labels the user-authored
   change description **Requested outcome**, not Goal. The browser still maps it
   to the existing `SetupRequest.goal` payload field; it does not invoke or imply
   Hermes' `/goal` session feature.

## Use-case catalog

Actor is always an attended human operator. Legend: ✅ implemented · 🟡 planned.

### Surface A — Onboard & verify (P0200, P0240)
1. **Verify mounted plugin/identity** 🟡 — show host/profile identity; install/enable commands displayed, never executed.
2. **Browse & validate packs** 🟡 — list/validate both packs, readiness.
3. **Preview/confirm external pack install** 🟡 — dry-run-first; apply needs confirmation.
4. **Initialize profile (dry-run-first)** 🟡 — preview data root without creating schema; confirmed apply idempotent; health/preview create nothing.
5. **Run prerequisite diagnosis** 🟡 — strict `doctor` with stable check IDs; local default + explicit bounded live; validated `project_id`; no credential values.

### Surface B — Start a workflow (P0210 Phase 0)
6. **Guided setup wizard** 🟡 — profile, pack, repository, requested outcome, stage-profiles, constraints, board; the UI maps requested outcome to the existing `request.goal` field and only nested `request` reaches `SetupRequest.from_payload`; preview → literal confirm → start.

### Surface C — Supervise & decide (P0210 Phase 1) ✅/🟡
7. **Watch workflows (read-only)** ✅ — poll ≥5s while visible; manual refresh.
8. **Approve the exact plan** 🟡 — decision-first panel; source-bound summary then verified bounded plan body, plan/constraint tuple, checklist, consequences; bound to verified artifact identity + literal "I reviewed this exact plan"; disabled on stale/mismatched identity; literal escaped text.
9. **Review disposition before delivery** 🟡 — source-bound summary + exact escaped diff + verification + findings + ledger-owned gate; accept-and-deliver only for accepted non-blocking review.
10. **Request revision** 🟡 — previewed consequences, literal confirm, navigate to new revisioned plan approval.
11. **Recover a blocked card** 🟡 — requested decision + latest relevant evidence + targeted comment/unblock.
12. **Cancel a workflow** 🟡 — preview cards/worktree/reason, digest + confirm, name affected worktree first.
13. **Reopen/resume by exact ID** 🟡 — reopen and continue read-only watch, not a new workflow.
14. **Inspect workflow artifacts** 🟡 — each workflow card expands its ledger-bound artifacts by default, reusing the Artifacts view's list/selected-detail pattern for the exact workflow; `View all` opens the Artifacts view filtered to that workflow ID without exposing a filesystem path.

### Surface D — Configure checkouts & GitHub links (P0220)
15. **Configure checkout root + TTL** 🟡 — disabled / wipe-if-clean / backup-then-wipe, default disabled; root change 409 while owned checkouts exist; `.daidala-owner` marker.
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

Three primary views + two secondary, all inside the single tab:

- **Overview (default)** — mount/health metrics, then workflow groups: `Needs your
  decision`, `Active`, and `Recent`. Each attention card contains workflow
  identity, compact stage timeline, an expanded-by-default artifact browser, and
  then its current plan, review, blocked-card, or cancellation gate. The artifact
  browser is foldable and reuses the Artifacts view's list/selected-detail pattern
  scoped to the workflow. Multiple workflows remain distinct while urgent
  decisions stay at the top. The page scrolls vertically rather than compressing
  expanded evidence and authority controls into one viewport.
- **Workflow detail** — decision-first: the active decision panel (plan approval /
  review disposition / blocked-card / cancel-preview) occupies the top ~60% with
  source-bound summary + verified evidence; below it a lower-noise stage timeline and
  card list; raw run/event detail behind progressive disclosure.
- **Start (wizard)** — identity → target → requested outcome → policy → board →
  preview → confirm → start. `Requested outcome` maps to `SetupRequest.goal` only
  at the request boundary and is not Hermes `/goal`. `Repository URI` shows the
  canonical remote (e.g. `git@github.com:forgegod/daidala.git`) and resolves to a
  trusted local checkout; it is an identity label, not a writable path.
- **Configure (secondary, tabbed)** — Checkouts/TTL, GitHub Projects, Constraints,
  Verification (read-only).
- **Artifacts (secondary)** — workflow/kind/state filters; ledger-bound artifact
  list and selected-artifact detail/escaped preview; download plus
  preview-confirm curator controls; cron opt-in guidance.

## Core component patterns

- **Workflow attention card** — the scalable Overview unit. Its header names and
  links the exact workflow, pack/board, current status, and artifact count. A
  compact stage timeline is followed by an expanded-by-default artifact browser
  and then the embedded decision card. One workflow may expose only its current
  actionable gate; other workflows render as compact read-only rows under Active
  or Recent.
- **Decision card** — one component for every authority action, always embedded
  in its owning workflow context: action-kind title,
  source-bound change summary, verified evidence (escaped text), identity tuple
  (plan/constraint/digest), consequence preview, literal-confirm checkbox, action
  button disabled until identity verified. Used for plan approval, review disposition,
  revision, cancel, checkout refresh, backup prune, link edit, constraint replace,
  pack install, profile init.
- **Embedded artifact browser** — a foldable, expanded-by-default workflow-scoped
  count/header above a compact artifact list and selected-artifact metadata plus
  literal escaped preview. `View all` opens the Artifacts view with a
  server-validated workflow filter; no client path is sent. Download remains
  read-only; pin/archive/restore stay in the full Artifacts view so the attention
  card does not combine evidence review with unrelated curation mutations.
- **Preview → confirm envelope** — every mutating form renders the exact strict
  payload + digest on Preview, then a disabled-until-confirmed apply button.
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
- **Entry from Overview:** `View all` carries only the exact workflow ID and lands
  on the filtered artifact list; the server resolves ledger identities. The
  Overview's expanded browser uses the same list/detail semantics but remains
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

## Live references and Pen design source

The live baseline and adapted concepts are stored beside this document. The Pen
source is an open-format `.pen` file with three 1280×720 frames and a 1280×1000
scroll-page Overview frame. The longer Overview preserves two expanded artifact
browsers and their gates without compressing evidence or controls. The source is
layout-checked and exported with the headless Pen CLI; Pen Desktop remains
available through Irigate for interactive editing.

| File | Purpose |
|---|---|
| [`hermes-dashboard-live-sessions.png`](hermes-dashboard-live-sessions.png) | Live Hermes v0.19.0 Sessions page; shell, metrics, tabs, list/status patterns |
| [`hermes-dashboard-live-kanban.png`](hermes-dashboard-live-kanban.png) | Live Kanban plugin; plugin integration, fieldsets, filters, lanes, cards, empty states |
| [`hermes-dashboard-ux-live.pen`](hermes-dashboard-ux-live.pen) | Editable Pen source with Overview, Start, Configure, and Artifacts frames |
| [`dashboard-ux-overview.png`](dashboard-ux-overview.png) | Scroll-page workflow overview with expanded artifact browsers above plan/review gates |
| [`dashboard-ux-wizard.png`](dashboard-ux-wizard.png) | Start wizard (preview → confirm → start) |
| [`dashboard-ux-config.png`](dashboard-ux-config.png) | Configure tabs (Checkouts/TTL + read-only verification) |
| [`dashboard-ux-artifacts.png`](dashboard-ux-artifacts.png) | Ledger-bound artifact browser, detail/escaped preview, and curator actions |
| [`hermes-dashboard-live-plugins.png`](hermes-dashboard-live-plugins.png) | Live Plugins page; gap scale and fieldset/input rhythm reference |

The live comparison changed the concepts in five concrete ways: reproduce the
profile-scope banner and Large-scaled sidebar; use host segmented tabs and primary
buttons; use bordered metrics and fieldset-like controls; reserve rounding for
content cards; and separate the non-mutating preview result from confirmation to
apply the displayed mutations. Configure subtabs use an accent surface rather
than competing with primary navigation's cream selected state.

The information model uses `Requested outcome` rather than `Goal`; Overview
decision gates live inside workflow cards; the multiple-workflow example contains
both plan approval and review disposition; each attention card expands its
ledger-bound artifacts above the gate; and Artifacts has a complete two-pane
concept rather than navigation-only scope.

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
snapshot_layout({ parentId: "Ov001", maxDepth: 8, problemsOnly: true })
export_nodes({ nodeIds: ["Ov001", "Wi001", "Cf001", "Ar001"], outputDir: "/tmp/daidala-ux-export", format: "png", scale: 1 })
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
| A Onboard/verify | 1–5 | Overview status strip + Configure → Verification |
| B Start | 6 | Start wizard |
| C Supervise/decide | 7–14 | Workflow-grouped Overview attention cards + Workflow detail |
| D Checkouts/links | 15–18 | Configure → Checkouts & GitHub |
| E Constraints/config | 19–20 | Configure → Constraints & Verification |
| F Artifacts | 21–23 | Artifacts view; workflow-filtered entry from Overview |
| Runbook parity | 24 | Overview guidance panel (host-owned commands) |

## Out of scope

- No implementation phases, routes, or code — P0200–P0240 and P0320 own those.
- No manifest change; the single `/daidala` tab is preserved.
- No new mutation surface, workflow engine, scheduler, or command-dispatch route.
- No change to `SetupRequest`, registration storage, review/revision semantics,
  Kanban authority, or the closed route inventory.

## Risks & open questions

- The concept is a design contract; implementation plans must cite it for
  presentation decisions rather than re-deriving layout. If a phase needs a deviation,
  it amends this document first.
- The live baseline is the currently supported Hermes v0.19.0 Hermes Teal (Large)
  presentation at 1280×720. Other themes and responsive breakpoints must continue
  to derive from host tokens and layout primitives rather than these resolved values.
