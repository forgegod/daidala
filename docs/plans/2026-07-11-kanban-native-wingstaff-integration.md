# Kanban-native Wingstaff integration implementation plan

> Status: approved on 2026-07-11; Phase 3 is done.
>
> For the implementing agent: read `/AGENTS.md`, `wingstaff/AGENTS.md`,
> `tests/AGENTS.md`, `docs/AGENTS.md`, this plan, the current official Hermes
> [Kanban](https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban)
> and [worker-lane](https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban-worker-lanes)
> documentation, and the live host tool schemas before each phase. Stop when a
> verification gate fails. Do not infer unsupported Kanban operations.

## Execution status

A phase becomes `Done` only after its verification gate passes. The next phase
remains `Todo` until the completed phase commit is pushed. Exactly one phase may
be in progress.

| Phase | Status | Next condition |
|---|---|---|
| 0 — verify the live Hermes boundary | Done | Preserve the v0.18.2 public capability matrix and agent-only dispatch boundary. |
| 1 — define the Kanban-native contract | Done | Preserve one Kanban authority, one policy ledger, and the exact card/handoff/recovery contract. |
| 2 — replace workflow state with a policy ledger | Done | Preserve the status-free ledger, fresh persistence schema, exact skill provenance, and migrated consumers. |
| 3 — build the Kanban graph adapter | Done | Preserve the explicit board/profile map, approval-gated graph, strict host parsing, and live read-only status. |
| 4 — adapt workers, artifacts, and recovery | Done | Preserve card-pinned worker instructions, structured handoffs, same-card recovery, and immutable retry evidence. |
| 5 — simplify the CLI and operator experience | Done | Preserve public Kanban CLI translation, one default profile with explicit overrides, and combined diagnostics. |
| 6 — rewrite product and integration documentation | Todo | Start only after Phase 5 is pushed. |
| 7 — end-to-end and release verification | Todo | Start only after Phase 6 is pushed. |

## Goal

Make Hermes Kanban the canonical user-visible lifecycle, coordination surface,
and audit trail for Wingstaff workflows while retaining Wingstaff as the
software-delivery policy and workflow-pack layer that Hermes does not provide.

A user should create, inspect, comment on, approve, retry, reassign, and review
Wingstaff work through familiar Hermes Kanban surfaces. Wingstaff should no
longer expose a competing user-visible workflow state machine.

## Product position

### What Hermes already provides

Hermes owns the general multi-agent runtime:

- boards, cards, dependencies, assignment, and promotion;
- named profile and orchestrator worker lanes;
- claims, heartbeats, retries, crash recovery, timeouts, and run history;
- comments, blocking, unblocking, attachments, and human interaction;
- dashboard, CLI, slash-command, gateway, and notification surfaces;
- workspaces and worktrees for task execution.

Wingstaff must use these facilities rather than recreate them.

### Wingstaff's value add

Wingstaff turns generic Hermes Kanban into a controlled software-delivery
workflow. Its durable value is:

1. **Interchangeable workflow packs.** Map Addy Osmani, AI-DLC, and future
   skill sets onto a common delivery contract without adding pack-specific
   branches to the engine.
2. **Supply-chain validation.** Require exact skill names, pinned source
   revisions, bounded Hermes compatibility, and complete-directory digests.
3. **Plan-bound approval.** Bind human authorization to the SHA-256 digest of
   the complete plan and invalidate authorization when that plan changes.
4. **Repository safety.** Require a clean baseline and isolate implementation
   in a Wingstaff-owned detached Git worktree.
5. **Evidence integrity.** Capture an immutable implementation diff, changed
   paths, exact verification commands, exit codes, output, and review artifacts.
6. **Conservative delivery.** Produce a reviewed diff without silently
   committing or pushing target changes.
7. **Pack-neutral policy enforcement.** Keep deterministic validation and state
   checks in Python while leaving definition, planning, implementation, and
   review judgment to Hermes workers and skills.

Concise positioning for the README:

> Wingstaff is the software-delivery policy and workflow-pack layer for Hermes
> Kanban. Hermes owns the board and worker lifecycle; Wingstaff adds exact skill
> provenance, digest-bound approval, safe Git worktrees, and evidence-backed
> delivery—without another server or dashboard.

## Replacement rule

Implement the target architecture as the only Wingstaff architecture. The
existing runtime has not been released or used in production, so its state
model, schemas, tools, and documentation impose no compatibility contract.
Delete or replace conflicting code directly and implement one clean design from
scratch. Do not retain alternate readers, aliases, dual writes, or explanatory
breadcrumbs for removed behavior.

