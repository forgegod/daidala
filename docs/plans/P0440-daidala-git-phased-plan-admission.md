# Daidala Git-pinned phased-plan admission

**Plan ID:** daidala-git-phased-plan-admission

**Execution slot:** P0440

**Created:** 2026-07-25

**Depends on:** daidala-git-preplanned-cli-tools

**Entry checkpoint:** P0430 completed with equivalent native, standalone, and plugin-tool admission over the verified Git-pinned service

**Context sources:** [`docs/02-workflow-state.md` identity and baseline](../02-workflow-state.md#identity-and-baseline), [card graph](../02-workflow-state.md#card-graph), and [approval integrity](../02-workflow-state.md#approval-integrity); [`docs/05-lifecycle-stages.md` graph creation](../05-lifecycle-stages.md#graph-creation-and-assignment), [human gate](../05-lifecycle-stages.md#human-gate), and [delivery boundary](../05-lifecycle-stages.md#delivery-boundary); P0400–P0430 completion evidence; `AGENTS.md`, `daidala/AGENTS.md`, `dashboard/AGENTS.md`, and `tests/AGENTS.md`

**Produces:** synchronized worker, operator, dashboard-read, and verification contracts plus end-to-end evidence that each externally committed checkpoint requires a new exact source admission and human approval

**Status:** completed

## Goal

Make the Git-pinned admission chain understandable and observable on every supported surface, then prove a two-phase sequence without giving Daidala authority to commit or push.

## Current state

- P0400 owns strict committed-plan parsing and canonical packet identity; P0410 owns immutable source evidence and checkpoint validation.
- P0420 owns internal service/approval/graph admission and P0430 owns equivalent native, standalone, and plugin-tool adapters.
- This plan owns worker/operator contracts, read-only dashboard/recommendation projection, and the complete two-phase integration gate.

## Risk call-out

A mutable working-tree plan, an uncommitted status edit, or a source revision different from the implementation baseline would create a time-of-check/time-of-use gap. Admission must read the plan blob from the exact clean HEAD, require that HEAD as the implementation baseline, reject symlinks, traversal, ambiguous plans, non-UTF-8 or oversized content, and bind approval to the complete source packet. Daidala must not create the checkpoint commit: delivery remains `committed: false` and `pushed: false`. The next admission validates the externally created single checkpoint commit and receives a new approval; it never inherits authority from the prior phase. Any validation or partial artifact failure creates no cards or worktree; retry starts from the unchanged source revision after removing only unreferenced Daidala-owned artifacts.

## Phase table

| # | Phase | Status | Verification gate |
|---|---|---|---|
| 0 | Reconcile worker, operator, dashboard-read, and verification contracts | done (focused gate; `pytest`: 677 passed; docs, lint, pack, and package checks passed) | `pytest -q tests/test_worker_contract.py tests/test_recommendations.py tests/test_dashboard_api.py tests/test_cli.py tests/test_plugin.py tests/test_plan_admission.py::test_two_phase_checkpoint_chain && python scripts/check_md_links.py . && lefthook validate && pytest && ruff check . && daidala packs validate addyosmani && daidala packs validate aidlc && python -m build && python -m twine check dist/* && python scripts/check_release_contents.py . --wheel dist/*.whl` exits 0 |

Mark a phase `in-progress` while running it, `done (<evidence>)` once its gate passes, `pending` otherwise. In Git-pinned admission, the active source file remains `pending` during Daidala execution; Kanban carries `in-progress`, and only the successful status/checkpoint commit projects `done` into the next source revision.

## Phase 0 — Reconcile worker, operator, dashboard-read, and verification contracts

**Goal:** Make the source-revision chain understandable and observable across supported operator surfaces, then exercise two phases end to end without granting Daidala commit authority.

Steps:

1. Update `daidala/skills/orchestrate/SKILL.md` so imported-plan implementation workers treat the source packet as immutable authority, never edit the active plan path, and block for a new committed source admission when findings change approved scope. Generated-plan behavior remains unchanged.
2. Update `docs/00-getting-started.md`, `docs/02-workflow-state.md`, `docs/05-lifecycle-stages.md`, `docs/07-runbook.md`, `docs/08-hermes-integration.md`, and relevant DOX files with generated versus Git-pinned admission, exact approval identity, checkpoint creation outside Daidala, the reserved plan path, and next-phase admission commands. Do not claim automatic commit or push.
3. Extend the dashboard read model and recommendations only enough to display imported-plan mode, opaque source revision/Plan ID/phase identity, packet verification state, and the next attended action. Do not add dashboard admission or checkpoint mutation controls in this plan.
4. Add `tests/test_plan_admission.py::test_two_phase_checkpoint_chain` with an isolated temporary-repository probe and two-phase plan: admit phase 0 from commit A, approve and run through accepted delivery, create one explicitly authorized checkpoint commit B containing only the delivered change and allowed status projection, admit phase 1 from B, and prove the phase-0 approval cannot authorize B or phase 1. The probe must leave the original checkout and active Hermes profile unchanged.
5. Run focused tests, Markdown links, every root `AGENTS.md` verification command, and package/install probes. Reconcile source, test, CLI, tool, documentation, and package inventories before marking the plan complete.

Verification gate: `pytest -q tests/test_worker_contract.py tests/test_recommendations.py tests/test_dashboard_api.py tests/test_cli.py tests/test_plugin.py tests/test_plan_admission.py::test_two_phase_checkpoint_chain && python scripts/check_md_links.py . && lefthook validate && pytest && ruff check . && daidala packs validate addyosmani && daidala packs validate aidlc && python -m build && python -m twine check dist/* && python scripts/check_release_contents.py . --wheel dist/*.whl` exits 0; delivery still records `committed: false` and `pushed: false`.

## Out of scope

- Do not make Daidala create, amend, sign, push, merge, or tag the status/checkpoint commit.
- Do not let a previous approval authorize a descendant commit, changed plan status, next phase, or changed constraints.
- Do not execute an entire multi-phase plan in one workflow or recapture implementation after verification/review.
- Do not accept untracked plans, mutable working-tree bytes, profile-private plans, arbitrary filesystem paths, remote-only revisions, or implicit plan discovery.
- Do not add a repository-local agent authority layer, MCP server, HTTP daemon, nested `hermes chat`, or alternate lifecycle state machine.
- Do not add dashboard admission/checkpoint mutations; a later plan may add UI only after native/standalone behavior is exercised.
- Do not retrofit historical generated-plan workflows with fabricated source packets or plan-stage evidence.
