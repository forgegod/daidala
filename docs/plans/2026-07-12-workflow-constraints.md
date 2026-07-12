# Workflow constraints implementation plan

> Status: approved for phase-gated execution. Phase 1 is complete; no runtime
> or user-facing workflow-constraint behavior is implemented yet.
>
> For the implementing agent: read `/AGENTS.md`, `docs/AGENTS.md`,
> `wingstaff/AGENTS.md`, `tests/AGENTS.md`, this plan, and
> `docs/14-workflow-constraints.md`. Stop when any gate fails.

## Goal

Give one Wingstaff workflow a durable, revisioned policy contract that applies to
all executable phases. Constraints express invariants and approval boundaries,
not methodology. Exact Hermes policy skills provide reusable sources; Wingstaff
materializes their validated content into immutable workflow artifacts.

Before describing the feature as implemented, document the topology from Hermes
profile and worker lane through named board and Wingstaff workflow to the
workflow-scoped constraint artifact. The documentation must make authority,
cardinality, dispatch, and lifecycle ownership explicit rather than implying a
parent-child hierarchy that Hermes does not provide.

## Execution phases

The user approved this plan for phase-gated execution on 2026-07-12. Execute
exactly one row per committed checkpoint; a later row remains unstarted until
the current row's gate and commit succeed.

| Phase | Status | Scope | Gate |
|---|---|---|---|
| 1. Host feasibility and bounds | Done | Prove exact installed-skill resolution, public Kanban lifecycle operations, and the worker-context body limit against an isolated Hermes v0.18.2 home. | Isolated host probes plus the repository gate. |
| 2. Constraint model | Done | Add strict YAML parsing, canonicalization, immutable artifacts, provenance, and state identities. | Focused model/parser tests plus the repository gate. |
| 3. Persistence and transitions | Todo | Persist append-only constraint revisions and implement deterministic idempotent recording and invalidation. | Store/workflow/execution tests plus the repository gate. |
| 4. Card and worker enforcement | Todo | Project applicable policy onto cards and reject stale cards, workers, activation, handoffs, and evidence. | Kanban/worker/execution tests plus the repository gate. |
| 5. Approval and graph replacement | Todo | Bind approval to plan and constraint identity; durably invalidate and recreate stale workflow work. | Workflow/service/Kanban recovery tests plus the repository gate. |
| 6. Tool and CLI surfaces | Todo | Expose explicit start, replacement, status, skill-source, and file-source inputs through shared service paths. | Tool/plugin/CLI parity tests plus the repository gate. |
| 7. Documentation and host verification | Todo | Reconcile numbered docs, architecture, integration guidance, operator surfaces, and supported-host evidence. | Full repository gate and isolated supported-host probes. |
| 8. Release compatibility regression | Todo | Turn the Phase 1 host findings into durable architecture documentation and a repeatable Hermes compatibility probe that gates Wingstaff releases and intentional host-version changes, not every push. | Script tests, an isolated supported-host run, release-workflow trigger assertions, and the repository gate. |

Phase 2 verdict: GREEN. Strict parser/model coverage passed with 61 focused
tests; the repository gate passed with 165 tests, Ruff, both pack validators,
sdist/wheel build, Twine, release-content validation, Markdown links, Lefthook,
and clean diff checks.

Phase 1 verdict: GREEN on Hermes Agent v0.18.2 (2026.7.7.2), upstream
`4281151a`. In isolated `HERMES_HOME` directories, exact skill inventory found
only `policy-probe`, deterministic directory hashing returned one digest, and a
missing exact name returned no match. Public named-board create, show, comment,
parent-link, complete, and archive operations succeeded. Worker context retained
task bodies of 7,900 and 8,192 characters intact and visibly truncated an
8,300-character body. The implementation therefore caps canonical constraint
content at 4,096 UTF-8 bytes and rejects any fully rendered card body over 8,192
characters; it never truncates policy content. The smaller canonical-content
budget reserves space for Wingstaff card identity, goal, pack, plan, worktree,
and worker instructions and remains safe for multibyte constraint text.

## Scope and authority

Constraints belong to one workflow. The workflow selects one named Hermes board,
while its pack and constraints remain workflow properties. Two workflows on one
board may select different packs and constraints; one pack or reusable constraint
source may be used on multiple boards.

