# Wingstaff Bootstrap and Implementation Roadmap

> For the implementing agent: read `/AGENTS.md`, the applicable child `AGENTS.md`, this plan, and current official Hermes plugin documentation before each phase. Implement one phase at a time and stop when its verification gate fails.

## Goal

Deliver Wingstaff as a native, installable Hermes Agent plugin that coordinates autonomous software-development workflows from interchangeable skill packs, requires one explicit human approval before implementation, and introduces no separate server or daemon.

## Product boundary

Wingstaff is:

- a Hermes general plugin;
- deterministic workflow and validation code;
- namespaced bundled orchestration skills;
- workflow-pack adapters for external skill repositories;
- an operator CLI registered as `hermes wingstaff ...`;
- a user of Hermes delegation, Kanban, cron, gateway, tools, and host-owned LLM access.

Wingstaff is not:

- an MCP server;
- an HTTP service or dashboard server;
- a replacement gateway, scheduler, Kanban board, memory store, or model provider;
- a wrapper that launches nested `hermes chat` subprocesses;
- a vendor of copied third-party skill bodies;
- a system that invents fallback specs, plans, code, or verification results after failure.

## Source material

Read these before porting behavior:

- `../tonbistudio-hermes-multi-agent-workflow/` — retain its data-driven workflow, scope rails, task-chain, human-gate, cost-gate, and durable-workspace ideas.
- `../Ebonyhtx-Hermes-Hive/` — use only as a requirements source for explicit states, status, rollback, and structured outputs. Do not copy its daemon, MCP server, dashboard, subprocess bridge, hard-coded prompts, or fallback generation.
- https://github.com/addyosmani/agent-skills — first workflow-pack source.
- https://github.com/awslabs/aidlc-workflows — second adapter after the core proves pack neutrality.
- https://hermes-agent.nousresearch.com/docs/developer-guide/plugins — authoritative Hermes extension contract.

Do not modify either sibling source repository while implementing Wingstaff.

## Decisions fixed for the bootstrap

1. Repository, distribution, import package, and plugin name: `wingstaff`.
2. Python: 3.11 or newer.
3. License: MIT.
4. Canonical install, verified on Hermes v0.18.2:
   `hermes plugins install forgegod/hermes-wingstaff --enable`.
5. Canonical operator surface: `hermes wingstaff ...`; standalone `wingstaff` remains diagnostics-only.
6. Stable lifecycle: `discover -> define -> plan -> gate -> implement -> verify -> review -> deliver`.
7. The first executable pack is Addy Osmani's `agent-skills`.
8. AI-DLC is added only after one real end-to-end workflow passes.
9. External skills are referenced by fully qualified install targets and not vendored.
10. Runtime state belongs below a profile-aware Hermes home resolved through supported APIs; never hard-code `~/.hermes`.
11. The existing Hermes gateway is the only required long-running process for unattended operation.

## Bootstrap delivered with this plan

The initial repository contains:

- `plugin.yaml` plus Git-directory plugin entry point;
- `pyproject.toml` with `hermes_agent.plugins` entry point;
- `wingstaff.register(ctx)` using documented plugin APIs only;
- the `wingstaff_pack_info` tool;
- the `wingstaff:orchestrate` bundled skill;
- immutable pack dataclasses and deterministic validation;
- `packs/addyosmani.yaml` mapping the six core lifecycle stages;
- standalone `wingstaff packs validate addyosmani` diagnostics;
- tests using a fake Hermes plugin context;
- DOX work contracts.

This bootstrap intentionally does not claim workflow execution exists.

## Execution status

Status is updated only after a phase passes its verification gate. A phase is
committed before work starts on the next phase.

