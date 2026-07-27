# Daidala dashboard setup and workflow supervision

**Plan ID:** daidala-dashboard-setup-and-supervision

**Execution slot:** P0210

**Created:** 2026-07-23

**Depends on:** daidala-dashboard-user-config-packs-start-constraints-github-links, daidala-artifact-access-core, daidala-review-disposition-and-revision-loop

**Split from:** daidala-dashboard-user-config-packs-start-constraints-github-links

**Plan family:** daidala-dashboard

**Entry checkpoint:** P0200 completed with a verified mounted host, disposable fixture recipe, and pack readiness surface; P0205 completed exact current-plan artifact resolution; P0207 completed structured review, attended disposition, revision-loop authority, and synchronized runtime documentation

**Context sources:** [UX concept and design contract](P0250-daidala-dashboard-ux-concept.md), [shared goal and current state](daidala-dashboard-execution-contract.md#goal), [browser fixture and mutation boundaries](daidala-dashboard-execution-contract.md#operator-pinning), [approval summary and escaped-text contract](daidala-dashboard-execution-contract.md#approval-summary-and-escaped-text-contract), [review disposition contract](daidala-dashboard-execution-contract.md#review-disposition-and-revision-loop-contract), [SetupRequest envelope decision](daidala-dashboard-execution-contract.md#setup-request-envelope), [operator runbook coverage](daidala-dashboard-execution-contract.md#operator-runbook-coverage), [implementer discipline](daidala-dashboard-execution-contract.md#implementer-discipline), [workflow-cancellation risk](daidala-dashboard-execution-contract.md#risk-call-out), [runbook start and resume](../07-runbook.md#start-and-resume-a-workflow), [exact approval](../07-runbook.md#approve-the-exact-plan), [cancellation](../07-runbook.md#cancel), [recovery](../07-runbook.md#recovery), [artifact resolver contract](daidala-artifact-review-execution-contract.md#phase-0-add-the-ledger-owned-artifact-catalog-and-resolver), P0205 and P0207 completion evidence, and detailed [contract Phase 2](daidala-dashboard-execution-contract.md#phase-2-first-workflow-setup-wizard-ux) and [contract Phase 3](daidala-dashboard-execution-contract.md#phase-3-workflow-supervision-actions)

**Produces:** an inventory-backed first-workflow wizard with mounted-profile scope, registered-repository capability readiness, non-authoritative defaults and Hermes Cron handoff, plus decision-first plan approval, review disposition, revision request, recovery, and cancellation controls over existing Daidala and Hermes authority surfaces

**Status:** Phases 0 and 1 complete — the registered setup boundary and inventory-backed first-workflow wizard pass their automated and disposable-browser gates; Phase 2 is pending

## Goal

Add the browser path that resolves one mounted-profile registration into the existing setup model, starts a first workflow only after exact capability readiness, reopens an existing exact workflow as the runbook's resume path, and supervises it without introducing a second workflow engine, scheduler, timed pause, or general command-dispatch route.

## Current state

- P0200 owns the mounted host, fixture recipe, pack readiness, and supported React SDK boundary.
- P0205 owns exact ledger-bound plan text resolution; approval must consume it rather than a profile-local path.
- P0207 owns structured automated review, attended review disposition, delivery release, revision-request cleanup, revisioned planning, CLI fallback, and synchronized current-behavior documentation; this plan only presents those services in Hermes Dashboard.
- `SetupRequest.from_payload`, `confirmed_start`, workflow read models, approval, Kanban recovery, and cancellation already define the authority boundaries.
- The current pending-decision UI shows only generic rationale and does not render the plan body or complete tuple; approving from that surface would not be informed consent.
- The shared contract pins the exact request envelope, blank workflow-ID behavior, disposable fixture rules, closed route inventory, and cancellation recovery path; resume means reopen and continue watching an existing workflow, not create a duplicate.

## Phase table

| # | Phase | Status | Verification gate |
|---|---|---|---|
| 0 | Establish the registered setup boundary | done (`python -m pytest -q`; Ruff; Lefthook; pack/link/build/release checks; isolated live Hermes compatibility probe) | The service and closed dashboard routes resolve only a selected mounted-profile registration into the exact `SetupRequest` path, share mutation-free start readiness with confirmed start, bind preview/apply to a fresh exact digest, and reject browser paths, unknown fields, stale previews, and explicit existing workflow IDs |
| 1 | Render the inventory-backed first-workflow wizard | done (focused and full repository gates; unchanged long-name fixture; stateful disposable-browser readiness, stale-preview invalidation, confirmed Start, detail reload, and cleanup) | The browser consumes the Phase 0 boundary to select ready packs, registrations, profiles, boards, and constraints; preserves an in-memory non-secret draft/default; creates boards only through preview-confirm; and reaches a newly created workflow or a safe existing-workflow reference |
| 2 | Add decision-first workflow supervision | pending | Existing workflows reopen by exact ID; isolated-browser evidence proves verified plan approval, exact review disposition before delivery, review-driven revision to a new plan approval, bounded blocked-card recovery, and previewed cancellation |

Mark a phase `in-progress` while running it, `done (<evidence>)` once its gate passes, `pending` otherwise.

## Phase 0 — Establish the registered setup boundary

**Goal:** Make the typed, registration-resolved, digest-bound setup contract a
closed dashboard API before a browser view can consume it.

Steps:

1. Read contract Phase 2, the SetupRequest decision, and all linked AGENTS files.
2. Extract one typed, mutation-free start-readiness preflight from
   `WorkflowService.start`; use it for both confirmed start and the dashboard
   readiness/preview routes so the browser cannot replace repository, pack,
   board, or stage-profile checks with a weaker copy.
3. Replace direct browser setup payloads with the strict `{selection,
   request}` preview envelope and `{selection, request, preview_digest,
   confirm}` apply envelope. Resolve `selection.project_id` only through the
   mounted profile's registration and trusted checkout; reject browser paths,
   unknown outer/request fields, non-literal confirmation, stale digests, and an
   explicit workflow ID that already names a ledger. Remove the legacy
   three-field browser control in this phase rather than retaining a direct-path
   compatibility call; Phase 1 reintroduces Start workflow only through this
   boundary.
4. Add profile-safe inventory, readiness, and board preview/confirmed-creation
   routes. Keep readiness and previews mutation-free; board apply reruns current
   inventory and conflicts if the reviewed slug now exists.
5. Extend typed setup/API tests and the closed route inventory. Verify that the
   service and dashboard preflight share their behavior and that declined or
   stale dashboard operations create no ledger, artifact, worktree, card, or
   board.

Verification gate: The Phase 0 table predicate passes. Focused setup/API tests
prove the registration-resolved envelope, strict field rejection, shared
preflight, mutation-free readiness, exact preview/apply binding, and board
creation conflict handling. Asset tests prove the legacy direct-path control is
absent. Phase 1 owns the static bundle's new browser-memory draft and rendered
inventory controls.

## Phase 1 — Render the inventory-backed first-workflow wizard

**Goal:** Present the Phase 0 API as the guided first-run browser flow without
adding browser authority or persistent dashboard state.

Steps:

1. Read Phase 0 completion evidence and contract Phase 2's selector, default,
   constraints, and handoff rules.
2. Extend the existing closed inventory/readiness projection only as needed to
   identify the mounted controller profile and bind a selected registration to
   that profile before the browser can render it. Keep controller identity
   read-only, derive it through the documented profile inventory, and reject a
   registration belonging to another profile; do not accept a browser profile,
   checkout, credential, or path. This closes the missing Phase 0 browser input
   discovered during Phase 1 execution.
3. Implement the read-only mounted controller identity; ready-pack,
   registered-repository, worker-default/six-stage-profile, and existing-board
   selectors; requested outcome / prompt (mapped to `SetupRequest.goal`);
   constraint source controls; browser-local non-secret defaults; readiness;
   preview; and literal confirmation. Never label the browser control `Goal`.
4. Add the preview-confirm board action, source-change invalidation, and the
   `Manage sources` navigation affordance to Config → Constraints. P0230 owns
   that destination's reusable-source browser and return implementation; this
   phase keeps the draft only in browser memory.
5. Persist only `{project_id, pack, board_slug, stage_profiles}` in the
   mounted-profile-scoped browser preset. Inventory/readiness changes invalidate
   preview; stale/missing identities remain unselected and never authorize start.
6. On successful creation open the returned workflow; on an explicit existing
   workflow conflict offer only the safe exact-ID reopen path. Include Hermes
   Cron as a host-owned admission handoff, not a Daidala scheduler.
7. Recreate the disposable stateful fixture for browser evidence and remove it
   after stopping its owned process. Update asset tests, CSS, route inventory,
   and owning DOX contracts.

Verification gate: The Phase 1 table predicate and exact detailed Phase 2
browser/asset gates pass. Browser evidence proves a Start draft is neither
persisted nor included in defaults, a returned source selection invalidates the
prior preview, and the old preview cannot authorize Start after a source change.
The `Manage sources` link is present and routes to Config → Constraints; its
full destination surface is verified under P0230.

### Current Phase 1 state

- The wizard implementation now includes installed policy-source inventory and
  exact digests, board display names, browser-memory source return navigation,
  the strict preset shape, safe existing-workflow reopen, and the host-owned
  Cron handoff. Compatibility probes verify the executable's local Git revision
  or build metadata rather than the banner's mutable `origin/main` label.
- A fresh isolated fixture process proves the mounted identity and renders the
  profile, board, worker, constraint-tab, and installed policy-source
  inventories. The fixture exposed a valid long-name profile row with only one
  separator space; the shared parser now handles display-column overflow and
  validates the runtime-root candidate against the complete profile inventory.
  Source navigation reaches the `return=start-workflow` context, and browser Back
  preserves the in-memory prompt and constraint mode without writing a default.
- The unchanged long-name fixture remains stopped and unmodified. A separate
  approved disposable profile supplied one clean registered repository, one
  isolated board, the exact bundled AI-DLC adapter, and a deterministic pinned
  source-resolution boundary for the declared pack revision. Browser evidence
  proves readiness, non-mutating preview, source-change invalidation of Start
  authority, fresh preview confirmation, confirmed Start, live define/plan card
  state, and one complete workflow card after reload. The fixture profile,
  temporary repository, source shim, board, dashboard process, and runtime state
  were removed; port 9121 is closed.
- Live Start exposed an incomplete duplicate selected-workflow card: the opened
  component passed only an ID while its renderer continued reading summary fields
  from that placeholder. The renderer now hydrates identity from the fresh detail
  response and filters the selected ID from the ordinary list; focused asset tests
  and the browser reload prove one complete card with no `undefined` identity.
- Full pytest, Ruff, Lefthook validation, both pack validations, fixture unittest,
  Markdown links, build, Twine, release contents, and the isolated Hermes
  dashboard compatibility probe pass.

## Phase 2 — Add decision-first workflow supervision

**Goal:** Make a newly started workflow understandable and controllable through a decision-first dashboard that shows the exact evidence required for each human action while Hermes remains the dashboard host and Kanban lifecycle authority.

Steps:

1. Read contract Phase 3, the workflow cancellation risk, and linked AGENTS files.
2. Implement a primary `Needs your decision` panel above the lower-noise stage timeline. The Overview queue sorts waiting gates by the time they became actionable, ascending, with stable workflow-ID tie-breaking; urgency is a displayed badge, never a reorder rule. Represent approval as a visually distinct `Human approval — Daidala policy gate` timeline step between `plan` and `implement`, never as a fabricated Kanban card. For plan approval, lead with the exact source-bound AI-assisted proposed-change summary, then render the verified bounded plan body, full plan/constraint tuple, scope-risk-verification checklist, a separately labelled read-only next-stage packet, and exact post-approval consequences; keep raw run/event detail behind progressive disclosure. The summary is never the packet or consent substitute.
3. Bind `Approve exact plan` to the displayed verified artifact and summary identities and a literal `I reviewed this exact plan` confirmation. Disable it when either identity is unavailable, stale, malformed, unbound, oversized, or digest-mismatched; never permit approval from a summary, label, digest, or client-cached snapshot alone.
4. After automated review, lead with the strict review record's source-bound AI-assisted change summary, then render the exact diff as escaped unified-diff text, changed paths, verification results, structured findings, a separately labelled read-only successor packet, and a ledger-owned human disposition gate. Offer accept-and-deliver only for accepted non-blocking review, request-revision with feedback, reject workflow, or challenge-reviewer through comment/unblock. Never show a delivery card before attended acceptance. Version 1 renders every reviewable text artifact literally; it does not render Markdown, JSON, YAML, source code, HTML, or diff syntax semantically.
5. On request revision, show the P0207 canonical successor packet and previewed cards/worktree consequences before allowing apply. Its immutable fields remain read-only; require non-empty feedback, show the resulting feedback in the packet, and require literal confirmation. Call only P0207 services, then navigate to the new revisioned plan card and exact plan-approval panel. Never mutate the rejected diff or imply that old cards moved backward.
6. Implement reopen-by-exact-ID resume, read-only watch/refresh, card comment/unblock recovery, and previewed cancellation exactly as ranged by the contract. Blocked-card decisions must lead with the requested decision, latest relevant comment/evidence, and targeted action rather than the full audit thread.
7. Keep plan approval, review disposition/revision, and cancellation in their existing `WorkflowService` boundaries and comments/unblock in public Hermes Kanban operations. The dashboard router must not implement state transitions, delete worktrees, archive cards, or access Kanban storage directly.
8. Extend the closed route inventory and same-commit DOX contracts. Update dashboard-specific documentation and cross-links without duplicating P0207's current runtime documentation.
9. Run the focused API, asset, CLI, and disposable-browser gates named by the contract.

Verification gate: The Phase 2 table predicate passes; browser evidence proves waiting decisions are oldest-actionable first, a user can compare each source-bound AI-assisted summary with the complete escaped evidence and separately visible read-only next-card packet, read and approve the exact plan, inspect and manually disposition the exact review, request changes into one new plan revision with visible feedback and successor packet, challenge a reviewer without overriding policy, resolve one blocked card without raw audit noise, and perform every bounded action without creating a general dispatch path. Browser tests also prove Markdown/HTML is displayed as literal escaped text, deterministic packet fields cannot be edited, and no summary-only approval is possible.

## Out of scope

- Do not change `SetupRequest`, registration storage, P0207 review/revision semantics, or Kanban authority; this plan is presentation and bounded routing only.
- Do not add a wizard-local controller-profile switch, Daidala scheduler, timed
  pause/resume, arbitrary repository URI/path field, pack upload/enable/disable,
  credential storage, or server-side default store. Hermes Cron owns
  delayed/recurring admission; pausing it affects future admissions only.
- Do not implement checkout policy, GitHub Projects links, constraints, configuration verification, or the general artifact browser; this plan exposes only the exact current plan and review evidence required for attended decisions.
- Do not reuse state from a deleted fixture profile.