| Concern | Owner |
|---|---|
| How work is performed | Skills selected by the workflow pack |
| Required or conditional skills per phase | Workflow pack |
| What must remain true regardless of methodology | Workflow constraints |
| Card lifecycle, assignment, comments, dependencies, and retries | Hermes Kanban |
| Artifact integrity, approval binding, and stale-worker rejection | Wingstaff |

## Topology and worker-lane documentation

The repository has authority and lifecycle descriptions, but no single current
description of this complete topology. Before implementation closes, add one
operator-facing diagram and accompanying prose to the numbered architecture and
Hermes-integration documents. It must use the current official [Hermes worker
lane contract](https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban-worker-lanes)
as the host reference and state all of the following:

- A Hermes profile is an independently configured agent identity. When its name
  is used as a card assignee, it is the default Hermes profile worker lane; it
  is not a board, workflow, or constraint container.
- A named Hermes board is an independent card namespace and the canonical
  lifecycle and audit authority. It owns cards, dependencies, assignments,
  claims, retries, comments, run history, and the dispatcher; it does not own
  Wingstaff workflow policy.
- A Wingstaff workflow is a profile-local policy-ledger record that selects
  exactly one existing board and maps each lifecycle stage to a profile-lane
  assignee. It creates and identifies its card graph on that board, but does not
  mirror Kanban status or dispatch workers.
- The dispatcher routes a ready card to its assignee lane. A Hermes profile lane
  receives the card's board, task, workspace, and run identity through Hermes;
  it ends the run through the public `kanban_complete` or `kanban_block`
  boundary. Wingstaff must not replace that lifecycle terminator or dispatcher.
- Workflow constraints are immutable, revisioned, workflow-owned artifacts. They
  are neither profile instructions nor board configuration: a workflow projects
  its current constraint identity and applicable text onto its own cards, and
  changed content restarts only that workflow's graph under a new policy
  revision.
- The diagram distinguishes one-to-many relationships: one profile can serve
  cards on many boards and workflows; one board can host many workflows; each
  workflow selects one board; and each workflow revision owns at most one current
  constraint artifact, with immutable historical revisions retained.

The documentation must also distinguish the standard `review-required` Kanban
block convention from Wingstaff's exact plan-and-constraint approval gate:
unblocking a card remains a Kanban interaction and cannot authorize a stale or
changed Wingstaff workflow.

Workflow constraints may express:

- prohibitions, such as no commit, push, or deployment;
- approval requirements, such as no new dependency without human approval;
- required output properties, such as documentation matching changed contracts;
- quality or release boundaries, such as unresolved critical security findings
  blocking delivery.

Workflow constraints may not express:

- procedures or step sequences;
- methodology such as TDD, decomposition, debugging, or review technique;
- skill, pack, profile, model, or tool selection;
- shell commands or tool calls;
- activation modes, ranks, or overrides;
- permissions or exceptions to Wingstaff, Hermes, repository, or system policy.

Structured fields named `skills`, `pack`, `profiles`, `models`, `tools`, `steps`,
`commands`, `activation`, or equivalent executable configuration are rejected as
unknown fields. Workers block free-text constraints that attempt to prescribe
methodology or capabilities. Such content belongs in a skill or pack. Wingstaff
does not claim deterministic semantic classification of arbitrary prose.

## Constraint artifact

The schema is `wingstaff.workflow-constraints/v1`:

```yaml
schema: wingstaff.workflow-constraints/v1
global:
  - Never commit or push.
  - Do not add production dependencies without explicit approval.
phases:
  review:
    - Unresolved critical security findings block delivery.
  deliver:
    - |-
      Documentation must match changed public contracts and describe
      any required operator action.
```

Contract:

- `schema` is exact and required;
- `global` is a required non-empty bounded list of strings;
- `phases` is optional and accepts only `define`, `plan`, `implement`, `verify`,
  `review`, and `deliver`;
- each present phase contains a non-empty bounded list of strings;
- each list item may use a plain, quoted, literal block (`|-`), or folded block
  (`>-`) YAML scalar;
- literal blocks preserve line breaks; folded blocks apply YAML folding before
  validation and canonicalization;
- explicit YAML tags, duplicate keys, aliases, merge keys, custom tags, control
  characters, non-string constraints, and unknown fields are rejected;