| Phase | Status | Next condition |
|---|---|---|
| Bootstrap package and guarded pack validation | Done | Preserve as the runtime baseline. |
| 0A — brand and narrative | Done | Reconcile only when the product boundary changes. |
| 0B — technical documentation set | Done | Preserve source-grounding and support-status rules. |
| 0C — Markdown verifier hardening | Done | Preserve the focused edge-case regression tests. |
| 1 — isolated Hermes installation proof | Done | Preserve both directory and entry-point regression coverage. |
| 1A — compatibility baseline and release policy | Done | Preserve the v0.18.2 host boundary and fixed execution policy. |
| 1B — public Git installation proof | Done | Preserve the verified public install command and fresh-process probe. |
| 2 — workflow state contract | Done | Preserve the BLOCKED-terminal rule and approval-digest binding. |
| 3 — durable persistence | Done | Preserve the optimistic-concurrency guard on update. |
| 4 — read-only and gate tools | Done | Preserve strict JSON boundaries and monotonic transition timestamps. |
| 4A — exact external-skill prerequisite check | Done | Preserve exact-name matching and read-only host inventory access. |
| 5 — thin Addyosmani workflow | Done | Preserve worktree isolation, immutable diff scope, and evidence-backed delivery. Gate: 19 Markdown files, 65 tests, Ruff, pack validation, build, Twine, diff check, and isolated 12-tool load passed. |
| 6 — external skill installation and revision management | Done | Preserve publisher-pinned targets, bounded Hermes compatibility, complete-directory digests, dry-run-by-default mutation plans, post-apply verification, and refused recursive installation. Gate: 19 Markdown files, 75 tests, Ruff, pack validation, build, Twine, diff check, 20-action standalone dry-run, recursive refusal, and on-disk digest-mismatch blocking passed. |
| 7 — Hermes Kanban mapping | Done | Preserve `ctx.dispatch_tool` isolation, post-approval creation, persistent worktree assignment, exact skill pins, idempotency keys, and Wingstaff/Hermes authority separation. Gate: 19 Markdown files, 77 tests, Ruff, pack validation, build, Twine, diff check, interruption recovery, restart deduplication, and isolated real-host one-card/two-call probe passed. |
| 8 — `hermes wingstaff` operator CLI | Done | Preserve the shared parser/service dispatcher, profile-local dry-run initialization, read-only doctor, required cancellation reasons, isolated-module resource loading, and v0.18.2 process exit-code shim. Gate: 20 Markdown files, 86 tests, Ruff, pack validation, build, Twine, diff check, isolated native Hermes command/doctor probes, and clean-wheel standalone init/list probe passed. |
| 9 — AI-DLC adapter | Done | Preserve the pinned MIT-0 adapter, mutually exclusive external/bundled skill providers, and pack-neutral engine path. Gate: 21 Markdown files, 92 tests, Ruff, both pack validations, build, Twine, diff check, isolated two-skill directory load, and no-`aidlc`-runtime-literal scan passed. |
| 10 — operational hardening and release | Todo | Start only after the Phase 9 commit and public installation checkpoint. |

## Phase 0A — rescue the Wingstaff brand under the new narrative

### Objective

Move only the selected Wingstaff identity from
`../tonbistudio-hermes-multi-agent-workflow/assets/` into this repository,
remove the naming-comparison history, and regenerate the derived assets from a
Wingstaff-owned source.

### Narrative contract

Use this as the canonical product description:

> Wingstaff is a Hermes-native staff of specialist agents that moves software
> work through interchangeable workflow packs and one explicit human approval
> gate—without introducing a second orchestration server.

Use this shorter asset tagline where space is limited:

> Hermes-native orchestration. Specialist agents. Human-approved implementation.

The name continues to carry both meanings: Hermes' winged herald staff and a
staff of specialists coordinating work for a human decision. Do not describe
Wingstaff as a unified CLI, a scout-first triage product, an MCP server, or a
standalone agent daemon.

### Source classification

Rescue:

- `assets/logo.svg` — selected Wingstaff lockup;
- `assets/logo-mark.svg` — selected winged-staff mark;
- `assets/logo-256.png`, `logo-512.png`, `logo-1024.png` — derived review/use renders;
- the selected mark/lockup geometry, palette, and generation logic from
  `assets/build_name_proposals.py`.

Do not copy:

