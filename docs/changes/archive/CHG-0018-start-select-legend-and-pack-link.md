# CHG-0018: Start select legend and Manage packs link

**Status:** done
**Source request:** Direct operator request: "In "Start workflow" (1) change the text "Registered repository" to "Registered repository (<repo> * <board> * <profile>)" explaining the elements in the select -- if I undertsand the format right (2) The styling of "Manage packs" looks not like a link (not blue)"
**Affected capabilities:** CAP-0003
**Created:** 2026-08-15

## Outcome

The Start registered-repository select names its three fields in order
`repo · board · profile`. Manage packs uses the same accent link color as
Register repository. Start states that the repository profile and the worker
profile default are different jobs and that a mismatch is allowed.

## Scope

- Change the select label to a field legend and reorder option text to
  `repository · board · profile`.
- Style Start heading links with the wizard accent color.
- Show that the repository `<profile>` owns the registration while Worker
  profile default assigns card runners, including the allowed-mismatch
  implication.
- Update CAP-0003 and the focused dashboard asset test.

## Phases

| Phase | Status | Verification gate |
|---|---|---|
| Operator approval | done | Operator requested the select legend and the blue Manage packs link. |
| Vertical slice | done | 2026-08-15: `python -m pytest tests/test_dashboard_assets.py -q` passed; `python scripts/check_records.py .` and `python scripts/check_md_links.py .` exit 0. |
| Worker implication | done | 2026-08-15: `python -m pytest tests/test_dashboard_assets.py -q` passed; `python scripts/check_records.py .` and `python scripts/check_md_links.py .` exit 0. |
| Copy placement | done | 2026-08-15: `python -m pytest tests/test_dashboard_assets.py -q` passed; `python scripts/check_records.py .` and `python scripts/check_md_links.py .` exit 0. |
| Closeout | done | 2026-08-15: root `AGENTS.md` gate passed — `python scripts/check_records.py .`, `lefthook validate`, `python -m pytest`, `ruff check .`, `daidala packs validate addyosmani`, `daidala packs validate aidlc`, `python -m build`, `python -m twine check dist/*`, and `python scripts/check_release_contents.py . --wheel dist/*.whl`. |

## Decisions

- The live option text was `repo · profile · board`. The operator asked for
  `repo * board * profile`. Keep the existing middle-dot separator and adopt
  the requested field order.
- Do not change selection values, inventory, or uniqueness classification.
- Do not force Worker profile default to equal the registration profile.

## Evidence

- Worker implication: focused dashboard asset tests and record/link checks passed.
- Closeout: root `AGENTS.md` verification passed on 2026-08-15, including
  `python -m pytest`, `ruff check .`, pack validation, `python -m build`,
  `python -m twine check dist/*`, and `python scripts/check_release_contents.py`.
