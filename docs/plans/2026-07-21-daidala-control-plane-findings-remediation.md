# Daidala Control-Plane Findings Remediation Plan

**Status:** in progress — Increment A revision `9f380a6` is retained, installed,
and controlled-evidence verified. Increment B is repository-verified at candidate
diff `4babce8a` under exact scope `d531546d`; retention, installation, live
probing, finding closure, push, release, and deployment remain unapproved.

**Parent plan:**
[`2026-07-13-daidala-self-improvement-loop.md`](2026-07-13-daidala-self-improvement-loop.md)

**Parent phase:** `5C-R — Control-plane findings remediation`

**Activation boundary:** after completed Phase 5C checkpoint `04f6516` and before
Phase 5D. Parent-plan execution must enter this child plan at its first incomplete
phase and must not start Phase 5D until the parent 5C-R gate passes.

## Goal

Close the two failed Phase 5C control cases without weakening Daidala's existing exact-digest, Kanban, worktree, or evidence contracts:

1. `TC-F06-01`: an approval gate must never become executable by a Kanban worker.
2. `TC-F07-01`: replacing policy or plan revisions must never overwrite bytes referenced by historical evidence.

## Assessment

Both findings are directly relevant to the implementation. They were recorded as failed cases and publication-pending findings, but they were not remediation action items in the completed Phase 5C scope.

- The approval finding is in Daidala's orchestration boundary. `WorkflowService._ensure_approval_card()` creates a normal assigned Kanban card. `KanbanGraphAdapter.ensure_card()` only distinguishes it through `initial_status="blocked"`. Hermes documents `promote` as a manual recovery path; once promoted, the assigned card can be dispatched. An approval card with no worker skills is still executable.
- The artifact finding is in Daidala's storage boundary. `ExecutionWorkspace.write_artifact()` uses `Path.write_text()`, while `WorkflowService.submit_artifact()` repeatedly selects fixed names such as `plan.md`. A later revision can therefore replace bytes at a path retained by an older ledger record.

Documentation in the Phase 5C evaluation and parent plan did not fix either behavior. This plan turns both findings into explicit, separately gated work.

## Phase table

