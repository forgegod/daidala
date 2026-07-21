# Phase 5B — Paused reconciliation cron and controlled tick

Produce one repository-tested `project-cycle reconcile` path, install it as an
exact detached Daidala controller revision, create one profile-local Hermes cron
job that remains paused, and retain evidence that two controlled invocations
admit at most one maintainer-ready issue and converge on one workflow.

**Status:** in-progress — the original reconciliation scope through Phase 6 and
the Phase 7 deterministic closeout implementation are complete. Phase 8
installed exact revision `550671c`; live cancellation remains separately
exact-digest approval-gated. Phase 0 is complete at
merge checkpoint `bdd2baf` and
Phase 1 is complete at checkpoint `1d6a909`; Phase 2 is complete at the shared
dry-run-first CLI checkpoint `5472cc1`. Phase 3 repository reconciliation and
the complete release gate are complete at the repository checkpoint.
Phase 4 is complete: the controller runs clean detached revision `80dd73e`,
native and standalone live diagnosis passed 11/11 before admission, and rollback
revision `31331e8` remains retained outside the plugin scan root. Phases 5 and 6 are
complete: two separately approved job runs produced one admission and one replay
for the same issue, claim, cycle, graph, and attended receipt. The job is paused
again; later workflow stages remain separately approval-gated.

## Current state

- `main` retains the approved Phase 5B plan checkpoint `033325f`; the
  `feat/phase-5b-reconciliation` integration checkpoint contains both current
  `main` and detached live-controller revision
  `80dd73efa9a4e462304b71ba157b5e5c0172b793` in its ancestry.
- The integrated recovery line contributes the exercised admission replay,
  evaluator request, and cycle-completion implementation and tests without
  replacing the later Phase 4F/5A evidence on `main`.
- Phase 5A and Phase 5B are complete. Phase 5B created one paused cron and one
  active probe cycle; it created no retained change or remote finding.
- Current source implements dry-run-first, digest-bound cancellation for that
  terminal probe closeout. It passes the complete repository and release gate
  and is installed at detached controller revision `550671c`; cancellation has
  not been applied.
- `daidala/reconciliation.py` now owns strict previews/results and immutable
  mode-`0600` tick evidence; `daidala/project_cycles.py` composes explicit
  prerequisite interpretation, terminal-record-aware active ownership, stable
  one-item selection, admission replay, and two-authority claim recovery.
- `daidala/live_adapters.py` now inventories ready and claimed issues and uses
  audited, replay-safe claim release. The shared CLI exposes reconciliation as
  dry-run by default and requires an exact preview digest for apply.
- Current source and the installed controller expose equivalent standalone and
  native reconciliation and cancellation help. The controller profile runs
  exact clean detached revision `550671c`.
- The complete repository, packaging, release-content, pack, link, lint, and
  test gate passes with 398 tests. Native and standalone installation diagnosis
  passed all eleven checks after Docker integration was restored. Current live
  diagnosis intentionally reports only `SI-ACTIVE-CYCLE` blocked while the probe
  workflow waits at its plan approval boundary; no remote ref changed.
- `hermes -p daidala-self-improvement cron status` reports a running gateway and
  no active jobs. `cron list --all` reports exactly one paused no-agent job named
  `daidala-forgegod-daidala-reconciliation` on `every 15m`; its repeat is
  infinite, its script digest matches profile-local evidence, and exactly two
  successful direct executions are retained.
- Issue #4 has one claim comment and one claimed label. Its two content-addressed
  tick results are `admitted` then `replayed`; both bind the same cycle and
  attended receipt. The workflow has one two-card graph, no approval or worktree,
  and records commit and push as false.
- Hermes v0.18.2 supports create, pause, edit, run, and durable run history, but
  `hermes cron create --help` exposes no atomic create-paused option. A manual
  run also refuses a paused job (`tools/cronjob_tools.py:604-637` in the
  installed Hermes source).

## Risk call-out

The controller remains pinned to exact detached revision `550671c` even as
documentation checkpoints advance the working branch. Staging, failed, and
rollback checkouts stay outside the profile plugin scan root so no duplicate
Daidala manifest can override the active controller.

The second risk is a nominal "paused" job that can still run before verification.
Later phases mutate profile-local controller state, Hermes cron state, GitHub
issue state, Kanban state, and the attended channel. Their safety net is the
clean Git tree, exact detached installation revision, content-addressed tick
receipts, one approved issue, and a cron job that is created on an `every 24h`
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
| 0 | Integrate the exercised controller line | done (`bdd2baf`; 30 focused + 374 full tests) | `git merge-base --is-ancestor 31331e8352208321ae819ad2464396f03207602b HEAD` exits 0; focused recovery tests exit 0. |
| 1 | Implement deterministic reconciliation | done (24 focused + 384 full tests) | `pytest tests/test_reconciliation.py tests/test_live_adapters.py tests/test_project_cycles.py` exits 0 with selection, replay, recovery, outage, and notification cases. |
| 2 | Expose the dry-run-first operator surface | done (39 focused + 388 full tests) | Current-source native and standalone `project-cycle reconcile --help` agree; CLI tests exit 0; dry-run fixtures produce no mutation. |
| 3 | Reconcile contracts and checkpoint the implementation | done (388 tests + complete release gate) | The complete repository gate exits 0; one reviewed repository checkpoint exists; no push occurs. |
| 4 | Install and verify the exact controller revision | done (`80dd73e`; native + standalone 11/11) | Clean detached identity, both packs, reconciliation CLI, gateway restart, and both live reports pass; `31331e8` rollback remains outside the scan root and cron remains empty. |
| 5 | Create the profile-local wrapper and paused cron | done | `cron list --all` shows exactly one paused no-agent named job with infinite repeat; its script digest matches profile-local evidence. |
| 6 | Run and replay one controlled tick | done | Two completed executions yield one claim, cycle, workflow graph, and attended receipt; immutable outcomes are `admitted` then `replayed`, and the job is paused on `every 15m`. |
| 7 | Implement deterministic terminal cancellation | done (58 focused + 398 full tests; complete release gate) | Focused cancellation, adapter, project-cycle, CLI, and active-ownership tests pass; the full repository and release gate pass. |
| 8 | Install and apply the exact probe cancellation | in-progress (installation passed at `550671c`) | Native/standalone help and active-cycle-only diagnosis pass; a fresh cancellation digest still requires separate approval before issue, workflow, notification, or terminal mutation. |

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
5. Reuse the admission coordinator's event-bound admission notification and send
   reconciliation-owned blocker and recovery notifications. Approval-wait
   notification remains workflow-owned because reconciliation cannot announce a
   plan gate before the workflow reaches it. Validate returned receipts before
   retaining them; a delivery failure is a failed tick, not success.
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
   cycle/workflow IDs, board, current stage when proven (otherwise `null`),
   receipt identity, and exact profile-scoped inspection command. Never emit
   credential values, private destination data, issue bodies, or unbounded host
   output.
