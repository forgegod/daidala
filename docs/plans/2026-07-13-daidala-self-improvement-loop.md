# Daidala self-improvement dogfood instance

## Parent contract

This plan instantiates the reusable
[project self-improvement protocol](2026-07-13-self-improvement-loop.md) for
`forgegod/daidala`. The parent plan is binding for project admission, authority,
isolation, cycle identity, approval, evidence, comparison, recovery, adapters,
archival, generic edge cases, and stop conditions.

This document owns only Daidala-specific configuration, backlog conventions,
use cases, evaluation cases, artifacts, implementation sequencing, and approval
gates. If the documents conflict, the safer or more restrictive requirement
controls until both plans are corrected.

## Goal

Use Daidala as the first registered project to prove that the generic loop can:

- detect regressions before a Daidala release;
- compare Daidala against a candidate Hermes Agent release without modifying the
  active runtime;
- improve Daidala code, tests, documentation, packs, or bundled skills through
  its own exact-approval lifecycle;
- preserve reproducible evidence and actionable GitHub findings; and
- retain only measured improvements that preserve all existing policy gates.

The persistent controller stays on the last-known-good Daidala and Hermes
combination. Candidate code and host versions load only in fresh evaluators.
The system never asks a candidate Daidala plugin to replace the plugin already
loaded by the controller gateway.

## Execution status

