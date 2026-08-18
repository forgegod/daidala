# CHG-0029: Clear bootstrap preview after successful apply

**Status:** done
**Source request:** Direct operator request: "If I apply the default policy to the new repository the 'Bootstrap preview' UI element does not disappear so the user is missing a feedback that it worked"
**Affected capabilities:** CAP-0006
**Created:** 2026-08-18

## Outcome

After a confirmed bootstrap apply succeeds, the Bootstrap preview panel
disappears from the inspected row. The success message and the row's
pending pull-request link are the feedback that the apply worked, and the
pending link remains the durable follow-up until the repository is
registered.

## Scope

- Clear the browser `bootstrapPreview` state after a successful
  `POST /repository-registration/bootstrap` apply in
  `dashboard/dist/index.js`; the public PR link stays reachable through
  the profile-local pending-bootstrap receipt that inventory projects onto
  the row.
- Update the `tests/test_dashboard_assets.py` repository-registration UI
  contract to pin the clear-on-success behavior.
- Update CAP-0006 behavior text, the `dashboard/AGENTS.md` contract, and
  the `docs/07-runbook.md` bootstrap paragraph.

Not in scope: the registration preview panel lifecycle, CLI bootstrap
output, and the server response shape (the `applied` flag and links
remain in the response).

## Phases

| Phase | Status | Verification gate |
|---|---|---|
| Vertical slice | done | `.venv/bin/python -m pytest tests/test_dashboard_assets.py tests/test_dashboard_api.py -q` exited 0 |
| Closeout | done | `python scripts/check_records.py . && python scripts/check_md_links.py . && lefthook validate && .venv/bin/python -m pytest && ruff check . && python -m build && python -m twine check dist/* && python scripts/check_release_contents.py . --wheel dist/*.whl` exited 0 |

## Decisions

- The preview panel is the apply authority, not the receipt: after success
  it has nothing left to confirm, and the persistent feedback already
  lives in the success message and the row's pending PR link, which is
  receipt-backed and survives a Hermes restart.
- A failed apply keeps the panel: the preview digest is still valid and
  the operator can retry.

## Evidence

- Focused `tests/test_dashboard_assets.py tests/test_dashboard_api.py`
  suite passed with the scoped `applyBootstrap` clear-on-success pins.
- Full closeout gate passed: records, markdown links, lefthook validate,
  full `pytest`, ruff, build, twine check, and release-content check all
  exited 0.
- No wireframe regeneration was required: the static CAP-0006 wireframe
  depicts the pre-apply state, which is unchanged.