- `project-name-proposals.svg` or `.png`;
- `proposal-heraldforge*`, `proposal-signalstaff*`, or `proposal-wingmarshal*`;
- `proposal-wingstaff*`, because it duplicates the selected canonical lockup;
- the stale subtitle `Pip-installable unified CLI · scout → proposal → human
  gate → fulfillment`;
- `__pycache__` or any generated runtime residue.

### Target files

- create `assets/AGENTS.md`;
- create `assets/README.md` as the concise brand and narrative guide;
- create `assets/build_brand_assets.py` as the deterministic source;
- create `assets/logo.svg` and `assets/logo-mark.svg`;
- create `assets/logo-256.png`, `assets/logo-512.png`, and `assets/logo-1024.png`;
- create `assets/social-card.svg` and `assets/social-card.png` using the new
  narrative, lifecycle, and no-second-server boundary;
- update `/AGENTS.md` Child DOX Index;
- update `/README.md` to use the canonical logo and product description;
- add any bundled font license under `assets/fonts/` if the approved deterministic
  rendering approach requires one.

### Steps

1. Record hashes and dimensions of the five canonical source assets before
   touching them.
2. Copy the selected SVG geometry into Wingstaff and render it once to prove the
   visual identity survived the move.
3. Rename and reduce `build_name_proposals.py` to `build_brand_assets.py`: one
   selected brand only, no proposal dataclass, no alternative names, and no
   comparison board.
4. Replace the old proposal rationale and subtitle with the narrative contract
   above.
5. Make generation work from any current working directory.
6. Remove the Windows-only `/mnt/c/Windows/Fonts/georgiab.ttf` dependency. Use
   an approved deterministic font strategy; do not silently substitute fonts.
7. Generate SVG first and PNG only from the SVG source.
8. Add a social card that shows the lockup, the short tagline, and a restrained
   lifecycle line: `define → plan → approve → implement → verify → deliver`.
9. Use `vision_analyze` on the logo, mark, and social card. Check transparency,
   clipping, small-size legibility, contrast, text accuracy, and overlap.
10. Confirm regeneration leaves the working tree clean after generated outputs
    are staged.

### Verification gate

- `python assets/build_brand_assets.py` succeeds outside the repository root;
- a second run produces byte-identical SVG and PNG files;
- SVG files have an accessible `<title>` and no stale project-name language;
- PNG dimensions match their filenames and have non-zero alpha content;
- `vision_analyze` confirms the wordmark, mark, tagline, and lifecycle are legible;
- repository search finds none of `HERALDFORGE`, `SIGNALSTAFF`, `WINGMARSHAL`,
  `PROJECT NAME PROPOSALS`, or `Pip-installable unified CLI` outside this plan's
  source-classification section.

### Stop-and-ask rules

- Stop if the source SVG and rendered PNG disagree materially; present both
  rather than choosing one silently.
- Stop if deterministic rendering requires redistributing a font whose license
  is unclear.
- Stop if the new social-card wording needs to omit either the human gate or the
  no-second-server boundary to fit.

### Decision: approved — deterministic wordmark font

Bundle an OFL-licensed bold serif selected to preserve the current Georgia-like
character, include its license, and accept a narrowly reviewed wordmark-metric
change.

## Phase 0B — establish the technical documentation set

### Objective

Create a numbered, source-grounded documentation set comparable in navigability
to the predecessor's `docs/`, but owned by the Hermes-native plugin and
pack-neutral lifecycle rather than by the old triage scaffold.

### Final documentation map

