# Daidala dashboard review disposition and revision

**Plan ID:** daidala-dashboard-review-disposition

**Execution slot:** P0212

**Created:** 2026-07-27

**Depends on:** daidala-dashboard-setup-and-supervision#phase-2

**Split from:** daidala-dashboard-setup-and-supervision#phase-2

**Plan family:** daidala-dashboard

**Entry checkpoint:** P0210 Phase 2 completed with the decision-first workflow-detail foundation, bounded read-only card projection, exact-ID reopen, and exact-plan approval surface.

**Context sources:** [Supervise & decide UX surface](P0250-daidala-dashboard-ux-concept.md#surface-c-supervise-decide-p0210-phase-2-p0212-phase-0-p0214-phase-0), [approval summary and escaped-text contract](daidala-dashboard-execution-contract.md#approval-summary-and-escaped-text-contract), [review disposition and revision-loop contract](daidala-dashboard-execution-contract.md#review-disposition-and-revision-loop-contract), [operator runbook coverage](daidala-dashboard-execution-contract.md#operator-runbook-coverage), [implementer discipline](daidala-dashboard-execution-contract.md#implementer-discipline), [review disposition runbook](../07-runbook.md#review-disposition), P0207 completion evidence, and detailed [contract Phase 3](daidala-dashboard-execution-contract.md#phase-3-workflow-supervision-actions).

**Produces:** an escaped, source-bound review-evidence panel with attended disposition and revision-request preview/confirm actions that navigate to the successor exact-plan approval decision.

**Status:** complete — Phase 0 is implemented and verified.

## Goal

Present P0207's existing attended review authority in the workflow detail without creating a delivery card early, weakening exact evidence binding, or reimplementing review/revision state transitions in the dashboard.

## Current state

- P0207 owns structured review records, exact attended disposition, revision-request cleanup, canonical successor packets, and native/standalone CLI parity.
- P0210 owns the workflow-detail foundation, escaped text rendering, and exact-plan approval. This plan adds only the separately gated review decision surface.
- The dashboard remains a presentation layer over existing services; all identity is derived from current durable state and no browser value may select a board, path, review, artifact, or revision.

## Phase table

| # | Phase | Status | Verification gate |
|---|---|---|---|
| 0 | Add attended review disposition and revision request | done (525 tests; isolated desktop/narrow browser revision loop and exact-route reopen passed) | Focused API and asset tests prove escaped exact review evidence, delivery absence before attended acceptance, stale/unchecked disposition rejection, and convergent revision request navigation to one successor plan approval. |

Mark a phase `in-progress` while running it, `done (<evidence>)` once its gate passes, `pending` otherwise.

## Phase 0 — Add attended review disposition and revision request

**Goal:** Render the exact review evidence and let an attended user preview and confirm only the dispositions authorized by P0207.

Steps:

1. Read the linked P0207 completion evidence and Phase 3 contract. Preserve P0210's snapshot-only client authorization and escaped literal-text renderer.
2. Add a distinct `Human review disposition — Daidala policy gate` timeline step with no Kanban task ID. Fetch P0207's current review state through a thin authenticated route and render its source-bound change summary, escaped unified diff, changed paths, verification results, structured findings, complete tuple, fixed consequences, and separately titled read-only successor packet before any action.
3. Add mutation-free preview and confirmed review-disposition routes. Preview accepts exactly `{action, rationale}`; apply accepts exactly `{action, review_digest, preview_digest, rationale, confirm: true}`. Recompute current server-derived identity before applying and delegate only to existing P0207 service operations.
4. Render `Accept and continue to delivery` only for an accepted review without blocking findings. Require non-empty feedback for `Request revision`; render the canonical successor packet and consequences before literal confirmation, then navigate directly to the returned revisioned plan and exact-plan approval decision. Render `Challenge reviewer` only as public Kanban comment/unblock, not as a policy override. Never show a delivery card or control before attended acceptance.
5. Extend the closed route inventory, dashboard mutation allowlist, and asset contract in the same implementation commit. Add focused API and asset coverage before or with the routes, then run the isolated browser gate for review evidence and revision navigation.

Verification gate: `pytest tests/test_dashboard_api.py tests/test_dashboard_assets.py -q` exits 0 and proves exact escaped review rendering, delivery absence before attended acceptance, stale or unchecked disposition rejection, accepted-only delivery control, required revision feedback, canonical successor-packet preview/apply parity, navigation to one new plan approval, literal text rendering, and absence of arbitrary dispatch, commit, or push routes. The isolated browser probe proves review evidence precedes authority controls and a revision request cannot mutate the rejected diff or imply an in-place phase rewind.

## Completion evidence

- `python -m pytest` passed 527 tests; the frozen package-resource unittest and `ruff check .` also passed.
- Both pack validators, `node --check dashboard/dist/index.js`, the 64-file Markdown link check, wheel/sdist build, Twine checks, the 222-source/55-wheel-member release-content check, and `git diff --check` passed.
- An isolated Hermes profile, Kanban board, repository, owned detached worktree, and Chromium browser rendered the exact review summary, literal `<script>` diff text without a nested script node, changed paths, verification evidence, findings, identity tuple, and pending non-Kanban review gate. The desktop and 390-pixel layouts had no document overflow, review API payloads exposed no profile-local path, and delivery authority was absent.
- The browser previewed and confirmed `request_revision`. Durable state advanced to plan revision 1, preserved one review, disposition, and revision-request history entry, cleared approval and review authority, released the owned worktree, archived the current review card, created exactly one ready successor Plan card, and navigated to the revision-addressed exact-plan approval URL. The disposable profile, board, repository, browser artifacts, process, and port were removed afterward.
- A self-contained Chromium route gate proved initial exact-ID reopen, `popstate` reopen to another workflow, and approval focus only after the server-returned packet matched the requested plan revision.

Post-checkpoint review follow-up completed: review packets, reviewed
implementation paths, and the sibling exact-plan approval projection now use
one captured ledger snapshot, so an authenticated read cannot combine
concurrent workflow revisions. Focused snapshot-identity and mismatch tests plus
the 527-test full suite passed.

## Out of scope

- Do not add review policy, delivery authority, revision persistence, or a second state-transition implementation; P0207 owns them.
- Do not implement blocked-card remediation or cancellation; P0214 owns those operations.
- Do not render Markdown, HTML, JSON, YAML, source code, or diffs semantically; all reviewable text remains literal escaped text.
