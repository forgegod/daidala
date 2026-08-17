# CHG-0026: Registration defaults maintainer identity

**Status:** done
**Source request:** Direct operator request: "Explain this in the description of the field including what the GitHub username is: email adress, profile name etc."
**Affected capabilities:** CAP-0004
**Created:** 2026-08-17

## Outcome

The registration-defaults Maintainers field states that each identity is a
GitHub username (the login in the profile URL) and is not an email address,
display name, Hermes profile name, or Git author name.

## Scope

- Replace the Maintainers help on the Config defaults wizard.
- Keep the same wording in the runbook, CAP-0004, dashboard contract, and
  asset tests.
- Do not change validation, preview/apply authority, or the allowlist
  comparison.

## Phases

| Phase | Status | Verification gate |
|---|---|---|
| Vertical slice | done | `.venv/bin/python -m pytest tests/test_dashboard_assets.py -q` exited 0 (34 tests) |
| Closeout | done | `python scripts/check_records.py . && python scripts/check_md_links.py . && lefthook validate && .venv/bin/python -m pytest && ruff check .` exited 0 |

## Decisions

- The live admission actor is the GitHub `login` from the last
  `daidala-si:ready` label event, not a Hermes gateway identity.
- Help names that GitHub username as the profile-URL login and lists the
  common wrong values.

## Evidence

- Config wizard Maintainers help names the GitHub profile-URL login and
  rejects email, display name, Hermes profile, and Git author name.
- Runbook, CAP-0004, dashboard contract, asset tests, and CAP-0004 wireframe
  at 1440 × 1880 match that wording.
- Closeout gate passed: records, markdown links, lefthook, pytest (803), ruff.
