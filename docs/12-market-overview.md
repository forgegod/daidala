# 12 — Workflow ecosystem market overview

This overview evaluates adjacent agent-skill, workflow, specification, and design
projects as inputs to Daidala. It distinguishes projects that can become
workflow packs from projects that are better treated as interoperability layers,
optional tools, or product references.

The assessment reflects the sources available from 2026-07-11 through
2026-07-16. A positive fit is
not an implementation commitment; every bundled adapter still requires a pinned
revision, license review, exact skill provenance, tests, and explicit human
approval before implementation.

## Evaluation criteria

A strong Daidala pack candidate should:

- provide reusable instructions or skills rather than require a competing agent
  runtime;
- map honestly onto `define → plan → implement → verify → review → deliver`;
- preserve Daidala's human gate after planning;
- let Hermes remain the Kanban, worker, delegation, and retry authority;
- produce repository artifacts and verification evidence that Daidala can
  capture;
- support revision pinning, attribution, and deterministic prerequisite checks;
- avoid a new Daidala daemon, dashboard, MCP server, or nested agent process.

Projects may still be valuable when they fail the pack test. Declarative
contracts can improve stage handoffs, design systems can extend artifact types,
and proprietary products can provide useful product comparisons without being
adaptable source material.

The **Daidala rating** below measures fit as a Daidala pack, not general
project quality or popularity:

- **5/5** — direct pack candidate with full lifecycle coverage and minor adaptation;
- **4/5** — strong candidate with bounded policy conflicts;
- **3/5** — useful partial methodology or specialized pack requiring extensions;
- **2/5** — better as an adapter, interoperability layer, or reference;
- **1/5** — duplicates the host runtime, lacks provenance, or is not safely adaptable.

