# CHG-0001: Adopt application records

**Status:** done
**Source request:** Direct operator request: "I would like to keep the old planing files as historical information but switch the the new approach for future steps"
**Affected capabilities:** CAP-0001, CAP-0002, CAP-0003
**Created:** 2026-08-10
**Completed:** 2026-08-10

## Outcome

Daidala uses capability records for current material behavior and change records for future material implementation progress. Existing files under `docs/plans/` remain unchanged historical provenance and never become competing progress authorities.

## Scope

- Add the canonical product capability and change-record boundaries.
- Track the repository-owned application-record adoption skills and their DOX
  boundaries.
- Establish a source-and-test-backed baseline of three implemented capabilities.
- Add a current static wireframe for the primary operator dashboard surface.
- Add deterministic record validation and repository guidance.
- Preserve every existing planning file and plan-owned design artifact in place.

## Phases

| Phase | Status | Verification gate |
|---|---|---|
| Record contract | done | CAP/CHG directories, templates, indexes, and contributor routing exist. |
| Baseline capabilities | done | Each CAP links current runtime source and executable tests; the dashboard CAP links an HTML/PNG pair. |
| Validation | done | Record checker regressions, record validation, Markdown links, and affected behavior tests pass. |
| Closeout | done | Full repository verification passes and this CHG is archived as done. |

## Decisions

- New material work uses one active `docs/changes/active/CHG-*.md` as progress authority.
- `docs/plans/` is historical. No existing plan, execution contract, Pen source, or review render is moved or rewritten by this migration.
- Architecture, lifecycle, security, setup, and runbook documents retain their current ownership.
- Wireframes are required only for capabilities that create or materially change a primary human-facing surface.

## Evidence

- `node docs/product/wireframes/generate.mjs --render` generated the CAP-0003
  HTML, index, manifest, and 1440 × 960 PNG from one repository-owned source.
- Visual inspection confirmed complete shell/navigation, legible normal and
  attended states, and explicit empty/unavailable guidance using synthetic data.
- `python -m pytest tests/test_check_records.py`: 4 passed.
- `python scripts/check_records.py .`: 3 capabilities, 1 change record, and 1
  wireframe passed validation.
- `python -m pytest`: 681 passed.
- `ruff check .` and `lefthook validate`: passed.
- Both workflow packs validated.
- Wireframe regeneration produced byte-identical HTML, index, manifest, and PNG
  artifacts.
- `python -m build`, `python -m twine check dist/*`, and the release-content
  check over a temporary complete Git index passed.
- Markdown links, changed-table structure, and `git diff --check` passed.
- `git diff --name-only -- docs/plans/'P*.md' docs/plans/'*.json'
  docs/plans/'*.pen' docs/plans/'*.png'` returned no paths; historical plan and
  design files were not modified.
