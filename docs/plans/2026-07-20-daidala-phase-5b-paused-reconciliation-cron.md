# Phase 5B — Paused reconciliation cron and controlled tick

Produce one repository-tested `project-cycle reconcile` path, install it as an
exact detached Daidala controller revision, create one profile-local Hermes cron
job that remains paused, and retain evidence that two controlled invocations
admit at most one maintainer-ready issue and converge on one workflow.

**Status:** in-progress — Phase 0 is complete at the integration checkpoint;
Phase 1 remains unstarted, and controller installation, cron creation, GitHub
mutation, and controlled dispatch remain separately approval-gated.

## Current state

- `main` retains the approved Phase 5B plan checkpoint `033325f`; the
  `feat/phase-5b-reconciliation` integration checkpoint contains both current
  `main` and detached live-controller revision
  `31331e8352208321ae819ad2464396f03207602b` in its ancestry.
- The integrated recovery line contributes the exercised admission replay,
  evaluator request, and cycle-completion implementation and tests without
  replacing the later Phase 4F/5A evidence on `main`.
- Phase 5A is complete and Phase 5B is in progress in
  `docs/plans/2026-07-13-daidala-self-improvement-loop.md:33-56`; no cron, new
  cycle, retained change, or remote finding has been created by Phase 5B.
- `daidala/reconciliation.py:20-142` has strict claim-recovery and pending-finding
  primitives, but their only current callers are tests in
  `tests/test_reconciliation.py:64-101`; there is no runtime reconciliation-tick
  coordinator or CLI command.
- `daidala/live_adapters.py:97-128` can fetch bounded ready issues, and
  `daidala/project_cycles.py:94-174` can preview or admit one explicitly named
  issue. No current surface deterministically selects one candidate, interprets
  an active cycle, or composes two-authority claim recovery.
- `hermes -p daidala-self-improvement cron status` reports a running gateway and
  no active jobs; `hermes -p daidala-self-improvement cron list` reports no
  scheduled jobs.
- The read-only query `gh-vault run --name ghcli -- gh issue list --repo
  forgegod/daidala --state open --label daidala-si ...` currently returns an
  empty list, so a controlled live tick has no existing issue to admit.
- Hermes v0.18.2 supports create, pause, edit, run, and durable run history, but
  `hermes cron create --help` exposes no atomic create-paused option. A manual
  run also refuses a paused job (`tools/cronjob_tools.py:604-637` in the
  installed Hermes source).

## Risk call-out

The first prerequisite is source integration, not cron creation. The live
controller revision and `main` have diverged. Building Phase 5B only on `main`
would silently discard the exact admission-replay and completion behavior that
produced the retained live evidence. Preserve the recovery commits by merging
`recovery/self-improvement-admission-replay` into a branch from `main`; do not
reimplement or squash them away. If integration verification fails, abort the
merge and leave the controller at revision `31331e8`.

Later phases mutate profile-local controller state, Hermes cron state, GitHub
issue state, Kanban state, and the attended channel. Their safety net is the
clean Git tree, exact detached installation revision, content-addressed tick
receipts, one approved issue, and a cron job that is created on a 24-hour
placeholder schedule and paused before its schedule is edited. If cron setup
fails, remove the new job and profile-local wrapper. If a controlled tick fails
after claiming an issue, keep the job paused, preserve the run and claim
evidence, and use two-authority recovery; never delete a claim or worktree by
inspection alone.

Hermes cannot manually run a paused job. For each controlled invocation, set a
24-hour future interval, resume the job, run it immediately, and pause it again
before any later phase. The immediate run uses Hermes' at-most-once claim; the
24-hour schedule prevents the gateway ticker from racing the operator sequence.

## Phase table

| # | Phase | Status | Verification gate |
|---|---|---|---|
| 0 | Integrate the exercised controller line | done (30 focused + 374 full tests; merge checkpoint) | `git merge-base --is-ancestor 31331e8352208321ae819ad2464396f03207602b HEAD` exits 0; focused recovery tests exit 0. |
| 1 | Implement deterministic reconciliation | pending | `pytest tests/test_reconciliation.py tests/test_live_adapters.py tests/test_project_cycles.py` exits 0 with selection, replay, recovery, outage, and notification cases. |
| 2 | Expose the dry-run-first operator surface | pending | Native and standalone `project-cycle reconcile --help` agree; CLI tests exit 0; dry-run fixtures produce no mutation. |
| 3 | Reconcile contracts and checkpoint the implementation | pending | The complete repository gate exits 0; one reviewed implementation checkpoint exists; no push occurs. |
| 4 | Install and verify the exact controller revision | pending | Native and standalone `doctor --live` report 11/11 pass for the separately approved checkpoint. |
| 5 | Create the profile-local wrapper and paused cron | pending | `cron list --all` shows exactly one paused named job; `cron runs <job>` is empty; scheduling remains disabled. |
| 6 | Run and replay one controlled tick | pending | Two completed cron attempts yield one cycle/workflow, no duplicate claim or graph, attended receipts, and a still-paused job. |

