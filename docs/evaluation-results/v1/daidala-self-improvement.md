# Daidala self-improvement evaluation v1

## Record status

Phases 1 through 4F and Phase 5A reconciliation are complete. Detached
controller revision `31331e8352208321ae819ad2464396f03207602b` completed one
Addyosmani and one Aidlc UC-01 workflow. Both issues are closed as completed,
their claims and owned worktrees are released, attended completion receipts are
retained, and both deliveries record `committed: false` and `pushed: false`.

Each workflow independently changed only `calculator.py` and
`test_calculator.py`, reproduced `AssertionError: 1 != 2` in the restricted
baseline, passed its approved restricted candidate, and received an accepted
`improved` review. The cross-pack comparison is nevertheless `incomparable`:
the workflows used different repository baselines and different candidate test
fixtures. No preferred pack, retained change, reconciliation cron, new cycle,
or published finding is authorized by this record.

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
| TC-F05-01 | Define and plan | Persist activation, definition, plan, and handoff identities; create one blocked approval card. | Implementation-card creation. | pass |
| TC-F06-01 | Exact approval | Reject wrong or stale tuple; exact approval creates one owned worktree and post-gate graph. | Treating generic Kanban unblock as approval. | pass |
| TC-F07-01 | Constraints | Formatting-only replacement is identity-preserving; semantic replacement invalidates stale work. | Deleting historical evidence. | not-run |
| TC-F08-01 | Implementation | Capture immutable changed paths and evidence from only the owned worktree. | Mutation of the target checkout or protected paths. | pass |
| TC-F08-02 | Verification recovery | Preserve a failed attempt and allow bounded same-card recovery. | Hiding the failed command or output digest. | not-run |
| TC-F09-01 | Review and delivery | Review frozen scope; delivery records commit and push as false. | Review mutation, commit, or push. | pass |
| TC-F10-01 | Status and cancellation | Read live Kanban without mirrored status; remove only owned worktree state. | Writing Hermes Kanban storage directly. | not-run |
| TC-F11-01 | Packaging | Wheel and directory installs expose code, packs, skills, tools, and dashboard assets only. | Packaging runtime state, credentials, or evidence. | not-run |
| TC-F12-01 | Hermes routes | Exercise bounded default, fallback, MoA, goal, auxiliary, and delegation paths. | Replacing Hermes model/runtime authority. | not-run |
| TC-F13-01 | Issue intake | Accept only structured maintainer-ready issues and create one recoverable claim. | Inferring readiness from prose or Project membership. | pass |
| TC-F13-02 | Finding synchronization | Deduplicate stable finding identity and require a returned identity and URL before `published`. | Applying `daidala-si:ready` to generated findings. | pass |
| TC-F14-01 | Version comparison | Compare exact supported and candidate Daidala/Hermes identities. | Updating the active runtime. | not-run |
| TC-F15-01 | Controller isolation | Load candidate artifacts only in a fresh evaluator. | Candidate plugin loading in the persistent controller. | pass |
| TC-F16-01 | Reconciliation | Duplicate ticks converge; missing board, dirty worktree, or uncertain claim blocks. | Recreating state from titles or prose. | not-run |
| TC-F17-01 | Metrics | Required deterministic and repeated thresholds govern retention eligibility; missing evidence is `incomparable`. | Retention from observational evidence alone. | pass |
| TC-F18-01 | Producer provenance | Reject unknown skill producers, digest drift, duplicate entry IDs, and stale activation identity. | Worker self-assertion of an unactivated skill. | pass |
| TC-F18-02 | Document promotion | Reject ephemeral scratch, undeclared repository paths, oversized documents, and invalid dispositions. | Promotion by Kanban comment or file existence. | pass |
| TC-F18-03 | Retention and DOX | Require planned mutable path, frozen diff, increment manifest, and owning DOX scope before retention. | Treating a workflow artifact as current documentation. | pass |

Repository-only `pass` rows remain grounded by the pure and fake-adapter tests
in `tests/test_projects.py`, `tests/test_registrations.py`,
`tests/test_adapters.py`, `tests/test_controller.py`,
`tests/test_reconciliation.py`, `tests/test_credentials.py`,
`tests/test_prerequisites.py`, `tests/test_evaluation.py`,
`tests/test_live_adapters.py`, `tests/test_project_cycles.py`, and
`tests/test_increments.py`. Live rows marked `pass` are additionally grounded by
the content-addressed UC-01 artifacts below. TC-F08-02 and TC-F16-01 remain
`not-run`: the workflows did not exercise same-card verification recovery or a
controlled reconciliation tick.

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

Status: `not-run`. No candidate task or skill set has been selected. Selection
and any later promotion remain human decisions.

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

The required follow-up is a new separately approved paired evaluation from one
frozen repository baseline and one canonical fixture containing the same focused
and adjacent tests for both packs. Until then, pack selection and retention are
blocked. A local actionable finding is recorded here as publication pending; no
GitHub finding was created or updated during reconciliation.

## Identities, receipts, findings, and blockers

- Project: `forgegod-daidala`.
- Committed manifest path: `.daidala/project.yaml`.
- Phase 3 implementation checkpoint: `31e043be49f19a8f69cfb5eb630fb5b1257abc00`.
- Phase 4 implementation checkpoint: `cba9c52`.
- Installed detached controller: `31331e8352208321ae819ad2464396f03207602b`.
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
- Both workflow evidence sets remain mode-`0600` profile-local files. Private
  destination data is omitted from this record.
- No retained increment, preferred-pack decision, reconciliation cron, new
  cycle, or remote finding was created by Phase 5A.

## Redaction statement

This record contains no credentials, connection strings, profile dumps, private
Kanban records, or raw unbounded logs. Future evidence must use redacted,
content-addressed references and preserve only the bounded fields required by
the protocol.
