# Project self-improvement loop

## Goal

Implement a reusable, approval-gated protocol that lets an explicitly registered
software project use Daidala and Hermes Agent to:

1. establish a reproducible baseline;
2. execute a bounded workflow;
3. collect deterministic and AI-guided evidence;
4. propose an improvement or report a regression;
5. obtain human approval for any mutation;
6. repeat the evaluation in a fresh environment; and
7. retain a change only when the comparison shows a gain without weakening an
   existing contract.

Daidala remains the deterministic workflow, policy, approval, artifact, and
evidence engine for every registered project. Hermes remains the agent runtime,
model router, Kanban dispatcher, scheduler, gateway, delegation host, and tool
boundary. Workflow packs remain independently versioned methodology mappings;
the loop selects and snapshots them but does not absorb them.

The first concrete project is defined in
[`2026-07-13-daidala-self-improvement-loop.md`](2026-07-13-daidala-self-improvement-loop.md).

## Execution status

| Phase | Status | Checkpoint |
|---|---|---|
| 1 — Schemas and pure identity | Done | Commit `78c9732`; repository-local schemas, Daidala fixture, stable cases, documentation, 273 tests, Ruff, Markdown links, package/release checks, DOX, and post-commit graph review passed 2026-07-13. |
| 2 — Controller coordination and adapters | Done | Commits `3d22a84`, `5b375f6`, and regression `3a75a88`; repository coordination, fake-adapter tests, 287 tests, Ruff, Lefthook, Markdown links, both pack validations, package/release checks, DOX, and post-commit graph rebuild passed 2026-07-13. |
| 3 — Checklist-driven prerequisite diagnosis | Done | Commit `31e043b`; 308 tests, Ruff, Lefthook, Markdown links, both pack validations, build/Twine/release checks, incremental graph updates, and the clean-tree blocked live report passed 2026-07-14. |
| 4 — Evaluator and comparison | Done | Commit `cba9c52`; complete local fixtures ran in all three modes with isolation-receipt identity, durable baseline ordering, clean teardown, dirty-state quarantine, strict comparison and lesson-reuse evidence, increment/DOX reconciliation, 328 tests, Ruff, Lefthook, Markdown links, both pack validations, build/Twine/release checks, independent review, and incremental graph updates passing 2026-07-14. |
| 5 — Project onboarding and reconciliation | Blocked | Live prerequisite report `019e7de0` exits `2`: only `SI-REPOSITORY` passes; trusted registration/profile/board, controller packs, GitHub intake/findings/Project evidence, attended notification receipt, evaluator isolation evidence, and active-cycle evidence are absent. The mandatory manual-cycle and attended-delivery gate has not occurred. |
| 6 — Repository and host gate | Blocked | Phase 5 evidence does not exist; repository/host acceptance must not run. |

Relevant standing documents are
[Workflow ecosystem market overview](../12-market-overview.md),
[Autonomous triggering](../13-autonomous-triggering.md),
[Workflow constraints](../14-workflow-constraints.md), and
[Daidala documentation index](../README.md). The market overview records the
Multi-Agent & Swarms audit inputs; this plan adopts only the reusable evidence
and evaluation patterns, not any competing runtime.

## Scope and non-goals

A project is eligible only after explicit local registration and validation of
its committed manifest, repository identity, workflow pack, verification
contract, credential mapping, approval authority, and execution boundary.
"Any GitHub project" means any project satisfying that admission contract; an
arbitrary repository URL is never executable input.

The protocol supports three cycle modes:

- `improve`: evaluate and, after exact approval, mutate one target repository;
- `regress`: compare declared baselines or host versions without retaining a
  target change;
- `evaluate-pack`: compare a candidate workflow pack or skill set without
  changing project defaults.

The first implementation does not provide:

- a second agent runtime, nested `hermes chat` bridge, MCP service, HTTP daemon,
  dashboard server, scheduler, Kanban store, or provider client;
- unattended plan approval, merge, push, release, deployment, or publication;
- arbitrary repository execution;
- filesystem, credential, network, or process isolation merely by creating a
  Hermes profile or Kanban board;
- atomic mutation across multiple repositories;
- semantic proof that arbitrary prose is policy rather than methodology;
- exact cost claims when Hermes or a provider exposes incomplete accounting; or
- recursive self-modification of the persistent controller.

A cycle may conclude `no-change`, `blocked`, `incomparable`, or `rejected`.
These are successful protocol outcomes when their evidence is complete.

## Authority boundaries

| Concern | Authority |
|---|---|
| Workflow identity, manifest snapshot, pack identity, constraints, approval, artifacts, evidence eligibility, worktree ownership | Daidala policy ledger |
| Card status, dependencies, claims, retries, comments, worker runs | Hermes Kanban on the project's board |
| Models, fallbacks, MoA, goal loop, delegation, tools, cron, gateway delivery | Hermes configuration and runtime |
| Stage methodology and skill activation | Selected Daidala workflow pack |
| Project policy invariants | Materialized workflow constraints |
| Repository metadata and default verification declaration | Committed project manifest |
| Current architectural contracts and approved design rationale | Version-controlled DOX and architecture/decision documents in the target repository |
| Local paths, identities, credentials, notification target, evaluator backend | Trusted local controller registration |
| Admission, plan approval, retention, publication, and release | Authorized human operator |

