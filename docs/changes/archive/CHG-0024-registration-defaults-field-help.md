# CHG-0024: Registration defaults field help

**Status:** done
**Source request:** Direct operator request: "During the implementation of CHG-0022 for the \"Registration defaults\" I would like to have some explementation for each of the form elements, e.g. explain what is the \"Intake alias\" for, how the alias should be choosen (is there a special naming format the user have to satisfy), where is it used for, why does it matter. The explenations should help the user to make the right decission without reading the documentation first"
**Affected capabilities:** CAP-0004
**Created:** 2026-08-17

## Outcome

The Config → GitHub Repositories registration-defaults wizard explains each
field in place: purpose, allowed format, and why the value matters. Operators
can complete the form without opening the runbook first.

## Scope

- Add per-field decision help and example placeholders on the defaults wizard.
- Pin the help contract in dashboard asset tests.
- Update CAP-0004, the CAP-0004 wireframe, and dashboard DOX.
- Do not change validation rules, preview/apply authority, or collect tokens.

## Phases

| Phase | Status | Verification gate |
|---|---|---|
| Vertical slice | done | `.venv/bin/python -m pytest tests/test_dashboard_assets.py -q` exited 0 (34 tests) |
| Closeout | done | `python scripts/check_records.py . && python scripts/check_md_links.py . && lefthook validate && .venv/bin/python -m pytest && ruff check .` exited 0 |

## Decisions

- The request names CHG-0022; the wizard shipped in CHG-0023. This change
  extends that wizard only.
- Help text restates the existing parser contract. It does not invent new
  formats or make unused limits sound like live runtime gates.
- Help stays visible under each label. It is not hidden behind a tooltip.

## Evidence

- Config wizard fields now show grouped decision help and example placeholders.
- Dashboard asset tests pin the help contract and CSS class.
- CAP-0004 wireframe regenerated at 1440 × 1480 with visible field help and
  both confirmation actions unclipped.
- Closeout gate passed: records, markdown links, lefthook, pytest, ruff.
