# CHG-0020: Worker gateway readiness

**Status:** in-progress
**Source request:** Direct operator request: "I would like to have this check implemented in the "readiness" check in the workflows overview also while creating the workflow, that that corresponding/required/mandatory geteway have to be up and running -- if I'm right with my conclusio" Continued: also treat "Cannot record required skill activation: the active card is assigned to default but the workflow binds define to daidala-self-improvement. Align the card assignee/stage profile and retry." as a readiness constraint.
**Affected capabilities:** CAP-0001, CAP-0003
**Created:** 2026-08-16

## Outcome

Start and dashboard readiness name the selected worker profiles' Hermes
gateways as mandatory, and refuse a live card whose assignee does not match
the workflow-bound stage profile. A stopped worker gateway or an assignee
mismatch blocks start and appears as the next missing condition on Workflows.

## Scope

- Shared start preflight refuses a graph when any selected stage assignee
  gateway is not running, or when a live card assignee does not match the
  bound stage profile.
- Start readiness, Workflows overview guidance, and on-demand setup analysis
  expose those path-free worker-gateway and assignee-alignment facts.
- Tests, CAP-0001/CAP-0003, the operator runbook, and the CAP-0003 wireframe
  stay in the same vertical slice.

## Phases

| Phase | Status | Verification gate |
|---|---|---|
| Vertical slice | done | `python -m pytest tests/test_gateway.py tests/test_assignee_alignment.py tests/test_kanban.py tests/test_skills.py tests/test_dashboard_advice.py tests/test_dashboard_api.py tests/test_dashboard_assets.py -q` |
| Informative start readiness | done | `python -m pytest tests/test_dashboard_assets.py tests/test_dashboard_api.py tests/test_skills.py tests/test_assignee_alignment.py tests/test_gateway.py -q` |
| Ignore terminal cards | done | `python -m pytest tests/test_assignee_alignment.py tests/test_dashboard_api.py -q` |
| Closeout | pending | `python scripts/check_records.py . && python scripts/check_md_links.py . && python -m pytest tests/test_dashboard_assets.py tests/test_dashboard_api.py tests/test_skills.py tests/test_assignee_alignment.py tests/test_gateway.py -q && ruff check dashboard/plugin_api.py dashboard/dist/index.js daidala/service.py` |

## Decisions

- Require the selected worker profile gateways, not "any Hermes gateway".
  Cards are assigned to those profiles; the operator-actionable command is
  `hermes -p <worker> gateway start`.
- Keep the probe off the five-second workflow poll. Overview uses a one-shot
  readiness read; start uses the existing on-demand preflight.
- Do not add a dashboard control that starts a gateway.
- Card assignee versus bound stage profile is the same fail-closed rule
  already used by skill activation. Reassigning a Ready card without updating
  the ledger is a readiness blocker, not a workaround.
- Archived and done cards are not live. Overview readiness ignores them for
  assignee alignment and does not keep probing their bound worker gateways.
- Check readiness must run before Preview is available. The readiness result
  is informative and does not block Preview. Start remains fail-closed.

## Evidence

- `python -m pytest tests/test_assignee_alignment.py tests/test_dashboard_api.py -q` passed.
- `ruff check daidala/service.py dashboard/plugin_api.py tests/test_assignee_alignment.py tests/test_dashboard_api.py` passed.
- `python -m pytest -q` passed for the earlier vertical slice.
- `python scripts/check_records.py .` and `python scripts/check_md_links.py .` passed for the earlier vertical slice.
