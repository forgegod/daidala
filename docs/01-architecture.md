# 01 — Architecture

## Product boundary

Daidala is a general Hermes plugin plus bundled resources. Hermes owns the
agent process, model access, tool registry, skill loading, gateway, delegation,
Kanban lifecycle, and cron facilities. Daidala adds workflow packs, exact skill
provenance, workflow-scoped constraint artifacts, plan-and-constraint approval,
repository safety, and evidence integrity on top of those host facilities.

Daidala is not an MCP server, HTTP service, dashboard service, model provider,
message gateway, scheduler, or nested `hermes chat` launcher.

## Component boundary

```mermaid
flowchart TB
    subgraph H["Existing Hermes process"]
        PM["Hermes plugin manager"]
        TR["Hermes tool registry"]
        SR["Hermes namespaced skill registry"]
        HOST["Hermes-owned model and runtime facilities"]
        KB["Hermes Kanban tools + durable board"]

        subgraph W["Daidala plugin — loaded in-process"]
            REG["register(ctx)"]
            TOOL["JSON tool handlers"]
            PACK["deterministic pack loader and validator"]
            SERVICE["policy service"]
            STATE["policy + artifact ledger"]
            EXEC["artifact + worktree boundary"]
            KBA["public Kanban dispatch adapter"]
            SKILL["bundled orchestrate SKILL.md"]
            YAML["bundled pack YAML"]
        end

        PM --> REG
        REG --> TR
        REG --> SR
        TR --> TOOL
        TOOL --> SERVICE
        SERVICE --> PACK
        SERVICE --> STATE
        SERVICE --> EXEC
        SERVICE --> KBA
        KBA -->|"ctx.dispatch_tool"| KB
        PACK --> YAML
        SR --> SKILL
        HOST -->|"skill inventory and normal tools"| W
    end

    TARGET["Local Git target + detached worktree"]
    DATA["Hermes profile data root"]
    EXT["External skill repositories<br>pinned revision + skill digests"]
    POLICY["Exact installed policy skill<br>or explicit constraint content"]
    EXEC --> TARGET
    STATE --> DATA
    EXEC --> DATA
    YAML -."source URL and install-target strings".-> EXT
    POLICY -->|"verified source + canonical snapshot"| SERVICE
```

Daidala has no autonomous execution loop, scheduler, model client, or second
service. Its Kanban adapter calls documented host operations; it never imports
or writes Hermes' board database. Hermes owns card status, assignment, claims,
heartbeats, completion, dependencies, retries, and worker restart. Daidala's
SQLite data is a narrow policy and artifact-integrity ledger, not another task
state machine.

## Authority split

| Concern | Authority |
|---|---|
| Board, card status, dependencies, assignment, claims, retries, comments, and run history | Hermes Kanban |
| User-visible progress and recovery | Hermes Kanban CLI, slash command, dashboard, and gateway |
| Pack selection, stage skills, provenance, and compatibility | Daidala |
| Workflow constraint identity, immutable policy artifact, projection, and replacement | Daidala |
| Repository baseline, owned worktree, and immutable implementation scope | Daidala |
| Plan-and-constraint tuple approval, artifact digests, and verification evidence | Daidala policy ledger |
| Target commit or push | Unavailable without separate authorization |

No operational transition requires bidirectional status synchronization.
Daidala reads Hermes status when presenting a combined view and applies only
Daidala-owned policy checks before creating or releasing cards.

## Workflow constraint topology

The topology is composition, not a Hermes parent-child hierarchy:

```mermaid
flowchart LR
    HP["Hermes profile"] -->|"runs assigned workers"| WL["Worker lane"]
    WL -->|"claims cards"| KB["Named Hermes Kanban board"]
    KB -->|"hosts cards for many workflows"| WF["Daidala workflow ledger"]
    WF -->|"selects exactly one pack"| PK["Workflow pack"]
    WF -->|"references zero or one current revision"| CA["Immutable constraint artifact"]
    PS["Exact policy skill or explicit content"] -->|"materialized once"| CA
```

- One Hermes profile may run workers for many boards and workflows.
- One named board may host cards from many Daidala workflows.
- Each Daidala workflow selects exactly one board and one pack.
- Each workflow has zero or one current constraint identity and retains every
  historical constraint artifact append-only.
- A reusable policy skill may source many workflows, but it grants no worker
  activation and owns no lifecycle state. Daidala verifies and snapshots it;
  later workflow execution reads the immutable workflow artifact.
- Hermes dispatch owns card claims and worker runs. Daidala owns policy
  identity, card eligibility, approval binding, and artifact integrity.

## Process boundary

The optional dashboard is a Hermes-owned extension, not another process. Hermes
serves the packaged manifest, browser assets, and authenticated router inside its
existing dashboard process. The router delegates deterministic policy to the
same `WorkflowService`; Hermes Kanban CLI operations remain the host boundary.

```mermaid
flowchart LR
    START["Daidala validates pack, profiles, and clean baseline"] --> DEFINE["define card"]
    DEFINE --> PLAN["plan card"]
    PLAN --> APPROVAL["blocked approval card"]
    APPROVAL -->|"exact digest approved"| IMPLEMENT["implement card"]
    IMPLEMENT --> VERIFY["verify card"]
    VERIFY --> REVIEW["review card"]
    REVIEW --> DELIVER["deliver card"]

    KB["Hermes Kanban owns every card status and retry"] --> DEFINE
    LEDGER["Daidala policy ledger"] -."digests + evidence refs".-> APPROVAL
    WORKTREE["One absolute Daidala-owned worktree"] --> IMPLEMENT
    WORKTREE --> VERIFY
    WORKTREE --> REVIEW
    WORKTREE --> DELIVER

    CLI["Native or standalone operator command"] -->|"documented hermes kanban subprocesses"| KB
```

