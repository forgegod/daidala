# CHG-0027: Registration defaults maintainer usage

**Status:** done
**Source request:** Direct operator request: "did you also described for what this is used? update the documentation within this project accordingly"
**Affected capabilities:** CAP-0004
**Created:** 2026-08-17

## Outcome

The Maintainers field and matching operator docs state what the list is
used for: copied onto each new registration, it gates cycle admission,
issue claim comments, and notification prerequisite evidence, and it is
not dashboard plan approval.

## Scope

- Extend the defaults-wizard Maintainers help with usage.
- Keep the same usage in the runbook, CAP-0004, dashboard contract,
  self-improvement docs, asset tests, and CAP-0004 wireframe.
- Do not change validation, preview/apply authority, or comparison.

## Phases

| Phase | Status | Verification gate |
|---|---|---|
| Vertical slice | done | `.venv/bin/python -m pytest tests/test_dashboard_assets.py -q` exited 0 |
| Closeout | done | `python scripts/check_records.py . && python scripts/check_md_links.py . && lefthook validate && .venv/bin/python -m pytest && ruff check .` exited 0 |

## Decisions

- Usage is the three live allowlist checks: ready-label admission actor,
  GitHub claim-comment author, and `authorized_maintainer` in notification
  prerequisite evidence.
- Dashboard exact-plan approval stays out of this list.

## Evidence

- Config wizard Maintainers help names the three allowlist uses and excludes
  dashboard plan approval.
- Runbook, CAP-0004, dashboard contract, docs/15, docs/16, asset tests, and
  CAP-0004 wireframe at 1440 × 2040 match that usage.
- Closeout gate passed: records, markdown links, lefthook, pytest (803), ruff.