| File | Owns | First complete after |
|---|---|---|
| `docs/README.md` | Entry point, reading order, lifecycle diagram, support-status table, and symptom-to-document routing. | Phase 0B |
| `docs/01-architecture.md` | Plugin/skill/pack boundaries; deterministic engine vs. model judgment; why there is no Wingstaff server; component and process diagrams. | Phase 0B, reconciled every runtime phase |
| `docs/02-workflow-state.md` | Workflow identity, statuses, transitions, artifact references, plan-digest approval, idempotency, and recovery. | Phase 2 |
| `docs/03-pack-reference.md` | Complete workflow-pack schema: source, revision, stages, skills, artifacts, gate, verification, and transitions. | Phase 0B for schema v1; extend with Phase 6 |
| `docs/04-authoring-packs.md` | How to map a new skill set without adding pack-specific branches to the engine; validation and fixture requirements. | Phase 0B |
| `docs/05-lifecycle-stages.md` | Define, plan, gate, implement, verify, review, and deliver contracts, inputs, outputs, and failure semantics. | Phase 5 |
| `docs/06-security.md` | Trust boundaries, plugin opt-in, untrusted repositories, worktree isolation, secrets, command approval, human gate, and supply-chain rules. | Phase 0B, hardened in Phase 10 |
| `docs/07-runbook.md` | Verified install, enable, init, doctor, start, approve, resume, cancel, recovery, and upgrade procedures. | Phase 8 |
| `docs/08-hermes-integration.md` | Hermes plugin APIs, bundled namespaced skills, host LLM access, tool dispatch, delegation limits, Kanban ownership, cron/gateway runtime, and compatibility matrix. | Phase 1, extended in Phase 7 |
| `docs/09-pack-adapters.md` | Source-grounded mappings for Addyosmani and AI-DLC, including divergences and artifacts. | Addyosmani in Phase 5; AI-DLC in Phase 9 |

### Documentation rules

- `docs/README.md` is the only reading-order and symptom-routing index.
- Use repo-relative links for local documents and authoritative upstream URLs for
  Hermes or pack-source claims.
- Distinguish implemented, verified behavior from planned contracts in one
  support-status table; do not scatter `TODO` claims through every document.
- Do not copy predecessor text and rename symbols. Re-derive every runtime claim
  from Wingstaff source and current official Hermes documentation.
- Do not retain migration history, naming comparisons, prior architecture, or
  line-number references to sibling repositories.
- Diagrams must show the existing Hermes process as host and make clear that
  Wingstaff registers in-process. Do not draw a Wingstaff HTTP/MCP service.
- Each runtime document names its source-of-truth modules and verification tests.
- Commands appear only after they have been exercised against the supported
  Hermes version. Before that, the support-status table marks the surface as
  unavailable rather than publishing speculative commands.
- Every phase that changes a documented contract updates the owning document in
  the same batch; documentation is not deferred wholesale to Phase 10.

### Phase 0B deliverables

Create the documentation framework and fully author the documents whose claims
are already grounded by the bootstrap:

1. `docs/README.md`;
2. `docs/01-architecture.md`;
3. `docs/03-pack-reference.md` for the implemented schema-v1 subset;
4. `docs/04-authoring-packs.md`;
5. `docs/06-security.md` for the current plugin/package boundary;
6. placeholders in `docs/README.md` for the remaining numbered documents, but
   do not create empty files or speculative command guides;
7. update `docs/AGENTS.md` ownership, numbered reading order, source-grounding
   rules, and verification;
8. add a markdown link checker to development dependencies or a small
   dependency-free script under `scripts/check_md_links.py`;
9. update root `AGENTS.md` if `scripts/` becomes a durable boundary.

Later phases create each remaining document only when its owning behavior is
implemented and verified, according to the map above.

### Verification gate

- every path in `docs/README.md` either exists or is explicitly shown in the
  support-status table as a future document without a link;
- all relative links and heading anchors pass the chosen link checker;
- `docs/README.md` reading order matches actual numbered files;
- architecture diagrams render with Mermaid and contain no standalone
  Wingstaff server;
- source-to-document audit confirms each runtime claim against `wingstaff/`,
  tests, or current official Hermes docs;
- `pytest`, `ruff check .`, pack validation, and package build remain green.

### Stop-and-ask rules

- Stop when a predecessor claim cannot be verified against Wingstaff or current
  Hermes behavior; omit it rather than carrying it forward.
- Stop when a command differs between the live Hermes CLI and official docs;
  record the incompatibility in the plan and ask which supported version wins.
- Stop before creating an empty numbered document merely to make the set look
  complete.

