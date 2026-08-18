# CHG-0028: Multiple notification target identities

**Status:** pending
**Source request:** Direct operator request: "For a migration path between different slugs, or supporting multiple users, it would be a value add to support multiple identities for 'Notification target' -- if this does not contradict Daidala's architecture/principles"
**Affected capabilities:** CAP-0004
**Created:** 2026-08-18

## Outcome

A registration can declare several attended notification identities, each an
explicit pair of one `target` slug and one exact Hermes `destination`.
Notification receipts still match exactly one declared identity, the
destination is still the single delivery address, and the notification
prerequisite evidence binds one identity pair per registration.

## Scope

- Extend the registration/registration-defaults notification model from one
  `{target, destination}` pair to a bounded, duplicate-free list of
  `{target, destination}` identities (adapter stays `hermes-gateway`).
- Update strict parsing, canonical serialization, and exact-field checks in
  `daidala/registrations.py` and `daidala/repository_registration.py`,
  including the defaults-to-registration copy and the defaults wizard preview.
- Update `HermesGatewayNotificationAdapter` construction so each delivery is
  bound to the identity pair the operator selected for that registration, and
  `validate_notification_receipt` plus `_check_notification`
  (`daidala/prerequisites.py`) accept a receipt only when its
  `target_alias` and the delivery destination match one declared identity.
- Extend the registration-defaults wizard in `dashboard/dist/index.js`
  (repeatable identity rows), its field help, `dashboard/AGENTS.md` contract
  text, and `docs/07-runbook.md` Attended notifications section.
- Tests: strict parse/round-trip for the new shape, legacy one-pair input,
  duplicate and cross-bound receipt rejection, prerequisite check against
  multiple identities, defaults-wizard field help and preview projection.
- Update CAP-0004 behavior text, its wireframe (regenerated at the manifest
  viewport), and `dashboard/AGENTS.md`.

Not in scope: multiple maintained destinations on one registration without
per-destination identities, multi-actor attended approval, and message-content
changes (subject, salutation, body).

## Phases

| Phase | Status | Verification gate |
|---|---|---|
| Design decision | pending | `## Decisions` records the identity-pair decision, the legacy-compatibility choice, and the explicit rejection of slug migration without a destination change |
| Vertical slice | pending | Focused `pytest` over `tests/test_repository_registration.py`, `tests/test_live_adapters.py`, `tests/test_prerequisites.py`, `tests/test_dashboard_api.py`, `tests/test_dashboard_assets.py` exits 0 |
| Closeout | pending | `python scripts/check_records.py . && python scripts/check_md_links.py . && lefthook validate && .venv/bin/python -m pytest && ruff check .` exits 0 with CAP-0004 and its wireframe regenerated |

## Decisions

- Pending implementation.
- Pre-bound by architecture: the integrity chain is
  registration identity → `NotificationReceipt.target_alias` →
  `validate_notification_receipt` (`daidala/controller.py`) and
  `_check_notification` (`daidala/prerequisites.py`), with receipts persisted
  as cycle evidence. A receipt proves delivery to one exact destination, so a
  slug alone cannot migrate to a different destination — old receipts stay
  bound to the old destination and are not re-attested by accepting a new
  slug. Supporting "multiple users" means multiple
  `{target, destination}` identities, not several slugs for one destination.

## Evidence

Pending phase verification.
