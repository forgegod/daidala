# CHG-0003: Readiness-analysis prerequisites

**Status:** done
**Source request:** Direct operator request: "Add further test to the AI supported readyness analysis: (1) we need at least one registered github project (2) skill pack need to be present with at least one skills installed per phase; blocked skill packs should be unblocked (*) Identify further apsepects to get Daidala working into the analysis"
**Affected capabilities:** CAP-0003
**Created:** 2026-08-11

## Outcome

The explicit dashboard readiness analysis supplies the host model with path-free deterministic facts for a registered GitHub Project and per-phase workflow-pack skill coverage, along with existing registration, workflow, and artifact readiness evidence.

## Scope

- Derive counted setup requirements from existing configuration and pack-check projections.
- Identify registered GitHub Project availability, installed and ready skill coverage for every declared lifecycle phase, and blocked packs without exposing paths, credentials, project identifiers, or blocker text.
- Keep the model request explicit, advisory-only, and unable to modify pack availability.

## Phases

| Phase | Status | Verification gate |
|---|---|---|
| Vertical slice | done | `74 passed`: `pytest tests/test_dashboard_advice.py tests/test_dashboard_api.py tests/test_dashboard_assets.py`; focused Ruff passed. |
| Closeout | done | Full repository, release, record, pack, syntax, lint, and hook gates passed. |

## Decisions

- The analysis receives aggregate counts and boolean readiness outcomes, not project IDs, pack source URLs, skill names, raw blockers, or installation commands.
- A pack is blocked only when its existing check reports blockers. Missing or disabled skills remain separate aggregate facts so the model can guide the operator to Config → Packs without treating a model response as authority.

## Evidence

- Focused dashboard advice, API, and asset tests passed (74 tests).
- Focused Ruff checks and `git diff --check` passed.
- Full test suite passed (698 tests); record/link checks, Ruff, Lefthook, pack
  validation, JavaScript syntax checks, build, Twine, and release-content checks
  passed.
- Wireframes are unchanged because the existing browser UI and interaction
  contract are unchanged; this change only broadens the server-derived advice
  snapshot.