## Target architecture

### Authority split

| Concern | Authority |
|---|---|
| Board, card status, dependencies, assignment, claims, retries, comments, run history | Hermes Kanban |
| User-visible progress and recovery | Hermes Kanban CLI, slash command, dashboard, and gateway |
| Pack selection and stage-to-skill mapping | Wingstaff |
| Skill provenance and compatibility validation | Wingstaff |
| Repository baseline and worktree policy | Wingstaff |
| Plan digest and approval integrity | Wingstaff policy ledger |
| Artifact digests and verification evidence | Wingstaff policy ledger plus Kanban handoff metadata/comments |
| Commit/push authorization | Wingstaff; unavailable unless separately authorized |

Wingstaff's persistence becomes a policy and artifact-integrity ledger. It may
record workflow identity, board/card IDs, baseline commit, pack revision,
artifact references, approval digest, and delivery evidence, but it must not
publish a second operational status vocabulary.

### Kanban graph

The normal graph is:

```text
define → plan → HUMAN APPROVAL → implement → verify → review → deliver
```

The graph is created incrementally:

1. `wingstaff_start` validates the pack, exact skills, host capabilities, and
   clean repository baseline, then creates `define` and dependent `plan` cards.
2. The definition and plan workers complete their cards with structured
   artifact handoffs.
3. Wingstaff records the plan artifact and digest and surfaces an approval gate
   on the board.
4. Explicit human approval must name the current plan digest. A generic Kanban
   unblock is not sufficient authorization.
5. Only after approval does Wingstaff create or release `implement`, `verify`,
   `review`, and `deliver` cards with real dependency links.
6. The post-approval cards share the persistent Wingstaff worktree through an
   explicitly supported absolute workspace mapping.
7. Every worker terminates its Kanban run with `kanban_complete` or
   `kanban_block`; Wingstaff policy tools validate and record stage evidence but
   do not independently declare the workflow operationally complete.

### Human approval

Hermes blocking is the interaction mechanism; Wingstaff remains the approval
validator.

The implementation must prove which supported public Kanban operation can
represent the gate. Preferred behavior:

- the plan card completes only after emitting the plan artifact and digest;
- an approval card or board-visible gate is blocked with a reason containing
  the workflow ID and digest;
- `hermes wingstaff approve <workflow-id> <digest>` records the decision and
  advances/completes that gate through documented host APIs;
- changing the plan creates a new digest, invalidates approval, and prevents
  implementation promotion.

Do not equate `hermes kanban unblock` with approval. If the host cannot enforce
that distinction through public APIs, retain a blocked approval card as the
user-visible representation while Wingstaff creates post-gate cards only after
its own approval command succeeds.

### Worker handoffs

Each stage completion must include a concise summary and structured metadata:

- `workflow_id`, `stage`, `pack`, and `pack_revision`;
- artifact path and digest where applicable;
- worktree path for post-approval stages;
- changed files and implementation diff reference;
- verification commands, exit codes, and output references;
- approval digest or review decision where applicable.

Kanban comments carry durable human-readable context. Wingstaff's artifact
store remains the integrity source for large or immutable evidence. Do not copy
large artifacts into card prose.

## Explicit scope

### In scope

- Kanban-native stage graph and dependency handling;
- board-visible approval and explicit digest validation;
- a narrow policy ledger with no operational task statuses;
- reusable persistent worktree across implementation, verification, and review;
- recoverable verification and review blocking;
- operator guidance centered on normal Hermes Kanban surfaces;
- README and numbered-document rewrite led by Wingstaff's value add;
- compatibility probing against the current supported Hermes host.

### Out of scope

- a Wingstaff dashboard, daemon, HTTP API, MCP server, or scheduler;
- a custom external worker lane when a Hermes profile lane is sufficient;
- direct writes to Hermes Kanban SQLite;
- importing private Hermes Kanban internals;
- automatic target commit, push, merge, or pull-request creation;
- multi-host boards;
- support machinery for unreleased runtime state or removed tools.

## Phase 0 — verify the live Hermes boundary

### Objective

Prove the current host API before freezing the graph design. The repository's
current compatibility statement is limited to Hermes v0.18.2, while current
Kanban documentation includes boards, worker lanes, richer blocking, goal mode,
and diagnostics that may not exist in that version.

### Read and probe

