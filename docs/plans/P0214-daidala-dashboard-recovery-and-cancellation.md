# Daidala dashboard recovery and cancellation

**Plan ID:** daidala-dashboard-recovery-and-cancellation

**Execution slot:** P0214

**Created:** 2026-07-27

**Depends on:** daidala-dashboard-setup-and-supervision#phase-2

**Split from:** daidala-dashboard-setup-and-supervision#phase-2

**Plan family:** daidala-dashboard

**Entry checkpoint:** P0210 Phase 2 completed with the decision-first workflow-detail foundation and bounded read-only card projection; P0207 completed preserved-evidence cancellation and review authority.

**Context sources:** [Supervise & decide UX surface](P0250-daidala-dashboard-ux-concept.md#surface-c-supervise-decide-p0210-phase-2-p0212-phase-0-p0214-phase-0), [operator runbook coverage](daidala-dashboard-execution-contract.md#operator-runbook-coverage), [workflow-cancellation risk](daidala-dashboard-execution-contract.md#risk-call-out), [implementer discipline](daidala-dashboard-execution-contract.md#implementer-discipline), [recovery runbook](../07-runbook.md#recovery), [cancellation runbook](../07-runbook.md#cancel), and detailed [contract Phase 3](daidala-dashboard-execution-contract.md#phase-3-workflow-supervision-actions).

**Produces:** targeted blocked-card comment/unblock actions and a digest-bound cancellation preview/confirm surface over the existing public Hermes Kanban and `WorkflowService.cancel` boundaries.

**Status:** in-progress — Phase 0 complete (commit pending); P0210 Phase 2 is complete and human implementation approval is recorded for Phase 0.

## Goal

Give an operator bounded recovery and cancellation controls that lead with the required decision and affected consequences, while preserving Hermes Kanban as lifecycle authority and keeping destructive worktree cleanup inside the existing service.

## Current state

- P0210 provides the workflow-owned bounded `kanban show` and `kanban runs` read projection consumed here.
- P0207 and `WorkflowService.cancel` preserve the policy and artifact ledger, archive only recorded cards, and clean only a Daidala-owned worktree.
- The browser may never select a board, directly read Kanban storage, delete a worktree, or dispatch an arbitrary Hermes or Daidala command.

## Risk call-out

Cancellation can archive cards and remove a Daidala-owned worktree. The router only previews and delegates to `WorkflowService.cancel`; it must name the affected worktree and cards, recompute the canonical digest from current state, and fail closed when the ledger token or identities changed.

## Phase table

| # | Phase | Status | Verification gate |
|---|---|---|---|
| 0 | Add blocked-card remediation and previewed cancellation | done (pytest + ruff + pack-validate + build + twine + release-contents + browser probe; gate green) | Focused API and asset tests prove workflow-owned-card validation, bounded public-Kanban forwarding, required confirmation/text bounds, and stale-digest cancellation rejection with an affected cards/worktree projection. |

Mark a phase `in-progress` while running it, `done (<evidence>)` once its gate passes, `pending` otherwise.

## Phase 0 — Add blocked-card remediation and previewed cancellation

**Goal:** Add targeted recovery and cancellation actions without adding a general command bridge or a second workflow engine.

Steps:

1. Read the linked recovery/cancellation contract and runbook sections. Reuse P0210's bounded read projection; do not persist host-owned comments, runs, events, or card status in Daidala.
2. For a blocked card, lead with the stage, blocker kind, requested remediation, latest relevant comment, and linked evidence. Keep older comments, events, and run history behind progressive disclosure.
3. Add private public-Kanban CLI adapters for exactly `comment` and `unblock`, after validating the card belongs to the current workflow and deriving the board from durable registration state. Enforce the contract's text bounds and control-character rules, invoke argv without a shell, and fail closed on timeout or nonzero exit. Expose only the named confirmation-gated routes; never extend a generic Daidala CLI dispatch surface.
4. Add cancellation preview and confirmed routes. Preview accepts exactly `{reason}`; apply accepts exactly `{reason, preview_digest, confirm: true}`. Derive cards, owned worktree, ledger token, and normalized reason server-side, recompute the canonical preview digest immediately before apply, and delegate only to `WorkflowService.cancel`.
5. Extend the closed route inventory, dashboard mutation allowlist, and asset contract in the same implementation commit. Add focused API and asset coverage before or with the routes, then run the isolated browser gate for blocked-card remediation and cancellation preview.

Verification gate: `pytest tests/test_dashboard_api.py tests/test_dashboard_assets.py -q` exits 0 and proves workflow-owned-card checks, bounded comment/unblock forwarding, required text and literal confirmation, no approval through unblock, cancellation reason/preview-digest/confirmation enforcement, stale preview rejection, affected cards and owned-worktree projection, and absence of arbitrary dispatch, commit, or push routes. The isolated browser probe proves a blocked decision leads with targeted remediation and cancellation cannot be enabled before its preview names the affected worktree.

## Out of scope

- Do not add a scheduler, timed pause/resume, or direct Kanban database access.
- Do not change approval, review disposition, revision, or delivery semantics.
- Do not delete a worktree, archive cards, or mutate live Kanban state outside the existing public Hermes and `WorkflowService.cancel` boundaries.
