# Daidala self-improvement evaluation v1

## Record status

Phase 4 adds repository-tested fresh evaluator homes, immutable metric evidence,
comparison verdicts and controlled lesson-reuse deltas for all three modes,
isolation-receipt and candidate/controller separation, identity-bound
baseline-before-mutation ordering, clean teardown, dirty-state quarantine, and
increment/DOX reconciliation. Phase 3 implements strict credential bindings,
the stable eleven-check prerequisite registry, redacted reports, bounded live
probes, and native versus standalone handler parity. A clean-tree `--live` run
produced one blocked report:
only `SI-REPOSITORY` passed because trusted registration, controller plugin,
board, credential capability records, Project evidence, attended receipt, and
evaluator receipt do not exist. No setup mutation, GitHub write, container run,
model call, browser run, cron job, or self-improvement cycle occurred. This
document is not evidence that the loop works end to end.

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
| TC-F03-01 | CLI and tools | Compare planned native and standalone project-cycle surfaces. | Registering an untested tool. | not-run |
| TC-F03-02 | Prerequisite CLI parity | Execute the shared handler through standalone and native parser surfaces; JSON and exit code match. | Adding a second checker executable. | pass |
| TC-F04-01 | Setup preview | Preview registration and admission without mutation; require literal confirmation for setup. | Profile, board, GitHub, or repository mutation. | not-run |
| TC-F04-02 | Prerequisite diagnosis | Run the complete stable checklist from a clean checkout; retain exact passes and blockers. | Fixing or creating prerequisite state. | blocked |
| TC-F05-01 | Define and plan | Persist activation, definition, plan, and handoff identities; create one blocked approval card. | Implementation-card creation. | not-run |
| TC-F06-01 | Exact approval | Reject wrong or stale tuple; exact approval creates one owned worktree and post-gate graph. | Treating generic Kanban unblock as approval. | not-run |
| TC-F07-01 | Constraints | Formatting-only replacement is identity-preserving; semantic replacement invalidates stale work. | Deleting historical evidence. | not-run |
| TC-F08-01 | Implementation | Capture immutable changed paths and evidence from only the owned worktree. | Mutation of the target checkout or protected paths. | not-run |
| TC-F08-02 | Verification recovery | Preserve a failed attempt and allow bounded same-card recovery. | Hiding the failed command or output digest. | not-run |
| TC-F09-01 | Review and delivery | Review frozen scope; delivery records commit and push as false. | Review mutation, commit, or push. | not-run |
| TC-F10-01 | Status and cancellation | Read live Kanban without mirrored status; remove only owned worktree state. | Writing Hermes Kanban storage directly. | not-run |
| TC-F11-01 | Packaging | Wheel and directory installs expose code, packs, skills, tools, and dashboard assets only. | Packaging runtime state, credentials, or evidence. | not-run |
| TC-F12-01 | Hermes routes | Exercise bounded default, fallback, MoA, goal, auxiliary, and delegation paths. | Replacing Hermes model/runtime authority. | not-run |
| TC-F13-01 | Issue intake | Accept only structured maintainer-ready issues and create one recoverable claim. | Inferring readiness from prose or Project membership. | not-run |
| TC-F13-02 | Finding synchronization | Deduplicate stable finding identity and require a returned identity and URL before `published`. | Applying `daidala-si:ready` to generated findings. | pass |
| TC-F14-01 | Version comparison | Compare exact supported and candidate Daidala/Hermes identities. | Updating the active runtime. | not-run |
| TC-F15-01 | Controller isolation | Load candidate artifacts only in a fresh evaluator. | Candidate plugin loading in the persistent controller. | not-run |
| TC-F16-01 | Reconciliation | Duplicate ticks converge; missing board, dirty worktree, or uncertain claim blocks. | Recreating state from titles or prose. | not-run |
| TC-F17-01 | Metrics | Required deterministic and repeated thresholds govern retention eligibility; missing evidence is `incomparable`. | Retention from observational evidence alone. | pass |
| TC-F18-01 | Producer provenance | Reject unknown skill producers, digest drift, duplicate entry IDs, and stale activation identity. | Worker self-assertion of an unactivated skill. | pass |
| TC-F18-02 | Document promotion | Reject ephemeral scratch, undeclared repository paths, oversized documents, and invalid dispositions. | Promotion by Kanban comment or file existence. | pass |
| TC-F18-03 | Retention and DOX | Require planned mutable path, frozen diff, increment manifest, and owning DOX scope before retention. | Treating a workflow artifact as current documentation. | pass |

The deterministic `pass` rows are grounded by the pure and fake-adapter tests in
`tests/test_projects.py`, `tests/test_registrations.py`, `tests/test_adapters.py`,
`tests/test_controller.py`, `tests/test_reconciliation.py`,
`tests/test_credentials.py`, `tests/test_prerequisites.py`,
`tests/test_evaluation.py`, and `tests/test_increments.py`. The current repository
gate passes 328 tests, Ruff, Lefthook validation, both pack validations, Markdown
links, build, Twine, release-content, and diff checks. Live cycle rows stay
`not-run` until their own gate.

## Use-case records

### UC-01 — approval-gated bug fix and recovery

Status: `not-run`. The temporary calculator fixture, both pack runs, exact plan
gate, failed verification preservation, and unchanged target checkout still
require a separately approved live cycle.

### UC-02 — constraint change and candidate regression

Status: `not-run`. The semantic constraint replacement, checked-division
fixture, fresh candidate evaluator, dashboard observation, and dedicated debug
browser probe still require separate approvals and prerequisites.

### UC-03 — pack and skill compatibility

Status: `not-run`. No candidate task or skill set has been selected. Selection
and any later promotion remain human decisions.

## Identities, receipts, findings, and blockers

- Project: `forgegod-daidala`.
- Committed manifest path: `.daidala/project.yaml`.
- Phase 3 implementation checkpoint: `31e043be49f19a8f69cfb5eb630fb5b1257abc00`.
- Phase 4 implementation checkpoint: `cba9c52`.
- The redacted prerequisite report is
  [`prerequisite-report-d4e1b3a3498507f9f9c069fc16beb4c81d4eb7c65943d82c5bf96f38497bcc3e.json`](prerequisite-report-d4e1b3a3498507f9f9c069fc16beb4c81d4eb7c65943d82c5bf96f38497bcc3e.json),
  exits `2`, has SHA-256
  `d4e1b3a3498507f9f9c069fc16beb4c81d4eb7c65943d82c5bf96f38497bcc3e`,
  records `SI-REPOSITORY=pass`, and records all ten other checks as `blocked`.
- Controller profile `daidala-self-improvement` exists, but its native
  `daidala` command is unavailable because no non-bundled plugin is installed;
  the dedicated board and trusted registration also do not exist.
- The Docker CLI is unavailable in this WSL distro, so `restricted-container`
  remains blocked pending Docker Desktop WSL integration and verification.
- GitHub repository, Issues, and operator Project queries work, but no Project
  exists and the runtime issue aliases are not bound or least-privilege verified.
- No messaging platform is configured and the gateway is stopped, so
  `attended-daidala` has no verified destination or receipt.
- No delivery receipt, remote finding identity, evaluator result, retained
  increment, or version comparison exists yet.
- Incremental graph updates parsed all 26 changed and dependent files without
  errors; the post-commit hook rebuilt the 1,079-row FTS index. Graph test-gap
  counts remain observational and cannot replace the repository gate.

## Redaction statement

This record contains no credentials, connection strings, profile dumps, private
Kanban records, or raw unbounded logs. Future evidence must use redacted,
content-addressed references and preserve only the bounded fields required by
the protocol.