Mark a phase `in-progress` while running it, `done (<sha-or-evidence>)` once its
gate passes, and `pending` otherwise.

## Phase 0 — Integrate the exercised controller line

**Goal:** Create one implementation branch whose history contains both current
`main` documentation and the exact live controller revision `31331e8`.

Steps:

1. Reconfirm `main` is clean and synchronized with `origin/main`; stop on any
   unrelated worktree change.
2. Create a Phase 5B branch from `main`.
3. Merge `recovery/self-improvement-admission-replay` with `--no-commit` so the
   eleven exercised commits remain in history. Resolve documentation conflicts
   to current Phase 5A state while retaining recovery-line Python and tests.
4. Re-read the root, `daidala/`, `tests/`, `docs/`, and evaluation-result DOX
   chains before resolving their files.
5. Run focused recovery coverage:
   `pytest tests/test_completion.py tests/test_project_cycles.py
   tests/test_restricted_container.py tests/test_controller.py`.
6. Review the merge diff for lost evaluator-request, admission-replay,
   completion, or current Phase 5A evidence. Create the integration checkpoint
   only after the focused gate passes.

Verification gate: `git merge-base --is-ancestor
31331e8352208321ae819ad2464396f03207602b HEAD` exits 0, the focused pytest
command exits 0, and the merged plan still names Phase 5A done and Phase 5B
pending.

## Phase 1 — Implement deterministic reconciliation

**Goal:** Add one pack-neutral coordinator that produces immutable, bounded tick
evidence and mutates at most one validated intake item only on apply.

Steps:

1. Extend `daidala/reconciliation.py` with strict reconciliation preview/result
   records and a content-addressed profile-local tick store. The finite outcomes
   are idle, active-cycle convergence, blocked, admission preview, admitted, and
   replayed; unknown fields or unbounded text fail closed.
2. Interpret the prerequisite report explicitly: every check must pass except
   that `SI-ACTIVE-CYCLE` may identify one existing owner to observe and
   converge on. Never convert another blocked/error/not-run check into success.
3. Extend the production composition in `daidala/project_cycles.py` to:
   - verify registration, checkout, board, gateway, notification, credentials,
     and installed controller identity;
   - inspect stored admission/completion facts plus live Kanban ownership before
     selecting work;
   - fetch at most 100 structured ready issues, sort numeric issue IDs ascending,
     and select at most one;
   - evaluate expired claims with `ClaimRecoveryEvidence`, requiring both
     Daidala-ledger and live-board proof of no owner before release or reclaim;
   - derive the existing deterministic cycle/workflow identity and reuse the
     admission coordinator rather than duplicating its policy;
   - retain a content-addressed tick record under the controller profile.
4. Extend `daidala/live_adapters.py` only where the coordinator needs bounded
   claimed-item inventory or replay-safe release. Keep GitHub reads on the intake
   alias and mutations on the findings alias.
5. Send event-bound attended notifications for admission, approval wait, blocker,
   and recovery. Validate returned receipts before retaining them; a delivery
   failure is a failed tick, not success.
6. Add positive, policy-violation, replay, persistence, and boundary-failure
   tests in `tests/test_reconciliation.py`, `tests/test_project_cycles.py`, and
   `tests/test_live_adapters.py`. Include no candidate, multiple candidates,
   existing active cycle, duplicate tick, unexpired claim, expired claim with
   either owner still active, missing board, GitHub outage, and notification
   failure.

Recovery: if implementation reveals that current admission or completion APIs
cannot provide one required ownership fact, add that fact to the narrow owning
module and its tests in this phase. Do not infer status from filesystem presence
or duplicate Hermes Kanban state in Daidala.

Verification gate: `pytest tests/test_reconciliation.py
 tests/test_live_adapters.py tests/test_project_cycles.py` exits 0 and proves
that every mutation path selects at most one issue while duplicate calls return
one cycle/workflow identity.

## Phase 2 — Expose the dry-run-first operator surface

**Goal:** Make the same reconciliation operation callable from standalone
`daidala` and native `hermes daidala` without an LLM or nested chat process.

Steps:

1. Add `project-cycle reconcile` to the shared parser in `daidala/cli.py` with
   exact project-manifest, registration, default/stage profiles, pack, candidate
   limit, and claim-lease inputs.