- current official Kanban and worker-lane documentation;
- installed `hermes --version` and plugin API documentation;
- live `kanban_create`, `kanban_complete`, `kanban_block`, `kanban_unblock`,
  comment, parent-link, skills, workspace, board, and idempotency schemas;
- `ctx.dispatch_tool` behavior for every operation Wingstaff needs;
- worker tool availability and task scoping;
- named-board selection and gateway dispatcher behavior.

Use an isolated `HERMES_HOME`; do not mutate the active profile or its board.
Do not read or write Kanban SQLite directly.

### Decision record

Record a capability matrix in
`docs/plans/2026-07-11-kanban-native-wingstaff-integration.md` during execution
or in `docs/08-hermes-integration.md` once implemented. Choose and document a
minimum supported Hermes version that exposes the required public operations.
Do not retain v0.18.2 support if doing so requires a second orchestration path.

### Verified capability matrix

The isolated probe ran against Hermes Agent v0.18.2 (`7acaff5e`) with a named
board and no gateway or live profile state. It used only `hermes kanban`,
worker `kanban_*` tools, and `PluginContext.dispatch_tool`; it did not import
Kanban modules or read the board database.

| Required capability | Public operation | Observed result |
|---|---|---|
| Named board selection | `hermes kanban --board <slug> ...` and tool `board` argument | Separate board created and selected without changing the active board. |
| Assignee discovery | `hermes kanban assignees --json` | Existing `hermes-vc` profile reported `on_disk: true`; no inferred fallback is required. |
| Exact skill pins | `create --skill` / `kanban_create.skills` | Created cards retained the exact requested skill list. |
| Linked cards | `create --parent` / `kanban_create.parents` | `plan` remained `todo` until `define` completed, then promoted to `ready`. |
| Structured worker handoff | `kanban_complete(summary, metadata)` | Closing run retained summary, workflow/stage metadata, artifact digest, and worker session ID. |
| Blocked human gate | `create --initial-status blocked`, comment, and unblock | Gate was board-visible; a reasoned unblock returned it to `ready`. |
| Digest-specific authorization | Wingstaff policy check before host release | Host unblock is interaction only; Wingstaff must retain the exact-digest check and create no post-gate cards before it passes. |
| Shared persistent workspace | absolute `dir:<path>` / `workspace_kind=dir` plus `workspace_path` | Linked cards retained the same absolute path; relative-path fallback is unnecessary. |
| Retry-safe creation | `idempotency_key` | Separate CLI processes and repeated plugin dispatch returned the same task IDs. |
| Plugin host dispatch | `PluginContext.dispatch_tool("kanban_create", ...)` | In-session agent process returned structured success and created one retry-safe card. |
| Worker tool boundary | task-scoped `kanban_show`, `complete`, `block`, `heartbeat`, `comment`, `create`, and `link` | Worker completion succeeded through the injected task-scoped toolset; orchestrator-only list/unblock remain separate. |
| Gateway dispatcher compatibility | `hermes kanban dispatch --dry-run --json` | Ready cards resolved to the named `hermes-vc` profile without spawnability errors. |

Minimum supported Hermes remains v0.18.2. The required graph, gate
representation, absolute shared workspace, structured handoff, idempotency,
and plugin dispatch are all available through public operations. Phase 1 must
specify one named board per workflow and must treat generic unblock as
insufficient authorization.

One host-boundary asymmetry is now explicit: `PluginContext.dispatch_tool`
works in an agent process after built-in tools load, but a plugin CLI
subcommand started outside the agent process returned `Unknown tool:
kanban_create`. Wingstaff runtime graph operations therefore remain
agent/plugin-tool operations. Operator CLI commands may update Wingstaff policy
and invoke documented Kanban CLI behavior, but must not assume the in-agent
tool registry exists or add a private-import fallback.

Phase 0 gate: GREEN — isolated named-board graph, exact skills, absolute shared
workspace, structured worker completion, blocked gate/release, restart-safe
idempotency, in-agent `PluginContext.dispatch_tool`, and dispatcher dry-run all
passed; repository gate passed with 22 Markdown files, 97 tests, Ruff, both
pack validations, build, Twine, release-content audit, and diff checks.

### Verification gate

An isolated real-host probe must demonstrate:

- creation of two linked cards with exact skills;
- board/workspace selection;
- structured completion handoff from a worker;
- blocked human gate and controlled release path;
- idempotent creation after process restart;
- no private import or database access.

Stop and ask if the public API cannot safely represent the approval gate or
shared persistent workspace.

### Commit boundary

