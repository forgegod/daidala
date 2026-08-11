# CHG-0006: Manage pack skill availability

**Status:** done
**Source request:** Direct operator request: "Would it be possible to install/uninstall skills within the configuration pack view? (1) Instead of mentioning that this skill should be installed, add install/uninstall buttons (2) add also the option/buttons to install/uninstall all skills from the package (3) add also a click-able link to the source of the skill"; clarified to use the Hermes dashboard's enable/disable behavior instead of uninstall.
**Affected capabilities:** CAP-0003
**Created:** 2026-08-11

## Outcome

Config → Packs manages declared skills through preview-confirmed install, enable, and disable actions, links each skill to its source, and computes readiness from exact content plus enabled state.

## Scope

- Extend the typed pack service and dashboard routes with bounded individual and pack-wide skill actions.
- Use Hermes' active-profile `skills.disabled` contract; preserve installed skill content and provenance.
- Add exact external and bundled source links without fetching uninstalled skill content.
- Update the maintained dashboard assets, focused tests, CAP-0003, operator guidance, and owning DOX contracts.

## Phases

| Phase | Status | Verification gate |
|---|---|---|
| Vertical slice | done | `pytest tests/test_packs.py tests/test_pack_service.py tests/test_dashboard_api.py tests/test_dashboard_assets.py` |
| Closeout | done | Record validation and repository verification in `/AGENTS.md`. |

## Decisions

- Replace uninstall with reversible active-profile enable/disable semantics matching Hermes' Skills dashboard.
- Disabled declared skills are installed but not pack-ready.
- Individual and pack-wide mutations require a fresh action-specific preview digest and literal confirmation.
- External source links target the pack's exact pinned revision; bundled source links target the Daidala source tree.

## Evidence

- Full `pytest`, `ruff check .`, focused Ruff formatting, `lefthook validate`,
  JavaScript syntax, record, and Markdown-link checks pass.
- Both bundled packs validate with source links and enabled-state projections.
- An isolated authenticated-SDK browser probe verified individual and pack-wide
  install preview/confirm/apply, exact pinned source links, disabled button
  states, Ready convergence, and zero console errors without touching a real
  Hermes profile.
- Wheel and source distribution build, Twine metadata, and release-content
  checks pass.
