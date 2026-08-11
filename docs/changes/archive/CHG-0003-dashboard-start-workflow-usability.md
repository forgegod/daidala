# CHG-0003: Improve Start workflow usability

**Status:** done
**Source request:** Direct operator request: "(1) I've installed daidala and found the \"Packs\" select/drop-down element within \"Start workflow\" at http://localhost:9119/daidala does not offer the available \"addyosmani\" and \"aidlc\", even if the are \"blocked\" (or \"not checked\"); (2) Add also a button/link to register a repository (3) While creating a new workflow switching to \"Artifacts\" or \"Config\" does not work; disable these menu items to prevent loosing the edit -- if appropriate"
**Affected capabilities:** CAP-0003
**Created:** 2026-08-11

## Outcome

Start workflow lists every bundled pack with its current readiness state, exposes a repository-registration guidance entry point, and makes unavailable primary navigation explicit while the browser-only draft is open.

## Scope

- Update the dependency-free dashboard bundle and focused asset regressions.
- Amend the operator-dashboard capability and nearest DOX contracts.
- Preserve the path-free registration boundary and existing preview/confirm workflow authority.

## Phases

| Phase | Status | Verification gate |
|---|---|---|
| Vertical slice | done | `.venv/bin/python -m pytest tests/test_dashboard_assets.py tests/test_dashboard_api.py -q` |
| Closeout | done | Repository record, lint, pack, test, and package gates pass. |

## Decisions

- Repository registration remains profile-local and outside the browser because a valid registration contains trusted paths, credentials, attended identity, and evaluator authority. The new Start entry point links to explicit dashboard runbook guidance rather than inventing a partial registration mutation.
- Blocked and unchecked packs remain selectable; server-owned readiness and preview gates continue to prevent an invalid start.

## Evidence

- Focused dashboard asset regressions pass for inventory-backed pack states, the repository-registration entry point, and disabled draft-unsafe navigation.
- A Hermes 0.20.0 browser smoke test rendered `addyosmani · blocked` and `aidlc · blocked`, exposed the `Register repository` link, and reported Artifacts and Config as disabled while Start workflow remained open.
- Record and Markdown-link checks, Lefthook validation, 683 tests, Ruff, both pack validators, package build, Twine, and release-content verification pass.