### Decision: approved — documentation timing

Create incremental, source-grounded documentation as specified above—five
substantive documents in Phase 0B, then state/stages/runbook/integration
documents alongside the phases that make them true.

## Phase 0C — harden Markdown verification

### Objective

Turn the Phase 0B link checker from a repository-content smoke check into a
small, tested verifier with explicit Markdown edge-case behavior.

### Files

- extend `scripts/check_md_links.py`;
- create `tests/test_check_md_links.py`;
- update `scripts/AGENTS.md` if the supported syntax changes.

### Required behavior

- ignore fenced and four-space-indented code blocks;
- recognize ATX headings with up to three leading spaces;
- read UTF-8 files with or without a byte-order mark;
- handle quoted and parenthesized inline-link titles;
- report missing files and anchors with consistent repository-relative paths;
- preserve external URL, duplicate-heading, custom-anchor, image-link, and
  reference-link behavior;
- keep the checker dependency-free.

### Verification gate

- focused tests cover every required behavior and both success and failure exit
  paths;
- `python scripts/check_md_links.py .` passes;
- `pytest` and `ruff check .` remain green.

## Phase 1 — prove installation against Hermes

### Objective

Install the local repository as a Hermes plugin in an isolated profile and prove discovery, enablement, tool registration, and bundled skill loading without modifying the user's normal profile.

### Files

- `plugin.yaml`
- root `__init__.py`
- `pyproject.toml`
- `wingstaff/__init__.py`
- `tests/test_installation.py`
- `README.md`
- `docs/README.md`
- `docs/08-hermes-integration.md`

### Steps

1. Inspect the live `hermes plugins install --help`, `hermes plugins list`, and profile commands. Do not rely on remembered syntax.
2. Create a temporary Hermes home/profile fixture.
3. Verify the local checkout through an isolated user-plugin directory and the
   built wheel through an isolated entry-point target. The tested Hermes CLI
   does not accept local paths or wheels in `hermes plugins install`.
4. Enable it explicitly.
5. Start a fresh Hermes process and verify `wingstaff_pack_info` appears.
6. Load `wingstaff:orchestrate` explicitly and verify its content is reachable.
7. Add an automated smoke test around the stable boundary available in the installed Hermes version.
8. Resolve the root directory-plugin `__init__.py` versus import-package name
   collision that makes targeted pytest collection fail, without breaking either
   plugin discovery path.
9. Document the exact verified development procedure and do not publish a
   remote installation command until a real remote is available and exercised.

### Verification gate

- `pytest`
- `ruff check .`
- `python -m build`
- wheel contains `packs/addyosmani.yaml` and `skills/orchestrate/SKILL.md`;
- isolated Hermes reports Wingstaff enabled and registered.
- both `pytest` and `pytest tests/test_installation.py` collect without import
  ambiguity.

Stop if Git-directory and pip-entry-point installations behave differently. Resolve packaging before adding workflow logic.

## Phase 1A — establish compatibility and first-release policy

### Objective

Convert the Phase 1 live results into explicit compatibility and execution
policy before the workflow state model is frozen.

### Decisions

- declare the tested Hermes version or bounded version range;
- produce a reviewed working-tree diff only; never commit or push target changes
  without separate authorization;
- bind one approval to the whole plan digest and require reapproval after plan
  changes;
- reject dirty target repositories and use a fresh Wingstaff worktree;
- support local target repositories only in the first executable release.

### Files

- update `docs/01-architecture.md`;
- create or update `docs/08-hermes-integration.md`;
- update this status table and package compatibility metadata only when the
  supported Hermes boundary is proven.

### Verification gate

Every Phase 2 state invariant and every public Phase 4 tool can be evaluated
against one unambiguous execution policy and a declared Hermes compatibility
boundary.

## Phase 1B — prove public Git installation

### Objective

Close the deferred remote-installation gap after the local repository is joined
to a public GitHub repository.

### Steps