4. Add shared-parser tests in `tests/test_cli.py` and operator tests in
   `tests/test_project_cycles.py` for standalone/native parity, dry-run
   non-mutation, missing expected digest, stale digest, exit codes, and structured
   output.
5. Do not register a new model-facing tool unless a later use case needs one;
   Phase 5B uses a deterministic no-agent cron script and the operator CLI.

Verification gate: both `daidala project-cycle reconcile --help` and an
isolated current-source `hermes daidala project-cycle reconcile --help` expose
equivalent arguments;
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
5. Run native live diagnosis and run standalone live diagnosis with the
   controller profile environment imported without printing any value.
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
4. Create `daidala-forgegod-daidala-reconciliation` as a `--no-agent` job on an
   `every 24h` placeholder interval with infinite repeat, the registered checkout
   as `--workdir`, and attended failure delivery. Immediately pause it by exact
   name, then edit the desired operational schedule to `every 15m` while it
   remains paused. Pass only the script filename to `cron create`; Hermes rejects
   an absolute script path. Do not use bare `24h`, which is a one-shot schedule;
   use `every 24h --repeat 0` so the edited job retains infinite repeat.
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

## Phase 7 — Implement deterministic terminal cancellation

**Goal:** Add the missing pack-neutral closeout path for an admitted cycle that
must terminate without implementation, without mutating the live probe.

Steps:

1. Add strict cancellation preview, remote, workflow, attended, and final
   terminal receipt schemas. Persist each immutable artifact at mode `0600`.
2. Extend the GitHub intake adapter with replay-safe not-planned closure that
   requires the exact claim owner and removes both ready and claimed labels.
3. Coordinate remote closure, generic workflow archival, owned-worktree cleanup,
   attended notification, and final terminal evidence as a convergent operation.
4. Add shared native/standalone `project-cycle cancel`; keep it dry-run by
   default and require `--apply --expected-preview-digest` for mutation.
5. Release active admission ownership only for exactly one strict completion or
   cancellation record whose cycle, workflow, and admission digest match.
6. Add adapter, schema, coordinator, project-cycle, CLI parity, replay, identity
   drift, and active-ownership tests. Update runtime, test, operator, and plan
   contracts.
7. Run the complete repository and release gate, then create one source
   checkpoint. Do not install or apply cancellation in this phase.

Verification gate: focused cancellation coverage and full `pytest` pass;
`ruff check .`, package validation, pack validation, link checking, release
contents, and `git diff --check` pass; the live controller, issue, claim, board,
cron, and attended channel are unchanged.

## Phase 8 — Install and apply the exact probe cancellation

**Goal:** Promote the reviewed cancellation source under rollback protection,
then close only the controlled probe after a separate exact-digest approval.

Steps:

1. Obtain approval for the exact detached controller revision and automatic
   rollback on any installation gate failure.
2. Install outside the plugin scan root, verify clean detached identity, restart
   the gateway, validate both packs, and prove native/standalone cancellation
   help parity plus live diagnosis.
3. Generate a cancellation preview for issue #4 and its deterministic cycle with
   the bounded reason that the controlled reconciliation replay completed and no
   implementation was authorized.
4. Present the exact preview digest and identities for separate apply approval.
5. Apply once. Verify issue #4 is closed not planned without active intake
   labels, all workflow cards are archived, no worktree exists, one attended
   cancellation receipt exists, one terminal record releases active ownership,
   doctor passes, and replay returns the same evidence without another send.
6. Retain redacted evidence, synchronize current docs and plans, run the complete
   gate, and create one checkpoint. Do not admit Phase 5C work in this phase.

Recovery: any installation failure restores the exact prior controller revision.
Any partial cancellation preserves receipts and retries the same approved digest;
never delete admission, workflow, claim, or terminal evidence manually.

Verification gate: exact installed revision and help parity pass; cancellation
replay converges; issue, workflow, artifact modes, notification receipt, doctor,
cron pause, repository gate, and clean Git status all pass.

## Out of scope

- Do not enable recurring scheduling in Phase 5B.
- Do not approve or run implementation for the controlled cycle.
- Do not apply cancellation before Phase 8 installation and exact-digest approval.
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
