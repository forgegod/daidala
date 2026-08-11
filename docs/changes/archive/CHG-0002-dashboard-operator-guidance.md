# CHG-0002: Dashboard operator guidance

**Status:** done
**Source request:** Direct operator request: "I would like to have more decriptive text for the different screens, like the workflow. The descriptive text should explain what that screen is for or what is missing. It could be possible to create here a AI generated message that result in an analysis of the current situation and give the user advice how to enable the power of Daidala. E.g. the curator model could be used to analyse the situation and give the user advice how to proceed as next."
**Affected capabilities:** CAP-0003
**Created:** 2026-08-11

## Outcome

The operator dashboard explains the purpose and missing prerequisites of each primary screen and can request a bounded, advisory-only setup analysis from the Hermes host model.

## Scope

- Add screen-specific purpose, empty, unavailable, and next-step guidance for Workflows, Artifacts, and Config.
- Add an explicit on-demand setup-analysis route and panel that sends only the existing path-safe configuration/readiness projection to a host-owned structured LLM call.
- Keep model advice non-authoritative and non-mutating; failures remain explicit and do not replace deterministic workflow recommendations.
- Update CAP-0003, dashboard contracts, focused tests, and its generated wireframe.

## Phases

| Phase | Status | Verification gate |
|---|---|---|
| Vertical slice | done | `pytest tests/test_dashboard_advice.py tests/test_dashboard_api.py tests/test_dashboard_assets.py tests/test_dashboard.py tests/test_plugin.py` — 89 passed |
| Closeout | done | `python scripts/check_records.py . && python scripts/check_md_links.py . && pytest && ruff check .` — all passed |

## Decisions

- The existing Daidala curator is the artifact-retention service, not an LLM. The dashboard names the new capability setup analysis rather than overloading curator terminology.
- Hermes' documented plugin facade exposes the active configured host model, not the `auxiliary.curator` slot. The approved implementation uses `ctx.llm` and reports unavailable on hosts without that facade rather than importing Hermes internals.
- The browser cannot trigger actions from model text. Advice is bounded to existing screen links and native CLI/runbook guidance.

## Evidence

- Focused dashboard, API, host-model, and plugin-registration tests passed: 89 passed.
- Regenerated and rendered `CAP-0003` wireframe at 1440 × 960; the visual review shows workflow supervision and readiness advice without clipping core content.
- Full suite passed: 697 passed. `ruff check .`, `lefthook validate`, record/link checks, JavaScript syntax checks, and both pack validations passed.
- Built sdist and wheel; `twine check dist/*` and `check_release_contents.py . --wheel dist/*.whl` passed.
