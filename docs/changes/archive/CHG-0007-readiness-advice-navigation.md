# CHG-0007: Readiness advice navigation

**Status:** done
**Source request:** Direct operator request: "(1) The readiness advice should link to the corresponding configuration tab for \"Resolve blocked workflow packs\" or \"Confirm phase skill coverage\"; right now the buttons are \"Open worflows\". (2) Check this also for the other advices integrated"
**Affected capabilities:** CAP-0003
**Created:** 2026-08-11

## Outcome

Readiness advice links to its exact dashboard destination, including the relevant Config tab for pack and skill-coverage remediation.

## Scope

- Replace generic advice screen targets with a closed set of exact dashboard destinations.
- Route pack and phase-skill readiness advice to Config → Packs and give every advice action a descriptive destination label.
- Update focused tests, CAP-0003, dashboard contract documentation, and the CAP wireframe.

## Phases

| Phase | Status | Verification gate |
|---|---|---|
| Vertical slice | done | `34 passed`: `pytest tests/test_dashboard_advice.py tests/test_dashboard_assets.py`; focused Ruff, JavaScript syntax, and diff checks passed. |
| Closeout | done | Full repository, record, package, and release-content gates passed. |

## Decisions

- Advice returns one closed `target` rather than a generic screen plus inferred tab, so the UI never derives navigation from model-provided prose.
- Blocked workflow packs and missing phase skill coverage require the `config-packs` target; all other advice uses the same closed destination set.

## Evidence

- `pytest`: 699 passed; `ruff check .`; `lefthook validate`; record and Markdown-link checks passed.
- Both bundled packs validated; JavaScript syntax and `git diff --check` passed.
- Wheel and source distribution build, Twine metadata, and release-content checks passed.
- The regenerated 1440 × 960 CAP wireframe visibly shows `Resolve blocked workflow packs` with a readable `Open Config → Packs` control and no clipping or overlap.
