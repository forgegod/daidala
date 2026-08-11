# CHG-0008: Focus routed workflow configuration

**Status:** done
**Source request:** Direct operator request: "While creating a new workflow there are also links to \"Manage packs\", \"Register repository\" or \"Manage sources\" that opens the configuration above the current view but do not jump to them visually so it's hard for the user to see the effect of this links"
**Affected capabilities:** CAP-0003
**Created:** 2026-08-11

## Outcome

Start-workflow configuration links visibly move focus to the requested Config panel while preserving the browser-local workflow draft and its return path.

## Scope

- Add routed Config-panel scroll and keyboard focus in `dashboard/dist/index.js`.
- Add focused regression coverage in `tests/test_dashboard_assets.py`.
- Update CAP-0003 and the dashboard DOX contract; static wireframes remain unchanged because they cannot represent navigation focus or scroll behavior.

## Phases

| Phase | Status | Verification gate |
|---|---|---|
| Vertical slice | done | `python -m pytest tests/test_dashboard_assets.py -q`, focused Ruff and Node syntax checks, and the browser probe pass; routed Config panels receive focus at viewport top with the requested tab selected. |
| Closeout | done | `700 passed`; record/link checks, Lefthook, Ruff, pack validation, build, Twine, release checks, and packaged-dashboard assertions pass. |

## Decisions

- Keep the Start workflow mounted so its browser-local draft remains intact.
- Focus and scroll the routed Config section after React renders it instead of reordering or duplicating configuration content.

## Evidence

- All 30 dashboard asset tests pass; focused Ruff and Node syntax checks pass.
- A host-isolated Chromium probe exercised Manage sources, Manage packs, and Register repository. Each route selected Constraints, Packs, and Runbook respectively, focused `daidala-config`, and placed the panel at viewport top with no console errors.
- Static wireframes remain unchanged because scroll position and keyboard focus are interaction behavior rather than a distinct screen state.
- Record and Markdown-link checks, Lefthook validation, 700 tests, Ruff, both pack validators, package build, Twine, release-content verification, and packaged-dashboard focus assertions pass.