`test: probe kanban-native Wingstaff host capabilities`

## Phase 1 — define the Kanban-native contract

### Objective

Establish the single authority model before changing runtime code.

### Files

- update this plan with Phase 0 findings;
- rewrite the applicable parts of
  `docs/plans/2026-07-10-wingstaff-bootstrap-and-roadmap.md` so it directly
  describes the Kanban-native design;
- update `docs/01-architecture.md` with the new authority split and component
  diagram;
- update `docs/02-workflow-state.md` to specify the policy ledger rather than a
  second operational state machine;
- update `docs/05-lifecycle-stages.md` with the card graph, stage handoffs, and
  approval behavior;
- update `docs/08-hermes-integration.md` with the verified host version and APIs.
- update `docs/README.md`, `docs/06-security.md`, `docs/07-runbook.md`, and
  `docs/AGENTS.md` because their current support, security, ownership, and
  recovery claims otherwise contradict the authority split.

### Required decisions

- exact card creation order and parent links;
- exact approval-card representation;
- board selection rule, preferably one named board per project or an explicit
  caller-selected board;
- assignee mapping from pack stage to existing profile;
- shared workspace representation supported by the probed host;
- evidence metadata schema;
- worker block/retry semantics for verification and review failures.

### Phase 1 decision record

- The caller selects one existing named board per workflow; Wingstaff never
  changes or relies on the global current-board pointer.
- The caller supplies one default Hermes profile plus optional stage overrides.
  Wingstaff expands and validates all stage assignees before creating any card.
- Initial graph: `define -> plan -> approval`. The approval card is created only
  after the plan digest exists, links to `plan`, and starts blocked.
- Post-gate graph: `approval -> implement -> verify -> review -> deliver`.
  Wingstaff creates it only after recording approval for the exact current plan
  digest.
- Every card uses idempotency key
  `wingstaff:<workflow-id>:<plan-revision>:<stage>`, real parent links, exact pack
  skills, and the expanded stage profile.
- All post-gate cards use one absolute Wingstaff-owned worktree. No scratch or
  relative workspace fallback is permitted.
- Generic Kanban unblock never grants approval. Agent-facing tools use
  `PluginContext.dispatch_tool`; operator CLI handlers use documented
  `hermes kanban` commands through an injected runner.
- Worker handoff metadata uses schema `wingstaff.handoff/v1` with required
  `workflow_id`, `plan_revision`, `stage`, `pack`, `pack_revision`, `outcome`,
  and `artifact_refs`; post-gate handoffs also require `workspace_path` and
  `baseline_commit`. Verification adds exact command, exit-code, and output
  references; implementation adds the diff and changed-path manifest.
- Workers comment before blocking. Dependencies use `dependency`, missing host
  access uses `capability`, deterministic verification/review feedback uses
  `needs_input`, and only genuinely flaky host failures use `transient`.
  Human comment/reassign/unblock resumes the same card and workspace.

Phase 1 gate: GREEN — every planned transition maps to a documented Hermes
v0.18.2 event and, where required, one Wingstaff policy check; no contract
requires bidirectional status synchronization. Documentation ownership,
support-status, security, runbook, architecture, ledger, lifecycle, compatibility,
and both plans are synchronized. Repository gate passed with 22 Markdown files,
97 tests, Ruff, both pack validations, build, Twine, release-content audit, and
diff checks.

### Verification gate

Every runtime transition in later phases must have one named Kanban event and,
where required, one Wingstaff policy check. No transition may require keeping
Wingstaff and Kanban statuses synchronized bidirectionally.

### Commit boundary

`docs: define Kanban-native Wingstaff authority and workflow`

## Phase 2 — replace workflow state with a policy ledger

### Objective

Persist only Wingstaff-owned integrity facts and Kanban identifiers.

### Files

- refactor `wingstaff/state.py`;
- refactor or replace `wingstaff/workflow.py`;
- replace `wingstaff/store.py` with the minimal policy-ledger schema;
- update `wingstaff/errors.py` for current policy violations;
- migrate direct state consumers in `wingstaff/service.py`, `wingstaff/tools.py`,
  `wingstaff/cli.py`, and registration without implementing Phase 3 host graph
  dispatch;
- rewrite state/store tests and update affected service, tool, CLI, execution,
  and installation expectations.

### Ledger model

At minimum record:

- workflow ID, board slug, target repository, baseline commit, and goal;
- pack name, source revision, and exact skill digests;
- stage-to-card IDs and idempotency keys;
- worktree path and ownership marker;
- definition, plan, implementation, verification, review, and delivery artifact
  references and digests;