Native `hermes daidala` is the canonical operator surface. The standalone
`daidala` executable shares its parser and handlers for diagnostics and smoke
tests. Neither is a long-running orchestration process.

## Deterministic mechanism and model judgment

The Kanban-native deterministic boundary keeps the implemented pack,
repository, and artifact mechanisms and replaces private lifecycle state with:

- `daidala.packs.load_pack()` resolves a conservative bundled pack name;
- `yaml.safe_load()` parses the package resource;
- `validate_pack()` validates schema shape, lifecycle order, skill references,
  and pre-implementation gate placement;
- immutable dataclasses and SQLite enforce policy-ledger invariants, optimistic
  updates, exact plan approval, and artifact integrity;
- exact installed-skill names gate workflow graph creation and validation;
- profile-local artifact paths and detached Git worktrees isolate execution;
- captured diffs, changed paths, command results, and delivery flags remain
  deterministic;
- every plugin handler serializes success or failure as JSON.

Daidala calls no model. Hermes profile workers and the selected pack skills
produce definition, plan, implementation, verification, and review judgment.
Workers terminate through `kanban_complete` or `kanban_block`; Daidala records
artifact digests, approval, verification evidence, and delivery scope without
declaring a second operational status.

## Release host compatibility

Hermes v0.18.2 preserves worker task bodies through 8,192 characters and visibly
truncates larger bodies. Daidala therefore limits canonical constraints to
4,096 UTF-8 bytes and rejects a fully rendered card body over 8,192 characters;
it never silently truncates policy content.

`scripts/probe_hermes_compatibility.py` makes this a release contract rather than
a one-time observation. It checks exact Hermes semantic, build, and upstream
identity, exact policy-skill hashing, public Kanban lifecycle operations, and
both sides of the worker-context boundary in an isolated `HERMES_HOME`. Ordinary
pushes and pull requests use fast regressions; version tags and explicit release
dispatches run the live probe after tests and packaging pass.

## First-release execution policy

The first executable release is constrained to local target repositories. Its
state and lifecycle tools enforce one policy consistently:

- reject a target repository with existing tracked or untracked changes;
- create a fresh Daidala-owned Git worktree for implementation;
- produce a reviewed working-tree diff, not an automatic target commit or push;
- require separate authorization before committing or pushing target changes;
- bind one human approval to the complete plan artifact digest;
- invalidate approval whenever that plan changes.

These controls are executable and covered by the cross-pack fixtures. The
support-status table remains authoritative for later capabilities.

## Plugin and package entry points

The repository supports two discovery shapes verified against Hermes v0.18.2:

- the root `plugin.yaml` and root `__init__.py` form the Git-directory plugin
  entry point;
- the `hermes_agent.plugins` entry point in `pyproject.toml` resolves to
  the `daidala` module for Python-package discovery. Hermes then calls its
  module-level `register(ctx)` function.

`daidala.register(ctx)` uses the documented `register_tool()` and
`register_skill()` context APIs. Hermes documents plugin skills as read-only,
namespaced resources loaded as `plugin:skill`; therefore the registered
`orchestrate` resource is addressed as `daidala:orchestrate` when the plugin
name is `daidala`.

## Pack neutrality

The Python validator knows lifecycle mechanics, not Addy Osmani-specific skill
semantics. Pack-specific data lives in `daidala/packs/*.yaml`. Schema v1 is
intentionally strict: every pack uses the same six ordered stages, and each
stage supplies external or plugin-bundled skill references. External skills
remain the default; bundled references exist for licensed adapters whose
upstream source does not ship Hermes Agent Skills.

Adding a pack-specific conditional to `daidala/packs.py` would violate this
boundary. Extend the schema only for a capability shared by packs, then validate
that capability generically.

## Source of truth

| Contract | Current source or migration target | Verification |
|---|---|---|
| Plugin declarations | `plugin.yaml`, `pyproject.toml` | `tests/test_installation.py`; live directory and entry-point probes |
| Registration | `daidala/__init__.py` | `tests/test_plugin.py` fake-context assertions |
| Tool schema and JSON boundary | `daidala/schemas.py`, `daidala/tools.py` | `tests/test_plugin.py` |
| Policy ledger and persistence | `daidala/state.py`, `daidala/workflow.py`, `daidala/store.py` | State, policy, persistence, and restart tests |
| Kanban graph and execution isolation | `daidala/service.py`, `daidala/kanban.py`, `daidala/execution.py` | Fake-host graph/recovery tests and isolated Hermes lifecycle probes |
| Worktree cleanup and rollback | `daidala/service.py`, `daidala/execution.py` | Cross-pack delivery and cancellation tests |
| Pack schema and invariants | `daidala/packs.py` | `tests/test_packs.py` |
| Addy Osmani mapping | `daidala/packs/addyosmani.yaml` | Pack load and CLI validation |
| AI-DLC mapping | `daidala/packs/aidlc.yaml`, `daidala/skills/aidlc-adapter/` | Pack, fixture-workflow, registration, and wheel tests |
| Bundled procedures | `daidala/skills/*/SKILL.md` | Registration and packaging tests |
| Hermes extension behavior | [official plugin guide](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins) | Upstream documentation plus the v0.18.2 compatibility probe |
