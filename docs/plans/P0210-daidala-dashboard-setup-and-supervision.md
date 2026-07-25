# Daidala dashboard setup and workflow supervision

**Plan ID:** daidala-dashboard-setup-and-supervision

**Execution slot:** P0210

**Created:** 2026-07-23

**Depends on:** daidala-dashboard-user-config-packs-start-constraints-github-links, daidala-artifact-access-core, daidala-review-disposition-and-revision-loop

**Split from:** daidala-dashboard-user-config-packs-start-constraints-github-links

**Plan family:** daidala-dashboard

**Entry checkpoint:** P0200 completed with a verified mounted host, disposable fixture recipe, and pack readiness surface; P0205 completed exact current-plan artifact resolution; P0207 completed structured review, attended disposition, revision-loop authority, and synchronized runtime documentation

**Context sources:** [shared goal and current state](daidala-dashboard-execution-contract.md#goal), [browser fixture and mutation boundaries](daidala-dashboard-execution-contract.md#operator-pinning), [review disposition contract](daidala-dashboard-execution-contract.md#review-disposition-and-revision-loop-contract), [SetupRequest envelope decision](daidala-dashboard-execution-contract.md#setup-request-envelope), [operator runbook coverage](daidala-dashboard-execution-contract.md#operator-runbook-coverage), [implementer discipline](daidala-dashboard-execution-contract.md#implementer-discipline), [workflow-cancellation risk](daidala-dashboard-execution-contract.md#risk-call-out), [runbook start and resume](../07-runbook.md#start-and-resume-a-workflow), [exact approval](../07-runbook.md#approve-the-exact-plan), [cancellation](../07-runbook.md#cancel), [recovery](../07-runbook.md#recovery), [artifact resolver contract](daidala-artifact-review-execution-contract.md#phase-0-add-the-ledger-owned-artifact-catalog-and-resolver), P0205 and P0207 completion evidence, and detailed [contract Phase 2](daidala-dashboard-execution-contract.md#phase-2-first-workflow-setup-wizard-ux) and [contract Phase 3](daidala-dashboard-execution-contract.md#phase-3-workflow-supervision-actions)

**Produces:** a guided first-workflow wizard plus decision-first plan approval, review disposition, revision request, recovery, and cancellation controls over existing Daidala and Hermes authority surfaces

**Status:** pending — blocked until P0200, P0205, and P0207 complete and human implementation approval is recorded

## Goal

Add the browser path that starts a first workflow through the existing setup model, reopens an existing exact workflow as the runbook's resume path, and supervises it without introducing a second workflow engine or a general command-dispatch route.

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
| 0 | Add first-workflow setup wizard UX | pending | The wizard uses the exact `SetupRequest`/`daidala:setup` path, verifies prerequisites, creates or selects a board, renders required controls, and preserves preview-then-confirm start semantics |
| 1 | Add decision-first workflow supervision | pending | Existing workflows reopen by exact ID; isolated-browser evidence proves verified plan approval, exact review disposition before delivery, review-driven revision to a new plan approval, bounded blocked-card recovery, and previewed cancellation |

Mark a phase `in-progress` while running it, `done (<evidence>)` once its gate passes, `pending` otherwise.

## Phase 0 — Add the first-workflow setup wizard

**Goal:** Provide a guided browser form that is an alternative presentation over the existing validated setup request and confirmed-start path.

Steps:

1. Read contract Phase 2, the SetupRequest decision, and all linked AGENTS files.
2. Implement the contract's profile, pack, repository, goal, stage-profile, constraint, board, preview, and confirmation controls.
3. Pass only the nested `request` payload to `SetupRequest.from_payload`; keep confirmation and digest fields outside the model.
4. Recreate the disposable stateful fixture for browser evidence and remove it after stopping its owned process.
5. Update route inventory and owning AGENTS contracts with the source changes, then run the focused setup/API/asset/browser gates from the contract.

Verification gate: The Phase 0 table predicate and the exact detailed Phase 2 contract gates pass.

## Phase 1 — Add decision-first workflow supervision

**Goal:** Make a newly started workflow understandable and controllable through a decision-first dashboard that shows the exact evidence required for each human action while Hermes remains the dashboard host and Kanban lifecycle authority.

Steps:

1. Read contract Phase 3, the workflow cancellation risk, and linked AGENTS files.
2. Implement a primary `Needs your decision` panel above the lower-noise stage timeline. Represent approval as a visually distinct `Human approval — Daidala policy gate` timeline step between `plan` and `implement`, never as a fabricated Kanban card. For plan approval, render the verified bounded plan body, full plan/constraint tuple, scope-risk-verification checklist, and exact post-approval consequences; keep raw run/event detail behind progressive disclosure.
3. Bind `Approve exact plan` to the displayed verified artifact identity and a literal `I reviewed this exact plan` confirmation. Disable it when content is unavailable, stale, binary, oversized, or digest-mismatched; never permit approval from a label, digest, or client-cached snapshot alone.
4. After automated review, render the exact diff, changed paths, verification results, structured findings, and a ledger-owned human disposition gate. Offer accept-and-deliver only for accepted non-blocking review, request-revision with feedback, reject workflow, or challenge-reviewer through comment/unblock. Never show a delivery card before attended acceptance.
5. On request revision, show the previewed cards/worktree consequences, require literal confirmation, call only P0207 services, then navigate to the new revisioned plan card and exact plan-approval panel. Never mutate the rejected diff or imply that old cards moved backward.
6. Implement reopen-by-exact-ID resume, read-only watch/refresh, card comment/unblock recovery, and previewed cancellation exactly as ranged by the contract. Blocked-card decisions must lead with the requested decision, latest relevant comment/evidence, and targeted action rather than the full audit thread.
7. Keep plan approval, review disposition/revision, and cancellation in their existing `WorkflowService` boundaries and comments/unblock in public Hermes Kanban operations. The dashboard router must not implement state transitions, delete worktrees, archive cards, or access Kanban storage directly.
8. Extend the closed route inventory and same-commit DOX contracts. Update dashboard-specific documentation and cross-links without duplicating P0207's current runtime documentation.
9. Run the focused API, asset, CLI, and disposable-browser gates named by the contract.

Verification gate: The Phase 1 table predicate passes; browser evidence proves a user can read and approve the exact plan, inspect and manually disposition the exact review, request changes into one new plan revision, challenge a reviewer without overriding policy, resolve one blocked card without raw audit noise, and perform every bounded action without creating a general dispatch path.

## Out of scope

- Do not change `SetupRequest`, registration storage, P0207 review/revision semantics, or Kanban authority; this plan is presentation and bounded routing only.
- Do not implement checkout policy, GitHub Projects links, constraints, configuration verification, or the general artifact browser; this plan exposes only the exact current plan and review evidence required for attended decisions.
- Do not reuse state from a deleted fixture profile.
