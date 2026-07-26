# Daidala Git-pinned phased-plan admission

**Plan ID:** daidala-git-phased-plan-admission

**Execution slot:** P0400

**Created:** 2026-07-25

**Depends on:** none

**Entry checkpoint:** none — the current clean-baseline, exact-plan approval, immutable delivery, and profile-local ledger contracts are sufficient inputs

**Context sources:** [`docs/02-workflow-state.md` identity and baseline](../02-workflow-state.md#identity-and-baseline), [card graph](../02-workflow-state.md#card-graph), and [approval integrity](../02-workflow-state.md#approval-integrity); [`docs/05-lifecycle-stages.md` graph creation](../05-lifecycle-stages.md#graph-creation-and-assignment), [human gate](../05-lifecycle-stages.md#human-gate), and [delivery boundary](../05-lifecycle-stages.md#delivery-boundary); `AGENTS.md`, `daidala/AGENTS.md`, and `tests/AGENTS.md`

**Produces:** a deterministic Git-pinned phase-admission packet, a preplanned approval path that starts the normal post-gate graph without model-generated define/plan cards, and a verified checkpoint chain in which each committed phase result becomes the only source revision eligible for the next admission

**Status:** pending — the source-revision checkpoint policy is pinned; human approval is required before implementation

## Goal

Allow an operator to admit one pending phase from a repository-tracked `Pnnnn-*.md` plan at the clean checkout's exact Git revision, approve that immutable source packet, run the existing isolated implementation lifecycle, and use the separately authorized status/checkpoint commit as the exact source revision for the next phase without letting a previous approval authorize later Git bytes.

## Current state

- `WorkflowService.start` validates a clean checkout and records its HEAD as `baseline_commit`, but always creates model-executed `define` and dependent `plan` cards (`daidala/service.py:90-175`, `724-733`).
- A submitted `plan.md` is profile-local model output. Approval binds its digest and current constraints, not a repository path, Git blob, selected phase, or source revision (`daidala/service.py:399-438`, `daidala/workflow.py:216-244`).
- `_ensure_post_gate_graph` requires both a plan card and plan artifact and parents `implement` from that card (`daidala/service.py:735-755`). A deterministic imported plan therefore cannot currently enter the post-gate graph without fabricating pre-gate worker history.
- Daidala captures one immutable implementation diff, verifies and reviews it, records `committed: false` and `pushed: false`, and releases its owned worktree after delivery (`docs/05-lifecycle-stages.md:89-99`, `126-130`; `daidala/service.py:461-505`, `710-722`).
- `WorkflowStore.list_all` can inspect prior ledgers for a chain check, but no ledger field identifies a repository plan, selected phase, source commit, plan blob, or predecessor workflow (`daidala/store.py:217-223`, `daidala/state.py:680-703`).
- Active phased plans already carry stable plan IDs, execution slots, dependencies, phase statuses, and executable gates. Their status vocabulary does not yet define a Daidala delivery-evidence token or a source-revision chain.

## Risk call-out

A mutable working-tree plan, an uncommitted status edit, or a source revision different from the implementation baseline would create a time-of-check/time-of-use gap. Admission must read the plan blob from the exact clean HEAD, require that HEAD as the implementation baseline, reject symlinks, traversal, ambiguous plans, non-UTF-8 or oversized content, and bind approval to the complete source packet. Daidala must not create the checkpoint commit: delivery remains `committed: false` and `pushed: false`. The next admission validates the externally created single checkpoint commit and receives a new approval; it never inherits authority from the prior phase. Any validation or partial artifact failure creates no cards or worktree; retry starts from the unchanged source revision after removing only unreferenced Daidala-owned artifacts.

## Phase table

| # | Phase | Status | Verification gate |
|---|---|---|---|
| 0 | Add strict Git plan-source and checkpoint-chain policy | pending | `pytest -q tests/test_plan_admission.py tests/test_workflow.py tests/test_store.py tests/test_execution.py` exits 0 and proves canonical packet identity, strict phased-plan parsing, exact Git-blob reads, clean-HEAD equality, direct-parent checkpoint validation, exact delivery/status projection, and fail-closed malformed or drifted inputs |
| 1 | Add preplanned admission to service, graph, tools, and CLI | pending | `pytest -q tests/test_plan_admission.py tests/test_execution.py tests/test_kanban.py tests/test_tools.py tests/test_cli.py tests/test_plugin.py` exits 0 and proves dry-run/apply identity, native/standalone/tool parity, restart convergence, exact approval binding, and an imported-plan `implement → verify → review → deliver` graph with no fabricated define/plan cards |
| 2 | Reconcile worker, operator, dashboard-read, and verification contracts | pending | `pytest -q tests/test_worker_contract.py tests/test_recommendations.py tests/test_dashboard_api.py tests/test_cli.py tests/test_plugin.py tests/test_plan_admission.py::test_two_phase_checkpoint_chain && python scripts/check_md_links.py . && lefthook validate && pytest && ruff check . && daidala packs validate addyosmani && daidala packs validate aidlc && python -m build && python -m twine check dist/* && python scripts/check_release_contents.py . --wheel dist/*.whl` exits 0 |

Mark a phase `in-progress` while running it, `done (<evidence>)` once its gate passes, `pending` otherwise. In Git-pinned admission, the active source file remains `pending` during Daidala execution; Kanban carries `in-progress`, and only the successful status/checkpoint commit projects `done` into the next source revision.

## Phase 0 — Add strict Git plan-source and checkpoint-chain policy

**Goal:** Give Daidala one deterministic, profile-safe representation of an exact committed plan phase and one read-only validator for the commit that carries the preceding delivery into the next phase.

Policy invariants:

- One Daidala workflow executes exactly one plan phase. A multi-phase file or plan family produces a sequence of workflows, not one workflow with repeated mutable implementation captures.
- `source_revision` must equal the clean target checkout's full `HEAD`, and that same value remains `baseline_commit`. Plan content is read with Git object semantics from `source_revision:<repository-relative-plan-path>`, never from mutable working-tree bytes.
- The admitted plan path is repository-relative, inside the worktree, regular, non-symlinked at the selected revision, UTF-8, and within the existing bounded-document limit. The filename slot equals `Execution slot`; `Plan ID` and slot are unique among active `Pnnnn-*.md` plans at that revision; every declared dependency resolves without a cycle.
- The selected phase is `pending`. Every preceding phase in the same plan is `done (<evidence>)`; every following phase remains `pending`. `in-progress` is operational Kanban state and is not committed before Daidala approval.
- The immutable plan-source packet records mode `git-phased-plan`, repository identity, source revision, plan path, plan blob object ID, plan byte digest, Plan ID, execution slot, phase number/title/gate, direct dependencies, predecessor workflow ID when present, and a canonical packet digest.
- Approval binds the packet digest in addition to the exact imported `plan.md` digest and current constraints. The exact repository plan bytes are copied into Daidala's immutable artifact store; no model rewrites or summarizes them as approval authority.
- A first-phase admission has no predecessor workflow. A later phase names the immediately preceding phase workflow and requires that workflow to have accepted review and delivery evidence for the same Plan ID and preceding phase.
- The checkpoint source revision for phase `N+1` is a new single commit whose direct parent is phase `N`'s source revision. It contains the immutable delivered implementation plus the deterministic status projection for phase `N`; unrelated paths or extra commits are rejected.
- Imported-plan mode reserves the active plan path from implementation edits. A scope discovery blocks and supersedes the current admission: the operator commits a plan-only revision, starts a new workflow for the same pending phase at that new source revision, and grants fresh approval. The profile-local generated-plan `replace_plan` path cannot rewrite imported source or baseline identity.
- The checkpoint plan change is limited to marking the completed phase `done (daidala:<workflow-id>:<delivery-digest>)`, updating the document-level status to the next pending phase or complete, and leaving all phase goals, steps, gates, dependencies, ordering, and later statuses unchanged.
- Checkpoint validation compares the new commit's non-plan tree delta with the prior delivery's immutable diff and changed-path manifest, validates the exact allowed plan status projection, and rejects any mismatch. Validation is read-only and may use a temporary detached checkout; it never commits, pushes, merges, or mutates the operator checkout.
- The new checkpoint commit and packet receive a new human approval before phase `N+1` implementation. Approval of phase `N` covers only phase `N`'s immutable source revision and packet.
- A same-phase scope-revision commit is not a successful checkpoint and cannot carry implementation bytes. It has the prior source revision as direct parent, changes only the active plan, keeps the selected phase `pending`, optionally records the superseded workflow ID, and starts a new admission whose normal predecessor remains the last successfully delivered phase.

Steps:

1. Add `daidala/plan_admission.py` with strict bounded parsing for the phased-plan header, phase table, selected `## Phase N` section, verification gate, status vocabulary, plan IDs, execution slots, and direct dependencies. Reject duplicate fields, duplicate IDs/slots, unknown dependencies, cycles, noncontiguous phase numbers, mismatched table/headings, malformed evidence, and ambiguous Markdown instead of repairing it.
2. Resolve repository identity, full source revision, tree entry type, plan blob object ID, and exact bytes through an injectable Git command boundary. Require `source_revision == baseline_commit ==` clean checkout `HEAD`; reject abbreviated revisions, dirty repositories, submodule/tree/symlink plan entries, traversal, files outside the repository, non-UTF-8, and over-limit content.
3. Add a strict immutable `PlanSourceReference`/packet model in `daidala/state.py`, canonical serialization and digest identity, optional ledger persistence for generated-plan compatibility, and pure policy operations in `daidala/workflow.py`. Bind imported-plan approval to both plan and packet digests without weakening existing generated-plan ledgers.
4. Store the exact committed Markdown as the current immutable `plan.md` plus a canonical `plan-source.json` sidecar under the workflow's revision-addressed artifact root. Use create-or-verify replay semantics and retain historical source packets.
5. Implement predecessor lookup through `WorkflowStore.list_all` and checkpoint validation. Require same repository identity, Plan ID, immediately preceding phase, accepted review/delivery, direct-parent source revision, exact non-plan delivery delta, reserved plan path, and exact deterministic status projection with `daidala:<workflow-id>:<delivery-digest>` evidence.
6. Add temporary-repository tests for valid first and later phases, plan-only same-phase supersession, generated-plan backward compatibility, source/blob/tree/path failures, duplicate/cyclic plan graphs, stale or wrong predecessor identity, absent delivery, wrong parent, extra commits/paths, tampered status evidence, plan-content drift, binary diffs, replay, and no mutation of the operator checkout.
7. Update `daidala/AGENTS.md` and `tests/AGENTS.md` in the implementation commit with the new ownership and verification contracts.

Verification gate: The Phase 0 table command exits 0; packet and checkpoint validation is deterministic from committed Git objects and immutable Daidala evidence, and every mutable, ambiguous, stale, or unrelated input fails before ledger or Kanban mutation.

## Phase 1 — Add preplanned admission to service, graph, tools, and CLI

**Goal:** Admit a validated committed phase without model-generated definition/planning work, preserve the existing human gate, and dispatch only the normal post-gate implementation lifecycle after exact approval.

Steps:

1. Add a dry-run-first `start-from-plan` operation to `WorkflowService` and the shared native/standalone CLI. Inputs include target repository, repository-relative plan path, phase number, full source revision, board, complete stage-profile mapping, pack, workflow ID, optional predecessor workflow ID, and the existing explicit constraint source. Apply requires the exact fresh admission-packet digest returned by dry-run.
2. Add the equivalent strict plugin tool schema/handler and registration inventory. Handlers continue to accept `args: dict, **kwargs`, return JSON strings, and never expose plan bytes, profile-local paths, credentials, or raw Git output in errors.
3. On apply, re-run every Git, plan, dependency, predecessor, pack, profile, board, constraint, and checkpoint check before writing artifacts or ledger state. A stale dry-run digest creates no workflow or cards. Restart succeeds only when every source-packet and workflow input matches exactly.
4. Persist imported-plan mode and its packet before exposing the attended approval decision. Do not create `define` or `plan` cards and do not synthesize activation history for stages that did not execute.
5. Make approval require the imported plan digest, packet digest, and current constraint tuple. Only after approval create the Daidala-owned detached worktree at the identical source/baseline revision.
6. Extend `_ensure_post_gate_graph` and Kanban card rendering so imported-plan mode starts `implement` without a fabricated plan-card parent; `verify`, `review`, and `deliver` retain their normal parent chain, exact skills, activation requirements, workspace, revision, and idempotency behavior. Generated-plan mode continues to require the current plan card.
7. Keep generated-plan `replace_plan` behavior unchanged. Imported-plan replacement rejects profile-local artifact substitution and requires a new Git source revision/workflow; cancellation or supersession archives obsolete post-gate cards and removes only the owned worktree.
8. Update status/recommendation projections to treat the validated imported plan artifact as the pre-gate prerequisite while preserving Kanban as operational state authority and the ledger as approval/source authority.
9. Add positive, policy-violation, persistence, restart, stale-preview, supersession, wrong-worker, wrong-board, graph-parent, generated-mode regression, and native/standalone/tool parity tests.

Verification gate: The Phase 1 table command exits 0; a committed pending phase can be previewed, applied, reviewed, approved, and dispatched without define/plan workers, while stale or mismatched identity fails before worktree or card creation.

## Phase 2 — Reconcile worker, operator, dashboard-read, and verification contracts

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
