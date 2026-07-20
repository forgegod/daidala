# Daidala self-improvement evaluation v1

## Record status

Phases 1 through 4D are complete. The post-install clean-checkout live report
passes all eleven stable `SI-*` checks with repository and detached controller
revision `311fcae39e4d1e6505b38c015792008315f64e95`. The operator approved
UC-01 on 2026-07-20.

UC-01 remains blocked before mutation. The committed detached controller now
exposes the production GitHub intake/claim and attended notification adapters
through dry-run-first `project-cycle admit`; registration v2 binds the approved
private destination profile-locally. No controlled issue exists, so preview and
apply have not run. Generic `daidala start` is not project admission. No issue,
claim, cycle, workflow, card, worktree, evaluator, or model call occurred.

This document is not evidence that the loop works end to end.

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
`tests/test_evaluation.py`, `tests/test_live_adapters.py`,
`tests/test_project_cycles.py`, and `tests/test_increments.py`. The current source
gate passes 356 tests, Ruff, Lefthook validation, both pack validations, and
Markdown links, build, Twine, release-content, wheel-member, and diff checks.
Live cycle rows stay `not-run` until their own gate.

## Use-case records

### UC-01 — approval-gated bug fix and recovery

Status: `blocked`. The operator approved UC-01 on 2026-07-20, the exact detached
admission controller is installed, registration v2 is migrated, and all eleven
post-install live prerequisite checks pass. A separately approved controlled
issue, dry-run inspection, and apply approval remain outstanding. The temporary
calculator fixture, both pack runs, exact plan gate, failed verification
preservation, and unchanged target checkout remain unexercised.

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
- Operational admission checkpoint and installed controller:
  `311fcae39e4d1e6505b38c015792008315f64e95`.
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
- Native command discovery exposes `project-cycle admit`; registration v2 and
  approved-controller evidence validate with mode-`0600` profile-local files.
  The private destination is omitted from this record.
- No issue, claim, admission, workflow, card, worktree, evaluator result,
  retained increment, or version comparison was created by the approved attempt.

## Redaction statement

This record contains no credentials, connection strings, profile dumps, private
Kanban records, or raw unbounded logs. Future evidence must use redacted,
content-addressed references and preserve only the bounded fields required by
the protocol.