- canonical content is normalized JSON from the validated model, with SHA-256
  computed over its UTF-8 bytes;
- list order and scalar content after YAML parsing are meaningful; scalar style,
  indentation, and mapping-key order are not;
- `global` and each phase list contain at most 16 items;
- each parsed constraint contains 1–1,024 UTF-8 bytes after normalization;
- canonical constraint content contains at most 4,096 UTF-8 bytes;
- the fully rendered card body contains at most 8,192 characters, matching the
  supported Hermes v0.18.2 worker-context boundary proven in Phase 1;
- oversized canonical content or card projection is rejected, never truncated.

The artifact is immutable and workflow-owned. Its reference records revision,
path, digest, and recording time. Revisions are contiguous and append-only.
A workflow without constraints has explicit null identity and no implied defaults.

Implementation ownership:

- `wingstaff/constraints.py` — parsing, canonicalization, source materialization,
  and rendering;
- `wingstaff/state.py` — immutable artifact, reference, provenance, approval, and
  policy-revision models;
- `wingstaff/workflow.py` — deterministic recording and invalidation transitions;
- `wingstaff/execution.py` — exclusive artifact writes and digest verification;
- `wingstaff/store.py` — optimistic persistence of the extended ledger.

## Reusable policy skills

A reusable constraint source is an exact installed Hermes policy skill containing
only a `wingstaff.workflow-constraints/v1` document and bounded descriptive skill
metadata. Hermes owns skill installation, discovery, and loading. Wingstaff:

- resolves the source by exact skill name;
- verifies the installed source digest supplied by the caller;
- validates and canonicalizes its constraint document;
- snapshots canonical content into the workflow-owned artifact;
- records source name and source digest as provenance;
- keeps the policy skill separate from pack-stage methodology candidates,
  required/conditional activation, and attention ranks;
- never needs the source again after successful materialization.

One-off constraint content and a reusable policy skill use the same validation,
materialization, persistence, projection, approval, and replacement paths. They
are mutually exclusive inputs.

The host integration gate must prove that exact skill content can be resolved,
digest-verified, snapshotted, and represented separately from pack activation.
Failure blocks implementation and requires an amended, separately approved plan;
Wingstaff must not introduce a second skill-loading or activation system.

Likely integration points:

- `wingstaff/skills.py` — exact installed-skill inventory and digest verification;
- `wingstaff/constraints.py` — policy-skill document extraction and materialization;
- `tests/test_constraints.py` — source validation, digest, disappearance, and
  activation-separation cases.

## Persistence and idempotency

`WorkflowLedger` stores append-only constraint references and exposes the current
reference. `WorkflowConstraintsArtifact` contains workflow ID, policy revision,
constraint revision, canonical content, and optional source provenance. The
constraint digest covers canonical constraint content; provenance is validated
and reported separately.

Recording enforces:

- contiguous revisions beginning at 1;
- compare-and-swap against the expected current constraint digest, including an
  explicit no-constraints expectation;
- monotonic timezone-aware timestamps;
- exclusive artifact creation followed by read-back digest verification;
- optimistic store concurrency;
- idempotency when canonical content equals the current content.

Semantically identical content allocates no revision, invalidates no approval,
archives no card, and removes no worktree. Differently formatted YAML with the
same parsed strings and list order is semantically identical.

## Card and worker integration

Every executable card receives a delimited `Workflow constraints` section with:

- workflow ID and named board;
- policy revision;
- constraint revision and digest;
- immutable artifact path;
- all global constraints;
- only the current phase's constraints;
- instructions to block on conflicts or methodology-like content rather than
  weaken higher-level policy.

Constraint identity participates in card references and idempotency keys.
Workers compare card identity with current Wingstaff status after `kanban_show`
and before applying methodology or submitting evidence.

Constraint identity is carried by:

- finalized activation manifests;
- successful and blocked handoffs;
- definition, plan, implementation, verification, review, and delivery evidence;
- exact human approval.

The policy skill remains separate from the pack candidate list and activation
manifest ranks. Constraint text never grants tools, credentials, permissions,
commit authority, push authority, or an exception to higher-level policy.

Implementation ownership:

- `wingstaff/kanban.py` — deterministic projection and policy-aware card identity;
- `wingstaff/service.py` — current-identity validation and coordination;
- `wingstaff/skills/orchestrate/SKILL.md` — worker comparison and blocking
  contract;