**Status:** Phase 5A evidence reconciliation is complete with an
`incomparable` cross-pack outcome. Phase 5B is complete: two separately approved
cron executions converged on one claim, cycle, graph, and attended receipt, and
the no-agent job is paused again. Exact detached controller revision `550671c`
was used for the Phase 5B closeout. Separately approved cancellation closed issue
#4 not planned, archived both cards, retained receipt `telegram:37`, converged on
replay, and returned native and standalone live diagnosis to 11/11. Phase 5B-C
is complete.
Phase 5C retained controller-revision evidence, installed exact detached
controller `9d9f4f6`, closed issue #5 completed with receipt `telegram:44`, and
returned both diagnosis routes to 11/11.
Phase 5C-R is complete. Separately approved Increment A/B retention,
installation, controlled probes, terminal cleanup, and finding reconciliation
retain `TC-F06-01` and `TC-F07-01` as `pass`. Issues
[#6](https://github.com/forgegod/daidala/issues/6) and
[#7](https://github.com/forgegod/daidala/issues/7) are closed `completed` and
`Done`; exact detached controller `2595bf5` and rollback `9f380a6` are clean,
reconciliation remains paused, and native plus standalone diagnosis pass 11/11.
Phase 5D is in progress through its ranged paired-evaluation child plan. Phase 0
is complete with 416 tests and the complete repository/release gate passing. The
operator approved the pinned Addyosmani-versus-Aidlc comparison and canonical
`importlib.resources` migration fixture. Child Phase 1 froze exact packet
`c0cdfefb` and installed detached controller `3ce1bfc`. The first control cycle
was canceled at `e606f24c` before plan approval because its definition could not
read the packet from detached baseline `3ce1bfc`; issue #9 is closed not planned,
issue #10 remains unready, and diagnosis is 11/11. Remediation packet `eb02da7c`
was installed at its exact profile-local path, but replacement issue #11 was
canceled at `fc865175` when planning proved baseline `3ce1bfc` lacked the fixture.
Dedicated fixture baseline `c53ba52` now passes the frozen behavior and repository
gates; packet v3 `7139cf3e` binds it. Distribution, intake mutation, readiness,
replacement cycle, plan, cleanup, retention, publication, push, release, and
promotion remain gated.
The resumable execution record is saved in
[`2026-07-20-daidala-phase-5b-paused-reconciliation-cron.md`](2026-07-20-daidala-phase-5b-paused-reconciliation-cron.md).
The two failed Phase 5C control cases are explicit follow-up actions in
[`2026-07-21-daidala-control-plane-findings-remediation.md`](2026-07-21-daidala-control-plane-findings-remediation.md).
Phase 5D execution is ranged in
[`2026-07-21-daidala-phase-5d-uc03-pack-evaluation.md`](2026-07-21-daidala-phase-5d-uc03-pack-evaluation.md).

| Phase | Status | Evidence |
|---|---|---|
| 1 — Daidala fixture and deterministic foundation | done | Manifest, constraints, issue form, strict identities, fake-adapter records, and F01-F18 cases are repository-tested. |
| 2 — Controller coordination and adapters | done | Replay-safe coordination, normalized adapter contracts, and fake-boundary regressions are repository-tested. |
| 3 — Prerequisite doctor and setup confirmation | done | The read-only prerequisite report, credential-binding contract, and setup confirmation rules are repository-tested. |
| 4A — Controller and shared-board bootstrap | done | The controller profile and shared board remain valid; approved detached controller revision `80dd73efa9a4e462304b71ba157b5e5c0172b793` is clean and both packs validate. |
| 4B — GitHub projection and static registration | done | Project 1 is repository-linked with all required fields, all exact labels exist, optional attended auto-add is enabled, and strict registration plus non-secret bindings parse. |
| 4C — Capability and isolation receipts | done | Runtime read/write probes, attended Telegram delivery, controlled findings write, and restricted-container isolation receipts are retained as strict non-secret evidence. |
| 4D — Live prerequisite gate | done | Native and standalone `doctor --live` report all eleven `SI-*` checks as `pass`, including `SI-ACTIVE-CYCLE`, with controller revision `80dd73efa9a4e462304b71ba157b5e5c0172b793`. |
| 4E prerequisite — Operational admission and completion paths | done | Dry-run-first admission and completion, exact digest gates, replay-safe issue closure, claim release, attended notification, immutable receipts, and completion-aware active ownership are installed and exercised. |
| 4E — Addyosmani UC-01 live evaluation | done | Cycle `cycle-21158b4320bf09968915110abdfeb32ac2a0c833acfe90a99bf340936c148f55` reached accepted evidence-only delivery and completion; issue #2 is closed as completed and the claim is released. |
| 4F-A — Aidlc intake rescope and fresh preview | done | Issue #3 authorized the full Aidlc lifecycle; final fresh preview identity `cycle-98afe833a63afdbfce7a16bcd9741d4475e46cfb47013c2982cbe3ad04653c26` and intake digest `377e2976bd1f5998a5bfc9b1c9df92aed53232099f4769330191a72fda8d4b1a` were retained without mutation and explicitly approved. |
| 4F-B — Aidlc admission and plan gate | done | Exact admission and replay converged with attended receipt `telegram:21`; definition and planning stopped at approved plan digest `22a1a91ce4a0872296020d3744714be4252187462f34bc4cd1e482f1d583986c`. |
| 4F-C — Aidlc execution and evidence-only delivery | done | Restricted baseline `80bb8cf7` failed with `1 != 2`; candidate `6f97e6d2` passed both approved tests; review returned `improved`; delivery recorded commit/push false and released worktree ownership. |
| 4F-D — Aidlc terminal completion | done | Completion digest `250756b4021b92e7b9ef74214febfab1d5891baf908ca3650acb473505eb1101` closed issue #3, released its claim, delivered `telegram:23`, converged on replay, and returned doctor to 11/11. |
| 5A — UC-01 evidence reconciliation | done | All retained plan, baseline, candidate, review, delivery, and completion hashes match; both workflows are terminal, but different repository baselines and candidate test fixtures make pack comparison `incomparable`. |
| 5B — Paused reconciliation cron and controlled tick | done | Two approved executions produced `admitted` then `replayed` for one issue, claim, cycle, graph, and attended receipt. The no-agent job is paused on `every 15m`; no worktree, approval, commit, or push exists. |
| 5B-C — Deterministic probe cancellation | done | Exact detached revision `550671c`, approved preview `9deb8cef`, terminal digest `99fe86b3`, receipt `telegram:37`, identical replay, archived cards, and 11/11 diagnosis prove deterministic closeout. |
| 5C — Approved improvement and findings synchronization | done | Issue #5 retained strict v2 controller-revision evidence; completion `f9f5566e` released the claim and delivered `telegram:44`. The two control findings were ranged into Phase 5C-R. |
| 5C-R — Control-plane findings remediation | done | Exact controller `2595bf5`; `TC-F06-01`/`TC-F07-01` retained as `pass`; issues #6/#7 closed completed and `Done`; probe manifests `0db444d6`/`5a79e2fa`; cron paused; diagnosis 11/11. |
| 5D — UC-03 pack evaluation | in-progress ([child plan](2026-07-21-daidala-phase-5d-uc03-pack-evaluation.md)) | Control attempts canceled at `e606f24c`/`fc865175` without implementation; clean fixture baseline `c53ba52` and packet v3 `7139cf3e` are prepared; issue #10 is unready, diagnosis is 11/11, and replacement live mutations remain gated. |
| 6 — Version-aware re-evaluation | blocked | Requires the Phase 5D child closeout; candidate Hermes identity is selected here, not invented earlier. |
| 7 — Repository gate and documentation | blocked | Requires the preceding live evaluation and comparison evidence. |

Mark a phase `in-progress` while running it, `done` only after its gate passes
with exact evidence, `pending` when it is next but unstarted, and `blocked` when
a named prerequisite is incomplete.

## Current operational state

- The persistent controller loads clean detached revision
  `2595bf5f8aacdd1411c101250acc2d0211eaf22a`; protected prerequisite and paused
  cron evidence record the same revision. Clean rollback revisions `9f380a6`,
  `9d9f4f6`, and `550671c`, plus recovery revision `31331e8`, remain outside the
  plugin scan root.
- Addyosmani cycle
  `cycle-21158b4320bf09968915110abdfeb32ac2a0c833acfe90a99bf340936c148f55`
  retains accepted review and evidence-only delivery with commit and push false.
- Completion digest
  `56ba5dced96190df7325bad48ae8fbcf0e324db04f1e606189b00b4fe286998d`
  closed issue #2 as completed, removed only `daidala-si:claimed`, delivered
  attended receipt `telegram:20`, and converged identically on replay.
- Aidlc cycle
  `cycle-98afe833a63afdbfce7a16bcd9741d4475e46cfb47013c2982cbe3ad04653c26`
  binds baseline `66e3ad03b70a99bffa67c16596b6cd59fc0967d2`, plan digest
  `22a1a91ce4a0872296020d3744714be4252187462f34bc4cd1e482f1d583986c`,
  restricted baseline/candidate evidence `80bb8cf7` / `6f97e6d2`, accepted
  review digest `8bbe5196`, and delivery digest `3647d6c1`.
- Completion digest
  `250756b4021b92e7b9ef74214febfab1d5891baf908ca3650acb473505eb1101`
  closed issue #3 with reason `completed`, removed only
  `daidala-si:claimed`, cleared claim/cycle/workflow Project fields, delivered
  attended receipt `telegram:23`, and converged identically on replay.
- Both UC-01 workflows retain mode-`0600` evidence with commit and push false.
  No owned worktree remains; the registered checkout and main branch remain
  clean, while the immutable Aidlc cycle baseline remains
  `66e3ad03b70a99bffa67c16596b6cd59fc0967d2`.
- Phase 5A recomputed the retained Addyosmani and Aidlc plan, baseline,
  candidate, review, delivery, and completion hashes. Every named file matches
  its content address.
- The restricted image and command agree, but Addyosmani binds repository
  baseline `72ac8c5567358a6ad8fd40baaf37d5a4db17284e` and one candidate test while
  Aidlc binds baseline `66e3ad03b70a99bffa67c16596b6cd59fc0967d2` and two candidate tests. The
  missing canonical fixture prevents a measured pack preference.
- No preferred pack, retained change, cron job, new cycle, or remote finding was
  created during Phase 5A evidence reconciliation.
- Phase 5B created one digest-matched no-agent cron and probe cycle. Controlled
  outcomes were `admitted` then `replayed` with one claim, graph, and attended
  receipt. Before closeout, the plan card remained blocked without approval or a
  worktree; commit and push remain false.
- Phase 5B-C cancellation passed the repository and release gate and was exercised
  at `550671c`. Issue #4 is closed not planned, its active labels are removed,
  both cards are archived, receipt `telegram:37` is retained, diagnosis is 11/11,
  and the cron remains paused.
- Phase 5C cycle
  `cycle-cbbbfd0273b7144cd2475369d14c9b55bd301ffd442728531bcb61db3c71ba18`
  retains implementation `401f3dfe`, completion `f9f5566e`, and receipt
  `telegram:44`. Issue #5 is closed completed, its claim is released, no worktree
  remains, and commit/push in delivery evidence remain false.
- Phase 5C-R approval workflow `tc-f06-direct-approval-probe-v2` retains
  fail-closed worker envelope `1f4a99ec`, zero-mutation comparison `217d8b9d`,
  post-approval graph verification `5d9491c3`, and final manifest `0db444d6`.
- Artifact workflow `tc-f07-revision-artifact-probe-v1` retains replay comparison
  `1032386d`, conflict envelope `91a4efad`, five historical artifact references,
  terminal system evidence `e9224f67`, and cleanup manifest `5a79e2fa`.
- Both workflows were separately cancelled and cleaned up before gateway
  restoration. Issues #6 and #7 are closed `completed` and `Done`; diagnosis is
  11/11, no active cycle or owned worktree exists, and the cron remains paused.

## Registered project

The first committed project manifest is `.daidala/project.yaml` with:

- project ID `forgegod-daidala`;
- canonical GitHub repository `forgegod/daidala`;
- exact verified `origin` identity;
- allowed packs `addyosmani` and `aidlc` with their packaged source revisions
  and content digests;
- `addyosmani` as the default pack for the first vertical slice;
- workflow constraints sourced from an explicit project file or exact installed
  policy skill;
- the repository gate from `/AGENTS.md`;
- protected controller, registration, runtime-state, credential, generated
  workspace, and evidence paths;
- release, push, merge, publication, and deployment disabled by default; and
- maintainer approval required for admission, implementation, retention, and
  publication.

The manifest is untrusted input and is snapshotted per cycle. It cannot grant
credentials or mutate the local controller registration.

The trusted local registration uses:

- controller profile: `daidala-self-improvement`;
- board: `daidala-forgegod-daidala`;
- checkout: the verified absolute local `forgegod/daidala` repository;
- dedicated least-privilege GitHub intake/findings credential aliases;
- one attended Hermes gateway target alias;
- a fresh evaluator home and process per run;
- a restricted evaluator backend where the selected case requires filesystem or
  network isolation; and
- one active cycle globally.

The profile is never made the user's sticky default. Board isolation is not
reported as execution isolation. Existing user profiles, boards, browser
profiles, repositories, credentials, and private Kanban databases are outside
scope.

## Workflow packs and constraints

Both bundled packs use the existing pack-neutral lifecycle:

```text
define -> plan -> exact human gate -> implement -> verify -> review -> deliver
```

- `addyosmani` maps external pinned skills from
  `addyosmani/agent-skills`.
- `aidlc` maps the packaged `daidala:aidlc-adapter` skill.
- Every executable card pins `daidala:orchestrate` and the complete exact
  pack-stage candidate set.
- Required and conditional activation remain governed by
  `daidala.skill-activation/v1`.
- Constraints remain separate from pack methodology and bind the exact approval
  tuple.

The first controlled evaluation runs the same fixture as two independent
workflows, one per pack. A pack comparison never silently updates
`.daidala/project.yaml`, the controller profile, or installed controller skills.

## GitHub Issues adapter

GitHub Issues is the initial intake and findings adapter. Versioned experiment
records are evidence authority; issues are work items linking to that evidence.
A dedicated GitHub Project may provide a human queue view but is never queue or
execution authority.

### Repository setup

Setup must idempotently create and verify:

- `.github/ISSUE_TEMPLATE/daidala-self-improvement.yml`;
- base label `daidala-si`;
- admission label `daidala-si:ready`;
- claim label `daidala-si:claimed`;
- blocked label `daidala-si:blocked`;
- exactly one category label from:
  `daidala-si:regression`, `daidala-si:improvement`,
  `daidala-si:compatibility`, `daidala-si:skill-gap`, and
  `daidala-si:research-candidate`;
- one priority label from `daidala-si:priority-1` through
  `daidala-si:priority-5`; and
- a dedicated GitHub Project with an auto-add view for `daidala-si` issues.

Project membership is presentation only. An issue becomes eligible only when an
authorized maintainer separately applies `daidala-si:ready` and its structured
body validates.

### Intake shape

An eligible issue contains:

- observable title and one namespaced category;
- originating experiment, test-case, or external source identity;
- affected Daidala and Hermes versions where known;
- expected and observed behavior;
- redacted evidence reference and digest;
- acceptance criteria;
- dependencies and risk;
- priority; and
- publication state.

Ordinary issues are never inferred to be loop items from title or prose. Unknown,
missing, contradictory, oversized, or stale fields fail closed rather than being
repaired with model judgment.

Selection records `daidala-si:claimed`, cycle and workflow IDs, claim timestamp,
and lease expiry. Replay converges through deterministic cycle identity. A stale
claim returns to ready only after the Daidala ledger and project board prove no
active owner exists.

### Findings and publication

Create or update a finding only for an actionable, reproducible result that
cannot be completed safely inside the currently approved improvement. Search
open and closed issues for the same stable finding identity first. Do not create
issues for speculation, passing observations, duplicates, or generated noise.

The loop may create `daidala-si` findings but never applies
`daidala-si:ready` to its own finding. A maintainer admits it separately.

A local finding may be `publication: pending`. Commit, push, and pull-request
creation remain separately approved. An issue changes to
`publication: published` only after a returned commit or pull-request URL is
verified. GitHub failure preserves local evidence and marks synchronization
pending; no remote identity is fabricated.

The GitHub mutation credential is fine-grained for issue read/write and
repository contents read. It has no contents write, merge, release, deployment,
webhook administration, or repository administration capability. Evaluators do
not receive it.

## Controller lifecycle

The first cycle is manual and observed through the exact plan gate. Only after
that cycle and replay recovery pass may the controller own one paused
reconciliation cron job. A controlled tick:

1. verifies controller profile, board, gateway, notification target, repository,
   registration, credential capability, and last-known-good runtime;
2. confirms no cycle is active;
3. queries only structured, maintainer-ready issues from `forgegod/daidala`;
4. validates or recovers claim leases;
5. selects at most one item;
6. starts one deterministic Daidala cycle and workflow; and
7. sends a verifiable notification naming all inspection identities.

The reconciliation cron is a deterministic `--no-agent` script, so it has no
provider or model identity and a global model change cannot alter the tick. Its
unattended identities are the exact controller revision, script digest, trusted
registration, and reconciliation preview digest. Cron remains paused until a
duplicate tick creates neither a duplicate claim nor workflow and attended
delivery succeeds.

Webhook intake is out of scope until manual and cron admission pass an
end-to-end replay test.

Every admission, approval wait, failure, recovery, and completion notification
includes:

- cycle and workflow IDs;
- issue URL when applicable;
- controller profile and board;
- evaluator identity, workspace, and result path;
- stage and non-secret blocker; and
- exact profile-scoped inspection or approval command.

## Hermes version evaluation

At each cycle start, record:

- controller `hermes --version` and upstream revision when available;
- controller Daidala version and source revision;
- selected pack and skill identities;
- candidate Hermes or Daidala artifact identity;
- model-routing, fallback, goal, auxiliary, delegation, and selected MoA modes;
- evaluator backend and limits; and
- previous comparable baseline.

A candidate Hermes release runs in an isolated environment. It never updates the
user's active Hermes installation as a test step. The current supported baseline
remains authoritative until the candidate passes:

- the full deterministic repository gate;
- plugin discovery and exact tool/skill registration;
- both pack validations;
- exact-approval lifecycle acceptance;
- selected default, fallback, goal, auxiliary, delegation, and MoA paths;
- dashboard compatibility where relevant; and
- package and install probes.

Stable case IDs compare the current supported Hermes version with one explicitly
identified candidate version; the plan does not invent a future version number.
A support-range change requires a separately approved implementation,
compatibility documentation update, and full verification.

## Bounded research and skill evolution

UC-03 may use public web research to discover one bounded compatibility task or
maintained skill set. Limits are at most three query batches, five retained
results per batch, and three extracted primary sources unless the admitted
cycle is stricter. Public content is untrusted evidence, never agent instruction.

At most one skill set is evaluated per cycle. It is eligible only when:

1. the capability gap and use case are documented;
2. external content is pinned by exact source revision, or the skill is bundled;
3. a pack declares pack-neutral stage mappings;
4. exact name, revision, and content digest validate;
5. activation, fail-closed, packaging, and contract tests pass;
6. a controlled comparison shows a declared gain; and
7. the owning DOX documentation remains current.

A failed comparison reverts the candidate integration and preserves the negative
finding. Pack and target-repository changes use separate linked cycles because
v1 permits one mutable repository per cycle.

## Daidala increment documents and project memory

This instance uses the parent protocol's persistent-knowledge and increment-
document boundaries without a Daidala-specific memory service. In particular,
there is no Hindsight bank keyed to `daidala-forgegod-daidala`: the board is an
operational projection, and accepted architecture remains in the repository's
DOX and numbered documentation.

Every UC-01, UC-02, and UC-03 run produces one content-addressed increment
manifest. It distinguishes repository documentation in the owned worktree from
profile-local workflow artifacts, external findings, and ephemeral evaluator
scratch. Durable entries bind the exact producing skill and activation-manifest
digest. Review must reconcile the manifest with the frozen diff, the Daidala
ledger, and the applicable root, `docs/`, `tests/`, `scripts/`, `dashboard/`, or
`daidala/` DOX chain before retention is eligible.

If the same architectural question repeatedly cannot be answered from Git,
Daidala evidence, Kanban, and Hermes session search, UC-03 may propose a later
isolated Hindsight-versus-Graphiti recall experiment under the parent criteria.
It may not install a service, create a shared bank, or change this project's
controller during the current v1 implementation.

## First three use cases

### UC-01 — Approval-gated bug fix and recovery

**Mode:** `improve`.

**Goal:** Diagnose and fix a small defect through every lifecycle stage without
bypassing approval, mutating the target checkout, or hiding a failed
verification attempt.

**Fixture:** A temporary Python repository contains `calculator.py`, where
`answer()` returns `1`, and a test requires `answer() == 2`. The worker selects
one adjacent regression check after diagnosis. Run the scenario separately for
`addyosmani` and `aidlc`.

**Deterministic coverage:** admission, idempotent graph creation, stage
promotion, exact-digest approval, skill activation, immutable implementation
evidence, verification recovery, review, conservative delivery, and unchanged
target checkout.

**Observational evidence:** competing hypotheses, rationale for the adjacent
check, retry explanation, card clarity, handoff quality, and operator
recommendations.

**Completion:** Both pack runs satisfy the deterministic baseline. At most one
separately approved patch-level improvement is retained when before/after
evidence shows reduced ambiguity, failed work, or resource use without another
regression.

### UC-02 — Changing constraints and candidate release regression

**Modes:** `improve` followed by `regress`.

**Goal:** Implement a multi-file feature after a semantic constraint change
invalidates the original plan, then compare the resulting candidate Daidala
artifact against the last-known-good Hermes/Daidala baseline.

**Fixture:** Extend a temporary calculator library with checked division,
public API documentation, and normal and divide-by-zero tests. After the first
plan, replace constraints to require an exact verification command and prohibit
one proposed implementation path. Exercise a formatting-only replacement as a
separate no-op.

**Deterministic coverage:** setup preview, stale-digest rejection, semantic
invalidation, new card graph, worktree scope, status and recommendations,
dashboard projection, candidate plugin loading in a fresh process, and bounded
Hermes execution.

**Observational evidence:** explanation of stale-plan ineligibility, regenerated
rather than patched stale work, one CLI observation, and one dedicated-debug-
browser observation.

**Completion:** The feature passes under current constraints; stale work remains
ineligible; CLI, dashboard, and evaluator evidence agree; the active controller
runtime is unchanged; and any retained improvement passes the complete baseline.

### UC-03 — Pack and skill compatibility evaluation

**Mode:** `evaluate-pack`, with a later `improve` cycle only if promotion is
approved.

**Goal:** Select one externally grounded software-development task, evaluate
Daidala compatibility, and determine whether one pack-integrated skill set
measurably improves the result.

**Candidate categories:** behavior-preserving refactoring, test authoring,
dependency or API migration, packaging compatibility, and documentation-linked
implementation. Human approval selects the fixture before execution.

**Coverage:** pack and source compatibility, provenance, activation, isolated
implementation, review and delivery, packaging, model execution, and comparison
against the same goal, fixture, routing configuration, and limits.

**Completion:** Retain no project default automatically. A candidate becomes a
separate improvement proposal only when it improves a declared result without
weakening fail-closed behavior, packaging, or UC-01/UC-02. Otherwise preserve
the negative finding and synchronize an issue when actionable.

## Atomic evaluation matrix

Implementation expands every area into stable `TC-Fxx-nn` cases. Positive and
fail-closed outcomes are separate cases; pack-dependent results remain visible.

| Area | Required observable goals |
|---|---|
| F01 project and registration | Manifest snapshots validate; remote, profile, board, credential aliases, notification target, and evaluator backend match trusted registration. |
| F02 packs and provenance | Both packs load; exact mappings and supported host boundaries validate; missing or drifted skills fail closed. |
| F03 CLI and tools | Standalone and native surfaces agree; exactly declared JSON tools register; invalid arguments do not mutate state. |
| F04 setup and admission | Preview is non-mutating; literal confirmation is required; start is idempotent; no implementation card exists before approval. |
| F05 definition and planning | Workers record activation, artifacts, and handoffs; plan completion exposes the ledger-owned pending approval action without creating an executable approval task. |
| F06 approval | Wrong or stale digest fails; generic unblock is not approval; exact approval creates one owned worktree and post-gate graph. |
| F07 constraints | Canonical parsing and compare-and-swap hold; formatting-only replacement is a no-op; semantic replacement invalidates stale identity and work. |
| F08 implementation and verification | Work occurs only in the owned worktree; changed paths and evidence are immutable; same-card recovery remains possible. |
| F09 review and delivery | Review cannot mutate captured scope; delivery does not commit or push and removes only owned state. |
| F10 status, cancellation, and dashboard | Status reads live Kanban without mirroring; cancellation is ownership-safe; dashboard unavailable states do not invent data. |
| F11 packaging and host compatibility | Wheel and directory installs expose code, packs, skills, tools, and dashboard assets without runtime state or secrets. |
| F12 Hermes execution | Default, fallback, selected MoA, goal, auxiliary, and delegation paths remain Hermes-owned and bounded. |
| F13 issue feedback | Structured findings deduplicate and return verifiable identities; only maintainer-ready issues seed a claimed cycle; offline states recover. |
| F14 version comparison | Stable cases compare exact Daidala and Hermes identities; support-range changes remain separately approved. |
| F15 controller and evaluator isolation | Persistent controller stays last-known-good; fresh evaluators cannot mutate controller control material or reuse its loaded candidate plugin. |
| F16 reconciliation | Duplicate ticks converge; expired claims require ledger and board proof; dirty worktrees quarantine; missing boards block. |
| F17 metric comparison | Deterministic, repeated, and observational metrics follow the parent contract; missing or noisy evidence produces `incomparable`. |
| F18 increment documents and memory boundary | Every durable skill-produced document has manifest, producer, activation, digest, revision, retention, and DOX provenance; scratch cannot become evidence; no semantic-memory service is required for a deterministic result. |

Each case records goal, preconditions, exact procedure, expected result,
prohibited side effects, observed result, status, and redacted evidence. Statuses
are `pass`, `fail`, `blocked`, and `not-run`.

## Planned repository artifacts

```text
.daidala/project.yaml
.daidala/constraints.yaml
.github/ISSUE_TEMPLATE/daidala-self-improvement.yml
tests/test_self_improvement_loop.py
docs/evaluation-results/AGENTS.md
docs/evaluation-results/v1/experiment-limits.yaml
docs/evaluation-results/v1/daidala-self-improvement.md
docs/15-self-improvement.md
```

`experiment-limits.yaml` contains only goal, worker, research, time, and system-
boundary limits. It does not copy model/provider credentials or duplicate
Hermes configuration. The result document contains the case matrix, use-case
records, timeline, version comparison, identities, receipts, findings, blockers,
and redaction statement.

The advanced tutorial is indexed in `docs/README.md` only after its commands are
exercised against the supported Hermes version. The normal first-workflow path
in `docs/00-getting-started.md` remains unchanged.

## Comprehensive Daidala flow documentation

This instance must complete the `forgegod/daidala` sections of
`docs/15-self-improvement.md`; a filename in the artifact list is not sufficient.
The generic plan defines the complete protocol-level contents and verification.
The Daidala instance contribution must additionally document:

- the concrete controller profile `daidala-self-improvement`, board
  `daidala-forgegod-daidala`, committed manifest, trusted registration, gateway,
  paused cron, evaluator, worktree, and evidence locations;
- a Mermaid sequence diagram from one `daidala-si:ready` issue through claim,
  manifest snapshot, baseline, Daidala card graph, approval wait, evaluator,
  comparison, finding synchronization, notification, and claim release;
- a separate controller-cron reconciliation diagram covering duplicate tick,
  active-cycle, expired-lease, GitHub outage, missing-board, and delivery-failure
  branches;
- the exact mapping between GitHub issue state, Daidala policy-ledger facts,
  Hermes Kanban state, evaluator records, and versioned evidence, explicitly
  identifying which projection is authoritative for each fact;
- the instance approval tuple with concrete examples for plan replacement,
  constraint replacement, manifest change, pack change, baseline change,
  candidate Daidala change, and candidate Hermes change;
- step-by-step technical walkthroughs of UC-01, UC-02, and UC-03, linked to their
  `TC-Fxx-nn` cases, expected artifacts, prohibited side effects, recovery paths,
  and completion decisions;
- the Addyosmani and AI-DLC activation and handoff flow without introducing
  pack-name branches in the engine;
- the last-known-good controller versus candidate evaluator loading boundary,
  including promotion and rollback of a candidate Daidala or Hermes version;
- the concrete increment-document manifest and reconciliation flow, including
  examples of repository documentation, workflow artifacts, findings, and
  discarded scratch output;
- the DOX, Git, Daidala ledger, Kanban, session-search, and optional future
  semantic-recall authority boundaries;
- GitHub label and structured-body validation, stable finding identity,
  deduplication, pending publication, returned URL verification, and
  least-privilege credential flow;
- notification payload and receipt examples for admission, approval, blocked,
  failure, recovery, and completion; and
- exercised setup, first run, status, approval, recovery, pause/resume, upgrade,
  archival, and teardown commands, with unsupported or unexercised paths clearly
  labeled.

The document must cross-reference `02-workflow-state.md`,
`03-pack-reference.md`, `05-lifecycle-stages.md`, `06-security.md`,
`08-hermes-integration.md`, and `14-workflow-constraints.md`. It must show
Daidala as a plugin inside the existing Hermes process, never as an independent
controller service. The corresponding versioned result document records what
actually happened; `docs/15-self-improvement.md` explains the reusable and
concrete technical flow and must not fabricate live evidence.

## Implementation phases

### Phase 1 — Daidala project fixture and deterministic foundation

- Implement the parent protocol's Phase 1 models and tests through the Daidala
  project manifest as the first vertical slice.
- Materialize F01-F18 with stable case IDs, including F18's fail-closed producer,
  digest, promotion, retention, mutable-path, and DOX-reconciliation cases.
- Add the Daidala manifest, constraints fixture, result-directory DOX contract,
  limits schema, and result template.
- Add fake GitHub adapter tests for labels, structured bodies, readiness, claim
  leases, deduplication, publication state, and notification payloads.
- Draft the advanced tutorial without indexing unexercised commands.
- Add the Daidala topology, GitHub issue/claim sequence, cron reconciliation,
  UC-01/UC-02/UC-03 walkthroughs, version-promotion boundary, and case links to
  the planned comprehensive technical flow document. Keep live commands marked
  unexercised.

Gate: focused tests, Ruff, Markdown links, and DOX reconciliation pass. No branch,
profile, board, GitHub object, live model, evaluator, or browser is created by
approval of this document alone.

### Phase 2 — Controller coordination and adapters

Repository coordination and fake-adapter tests are implemented and verified.
The operator checklist is
[`../16-self-improvement-setup.md`](../16-self-improvement-setup.md).

- Finish project admission, immutable manifest snapshots, deterministic
  cycle/workflow/baseline binding, canonical constraint and stage-profile replay
  identity, replay-safe claims, pending finding synchronization, strict adapter
  serialization, and event-bound receipt validation.
- Keep concrete profile, board, gateway, GitHub, credential, evaluator, and live
  cycle mutation outside this repository-only phase.

Gate: duplicate admissions and adapter retries converge; malformed external data
fails before board or repository mutation; focused and repository tests, Ruff,
Markdown links, and DOX pass.

### Phase 3 — Prerequisite doctor and setup confirmation

- Implement the parent protocol's checklist-driven `doctor` extension using the
  stable check IDs and remediation sections in
  [`../16-self-improvement-setup.md`](../16-self-improvement-setup.md).
- Keep the guide normative and require exact guide/CLI check-ID parity in tests.
- Add explicit profile-local environment bindings for the two GitHub aliases;
  matching Bitwarden/KeePass entry names are not implicit bindings and Daidala
  does not invoke personal password-manager CLIs.
- Support the same JSON and exit-code behavior through standalone `daidala` and
  native `hermes daidala` entry points.
- Exercise a non-mutating live run against the current environment. Existing
  Docker, GitHub Project, credential-alias, and gateway gaps must be reported as
  exact blockers rather than repaired or treated as success.

Gate: every ready-to-admit row is represented exactly once; the command leaks no
secret or private destination data; no profile, board, gateway, GitHub,
repository, evaluator, or admission state changes; and the report gives the
operator one complete confirmation of passes and omissions.

### Phase 4A — Controller and shared-board bootstrap

- Require a current Phase 3 prerequisite report before setup. A report is
  advisory evidence, not setup approval or cycle approval.
- Install the controller plugin from the exact approved committed revision using
  verified GitHub installation or a detached local clone. A mutable symlink,
  editable checkout, uncommitted tree, or mismatched remote head fails setup.
- After separate setup approval, create the controller profile and board without
  changing the sticky default.
- Validate the exact detached plugin, packs, installation-global board identity,
  unchanged current board, and unchanged sticky profile.

Gate: plugin and board checks pass without admitting a cycle.

### Phase 4B — GitHub projection and static registration

- Idempotently create and verify labels, issue template, repository link, and
  Project fields through the public `gh` CLI.
- Keep built-in Project auto-add as optional attended UI presentation because
  GitHub exposes no public create/update workflow mutation.
- Materialize strict profile-local registration and non-secret environment
  bindings without capability receipts or token values.

Gate: remote identities read back exactly and both static files parse.

### Phase 4C — Capability and isolation receipts

- Replace invalid or insufficient runtime credentials and prove the exact
  read-only intake and issue-only findings boundaries.
- Produce an attended gateway delivery receipt through the registered adapter.
- Implement and exercise the restricted-container boundary with a pinned image,
  denied network, fresh home, absent controller credentials, and bounded mounts.
- Write prerequisite evidence only from those returned identities and receipts.

Gate: credential, notification, evaluator, controller, board, pack, repository,
and Project checks pass without cycle admission.

### Phase 4D — Live prerequisite gate

- Run `daidala doctor --live` from the clean registered checkout.
- Stop on any blocked, not-run, or error row; never edit evidence merely to make
  the checker green.

Gate: all eleven `SI-*` rows pass with the exact retained evidence.

### Phase 4E prerequisite — Operational admission path

The installed controller now provides shared native/standalone dry-run-first
`project-cycle admit` and `project-cycle complete` dispatch. Admission apply
requires the exact cycle ID and canonical intake digest from a fresh preview.
Completion apply requires the exact delivered cycle ID and completion preview
digest. Both paths recompute live identities before mutation, retain mode-`0600`
receipts, and converge on replay. Generic `daidala start`, manual issue closure,
and manual claim-label removal remain prohibited substitutes.

Gate: exercised Addyosmani admission and completion prove preview immutability,
exact apply gates, recoverable claims, attended receipts, terminal claim release,
completion-aware active ownership, and replay convergence through production
adapters.

### Phase 4E — Addyosmani UC-01 live evaluation

The Addyosmani run is terminal. Its exact approved plan revision produced one
owned worktree, diagnostic failing baseline, passing restricted-container
candidate, `improved` comparison, accepted review, and evidence-only delivery.
Delivery recorded `committed: false` and `pushed: false`; worktree ownership was
released before completion. Issue #2 is closed with reason `completed`, only its
claim label was removed, immutable admission/workflow/evaluator evidence remains,
and exact completion replay created no duplicate comment or notification.

Gate: completion digest
`56ba5dced96190df7325bad48ae8fbcf0e324db04f1e606189b00b4fe286998d`,
attended receipt `telegram:20`, one unchanged claim comment, retained mode-`0600`
completion artifacts, and post-completion doctor 11/11 agree while the registered
checkout remains unchanged.

### Phase 4F-A — Aidlc intake rescope and fresh preview

**Goal:** Convert issue #3 from a preview-only control into the separately
approved Aidlc UC-01 execution intake without admitting it.

Observed gate: steps 1-7 passed for final workflow identity
`cycle-98afe833a63afdbfce7a16bcd9741d4475e46cfb47013c2982cbe3ad04653c26`
and intake digest
`377e2976bd1f5998a5bfc9b1c9df92aed53232099f4769330191a72fda8d4b1a`.
Protected final-preview verification SHA-256 is
`5188982c6bdb94c2f6dd82afe02fb70e066ad8f0f95c206121a1e904ddf2deba`.

Steps:

1. Snapshot issue #3, its GitHub Project item, open admissions, policy-ledger
   hash, workflow directories, controller revision, and registered checkout.
2. Obtain explicit approval for the exact issue title, structured body, labels,
   and Project projection before any GitHub write.
3. Replace preview-only wording with the full Aidlc UC-01 lifecycle criteria:
   exact admission gate, plan-digest gate, restricted diagnostic baseline,
   bounded candidate, accepted review, evidence-only delivery, completion, and
   claim release. Do not change category, priority, evidence provenance, or
   repository target silently.
4. Keep `daidala-si:ready`; require zero claim comments, no claimed label, and
   empty claim/cycle/workflow Project fields before preview.
5. Run `project-cycle admit` without `--apply`, pin pack `aidlc`, and retain the
   complete bounded preview at mode `0600`.
6. Prove the issue, Project item, policy ledger, admissions, Kanban, checkout,
   worktrees, and evaluator artifacts are unchanged by preview and identical
   preview replay.
7. Stop for explicit approval of the new exact cycle ID and intake digest. The
   prior preview identity `cycle-a5acefda9b2c85f63a1b447fb1deb6e095f0c5f49441fe39f574c582d249cff4`
   and intake digest
   `1c761c6367cfc8a05598acbfb966e8d1183e05bd5df8f9355227d73764538e07`
   are stale immediately after the issue changes and must never be applied.

Verification gate: the revised issue validates as Aidlc UC-01 input; two fresh
previews are byte-identical; all before/after no-mutation snapshots agree; no
claim or workflow exists; and the operator has approved the exact new cycle ID
and intake digest.

### Phase 4F-B — Aidlc admission and plan gate

**Goal:** Admit exactly the approved Aidlc preview and stop before implementation.

Steps:

1. Re-run live doctor and the admission preview immediately before apply; reject
   any changed issue, manifest, registration, baseline, constraints, pack,
   controller, stage profile, cycle ID, or intake digest.
2. Apply once with the approved exact cycle ID and intake digest, then verify one
   recoverable claim, one immutable admission, one event-bound notification, and
   one workflow through the blocked plan-approval card.
3. Replay the exact apply; require identical admission and receipt identities,
   one claim comment, no duplicate workflow/cards/notification, and no unrelated
   Project or repository mutation.
4. Run definition and planning through the Aidlc pack. The plan must use an
   image-internal Python/pytest path, name the diagnostic failing baseline, set
   the comparison pass condition to `improved`, and bind the exact current
   baseline, constraints, pack, stage profiles, and evaluator policy.
5. Stop at the exact plan-digest approval gate. Require no implementation card,
   owned worktree, baseline run, or candidate run before that approval.

Verification gate: admission and apply replay converge; issue, claim, admission,
notification, workflow, and current plan identities agree; the approval card is
blocked; and repository/worktree/evaluator state remains untouched.

Observed gate: admission and replay converged with attended receipt
`telegram:21`; one claim and one seven-card workflow were created; definition
and planning stopped before worktree creation at exact plan digest
`22a1a91ce4a0872296020d3744714be4252187462f34bc4cd1e482f1d583986c`.

### Phase 4F-C — Aidlc execution and evidence-only delivery

**Goal:** Exercise the same UC-01 fixture through Aidlc without retaining or
publishing implementation changes.

Steps:

1. Obtain explicit approval of the exact current Aidlc plan digest. Approval
   creates one Daidala-owned worktree and the post-gate card graph.
2. Construct the temporary calculator fixture only inside the owned worktree or
   restricted evaluator; never write it into the registered checkout.
3. Retain the diagnostic baseline where `answer()` is not `2`; run the approved
   focused repair and one adjacent regression check without broadening scope.
4. Run baseline and candidate in the digest-pinned restricted container with
   denied network, fresh home, credential-free environment, and one bounded
   workspace mount. Preserve failed and passing evidence independently.
5. Record the deterministic comparison, verification commands and outputs,
   frozen implementation paths/diff, activation provenance, and increment
   manifest before review.
6. Review frozen scope against the approved plan, constraints, DOX chain, and
   Addyosmani evidence. Record findings or acceptance without changing the
   reviewed artifacts.
7. Deliver evidence only with `committed: false` and `pushed: false`; release the
   owned worktree and prove the registered checkout, main branch, and remote are
   unchanged.

Verification gate: all current post-gate cards are done; restricted baseline and
candidate evidence produce an explicit comparable outcome; review and delivery
are accepted; commit/push are false; worktree ownership is released; and no
retention, publication, or controller promotion occurred.

Observed gate: restricted baseline evidence `80bb8cf7` reproduced `1 != 2`;
candidate evidence `6f97e6d2` passed exactly two tests; review digest `8bbe5196`
accepted the `improved` result; delivery digest `3647d6c1` recorded
`committed: false` and `pushed: false`; the owned worktree was released.

### Phase 4F-D — Aidlc terminal completion

**Goal:** Release Aidlc active ownership while preserving every immutable cycle
artifact for Phase 5 comparison.

Steps:

1. Run and retain a no-mutation completion preview for the exact Aidlc cycle;
   verify accepted review/delivery, passing verification, released worktree,
   commit/push false, exact claim owner, and current issue identity.
2. Stop for explicit approval of the exact Aidlc cycle ID and completion preview
   digest.
3. Apply completion once; require issue #3 closed with reason `completed`, only
   `daidala-si:claimed` removed, one existing claim comment, and matching
   mode-`0600` remote, attended-notification, and final completion receipts.
4. Replay completion; require identical output and receipt hashes with no
   duplicate comment, issue mutation, or notification.
5. Re-run `doctor --live`; require all eleven checks including
   `SI-ACTIVE-CYCLE` to pass.
6. Freeze the Addyosmani and Aidlc UC-01 identities, plans, baseline/candidate
   evidence, comparisons, reviews, deliveries, completions, and operator
   receipts as the Phase 5 input set. Do not select a preferred pack or retain a
   patch in this phase.

Verification gate: issue #3, immutable cycle artifacts, completion replay,
attended receipt, doctor 11/11, checkout state, and the frozen two-pack input set
agree; no commit, push, retention, publication, or third workflow occurred.

Observed gate: completion preview
`905b734fee29f5ac4358e331e6a0fff03c9f6620503a1fae23a5a7f04ee0b2b5`
required recovery commit `31331e8` because the completion schema contradicted
the engine's valid initial plan revision `0`. Exact approved controller revision
`31331e8352208321ae819ad2464396f03207602b` passed 373 tests and two identical
live previews before installation. Completion digest
`250756b4021b92e7b9ef74214febfab1d5891baf908ca3650acb473505eb1101`
then closed issue #3, cleared its claim projection, delivered `telegram:23`,
replayed without mutation, and returned live doctor to 11/11.

### Phase 5 — Reconciliation, findings, and pack evaluation

#### Phase 5A — UC-01 evidence reconciliation

- Recompute the retained Addyosmani and Aidlc UC-01 plan, restricted baseline,
  restricted candidate, review, delivery, and completion hashes.
- Verify independent lifecycle completion, issue closure, claim and worktree
  release, attended receipts, and evidence-only delivery.
- Compare fixture, plan, evaluator, verification, delivery, and repository
  identities before selecting a preferred pack or proposing retention.
- Record `incomparable` rather than inferring a pack effect when any required
  comparison identity differs.
- Update the versioned result record without creating a cron, GitHub mutation,
  new cycle, retained change, publication, or controller promotion.

Observed gate: all twelve primary artifact hashes match and both workflows are
independently terminal. The restricted image, command, changed-path set, baseline
failure, and conservative delivery policy agree. Comparison eligibility fails
because the repository baselines differ and Addyosmani has one candidate test
while Aidlc has the required focused and adjacent tests. No preferred pack is
selected.

#### Phase 5B — Paused reconciliation cron and controlled tick

Detailed execution plan:
[`2026-07-20-daidala-phase-5b-paused-reconciliation-cron.md`](2026-07-20-daidala-phase-5b-paused-reconciliation-cron.md).

- Create the reconciliation cron job paused only after separate approval.
- Run and replay one controlled tick only after separate dispatch approval.
- Keep scheduling disabled until selection, deduplication, recovery, and
  attended notification pass.
- Select at most one structured maintainer-ready issue and create no duplicate
  workflow.

Gate: duplicate ticks converge, failures and approval waits reach the attended
channel, and scheduling remains disabled until separately approved.

#### Phase 5C — Approved improvement and findings synchronization

- Run at most one separately approved improvement and preserve comparable
  baseline/candidate evidence.
- Retain, reject, or revert only from measured results and separate retention
  approval.
- Synchronize actionable findings only after separate publication approval and
  a returned GitHub identity; leave generated issues unready.

Gate: every retained change resolves its cited case without weakening another
gate, and adapter replay creates no duplicate finding.

Observed gate: published issue #5 selected one controller-identity improvement.
Cycle `cycle-cbbbfd0273b7144cd2475369d14c9b55bd301ffd442728531bcb61db3c71ba18`
used approved policy revision 2 and final plan revision 3. Immutable implementation
`401f3dfec2604f5d64a7a605ede17f494644574dc567d755512f86b1c27a93f3`
passed 50 focused and 406 full tests, accepted review, both pack validations, the
complete release gate, and separate retention approval before application to
baseline `106b4f923823e016d33f95c66a826ec55a2bb1e1`. The run also exposed two local
publication-pending control findings: autonomous promotion of a blocked approval
gate and historical artifact-path reuse across revisions. The first completion
preview exposed duplicate successful-output digests; checkpoint `9d9f4f6`
canonicalizes them and produced stable no-mutation preview digest
`a09f3405f8dcd98360186b2373bb8845e7d3cc84ca5a47f214d8d19d80027c8b`.
Separate install and apply approvals produced terminal completion `f9f5566e`,
receipt `telegram:44`, issue #5 closed completed, and 11/11 diagnosis. Push and
release remain separately gated. The control findings were subsequently
published and closed through Phase 5C-R.
The remediation plan completed separately approved source, installation,
controlled evidence, cleanup, and finding closeout for both control cases.
`TC-F06-01` and `TC-F07-01` are retained as `pass`.

#### Phase 5C-R — Control-plane findings remediation

- Execute
  [`2026-07-21-daidala-control-plane-findings-remediation.md`](2026-07-21-daidala-control-plane-findings-remediation.md)
  from its first incomplete phase.
- Keep this parent row `in-progress` while any child phase is incomplete.
- Apply the child plan's separate publication, implementation, retention,
  installation, live-probe, and closeout gates in order.
- Do not start Phase 5D from the parent plan until the child plan is done.

Gate passed: child plan is `done`; `TC-F06-01` and `TC-F07-01` are retained as
`pass`; issues #6/#7 are closed completed and `Done`; native and standalone
diagnosis pass 11/11; reconciliation remains paused; repository and installed
controller are clean at `2595bf5`; and the row records probe manifests
`0db444d6` and `5a79e2fa`. Phase 5D remains unstarted.

#### Phase 5D — UC-03 pack evaluation

- Execute
  [`2026-07-21-daidala-phase-5d-uc03-pack-evaluation.md`](2026-07-21-daidala-phase-5d-uc03-pack-evaluation.md)
  from its first incomplete phase.
- Keep this parent row `in-progress` while any child phase is incomplete.
- Freeze one repository baseline and the approved canonical package-resource
  fixture for both compared packs before either run.
- Compare pinned current/default `addyosmani` only with the one approved pinned
  `aidlc` candidate identity.
- Require identical evaluator, routing, verification, limits, and metric
  identities; any drift produces `incomparable`.
- Do not start Phase 6 until every child phase and this row's gate pass.

Gate: the child plan is `done`, a pack conclusion is supported by a valid paired
comparison, and no project default changes automatically.

### Phase 6 — Version-aware re-evaluation

- Identify one candidate Hermes version without changing the active runtime.
- Run the stable matrix and selected use cases in an isolated evaluator.
- Compare with the last-known-good baseline.
- Resolve, reopen, or create compatibility findings.
- Propose a supported-range change only after the complete comparison.

Gate: comparison is reproducible, candidate identities are exact, and the active
Hermes and controller Daidala installations remain unchanged.

### Phase 7 — Repository gate and documentation

Run:

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

Run documented compatibility and dashboard probes for each candidate host whose
prerequisites are satisfied. A blocked live probe remains `blocked`; repository
tests do not convert it to success. Complete the result document and DOX pass.
Commit, push, merge, release, and publication remain separately gated.

The documentation gate also verifies that every Daidala-specific flow branch in
`docs/15-self-improvement.md` maps to the case matrix or an explicit blocked live
probe, that its GitHub/Kanban/ledger authority table matches the parent protocol,
and that no diagram depicts Daidala as a separate service.

## Daidala-specific stop conditions

In addition to the parent protocol, stop when:

- `forgegod/daidala` remote identity or the supported Hermes boundary is unknown;
- either bundled pack or exact skill provenance fails validation;
- controller profile, `daidala-forgegod-daidala` board, pinned cron identity, or
  attended target cannot be verified;
- a candidate Daidala artifact would load in the persistent controller;
- issue intake lacks namespaced labels, maintainer readiness, structured fields,
  or a recoverable claim;
- an issue, manifest, registration, baseline, constraints, pack, stage profile,
  controller, cycle ID, intake digest, plan digest, or completion preview digest
  changed after its approval;
- Aidlc implementation would start from issue #3's preview-only body or the stale
  preview identity recorded before Phase 4F-A;
- GitHub mutation is requested with contents-write, merge, release, deployment,
  webhook-administration, or repository-administration capability;
- evidence publication lacks separate approval and a returned verifiable URL;
- a browser observation would use the user's normal browser profile; or
- the complete repository gate fails.

A GitHub outage blocks synchronization, not local evidence capture. An
unavailable candidate Hermes version blocks that comparison, not the established
baseline.

## Phase 1 decisions

- `.daidala/project.yaml` pins Addyosmani revision
  `7ce442de03ddc1b72480c3b48d55c62880ea2a90` with packaged-resource digest
  `991faf8e26d1c472230dcbf2c29baae9925ad9b9e0cd954f1d90b374302b7832`, and
  AI-DLC revision `e49341dbeb8af82758dd85e96ed7fe9bcf38a447` with digest
  `e4e921b9e719eb54a7d5ec753418e2e451369a3ef50ffd7f52cf74a85d6a6b6a`.
- The only accepted v1 evaluator declaration is `restricted-container` with
  denied-by-default network; Phase 3 diagnosis and Phase 4 isolation verification
  remain stop gates before live admission.
- The local notification alias is `attended-daidala`. Its gateway destination
  and authorized approval identities remain uncommitted trusted registration
  data. Approval uses the exact tuple defined by the parent protocol.
- Candidate Hermes selection belongs to Phase 6 as that phase states. Phase 1
  does not invent a future version; Phase 6 must record one exact available
  candidate before evaluation.
- `docs/evaluation-results/v1/daidala-self-improvement.md` materializes stable
  `TC-F01-01` through `TC-F18-03` procedures and separates pure-model passes
  from `not-run` live cases.

The repository path `.daidala/project.yaml`, controller profile
`daidala-self-improvement`, board `daidala-forgegod-daidala`, one global active
cycle, GitHub Issues-only v1 adapter, and deferred webhook intake are settled by
this plan unless it is amended and reapproved.

## Approval checkpoint

No implementation, branch creation, GitHub mutation, profile or board setup,
workflow, evaluator, model experiment, dashboard launch, browser execution, cron
creation, or Hermes version change starts until both this instance plan and its
parent protocol are explicitly approved.

Approval of these documents authorizes no implementation phase automatically.
Phase 1, Phase 2 coordination, Phase 3 checker implementation, Phase 4 setup,
Phase 4F issue rescope, admission apply, plan digest, completion apply, Phase 5
cron enablement, every isolated cycle, each retained improvement, evidence
publication, commit, push, merge, release, and active-runtime promotion require
their stated separate approvals.
