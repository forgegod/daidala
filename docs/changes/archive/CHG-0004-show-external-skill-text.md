# CHG-0004: Show pinned external skill text

**Status:** done
**Source request:** Direct operator request: "In Daidala Config Packs view, I would like to view the content/text of the skill by selecting one. This is the case for \"aidlc\" but not for \"addyosmani\""
**Affected capabilities:** CAP-0003
**Created:** 2026-08-11

## Outcome

Config → Packs renders bounded literal `SKILL.md` text for declared Addyosmani skills before installation, while keeping installed readiness and source-preview identity distinct.

## Scope

- Add immutable, attributed Addyosmani `SKILL.md` display snapshots from the pack's pinned source revision.
- Extend the pack content projection and dashboard labels without treating display snapshots as installed activation providers.
- Add focused service, asset, and package-resource regressions; update CAP-0003 and nearest DOX contracts.
- Keep the existing CAP wireframe unchanged because its primary Workflows frame does not depict Config → Packs.

## Phases

| Phase | Status | Verification gate |
|---|---|---|
| Vertical slice | done | `pytest tests/test_pack_service.py tests/test_dashboard_api.py tests/test_dashboard_assets.py tests/test_installation.py` passed (81 tests). |
| Closeout | done | Record, lint, pack, test, build, Twine, and release-content gates passed. |

## Decisions

- Display-only source snapshots do not satisfy skill installation or digest readiness; they provide literal review text only.
- Preserve the upstream MIT license and exact source revision beside the snapshots.

## Evidence

- The focused 81-test pack-service, dashboard API/assets, and wheel-resource gate passes.
- All 20 declared Addyosmani snapshots and the MIT license are byte-identical to source revision `7ce442de03ddc1b72480c3b48d55c62880ea2a90`.
- `pytest` passed with 685 tests; Ruff, Lefthook, both pack validations, record and Markdown-link checks passed.
- Build and Twine checks passed; the release-content audit found 269 tracked files and 85 wheel members.
- Runtime smoke returned `pinned-source`, `available: true`, `installed: false`, and `ready: false` for uninstalled `addyosmani/interview-me`, preserving the readiness distinction.
- CAP-0003's Workflows wireframe stayed unchanged because it does not depict Config → Packs.