- `tests/test_kanban.py`, `tests/test_worker_contract.py`, and
  `tests/test_execution.py` — projection and stale-worker behavior.

## Approval and graph revision

Approval binds the exact tuple:

```text
(plan_revision, plan_digest, constraints_revision, constraints_digest)
```

A changed constraint revision:

1. persists the new immutable artifact and policy identity;
2. clears approval before host cleanup;
3. makes prior activation, artifacts, evidence, and cards historical;
4. removes a Wingstaff-owned worktree through the ownership guard;
5. comments on and archives obsolete cards through public Hermes operations;
6. creates a fresh `define -> plan` graph under the new policy revision;
7. requires regenerated definition and plan artifacts;
8. requires renewed exact plan-and-constraint approval.

Interrupted cleanup and graph recreation are idempotently recoverable and never
restore stale approval. Public Hermes Kanban operations remain the only card
boundary; Wingstaff does not import host internals or access Kanban SQLite.

Implementation ownership:

- `wingstaff/workflow.py` — approval tuple and pure invalidation transitions;
- `wingstaff/service.py` — durable-before-host mutation ordering and recovery;
- `wingstaff/kanban.py` — comment, archive, and graph recreation;
- workflow, Kanban, and execution tests — replacement at every lifecycle point,
  concurrency, failed archival, failed recreation, and retry.

## Tool and operator surfaces

`wingstaff_start` accepts at most one constraint source:

- inline `constraints` content; or
- `constraints_skill` with mandatory `expected_constraints_skill_digest`.

The CLI accepts explicit, mutually exclusive selectors:

- `--constraints-file PATH`;
- `--constraints-skill NAME` with
  `--expected-constraints-skill-digest DIGEST`.

No interface infers a path or skill name from arbitrary text.

A replacement operation accepts:

- workflow ID;
- expected current constraint digest or explicit no-constraints expectation;
- one-off content or an exact policy-skill source.

Status reports workflow constraint identity and source provenance separately.
Replacement reports approval invalidation, archived cards, worktree impact, and
next action. Tool handlers remain `args: dict, **kwargs`, return JSON strings,
reject unknown fields, and share one service path with native and standalone CLI
commands.

Implementation ownership:

- `wingstaff/service.py` — start, status, and replacement operations;
- `wingstaff/schemas.py` — strict model-facing schemas;
- `wingstaff/tools.py` and `wingstaff/__init__.py` — handlers and registration;
- `wingstaff/cli.py` — explicit file and skill selectors;
- `tests/test_tools.py`, `tests/test_plugin.py`, and `tests/test_cli.py` — schema,
  dispatch, mutual exclusion, compare-and-swap, and parity.

Changing the public start surface requires synchronizing every consumer listed in
`wingstaff/AGENTS.md`.

## Host integration requirements

An isolated supported Hermes profile and named board must prove:

- exact policy-skill resolution and digest verification;
- separation of policy skills from pack activation metadata;
- full bounded constraint projection without card-body truncation;
- create, show, comment, dependency, complete, and archive behavior through public
  Kanban operations;
- archival of obsolete nonterminal cards and recreation with distinct idempotency
  keys;
- stale-card and stale-worker rejection;
- materialized workflow operation after the source skill changes or disappears.

No fallback may use private Hermes imports, direct Kanban database access,
digest-only card projection, a daemon, an MCP server, or nested `hermes chat`.

## Release compatibility regression

After the feature and operator documentation are complete, make the Phase 1 host
findings durable rather than leaving them only in this plan:

1. Document the 8,192-character worker-context body boundary, the 4,096-byte
   canonical constraint budget, exact policy-skill discovery, and public Kanban
   lifecycle dependency in `docs/01-architecture.md` and
   `docs/08-hermes-integration.md`. Keep the architecture document focused on
   why Wingstaff rejects oversize projections; keep observed host versions and
   probe evidence in the integration document.
2. Add a dependency-free script under `scripts/` that creates an isolated
   `HERMES_HOME`, installs a synthetic exact policy skill, verifies its exact
   inventory name and deterministic Wingstaff directory digest, exercises a
   named-board create/show/comment/link/complete/archive lifecycle, and proves
   that 8,192-character bodies remain intact while larger bodies are visibly
   truncated. The script must never inspect or mutate the active profile.