2. Default to dry-run. Emit a canonical preview plus digest. Require
   `--apply --expected-preview-digest <digest>` for mutation, then rerun all live
   reads and reject drift before claim, workflow, or notification effects.
3. Return bounded JSON with the outcome, selected issue identity when present,
   cycle/workflow IDs, board, current stage, receipt identity, and exact
   profile-scoped inspection command. Never emit credential values, private
   destination data, issue bodies, or unbounded host output.
4. Add shared-parser tests in `tests/test_cli.py` and operator tests in
   `tests/test_project_cycles.py` for standalone/native parity, dry-run
   non-mutation, missing expected digest, stale digest, exit codes, and structured
   output.
5. Do not register a new model-facing tool unless a later use case needs one;
   Phase 5B uses a deterministic no-agent cron script and the operator CLI.

Verification gate: both `daidala project-cycle reconcile --help` and
`hermes daidala project-cycle reconcile --help` expose equivalent arguments;
`pytest tests/test_cli.py tests/test_project_cycles.py` exits 0; a fake-boundary
dry-run leaves issue, board, ledger, notification, and tick-store state
unchanged.

## Phase 3 — Reconcile contracts and checkpoint the implementation

**Goal:** Produce one reviewed repository checkpoint whose code, tests, plans,
and operator documentation describe the same paused no-agent reconciliation
boundary.

Steps:

1. Update `daidala/AGENTS.md` and `tests/AGENTS.md` for the new coordinator,
   profile-local tick evidence, shared CLI, and replay/recovery coverage.
2. Update `docs/15-self-improvement.md` so support status reflects the exercised
   manual cycles and the newly implemented but not-yet-live reconciliation path.
3. Update `docs/13-autonomous-triggering.md` to document the Daidala dogfood
   composition as a deterministic `--no-agent` script. Clarify that no provider
   or model executes in this job; the exact controller revision, script digest,
   registration, and CLI preview digest are the unattended identities.
4. Keep `docs/evaluation-results/v1/daidala-self-improvement.md` cases for the
   controlled tick as `not-run` until Phase 6 supplies live evidence.
5. Update this plan and
   `docs/plans/2026-07-13-daidala-self-improvement-loop.md` without marking
   Phase 5B done.
6. Run the complete repository gate and review staged scope before creating the
   implementation checkpoint. Do not push.

Verification gate: all of the following exit 0:

```bash
lefthook validate
pytest
ruff check .
daidala packs validate addyosmani
daidala packs validate aidlc
python scripts/check_md_links.py .
python -m build
python -m twine check dist/*
python scripts/check_release_contents.py . --wheel dist/*.whl
git diff --check
```

The checkpoint contains only the recovery-line integration, reconciliation
implementation, tests, contracts, and synchronized documentation. `git status
--short` is clean and no remote ref changed.

## Phase 4 — Install and verify the exact controller revision

**Goal:** Replace the detached controller installation only with the separately
approved Phase 3 checkpoint and restore a clean 11/11 live prerequisite report
before cron state exists.

Steps:

1. Present the exact Phase 3 commit SHA, diff scope, repository-gate evidence,
   and detached-install command for separate controller-installation approval.
2. Follow the verified detached installation procedure in
   `docs/16-self-improvement-setup.md`; never install from the mutable working
   tree, an editable package, or a symlink.
3. Restart the `daidala-self-improvement` gateway and verify the installed
   plugin source revision and both workflow packs in fresh processes.
4. Update profile-local non-secret prerequisite evidence to the approved
   revision without exposing credentials or private destinations.
5. Run native and standalone live diagnosis from the clean registered checkout.
6. If any check fails, restore detached revision `31331e8`, restart the gateway,
   and stop before creating a script or cron job.

Verification gate: native `hermes -p daidala-self-improvement daidala doctor
--live ...` and standalone `daidala doctor --live ...` each report all eleven
stable checks as pass, the installed revision equals the approved Phase 3 SHA,
and `hermes -p daidala-self-improvement cron list --all` remains empty.

## Phase 5 — Create the profile-local wrapper and paused cron

**Goal:** Materialize exactly one deterministic script-only reconciliation job
under the controller profile and leave it paused with no execution history.

Steps:

1. Obtain separate approval for profile-local script creation and cron creation;
   this approval does not authorize a tick or schedule enablement.
2. Write a dependency-free Python wrapper under the active controller profile's
   Hermes `scripts/` directory. It must:
   - invoke `hermes -p daidala-self-improvement daidala project-cycle reconcile`
     with an argument list and fixed trusted paths;
   - parse the dry-run JSON, then invoke apply with its exact preview digest;
   - print nothing for an idle result;
   - print one bounded non-secret JSON summary for admitted, replayed, active, or
     blocked results; and
   - exit nonzero on malformed output, drift, adapter failure, or notification
     failure.
