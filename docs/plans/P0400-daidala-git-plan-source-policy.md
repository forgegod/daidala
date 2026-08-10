# Daidala Git plan-source policy

**Plan ID:** daidala-git-plan-source-policy

**Execution slot:** P0400

**Created:** 2026-08-10

**Depends on:** none

**Split from:** daidala-git-phased-plan-admission

**Entry checkpoint:** none — the clean-baseline, exact-plan approval, immutable delivery, and profile-local ledger contracts are sufficient inputs

**Context sources:** [`docs/02-workflow-state.md` identity and baseline](../02-workflow-state.md#identity-and-baseline) and [approval integrity](../02-workflow-state.md#approval-integrity); [`docs/05-lifecycle-stages.md` human gate](../05-lifecycle-stages.md#human-gate); `AGENTS.md`, `daidala/AGENTS.md`, and `tests/AGENTS.md`

**Produces:** a pure strict representation of a pending committed plan phase, exact Git-object source identity, and an immutable canonical plan-source packet

**Status:** complete — Phase 0 implementation and verification gate passed

## Goal

Establish the bounded deterministic policy that identifies exactly one pending phase in a committed repository plan and proves the source bytes belong to the clean target baseline.

**Atomicity rationale:** Parsing, Git-object identity, and immutable packet construction form one pure boundary. This phase neither persists packets nor starts workflows, creates cards, exposes adapters, or changes an existing ledger schema; P0410 and later plans own those integration surfaces.

## Risk call-out

A mutable working-tree plan, abbreviated revision, untracked source, symlink, traversal path, duplicate plan identity, malformed phase structure, or oversized/binary document can create ambiguity before attended approval. Every one fails before ledger, artifact, Kanban, or worktree mutation.

## Phase table

| # | Phase | Status | Verification gate |
|---|---|---|---|
| 0 | Add strict committed plan-source parsing and packet identity | done (verification passed) | `pytest -q tests/test_plan_admission.py tests/test_workflow.py tests/test_store.py` exits 0 and proves canonical packet identity, strict phased-plan parsing, exact Git-blob reads, clean-HEAD equality, and fail-closed malformed or drifted inputs |

Mark a phase `in-progress` while running it, `done (<evidence>)` once its gate passes, `pending` otherwise.

## Phase 0 — Add strict committed plan-source parsing and packet identity

**Goal:** Make an exact committed pending plan phase representable without creating a workflow or reading mutable plan bytes.

Steps:

1. Add `daidala/plan_admission.py` with strict bounded parsing for active-plan headers, phase tables, selected `## Phase N` sections, verification gates, status vocabulary, plan IDs, execution slots, and direct dependencies. Reject duplicate fields, duplicate IDs/slots, unknown dependencies, cycles, noncontiguous phase numbers, mismatched table/headings, malformed evidence, and ambiguous Markdown.
2. Add an injectable Git command boundary that resolves repository identity, full source revision, tree entry type, plan blob object ID, and exact bytes. Require `source_revision == baseline_commit ==` clean checkout `HEAD`; reject abbreviated revisions, dirty repositories, submodule/tree/symlink entries, traversal, paths outside the repository, non-UTF-8, and documents over the existing bounded-document limit.
3. Add strict immutable `PlanSourceReference` and packet models in `daidala/state.py` with canonical serialization and digest identity. Add pure policy constructors in `daidala/workflow.py` without changing generated-plan behavior or persistence layout.
4. Add temporary-repository tests for valid first-phase parsing, source/blob/tree/path failures, duplicate/cyclic plan graphs, plan-content drift, malformed statuses/evidence, canonical packet replay, and no mutation of the operator checkout.
5. Update `daidala/AGENTS.md` and `tests/AGENTS.md` with the plan-source policy ownership and focused verification contract.

Verification gate: The table command exits 0; packet identity is deterministic from committed Git objects, and every mutable or ambiguous input fails before any state mutation.

## Out of scope

- Persisting source packets or plan artifacts; P0410 owns evidence persistence and checkpoint validation.
- Workflow admission, approval, cards, CLI, plugin tools, dashboard projections, commits, pushes, or worktree creation.
- Accepting a working-tree plan, profile-private plan, arbitrary filesystem path, remote-only revision, or implicit plan discovery.