3. Add subprocess regression tests under `tests/` for successful probe parsing,
   changed or missing host output, boundary drift, cleanup, and actionable
   failure messages. Do not mock Wingstaff's canonicalization or digest code.
4. Integrate the live compatibility probe into `.github/workflows/release.yml`
   as a release-only job. It runs for version tags and explicit
   `workflow_dispatch`, and may run when the declared supported Hermes version
   changes. It must not run for every branch push or pull request. Fast unit and
   packaging checks remain eligible for normal CI.
5. Require a green probe before changing the supported Hermes baseline or
   publishing a Wingstaff release. Record the exact Hermes semantic version,
   build version, and upstream revision in `docs/08-hermes-integration.md`; any
   changed boundary blocks release until code, limits, tests, and documentation
   are reconciled.

The probe is compatibility evidence, not a runtime dependency. Wingstaff still
uses only public plugin, skill, and Kanban boundaries in production.

## Verification

Targeted gates:

```bash
pytest tests/test_constraints.py tests/test_workflow.py tests/test_store.py tests/test_execution.py
pytest tests/test_kanban.py tests/test_worker_contract.py tests/test_execution.py
pytest tests/test_tools.py tests/test_plugin.py tests/test_cli.py
ruff check wingstaff tests
```

Required cases:

1. Workflows without constraints preserve explicit null identity.
2. Plain, quoted, literal, and folded YAML strings parse and canonicalize as
   specified.
3. Invalid YAML structures, explicit tags, forbidden fields, controls, and bounds
   fail closed.
4. Global and phase-specific constraints project only to intended scopes on all
   executable cards.
5. One exact policy skill materializes identical content for workflows on two
   boards without making policy board-global.
6. Policy skills never join pack activation modes or attention ranks.
7. Methodology-like free text blocks for correction.
8. Identical content is idempotent; changed content invalidates approval,
   worktree, activation, artifacts, evidence, and graph without deleting history.
9. Stale source digests, stale workflow digests, stale workers, concurrent writers,
   interrupted writes, failed archival, and failed recreation fail closed.
10. Source disappearance does not invalidate materialized workflow artifacts.
11. Addyosmani and AI-DLC use the same pack-neutral path.

Repository gate:

```bash
lefthook validate
pytest
ruff check .
wingstaff packs validate addyosmani
wingstaff packs validate aidlc
python -m build
python -m twine check dist/*
python scripts/check_release_contents.py . --wheel dist/*.whl
python scripts/check_md_links.py .
git diff --check
```

Every published command must also pass an isolated supported-host probe.

## Documentation contract

After implementation, update `README.md`, `docs/01-architecture.md`,
`docs/08-hermes-integration.md`, `docs/14-workflow-constraints.md`,
`docs/README.md`, and owning AGENTS.md files. Document only commands exercised
against the supported host. Explain workflow scope, the policy/methodology
boundary, policy-skill materialization, the profile/lane/board/workflow/
constraint topology, inspection, replacement, invalidation, worktree impact, and
recovery.

## Market-overview constraint fit

This plan also governs how the constraint layer relates to projects assessed in
[Workflow ecosystem market overview](../12-market-overview.md). The assessment
below asks whether projects that were not direct workflow-pack matches can become
reusable constraint sources or otherwise benefit from the policy contract defined
in [Workflow constraints](../14-workflow-constraints.md).

No assessed project becomes a direct reusable constraint source. Such a source
must be an exact installed Hermes policy skill whose bounded content is only a
`wingstaff.workflow-constraints/v1` document. Existing workflow specifications,
methodologies, products, and tool configurations must not be accepted directly or
translated in a way that imports their runtime, procedures, or activation model.

| Project | Existing pack assessment | Constraint fit | Decision |
|---|---:|---|---|
| Open Agent Spec | 2/5 | Partial | Keep as future stage-contract interoperability; its evaluation and boundary declarations may inform separately curated constraints. |
| Open Design | 3.5/5 | Partial | Artifact invariants may inform constraints after Wingstaff can verify the required rendered or binary evidence. |
| Spec Kit Agent Skills | 2.5/5 | Partial to weak | Constitution principles may inform policy, but the CLI workflow, generated tasks, scripts, and license boundary remain outside constraints. |
| Superpowers and Matt Pocock Skills | 4/5 each | Compatibility mechanism | Keep as methodology-pack candidates; use constraints to test whether Wingstaff can bound their commit, tracker, worktree, setup, and delivery side effects. |
| BMad Method, Get Shit Done Skills, and AWS Kiro | 1–2/5 | No direct fit | Constraints do not resolve competing runtime, provenance, testing, licensing, or proprietary-source failures. |

