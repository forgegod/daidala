# Wingstaff documentation

Wingstaff adds pack provenance, persisted skill activation, digest-bound
approval, Git isolation, and durable evidence to Hermes Kanban. Hermes owns card
status, dependencies, assignment, retries, comments, and worker runs; Wingstaff
owns only its policy and artifact integrity boundary.

New operators should start with [Getting started](00-getting-started.md), not the
architecture references.

## Support status

| Document or surface | Status | Grounded by |
|---|---|---|
| [Getting started](00-getting-started.md) | Native first-workflow path verified on Hermes v0.18.2 | Isolated native lifecycle probe and CLI tests |
| [Architecture](01-architecture.md) | In-process policy adapter and Kanban authority split implemented | Runtime modules, graph tests, and isolated Hermes probes |
| [Policy ledger](02-workflow-state.md) | Status-free ledger and combined live Kanban diagnostics implemented | State, store, service, Kanban, and persistence tests |
| [Pack reference](03-pack-reference.md) | Schema-v1 providers and required/conditional activation implemented | Pack loader, bundled YAML, and pack tests |
| [Authoring packs](04-authoring-packs.md) | Pack-neutral mapping and activation authoring implemented | Pack loader and cross-pack tests |
| [Lifecycle stages](05-lifecycle-stages.md) | Approval graph, activation gate, handoffs, and recovery implemented | Graph, activation, worker-contract, and recovery tests |
| [Security](06-security.md) | Approval, activation, worktree, artifact, secrets, and supply-chain boundaries implemented | Runtime and release-content tests |
| [Runbook](07-runbook.md) | Native lifecycle and normal Kanban recovery commands verified | Shared CLI tests and isolated Hermes lifecycle probe |
| [Hermes integration](08-hermes-integration.md) | Hermes v0.18.2 plugin, CLI, Kanban, and gateway boundary verified | Isolated directory, entry-point, public Git, CLI, and Kanban probes |
| [Pack adapters](09-pack-adapters.md) | Addyosmani and AI-DLC mappings and activation modes implemented | Pack YAML, bundled adapter, and cross-pack execution tests |
| [Autonomous development use cases](10-autonomous-development-use-cases.md) | Current use cases, activation handoffs, user controls, tutorial ideas, and unsupported opportunities documented | Runtime contracts plus external agent-development research |
| [Skill usage and user control](11-skill-usage-and-user-control.md) | Candidate loading, persisted activation, structured handoff, and user-selection boundaries documented | Pack, policy ledger, worker contract, and cross-pack tests |
| Cron and target commit/push | Not part of Wingstaff runtime | Cron may be an external trigger; delivery records both flags as false |

“Implemented” means present in this repository. Compatibility claims are limited
to the host version and discovery paths in the
[Hermes integration guide](08-hermes-integration.md).

## Workflow and authority

```mermaid
flowchart LR
    S["explicit Wingstaff start"] --> D["define"]
    D --> P["plan"]
    P --> G["approval<br>blocked"]
    G -->|"Wingstaff exact-digest approval"| I["implement"]
    I --> V["verify"]
    V --> R["review"]
    R --> DL["deliver"]

    H["Hermes Kanban<br>lifecycle + retry authority"] --> D
    H --> P
    H --> I
    H --> V
    H --> R
    H --> DL
    W["Wingstaff<br>policy + evidence"] -.-> G
```

Wingstaff creates the graph explicitly. The existing gateway's Kanban dispatcher
runs ready cards; Wingstaff adds no scheduler, daemon, dashboard, or polling
loop. Generic Kanban unblock is interaction, not plan authorization.

Every executable card loads the complete exact pack-stage candidate set. After
`kanban_show`, its worker must persist a finalized, unblocked activation manifest
before applying methodology or submitting stage evidence. Successful handoffs
carry that manifest's digest and active skill names.

## Reading order

1. [Getting started](00-getting-started.md) — run the first workflow.
2. [Operator runbook](07-runbook.md) — operate, recover, cancel, and upgrade.
3. [Architecture](01-architecture.md) — understand the authority and process boundaries.
4. [Policy ledger](02-workflow-state.md) — understand durable Wingstaff facts.
5. [Lifecycle stages](05-lifecycle-stages.md) — inspect card inputs, handoffs, and blocks.
6. [Security](06-security.md) — review trust and Git boundaries.
7. [Pack reference](03-pack-reference.md) and [authoring guide](04-authoring-packs.md) — build adapters.
8. [Pack adapters](09-pack-adapters.md) — inspect the shipped mappings.
9. [Hermes integration](08-hermes-integration.md) — inspect verified host behavior.
10. [Autonomous development use cases](10-autonomous-development-use-cases.md) — choose suitable work, steer skills, and assess current limitations.
11. [Skill usage and user control](11-skill-usage-and-user-control.md) — understand how packs become card skills and which controls remain with the user.

## Find the right document

| Question or symptom | Read |
|---|---|
| How do I start and approve the first workflow? | [Getting started](00-getting-started.md) |
| Is Wingstaff a separate service or scheduler? | [Architecture](01-architecture.md#process-boundary) |
| Who owns status and retries? | [Policy ledger](02-workflow-state.md) |
| Why is Kanban unblock not approval? | [Security](06-security.md#human-approval-boundary) |
| What must each worker record? | [Lifecycle stages](05-lifecycle-stages.md) |
| Why is a loaded skill not necessarily active? | [Skill usage and user control](11-skill-usage-and-user-control.md#what-using-a-skill-means) |
| How do I recover a blocked card? | [Operator runbook](07-runbook.md#recovery) |
| Which Hermes version and commands are verified? | [Hermes integration](08-hermes-integration.md) |
| How do packs change stage workers without engine branches? | [Authoring packs](04-authoring-packs.md) |
| Which autonomous-development tasks fit, how do skills hand off, and where can I intervene? | [Autonomous development use cases](10-autonomous-development-use-cases.md) |
| What does “using” a pack skill mean, and can I select or override stage skills? | [Skill usage and user control](11-skill-usage-and-user-control.md) |

## Verification

```bash
python scripts/check_md_links.py .
```

The repository-wide gate is defined in [`/AGENTS.md`](../AGENTS.md).
