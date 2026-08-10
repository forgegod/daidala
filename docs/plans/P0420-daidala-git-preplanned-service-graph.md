# Daidala Git preplanned service and graph admission

**Plan ID:** daidala-git-preplanned-service-graph

**Execution slot:** P0420

**Created:** 2026-08-10

**Depends on:** daidala-git-plan-checkpoint-evidence

**Split from:** daidala-git-phased-plan-admission

**Entry checkpoint:** P0410 completed with immutable committed-plan evidence and read-only checkpoint-chain validation

**Context sources:** [`docs/02-workflow-state.md` card graph](../02-workflow-state.md#card-graph) and [approval integrity](../02-workflow-state.md#approval-integrity); [`docs/05-lifecycle-stages.md` graph creation and assignment](../05-lifecycle-stages.md#graph-creation-and-assignment), [human gate](../05-lifecycle-stages.md#human-gate), and [delivery boundary](../05-lifecycle-stages.md#delivery-boundary); P0410 completion evidence; `AGENTS.md`, `daidala/AGENTS.md`, and `tests/AGENTS.md`

**Produces:** an internal dry-run/apply service that admits exactly one committed pending phase, preserves exact attended approval, and creates an imported-plan `implement → verify → review` graph without fabricated define/plan history

**Status:** complete

## Goal

Integrate validated Git-pinned source packets with the service, ledger, approval, worktree, and Kanban graph while retaining generated-plan behavior.

## Risk call-out

A stale preview, changed pack/profile/board/constraint/baseline, inherited approval, fabricated pre-gate card history, or plan replacement may dispatch implementation for unapproved bytes. Apply reruns all identity checks before artifacts, ledger state, worktree, or cards mutate.

## Phase table

| # | Phase | Status | Verification gate |
|---|---|---|---|
| 0 | Add preplanned internal service, approval, and graph lifecycle | done (uv-run-pytest-phase-gate) | `pytest -q tests/test_plan_admission.py tests/test_execution.py tests/test_kanban.py tests/test_workflow.py` exits 0 and proves dry-run/apply identity, restart convergence, exact approval binding, imported-plan `implement → verify → review` graph, generated-plan regression coverage, and delivery only after exact attended review acceptance |

Mark a phase `in-progress` while running it, `done (<evidence>)` once its gate passes, `pending` otherwise.

## Phase 0 — Add preplanned internal service, approval, and graph lifecycle

**Goal:** Admit a validated committed phase internally without model-generated definition/planning work and dispatch only after fresh exact approval.

**Atomicity rationale:** This vertical slice spans ledger identity, source artifact
recording, approval, graph construction, regression coverage, and their owned
contracts. Splitting it would expose either imported bytes without an approval
binding or an approval path without its required graph and recovery invariants.

Steps:

1. Add a dry-run-first `start_from_plan` service operation accepting the validated source packet, board, complete stage-profile mapping, pack, workflow ID, optional predecessor workflow ID, and explicit constraint source. Apply reruns Git, packet, dependency, predecessor, pack, profile, board, constraint, and checkpoint checks; stale identity creates no workflow or cards.
2. Persist imported-plan mode and its source packet before exposing approval. Generated-plan mode remains unchanged, and imported-plan mode creates no `define` or `plan` cards or synthetic activation history.
3. Extend approval so imported-plan mode binds both the immutable plan digest and packet digest with the existing constraint tuple. Approval creates the detached worktree at the exact `source_revision == baseline_commit` only after all checks pass.
4. Extend post-gate graph creation so imported-plan mode starts `implement` without a plan-card parent while retaining the exact profiles, skills, revision, worktree, idempotency, verification, review, and attended-delivery constraints. Generated-plan mode keeps its current plan-card parent.
5. Reject profile-local `replace_plan` substitution for imported sources. Scope discovery supersedes the workflow and requires a plan-only new Git revision plus fresh admission; cancellation removes only owned resources.
6. Add positive, stale-preview, restart, wrong-worker, wrong-board, generated-mode regression, graph-parent, plan-replacement, and exact attended-review tests.

Verification gate: The table command exits 0; imported-plan service admission preserves the human gate and cannot authorize mutable or descendant sources.

## Out of scope

- Native/standalone CLI flags, plugin schemas/tools, and registration inventory; P0430 owns those adapters.
- Dashboard/recommendation projections and operator documentation; P0440 owns those surfaces.