Open Agent Spec has the strongest conceptual overlap because required inputs,
outputs, sandbox boundaries, and evaluation acceptance criteria are
constraint-shaped. Its prompts, models, tools, task dependencies, composition,
and runner behavior remain executable configuration and are prohibited constraint
content. An Open Agent Spec graph must not become a second Wingstaff workflow.

Open Design can supply output properties and release boundaries, such as
conformance to an approved design system, required export dimensions, rendered
visual evidence, or accessibility findings that block delivery. Its design loop is
methodology, and its daemon, CLI, model proxy, and MCP integration are tooling.
Constraints may require provable artifact properties but do not replace the
pack-neutral evidence model needed to prove them.

Spec Kit constitutions may contain durable policy invariants, such as requiring
public behavior to be specified or changed contracts to be documented. Its
clarification, planning, task generation, implementation sequence, external CLI,
`.specify/` state, and helper scripts remain methodology and tooling. Any reusable
policy would require a separately authored, provenance-checked policy skill and
license review; it would not be direct reuse of the existing conversion.

For Superpowers and Matt Pocock Skills, constraints improve compatibility without
changing classification. Prohibitions on commits, pushes, external issue creation,
worktree ownership, or unapproved repository setup can bound side effects while
the selected skills continue to provide methodology. Pack spikes must still prove
that workers obey current workflow constraints over conflicting skill instructions;
a constraint cannot silently rewrite or misrepresent an upstream skill.

BMad, Get Shit Done Skills, and Kiro remain unsuitable. A declarative policy layer
does not make a competing workflow framework pack-neutral, establish missing
license or behavioral provenance, or turn a proprietary product into a pinnable
Hermes source.

The immediate follow-up after plan approval is documentation and spike scoping,
not another adapter implementation:

1. Keep Open Agent Spec classified as interoperability and record that its
   evaluation and boundary declarations are possible inputs to policy curation.
2. Add workflow constraints as the explicit compatibility mechanism tested by the
   curated Superpowers and Matt Pocock pack spikes.
3. Keep Open Design and Spec Kit invariants observational until a concrete,
   independently verifiable policy-only source is justified.

Any proposal to import one of these projects directly as constraint content, infer
constraints from executable configuration, or create another runner, activation
layer, or methodology system meets this plan's stop conditions. Updating the
market overview with these implications is deferred until this plan is approved;
no project rating or implementation status changes as part of this plan.

## Acceptance criteria

- Workflow constraints are workflow-scoped policy artifacts.
- Packs remain the only per-workflow methodology and skill-activation selection.
- Constraints contain policy invariants, not procedures, tools, commands, or
  activation overrides.
- YAML constraint items support plain, quoted, literal, and folded strings with
  canonical identity based on parsed content.
- Reuse uses exact Hermes policy skills without joining pack activation.
- Materialization creates a self-contained immutable workflow artifact.
- The documented profile, worker-lane, board, workflow, and constraint topology
  preserves Hermes lifecycle authority and distinguishes it from Wingstaff
  approval.
- Approval and every current card, handoff, activation, and evidence operation
  bind current constraint identity.
- Changed constraints invalidate stale approval and work; identical content is
  idempotent.
- Hermes Kanban remains the only operational-status authority.
- No daemon, dashboard, MCP server, direct Kanban database access, private Hermes
  import, nested `hermes chat`, automatic commit, or push is introduced.

## Stop conditions

Stop implementation and ask the user when:

- skill-backed reuse would create another methodology or activation layer;
- public Hermes APIs cannot archive and recreate stale cards safely;
- full bounded constraint text cannot fit cards;
- stale evidence or workers cannot be invalidated;
- requirements expand to automatic fan-out, live links, composition, parameters,
  or per-workflow procedural overrides;
- a constraint must override required skills or deterministic safety;
- any verification gate fails.

## Approval checkpoint

No implementation starts until the user explicitly approves this plan. The host
integration requirements must pass before reusable-source APIs are implemented.