- current plan digest and optional matching approval record;
- immutable delivery restrictions (`committed: false`, `pushed: false`);
- creation/update timestamps and optimistic concurrency token.

Do not store a second `ready/running/blocked/done` representation. Derived
status queries read Kanban and combine it with Wingstaff policy facts.

### Clean implementation

- define one fresh policy-ledger schema;
- remove obsolete workflow-status columns and transition machinery;
- remove obsolete databases and test fixtures from the implementation contract;
- do not recognize, inspect, translate, or resume unreleased state formats;
- do not add aliases for removed lifecycle tools.

### Tests

Cover serialization, optimistic concurrency, plan replacement invalidating
approval, exact-digest approval, card-ID idempotency, and the absence of an
operational status field in the new model.

### Verification gate

Focused state/store tests pass and a repository search shows no new code that
mirrors Kanban task status into Wingstaff persistence.

Gate: GREEN — 91 tests, Ruff, both pack validations, package build, Twine,
release-content audit, Markdown links, Lefthook validation, and status-mirroring
search passed.

### Commit boundary

`refactor: reduce Wingstaff state to policy and artifact ledger`

## Phase 3 — build the Kanban graph adapter

### Objective

Replace the single implementation-card adapter with a documented host-tool
adapter for the full workflow graph.

### Files

- rewrite `wingstaff/kanban.py`;
- refactor `wingstaff/service.py`;
- update `wingstaff/schemas.py` and `wingstaff/tools.py`;
- update registration in `wingstaff/__init__.py` if tools change;
- replace fake-host coverage in `tests/test_tools.py`, `tests/test_plugin.py`,
  and the existing Kanban tests.

### Adapter requirements

- select an explicit board and preserve it for the workflow;
- discover or validate every requested assignee before card creation;
- create cards with deterministic idempotency keys
  `wingstaff:<workflow-id>:<plan-revision>:<stage>`;
- create parent links atomically with child creation where the host supports it;
- pin exact stage skills from the selected pack;
- create no implementation-capable card before digest-bound approval;
- use documented workspace fields and absolute paths;
- parse every host result strictly and stop on invalid structured output;
- never import or write Hermes internals;
- expose read-only combined status based on Kanban data plus policy evidence.

### Tool-surface direction

Retain a small operator/model entry surface:

- `wingstaff_pack_info`;
- `wingstaff_start` to validate and create the initial graph;
- `wingstaff_approve` to validate the exact plan digest and release post-gate
  work;
- `wingstaff_status` as a read-only combined view;
- `wingstaff_cancel` for Wingstaff-owned worktree cleanup plus documented board
  action.

Stage workers may still need narrowly scoped policy/evidence tools, but those
must be described as validation and artifact-recording tools, not lifecycle
commands. Remove or rename public tools whose only purpose is advancing the old
private state machine. Make the break explicit; do not preserve aliases.

### Tests

Use TDD for:

- define → plan parent graph;
- exact skill pins per stage;
- idempotent restart with no duplicate cards;
- unknown assignee refusal;
- invalid host JSON and host rejection;
- approval mismatch and plan-change invalidation;
- absence of post-gate cards before approval;
- correct post-gate graph after approval;
- board and workspace pinning;
- combined status without mirrored state;
- cancellation and worktree cleanup.

### Verification gate

Fake-host tests prove the graph and failure semantics. A real isolated-host test
creates exactly one card per expected stage across two identical calls.

Gate: GREEN — fake-host graph and failure coverage, 97 tests, Ruff, both pack
validations, package build, Twine, release-content audit, Markdown links,
Lefthook validation, and diff checks passed. A fresh isolated Hermes v0.18.2
board received the same `define` (`t_5d3c8b81`) and `plan` (`t_6b697dc7`) card
IDs across repeated host-dispatch calls and contained exactly two cards.

### Commit boundary

`feat: map Wingstaff workflows onto Hermes Kanban graphs`

## Phase 4 — adapt workers, artifacts, and recovery

### Objective

Make each stage a valid Kanban worker lane with structured handoffs and normal
Kanban recovery.

### Files

- refactor `wingstaff/skills/orchestrate/SKILL.md`;
- update `wingstaff/kanban.py` so every executable card pins the bundled
  `wingstaff:orchestrate` worker contract in addition to its exact pack skills;