1. Push all completed phases to `forgegod/hermes-wingstaff`.
2. Create a fresh `HERMES_HOME`.
3. Run `hermes plugins install forgegod/hermes-wingstaff --enable`.
4. Start a separate Hermes process using that home.
5. Verify the plugin is enabled without errors, registers
   `wingstaff_pack_info`, and loads `wingstaff:orchestrate`.
6. Publish only that exercised command in the README and integration guide.

### Verification gate

The isolated installation reports source `user`, enabled status, one registered
tool, and a successful explicit skill load.

## Phase 2 — define the workflow state contract

### Objective

Model workflow state and transitions without running agents or touching Kanban.

### Files

- create `wingstaff/workflow.py`
- create `wingstaff/state.py`
- create `wingstaff/errors.py`
- create `tests/test_workflow.py`
- update `wingstaff/AGENTS.md`

### Required state

Each workflow records:

- immutable workflow ID;
- canonical local target-repository path, baseline commit, and requested goal;
- target-cleanliness validation result and timestamp;
- Wingstaff worktree path once implementation begins;
- fixed delivery mode `reviewed_diff_only`;
- selected pack and exact pack/source revision;
- current stage and status;
- artifact references per completed stage;
- human-gate decision, exact approved plan digest, and timestamp;
- verification evidence;
- failure/block reason;
- created/updated timestamps.

Allowed statuses are explicit: `draft`, `running`, `awaiting_approval`, `approved`, `blocked`, `failed`, `completed`, `cancelled`.

### Rules

- No transition skips the human gate.
- Workflow creation accepts local repository paths only.
- Forward progress from `draft` requires a clean target and recorded baseline
  commit; tracked or untracked target changes block validation.
- Implementation requires a fresh Wingstaff-owned worktree distinct from the
  target checkout.
- Approval is single-shot and bound to a plan artifact digest.
- Modifying the plan after approval invalidates approval.
- Delivery produces a reviewed diff and cannot represent an automatic target
  commit or push.
- Failed validation or verification blocks forward progress.
- Re-running a completed transition is idempotent.
- No guessed artifact is accepted.

### Verification gate

Unit tests cover every valid transition, every invalid transition, approval invalidation, idempotency, and serialization round-trip.

## Phase 3 — add durable local persistence

### Objective

Persist state using a simple local store while keeping Kanban as coordination rather than the database of record.

### Files

- create `wingstaff/store.py`
- create `wingstaff/locations.py`
- create `tests/test_store.py`

### Approach

- Start with SQLite from the standard library.
- Resolve the profile-aware data root through the Hermes plugin context or supported Hermes path helper.
- Store workflow metadata and artifact paths; keep large artifacts in a workflow directory.
- Use transactions and uniqueness constraints for transition idempotency.
- Do not reach into Hermes' private session or Kanban SQLite schemas.

### Verification gate

Temporary-directory tests cover create/read/update, concurrent duplicate transition attempts, restart recovery, and schema migration from an empty database.

## Phase 4 — expose read-only and gate tools

### Objective

Provide the minimal safe plugin API before any autonomous execution.

### Tools

- `wingstaff_start` — create a draft workflow for a local repository only;
- `wingstaff_status` — inspect state and artifacts;
- `wingstaff_validate` — validate pack and prerequisites, reject dirty targets,
  and record the baseline commit;
- `wingstaff_approve` — approve the exact current plan digest;
- `wingstaff_modify` — record requested plan changes and invalidate approval;
- `wingstaff_cancel` — terminal cancellation.

### Files

- extend `wingstaff/schemas.py`
- extend `wingstaff/tools.py`
- create `wingstaff/service.py`
- create `tests/test_tools.py`

### Verification gate

Every handler returns a JSON string, catches boundary exceptions, rejects unknown fields, and is tested without a live model or real profile.

## Phase 4A — make exact skill availability a start prerequisite

### Objective

Resolve the Phase 5/6 ordering gap: Phase 5 requires exact skills to be
validated, while Phase 6 owns installation and revision management. Implement
the minimum read-only availability check before executable work begins.

### Scope