Marketplace install counts are discovery signals only. They are mutable,
skill-level counts—not quality scores, project-level active-user counts, or
security reviews. The Hermes Skills Hub dynamically exposed its catalog but no
extractable ranking during this assessment, so comparable-project discovery and
install signals came from the [skills.sh leaderboard](https://skills.sh/), then
each project's own repository and license were evaluated separately.
Likewise, the stars and ordering in the
[Hermes Atlas multi-agent framework list](https://hermesatlas.com/lists/multi-agent-frameworks)
are discovery metadata, not proof of Hermes compatibility, safety, adoption, or
architectural fit. Atlas entries were checked against their primary repositories.

## Decision matrix

| Project | Daidala rating | Marketplace signal | Recommended relationship | Status |
|---|---:|---:|---|---|
| [Addy Osmani Agent Skills](https://github.com/addyosmani/agent-skills) | 4.5/5 | Not used | External-skill pack | Implemented |
| [AWS AI-DLC](https://github.com/awslabs/aidlc-workflows) | 4/5 | Not used | Bundled adapter skill | Implemented |
| [Superpowers](https://github.com/obra/superpowers) | 4/5 | Top listed skill: 271.9K installs | Curated external-skill pack after conflict tests | Candidate |
| [Matt Pocock Skills](https://github.com/mattpocock/skills) | 4/5 | `grill-me`: 520.5K installs | External-skill pack after a focused compatibility spike | Candidate |
| [Open Design](https://github.com/nexu-io/open-design) | 3.5/5 | Not used | Narrow design pack using an optional external installation | Candidate after artifact-model work |
| [Spec Kit Agent Skills](https://github.com/dceoy/speckit-agent-skills) | 2.5/5 | Top listed skill: 469 installs | Definition-and-planning adapter, not a full pack yet | Watch |
| [Open Agent Spec](https://www.openagentspec.dev/) | 2/5 | Not used | Stage-contract interchange, not a lifecycle pack | Watch / design later |
| [BMad Method](https://github.com/bmad-code-org/BMAD-METHOD) | 2/5 | Top listed skill: 348 installs | Methodology reference or narrow skill subset | Do not adapt wholesale |
| [Get Shit Done Skills](https://github.com/ctsstc/get-shit-done-skills) | 1/5 | `gsd`: 2.7K installs | None until tested and licensed | Reject for now |
| [AWS Kiro](https://kiro.dev/) | 1/5 | Not applicable | Product reference only | Not a pack candidate |
| [Mission Control](https://github.com/builderz-labs/mission-control) | 1/5 | Hermes Atlas: #1 when assessed | Control-plane product reference | Reject as a dependency |
| [Agent of Empires](https://github.com/agent-of-empires/agent-of-empires) | 1/5 | Hermes Atlas: #2 when assessed | Session, worktree, and sandbox UX reference | Optional adjacent tool only |
| [CryptoDmitry Control Room](https://github.com/CryptoDmitry/hermes-agent-control-room) | 1/5 | Hermes Atlas: #3 when assessed | Operations-template reference | Do not integrate |
| [shannhk Control Room](https://github.com/shannhk/hermes-agent-control-room) | 1/5 | Hermes Atlas: #4 when assessed | Operations-template reference | Do not integrate |
| [SwarmClaw](https://github.com/swarmclawai/swarmclaw) | 1/5 | Hermes Atlas: #5 when assessed | Competing-runtime reference | Reject as a dependency |
| [Minions](https://github.com/agent37-platform/minions) | 1/5 | Hermes Atlas: #6 when assessed | Hermes supervision UX reference | Optional adjacent product only |
| [Hermes Agents Team](https://github.com/linke-ai/hermes-agent-team) | 1/5 | Hermes Atlas: #8 when assessed | Multi-profile team reference | Reject as infrastructure |
| [Hermes Agent Meta-Harness](https://github.com/howdymary/hermes-agent-metaharness) | 2/5 | Hermes Atlas: #9 when assessed | Evaluator and comparison reference | Watch; no current dependency |
| [Hermes ACP Orchestrator Skill](https://github.com/Rainhoole/hermes-agent-acp-skill) | 2/5 | Hermes Atlas: #11 when assessed | Delegation-method reference | Evaluate only as an external skill |
| [Ankh.md](https://github.com/Abruptive/Ankh.md) | 2/5 | Awesome Hermes catalogue: experimental | Project-scoping reference only | Not a pack candidate |
| [Gladiator](https://github.com/runtimenoteslabs/gladiator) | 1/5 | Awesome Hermes catalogue: experimental | Candidate-comparison reference only | Reject as infrastructure |
| [Big Iron](https://github.com/supermodeltools/bigiron) | 1/5 | Awesome Hermes catalogue: beta | Structural-evidence reference only | Archived and rejected |
| [opencode-hermes-multiagent](https://github.com/1ilkhamov/opencode-hermes-multiagent) | 1/5 | Awesome Hermes catalogue: beta | Conditional-role reference only | Reject |
| [MisakaNet](https://github.com/Ikalus1988/MisakaNet) | 2/5 | Awesome Hermes catalogue: beta | Lesson-reuse evaluation reference | Watch as a reference |

## Addy Osmani Agent Skills

### Why it matches

The repository publishes small, independently installable Agent Skills covering
requirements discovery, planning, incremental implementation, testing,
debugging, review, security, delivery, and documentation. That breadth maps
naturally to all six Daidala stages without importing another state machine.
The skills remain judgment providers while Daidala supplies provenance,
approval, worktree isolation, evidence, and conservative delivery.

### Why it does not match perfectly

The upstream collection is a capability library, not one authoritative workflow.
Daidala must select which skills are required or conditional and own their
stage mapping. Similar names are not sufficient: exact installed names,
repository paths, revisions, and complete-directory digests remain necessary.

### Daidala decision

Implemented as the `addyosmani` external-skill pack. The exact mapping and pinned
revision are documented in [Pack adapters](09-pack-adapters.md).

## AWS AI-DLC

### Why it matches

AI-DLC supplies a recognizable inception and construction lifecycle with
requirements, design, decomposition, implementation, build, test, and review
activities. Its methodology is broad enough to guide every Daidala stage and
places substantial emphasis on traceable artifacts and deliberate execution.

### Why it does not match perfectly

Stable AI-DLC publishes coding-harness rules rather than independently
installable Agent Skills. Its own state and audit files overlap with Daidala's
policy ledger and Hermes Kanban. The v2 preview goes further and owns hooks,
workspace state, orchestration, and lifecycle mechanics that must not become a
second authority inside Daidala.

### Daidala decision

Implemented as one attributed `daidala:aidlc-adapter` skill reused at every
stage. Daidala adopts the methodology but rejects its competing runtime and
state machinery.

## Matt Pocock Skills

The assessment used [mattpocock/skills](https://github.com/mattpocock/skills) at commit
`391a2701dd948f94f56a39f7533f8eea9a859c87`. Its package metadata identifies
`https://github.com/mattpocock/skills` as the upstream repository, while the
local checkout's Git origin is `forgegod/mattpocock-skills`; a production pack
must choose and pin one authoritative source rather than infer provenance from
this checkout.

### Why it matches

The engineering set is explicitly small, composable, model-independent, and
opposed to frameworks that take over the whole process. It offers strong stage
coverage:

| Daidala stage | Relevant Matt Pocock skills |
|---|---|
| Define | `grill-with-docs`, `domain-modeling`, `research`, `to-spec` |
| Plan | `to-tickets`, `wayfinder`, `codebase-design`, `prototype` |
| Implement | `implement`, `tdd`, `diagnosing-bugs` |
| Verify | `tdd`, `diagnosing-bugs` |
| Review | `code-review`, `improve-codebase-architecture` |
| Deliver | No dedicated delivery skill; Daidala's conservative delivery contract can remain authoritative |

The strongest differentiators are useful to Daidala: explicit test seams,
tracer-bullet tickets with dependency edges, domain vocabulary, disciplined bug
reproduction, and separate standards-versus-spec review axes. The MIT license
and `skills/<category>/<name>/SKILL.md` layout are also suitable for external
skill installation and content hashing.

### Why it does not match perfectly

Several instructions conflict with Daidala policy unless adapted:

- `implement` tells the worker to commit, while Daidala delivery must not
  commit or push without separate authorization.
- `to-spec` publishes directly to an issue tracker and `to-tickets` may create
  tracker issues and dependency links; Daidala currently creates and owns the
  Hermes Kanban graph instead.
- setup writes `docs/agents/*` plus `AGENTS.md` or `CLAUDE.md`, adding repository
  mutations that are not necessary for every workflow.
- user-invoked and model-invoked skill semantics do not directly equal
  Daidala's required and conditional stage activation.
- there is no dedicated delivery discipline, and verification is distributed
  across TDD, diagnosis, and review rather than represented as one stage skill.

These are adapter concerns, not reasons to copy or rewrite the skills. Silently
removing the conflicting instructions would misrepresent upstream behavior.

### Daidala decision

Run a focused pack spike. Prefer exact external skills and map the strongest
non-orchestrating skills first. Before implementation, decide whether the
commit, issue-tracker, and setup side effects can be constrained by Daidala's
higher-priority worker contract. If they cannot, do not ship the pack; a bundled
adapter that selectively restates the methodology would have higher maintenance
and attribution cost than the current AI-DLC case.

## Superpowers

Discovery signal: skills.sh listed `brainstorming` at 271.9K installs,
`systematic-debugging` at 181.8K, `writing-plans` at 180.0K, and several other
Superpowers skills above 100K during the assessment. These counts indicate broad
distribution, not correctness or compatibility.

### Why it matches

Superpowers is an MIT-licensed, composable software-development methodology with
nearly complete Daidala stage coverage:

| Daidala stage | Relevant Superpowers skills |
|---|---|
| Define | `brainstorming` |
| Plan | `writing-plans` |
| Implement | `test-driven-development`, `executing-plans`, `subagent-driven-development` |
| Verify | `verification-before-completion`, `systematic-debugging` |
| Review | `requesting-code-review`, `receiving-code-review` |
| Deliver | `finishing-a-development-branch` |

Its evidence-over-claims philosophy, mandatory verification, test-first loop,
design approval, and isolated-worktree practice align closely with Daidala.
The repository also maintains behavior evaluations, which is stronger upstream
quality evidence than marketplace installs alone.

### Why it does not match perfectly

Superpowers presents itself as the complete methodology and automatically
activates skills from session start. It creates its own worktrees, dispatches
subagents, commits during TDD, reviews between tasks, and offers merge, PR, keep,
or discard choices when finishing a branch. Those actions overlap or conflict
with Hermes delegation, Daidala's preserved worktree, one approval gate,
stage-scoped activation, immutable evidence capture, and prohibition on implicit
commit, merge, push, or PR creation.

The conflict is concentrated in orchestrating skills; the underlying
`brainstorming`, `writing-plans`, `systematic-debugging`, and verification skills
are substantially cleaner fits.

### Daidala decision

Rate **4/5** and run a curated-pack spike. Start with non-orchestrating skills,
then prove through tests that card instructions override commit, worktree,
subagent, and branch-finishing behavior. Do not install the complete plugin or
its session-start bootstrap as part of Daidala.

## Spec Kit Agent Skills

Discovery signal: the community `dceoy/speckit-agent-skills` conversion appeared
on skills.sh with `speckit-specify` at 469 installs and the remaining core skills
roughly between 176 and 398 installs. The official `github/spec-kit` repository
did not expose the complete workflow as similarly ranked Agent Skills in the
search results.

### Why it matches

The workflow has explicit skills for constitution, specification, clarification,
planning, consistency analysis, task generation, and implementation. It is
artifact-oriented and maps well to Daidala definition and planning:

| Daidala stage | Relevant Spec Kit skills |
|---|---|
| Define | `speckit-constitution`, `speckit-specify`, `speckit-clarify`, `speckit-baseline` |
| Plan | `speckit-plan`, `speckit-analyze`, `speckit-checklist`, `speckit-tasks` |
| Implement | `speckit-implement` |
| Verify | No dedicated verification methodology |
| Review | Consistency analysis is pre-implementation, not code review |
| Deliver | No dedicated delivery methodology |

The exact `skills/<name>/SKILL.md` layout is mechanically compatible with
external-skill hashing.

### Why it does not match perfectly

This is a third-party Agent Skills conversion that requires the separate Spec
Kit CLI, project initialization, `.specify/` templates, and Bash helper scripts.
It owns a feature workflow through generated files and tasks but lacks complete
verification, code review, and conservative delivery stages. The conversion is
AGPL-3.0, which requires legal review before bundling or adapting it; using exact
external skills is operationally and legally different from copying them into
Daidala.

### Daidala decision

Rate **2.5/5**. Do not present it as a full Daidala pack. Reassess as a
definition-and-planning adapter if there is real demand for Spec Kit artifacts,
the external CLI boundary is acceptable, and license obligations are resolved.

## BMad Method

Discovery signal: skills.sh listed many `bmad-code-org/bmad-method` skills, with
the highest observed entries around 348 installs. The small counts do not affect
the architectural assessment.

### Why it matches

BMad is MIT-licensed and offers broad lifecycle coverage: brainstorming,
research, product briefs, PRDs, architecture, UX, implementation-readiness,
stories, development, E2E test generation, review, and sprint planning. Its
scale-adaptive planning and specialized review skills could provide useful
methodology ideas or isolated stage skills.

### Why it does not match perfectly

BMad is intentionally a comprehensive framework with its own installer, 12+
specialized agent personas, 34+ workflows, help router, modules, configuration,
sprint concepts, and evolving automation. Adapting it wholesale would put a
second workflow framework and role model inside Hermes Kanban. Its direct
installation also mutates the target project for a chosen AI IDE, which is not
equivalent to Daidala's exact, profile-local skill readiness model. Trademark
constraints additionally require care in naming an adapter.

### Daidala decision

Rate **2/5**. Do not create a full BMad pack. Evaluate individual, independently
usable skills only if they can run without BMad's installer, agent personas,
workflow state, and module runtime. Otherwise retain BMad as a methodology
reference.

## Get Shit Done Skills

Discovery signal: skills.sh listed `ctsstc/get-shit-done-skills` at 2.7K installs,
ahead of several smaller GSD conversions.

### Why it appears relevant

The converted skill set covers project initialization, discussion, research,
planning, execution, verification, debugging, milestones, progress, pause/resume,
and codebase mapping. On names alone it resembles a complete Daidala pack.

### Why it is rejected for now

The repository explicitly describes itself as an untested AI conversion, warns
that features may not exist across agents, calls the flow heavy, and is uncertain
about its own value. It also had no retrievable root `LICENSE` file during this
assessment. Its phase, milestone, progress, pause/resume, and orchestration
commands duplicate Hermes Kanban and would require substantial behavioral
validation before any exact mapping could be trusted.

### Daidala decision

Rate **1/5** and reject for now. Install count does not compensate for missing
license clarity, upstream self-reported lack of testing, and overlapping state
machinery. Reconsider only after those fundamentals change.

## Open Agent Spec

### Why it matches

Open Agent Spec 1.5.0 declares task inputs, outputs, prompts, model configuration,
tools, task dependencies, specialist-spec composition, sandbox constraints, and
evaluation cases in version-controlled YAML. Its fail-fast schema validation is
well aligned with Daidala's refusal to fabricate or accept malformed worker
handoffs. It could make stage contracts portable and independently testable.

### Why it is not a workflow pack

Open Agent Spec defines agents and data dependencies, not a software-delivery
methodology. It deliberately does not prescribe governance or long-running
orchestration and provides no Daidala-equivalent approval, repository safety,
review, or delivery policy. Its `oa` runner, provider selection, tools, and
multi-task chaining also overlap with Hermes execution if adopted wholesale.

### Daidala decision

Do not force Open Agent Spec tasks into the six-stage pack schema. Consider a
future pack-neutral interoperability feature that can import or export a single
stage contract and translate schema violations into a blocked Kanban card.
Hermes must still execute the worker lifecycle, and an OA dependency graph must
not become a second Daidala workflow.

## Open Design

### Why it matches

Open Design describes an agent-native loop of discovering a brief, locking a
direction, streaming an artifact, critiquing it, and delivering exports. That
maps well to Daidala's define, plan, approval, implement, verify, review, and
deliver sequence. It publishes skills and `DESIGN.md` design systems and already
documents Hermes as a supported consumer through its CLI/MCP integration.

A narrow repository-backed HTML prototype or dashboard would fit Daidala well:
the brief and design system become inputs, the approved direction binds the
human gate, generated files stay in the worktree, and browser/render evidence
supports verification and review.

### Why it does not match perfectly

Open Design is also a local desktop application, daemon, model proxy, automation
surface, CLI, and MCP server. Daidala must not embed, recreate, or silently
start those facilities. Its broader outputs—images, PDF, PPTX, MP4, and motion
graphics—are binary artifacts for which a Git diff and ordinary test output are
insufficient evidence. Current pack schema v1 cannot declare artifact media
types, render properties, dimensions, duration, or visual evidence requirements.

### Daidala decision

First add pack-neutral binary and rendered-artifact evidence if those outputs are
in scope. Then consider an `open-design` pack limited initially to HTML
prototypes, with `od` and its Hermes integration as explicit optional external
prerequisites. Do not bundle the Open Design daemon or add an MCP server to
Daidala.

## AWS Kiro

### Why it is relevant

Kiro's spec workflow turns an idea into `requirements.md` or `bugfix.md`,
`design.md`, and `tasks.md`, then executes a dependency graph of tasks. This is a
useful product comparison for Daidala's definition, planning, approval, and
Kanban graph. Kiro also demonstrates that model selection is an execution-policy
concern rather than a workflow methodology: its recommended `Auto` setting
routes across models, while users may select specific Claude, DeepSeek, MiniMax,
GLM, or Qwen models.

### Why it is not a pack candidate

Kiro is a proprietary IDE and hosted agent runtime, not an open skill or workflow
source that Daidala can pin, hash, package, and execute through Hermes. Its own
spec task UI and parallel task runner duplicate responsibilities already owned
by Hermes Kanban. Product similarity alone is not an adapter boundary.

### Daidala decision

Use Kiro as a product and terminology reference only. Do not describe Daidala
as running Kiro specs unless AWS publishes a stable, reusable contract that can
be consumed without adopting Kiro's runtime.

## Multi-Agent and swarm references

The five entries in the
[awesome-hermes-agent Multi-Agent & Swarms catalogue](https://github.com/0xNyk/awesome-hermes-agent#multi-agent--swarms)
were audited against their primary repositories as a challenge to the planned
autonomous self-improvement loop. The catalogue labels are discovery metadata,
not verified maturity levels: Big Iron is already archived and deprecated, and
opencode-hermes-multiagent is an OpenCode configuration rather than a Hermes
Agent extension. None of the five is suitable as a Daidala pack or runtime
dependency.

| Project | Primary-source finding | Useful aspect | Blocking concern |
|---|---|---|---|
| Ankh.md | MIT-licensed wrapper and patched Hermes distribution with project-local `.agent/` configuration, skills, sessions, memories, and identity | Explicit project scoping and reduced delegated toolsets | Repository-local config and `.env` overrides can grant models, tools, instructions, and credential selection; folder scope is not a sandbox or approval boundary |
| Gladiator | MIT-licensed hackathon system in which two Paperclip-managed agent companies compete on separate repositories | Same-baseline, side-by-side strategy evaluation with visible cost and telemetry | Adds a second orchestrator, nested `hermes chat` processes, several state stores, and a Goodhart-prone synthetic projected-stars score rather than correctness evidence |
| Big Iron | Archived and deprecated graph-guided SDLC; no usable repository license was found during the audit | Blast-radius analysis, affected-flow detection, graph-guided test selection, and baseline/candidate structural deltas | External Supermodel service and MCP dependency, overlapping lifecycle authority, unsupported absolute correctness claims, and no clear reuse license |
| opencode-hermes-multiagent | OpenCode prompt/configuration repository defining 17 fixed specialist roles; no root license was found | Conditional specialist roles, security escalation, and bounded revision loops | Not a Nous Hermes Agent extension; fixed serial handoffs, broad context sharing, prompt-only policy, and no durable approval, provenance, or recovery contract |
| MisakaNet | Apache-2.0 Git-backed Markdown lesson network with lexical retrieval, contribution workflows, explicit limitations, and LessonReuseBench | Source-citable failure lessons and measurement of whether agents reuse verified experience | Community lessons remain untrusted, semantic correctness is not established by CI, Git synchronization is batch-oriented, and the published credential pattern is unsuitable for Daidala |

### What the projects validate

The projects collectively reinforce that project identity, bounded specialist
delegation, structural code intelligence, source-citable failure knowledge, and
comparable evaluation fixtures can improve agent work. They also demonstrate
why those capabilities are insufficient without Daidala's existing contracts:
most treat an agent role, folder, profile, repository, or board as authority or
isolation; approval is usually a prompt checkpoint; evidence is frequently
self-reported; and crash reconciliation across agents, repositories, and remote
side effects is underspecified.

### Transferable self-improvement insights

The audit retains four design inputs without adopting any competing runtime:

1. **Delegation provenance.** Evidence should preserve the parent and child run
   identities, delegated goal, role, toolsets, model route, input identities,
   output digest, resource observations, and terminal state. A child may return
   advice or artifacts but cannot approve, retain, publish, or expand authority.
2. **Lesson-reuse evaluation.** A repeated metric should compare approved
   failure fixtures with and without access to a retained lesson, measuring
   verified recovery, repeated failed actions, turns, wall time, irrelevant
   matches, and unsafe use. Accumulating lessons is not itself improvement.
3. **Bounded strategy comparison.** A future experiment may compare candidate
   strategies against one frozen baseline and identical fixtures, limits, and
   metrics in separate evaluator homes and worktrees. Candidates share no
   mutable memory, do not define the score, and require human retention approval.
4. **Structural graph evidence.** Supported repositories may record graph
   freshness, affected-flow and blast-radius deltas, dependency cycles, and new
   untested hotspots. Exact declared rules may be deterministic; centrality and
   risk scores remain observational, and an incomplete graph makes the result
   `incomparable` rather than successful.

MisakaNet's lesson protocol is the strongest direct challenge to the
self-improvement design, but it does not justify a second canonical lesson tree.
A lesson starts as a provisional, content-addressed workflow artifact and may
be promoted only through review and retention approval into existing project
documentation, a governed skill, or a rebuildable advisory retrieval index.
Unapproved lessons never enter shared project memory or execute commands.

## Hermes Atlas multi-agent framework comparison

Hermes Atlas describes this list as orchestration tools for running multiple
Hermes agents together. That category is adjacent to Daidala, but it is not
Daidala's product category. Daidala does not try to provide a fleet dashboard,
agent runtime, role topology, task bus, model router, or generic session manager.
It constrains one repository workflow executed by Hermes and makes methodology,
approval, repository mutation, and evidence identities auditable.

Two Atlas entries—[Gladiator](https://github.com/runtimenoteslabs/gladiator) and
[`opencode-hermes-multiagent`](https://github.com/1ilkhamov/opencode-hermes-multiagent)—were
already covered in the preceding swarm audit. The complete Atlas list produces
the following comparison:

| Atlas project | Main overlap with Daidala | Decisive difference | Recommendation |
|---|---|---|---|
| [Mission Control](https://github.com/builderz-labs/mission-control) | Tasks, review gates, receipts, approvals, skills, schedules, audit, and evaluation surfaces | It is a separate control plane with its own task state, SQLite store, dashboard, REST API, MCP server, scheduler, runtime adapters, and completion approval; Daidala deliberately leaves those concerns with Hermes and binds approval before implementation | Use its operator field-note and receipt UX as product research; do not connect Daidala to its task or policy state |
| [Agent of Empires](https://github.com/agent-of-empires/agent-of-empires) | Parallel worktrees, optional container isolation, diff review, notifications, and Hermes support | It manages persistent tmux sessions for many coding-agent runtimes and creates its own worktrees; it does not define Daidala's methodology provenance or exact approval/evidence contract | Treat as an optional operator-side launcher or UX reference, never as Daidala's execution authority |
| [CryptoDmitry Control Room](https://github.com/CryptoDmitry/hermes-agent-control-room) | Agent registries, runbooks, secret maps, specialist routing, and staged adoption | It is a VPS control-room repository with setup and operations skills plus task-bus and loop conventions, not an in-process workflow integrity layer | Reuse the operational lesson—start with one documented agent and separate control from runtime data—but do not add its sidecar control plane |
| [shannhk Control Room](https://github.com/shannhk/hermes-agent-control-room) | Same control-room, registry, task-bus, and operations-template concepts | It is a closely related template variant rather than independent evidence for a second architecture; its orchestrator and filesystem task bus duplicate Hermes facilities | Treat both Control Room entries as one design family and avoid double-counting their popularity or recommendations |
| [SwarmClaw](https://github.com/swarmclawai/swarmclaw) | Skills, delegation, schedules, memory, approvals, durable delivery status, and multi-agent operation | It explicitly replaces the agent runtime and owns models, memory, server, dashboard, scheduler, delegation, connectors, and learned skills | Reject as a dependency; its durable delivery and dead-letter diagnostics are useful recovery references only |
| [Minions](https://github.com/agent37-platform/minions) | Hermes task supervision, review queues, scheduled work, notifications, files, and human sign-off | It maps each task to a Hermes root session but also stores task status in its own SQLite-backed web server; its human gate accepts completion rather than authorizing an exact plan before mutation | Keep separate as an optional supervision product; consider its attention and review-queue UX for the existing Hermes dashboard extension |
| [`opencode-hermes-multiagent`](https://github.com/1ilkhamov/opencode-hermes-multiagent) | Specialist roles across a software lifecycle | It is an OpenCode configuration with fixed role handoffs, not a Hermes extension, and lacks durable provenance and approval authority | Continue to reject; use only as evidence that conditional specialists can be useful |
| [Hermes Agents Team](https://github.com/linke-ai/hermes-agent-team) | Hermes profiles, Kanban, staged product/development/test roles, review, and local operation | It adds an HTTP server, MCP bus, ACP launches, polling, status synchronization, agent lifecycle control, and another SQLite store, and requires disabling Hermes gateway dispatch | Reject as infrastructure; its leader/specialist split is already expressible through Hermes delegation without a second control plane |
| [Hermes Agent Meta-Harness](https://github.com/howdymary/hermes-agent-metaharness) | Frozen baselines, candidate identities, paired comparison, provenance hashes, archives, and improvement search | It optimizes benchmark harness candidates in a standalone outer loop and currently targets a legacy Hermes benchmark surface absent from recent Hermes releases; Daidala governs approved repository change and broader evidence eligibility | Compare schemas and fixtures with Daidala's self-improvement evaluator, but do not depend on it until compatibility and authority boundaries are current |
| [Gladiator](https://github.com/runtimenoteslabs/gladiator) | Comparable multi-agent strategies and visible telemetry | It adds Paperclip, nested Hermes processes, competing companies, and a projected-stars objective | Continue to reject the runtime and retain only bounded same-baseline comparison principles |
| [Hermes ACP Orchestrator Skill](https://github.com/Rainhoole/hermes-agent-acp-skill) | Isolated delegation, specialist routing, timeout, and output limits | It is one delegation skill, not a lifecycle or integrity framework, and routes to external coding-agent runtimes in addition to Hermes children | Evaluate as an exact external skill only if its current tool syntax is verified and Daidala/Hermes retain model, tool, approval, and delivery authority |

The list is dominated by control planes and runtime managers. That explains why
their visible feature sets are broader, but it does not make them substitutes for
Daidala's narrower integrity boundary. Conversely, Daidala is not a substitute
for users who need fleet monitoring, persistent terminal sessions, a general
agent-team UI, cross-runtime dispatch, or an organizational swarm.

### Is Daidala unique enough to exist?

**Yes, within this comparison—but only if it stays narrow.** None of the Atlas
projects examined combines all of these properties:

- runs in the existing Hermes process instead of introducing a control-plane
  service or agent runtime;
- treats Hermes Kanban as the sole operational status, retry, and dispatch
  authority;
- maps independently versioned methodologies onto a fixed delivery lifecycle
  with exact skill provenance;
- binds human authorization to the exact plan, constraints, baseline, and pack
  before repository mutation;
- owns a clean detached worktree and captures content-addressed artifacts and
  verification evidence without implicitly committing or publishing; and
- admits `blocked`, `rejected`, `incomparable`, and `no-change` as valid outcomes
  instead of treating agent activity or task completion as success.

This is a meaningful gap between methodology skills and fleet orchestration:
Hermes can run and supervise agents, while Daidala can answer which methodology
and policy were authorized, what exact repository state changed, and what
evidence makes the result eligible for review or retention. The project is
therefore reasonable to exist as a Hermes-native governance and evidence plugin,
not as another "multi-agent framework."

The case weakens if Daidala expands into generic scheduling, role routing, model
selection, fleet state, memory, dashboards, or cross-runtime execution. Those
markets already contain broader and more mature implementations. It also weakens
if the approval and evidence machinery costs more operator effort than the risk it
removes. Daidala should prove usefulness through auditable workflow outcomes and
recovery behavior, not feature count or marketplace stars. If Hermes eventually
provides equivalent provenance, exact approval, and artifact-integrity contracts,
Daidala should shrink or upstream those mechanics rather than preserve duplicate
state.

### Recommendations from the Atlas comparison

1. **Position Daidala as workflow integrity, not multi-agent orchestration.** Use
   "Hermes-native policy, provenance, approval, and evidence" consistently; avoid
   fleet, swarm, mission-control, or agent-team claims.
2. **Keep integrations host-mediated.** Compose through Hermes Kanban,
   delegation, cron, gateway, skills, and the existing dashboard extension. Do
   not add adapters to another product's task database, scheduler, MCP bus, or
   status model.
3. **Borrow operator UX, not runtime ownership.** Attention queues, review
   receipts, diff inspection, notifications, evaluator comparisons, and recovery
   diagnostics are useful references for Daidala's optional Hermes dashboard and
   evidence views.
4. **Cross-check self-improvement evidence with Meta-Harness.** Compare task-set
   identity, baseline reuse, candidate/config hashes, trace diagnostics, and
   incomparability handling. Preserve Daidala's broader approval and retention
   authority and current-Hermes compatibility.
5. **Treat delegation recipes as pack inputs only.** The ACP orchestrator skill
   may be useful after exact revision, syntax, side-effect, and authority tests;
   it must not choose an external runtime or bypass card-scoped activation by
   default.
6. **Validate the narrow product claim.** Measure whether Daidala catches stale
   approval, provenance drift, unsafe mutation, missing evidence, and failed
   recovery in realistic repository workflows. If it cannot demonstrate those
   outcomes with acceptable operator overhead, do not broaden the product to
   compensate.

## Recommended sequence

1. **Spike a curated Superpowers pack.** It has the strongest complete lifecycle
   coverage and upstream behavioral evaluations, but exclude its bootstrap and
   prove that Daidala retains worktree, delegation, commit, and delivery authority.
2. **Spike Matt Pocock Skills.** It remains a strong composable alternative and
   requires no new artifact model, but its setup, tracker, and commit side effects
   need explicit policy tests.
3. **Prototype Open Design with HTML only.** Prove the design lifecycle against
   existing worktree, browser, review, and evidence mechanics.
4. **Generalize artifact evidence only from the vertical slice.** Add media and
   render contracts when real Open Design outputs demonstrate the requirement;
   do not pre-build a broad binary-artifact framework.
5. **Evaluate Spec Kit only for artifact compatibility.** Do not add a full pack
   until verification, review, delivery, CLI prerequisites, and AGPL obligations
   have explicit answers.
6. **Evaluate Open Agent Spec interoperability later.** Introduce it only when a
   concrete consumer needs portable stage schemas; do not add a second runner
   merely because a standard exists.
7. **Keep BMad and Kiro observational.** Revisit BMad only for independently
   usable skills and Kiro only if an open, runtime-independent contract appears.
8. **Reject the current GSD conversion.** Missing license clarity and explicit
   lack of testing are stop conditions, regardless of marketplace installs.

## Evidence base

| Source | Evidence used |
|---|---|
| [Addy Osmani Agent Skills](https://github.com/addyosmani/agent-skills) | Installable skill set and lifecycle capability coverage |
| [AWS AI-DLC](https://github.com/awslabs/aidlc-workflows) | Stable methodology, rule distribution, and lifecycle ownership |
| [skills.sh leaderboard](https://skills.sh/) | Mutable skill-level install signals used for candidate discovery, not quality scoring |
| [Hermes Skills Hub](https://hermes-agent.nousresearch.com/docs/skills/) | Catalog scope and Hermes discovery surface; no extractable ranking was available during assessment |
| [Superpowers](https://github.com/obra/superpowers) | Lifecycle, composable skills, automatic bootstrap, behavioral evaluations, side effects, and MIT license |
| [mattpocock/skills](https://github.com/mattpocock/skills) `README.md` and `skills/engineering/` at commit `391a2701dd948f94f56a39f7533f8eea9a859c87` | Skill philosophy, catalog, stage coverage, side effects, and MIT license |
| [Spec Kit Agent Skills](https://github.com/dceoy/speckit-agent-skills) | Community conversion, Spec Kit prerequisites, workflow coverage, scripts, and AGPL-3.0 license |
| [BMad Method](https://github.com/bmad-code-org/BMAD-METHOD) | Complete framework scope, installer, agents, modules, workflows, MIT license, and trademark boundary |
| [Get Shit Done Skills](https://github.com/ctsstc/get-shit-done-skills) | Upstream self-assessment, conversion status, workflow breadth, and missing root license |
| [Open Agent Spec website](https://www.openagentspec.dev/) and [repository](https://github.com/prime-vector/open-agent-spec) | Version 1.5.0 contracts, runner boundaries, composition, tools, and tests |
| [Open Design repository](https://github.com/nexu-io/open-design) | Design loop, artifact types, skills, `DESIGN.md`, CLI/MCP architecture, Hermes support, and Apache-2.0 license |
| [Kiro Specs](https://kiro.dev/docs/specs/) and [Kiro Models](https://kiro.dev/docs/models/) | Proprietary spec workflow, dependency execution, and current multi-model routing |
| [awesome-hermes-agent Multi-Agent & Swarms](https://github.com/0xNyk/awesome-hermes-agent#multi-agent--swarms) | Discovery inventory and catalogue labels; labels were checked against primary repositories rather than accepted as maturity evidence |
| [Ankh.md](https://github.com/Abruptive/Ankh.md) `README.md` and `DOCS.md` on branch `divine` | Project-local configuration, skills, sessions, memories, delegation, secret precedence, unsupported surfaces, MIT license, and runtime-patching boundary |
| [Gladiator](https://github.com/runtimenoteslabs/gladiator) | Paperclip orchestration, nested Hermes execution, company topology, evidence watcher, projected-stars formula, runtime dependencies, and MIT license |
| [Big Iron](https://github.com/supermodeltools/bigiron) | Archived and deprecated status, graph-guided SDLC architecture, external Supermodel dependency, and missing usable repository license |
| [opencode-hermes-multiagent](https://github.com/1ilkhamov/opencode-hermes-multiagent) | OpenCode agent definitions and pipeline configuration, fixed specialist topology, revision loops, broad context handoffs, and missing root license |
| [MisakaNet](https://github.com/Ikalus1988/MisakaNet) | Git-backed lesson format, retrieval and contribution model, `LIMITATIONS.md`, security model, LessonReuseBench, and Apache-2.0 license |
| [Hermes Atlas multi-agent frameworks](https://hermesatlas.com/lists/multi-agent-frameworks) | Curated discovery inventory and mutable ordering; all listed projects were classified against Daidala's product boundary |
| [Mission Control](https://github.com/builderz-labs/mission-control) | Separate control-plane scope, task and approval state, receipts, schedules, interfaces, runtime adapters, alpha status, and MIT license |
| [Agent of Empires](https://github.com/agent-of-empires/agent-of-empires) | Hermes-capable session management, tmux persistence, worktrees, container isolation, review UX, HTTP surface, and MIT license |
| [CryptoDmitry Control Room](https://github.com/CryptoDmitry/hermes-agent-control-room) and [shannhk Control Room](https://github.com/shannhk/hermes-agent-control-room) | Closely related control-room templates, staged adoption, agent registries, operations skills, filesystem task bus, runtime-data separation, and MIT licenses |
| [SwarmClaw](https://github.com/swarmclawai/swarmclaw) | Full runtime ownership, models, skills, memory, delegation, schedules, dashboard, connectors, recovery signals, and MIT license |
| [Minions](https://github.com/agent37-platform/minions) | Hermes session supervision, separate task-state database, completion review, schedules, files, and MIT license |
| [Hermes Agents Team](https://github.com/linke-ai/hermes-agent-team) | Leader/specialist profiles, HTTP/MCP/ACP/Kanban topology, polling and status synchronization, local SQLite state, and MIT license |
| [Hermes Agent Meta-Harness](https://github.com/howdymary/hermes-agent-metaharness) | Baseline/candidate comparison, provenance hashes, comparability checks, frontier search, legacy Hermes dependency, and MIT license |
| [Hermes ACP Orchestrator Skill](https://github.com/Rainhoole/hermes-agent-acp-skill) | External delegation skill, context isolation, routing, limits, current example syntax, and MIT license |
| [Pack reference](03-pack-reference.md), [Authoring packs](04-authoring-packs.md), and [Pack adapters](09-pack-adapters.md) | Daidala schema, engine boundary, implemented mappings, and constraints |
