# CHG-0019: Workflow identity validation

**Status:** done
**Source request:** Direct operator request: "I set the \"Workflow identity (optional)\" to \"First Workflow\" and got following error message ... The problem is that there is no verfication in the UI neither those error message are only confirmed with 500 error in the UI"; approval: "approved"
**Affected capabilities:** CAP-0003
**Created:** 2026-08-16

## Outcome

Start workflow rejects an invalid optional workflow identity before any browser request, explains the allowed format beside the field, and returns a bounded client error instead of an HTTP 500 if a client bypasses the browser validation.

## Scope

- Normalize workflow-identity validation at the workflow service boundary.
- Add browser validation, accessible inline feedback, and request blocking for Start readiness and preview.
- Add API, service, and dashboard-asset regression coverage.
- Update CAP-0003, its generated wireframe, and the dashboard contract.

## Phases

| Phase | Status | Verification gate |
|---|---|---|
| Vertical slice | done | 2026-08-16: focused execution, dashboard API, and dashboard-asset tests passed; the generated wireframe was visually checked. |
| Closeout | done | 2026-08-16: root `AGENTS.md` gate passed — record/link checks, `lefthook validate`, full `pytest`, `ruff check .`, both pack validations, build, Twine, and release-content check. |

## Decisions

- Retain the existing safe identifier grammar; whitespace-containing display names cannot become profile-local artifact path identities.
- The service converts this expected validation failure to `ServiceError`, its public preflight boundary. Dashboard routes consequently return their existing HTTP 409 validation response without a route-specific exception list.
- The browser treats surrounding whitespace as absent because its request projection already trims the optional value.

## Evidence

- Invalid `First Workflow` input is blocked in the browser and presented as an
  accessible inline error; generated CAP-0003 wireframe confirms the field,
  error, and disabled readiness/preview controls are legible.
- Service preflight normalizes invalid workflow identities to `ServiceError`,
  and the dashboard API regression confirms its bounded HTTP 409 response.
- Focused tests, full `pytest`, lint, record/link validation, pack validation,
  package build, Twine, and release-content verification passed on 2026-08-16.
