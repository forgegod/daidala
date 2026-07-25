# Daidala dashboard setup and workflow supervision

**Plan ID:** daidala-dashboard-setup-and-supervision

**Execution slot:** P0210

**Created:** 2026-07-23

**Depends on:** daidala-dashboard-user-config-packs-start-constraints-github-links

**Split from:** daidala-dashboard-user-config-packs-start-constraints-github-links

**Plan family:** daidala-dashboard

**Entry checkpoint:** P0200 completed with a verified mounted host, disposable fixture recipe, and pack readiness surface

**Context sources:** [shared goal and current state](daidala-dashboard-execution-contract.md#goal), [browser fixture and mutation boundaries](daidala-dashboard-execution-contract.md#operator-pinning), [SetupRequest envelope decision](daidala-dashboard-execution-contract.md#setup-request-envelope), [operator runbook coverage](daidala-dashboard-execution-contract.md#operator-runbook-coverage), [implementer discipline](daidala-dashboard-execution-contract.md#implementer-discipline), [workflow-cancellation risk](daidala-dashboard-execution-contract.md#risk-call-out), [runbook start and resume](../07-runbook.md#start-and-resume-a-workflow), [exact approval](../07-runbook.md#approve-the-exact-plan), [cancellation](../07-runbook.md#cancel), [recovery](../07-runbook.md#recovery), and detailed [contract Phase 2](daidala-dashboard-execution-contract.md#phase-2-first-workflow-setup-wizard-ux) and [contract Phase 3](daidala-dashboard-execution-contract.md#phase-3-workflow-supervision-actions)

**Produces:** a guided first-workflow wizard over the existing `SetupRequest` path plus bounded watch, approval, recovery, and cancellation controls over existing authority surfaces

**Status:** pending — blocked until P0200 completes and human implementation approval is recorded

## Goal

Add the browser path that starts a first workflow through the existing setup model, reopens an existing exact workflow as the runbook's resume path, and supervises it without introducing a second workflow engine or a general command-dispatch route.

## Current state

- P0200 owns the mounted host, fixture recipe, pack readiness, and supported React SDK boundary.
- `SetupRequest.from_payload`, `confirmed_start`, workflow read models, approval, Kanban recovery, and cancellation already define the authority boundaries.
- The shared contract pins the exact request envelope, blank workflow-ID behavior, disposable fixture rules, closed route inventory, and cancellation recovery path; resume means reopen and continue watching an existing workflow, not create a duplicate.

## Phase table

| # | Phase | Status | Verification gate |
|---|---|---|---|
| 0 | Add first-workflow setup wizard UX | pending | The wizard uses the exact `SetupRequest`/`daidala:setup` path, verifies prerequisites, creates or selects a board, renders required controls, and preserves preview-then-confirm start semantics |
| 1 | Add workflow supervision actions | pending | Existing workflows reopen by exact ID and expose read-only watch/refresh, exact-digest approval, blocked-card comment/unblock recovery, and previewed cancellation through existing authority surfaces |

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

## Phase 1 — Add workflow supervision actions

**Goal:** Make a newly started workflow observable and controllable through existing Daidala and Hermes authority boundaries.

Steps:

1. Read contract Phase 3, the workflow cancellation risk, and linked AGENTS files.
2. Implement reopen-by-exact-ID resume, read-only watch/refresh, exact-digest approval, card comment/unblock recovery, and previewed cancellation exactly as ranged by the contract.
3. Keep cancellation in `WorkflowService.cancel`; the dashboard router must not delete worktrees or archive cards itself.
4. Extend the closed route inventory and same-commit DOX contracts.
5. Run the focused API, asset, CLI, and disposable-browser gates named by the contract.

Verification gate: The Phase 1 table predicate passes and the browser evidence proves each bounded action without creating a general dispatch path.

## Out of scope

- Do not change `SetupRequest`, registration storage, approval semantics, or Kanban authority.
- Do not implement checkout policy, GitHub Projects links, constraints, configuration verification, or artifact review.
- Do not reuse state from a deleted fixture profile.
