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

| Phase | Status | Checkpoint |
|---|---|---|
| 1 — Daidala fixture and deterministic foundation | Done | Commit `78c9732`; manifest, constraints, issue form, strict models, fake-adapter records, F01-F18 cases, technical flow, 273 tests, package/release checks, DOX, and post-commit graph review passed 2026-07-13. |
| 2 — Controller coordination and adapters | Done | Commits `3d22a84`, `5b375f6`, and regression `3a75a88`; repository coordination, fake-adapter tests, 287 tests, Ruff, Lefthook, Markdown links, both pack validations, package/release checks, DOX, and post-commit graph rebuild passed 2026-07-13. |
| 3 — Prerequisite doctor and setup confirmation | Todo | Requires the Phase 2 checkpoint and separate implementation approval; the setup guide remains normative. |
| 4 — Controller bootstrap and manual evaluation | Todo | Requires a completed Phase 3 report, separate setup approval, and a verified attended target. |
| 5 — Reconciliation, findings, and pack evaluation | Todo | Requires manual-cycle and replay evidence. |
| 6 — Version-aware re-evaluation | Todo | Candidate Hermes identity is selected here, not invented in Phase 1. |
| 7 — Repository gate and documentation | Todo | Requires prior live evidence or exact blockers. |

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

The first controlled workflow runs the same fixture separately with both packs.
A pack comparison never silently updates `.daidala/project.yaml`, the controller
profile, or installed controller skills.

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
- one repository priority label; and
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

The cron job pins its approved provider and model identity. A global model
change must not silently change unattended execution. Cron remains paused until
a duplicate tick creates neither a duplicate claim nor workflow and attended
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
| F05 definition and planning | Workers record activation, artifacts, and handoffs; plan completion creates a blocked approval card. |
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

Execution status: complete in commits `3d22a84` and `5b375f6`, with pack-digest
admission regression coverage in `3a75a88`. Repository coordination and
fake-adapter tests are implemented and verified. The operator checklist is
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

### Phase 4 — Controller bootstrap and manual live evaluation

- Require a current Phase 3 prerequisite report before setup. A report is
  advisory evidence, not setup approval or cycle approval.
- Install the controller plugin from the exact approved committed revision using
  verified GitHub installation or a detached local clone. A mutable symlink,
  editable checkout, uncommitted tree, or mismatched remote head fails setup.
- After separate setup approval, create the controller profile and board without
  changing the sticky default.
- Configure and verify attended notification and least-privilege GitHub aliases.
- Idempotently create and verify labels, issue template, and Project.
- Record controller and fresh-evaluator Hermes and Daidala identities.
- Validate plugin, packs, skills, CLI, dashboard, and evaluator readiness.
- Admit one controlled issue manually and run UC-01 for both packs.
- Stop at and exercise the exact plan gate before any implementation card.
- Run UC-02 only after its separate cycle approval.

Gate: each case has evidence or an exact blocker; no unrelated board, profile,
browser profile, repository, credential, or private database was touched; the
attended user received verifiable inspection identities.

### Phase 5 — Reconciliation, findings, and pack evaluation

- Create the reconciliation cron job paused.
- Run and replay one controlled tick; enable scheduling only after selection,
  deduplication, recovery, and attended notification pass.
- Select at most one structured maintainer-ready issue.
- Run one approved improvement and preserve baseline/candidate evidence.
- Run UC-03 with at most one candidate skill set.
- Retain, reject, or revert from measured results.
- Synchronize findings with returned GitHub identities while leaving new issues
  unready.

Gate: duplicate ticks create no duplicate workflows; every retained change
resolves its cited case without weakening another gate; failures and approval
waits reach the attended channel.

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
Phase 5 cron enablement, every isolated cycle, each retained improvement,
evidence publication, commit, push, merge, release, and active-runtime promotion
require their stated separate approvals.
