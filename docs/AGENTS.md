# docs/

## Purpose

Own current architecture documentation, the numbered reading set, and executable implementation plans.

## Ownership

- `README.md` is the only reading-order, support-status, and symptom-routing index.
- `00-getting-started.md` owns the executable first-run operator walkthrough.
- `01-architecture.md` owns process and component boundaries.
- `02-workflow-state.md` owns the Wingstaff policy ledger, Hermes Kanban state
  authority, and transition-ownership contract.
- `03-pack-reference.md` owns the implemented workflow-pack schema.
- `04-authoring-packs.md` owns pack-neutral adapter authoring.
- `05-lifecycle-stages.md` owns executable stage inputs, outputs, and gates.
- `06-security.md` owns current trust boundaries and unavailable controls.
- `08-hermes-integration.md` owns verified Hermes versions, discovery paths, and installation limitations.
- `09-pack-adapters.md` owns implemented pack mappings and divergences.
- `10-autonomous-development-use-cases.md` owns user-oriented task selection,
  skill handoffs, steering controls, tutorial ideas, and future use cases.
- `11-skill-usage-and-user-control.md` owns the design contract for card-scoped
  skill loading, cross-stage handoff, and user selection boundaries.
- `plans/` contains self-contained plans for future implementation sessions.

## Local Contracts

- Plans name exact files, verification gates, stop conditions, and unresolved decisions.
- Describe the current intended design without iteration diaries or stale migration breadcrumbs.
- Runtime claims must be grounded in Wingstaff source or current official Hermes documentation.
- Future numbered documents appear as unlinked support-status entries until their behavior exists.
- Runtime documents name their source-of-truth modules and verification tests.
- Use repository-relative links locally and authoritative upstream URLs for external claims.

## Work Guidance

- Update the active plan when a design decision changes before implementation begins.
- Move stable implemented contracts into normal architecture/operator docs rather than leaving the plan as the only source.
- Give new operators one user-centric, executable starting path before directing
  them to architecture or reference material. State what starts the workflow,
  what must remain running, what the user observes, and which action comes next.
- Keep deterministic behavior distinct from skill or model judgment.
- Do not publish operator commands until they have been exercised against the supported Hermes version.

## Verification

```bash
python scripts/check_md_links.py .
```

- Confirm Mermaid diagrams show Wingstaff inside the existing Hermes process, never as a server.
- Audit runtime claims against `wingstaff/`, `tests/`, and current official Hermes documentation.

## Child DOX Index

*(empty — `docs/` has no nested contract boundary.)*

See [`/AGENTS.md`](../AGENTS.md).