| # | Phase | Status | Verification gate |
|---|---|---|---|
| 0 | Finding publication and exact scope approval | done (issues #6/#7; scope `8752c064`) | Separately approved issue creation returns one identity per finding; the exact Increment A scope digest receives attended approval. |
| 1 | Increment A candidate — non-executable approval gate | done (candidate `ddef04b3`; 410 tests) | Focused tests and the complete repository gate pass against one immutable candidate diff; no live state changes. |
| 2 | Increment A retention, installation, and controlled evidence | done (manifest `0db444d6`; issue #6 completed) | Separate retention/install/probe approvals hold; `TC-F06-01` passes, diagnosis is 11/11, cron is paused, and the finding is terminally reconciled. |
| 3 | Increment B candidate — immutable revision artifacts | done (candidate `4babce8a`; 411 tests) | Focused tests and the complete repository gate pass against one immutable candidate diff; historical fixture bytes remain unchanged. |
| 4 | Increment B retention, installation, and controlled evidence | pending | Separate retention/install/probe approvals hold; `TC-F07-01` passes, diagnosis is 11/11, cron is paused, and the finding is terminally reconciled. |
| 5 | Closeout and parent-plan reconciliation | pending | Both cases are retained as `pass`, this plan is `done`, parent Phase 5C-R is done with closeout evidence, and Phase 5D remains unstarted. |

Mark one row `in-progress` while executing it, `done (<evidence>)` only after its
gate passes, and leave every later row `pending`.

## Phase 0 evidence

- `TC-F06-01` is published as
  [issue #6](https://github.com/forgegod/daidala/issues/6) with exact approved
  body digest `06bb1142d1a6385885209f52984ffeb1404bf6867cea6f334ca7239c95ff2fdf`.
- `TC-F07-01` is published as
  [issue #7](https://github.com/forgegod/daidala/issues/7) with exact approved
  body digest `21b403a3f1df58eff57f4773bb2796e60d5722a542b3e9aed25566196b045bdb`.
- Both issues are open, have only their approved base/category/priority labels,
  and do not have `daidala-si:ready`.
- The approved canonical Increment A packet is
  [`2026-07-21-daidala-increment-a-scope.json`](2026-07-21-daidala-increment-a-scope.json),
  SHA-256 `8752c0647d1d82b35cd5995527c3726af778392375baac904525735ea659979a`,
  at base revision `04f6516364ed84515ee47bc03c560259bd7884db`.
- Publication and scope approval authorize Phase 1 candidate work only. They do
  not authorize readiness, retention, installation, live probing, issue closure,
  push, release, or deployment.

## Phase 1 evidence

- The RED focused gate produced exactly seven expected failures covering approval
  card creation, worker approval, ledger-only recommendations, worker guidance,
  and both pack execution paths.
- The immutable candidate patch excludes plan closeout metadata and has SHA-256
  `ddef04b37f011c4d5b9062c2c7344152f1d44900a834f0e551a2c0e30d78b1ce`.
- The focused approval suite, Ruff, and Markdown links pass. The complete gate
  passes with 410 tests, both pack validations, sdist and wheel builds, Twine,
  release-content verification, Lefthook validation, and staged diff checks.
- The candidate creates no approval card, parents `implement` from `plan` only
  after exact ledger approval, rejects `HERMES_KANBAN_TASK` before approval
  mutation, derives the pending action without Kanban state, and leaves historical
  approval references readable and inert.
- Verification changed no live controller, profile, board, cron, issue state,
  worktree, or installed revision. The controller remains at `9d9f4f6` and Phase 2
  requires separate retention, installation, and controlled-probe approvals.

## Phase 2 evidence

- Retention and exact detached installation were approved for commit
  `9f380a6b04fdbb51817c7ac2279b217fda34f0c2` without authorizing a live probe.
- A clean detached local clone passed isolated Hermes discovery and both pack
  validations before the controller gateway was stopped.
- The controller swap retained clean rollback revision
  `9d9f4f6a2801293e20622d98c97f50d017888872` outside plugin discovery, preserved
  mode-`0600` prerequisite and cron evidence beside it, and atomically updated
  both live controller-revision fields to `9f380a6` before gateway restart.
- Native and standalone live diagnosis pass all eleven checks, the installed
  plugin is clean and detached, both packs validate, the gateway is running, and
  reconciliation job `1847b1b1e14b` remains paused.
- Controlled direct workflow `tc-f06-direct-approval-probe-v2` bound plan digest
  `443b226397b6eeb80bf0ec367986630ec83289467665334bfb9351657fde9878`.
  Worker-context approval returned the exact fail-closed envelope retained at
  digest `1f4a99ecff3146f1a253d1111f0c850aa195cc1a5792827908bb75b246bb1719`;
  mutation-sensitive pre/post evidence was identical at comparison digest
  `217d8b9d7c479ccd3997e3aa395963b641bbab3875ebc3d15dd952dec4722151`.
- One attended exact-digest approval created one owned worktree and exactly the
  implementation, verification, review, and delivery cards in a linear graph
  parented from the plan card, with no approval card and no post-gate worker run.
  Post-approval verification digest
  `5d9491c3d2f9fad9bed1321216a752fe33e678f7153384c4afc001a38a61a3e2`
  records that boundary.
- Separately approved cancellation archived all six cards, removed only the
  owned worktree, and retained commit/push as false. Cleanup digest
  `c0fb8d85ff6412c9d5e495b282dccd8e020f29f19efd5493e750e3af8bbb9518`
  and final-state digest
  `ec4807081364888000371035a77ca4d4d0e2dc92b2bd82251f4906cb2f41b695`
  are indexed by evidence manifest
  `0db444d65e36d8d55585391f06264611e2ed67fe943c66e57c9e92b82d0b0234`.
- Native and standalone diagnosis returned to 11/11 after the same gateway was
  restored. The repository remains clean, the reconciliation cron remains
  paused, and no push, release, or deployment occurred.
- [Issue #6](https://github.com/forgegod/daidala/issues/6) has the exact evidence
  comment digest `96eb8e8ea582070e9d9e1f54148e688a5c75ca04cacb1eda29db03fef6df1d3f`,
  is closed completed, and has Project status `Done`. Issue #7 remains open,
  `Todo`, and unready for Increment B.

## Decisions

### 1. The approval gate is ledger-owned, not a Kanban task

Do not create an approval Kanban card. The current plan and constraint tuple in `WorkflowLedger` is the gate. Status and recommendation surfaces expose the exact human action, but there is no task that a dispatcher can promote or execute.

After exact approval:

- create the owned worktree;
- create implementation, verification, review, and delivery cards;
- make the plan card their graph parent;
- retain the exact approval tuple in `ApprovalRecord`.

The `WorkflowStage.APPROVAL` enum may remain for serialized historical records and presentation, but new workflows do not record an approval `CardReference`. Existing terminal ledgers remain readable; old approval cards are inert historical evidence and are never recreated or used as a fallback.

### 2. Kanban workers cannot invoke approval

The plugin approval handler must fail closed when `HERMES_KANBAN_TASK` is present. This is the exact worker marker used by Hermes Kanban v0.18.2. It prevents a plan worker or any other dispatched card from crossing the gate through `daidala_approve`.

Approval remains available only from an attended, non-worker controller session or the explicit CLI. It still binds the current plan revision and digest plus the current constraint revision and digest. This is an operational guard, not a cryptographic identity claim; Daidala must not describe it as proof of a person's identity.

### 3. Artifact objects are immutable and revision paths are unique

`ExecutionWorkspace.write_artifact()` and `write_json_artifact()` become create-or-verify operations:

- create atomically with exclusive mode;
- if the path already exists with identical bytes, return the existing identity for same-operation replay;
- if the bytes differ, stop with `ExecutionError`;
- never truncate or replace an existing artifact.

Stage artifacts use deterministic revision directories:

```text
artifacts/
  policy-0002/
    define.md
    plan-0003/
      plan.md
      implementation.diff
      implementation-paths.json
      verification-<sha256>.txt
      review.md
      delivery.json
```

Constraint artifacts keep their existing exclusive, revision-addressed layout. Same-content verification retries may reuse the same immutable digest path inside one plan revision. Different policy or plan revisions never share stage artifact paths.

### 4. No in-place migration

There is no active cycle after Phase 5C. Do not rewrite existing profile-local evidence. New writes use the new layout. Historical paths remain readable through ledger references. If an old-layout nonterminal workflow is discovered before installation, stop installation and cancel or complete it with the old controller; do not migrate it in place.

## Scope and ordering

Implement as two independently reviewable increments. The approval fix is safety-critical and lands first.

### Increment A — Non-executable human approval gate

#### A1. Add failing policy tests

Files:

- `tests/test_kanban.py`
- `tests/test_tools.py`
- `tests/test_worker_contract.py`
- `tests/test_recommendations.py`
- `tests/test_execution.py`
- `tests/test_workflow.py`

Add tests proving:

1. submitting a plan records no approval Kanban card;
2. a gateway dispatch after plan completion cannot start approval work or create a worktree;
3. the approval tool returns a structured error when `HERMES_KANBAN_TASK` is set and leaves ledger, Kanban, and workspace unchanged;
4. wrong or stale exact digests still fail;
5. attended non-worker approval records the current plan/constraint tuple, creates one worktree, and creates one idempotent post-gate graph;
6. post-gate cards depend on the plan card and cannot exist before ledger approval;
7. status and recommendations expose one exact approval action without relying on a host approval card;
8. old serialized approval card references remain readable but are never completed, promoted, or recreated.

Run the focused tests before implementation and retain the expected failures.

#### A2. Remove the executable approval card path

Files:

- `daidala/service.py`
- `daidala/kanban.py`
- `daidala/recommendations.py`
- `daidala/tools.py`

Changes:

- stop calling `_ensure_approval_card()` after plan submission or replacement;
- remove `complete_approval()` from the new approval path;
- make `_ensure_post_gate_graph()` link post-gate cards to the current plan card;
- derive the pending gate from current ledger identity in status/recommendations;
- reject plugin approval calls under `HERMES_KANBAN_TASK` before service mutation;
- preserve exact-digest idempotency and worktree ownership behavior;
- leave old approval `CardReference` values read-only and inert.

Do not introduce a daemon, external approval service, synthetic assignee, hidden profile, or auto-generated approval token.

#### A3. Update contracts

Files:

- `README.md`
- `daidala/AGENTS.md`
- `tests/AGENTS.md`
- `daidala/skills/orchestrate/SKILL.md`
- `docs/00-getting-started.md`
- `docs/01-architecture.md`
- `docs/02-workflow-state.md`
- `docs/03-pack-reference.md`
- `docs/05-lifecycle-stages.md`
- `docs/10-autonomous-development-use-cases.md`
- `docs/11-skill-usage-and-user-control.md`
- `docs/13-autonomous-triggering.md`
- `docs/15-self-improvement.md`
- `docs/16-self-improvement-setup.md`

Replace the statement that approval creates or completes a blocked card. State that the ledger is the human gate, Kanban workers cannot approve, and post-gate cards appear only after attended exact approval.

### Increment B — Immutable revision-addressed artifacts

#### B1. Add failing storage and workflow tests

Files:

- `tests/test_execution.py`
- `tests/test_workflow.py`
- `tests/test_tools.py`
- `tests/test_cli.py`

Add tests proving:

1. different plan revisions produce different paths and leave the first plan bytes and digest unchanged;
2. a semantic constraint replacement creates a new policy directory and leaves prior define/plan artifacts unchanged;
3. changed bytes at an existing path fail without mutation;
4. same bytes at the same path converge idempotently;
5. implementation, changed-path, review, verification, and delivery artifacts use the current policy/plan directory;
6. delivery reads the revision-specific changed-path manifest rather than a fixed filename;
7. cancelled, completed, and replayed workflows resolve historical references without path rewriting;
8. traversal, absolute, oversized, and malformed relative paths still fail closed.

Retain before/after hashes in tests so path uniqueness alone cannot hide overwritten bytes.

#### B2. Introduce the immutable path contract

Files:

- `daidala/execution.py`
- `daidala/service.py`

Changes:

- add one validated helper for policy/plan artifact relative paths;
- make generic text/JSON writes atomic create-or-verify operations;
- pass `policy_revision` and `plan_revision` at every stage write;
- update all readers that currently use fixed names;
- keep verification artifacts content-addressed within the revision directory;
- preserve `StoredArtifact.path` as the authoritative read reference.

Do not add mutable `current` symlinks, copy old artifacts, or scan directories to infer current state. The ledger remains authoritative.

#### B3. Update contracts

Files:

- `daidala/AGENTS.md`
- `tests/AGENTS.md`
- `docs/15-self-improvement.md`
- `docs/16-self-improvement-setup.md`

Document revision-addressed immutable stage artifacts and create-or-verify replay semantics. Mark `TC-F07-01` pass only after controlled evidence exists.

## Verification gates

Each increment stops immediately on missing skills, invalid structured output, unexpected changed paths, or a failing command.

Focused gate:

```bash
pytest -q tests/test_kanban.py tests/test_tools.py tests/test_worker_contract.py \
  tests/test_recommendations.py tests/test_execution.py tests/test_workflow.py \
  tests/test_cli.py
ruff check daidala tests
python scripts/check_md_links.py .
git diff --check
```

Complete repository gate:

```bash
lefthook validate
pytest
ruff check .
daidala packs validate addyosmani
daidala packs validate aidlc
python -m build
python -m twine check dist/*
python scripts/check_release_contents.py . --wheel dist/*.whl
```

### Phase 3 candidate evidence

- Exact scope packet:
  `docs/plans/2026-07-21-daidala-increment-b-scope.json`
- Scope digest:
  `d531546dde3ba60dde5537da3b5fa037c59824cc13f6557fcc9eb8987181fe94`
- Implementation/test/contract diff digest:
  `4babce8aab0f6ba0e3d0acb175f1eed7f1ff400efb89f584ba30534e1a0389f2`
- Focused gate: 92 tests, Ruff, markdown links, and `git diff --check` pass.
- Complete gate: 411 tests, Ruff, both pack validators, build, Twine,
  release-content validation, and Lefthook pass.
- No commit, controller installation, live workflow, cron resume, push, release,
  or deployment occurred.

## Controlled evidence

Each live probe requires separate approval for the exact installed candidate,
workflow identity, current tuple, mutating operation, and cleanup.

### Approval probe — completed

The retained direct-workflow probe established all required boundaries:

1. pre-gate state contained only completed definition and plan cards;
2. no approval card, worktree, or post-gate card existed;
3. with the gateway stopped, one worker-marked approval call rejected before
   mutation and its exact envelope was durably retained before parsing;
4. one separately approved attended exact-digest call created one owned worktree
   and the four expected post-gate cards, with no approval card or worker run;
5. separately approved direct-workflow cancellation archived all six cards and
   removed only the owned worktree before the same gateway was restored; and
6. native and standalone live diagnosis returned to 11/11 with the cron paused
   and repository clean.

### Artifact probe

1. Start one disposable controlled workflow with the cron paused.
2. Capture hashes and modes for revision-1 define and plan artifacts.
3. Replace constraints and plan through separately approved operations.
4. Verify distinct revision paths and unchanged revision-1 bytes, hashes, and modes.
5. Replay same-content writes and verify convergence without new objects.
6. Attempt conflicting bytes at an existing path and verify fail-closed behavior.
7. Cancel the disposable cycle through its separately approved terminal preview.

Private destinations and credentials remain excluded from retained evidence.

## Publication, implementation, and retention gates

The following are separate decisions:

1. approve publication of one issue per finding;
2. approve Increment A's exact implementation plan digest;
3. approve Increment A retention and exact controller installation;
4. approve Increment B's exact implementation plan digest;
5. approve Increment B retention and exact controller installation;
6. approve each controlled live probe and terminal cleanup;
7. approve closing published findings only after their cases pass.

Do not combine approval-gate hardening and artifact immutability into the completed Phase 5C issue or its retained diff.

## Stop conditions

Stop before mutation when any of these is true:

- the repository or installed controller is dirty;
- an active cycle exists;
- the reconciliation cron is not paused;
- an old-layout nonterminal workflow exists;
- Hermes no longer exposes `HERMES_KANBAN_TASK` to dispatched workers;
- removing the approval card would require direct Kanban database writes;
- artifact readers depend on directory inference rather than ledger references;
- candidate scope includes push, release, cron resume, unrelated refactoring, or secret material.

## Expected outcome

- `TC-F06-01` passes because no executable approval task exists and Kanban workers cannot invoke approval.
- `TC-F07-01` passes because every revision has a distinct path and every stored object is immutable.
- `TC-F06-01` is retained as `pass` and issue #6 is closed completed.
- `TC-F07-01` remains `fail` and issue #7 remains open and unready until
  Increment B controlled evidence is retained.
