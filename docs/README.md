# Wingstaff documentation

The Wingstaff bootstrap is a Hermes plugin that can register one read-only
pack-inspection tool, register one bundled skill, and validate one bundled
workflow pack. It does not execute workflows yet.

## Support status

| Document or surface | Status | Grounded by |
|---|---|---|
| [Architecture](01-architecture.md) | Implemented bootstrap boundary | `wingstaff/__init__.py`, `plugin.yaml`, `pyproject.toml`, plugin tests, Hermes plugin docs |
| Workflow state (`02-workflow-state.md`) | Future — Phase 2; no file yet | Not implemented |
| [Pack reference](03-pack-reference.md) | Schema v1 implemented and unit-tested | `wingstaff/packs.py`, `wingstaff/packs/addyosmani.yaml`, pack tests |
| [Authoring packs](04-authoring-packs.md) | Implemented schema-v1 authoring path | Pack loader, bundled pack, pack tests |
| Lifecycle stages (`05-lifecycle-stages.md`) | Future — Phase 5; no file yet | Workflow execution not implemented |
| [Security](06-security.md) | Current package and plugin boundary | Manifest, registration, pack loader, tool handler, Hermes plugin docs |
| Runbook (`07-runbook.md`) | Future — Phase 8; no file yet | Operator CLI not implemented |
| [Hermes integration](08-hermes-integration.md) | Verified against Hermes v0.18.2 | Isolated directory and wheel-entry-point probes, `tests/test_installation.py` |
| Pack adapters (`09-pack-adapters.md`) | Future — Phase 5; no file yet | Adapter execution not implemented |
| `wingstaff_pack_info` | Implemented, unit-tested, and live registration-tested | `wingstaff/schemas.py`, `wingstaff/tools.py`, plugin and installation tests |
| `wingstaff:orchestrate` | Bundled and live loading-tested; procedure is not an execution engine | `wingstaff/skills/orchestrate/SKILL.md`, plugin and installation tests |
| `wingstaff packs validate addyosmani` | Implemented diagnostics command | `wingstaff/cli.py` |
| Workflow execution, persistence, approval tools, Kanban, cron, delivery | Unavailable | Planned in the [roadmap](plans/2026-07-10-wingstaff-bootstrap-and-roadmap.md) |

“Implemented” means present in this repository. Live installation claims are
limited to the Hermes version and discovery paths recorded in the
[Hermes integration guide](08-hermes-integration.md).

## Reading order

1. [Architecture](01-architecture.md) — process and component boundaries.
2. [Pack reference](03-pack-reference.md) — the exact implemented schema.
3. [Authoring packs](04-authoring-packs.md) — how to add another schema-v1 pack.
4. [Security](06-security.md) — current trust boundary and controls not yet present.
5. [Hermes integration](08-hermes-integration.md) — verified discovery, enablement, and packaging boundaries.
6. [Implementation roadmap](plans/2026-07-10-wingstaff-bootstrap-and-roadmap.md) — future phases.

## Lifecycle

The pack-neutral target lifecycle includes discovery and an explicit gate. The
schema-v1 pack stores the six skill-bearing stages and the gate
position; discovery is not represented as a stage and nothing executes them.

```mermaid
flowchart LR
    D["discover<br>host or future workflow input"] --> DF["define"]
    DF --> P["plan"]
    P --> G{"human approval<br>required before implementation"}
    G --> I["implement"]
    I --> V["verify"]
    V --> R["review"]
    R --> DL["deliver"]
```

## Find the right document

| Symptom or question | Read |
|---|---|
| Is Wingstaff a separate service? | [Architecture](01-architecture.md#process-boundary) |
| What does a schema-v1 pack file accept? | [Pack reference](03-pack-reference.md) |
| How do I add a pack without branching the engine? | [Authoring packs](04-authoring-packs.md) |
| Does the bootstrap enforce approval or execute skills? | [Security](06-security.md#human-approval-boundary) |
| Which Hermes version and installation paths are verified? | [Hermes integration](08-hermes-integration.md) |
| Where are install, run, resume, and recovery commands? | Not published yet; the runbook is a Phase 8 deliverable |
| Which future phase owns a missing surface? | [Implementation roadmap](plans/2026-07-10-wingstaff-bootstrap-and-roadmap.md) |

## Verification

Check all repository Markdown links and anchors with:

```bash
python scripts/check_md_links.py .
```

The repository-wide verification gate is defined in [`/AGENTS.md`](../AGENTS.md).
