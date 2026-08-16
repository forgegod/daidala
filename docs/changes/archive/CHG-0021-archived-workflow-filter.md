# CHG-0021: Archived workflow filter

**Status:** done
**Source request:** Direct operator request: "How can the workflow 7af035cc-4a16-42c3-8f89-56d32be050e5 be resolved because the underlaying card is gone and the status is stale?" Continued: "I've restarted hermes agent and gateways and dashboard but the workflow card is shown" and "so we need also a kind of filter to show archived workflows".
**Affected capabilities:** CAP-0003
**Created:** 2026-08-16

## Outcome

The Workflows view hides fully archived workflows by default, offers an explicit archived-workflow filter, and renders archived workflow history without invented pending stages or decisions.

## Scope

- Derive a read-only archived lifecycle projection only when every persisted Kanban card reference is live and archived.
- Preserve the audit ledger and its archived card history; do not add a workflow-state mutation or delete any record.
- Add a default-off archived filter, terminal rendering, regression coverage, CAP update, and regenerated CAP-0003 wireframe.

## Phases

| Phase | Status | Verification gate |
|---|---|---|
| Vertical slice | done | `.venv/bin/python -m pytest tests/test_dashboard.py tests/test_dashboard_assets.py tests/test_dashboard_api.py -q` |
| Closeout | done | `python scripts/check_records.py . && python scripts/check_md_links.py . && lefthook validate && .venv/bin/python -m pytest && ruff check . && daidala packs validate addyosmani && daidala packs validate aidlc && .venv/bin/python -m build && .venv/bin/python -m twine check dist/* && .venv/bin/python scripts/check_release_contents.py . --wheel dist/*.whl` |

## Decisions

- An archived workflow is a read-model conclusion, not a new persisted policy-ledger status: every persisted card reference must be present in the live snapshot and have status `archived`.
- The default Workflows view prioritizes active supervision. Archived workflows remain visible only through the explicit filter and exact-ID routes.

## Evidence

- The focused dashboard suite passed: 107 tests across backend, assets, and API.
- The full suite passed: 796 tests. Ruff, link/record checks, Lefthook, both pack
  validations, wheel build, Twine, and release-content checks passed.
- The live default-profile projection classifies workflow
  `7af035cc-4a16-42c3-8f89-56d32be050e5` as `archived` without mutating its
  ledger or Kanban cards.
