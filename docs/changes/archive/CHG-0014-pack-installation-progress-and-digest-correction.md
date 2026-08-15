# CHG-0014: Pack installation progress and digest correction

**Status:** done
**Source request:** Direct operator request: "(1) While installaing the skills (pack) there is no information about the progress. A simple counter and name of the skill is installed would be here good starting point. (2) I've also a unexpected digest missmatch e.g. for api-and-interface-design skill: Expected 323281e521320a8dcf8b70db1175da12d2c42c02201ffc1395adeb0503d20e55 · observed 0f762ddae2eb0c21141536d9fd755e39ce3306095fe8c63c999e1ab542db0f07"
**Affected capabilities:** CAP-0003, CAP-0007
**Created:** 2026-08-15

## Outcome

Config → Packs shows the current skill name and completed/total counter while
one preview-confirmed pack installation is running. The Addyosmani catalog's
expected digests match the exact bundles produced by Hermes from the pinned
source revision.

## Scope

- Stream bounded per-skill progress from the existing pack-wide installation
  action without polling, process-global job state, or exposing individual
  installation controls.
- Render an accessible progress status in Config → Packs and retain the existing
  final success, stale-preview, and partial-failure behavior.
- Replace incorrect Addyosmani expected digests with digests measured from a
  fresh isolated Hermes installation of the pinned raw targets.
- Repin this repository's committed Addyosmani pack identity to the corrected
  canonical pack digest without changing its source revision.
- Update CAP-0003, CAP-0007, the CAP-0007 wireframe, owning DOX contracts, and
  focused service, dashboard API, and browser-asset tests.

## Phases

| Phase | Status | Verification gate |
|---|---|---|
| Operator approval | done | The operator approved CHG-0014 on 2026-08-15. |
| Vertical slice | done | Focused pack service, dashboard API/assets, JavaScript syntax, pack validation, and record checks pass. |
| Closeout | done | Repository verification and fresh isolated Hermes digest comparison pass. |

## Decisions

- Preserve one logical pack-wide mutation. The recommended transport is a bounded
  streamed response from the existing service iteration, not browser-driven
  individual installs or a background job registry.
- Progress identifies only the ordinal, total, current catalog skill, and bounded
  state; command output and local paths remain hidden.
- Investigation found 19 installed-bundle mismatches in the 24-skill Addyosmani
  catalog. The reported `api-and-interface-design` observed digest exactly
  matches both the pinned raw source and the isolated Hermes-installed bundle.
- Preserve the existing JSON pack-install route for CLI and non-streaming API
  callers; Config → Packs uses the bounded progress stream.

## Evidence

- `api-and-interface-design` hashes to
  `0f762ddae2eb0c21141536d9fd755e39ce3306095fe8c63c999e1ab542db0f07`
  at pinned revision `bf223959faae96825f78ddf7bc33e114f3303c1e` and in the
  isolated Hermes installation.
- Comparing all 24 committed expectations with the retained fresh isolated
  Hermes installation found 19 mismatches; all 24 names are installed and
  enabled, so these are catalog-data defects rather than failed installations.
- 2026-08-15: direct operator approval — "Approve CHG-0014".
- The corrected catalog was checked against a fresh isolated Hermes installation:
  `skills=24 mismatches=0`.
- The CAP-0007 progress-state PNG was regenerated and visually reviewed; its
  one-based counter remains on one line, the current skill name remains legible,
  and no clipping or overlap was observed.
- `python -m pytest` passed with 760 tests. The project-local Python module
  invocation was used because the shell's bare `pytest` launcher resolves to a
  different user installation and cannot import the checkout package.
- `python scripts/check_records.py .`, `python scripts/check_md_links.py .`,
  `lefthook validate`, `ruff check .`, both pack validations, JavaScript syntax
  checks, `python -m build`, `python -m twine check dist/*`, and
  `python scripts/check_release_contents.py . --wheel dist/*.whl` passed.