- update verification evidence persistence in `wingstaff/service.py` and
  `wingstaff/workflow.py` so retry output uses immutable content-addressed
  artifacts and repeated identical evidence remains idempotent;
- update `wingstaff/execution.py` only where shared-workspace ownership requires
  it;
- update pack YAML only if the generic stage mapping needs assignee or handoff
  metadata;
- add cross-stage integration tests under `tests/`.

### Worker contract

- call `kanban_show` first and treat its card context as the task input;
- use the card's pinned skills rather than re-deriving stage skills;
- load the bundled Wingstaff worker contract from the card itself; a worker must
  not depend on a launcher session retaining orchestration instructions;
- write artifacts through narrowly scoped Wingstaff evidence tools;
- comment durable context and complete with structured metadata;
- block through Kanban for dependency, capability, transient, review-required,
  or needs-input conditions;
- never call a Wingstaff tool merely to duplicate a Kanban status transition;
- never commit or push;
- never create a separate Hermes process or service.

### Recovery

- verification failure blocks the verification card with exact command evidence;
- a human comment plus unblock respawns the worker in the same preserved
  workspace;
- review-required code changes follow the current Hermes convention and include
  changed files, tests, diff path, and decisions in a comment;
- a changed plan cannot reuse an approved implementation graph;
- worktree cleanup occurs only after delivery, explicit cancellation, or an
  operator-approved cleanup action.

### Verification gate

Exercise interruption, crash/reclaim, verification block/unblock, review
feedback, and restart idempotency. The board history must be sufficient to
understand what happened without reading Wingstaff's SQLite file.

Gate: GREEN — every executable stage for both packs pins the bundled worker
contract plus exact pack skills; fake-host recovery exercised
`show → comment → block → restart → unblock → show → complete` on the same card
and workspace; verification retries preserve prior content-addressed output and
deduplicate identical evidence. Lefthook, Markdown links, 122 tests, Ruff, both
pack validations, package build, Twine, release-content audit, and diff checks
passed. An isolated Hermes v0.18.2 card retained `wingstaff:orchestrate` and its
pack skill in the public Kanban task record.

### Commit boundary

`feat: use Kanban worker handoffs and recovery for Wingstaff stages`

## Phase 5 — simplify the CLI and operator experience

### Objective

Make normal Hermes Kanban surfaces the default workflow interface.

### Files

- refactor `wingstaff/cli.py`;
- update CLI tests;
- update completion/registration tests if applicable.

The lifecycle service constructed by the CLI must translate Wingstaff's narrow
Kanban adapter calls into documented `hermes kanban` subprocess commands. It must
not rely on the in-agent `PluginContext.dispatch_tool` registry, import Hermes
internals, or access Kanban SQLite directly. `start` accepts one required default
profile through `--default-profile` plus repeatable
`--stage-profile STAGE=PROFILE` overrides and expands the complete map before
policy validation. Do not use `--profile`: Hermes consumes that host-level flag
before the plugin subcommand parser receives it.

### Operator flow

The documented happy path should be no larger than:

```text
hermes wingstaff start ...
hermes kanban watch            # or dashboard / /kanban
hermes wingstaff approve <workflow-id> <plan-digest>
hermes kanban show <card-id>   # inspect, comment, unblock, reassign as normal
```

`hermes wingstaff` remains responsible only for Wingstaff-specific policy:
pack checks, starting the graph, digest approval, combined diagnostics, and
owned-resource cleanup. Card operations remain under `hermes kanban`.

### Verification gate

Native and standalone parser tests pass, help output does not teach duplicate
lifecycle commands, and every published command has been exercised against the
supported Hermes version.

Gate: GREEN — shared parser and fake-command coverage passed; an isolated
directory plugin on Hermes v0.18.2 exercised native `start`, combined `status`,
exact-digest `approve`, and `cancel` through documented `hermes kanban`
subprocess operations, producing the full approval-gated graph and archiving it
without importing Hermes internals or reading Kanban SQLite. Standalone `start`
and combined `status` produced the same graph boundary. Native help exposed one
lifecycle command set and used `--default-profile`, avoiding Hermes' reserved
`--profile` option. Lefthook, 22-file Markdown links, 128 tests, Ruff, both pack
validations, package build, Twine, release-content audit, and diff checks passed.

### Commit boundary

`refactor: make Hermes Kanban the Wingstaff operator surface`

## Phase 6 — rewrite the product and integration documentation

### Objective

Lead with Wingstaff's value add and make the Hermes/Wingstaff authority split
obvious before implementation details. Give a new operator one user-centric,
executable path from an installed plugin to a running first workflow; architecture
documents must support that path rather than serve as the starting point.

