# Dashboard integration and guided setup plan

> Status: execution in progress. Phases 0–3 completed on 2026-07-12; Phase 4
> remains unstarted.
>
> For the implementing agent: read `/AGENTS.md`, `docs/AGENTS.md`,
> `wingstaff/AGENTS.md`, `tests/AGENTS.md`, this plan, the current official Hermes
> [dashboard extension documentation](https://hermes-agent.nousresearch.com/docs/user-guide/features/extending-the-dashboard),
> and the active implementation plan under `docs/plans/`. Stop when any gate fails.

## Goal

Make Wingstaff easier to adopt and operate through a guided setup skill and,
only if the supported-host probe succeeds, a complementary dashboard surface:

1. an officially distributed `wingstaff:setup` skill that guides installation,
   environment checks, board selection or creation, profile mapping, pack setup,
   constraint authoring, and first workflow start; and
2. an optional drop-in extension of the existing Hermes dashboard that visually simplifies
   setup and shows live progress, pending human decisions, current constraints,
   and deterministic next-action recommendations.

The setup skill remains independently releasable if the dashboard track is
dropped. The dashboard is a presentation and command surface over Wingstaff and Hermes. It
must not become a second dashboard server, workflow engine, Kanban authority,
policy store, scheduler, or model client.

## Recommendation based on current progress

Implement the setup skill first, after a short host-feasibility probe, then add the
visual dashboard layer over the same contracts.

Wingstaff already has the difficult runtime guarantees: a Kanban-native card
 graph, exact skill provenance, workflow-scoped constraints, approval bound to
plan and constraint identity, stale-worker rejection, immutable evidence, and a
release compatibility probe. The missing value is operator convenience, not a
new orchestration mechanism.

The recommended delivery order is therefore:

1. prove how the supported Hermes host discovers dashboard assets and backend
   routes;
2. ship `wingstaff:setup` as the smallest immediately useful onboarding path;
3. expose a minimal profile-safe dashboard read model and deterministic action
   previews;
4. add the visual setup wizard and constraint editor only after the read path is
   proven end to end.

This order gives users a guided setup path even when they do not run the web
 dashboard. It also prevents the UI from inventing contracts that the skill, CLI,
and tools do not share.

## Current context

Implemented Wingstaff behavior already provides:

- `wingstaff_pack_info`, `wingstaff_start`, `wingstaff_status`,
  `wingstaff_replace_constraints`, `wingstaff_approve`, and cancellation and
  evidence tools;
- one explicit named board and a complete executable-stage profile map per
  workflow;
- live Kanban status combined with Wingstaff policy facts without status
  mirroring;
- immutable constraint revisions and exact plan-plus-constraint approval;
- an isolated compatibility probe for Hermes Agent v0.18.2;
- a bundled `wingstaff:orchestrate` worker skill.

The current official Hermes dashboard supports runtime themes, UI plugins, named
shell and page slots, and optional FastAPI routers mounted inside the existing
Hermes dashboard process. Dashboard plugins are discovered from a
`dashboard/manifest.json` subtree in a Hermes plugin directory and use the SDK on
`window.__HERMES_PLUGIN_SDK__`. That documented shape appears compatible with
Wingstaff's existing Git-directory installation, but it has not been exercised
against Wingstaff's pinned Hermes host and therefore remains a Phase 0 gate.

## Architecture and authority

| Concern | Authority |
|---|---|
| Boards, cards, dependencies, assignment, claims, retries, comments, and live status | Hermes Kanban |
| Pack, policy, approval, artifact, worktree, and evidence integrity | Existing Wingstaff service and ledger |
| Setup guidance and decisions about user intent | `wingstaff:setup` skill, with explicit confirmation before mutation |
| Dashboard rendering and local form state | Wingstaff dashboard UI plugin |
| Dashboard data and mutation boundary | Thin backend adapter calling existing Wingstaff services and documented Hermes operations |
| Next-action recommendation | Pure deterministic projection from current Wingstaff policy facts and live Kanban state |

No dashboard endpoint may import or write Hermes Kanban internals, access its
SQLite database, or persist a second copy of operational status. No UI action may
weaken the exact approval or constraint compare-and-swap checks.

## User experience

### Guided skill path

A user loads `wingstaff:setup`. The skill:

1. checks plugin, supported Hermes version, gateway/dispatcher, installed packs,
   required exact skills, available profiles, and named boards;
2. explains missing prerequisites and proposes explicit commands or tool calls;
3. lets the user select an existing board or explicitly approve creation of a
   named board;
4. defaults all executable stages to one selected profile and asks only for
   exceptional stage overrides;
5. offers no constraints, a validated starter template, an explicit file, or an
   exact installed policy skill;
6. previews the complete `wingstaff_start` input and asks for confirmation;
7. starts the workflow through the existing tool and points the user to Kanban or
   the Wingstaff dashboard tab.

The skill uses the exact argument names owned by `schemas.py::START`. It does not
create a second setup schema or infer paths, skills, profiles, boards, or policy
sources from arbitrary prose.

### Visual dashboard path

The `/wingstaff` tab has four focused views:

- **Setup** — a short wizard for prerequisites, board, default profile and
  overrides, pack, goal, constraints, preview, and start.
- **Workflows** — live workflow cards with current policy revision, constraint
  digest, approval state, and Kanban progress.
- **Decisions** — human-action items only: plan approval, blocked cards requiring
  input, stale approval after policy change, and constraint replacement impact.
- **Constraints** — full validated YAML, provenance, revision history, and a
  preview-before-replace editor.

A small page-scoped slot may show the number of pending Wingstaff decisions on a
built-in Hermes page. Use augmentation, not `tab.override`; Wingstaff must not own
or replace a built-in Hermes page.

### Visually simplified Kanban setup

Do not recreate Kanban columns or board administration. Simplify only the choices
Wingstaff needs:

- present existing named boards as selectable cards rather than requiring a slug
  from memory;
- provide an explicit “create board” path only if Phase 0 proves a documented
  public operation usable inside the dashboard process;
- show one default profile selector, with a collapsed “stage overrides” section;
- preview the resulting seven-card lifecycle before start;
- show the selected board as the lifecycle authority and link to the native
  Kanban view after creation.

If safe board creation is not available through the supported public boundary,
the UI must show the exact external command and refresh after the user runs it.
It must not use a private import or direct database write as a fallback.

## Pending decisions and recommendations

Pending decisions are derived, not persisted as a new status vocabulary. The
backend owns this complete action-kind vocabulary; the skill and UI must not
invent aliases:

| Action kind | Current evidence | Pending decision or recommendation |
|---|---|---|
| `approve_current_tuple` | Plan artifact exists and exact tuple is not approved | Review the plan and approve its displayed plan and constraint digests. |
| `reapprove_current_tuple` | Approval exists but current plan or constraint identity differs | Re-review and approve the current tuple; stale approval cannot be reused. |
| `resolve_blocked_card` | A card is blocked with `needs_input` | Read its latest evidence and comment with the requested decision, then use normal Kanban unblock. |
| `restore_capability` | A card is blocked with `capability` | Fix the named profile, tool, skill, access, or context problem before retrying. |
| `resolve_verification_failure` | Verification evidence has a non-zero exit code | Inspect the immutable output and choose plan replacement or an evidence-backed retry. |
| `replace_rejected_plan` | Review rejects the captured implementation | Replace the plan; do not patch the captured diff in place. |
| `wait_for_dispatch` | All prerequisites for the next linked card are complete | Wait for or inspect Hermes dispatch; do not create duplicate work. |
| `deliver_reviewed_diff` | Deliver is ready | Review the immutable diff and evidence, then run delivery; commit and push remain false. |

Every recommendation payload contains `action_kind`, `workflow_id`, optional
`card_id`, current plan revision/digest, current constraint revision/digest,
optional `evidence_ref`, `rationale`, and optional `blocker_kind`. Blocked-card
payloads also identify the concrete missing profile, skill, capability, comment,
or verification command and exit code. Recommendations do not use an LLM, write
ledger state, dismiss policy failures, or claim that a Kanban unblock grants
Wingstaff approval.

## Execution phases

Execute one phase per committed checkpoint after approval. A later phase remains
unstarted until the current phase gate passes.

| Phase | Status | Scope | Gate |
|---|---|---|---|
| 0. Supported-host feasibility | Done | Prove dashboard discovery, packaged assets, UI registration, backend route mounting, profile-path resolution, and documented Kanban operations against an isolated pinned Hermes host. | `195 passed in 12.45s`; live probe and browser assertions passed. |
| 1. Official setup skill | Done | Add and register `wingstaff:setup`, preserving the current start schema and human confirmation boundary. | `198 passed in 16.24s`; fresh-process `wingstaff:setup` load passed. |
| 2. Dashboard read model | Done | Add profile-safe read-only backend routes and pure pending-decision/recommendation derivation. | `204 passed in 15.33s`; focused router/recommendation tests and Ruff passed. |
| 3. Read-only dashboard UI | Done | Add the Wingstaff tab, workflow/progress cards, decisions view, and a pending-decision slot. | Isolated Hermes v0.18.2 desktop/narrow browser states and `sessions:top` slot passed; dashboard tests passed. |
| 4. Setup wizard and board simplification | Todo | Add prerequisite checks, visual board/profile/pack selection, lifecycle preview, explicit confirmation, and start. | Isolated first-run flow creates exactly one initial graph through public operations. |
| 5. Constraint preview and replacement | Todo | Add full YAML editor, canonical preview, digest and impact display, compare-and-swap replacement, and renewed-approval guidance. | Preview identity equals service identity; invalid and stale replacements fail closed. |
| 6. Theme, docs, packaging, and release gate | Todo | Add optional theme, package assets, operator docs, compatibility checks, and release verification. | Full repository and supported-host gates pass. |

## Phase 0 — supported-host feasibility

### Objective

Resolve packaging and host-version unknowns before designing the UI API.

### Probes

Using an isolated `HERMES_HOME` and the exact supported Hermes identity:

1. install or link Wingstaff using the same directory-plugin shape used by the
   release probe;
2. place a minimal `dashboard/manifest.json`, IIFE bundle, stylesheet, and
   `plugin_api.py` beneath the Wingstaff plugin directory;
3. start the existing Hermes dashboard on a non-default local test port;
4. verify `/api/dashboard/plugins` discovers Wingstaff and serves its static
   bundle;
5. verify the bundle registers one tab and one page-scoped slot through the SDK;
6. verify `/api/plugins/wingstaff/health` is mounted after process startup;
7. determine whether wheel/entry-point installations expose package dashboard
   assets automatically or require an installer/materialization step;
8. prove the public board inventory, optional board creation, profile inventory,
   and card-link targets available to the dashboard adapter.

### Likely files

- `scripts/probe_hermes_dashboard_compatibility.py`
- `tests/test_hermes_dashboard_compatibility_probe.py`
- `scripts/AGENTS.md`
- `tests/AGENTS.md`
- `docs/08-hermes-integration.md`

### Gate and decision

Record the exact supported layout and transport as a written Phase 0 decision in
this plan. The probe must also determine whether the dashboard process receives
the agent-process `configure_host(dispatch_tool)` binding. If it does not, select
one documented public alternative, preferably the existing injected
`hermes kanban` CLI adapter; never treat a Kanban-less `WorkflowService` as live
status. If Git-directory plugins work but
wheel entry points do not materialize dashboard assets, choose one explicit
installation contract:

- preferred: package assets and have Wingstaff's existing dry-run/apply setup
  operation materialize them into the profile's plugin directory; or
- fallback: distribute a separately installable, version-locked dashboard
  directory and have `wingstaff:setup` guide its installation.

Do not implement both transports or silently copy assets at import time. If
dashboard discovery or a public live-status boundary fails on the pinned host,
drop Phases 2–5, retain the independently useful setup-skill track, amend this
plan, and obtain approval for the reduced scope. Do not leave the dashboard
track indefinitely deferred.

Stop if the pinned Hermes host lacks the documented dashboard extension boundary.
Amend and reapprove the plan before raising the supported baseline.

### Phase 0 decision

Hermes Agent v0.18.2 (build `2026.7.7.2`, upstream `4281151a`) provides the
required dashboard extension boundary with plugin SDK `1.1.0`. An isolated live
host discovered a user plugin from
`$HERMES_HOME/plugins/wingstaff/dashboard/manifest.json`, served its manifest,
IIFE, and stylesheet, registered `/wingstaff`, rendered a `sessions:top` slot,
and mounted an auth-gated FastAPI router. Browser automation confirmed the tab,
page, slot, and SDK global with no console error.

Two expected shapes were not available. The documented page-slot catalogue has
no `kanban:top` slot, so Wingstaff will use `sessions:top` for the compact pending-
decision augmentation and retain its normal `/wingstaff` tab. A pip entry point
does not materialize dashboard files into the profile plugin directory, so the
single installation contract is to package the assets and extend Wingstaff's
existing dry-run/apply setup operation to materialize the `dashboard/` subtree
under the active profile's plugin directory. Import-time copying and a second
dashboard distribution remain prohibited.

The dashboard process does not provide a durable agent-process
`configure_host(dispatch_tool)` binding to backend route modules. Dashboard
adapters will therefore use documented subprocess boundaries: `hermes kanban`
for board inventory, board creation, and live card operations, and `hermes
profile list` for profile inventory. The live pinned host proved board listing
as JSON and public board creation through `hermes kanban boards`; profile list
is a documented human-readable CLI surface and requires a strict parser with
malformed-output tests before Phase 2. No private import or database access is
authorized.

The executable probe is `scripts/probe_hermes_dashboard_compatibility.py`.
Repository tests verify host-identity, discovery, asset, auth, drift, and cleanup
contracts; browser integration remains the final UI gate in Phases 3–5.

## Phase 1 — official `wingstaff:setup` skill

### Objective

Deliver a useful onboarding path independent of the web dashboard.

### Files

- `wingstaff/skills/setup/SKILL.md`
- optional focused references under `wingstaff/skills/setup/references/`
- `plugin.yaml`
- `pyproject.toml` package-data assertions if references are added
- `wingstaff/__init__.py`
- `tests/test_worker_contract.py` or a focused setup-skill contract test
- `tests/test_installation.py`
- `wingstaff/AGENTS.md`
- `docs/00-getting-started.md`

### Contracts

- Register the bundled skill as `wingstaff:setup` and declare it in
  `plugin.yaml`.
- Keep setup and orchestration separate: setup prepares and starts; workers still
  use `wingstaff:orchestrate`.
- Use `wingstaff_pack_info`, existing Hermes status/board/profile surfaces, and
  `wingstaff_start`; do not encode another copy of pack data.
- Preview all mutations and require explicit human approval.
- Prefer one default profile and optional overrides.
- Offer dashboard and CLI completion paths with equivalent inputs.
- Publish the skill with Wingstaff's normal release artifact; “official” means
  versioned, tested, documented, and distributed by the Wingstaff project rather
  than created in a user's mutable local skill store.

### Gate

A fresh-process plugin probe loads `skill_view("wingstaff:setup")`; package-content
checks include it; contract tests assert the current start parameter names and the
human-confirmation boundary. A dashboard-independence test must prove the skill
produces the same `wingstaff_start` request when the dashboard is unavailable.

## Phase 2 — dashboard read model

### Objective

Expose only the data needed by the UI through the existing Hermes dashboard
process.

### Proposed endpoints

- `GET /api/plugins/wingstaff/health`
- `GET /api/plugins/wingstaff/prerequisites`
- `GET /api/plugins/wingstaff/workflows`
- `GET /api/plugins/wingstaff/workflows/{workflow_id}`
- `GET /api/plugins/wingstaff/workflows/{workflow_id}/decisions`
- `GET /api/plugins/wingstaff/workflows/{workflow_id}/recommendations`
- `POST /api/plugins/wingstaff/constraints/preview`

The constraint preview endpoint is non-mutating. It returns validation errors,
canonical content, digest, size, and replacement consequences for a supplied
workflow identity and expected current digest.

### Files

- dashboard backend module at the exact path proven by Phase 0
- `wingstaff/recommendations.py` for pure derivation, if keeping it in the router
  would mix policy with HTTP concerns
- focused router and recommendation tests
- `wingstaff/AGENTS.md`

### Contracts

- Construct `WorkflowService` with the same profile-aware location and public
  Kanban boundary as existing tool and CLI paths.
- Add the smallest service query needed to list workflow ledgers; do not scan or
  query Kanban SQLite.
- Read live card state on request and label unavailable host data as unavailable,
  not cached truth.
- Return only the machine-readable action kinds defined in this plan's pending-
  decisions table, with exact identities and rationale.
- Do not expose secrets, raw environment values, or unbounded logs.

### Gate

Tests cover every recommendation row above, malformed host output, missing cards,
stale identities, absent constraints, and unavailable Kanban. A source audit finds
no new persistence table and no mirrored card-status field.

### Phase 2 decision

The dashboard backend reads the existing profile-local policy store and obtains
current card state through the documented `hermes kanban` subprocess adapter.
It does not depend on agent-process tool dispatch or read Hermes storage
directly. Host failures remain explicitly unavailable rather than cached truth.

`wingstaff/recommendations.py` owns the closed action vocabulary and pure
derivation. `dashboard/plugin_api.py` exposes the read routes and non-mutating
constraint preview through the FastAPI router proven in Phase 0. The repository
gate passed with 204 tests and Ruff clean.

## Phase 3 — read-only dashboard UI

### Objective

Prove the visual progress and decision experience before adding mutations.

### Files

- `dashboard/manifest.json`
- `dashboard/dist/index.js`
- `dashboard/dist/style.css`
- UI asset packaging or materialization code selected in Phase 0
- dashboard load and asset-content tests

### UI contract

- Register a normal `/wingstaff` tab after the native Kanban tab when supported.
- Add one compact pending-decision badge/card through a documented page-scoped
  slot; do not replace native Kanban or Sessions pages.
- Render progress from live card statuses and policy identity from Wingstaff.
- Link every decision to its workflow, underlying card, and artifact/evidence.
- Treat every response as a timestamped snapshot and never use client state to
  authorize a retry or mutation. Phase 0 must check for a documented SDK event,
  SSE, or WebSocket source. Use it if available; otherwise poll no faster than
  every five seconds while the tab is visible, stop polling when hidden, and
  provide manual refresh.
- Remain usable under built-in Hermes themes and narrow layouts.

### Gate

An isolated real dashboard discovers and renders the plugin. Browser console and
network logs contain no load errors. Screenshots verify progress, no-workflow,
pending-approval, blocked-card, and host-unavailable states. No write endpoint is
called.

### Phase 3 decision

The dependency-free IIFE registers `/wingstaff` and `sessions:top` through SDK
1.1.0, authenticates scoped GET requests with the dashboard session token, and
polls every five seconds only while visible. Browser execution against isolated
Hermes v0.18.2 verified desktop and 390-pixel layouts, no-workflow, pending
approval, blocked card, host-unavailable, and an exact two-decision slot count.
The browser gate exposed and fixed missing Bearer authentication, incorrect
host-unavailable interpretation, low-contrast fallback colors, and workflow-
count substitution in the decision slot.

## Phase 4 — setup wizard and board simplification

### Objective

Turn Wingstaff's required inputs into a short visual flow without hiding policy.

### Steps

1. Show prerequisite checks and actionable fixes.
2. Select an existing board; offer explicit creation only through the Phase 0
   public operation.
3. Select one default profile and optionally expand stage overrides.
4. Select and validate a pack and its exact skills.
5. Enter target repository, stable workflow ID, and goal.
6. Select no constraints, starter template, explicit content, or exact policy
   skill with digest.
7. Preview the board, seven-stage graph, profiles, pack, constraints, and all
   mutations.
8. Require explicit confirmation and call one backend command adapter that invokes
   the existing `WorkflowService.start` path.
9. Display returned card identities and link to native Kanban.

### Mutation boundary

Add only narrowly scoped endpoints required for prerequisite remediation, optional
board creation, and workflow start. Each endpoint validates an explicit typed
request, returns an action preview where applicable, and calls existing public
Wingstaff or Hermes operations. It does not accept arbitrary commands.

### Gate

A browser-driven isolated test creates or selects one board and starts the same
workflow twice without duplicate cards. Missing profiles, dirty targets, missing
skills, malformed constraints, and declined confirmation create no workflow graph.

## Phase 5 — constraint preview and replacement

### Objective

Make policy editing understandable without weakening the existing invalidation
contract.

### UX contract

- Show complete current YAML or canonical representation, source provenance,
  revision, digest, and byte limits; never truncate constraint text.
- Surface the server's exact limits: at most 16 global and 16 per-phase items,
  1–1,024 UTF-8 bytes per item, 4,096 canonical UTF-8 bytes, and an 8,192-character
  rendered-card limit. Client checks improve feedback but never replace server
  validation.
- Validate on demand through `wingstaff/constraints.py`, not duplicated
  JavaScript rules.
- Preview semantic identity: formatting-only changes are shown as no-op.
- For real changes, warn that approval, activation, evidence eligibility,
  worktree, and current cards are invalidated and a fresh define/plan graph is
  created.
- Require the displayed expected current digest and explicit confirmation.
- Call the same `replace_constraint_input` service path used by tools and CLI.
- Display the returned archival, worktree, new graph, and approval consequences.

### Gate

Tests prove preview and replacement canonical digests match exactly; stale
compare-and-swap, oversized text, forbidden fields, methodology-like content
handling, host cleanup failure, and retry behavior remain fail-closed and
idempotent.

## Phase 6 — theme, docs, packaging, and release gate

### Scope

- Add an optional restrained Wingstaff dashboard theme only if it improves setup
  readability; the UI must not require it. If omitted, no theme files may appear
  in the release artifact merely as dormant scaffolding.
- Update `README.md`, `docs/00-getting-started.md`, `docs/01-architecture.md`,
  `docs/02-workflow-state.md`, `docs/07-runbook.md`,
  `docs/08-hermes-integration.md`, `docs/14-workflow-constraints.md`,
  `docs/README.md`, and owning AGENTS.md files.
- Extend package-content checks for dashboard assets and the setup skill.
- Extend the release-only Hermes compatibility gate with dashboard discovery,
  route, and registration evidence at the selected supported host boundary.
- Document skill-first, dashboard-first, and CLI fallback paths without making
  the dashboard mandatory.

### Gate

```bash
lefthook validate
pytest
ruff check .
wingstaff packs validate addyosmani
wingstaff packs validate aidlc
python -m build
python -m twine check dist/*
python scripts/check_release_contents.py . --wheel dist/*.whl
python scripts/check_md_links.py .
python scripts/probe_hermes_compatibility.py
python scripts/probe_hermes_dashboard_compatibility.py
git diff --check
```

The release artifact must load both `wingstaff:setup` and
`wingstaff:orchestrate`, expose the documented dashboard assets through the chosen
transport, and complete one isolated setup-to-pending-approval flow.

## Likely files to change

The exact dashboard paths depend on Phase 0. Expected ownership includes:

- `plugin.yaml`
- `pyproject.toml`
- `wingstaff/__init__.py`
- `wingstaff/service.py`
- `wingstaff/recommendations.py` (new)
- `wingstaff/skills/setup/SKILL.md` (new)
- `dashboard/manifest.json` (new)
- `dashboard/plugin_api.py` or the supported equivalent (new)
- `dashboard/dist/index.js` and `dashboard/dist/style.css` (new)
- focused tests under `tests/`
- release and compatibility scripts under `scripts/`
- the owning operator, architecture, integration, constraint, runbook, package,
  and DOX documents.

## Risks and tradeoffs

### Supported Hermes version may predate dashboard extension support

Official current documentation is not evidence for the pinned v0.18.2 runtime.
Phase 0 must prove the feature against the supported host. Prefer raising the
minimum supported version through the existing release process over private
imports or two implementations.

### General-plugin and dashboard-plugin packaging may differ

A pip entry point discovers Python registration, while dashboard discovery is
path-based. Do not assume wheel package data appears in the profile plugin
 directory. Choose one explicit materialization or separate-install contract after
probing it.

### Backend routes have a different trust boundary

Hermes documents plugin routes as running in its local dashboard process. Keep the
dashboard bound to localhost, expose no secrets, use strict request models and
existing service validation, and document that untrusted plugins and public
binding increase risk.

### Setup convenience can hide important policy

The wizard may default stages to one profile and offer starter constraints, but it
must preview board, profiles, pack, policy source, invalidation effects, and the
exact start action before mutation.

### Recommendation logic can become another workflow engine

Keep recommendations pure, finite, and derived from current facts. They may say
what action is available and why; they must not dispatch workers, mutate cards,
score users, or predict completion.

### Browser delivery without a frontend build system

Hermes accepts a pre-built IIFE. Prefer a small dependency-free bundle using the
SDK's React and components. Add a bundler only if the UI complexity demonstrably
requires it, and then pin and audit the build dependency without shipping React.

## Out of scope

- a standalone Wingstaff dashboard or HTTP service;
- replacing a built-in Hermes page;
- mirroring or editing Kanban status outside public Hermes operations;
- automatic profile creation, credential entry, commit, push, deployment, merge,
  or pull-request creation;
- arbitrary shell execution from dashboard requests;
- live log streaming, model chat, artifact-body editing, or another scheduler;
- LLM-generated recommendations or automatic approval;
- backward-compatible alternate setup schemas.

## Future ideas — deferred, not authorized for execution

The following ideas are recorded for future planning only. They are not part of
Phases 0–6, create no current acceptance criteria, and must not be implemented as
incidental extensions of the dashboard or setup skill. Each requires a separate
source-backed plan, approval gate, and committed execution phases.

### Visual pack authoring

Allow an operator to define a new workflow pack by selecting lifecycle stages,
mapping exact external or bundled skills, declaring required or conditional
activation, and previewing the resulting card graph. The editor would emit a
normal pack artifact and run the existing deterministic pack validator; it must
not add pack-specific branches to the engine or invent skill content.

This is deferred because pack authoring changes a supply-chain and methodology
contract, not merely setup presentation. A future plan must specify provenance,
licensing, exact source revisions and digests, validation errors, storage,
distribution, and how an authored pack becomes available to other profiles.

### Pack source installation and revision management

Extend the setup skill and dashboard to discover, preview, install, check, and
update external pack sources through the existing dry-run-by-default mutation
boundary. The user would see every source, revision, skill, digest, and intended
filesystem mutation before applying it.

This is deferred until a separate plan proves a safe public installation path for
arbitrary sources. It must preserve exact-name matching, pinned revisions,
complete-directory digests, supported-Hermes bounds, post-apply verification,
and the rule that active workflows never update implicitly.

### Bundled pack-adapter development

Provide a guided developer workflow for adding a new adapter to the Wingstaff
distribution, including source and license audit, stage mapping, bundled skill
resources where justified, pack-neutral fixtures, release-content checks, and
cross-pack verification. This is a repository development workflow, not an
end-user dashboard mutation; the dashboard may eventually generate a reviewed
proposal but must not rewrite its installed package.

### Board and workflow templates

Allow users to save a reusable, non-secret template containing a board naming
pattern, selected existing pack, default profile plus stage overrides, and either
validated constraint content or an exact policy-skill reference. Instantiating a
template would still show a complete preview and require confirmation before
board creation or `wingstaff_start`.

A future plan must define template scope and ownership explicitly. Constraints
remain workflow-scoped after materialization, packs remain independently
selected, and a template must not turn either into board-global policy.

### Clone a prior workflow setup

Offer “start similar workflow” from an existing workflow by copying only
operator-selectable setup inputs: board choice, pack, stage-profile map, and
constraint source or materialized content. Never copy approval, plan artifacts,
card IDs, worktrees, activation manifests, evidence, or live status. The clone
must receive a new stable workflow ID, fresh baseline, fresh graph, and fresh
human approval.

### Multi-workflow overview and batch admission

Add portfolio views that group workflows by board, repository, pack, pending
decision, or profile lane. A later batch-admission flow could preview several
independent starts, but each workflow must retain its own validation result,
constraint identity, confirmation, graph, and approval gate. Partial failure must
not create ambiguous shared state or roll back unrelated successful workflows.

### Broader environment remediation

The setup skill may eventually guide explicit creation of dedicated Hermes
profiles, toolset configuration, gateway installation, and external skill setup.
Credential values must remain outside model and dashboard responses, every
mutation must be previewed, and Hermes' native setup/configuration surfaces remain
the authority. Automatic credential entry and silent profile creation remain
prohibited unless a future security review establishes a narrower safe contract.

### Explicitly excluded future directions

Do not reopen the following as convenience features without first changing the
project architecture through a separately approved decision:

- a standalone Wingstaff dashboard, daemon, scheduler, MCP server, or second
  Kanban/state store;
- LLM-generated operational status, recommendations, approvals, constraints, or
  pack definitions presented as deterministic facts;
- direct Kanban database access, private Hermes imports, or arbitrary shell
  execution from dashboard requests;
- automatic commit, push, deployment, merge, or pull-request creation.

## Acceptance criteria

- `wingstaff:setup` is officially bundled, versioned, loadable, and usable without
  the web dashboard.
- The visual setup path uses the same start arguments and service path as the
  skill, tool, and CLI.
- Board setup is visually reduced to selection, optional public creation, one
  default profile, optional overrides, lifecycle preview, and explicit confirm.
- Live progress comes from Hermes Kanban and is never mirrored as Wingstaff state.
- Pending decisions and recommendations are deterministic projections with exact
  workflow, card, policy, and evidence identity.
- Constraint preview and replacement use the existing parser, canonical digest,
  compare-and-swap, invalidation, and approval rules; text is never truncated.
- The dashboard extends the existing Hermes process and introduces no daemon,
  server, MCP service, nested `hermes chat`, or second state authority.
- Git-directory and release installation behavior is explicit and verified.
- All published commands and UI actions pass isolated supported-host probes.

## Stop conditions

Stop implementation and ask the user when:

- dashboard extension support cannot be proven on the supported Hermes host;
- packaging requires two divergent dashboard implementations;
- a requested UI action lacks a documented public Hermes or existing Wingstaff
  service boundary;
- board setup would require direct Kanban database access or private imports;
- a dashboard write would bypass `WorkflowService`, constraint
  compare-and-swap, exact approval, or worktree ownership checks;
- recommendations require model judgment or new persisted lifecycle state;
- full constraint content cannot be displayed and validated without truncation;
- any verification gate fails.

## Approval checkpoint

The user approved this plan's recommendations on 2026-07-12. That approval does
not start Phase 0 and does not authorize any item under **Future ideas**. Begin
Phase 0 only after a separate explicit start instruction, then execute one phase
at a time with a committed checkpoint. Phase 0 may change the proposed file
layout and minimum supported Hermes version; any such change must be written into
this plan and approved before Phase 1 begins.
