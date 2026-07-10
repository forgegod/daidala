# docs/

## Purpose

Own current architecture documentation, the numbered reading set, and executable implementation plans.

## Ownership

- `README.md` is the only reading-order, support-status, and symptom-routing index.
- `01-architecture.md` owns process and component boundaries.
- `03-pack-reference.md` owns the implemented workflow-pack schema.
- `04-authoring-packs.md` owns pack-neutral adapter authoring.
- `06-security.md` owns current trust boundaries and unavailable controls.
- `08-hermes-integration.md` owns verified Hermes versions, discovery paths, and installation limitations.
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