3. Record and verify the wrapper SHA-256 digest in profile-local non-secret
   evidence. Do not place credentials, private destinations, or mutable issue
   data in the script.
4. Create `daidala-forgegod-daidala-reconciliation` as a `--no-agent` job on a
   24-hour placeholder interval, with the registered checkout as `--workdir`
   and attended failure delivery. Immediately pause it by exact name, then edit
   the desired operational schedule to `every 15m` while it remains paused.
5. Verify the job is unique, no run attempt exists, the gateway is healthy, and
   its persisted mode is no-agent. Do not resume or run it in this phase.

Recovery: if the job cannot be paused or its stored script/workdir/delivery does
not match the approved values, remove the job, remove only the new wrapper, and
confirm the cron list is empty.

Verification gate: `hermes -p daidala-self-improvement cron list --all` shows
exactly one disabled/paused job named
`daidala-forgegod-daidala-reconciliation`; `hermes -p
 daidala-self-improvement cron runs daidala-forgegod-daidala-reconciliation
--limit 20` shows no attempts; the job's script digest matches retained evidence.

## Phase 6 — Run and replay one controlled tick

**Goal:** Exercise the paused cron twice against one separately approved
maintainer-ready issue, retain replay evidence, and leave implementation blocked
at human approval with scheduling disabled.

Steps:

1. Select one exact issue for the probe. No open `daidala-si` issue currently
   exists, so obtain separate approval before creating a structured issue or
   applying `daidala-si:ready`. The issue must use the committed template, name
   one bounded goal, and be marked ready by an authorized maintainer. The loop
   must not mark its own finding ready.
2. Re-run live doctor, confirm the checkout is clean, no cycle is active, the
   cron job is paused, and the exact issue is the only eligible item.
3. Run `project-cycle reconcile` without `--apply`; present the issue, cycle,
   workflow, baseline, pack, controller, board, and preview digest for separate
   controlled-dispatch approval.
4. Set the job schedule to a 24-hour interval while paused. Resume it, invoke
   `hermes -p daidala-self-improvement cron run <exact-job-id>`, inspect the
   completed attempt, and pause the job immediately. Confirm one claim, one
   manifest snapshot, one workflow graph, one approval wait, and an attended
   receipt.
5. Repeat the same resume → immediate run → pause sequence once. Confirm the
   second attempt reports the same active cycle/workflow or replay result and
   creates no second claim, manifest, graph, worktree, or issue.
6. Confirm no implementation approval, generic Kanban unblock, commit, push,
   finding publication, release, deployment, or controller promotion occurred.
7. Restore the intended `every 15m` schedule while the job remains paused.
8. Update `docs/evaluation-results/v1/daidala-self-improvement.md` with redacted,
   content-addressed TC-F16 evidence; update both plans and current operator docs.
   Mark Phase 5B done only after all replay and notification predicates pass.
9. Run the documentation link check, focused reconciliation tests, and the full
   repository gate before the evidence checkpoint. Do not push.

Recovery: a failed first or second attempt leaves the job paused. Preserve cron
history, tick records, claim data, Kanban facts, and notification evidence. If a
claim lease expires, release or reclaim it only after both Daidala and the live
board prove no active owner. Do not cancel a valid approval-wait cycle merely to
make live doctor green.

Verification gate: `cron runs <exact-job-id> --limit 20` shows two completed
controlled attempts; GitHub has one claim identity; profile-local artifacts and
Hermes Kanban name one cycle/workflow; the second attempt created no duplicate;
the approval card remains blocked; attended receipts validate; `cron list --all`
still reports the job paused; and the complete repository gate exits 0.

## Out of scope

- Do not enable recurring scheduling in Phase 5B.
- Do not approve or run implementation for the controlled cycle.
- Do not retain, reject, revert, commit, push, or publish a candidate change.
- Do not synchronize findings; that remains Phase 5C and separately publication-gated.
- Do not run the paired UC-03 pack evaluation; that remains Phase 5D.
- Do not add webhook intake, a Daidala scheduler, a daemon, an MCP server, or a
  nested `hermes chat` bridge.
- Do not update Hermes Agent or change the persistent controller's provider/model
  configuration.

## Risks & open questions

- The exact controlled issue is intentionally undecided. Phase 6 cannot start
  until the operator selects an existing issue or separately approves creation
  of one structured probe issue and its ready label.
- Hermes v0.18.2 has no atomic create-paused operation and refuses manual runs
  while paused. The 24-hour placeholder plus immediate pause, and later
  resume → immediate run → pause sequence, are required safety controls. Any
  host behavior that differs from the inspected v0.18.2 source stops the phase.