- create `wingstaff/skills.py` with a host boundary for exact installed-skill
  lookup;
- validate every selected pack skill by exact name before workflow start;
- return an actionable missing-skill error containing the fully qualified
  install target;
- perform no installation, update, or network mutation;
- test the boundary with fake installed-skill inventories.

### Verification gate

A missing or mismatched skill blocks workflow start before definition or plan
artifacts are requested. A complete fake inventory passes without mutation.

## Phase 5 — implement one thin end-to-end workflow

### Objective

Prove one issue can move from request to delivered verified change using Hermes facilities.

### Scope

Only this vertical slice:

1. User starts a workflow against a local Git repository.
2. Wingstaff rejects a dirty target and records its baseline commit.
3. Wingstaff validates the Addyosmani pack and uses the Phase 4A prerequisite
   check for every exact required skill.
4. Hermes produces a definition artifact.
5. Hermes produces a plan artifact.
6. Wingstaff pauses at `awaiting_approval` and presents the plan.
7. Human approves the plan digest.
8. One implementation task runs in a fresh Wingstaff-owned Git worktree.
9. Verification runs and captures command, exit code, and output reference.
10. Review runs against the diff.
11. Delivery reports changed paths and verification evidence. It does not commit or push unless separately authorized.

### Execution boundary

Prefer Hermes tools and Kanban:

- use plugin `ctx.dispatch_tool(...)` when an operator command needs a normal Hermes tool with parent context;
- use Kanban for durable assigned work;
- use delegation only for bounded subtasks that may die with the parent session;
- use the gateway's existing dispatcher for unattended tasks;
- use `ctx.llm.complete_structured(...)` only for narrow structured decisions, not for autonomous coding;
- never shell out to `hermes chat`.

### Verification gate

Run the slice against a temporary fixture Git repository containing a deliberately failing test and a small fix. Confirm the workflow cannot implement before approval and cannot complete while verification fails.

## Phase 6 — install and validate external skill dependencies

### Objective

Extend the read-only Phase 4A resolution boundary with dry-run installation,
source revision pinning, version constraints, and controlled update planning.

### Files

- extend `wingstaff/skills.py`;
- extend pack schema with source revision and optional version constraints;
- add standalone `wingstaff packs install`, `check`, and `update-plan`
  operations over a reusable service boundary; Phase 8 registers the same
  operations under `hermes wingstaff`;
- add tests with a fake Hermes command/registry boundary.

### Rules

- Pin publisher and repository in every install target.
- Record the resolved revision used by each workflow.
- Default to the pack's required subset. Hermes v0.18.2 exposes no recursive
  install flag, so an explicit recursive request must fail with an actionable
  unsupported-host result rather than inventing a command. A later supported
  host may enable recursive installation only after capability detection.
- Dry-run installation by default and show every external source.
- Do not silently update a pack during an active workflow.

### Verification gate

Dry-run output names every external source and intended mutation. Installation
or revision mismatch remains a workflow-start blocker with an actionable exact
install command.

## Phase 7 — map work onto Hermes Kanban

### Objective

Use the built-in durable queue without private database coupling.

### Files

- create `wingstaff/kanban.py`
- add task creation/transition tests around a fake plugin context;
- update architecture docs.

### Rules

- Board cards reference Wingstaff workflow/stage IDs.
- Wingstaff state remains authoritative for lifecycle and approval.
- Kanban remains authoritative for assignment, claim, heartbeat, completion, and dependency readiness.
- The first post-gate task is created only after approval.
- Workers use persistent worktrees/workspaces across dependent stages.

### Verification gate

Simulate worker interruption and restart; the workflow must resume from persisted state without duplicating implementation tasks.

## Phase 8 — register `hermes wingstaff` CLI

### Objective

Make Hermes the canonical operator shell.

### Commands

- `hermes wingstaff init`
- `hermes wingstaff doctor`
- `hermes wingstaff start`
- `hermes wingstaff status`
- `hermes wingstaff approve`
- `hermes wingstaff cancel`
- `hermes wingstaff packs list|validate|install|check`

