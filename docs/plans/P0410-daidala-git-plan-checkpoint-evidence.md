# Daidala Git plan checkpoint evidence

**Plan ID:** daidala-git-plan-checkpoint-evidence

**Execution slot:** P0410

**Created:** 2026-08-10

**Depends on:** daidala-git-plan-source-policy

**Split from:** daidala-git-phased-plan-admission

**Entry checkpoint:** P0400 completed with a deterministic committed plan-source packet and strict pending-phase policy

**Context sources:** [`docs/02-workflow-state.md` artifact identity and availability](../02-workflow-state.md#artifact-identity-and-availability), [approval integrity](../02-workflow-state.md#approval-integrity), and [persistence and concurrency](../02-workflow-state.md#persistence-and-concurrency); [`docs/05-lifecycle-stages.md` implementation isolation](../05-lifecycle-stages.md#implementation-isolation) and [delivery boundary](../05-lifecycle-stages.md#delivery-boundary); P0400 completion evidence; `AGENTS.md`, `daidala/AGENTS.md`, and `tests/AGENTS.md`

**Produces:** immutable stored plan-source evidence and a read-only validator for the single direct-parent checkpoint that authorizes the next committed phase source

**Status:** pending

## Goal

Persist an admitted committed plan source as immutable evidence and validate the operator-created status/checkpoint commit without granting Daidala Git mutation authority.

## Risk call-out

A checkpoint with a wrong parent, unrelated delta, tampered status token, missing delivery evidence, or plan rewrite beyond the allowed status projection could turn a prior approval into authority for different bytes. Validation is deterministic, read-only, and fails before a successor workflow exists.

## Phase table

| # | Phase | Status | Verification gate |
|---|---|---|---|
| 0 | Persist plan-source evidence and validate checkpoint chains | pending | `pytest -q tests/test_plan_admission.py tests/test_execution.py tests/test_store.py` exits 0 and proves create-or-verify source artifacts, direct-parent checkpoint validation, exact delivery/status projection, predecessor identity, and fail-closed wrong parent, extra path, missing evidence, or tampered checkpoint cases |

Mark a phase `in-progress` while running it, `done (<evidence>)` once its gate passes, `pending` otherwise.

## Phase 0 — Persist plan-source evidence and validate checkpoint chains

**Goal:** Retain the exact plan source packet under revision-addressed workflow artifacts and prove that only the immediately preceding delivered phase can advance a source revision.

Steps:

1. Store the exact committed Markdown as immutable `plan.md` plus canonical `plan-source.json` under the workflow's revision-addressed artifact root using create-or-verify semantics; conflicting bytes, unsafe paths, and symlink aliases fail closed.
2. Extend state/workflow policy only as needed to retain the optional immutable source reference while preserving generated-plan compatibility and existing ledger serialization.
3. Implement predecessor lookup through `WorkflowStore.list_all` and read-only checkpoint validation. Require identical repository identity and Plan ID, immediately preceding phase, accepted review and delivery evidence, direct-parent source revision, exact non-plan delivery delta, reserved plan path, and the exact allowed status projection `done (daidala:<workflow-id>:<delivery-digest>)`.
4. Add temporary-repository tests for valid first/later phases, absent or wrong predecessor, absent delivery, wrong parent, extra commits or paths, tampered status evidence, binary diffs, plan-only same-phase supersession, replay, and no mutation of the operator checkout.

Verification gate: The table command exits 0; immutable source evidence and checkpoint validation are deterministic from Git objects and retained delivery evidence.

## Out of scope

- Starting workflows, changing approval semantics, creating cards, or exposing CLI/tool commands; P0420 and P0430 own those surfaces.
- Creating, amending, signing, pushing, merging, or tagging checkpoint commits.