### README.md

Rewrite the opening sections in this order:

1. **One-sentence value proposition** using the wording in Product position.
2. **What Wingstaff adds to Hermes** with the seven concrete value points:
   packs, provenance, approval, Git safety, evidence, conservative delivery,
   and pack neutrality.
3. **How it integrates**: in-process plugin, Kanban graph, standard profile
   lanes, existing gateway dispatcher, no new server/dashboard/database access.
4. **Workflow diagram** showing Kanban cards and the digest-bound human gate.
5. **Operator quick start** with prerequisites, one minimal profile mapping, the
   exact verified workflow-start entry point, normal Kanban observation, and
   explicit digest approval. Link to `docs/00-getting-started.md` for the complete
   walkthrough. Do not advertise `hermes wingstaff start` if Phase 5 has not
   proved graph creation from that process against the supported Hermes host.
6. **Current support and limits**, including supported Hermes version,
   local/single-host scope, and no automatic commit/push.
7. Development and source-grounded documentation links.

Remove the stale statement that the canonical operator interface “will be”
`hermes wingstaff`; it is already implemented. Avoid describing durable private
workflow state as a product feature after the refactor.

### Numbered documentation

- `docs/README.md`: lead with the value-add and authority split; update support
  status, lifecycle diagram, reading order, and symptom routing.
- Create `docs/00-getting-started.md` as the user-facing starting point. It must
  walk through plugin readiness, board and profile prerequisites, starting the
  gateway dispatcher, selecting a pack and stable workflow ID, starting the
  workflow, observing `define` and `plan`, approving the exact plan digest, and
  following the post-gate cards through delivery. Use one profile for every
  stage in the minimal example and explain that dedicated stage profiles are
  optional.
- In `docs/00-getting-started.md`, explain the trigger and runtime boundary in
  operator terms: a workflow starts through an explicit Wingstaff start action,
  not through an implicit cron; `wingstaff_start` validates inputs and creates
  the initial linked Kanban cards; the gateway's Kanban dispatcher is the only
  unattended runtime that claims ready cards. Cron may prompt an agent to start
  a workflow as an optional external trigger, but Wingstaff owns no scheduler,
  daemon, or polling loop.
- In `docs/00-getting-started.md`, include a concise technical-background section
  explaining why Hermes issue #34977 does not determine Wingstaff routing:
  Wingstaff selects the board explicitly, assigns every executable stage to an
  explicit profile, and creates the graph directly rather than relying on global
  `kanban.orchestrator_profile` goal decomposition. State any remaining
  agent-process versus standalone-CLI limitation exactly as Phase 5 verified it.
- `docs/01-architecture.md`: replace the dual-authority component/process
  diagrams with Kanban as lifecycle truth and Wingstaff as policy adapter.
- `docs/02-workflow-state.md`: rename/reframe content around the policy ledger,
  approval integrity, card identity, and artifact evidence.
- `docs/03-pack-reference.md`: document any generic assignee/handoff additions.
- `docs/04-authoring-packs.md`: explain how a pack maps stages to Kanban cards
  without engine branches.
- `docs/05-lifecycle-stages.md`: document card inputs, outputs, links, block
  behavior, and structured metadata.
- `docs/06-security.md`: clarify that Kanban unblock is not digest approval;
  retain worktree, secrets, provenance, and commit/push boundaries.
- `docs/07-runbook.md`: replace duplicate status/recovery procedures with normal
  Kanban CLI/dashboard operations and Wingstaff-specific approval/cleanup.
- `docs/08-hermes-integration.md`: record the minimum verified Hermes version,
  public host APIs, worker lanes, board selection, and gateway requirement.
- `docs/09-pack-adapters.md`: describe both packs as Kanban graph mappings.
- `docs/AGENTS.md`: register `00-getting-started.md` as the owner of first-run
  operator guidance and preserve the user-centric documentation contract.
- `docs/plans/2026-07-10-wingstaff-bootstrap-and-roadmap.md`: rewrite affected
  sections to describe only the Kanban-native architecture; remove obsolete
  lifecycle and authority statements rather than preserving a decision trail.

### Documentation acceptance criteria

A reader must be able to answer, from README.md alone:

- What must be installed or running before the first workflow starts?
- What exact action starts a workflow, and which verified surface accepts it?
- What happens immediately after start, and what component runs ready cards?
- Is cron required, optional, or absent from Wingstaff's runtime?
- Why does the global Hermes orchestrator-profile limitation not route
  Wingstaff's stage cards?