### Rules

- Register through `ctx.register_cli_command` using the current documented signature.
- Mutating setup and external installation are dry-run by default.
- Keep the standalone executable only as a thin call into the same service layer.

### Verification gate

Command tests prove the Hermes and standalone surfaces produce equivalent service calls and exit codes.

## Phase 9 — add AI-DLC as the pack-neutrality test

### Objective

Integrate `awslabs/aidlc-workflows` without changing core workflow code.

### Steps

1. Audit the current upstream release, license, stages, artifacts, approval points, and installation format.
2. Write a design note mapping AI-DLC concepts to Wingstaff lifecycle stages. Record that stable v1.0.1 ships rules rather than Agent Skills, while the v2 preview requires a complete harness overlay and owns an incompatible nested state machine.
3. Add `wingstaff/packs/aidlc.yaml` plus a licensed, pinned pack-owned adapter skill derived from the stable rules release.
4. Extend the pack schema generically for bundled plugin skill references; external install targets remain the default and no pack-name branch is allowed.
5. Run the same fixture workflow used for Addyosmani.

### Stop condition

If AI-DLC requires core code branches named `aidlc`, the adapter boundary is wrong. Redesign the generic schema before merging.

## Phase 10 — operational hardening and release

### Scope

- cost budgets and token telemetry;
- worktree cleanup and rollback;
- interruption/restart recovery;
- secret and untrusted-repository boundaries;
- plugin compatibility matrix for supported Hermes versions;
- package provenance and dependency audit;
- release CI, wheel inspection, and isolated install test;
- final source-to-document reconciliation across the numbered technical set.

### Release acceptance

- no listening Wingstaff port or background daemon;
- one-command plugin installation from Git;
- plugin is opt-in and disabled until enabled;
- Addyosmani and AI-DLC fixture workflows both pass;
- implementation before approval is impossible through public tools;
- missing model/skill/tool failures stop rather than degrade into fabricated output;
- interruption can resume without duplicate work;
- no credentials or live workflow state enter the package or repository.

## Risks and mitigations

### Hermes plugin API drift

Mitigation: test against a declared Hermes version range and use only documented context APIs. Keep the host adapter small.

### Bundled plugin skills are not automatically indexed

Hermes requires explicit namespaced loading for plugin skills. The orchestration entry point must request `wingstaff:orchestrate`; do not assume discovery from the global skill list.

### Skill-pack drift

Store fully qualified install targets and the resolved source revision. Validate before workflow start and do not update active workflows implicitly.

### Unattended operation still needs a running process

“No new server” does not mean “no runtime.” Document that unattended work requires the existing Hermes gateway/dispatcher; interactive use does not.

### Premature profile proliferation

Start with the active profile plus isolated worktrees. Add dedicated profiles only when different models, toolsets, credentials, or trust boundaries require them.

### Overbuilding the dashboard

Do not build one. Use Hermes CLI, gateway messages, Kanban, and existing observability until a demonstrated operator need remains unmet.

## Decisions for the first executable slice

The conservative defaults are accepted and move into Phase 1A as binding
first-release policy: no automatic target commit or push, one approval bound to
the whole plan digest, reapproval after plan changes, rejection of dirty target
repositories, fresh Wingstaff worktrees, and local repositories only. Hermes
v0.18.2 is the only supported host boundary until another release passes the
same directory and entry-point probes.

## Remaining commit boundaries

Keep every remaining phase independently green and commit it before starting
the next phase:

1. `docs: lock Hermes compatibility and release policy`
2. `feat: define deterministic workflow state`
3. `feat: persist workflow state and approval decisions`
4. `feat: expose Wingstaff lifecycle tools`
5. `feat: validate exact external skill prerequisites`
6. `feat: execute approved Addyosmani workflow slice`
7. `feat: manage external skill revisions`
8. `feat: integrate Wingstaff with Hermes Kanban`
9. `feat: add Hermes-native Wingstaff CLI`
10. `feat: add AI-DLC workflow adapter`
11. `docs: harden operations and release evidence`
