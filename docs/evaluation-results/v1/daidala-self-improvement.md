# Daidala self-improvement evaluation v1

## Record status

Phases 1 through 5C-R are complete. Phase 5C retained published finding
[#5](https://github.com/forgegod/daidala/issues/5), and Phase 5C-R remediated and
closed published control findings
[#6](https://github.com/forgegod/daidala/issues/6) and
[#7](https://github.com/forgegod/daidala/issues/7) as completed. Detached
controller revision `3ce1bfc15c5102d75d54e846ea6ddb8520b6eed8` is installed;
native and standalone diagnosis pass 11/11, the reconciliation cron remains
paused, and no active cycle or owned worktree exists. Phase 5D packet `c0cdfefb`
is frozen and exact issues #9/#10 remain unready. Live paired evaluation remains
unapproved, as do push, release, and promotion.

Each Phase 5A workflow independently changed only `calculator.py` and
`test_calculator.py`, reproduced `AssertionError: 1 != 2` in the restricted
baseline, passed its approved restricted candidate, and received an accepted
`improved` review. That cross-pack comparison remains `incomparable`:
the workflows used different repository baselines and different candidate test
fixtures. No preferred pack or retained calculator change is authorized by the
Phase 5A comparison. Phase 5B authorizes only the retained paused cron and its
one controlled terminal probe cycle.

Limits: [`experiment-limits.yaml`](experiment-limits.yaml).
Protocol: [`../../15-self-improvement.md`](../../15-self-improvement.md).
Environment gate: [`../../16-self-improvement-setup.md`](../../16-self-improvement-setup.md).

## Evidence rules

Each executed case records its goal, preconditions, exact procedure, expected
result, prohibited side effects, observed result, status, and redacted evidence
references. Allowed statuses are `pass`, `fail`, `blocked`, and `not-run`.
Repository tests cannot convert a blocked live probe into `pass`.

## Stable case matrix

| ID | Area | Procedure and expected result | Prohibited side effect | Status |
|---|---|---|---|---|
| TC-F01-01 | Project manifest | Parse `.daidala/project.yaml`; canonical identity and both pack digests match packaged resources. | Trusting repository data as local authority. | pass |
| TC-F01-02 | Registration | Bind a valid trusted registration to the manifest; mismatched project, remote, or path fails closed. | Creating a profile or board. | pass |
| TC-F02-01 | Pack provenance | Validate Addyosmani and AI-DLC source revisions and content digests. | Installing or updating skills. | pass |
| TC-F02-02 | Pack drift | Change one pinned digest; validation rejects the identity. | Repairing the digest from remote state. | pass |
| TC-F03-01 | CLI and tools | Compare native and standalone project-cycle parser, dispatch, JSON, exit code, and exact apply identity. | Registering a second or untested handler. | pass |
| TC-F03-02 | Prerequisite CLI parity | Execute the shared handler through standalone and native parser surfaces; JSON and exit code match. | Adding a second checker executable. | pass |
| TC-F04-01 | Setup preview | Preview registration and admission without mutation; require literal confirmation for setup. | Profile, board, GitHub, or repository mutation. | not-run |
| TC-F04-02 | Prerequisite diagnosis | Run the complete stable checklist from a clean checkout; retain exact passes and blockers. | No setup mutation; fixing or creating prerequisite state. | pass |
| TC-F05-01 | Define and plan | Persist activation, definition, plan, and handoff identities; expose the ledger-owned pending approval action without an executable approval task. | Implementation-card creation before exact approval. | pass |
| TC-F06-01 | Exact approval | Reject wrong or stale tuples; keep the gate ledger-owned and non-executable; create one owned worktree only after exact attended approval. | Autonomous approval or an executable approval task. | pass |
| TC-F07-01 | Constraints | Formatting-only replacement is identity-preserving; semantic replacement invalidates stale work while immutable revision paths preserve historical artifacts. | Deleting or overwriting historical evidence. | pass |
| TC-F08-01 | Implementation | Capture immutable changed paths and evidence from only the owned worktree. | Mutation of the target checkout or protected paths. | pass |
| TC-F08-02 | Verification recovery | Preserve a failed attempt and allow bounded same-card recovery. | Hiding the failed command or output digest. | pass |
| TC-F09-01 | Review and delivery | Review frozen scope; delivery records commit and push as false. | Review mutation, commit, or push. | pass |
| TC-F10-01 | Status and cancellation | Read live Kanban without mirrored status; remove only owned worktree state. | Writing Hermes Kanban storage directly. | pass |
| TC-F11-01 | Packaging | Wheel and directory installs expose code, packs, skills, tools, and dashboard assets only. | Packaging runtime state, credentials, or evidence. | not-run |
| TC-F12-01 | Hermes routes | Exercise bounded default, fallback, MoA, goal, auxiliary, and delegation paths. | Replacing Hermes model/runtime authority. | not-run |
| TC-F13-01 | Issue intake | Accept only structured maintainer-ready issues and create one recoverable claim. | Inferring readiness from prose or Project membership. | pass |
| TC-F13-02 | Finding synchronization | Deduplicate stable finding identity and require a returned identity and URL before `published`. | Applying `daidala-si:ready` to generated findings. | pass |
| TC-F14-01 | Version comparison | Compare exact supported and candidate Daidala/Hermes identities. | Updating the active runtime. | not-run |
| TC-F15-01 | Controller isolation | Load candidate artifacts only in a fresh evaluator. | Candidate plugin loading in the persistent controller. | pass |
| TC-F16-01 | Reconciliation | Duplicate ticks converge; missing board, dirty worktree, or uncertain claim blocks. | Recreating state from titles or prose. | pass |
| TC-F17-01 | Metrics | Required deterministic and repeated thresholds govern retention eligibility; missing evidence is `incomparable`. | Retention from observational evidence alone. | pass |
| TC-F18-01 | Producer provenance | Reject unknown skill producers, digest drift, duplicate entry IDs, and stale activation identity. | Worker self-assertion of an unactivated skill. | pass |
| TC-F18-02 | Document promotion | Reject ephemeral scratch, undeclared repository paths, oversized documents, and invalid dispositions. | Promotion by Kanban comment or file existence. | pass |
| TC-F18-03 | Retention and DOX | Require planned mutable path, frozen diff, increment manifest, and owning DOX scope before retention. | Treating a workflow artifact as current documentation. | pass |

Repository-only `pass` rows remain grounded by the pure and fake-adapter tests
in `tests/test_projects.py`, `tests/test_registrations.py`,
`tests/test_adapters.py`, `tests/test_controller.py`,
`tests/test_reconciliation.py`, `tests/test_credentials.py`,
`tests/test_prerequisites.py`, `tests/test_evaluation.py`,
`tests/test_live_adapters.py`, `tests/test_project_cycles.py`,
`tests/test_cancellation.py`, and
`tests/test_increments.py`. Live rows marked `pass` are additionally grounded by
the content-addressed UC-01 artifacts below. TC-F16-01 also has the controlled
live evidence below. Phase 5C supplies live same-card verification recovery for
TC-F08-02. Controlled Phase 5C-R evidence additionally grounds TC-F06-01 and
TC-F07-01: the approval gate is ledger-owned and worker calls fail closed, while
revision-addressed create-or-verify artifacts preserve historical bytes. Issues
#6 and #7 are closed completed and `Done`.

## Use-case records

### UC-01 — approval-gated bug fix and recovery

Status: `pass` for independent lifecycle completion. Addyosmani cycle
`cycle-21158b4320bf09968915110abdfeb32ac2a0c833acfe90a99bf340936c148f55`
and Aidlc cycle
`cycle-98afe833a63afdbfce7a16bcd9741d4475e46cfb47013c2982cbe3ad04653c26`
both reached accepted evidence-only delivery and terminal completion. Neither
workflow committed, pushed, retained, published, or promoted its calculator
repair.

Pack comparison: `incomparable`. No preferred pack is selected. The Addyosmani
candidate contains only the focused `answer() == 2` test, while the Aidlc
candidate also contains the instance contract's required adjacent value-and-type
regression. The runs also bind different repository baselines. These are
comparison-input differences, not measured pack effects.

### UC-02 — constraint change and candidate regression

Status: `not-run`. The semantic constraint replacement, checked-division
fixture, fresh candidate evaluator, dashboard observation, and dedicated debug
browser probe still require separate approvals and prerequisites.

### UC-03 — pack and skill compatibility

Status: `not-run`. The operator selected the pinned current/default
`addyosmani` pack, pinned candidate `aidlc`, and one canonical Python
`importlib.resources.contents()` migration fixture. The dry-run-first
comparison-admission prerequisite passes the complete repository gate. Exact
packet `c0cdfefb6740752d96dd2864f751c5fda25292bb26d889764e593fccf2c8645e`
is locally preflighted; detached controller `3ce1bfc` is installed; exact open
issues #9/#10 have byte-identical payloads and no ready/claimed labels or events.
Cycles, plans, cleanup, retention, publication, push, release, and promotion
remain separately gated in the
[Phase 5D child plan](../../plans/2026-07-21-daidala-phase-5d-uc03-pack-evaluation.md).

## UC-01 reconciliation

All listed digests were recomputed from the retained immutable files before this
record was updated.

| Evidence | Addyosmani | Aidlc |
| --- | --- | --- |
| Cycle | `cycle-21158b4320bf09968915110abdfeb32ac2a0c833acfe90a99bf340936c148f55` | `cycle-98afe833a63afdbfce7a16bcd9741d4475e46cfb47013c2982cbe3ad04653c26` |
| Repository baseline | `72ac8c5567358a6ad8fd40baaf37d5a4db17284e` | `66e3ad03b70a99bffa67c16596b6cd59fc0967d2` |
| Plan | `10308dd2660c4ab015c96000ce5ddce60d51b75d59bea14e9993d17cd8baad10` | `22a1a91ce4a0872296020d3744714be4252187462f34bc4cd1e482f1d583986c` |
| Restricted baseline | `33d3623ddc6fbbbf958bb9ec2738d0590e05e560e39c8c34dd094af078e47027` | `80bb8cf75e3e70175b04754c1324144dc05f15b715f8844c9cf68061dd5219e2` |
| Restricted candidate | `0c45b4964850d499c85b87a27b21140240507ec67c0ac9515d7d8c3723c65975` | `6f97e6d234026a182d1d6088fa916d31a3b100eba470de3ed57599f43f394c6d` |
| Candidate tests | One focused regression | Focused and adjacent value/type regressions |
| Review | `a75ec87e299de4114d36ab4ef0fe1a183f9cbe2b5b9d18ad083c79a0df61ed26` | `8bbe519697cb1747cf844f6ee18c338cfe7da1b38f6b35ce8c4ac03e21eedd83` |
| Delivery | `37892c934fb5aee55168b1822d013ffb764c3151b3d991a952b568a89b0b661a` | `3647d6c1bc0e8009c3514b1b1321a00bc89d491f0099346e72b822eec31f4835` |
| Completion | `56ba5dced96190df7325bad48ae8fbcf0e324db04f1e606189b00b4fe286998d` | `250756b4021b92e7b9ef74214febfab1d5891baf908ca3650acb473505eb1101` |

The restricted image and inner command match, both baselines fail the focused
assertion, both candidates pass their approved tests, both changed-path sets are
exactly `calculator.py` and `test_calculator.py`, and both deliveries are
evidence-only. Comparison eligibility still fails because baseline revision,
baseline fixture digest, candidate fixture digest, and candidate test contract
differ. The restricted execution records also do not carry a controller revision
that could close the environment-identity gap.

The remaining pack-evaluation follow-up is a new separately approved paired
evaluation from one frozen repository baseline and one canonical fixture
containing the same focused and adjacent tests for both packs. Until then, pack
selection remains blocked.
The independent controller-identity finding was published as issue
[#5](https://github.com/forgegod/daidala/issues/5); the Phase 5A comparison itself
still authorizes no pack preference.

## Phase 5B controlled reconciliation tick

- **Goal:** prove that two separately approved cron invocations converge on one
  claim, cycle, workflow graph, and attended admission event.
- **Preconditions:** clean detached controller `80dd73e`, native and standalone
  11/11 diagnosis, digest-matched no-agent wrapper, one paused job with no run
  history, and maintainer-ready issue #4 as the only candidate.
- **Procedure:** approve preview
  `de26b48d6e77e8b496defdd44e48ffd1e861a77976dee36ffe3e97053a406b20`,
  execute and re-pause once; then separately approve active-cycle preview
  `ade8a3a8bb5fe3f859f9b8298f8d4635445c4e8667769fc13fbb580b5412dd55`,
  execute and re-pause again.
- **Expected:** first outcome `admitted`, second outcome `replayed`, with one
  claim comment, one workflow graph, and no duplicate admission notification.
- **Prohibited:** autonomous schedule escape, duplicate claim or graph, worktree,
  approval, implementation, commit, push, release, publication, or private
  destination disclosure.
- **Observed:** execution IDs `b668e16ad75142b38b576c53fa7ae961` and
  `9cd24ef3c1204192ae0109fdde3709e6` completed. Both mode-`0600` tick records bind
  cycle `cycle-1b2ab9b45a3e066498e2f79d1bb9c30b9ca26dffb0c6a5d965990551e8bdf9d6`;
  outcomes are `admitted` then `replayed`, and both reference attended receipt
  `telegram:30`. Issue #4 has one claim comment, the workflow has two cards, and
  the plan card is blocked without approval or a worktree. The job is paused on
  `every 15m` with infinite repeat; the repository remains clean.
- **Status:** `pass`.

## Phase 5B deterministic probe closeout

- **Goal:** terminate the admission/replay-only probe without authorizing its
  blocked implementation path or editing live state by inspection.
- **Installed controller:** clean detached revision
  `550671c19e5434fbe183140214ca12b4a047692d`; native and standalone cancellation
  help and active-cycle-only pre-apply diagnosis passed.
- **Approved preview:**
  `9deb8cefaa6be650eda41a076a58bb056782637d7d821103d51b553787f17810`,
  binding admission `dcbd215d11ea3d564a66e7fd308d6640fddb447ef9c662db5adb06ea8785c509`,
  workflow `911f904a6ea671992ef317bb4b707b4f01650c76434e0e429eaf9ea5ce8b0322`,
  issue #4, and the bounded no-implementation reason.
- **Observed:** cancellation digest
  `99fe86b360266677a74be7f7ad5d2a2c9618e0acd787e0c4bc6b73e2384c8e33` closed
  issue #4 as not planned, removed ready/claimed labels, archived cards
  `t_aca696c4` and `t_4fe72ba8`, retained no worktree, and delivered attended
  receipt `telegram:37`.
- **Replay:** the same digest returned the identical terminal result. GitHub kept
  one claim comment; each card kept one cancellation comment and one archive
  event; no second notification or artifact was created.
- **Evidence:** remote, workflow, notification, and terminal cancellation files
  are strict profile-local mode-`0600` records. The cron remains paused on
  `every 15m`, the repository is clean, and both live diagnosis routes pass
  11/11.
- **Status:** `pass`.

## Phase 5C controller-revision evidence improvement

- **Goal and source:** resolve published issue
  [#5](https://github.com/forgegod/daidala/issues/5) by replacing both
  restricted-container request and execution schemas with v2 contracts that bind
  one exact 40-lowercase-hex detached controller revision without exposing
  controller state to the evaluator.
- **Cycle and approval:** cycle
  `cycle-cbbbfd0273b7144cd2475369d14c9b55bd301ffd442728531bcb61db3c71ba18`
  retained policy revision 2 and separately approved plan revision 3, digest
  `0460b92b674e9c1a8bbe0eeb6c6f5face0184248838ba62ad7ba09390af39628`.
- **Candidate evidence:** immutable implementation
  `401f3dfec2604f5d64a7a605ede17f494644574dc567d755512f86b1c27a93f3`
  changes exactly five approved paths. Review
  `02d1f01e92c52a25a0a2f8a5825f55d3cff9d478a0bd9dac5a2e4123a89e4cc0`
  accepted the change without findings; evidence-only delivery
  `3b5a7db684bcf15c1009304b030f62544c04575020409fc223b62d9e3ea8a46d`
  records commit and push as false.
- **Measurement:** 50 focused and 406 full tests pass. Focused and full Ruff,
  both pack validations, 42-file Markdown links, package build, Twine,
  release-content, Lefthook, and diff checks pass. Failed runner-environment
  attempts remain in the verification record; the accepted recovery pins the
  repository interpreter and preserves all failed evidence.
- **Retention:** separate approval applied the exact immutable diff to clean
  baseline `106b4f923823e016d33f95c66a826ec55a2bb1e1`. The target checkout passes the
  complete repository gate and retains checkpoint `83780e2`. Push and release
  remain separately gated.
- **Control findings:** one blocked approval card was promoted and approved by an
  autonomous worker before attended approval; recovery stopped the worker before
  any diff, invalidated approval, and removed the clean worktree. Constraint and
  plan replacement also reused artifact paths referenced by older revisions.
  These are publication-pending control-plane findings, not accepted behavior.
- **Completion prerequisite:** repeated successful commands can share one output
  digest. The source completion preview now canonicalizes those passing identities
  as a unique sorted set. Two no-mutation standalone previews converge on digest
  `a09f3405f8dcd98360186b2373bb8845e7d3cc84ca5a47f214d8d19d80027c8b`;
  checkpoint `9d9f4f6` passes 407 tests and the complete release gate. Exact detached
  installation plus native/standalone parity passed before apply.
- **Completion:** separately approved application of that exact preview closed
  issue #5 as completed, released its claim, retained remote, notification, and
  terminal records at mode `0600`, and delivered receipt `telegram:44`.
  Completion digest is
  `f9f5566ee15f7797d72c230e69e06c13930f4b6a5ca6b9e5214cdd624ab9fd65`.
- **Status:** `pass`.

## Phase 5C-R control-plane remediation

- **Approval boundary:** exact detached revision `9f380a6` removed the executable
  approval card path and rejected worker-context approval before mutation.
  Controlled workflow `tc-f06-direct-approval-probe-v2` retained fail-closed
  envelope `1f4a99ec`, zero-mutation comparison `217d8b9d`, post-approval graph
  evidence `5d9491c3`, and manifest `0db444d6`.
- **Artifact boundary:** exact detached revision `2595bf5` made stage artifacts
  immutable and revision-addressed. Controlled workflow
  `tc-f07-revision-artifact-probe-v1` retained replay comparison `1032386d`,
  conflict envelope `91a4efad`, five historical references, terminal evidence
  `e9224f67`, and cleanup manifest `5a79e2fa`.
- **Closeout:** issues #6 and #7 are closed completed and `Done`; both cases are
  `pass`; the installed controller is clean at `2595bf5`; native and standalone
  diagnosis pass 11/11; reconciliation is paused; no active cycle or owned
  worktree exists; commit/push in probe delivery evidence remain false.

## Identities, receipts, findings, and blockers

- Project: `forgegod-daidala`.
- Committed manifest path: `.daidala/project.yaml`.
- Phase 3 implementation checkpoint: `31e043be49f19a8f69cfb5eb630fb5b1257abc00`.
- Phase 4 implementation checkpoint: `cba9c52`.
- Installed detached controller: `2595bf5f8aacdd1411c101250acc2d0211eaf22a`;
  rollback controllers `9f380a6b04fdbb51817c7ac2279b217fda34f0c2` and
  `550671c19e5434fbe183140214ca12b4a047692d` and their prior evidence remain
  outside plugin discovery.
- The approved-attempt prerequisite report is
  [`prerequisite-report-15c3a629e5d670012642a137524d3659ccd42bf6b034b2ec6eabd05e3bbd8e70.json`](prerequisite-report-15c3a629e5d670012642a137524d3659ccd42bf6b034b2ec6eabd05e3bbd8e70.json),
  exits `0`, has the matching SHA-256
  `15c3a629e5d670012642a137524d3659ccd42bf6b034b2ec6eabd05e3bbd8e70`,
  and records all eleven checks as `pass`.
- The post-install prerequisite report is
  [`prerequisite-report-d7a02f7cf12ee7290ded16517010c26cb2ed00ba8d211eb2ea2d953cfe6ef906.json`](prerequisite-report-d7a02f7cf12ee7290ded16517010c26cb2ed00ba8d211eb2ea2d953cfe6ef906.json),
  exits `0`, has matching SHA-256
  `d7a02f7cf12ee7290ded16517010c26cb2ed00ba8d211eb2ea2d953cfe6ef906`,
  and records all eleven checks as `pass` at controller revision
  `311fcae39e4d1e6505b38c015792008315f64e95`.
- Addyosmani completion receipt: `telegram:20`; issue #2 is closed as completed
  and its claim is released.
- Aidlc completion receipt: `telegram:23`; issue #3 is closed as completed and
  its claim is released.
- Phase 5B admission receipt: `telegram:30`; terminal cancellation receipt:
  `telegram:37`. Issue #4 is closed not planned and its active labels are removed.
- Phase 5C issue #5 is closed completed and its claim is released. Its retained
  cycle, plan, implementation, review, delivery, completion, and attended receipt
  identities are recorded above.
- Both workflow evidence sets remain mode-`0600` profile-local files. Private
  destination data is omitted from this record.
- Phase 5C retains one controller-identity increment. Phase 5C-R retains both
  control remediations and their published, completed findings. No preferred-pack
  decision, push, release, or promotion occurred. Phase 5B still leaves one
  paused cron and one terminal probe cycle.

## Redaction statement

This record contains no credentials, connection strings, profile dumps, private
Kanban records, or raw unbounded logs. Future evidence must use redacted,
content-addressed references and preserve only the bounded fields required by
the protocol.