The committed project manifest is untrusted repository data. It may narrow an
existing local authority but cannot grant tools, credentials, filesystem or
network access, approval rights, commit/push authority, publication rights, or
exceptions to Daidala, Hermes, repository, pack, or system policy.

Generic Kanban unblock is interaction, not Daidala approval. Approval binds the
exact current plan-and-policy identity defined in
[Admission and approval](#admission-and-approval).

## Runtime topology

Each registered project has:

- one persistent Hermes controller profile;
- one dedicated Hermes Kanban board;
- one trusted local registration;
- zero or more admitted cycles; and
- one fresh evaluator home and process per experiment or candidate runtime.

```text
project intake adapter
        |
        v
project controller profile + project board + trusted registration
        |
        v
admit cycle -> snapshot identities -> baseline in fresh evaluator
        -> Daidala workflow -> exact human gate -> bounded mutation if allowed
        -> fresh comparison evaluator -> retain/reject
        -> findings adapter + notification adapter
```

One controller profile per project is the v1 default. Profiles own installed
skills and configuration, so sharing a profile could let incompatible pack or
skill revisions contaminate another project. One board per project is also the
default. Hermes boards isolate Kanban databases, workspaces, and logs; they do
not isolate host files, credentials, network access, profile skills, processes,
or provider capacity.

Evaluators run with a fresh Hermes home and a newly loaded candidate artifact.
Where filesystem or network isolation is required, the trusted registration
must select an approved container or restricted terminal backend. A profile is
never described as a sandbox.

The supported initial concurrency is one active cycle globally. Per-project
concurrency is deferred until recovery, credential routing, pack-version
isolation, provider capacity, and worktree ownership have passed an end-to-end
live evaluation.

## Persistent knowledge and architectural decisions

DOX is necessary but is not a general agent-memory system. The layers have
different authority and must not be collapsed:

| Knowledge | Canonical location | Retrieval and mutation contract |
|---|---|---|
| Current binding instructions and local contracts | Applicable `AGENTS.md` chain | Read deterministically before work; changed only as a reviewed repository increment. |
| Current architecture and approved rationale | Version-controlled architecture and decision documents owned by the nearest DOX scope | Read from the repository and reviewed with the code; superseded text is corrected rather than left as an agent diary. |
| Cycle policy, identities, approvals, artifact digests, and evidence | Daidala policy and artifact ledger | Immutable or revision-scoped deterministic lookup. |
| Card lifecycle, retries, comments, and worker runs | Project Hermes Kanban board | Operational lookup only; the board is not architectural memory. |
| Session transcript and model observations | Hermes session facilities and bounded cycle artifacts | Advisory unless promoted through the [increment document protocol](#increment-document-protocol). |

Architectural rationale that must survive sessions is therefore a repository
increment, not an inferred memory. It names the decision, context, selected
option, rejected alternatives that remain relevant, consequences, owning DOX
scope, and the implementation or policy revision that makes it current. Its
repository path and format follow that project's existing documentation
conventions; the generic engine does not mandate an ADR directory. The normal
DOX pass decides whether the nearest `AGENTS.md`, an architecture document, or a
dedicated decision document owns the resulting current contract.

Git history is the v1 temporal record for accepted architecture. Agents may use
`git log`, `git show`, and code-graph queries to investigate when and why a
current contract changed, but current checked-out documents remain authoritative.
History explains supersession; it does not revive stale instructions.

Every controller, evaluator, and worker resolves the DOX chain and repository
architecture from its assigned checkout or candidate worktree root. It must not
read the persistent controller checkout's `AGENTS.md` or design documents as the
candidate's contract. A missing, escaped, or ambiguous worktree root blocks the
run rather than mixing baseline and candidate instructions.

### External memory systems considered

The first implementation does not integrate an external semantic-memory
service. The following projects are useful references, but none is a v1 source
of truth or runtime dependency:

| Project | Relevant capability | Decision for this protocol |
|---|---|---|
| [Hindsight](https://hindsight.vectorize.io/) | Isolated banks, document provenance, temporal/semantic/keyword/graph retrieval, and observation consolidation | Best candidate for a later recall spike, but refused for v1: it requires additional database, model, and service operations, while its consolidated observations are nondeterministic and cannot replace Git review or digest-bound evidence. |
| [Mem0](https://docs.mem0.ai/open-source/overview) | Self-hosted extracted memory with metadata filtering and hybrid retrieval | Refused for v1 for the same derived-memory and operational-dependency reasons; its simpler fact-memory model does not improve policy integrity. |
| [Graphiti](https://help.getzep.com/graphiti/getting-started/overview) | Open temporal knowledge graph with hybrid retrieval | Strong alternative for historical relationship queries, but graph infrastructure and derived edges are excessive before a measured cross-cycle recall failure exists. |
| [Letta](https://docs.letta.com/guides/core-concepts/memory/memory-blocks/) | Persistent editable context blocks plus archival memory | Refused because it introduces another stateful-agent model and agent-mutable memory rather than a read-only projection of Daidala records. |
| [Cognee](https://docs.cognee.ai/core-concepts/overview) | Vector-and-graph ingestion of unstructured corpora | Better suited to corpus processing than one bounded project's authoritative workflow records. |
| [LangMem](https://langchain-ai.github.io/langmem/) | Conversation extraction and long-term memory tools | Refused because it is LangChain-oriented and offers no advantage over Hermes-native facilities for the deterministic path. |
| [Microsoft GraphRAG](https://microsoft.github.io/graphrag/) | Batch knowledge-graph extraction and community summaries | Refused because it is a corpus-indexing pipeline, not low-latency workflow memory, and its own documentation identifies graph extraction as the dominant indexing cost. |

If repeated evaluations later prove that repository search, Daidala records,
Kanban, and session search cannot answer a declared cross-cycle query, a separate
approved `evaluate-pack`-style spike may compare Hindsight and Graphiti. Any
accepted integration must satisfy all of these boundaries:

- memory is keyed by stable `project_id`, never by mutable board name alone;
- candidate and cycle material is isolated by explicit identity and is not
  consolidated into project memory before retention approval;
- only redacted, approved, content-addressed documents and evidence are indexed;
- recalled or reflected content is advisory and cites its source identity;
- approval, policy checks, comparison, and recovery never depend on recall;
- the index is rebuildable from canonical repository and Daidala records; and
- Daidala does not start or own an MCP server, HTTP daemon, database, embedding
  service, or second agent runtime.

Unavailable memory must therefore reduce recall convenience, never block or
change a deterministic workflow result. A per-board bank is specifically
rejected because board identity is an operational projection, not project
identity.

## Project identity and committed manifest

Each target repository contains `.daidala/project.yaml`. Schema version 1 is
strict: unknown fields, duplicate keys, aliases, merge keys, custom tags,
control characters, and oversized content fail validation.

Proposed shape:

```yaml
schema: daidala.project/v1
project_id: example-owner-example-repository
repository:
  forge: github
  canonical: example-owner/example-repository
  allowed_remote_urls:
    - https://github.com/example-owner/example-repository.git
workflow:
  allowed_packs:
    - name: addyosmani
      source_revision: 0123456789abcdef0123456789abcdef01234567
      content_digest: 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
  default_pack: addyosmani
  default_constraints:
    source: .daidala/constraints.yaml
verification:
  suites:
    - id: repository
      kind: deterministic
      commands:
        - pytest
      timeout_seconds: 600
    - id: stability
      kind: repeated
      command: pytest tests/integration
      repetitions: 3
      acceptance:
        maximum_failures: 0
    - id: agent-observations
      kind: observational
      fields:
        - ambiguity
        - recovery_quality
improvement:
  mutable_paths:
    - src/**
    - tests/**
    - docs/**
  protected_paths:
    - .daidala/project.yaml
  maximum_changed_files: 20
  approval_roles:
    - maintainer
intake:
  adapter: github-issues
  eligible_categories:
    - regression
    - improvement
    - compatibility
    - skill-gap
release:
  allow_commit: false
  allow_push: false
  allow_publish: false
```

The implementation must define exact bounds for list sizes, strings, commands,
repetitions, timeouts, and glob syntax before accepting schema version 1.
Verification commands are data executed only inside the locally approved
evaluator boundary; declaring a command does not authorize a broader backend.

At admission, Daidala snapshots canonical manifest content and computes its
SHA-256 digest. The immutable snapshot, not the mutable working-tree file, binds:

- cycle and workflow identity;
- selected pack and constraints;
- baseline and candidate revisions;
- definition and plan artifacts;
- approval;
- executable cards;
- verification evidence; and
- comparison and retention decisions.

A manifest change during an active cycle does not change that cycle. New stage
evidence with a mismatched manifest identity fails closed. A manifest change
may be proposed as target work, but it can govern only a later admitted cycle.

## Trusted local controller registration

Local registration belongs under a Hermes-resolved profile data path and is
never committed to the target repository. It maps the untrusted project ID to
trusted operational facts:

```yaml
schema: daidala.controller-registration/v1
project_id: example-owner-example-repository
checkout: /absolute/path/to/repository
controller_profile: daidala-example-owner-example-repository
board: daidala-example-owner-example-repository
repository_identity:
  canonical: example-owner/example-repository
  verified_remote: https://github.com/example-owner/example-repository.git
credentials:
  intake: github-example-read-issues
  findings: github-example-write-issues
approval:
  maintainers:
    - local-operator-id
notifications:
  adapter: hermes-gateway
  target: configured-attended-target-alias
evaluator:
  backend: restricted-container
  network: denied-by-default
limits:
  active_cycles: 1
  goal_turns: 12
  delegated_workers: 3
  research_query_batches: 3
  extracted_sources: 3
  wall_clock_seconds: 3600
```

Registration validates absolute paths, safe slugs, board existence, controller
profile identity, exact repository remote identity, credential capability,
notification delivery, evaluator backend, and finite limits. Repository rename,
transfer, fork, or remote change blocks admission until a human updates and
revalidates registration. The controller never repairs trusted identity from a
repository manifest.

Credentials are referenced by alias and never copied into manifests, evidence,
cards, evaluator homes, or logs. Evaluators receive only the minimum read or
mutation capability required by their approved cycle; they never receive issue
mutation, publication, release, or controller credentials.

## Cycle identity and modes

A cycle has a path-safe deterministic identity derived from canonical inputs:

```text
(project_id, mode, intake_adapter, intake_item_id, manifest_digest,
 baseline_revision, selected_pack_identity, candidate_identity)
```

Replaying admission with the same tuple returns the same cycle and workflow.
Changing a material input creates a different identity; model prose, timestamps,
and local process IDs are not identity inputs.

### `improve`

1. Admit one bounded goal and baseline.
2. Capture pre-mutation deterministic and repeated evidence.
3. Run `define -> plan` through the selected pack.
4. Persist the exact plan, manifest, constraints, pack, baseline, and candidate
   identity tuple.
5. Require human approval of its digest before creating implementation-capable
   work.
6. Mutate only the one approved repository in a Daidala-owned worktree.
7. Capture immutable changed paths, diff, verification, review, and delivery
   evidence.
8. Re-run comparison in a fresh evaluator.
9. Retain only after all deterministic gates and declared repeated thresholds
   pass and no protected metric regresses.

### `regress`

`regress` is non-retaining. It compares an approved matrix of project, Daidala,
Hermes, pack, or model-routing identities using stable test-case IDs. Candidate
Hermes or Daidala versions run outside the persistent controller process. A
regression finding may create an intake item for a later `improve` cycle but
cannot silently change the current runtime.

### `evaluate-pack`

`evaluate-pack` compares the current pack with one candidate pack or skill-set
revision against the same goal, fixture, runtime routing, and limits. It does
not update the project manifest, installed controller skills, or default pack.
Promotion requires a separate approved `improve` cycle.

## Intake, findings, and notification adapters

The engine consumes normalized, validated records rather than GitHub-specific
labels or payloads.

An intake adapter returns:

- adapter name and immutable item identity;
- canonical source URL when available;
- category and priority;
- goal and acceptance criteria;
- evidence references and digests;
- dependencies and risk;
- admission actor and admission state; and
- claim identity, timestamp, and lease expiry.

A findings adapter accepts a redacted structured finding and returns a
verifiable external identity. The engine never claims synchronization without a
returned adapter identity and URL where applicable. Adapters must deduplicate
open and closed findings by stable finding identity.

A notification adapter returns a delivery receipt for admission, approval wait,
failure, blocked recovery, and completion. Unattended reconciliation requires a
successful probe to an attended target. Local-only output is permitted only for
an observed manual run.

GitHub Issues is the first planned adapter. Its labels, issue template, Project
view, and credential scopes belong to each concrete project instance rather
than this generic engine contract. Webhook intake is deferred until manual and
cron admission pass replay-safe end-to-end tests.

## Admission and approval

Before dispatch, a cycle records:

- one goal and completion contract;
- mode and immutable intake identity;
- manifest, pack, constraints, baseline, and candidate identities;
- verification suites and comparison metrics;
- goal-turn, worker, research, wall-clock, filesystem, network, repository,
  board, profile, browser, and credential limits;
- permitted and protected paths; and
- stop conditions.

The exact approval identity is:

```text
(cycle_id, workflow_id, mode, manifest_digest, baseline_revision,
 pack_identity, constraints_revision, constraints_digest,
 plan_revision, plan_digest, candidate_identity)
```

Only an authorized local registration identity may approve it. Project manifest
roles describe required roles but do not authorize people or agents. Changing
any tuple member invalidates approval and requires a fresh plan or cycle as
appropriate.

Admission, plan approval, retention, evidence publication, commit, push, merge,
release, deployment, and controller-runtime promotion are separate decisions.
No broad approval implies another.

## Evidence and comparison

Every run records non-secret reproducibility data:

- cycle, workflow, atomic test-case, project, board, profile, and evaluator IDs;
- manifest, pack, skill, constraints, repository, Daidala, and Hermes identities;
- model-routing mode and observed fallback events without credentials;
- evaluator backend, workspace, worktree ownership, and process result;
- goal, limits, actions, resource observations, and adaptive decisions;
- commands, exit codes, bounded output references, and artifact digests;
- delegation topology: parent run, child run, delegated goal, role, toolsets,
  model route, input artifact identities, output digest, resource observations,
  cancellation or failure state, and terminal state;
- intake and finding identities plus notification receipts;
- before/after metrics; and
- `retained`, `reverted`, `rejected`, `blocked`, `incomparable`, or `no-change`.

Metric kinds are:

- `deterministic`: exact pass/fail; every required deterministic metric must pass;
- `repeated`: an explicit repetition count and acceptance threshold; raw runs and
  aggregation method are retained;
- `observational`: structured evidence for review; it cannot alone justify
  retention.

Baseline and candidate must use the same declared fixture, commands, environment
class, limits, and metric definitions unless the approved experiment explicitly
tests that difference. Missing evidence, excessive variance, or an invalid
comparison produces `incomparable`, never an inferred improvement.

Where Hermes exposes reliable usage or cost data, record it. Otherwise record
bounded proxies such as turns, model calls, delegated workers, research calls,
and wall-clock time. Estimates remain labeled as estimates.

Cross-cycle learning is measured, not assumed. A retained lesson, skill update,
or documentation change may claim self-improvement only when a later evaluation
can cite the approved source and compare the run against a fixture with and
without that knowledge. The comparison records lesson applicability, repeated
failed actions avoided, recovery outcome, turns, wall time, irrelevant matches,
and unsafe use. Unapproved lessons remain workflow artifacts and never enter
shared project memory or command execution.

Supported repositories may add structural graph evidence: graph freshness,
affected-flow and blast-radius deltas, dependency cycles, bridge or hub changes,
and new untested hotspots. Exact declared graph rules may be deterministic;
centrality and risk scores are observational. A stale or incomplete graph makes
the graph comparison `incomparable`, not passing.

Credentials, tokens, connection strings, full profile contents, private Kanban
data, and unbounded logs are prohibited evidence. Accidental secrets are
replaced with `[REDACTED]` before persistence or publication.

## Increment document protocol

Skills may produce specifications, design records, migration notes, reports,
and other documents while executing an increment. A file's existence does not
make it evidence, policy, or durable project knowledge. Every produced document
is classified before the stage can complete:

| Class | Location and lifetime | Registration and authority |
|---|---|---|
| Repository increment | Approved Daidala-owned worktree; retained only with the accepted diff | Declared by repository-relative path in the approved plan, captured in the immutable changed-path manifest and diff, checked against its DOX chain, and covered by retention approval. This is the only class that may become current project documentation. |
| Workflow artifact | Profile-local immutable workflow artifact store | Submitted through the stage artifact/evidence boundary, content-digested, and bound to cycle, workflow, stage, plan revision, policy revision, and activation identity. It supports approval, comparison, review, or recovery but is not automatically committed documentation. |
| External finding or publication | Local workflow artifact first; remote system only after a separately authorized adapter call | Carries the source artifact digest and accepts only a returned verifiable remote identity. Publication never changes policy authority. |
| Ephemeral work product | Fresh evaluator or owned worktree scratch area | Unregistered and ineligible for approval, handoff, comparison, or future recall. It is discarded or quarantined with the evaluator unless explicitly promoted before stage completion. |

Each cycle has one canonical immutable increment manifest. It enumerates every
durable document and, for each entry, records:

- stable entry ID, class, media type, purpose, and repository-relative path or
  Daidala-owned artifact reference;
- SHA-256 content digest and bounded byte size;
- cycle, workflow, stage, plan revision, policy revision, manifest, pack,
  constraints, and activation-manifest identities;
- producing skill's exact name and complete-directory digest, or
  `producer: deterministic-engine` for engine-generated records;
- creation timestamp, superseded entry identity when applicable, redaction
  state, and intended retention or publication disposition; and
- owning DOX scope for repository increments.

Producer identity is derived from the finalized card-scoped activation manifest;
a worker cannot self-assert an unactivated skill. Multiple active skills may be
listed only when the handoff identifies which one produced or materially shaped
the document. Unknown producers, absolute repository paths, mutable artifact
references, digest mismatches, duplicate entry IDs, undeclared repository
documents, and unbounded content fail the stage.

For repository increments, the engine derives entries from the frozen changed-
path manifest, recomputes every digest and byte size from the owned worktree, and
requires every path to be declared by the approved plan and allowed by the
manifest's mutable-path policy. A worker-supplied manifest cannot override the
observed diff. Writes during a non-mutating stage and files omitted from either
the plan or increment manifest fail closed.

The protocol has two write chokepoints. Definition, plan, review, decision,
comparison, and report artifacts use Daidala's artifact submission boundary.
Documents intended to ship with the project are written only in the approved
worktree and are frozen by implementation capture. Verification output continues
through the verification-evidence boundary. A skill must not copy a workflow
artifact into the repository, publish it, or promote its own scratch output by
mentioning it in a Kanban comment.

The review stage reconciles the manifest against the frozen diff, artifact
ledger, activation manifests, and applicable DOX chain. It rejects undocumented
new files, missing planned documents, stale generated documents, and repository
documentation that leaves owning `AGENTS.md` or architecture indexes
contradictory. Retention preserves the accepted repository documents in Git and
the complete immutable cycle manifest in Daidala storage. Rejected and negative
cycles preserve bounded evidence and rationale without polluting current project
documentation or any future semantic-memory projection.

## Recovery and reconciliation

The controller reconciles the Daidala policy ledger, the project's board, local
worktrees/evaluator records, and adapter claims. No single projection is enough.

- A crash between intake claim and workflow creation is retried using the
  deterministic cycle/workflow identity.
- A claim lease may return to ready only after both Daidala and the board prove
  no active owner exists.
- A crash after mutation preserves or quarantines the owned worktree and marks
  the run incomplete. Dirty files are never accepted as evidence.
- Pre-mutation baseline evidence must be durable before implementation begins.
- A missing or manually modified board blocks reconciliation; cards are never
  recreated, completed, or associated from title or prose alone.
- Stale evaluators cannot submit evidence because current card, manifest, plan,
  constraints, pack, and candidate identities must all match.
- Duplicate cron ticks converge on the same cycle and cards and never start a
  second active cycle.
- GitHub or another adapter outage preserves local findings as synchronization
  pending; it does not fabricate remote state.

Recovery actions preserve the audit trail. Destructive cleanup occurs only for
Daidala-owned evaluators and worktrees after ownership and retention state are
proven.

## Cross-project and cross-repository edge cases

- Projects requiring different skill revisions use different controller
  profiles. Candidate revisions stay in fresh evaluator homes.
- Projects requiring incompatible Hermes versions use separate runtime
  environments, not only separate boards or profiles.
- One cycle mutates at most one repository in v1. A pack-repository and target-
  repository change becomes linked cycles with independent plans, approvals,
  worktrees, and evidence.
- Board and project slugs are derived and collision-checked; an existing board
  with different registered identity is rejected.
- Evidence and worktree paths include project and cycle identity and are checked
  for containment before creation or deletion.
- A project without a reproducible baseline may run a setup evaluation but
  cannot retain an improvement.
- Candidate code cannot modify the controller installation, trusted
  registration, approval policy, evaluator/judge implementation, immutable
  baseline evidence, active manifest snapshot, or another project.
- Project archival disables admission and reconciliation while preserving
  boards, policy records, evidence, and external finding links. Destructive
  teardown is a separate explicit operation.

## Planned implementation boundaries

The generic protocol is implemented inside the existing Daidala plugin, not as
another service. Proposed files are:

```text
daidala/projects.py             strict project-manifest model and digest
daidala/registrations.py        trusted local registration model and validation
daidala/cycles.py               cycle identity, modes, admission, comparison
daidala/increments.py           strict increment-manifest and document provenance
daidala/adapters.py             narrow intake/findings/notification protocols
daidala/reconciliation.py       replay-safe claim and evaluator recovery
tests/test_projects.py
tests/test_registrations.py
tests/test_cycles.py
tests/test_increments.py
tests/test_adapters.py
tests/test_reconciliation.py
docs/evaluation-results/AGENTS.md
```

## Comprehensive technical flow documentation

Implementation must create `docs/15-self-improvement.md` as the canonical
technical explanation of the autonomous self-improvement flow. This document is
descriptive; this plan, Daidala's deterministic runtime contracts, and the
selected project-instance plan remain authoritative when wording drifts.

The document must be comprehensive enough for an operator or implementer to
trace one cycle without reconstructing behavior from source. It must contain:

- a glossary and authority map for project, registration, cycle, workflow,
  controller, board, evaluator, pack, constraints, adapter, evidence, finding,
  and approval identities;
- the complete intake -> admission -> immutable snapshot -> baseline ->
  definition -> planning -> exact approval -> mutation when permitted -> fresh
  evaluation -> comparison -> retention/rejection -> findings -> archival flow;
- a state and transition table for `improve`, `regress`, and `evaluate-pack`,
  including owner, preconditions, durable writes, side effects, idempotency key,
  notifications, and stop result for every transition;
- Mermaid component, flowchart, and sequence diagrams for all three modes,
  showing Daidala as an in-process Hermes plugin and never as a server;
- cycle-identity derivation and the exact approval tuple, with examples of which
  changes invalidate admission, planning, approval, or evidence;
- the persistent-knowledge authority split, external-memory refusal, and the
  conditions under which a read-only semantic projection may be reconsidered;
- the increment document classes, manifest schema, producer provenance,
  promotion rules, DOX reconciliation, and retention behavior;
- committed-manifest versus trusted-registration data flow and the rule that
  repository data may narrow but never grant local authority;
- controller, project board, fresh evaluator, worktree, credential, filesystem,
  network, model-routing, and gateway boundaries;
- intake, findings, and notification adapter request/response contracts,
  deduplication, receipts, pending synchronization, and outage behavior;
- deterministic, repeated, and observational evidence pipelines, comparison
  eligibility, `incomparable` handling, retention, rollback, and publication;
- normal reconciliation plus decision tables for duplicate ticks, expired
  claims, missing or modified boards, crashed evaluators, dirty worktrees, stale
  manifests, stale cards, unavailable adapters, and exhausted budgets;
- security and threat-boundary analysis, including untrusted repository code,
  candidate attempts to alter controller material, secret redaction, confused
  deputy paths, and why profiles and boards are not sandboxes;
- project onboarding, manual first run, approval, inspection, recovery,
  archival, and teardown procedures; and
- links to the precise Daidala architecture, policy-ledger, lifecycle, pack,
  constraints, security, Hermes-integration, and project-instance contracts
  instead of duplicating their normative details.

The Daidala instance plan supplies the first concrete walkthrough and evidence.
The canonical document must clearly mark generic protocol sections and
`forgegod/daidala` examples so the example does not become an engine special
case. Commands remain drafts until exercised against the supported Hermes
version; `docs/README.md` must report that support state accurately.

Verification for the document includes Markdown links, Mermaid syntax and
process-boundary review, agreement between transition tables and tested runtime
contracts, and a source-reference audit. Missing diagrams, unresolved identity
ownership, or an undocumented recovery branch blocks publication.

Existing `state.py`, `workflow.py`, `store.py`, `service.py`, `execution.py`, and
`kanban.py` remain the policy-ledger and host-boundary foundation. The engine
must stay pack-neutral and use only public Hermes plugin and Kanban boundaries.

## Implementation phases

### Phase 1 — Schemas and pure identity

- Add strict project-manifest and trusted-registration models.
- Add cycle modes, deterministic identity, metric definitions, and comparison
  outcomes.
- Add strict increment-manifest, document classification, and producer-
  provenance models without adding an external memory dependency.
- Add delegation-topology and lesson-reuse evidence schema fields.
- Add canonical serialization, bounds, and digest tests.
- Add positive, malformed, unknown-field, collision, and stale-identity tests.
- Draft `docs/15-self-improvement.md` with the complete generic flow, identity
  map, mode sequences, transition tables, adapter contracts, evidence pipeline,
  and recovery decisions. Mark every unexercised command and live behavior as
  planned rather than implemented.

Gate: focused tests, Ruff, Markdown links, and DOX pass. No Hermes profile,
board, GitHub object, model, or external process is touched.

### Phase 2 — Controller coordination and adapters

- Add project admission and materialized manifest snapshots.
- Add narrow injectable intake, findings, and notification adapter protocols.
- Bind cycle identity, expected baseline, canonical constraints, and executable
  stage profiles to existing Daidala workflow and evidence operations.
- Add replay-safe claims, local pending synchronization, and receipt validation.
- Add fake-adapter tests with no network calls.

Gate: duplicate admissions and adapter retries converge; malformed external data
fails before board or repository mutation.

### Phase 3 — Checklist-driven prerequisite diagnosis

- Keep `docs/16-self-improvement-setup.md` as the normative operator guide and
  prerequisite list. Give each ready-to-admit row a stable `SI-*` check ID.
- Extend the existing shared `daidala doctor` / `hermes daidala doctor` command;
  do not add a competing executable or a setup side effect.
- Add `--project-manifest`, optional `--registration`, and explicit `--live`
  inputs. Without `--live`, network, gateway-delivery, and container execution
  checks report `not-run` and the aggregate result remains blocked.
- Add a strict profile-local credential-binding model that maps each registration
  alias to resolver `environment` plus an explicit environment-variable name.
  The file contains no credential values. V1 performs no alias-name inference,
  password-manager discovery, or `bw`/`bws`/`keepassxc-cli` invocation.
- Resolve a token only at the bounded adapter call, pass it as `GH_TOKEN` to the
  GitHub CLI child environment, and never print, persist, hash, or return it as
  evidence. Missing variables and unsupported resolvers fail closed.
- Add a strict `daidala.prerequisite-report/v1` JSON report with project and
  checklist identity, bounded redacted evidence, per-check `pass`, `blocked`,
  `not-run`, or `error` status, and the matching guide section.
- Return exit code `0` only when every required check passes, `2` when any check
  is blocked or not run, and `1` for invalid input or checker failure.
- Probe manifest/registration binding, checkout and remote, profile, board,
  plugin, packs, credential aliases, GitHub Project projection, attended target,
  restricted evaluator, and active ownership through injected public command
  boundaries. Never read or print token values, private destination IDs, profile
  dumps, or private databases.
- Validate retained capability metadata and prior approved receipts without
  creating them. A missing receipt or capability proof is `blocked`; diagnosis
  never sends a notification, writes a GitHub issue, or launches an evaluator to
  manufacture passing evidence.
- Add fake-command tests for complete, missing, malformed, denied, unavailable,
  and partially configured environments. Add a parity test that extracts the
  stable check IDs from `docs/16-self-improvement-setup.md` and requires exact
  agreement with the CLI registry.
- The command is diagnostic only: no `--fix`, `--apply`, profile/board creation,
  credential storage, notification send, GitHub mutation, evaluator launch, or
  admission. Human review of the guide and separate setup/cycle approvals remain
  mandatory.

Gate: standalone and Hermes-native outputs and exit codes agree; every guide
check is represented exactly once; fake probes prove fail-closed behavior; and a
live non-mutating run against the current host reports exact passes and blockers
without changing profile, board, gateway, GitHub, repository, or evaluator
state.

### Phase 4 — Evaluator and comparison

- Create fresh evaluator homes and owned worktrees through approved local
  registrations.
- Capture durable baseline evidence before mutation.
- Implement deterministic, repeated, and observational comparisons.
- Add controlled lesson-reuse comparison fixtures and optional structural graph
  evidence capture for supported repositories.
- Reconcile skill-produced documents against the frozen diff, artifact ledger,
  activation manifests, approved plan, and applicable DOX chain.
- Add quarantine and stale-evidence recovery tests.
- Prove candidate artifacts cannot replace the loaded controller plugin.

Gate: one complete local fixture runs in all three modes, and every failure path
produces evidence or an exact blocker.

### Phase 5 — Project onboarding and reconciliation

- Add dry-run-first project registration and archival commands.
- Verify profile, board, repository, credential capability, evaluator backend,
  and notification target.
- Add one paused reconciliation job only after a manual cycle passes.
- Exercise replay, crash, board deletion, adapter outage, and teardown.

Gate: unattended intake remains disabled until the attended notification and
replay-safety probes pass.

### Phase 6 — Repository and host gate

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

Live Hermes, adapter, model, or browser probes are reported separately and may
be `blocked`; repository tests cannot substitute for them.

Complete the technical-flow source audit: every transition and identity in
`docs/15-self-improvement.md` must point to its owning contract or tested source;
Mermaid diagrams must keep Daidala inside Hermes; exercised and unexercised
operator paths must be labeled distinctly.

## Stop conditions

Stop before another mutation or dispatch when:

- human approval is required or approval identity is stale;
- project registration, repository identity, board, profile, evaluator backend,
  credential capability, or notification target cannot be verified;
- the manifest, pack, skill provenance, constraints, structured handoff, or
  evidence is missing, malformed, oversized, or stale;
- another cycle is active or claim ownership is uncertain;
- candidate work would execute in the persistent controller;
- the operation would touch an unregistered repository, another project,
  protected control material, an active user browser profile, or an unapproved
  filesystem/network boundary;
- baseline evidence is incomplete;
- comparison inputs differ without explicit approval;
- repeated evidence exceeds its variance policy;
- a multi-repository mutation is required;
- generic Kanban unblock is the only approval representation;
- merge, push, release, publication, or deployment is requested without its own
  approval and verifiable result; or
- repository verification fails.

Resource exhaustion records `budget_exhausted` and stops before another
dispatch. It is not reported as a product failure.

## Phase 1 decisions

- `daidala/projects.py` and `daidala/registrations.py` own exact schema fields,
  unknown-field rejection, 64 KiB/32 KiB YAML bounds, 512-character normal
  text, 2,048-character commands, list bounds, 1-3,600 second command timeouts,
  2-20 repetitions, 1-100 changed files, normalized relative POSIX globs, and
  one global active cycle.
- V1 accepts only evaluator backend `restricted-container` with
  `denied-by-default` network. Phase 3 reports capability availability without
  mutation; Phase 4 must verify actual filesystem, process, network, and
  credential isolation before admission.
- Trusted registration is profile-local at
  `projects/<project_id>/registration.yaml` below the Hermes-resolved data root.
- Increment documents are bounded to 1 MiB each and 256 canonical entries.
  Their immutable manifest is stored at
  `projects/<project_id>/cycles/<cycle_id>/increment-manifest.json`; strict class,
  media type, producer digest, supersession, redaction, disposition, and DOX
  ownership rules live in `daidala/increments.py`.
- Evaluator scratch is contained at
  `projects/<project_id>/cycles/<cycle_id>/evaluators/<evaluator-id>/scratch`.
  Clean terminal scratch is discarded; dirty, crashed, or ownership-ambiguous
  state moves only to sibling `quarantine` pending explicit recovery.
- `daidala/adapters.py` defines normalized intake, claim, finding, publication,
  and notification records. Stable finding identity hashes project, category,
  normalized title, and evidence digest.
- Repeated metrics use declared `all-pass`, `mean`, or `median` aggregation and
  complete declared repetitions. Missing runs, identity mismatch, or excessive
  variance produces `incomparable`.
- Delegation evidence records parent/child run, goal, role, toolsets, model
  route, input/output digests, turns, wall time, terminal state, and bounded
  failure reason.
- UC-01 is the first lesson-reuse fixture. Graph evidence is comparable only
  when it contains files and nodes and identifies the exact evaluated revision;
  stale, empty, or unavailable graphs are `incomparable`.

The following v1 choices are settled unless this plan is amended and reapproved:
one active cycle globally, one mutable repository per cycle, one controller
profile and board per project, GitHub Issues as the first adapter, and webhook
intake deferred until manual and cron replay safety are exercised. DOX and
version-controlled project documents remain architectural authority; no external
semantic-memory system is a v1 dependency or source of truth.

## Approval checkpoint

This document defines the reusable protocol only. No Python or test
implementation, branch creation, profile or board setup, repository mutation,
external adapter mutation, model experiment, cron creation, or Hermes runtime
change starts until this plan and the selected project-instance plan are
explicitly approved.

Approval of an instance phase never waives per-cycle exact approval or grants
commit, push, merge, release, publication, deployment, or controller promotion.