- Why use Wingstaff instead of plain Hermes Kanban?
- Which system owns task status and retries?
- How is human approval stronger than a normal unblock?
- How do workflow packs affect workers?
- Where are code changes made and what evidence is retained?
- Does Wingstaff add a server, dashboard, model client, or commit/push behavior?

The README quick start and `docs/00-getting-started.md` walkthrough must agree and
must be executable against the supported Hermes version. Every command or
agent-facing action must identify where it runs, its required inputs, the
observable Kanban result, and the next human action. The walkthrough must include
the approval stop and must not imply that generic Kanban unblock authorizes
implementation.

### Verification gate

```bash
python scripts/check_md_links.py .
```

Audit every runtime claim against source, tests, and current official Hermes
documentation. Mermaid diagrams must show Wingstaff inside Hermes and must not
show a competing board, daemon, or dashboard.

### Commit boundary

`docs: explain Wingstaff value on top of Hermes Kanban`

## Phase 7 — end-to-end and release verification

### Objective

Prove one complete workflow through the real supported host boundary.

### Required scenarios

1. Addyosmani happy path from start through delivery.
2. AI-DLC happy path through the same engine with no pack-name branch.
3. Plan modification invalidates approval and prevents implementation.
4. Verification failure blocks, preserves evidence, and resumes after comment
   and unblock.
5. Worker interruption/restart creates no duplicate card or worktree.
6. Unknown/deleted assignee remains visible and diagnosable.
7. Cancellation cleans only Wingstaff-owned worktrees.
8. Delivery records an immutable diff with `committed: false` and
   `pushed: false`.
9. Board history explains the complete workflow without private-DB inspection.

### Repository verification

```bash
pytest
ruff check .
wingstaff packs validate addyosmani
wingstaff packs validate aidlc
python scripts/check_md_links.py .
python -m build
python -m twine check dist/*
python scripts/check_release_contents.py . --wheel dist/*.whl
```

Also repeat the isolated plugin installation, tool registration, skill loading,
Kanban graph, and package dependency audit required by the existing release
contract.

### Final DOX pass

- re-read the root, `wingstaff/`, `tests/`, and `docs/` AGENTS.md contracts;
- update ownership entries for changed or removed modules/tools;
- update affected Child DOX indexes;
- remove every stale dual-authority statement;
- confirm no plan or normal document still instructs users to operate a second
  Wingstaff lifecycle.

### Commit boundary

`test: verify Kanban-native Wingstaff end to end`

## Risks and mitigations

### Current Hermes version lacks required public operations

Mitigation: raise Wingstaff's minimum supported Hermes version after an isolated
probe. Do not add private imports, direct SQLite access, or an alternate
orchestration path merely to retain v0.18.2.

### Digest approval is weakened into ordinary unblock

Mitigation: retain Wingstaff's approval ledger and require the exact current
plan digest before creating or releasing implementation work. Treat unblock as
interaction, not authorization.

### Cross-card workspace drift

Mitigation: pin one absolute Wingstaff-owned worktree and prove the supported
workspace mapping against the live dispatcher. Stop if workers cannot reliably
reach it.

### Duplicate artifact sources

Mitigation: Kanban metadata/comments reference evidence; Wingstaff's artifact
store owns immutable bytes and digests. Do not copy or independently mutate the
same artifact in both systems.

### Too many cards for small changes

Mitigation: keep the pack lifecycle explicit for governed workflows. Plain
Hermes Kanban remains available for work that does not need Wingstaff's policy
guarantees. Do not make Wingstaff the mandatory path for every code edit.

### Profile proliferation

Mitigation: validate existing profile names and allow multiple stages to use the
same profile. Dedicated profiles remain optional and justified only by model,
tool, credential, or trust-boundary differences.

## Stop conditions

Stop implementation and ask the user when:

- the live public Hermes API cannot enforce the required graph without private
  imports or database writes;
- approval cannot be separated from generic unblock;
- a shared persistent worktree cannot be pinned safely;
- current Hermes documentation contradicts the live supported host;
- a pack requires core branches named after that pack;
- implementation would require a new server, daemon, dashboard, or nested
  `hermes chat` process;
- a verification gate fails.

## Approval checkpoint

No runtime or user-facing documentation implementation starts until the user
explicitly approves this plan. After approval, execute one phase at a time,
keep each commit boundary independently green, and stop at every failed gate.
