# Daidala Git preplanned CLI and tool admission

**Plan ID:** daidala-git-preplanned-cli-tools

**Execution slot:** P0430

**Created:** 2026-08-10

**Depends on:** daidala-git-preplanned-service-graph

**Split from:** daidala-git-phased-plan-admission

**Entry checkpoint:** P0420 completed with internal Git-pinned service admission, exact approval binding, and an imported-plan post-gate graph

**Context sources:** [`docs/02-workflow-state.md` identity and baseline](../02-workflow-state.md#identity-and-baseline) and [approval integrity](../02-workflow-state.md#approval-integrity); [`docs/05-lifecycle-stages.md` graph creation and assignment](../05-lifecycle-stages.md#graph-creation-and-assignment) and [human gate](../05-lifecycle-stages.md#human-gate); P0420 completion evidence; `AGENTS.md`, `daidala/AGENTS.md`, and `tests/AGENTS.md`

**Produces:** equivalent dry-run-first native, standalone, and plugin-tool admission interfaces over the verified preplanned service

**Status:** complete

## Goal

Expose the internal Git-pinned phase-admission service through existing operator and plugin boundaries without widening its authority or leaking source bytes or private paths.

## Risk call-out

A CLI/tool adapter that treats caller data as trusted, applies a stale packet, differs by host mode, or returns raw Git/plan/private-path errors would bypass the policy boundary. Every adapter delegates to the same service, validates exact identity before apply, and returns bounded metadata-only diagnostics.

## Phase table

| # | Phase | Status | Verification gate |
|---|---|---|---|
| 0 | Add native, standalone, and plugin-tool admission parity | done (674 pytest; lefthook, ruff, pack, build, and release checks passed) | `pytest -q tests/test_plan_admission.py tests/test_tools.py tests/test_cli.py tests/test_plugin.py` exits 0 and proves dry-run/apply identity, native/standalone/tool parity, schema/registration inventory consistency, stale-packet rejection, bounded failures, and no mutation before exact apply |

Mark a phase `in-progress` while running it, `done (<evidence>)` once its gate passes, `pending` otherwise.

## Phase 0 — Add native, standalone, and plugin-tool admission parity

**Goal:** Make preplanned admission operable without giving any adapter separate policy or mutation semantics.

Steps:

1. Add shared native/standalone `start-from-plan` parsing with repository, repository-relative plan path, phase number, full source revision, board, complete stage profiles, pack, workflow ID, optional predecessor workflow ID, and the existing explicit constraint source. Dry run is default; apply requires the exact fresh preview digest.
2. Add the equivalent strict plugin schema, JSON-returning handler, registration inventory, and tool tests. Handlers accept `args: dict, **kwargs`; errors exclude plan bytes, profile-local paths, credentials, and raw Git output.
3. Prove native, standalone, and tool projections delegate to the same service and agree on valid output, stale preview rejection, invalid selectors, and no pre-apply ledger/Kanban/worktree mutation. Applying an imported plan persists its immutable source and Plan artifact but creates no Kanban graph until the existing attended approval gate.
4. Exercise fresh process/plugin registration compatibility for the new inventory and retain generated-plan `start` command behavior unchanged.

Verification gate: The table command exits 0; all public entry points are equivalent bounded adapters over P0420 service policy.

## Out of scope

- Dashboard admission/checkpoint mutation controls.
- Documentation, worker contract, recommendation/dashboard-read projections, or the complete two-phase integration probe; P0440 owns those surfaces.
