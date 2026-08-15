# CHG-0017: Start workflow repository wording and inventory

**Status:** in-progress
**Source request:** Direct operator request: "The wording in the "Start Workflow" the wording is inconsistent and missleading because of "GitHut Projects". "Registered project" is not a "GitHub Project" but the "GitHub Repository". There is also a registered repository in the current hermes installation but is not selectable."
**Affected capabilities:** CAP-0003, CAP-0004, CAP-0006
**Created:** 2026-08-15

## Outcome

Start workflow names a registered **GitHub repository**, never a GitHub Project.
The registered-repository dropdown lists only bound tuples. Registrations that
violate CHG-0016 uniqueness or board bind state stay visible outside the
dropdown with a path-free reason and conclusion. Selecting a bound repository
still derives board and checkout server-side.

## Scope

- Replace Start Mode A copy that says "Registered project" / "Register project"
  with repository language. Keep the Config tab label **GitHub Repositories**
  next to **GitHub Projects**. Point the Start register link at that tab.
- List every ready profile's registrations on `GET /wizard/inventory`, split
  into selectable `projects` and `ineligible_repositories` with a finite reason
  and conclusion. Start rejects an ineligible selection.
- Registered start selection sends `{mode, project_id, controller_profile}`.
  The server revalidates the profile name through Hermes, reads that profile's
  registration store, and derives board plus checkout. The workflow ledger
  remains on the mounted dashboard profile.
- Update CAP-0003/0004/0006, CAP-linked wireframes, `dashboard/AGENTS.md`,
  `docs/07-runbook.md`, and focused dashboard tests.

## Phases

| Phase | Status | Verification gate |
|---|---|---|
| Operator approval | done | Operator reported the wording collision and the empty dropdown as the required fix. |
| Vertical slice | done | 2026-08-15: `python -m pytest tests/test_dashboard_api.py tests/test_dashboard_assets.py -q` 88 passed; `python scripts/check_records.py .` and `python scripts/check_md_links.py .` exit 0; `ruff check dashboard/plugin_api.py tests/test_dashboard_api.py tests/test_dashboard_assets.py` exits 0. |
| Ineligible inventory | done | 2026-08-15: `python -m pytest tests/test_dashboard_api.py tests/test_dashboard_assets.py -q` 89 passed; `python scripts/check_records.py .` and `python scripts/check_md_links.py .` exit 0; `ruff check dashboard/plugin_api.py tests/test_dashboard_api.py tests/test_dashboard_assets.py` exits 0. |
| Closeout | in-progress | Repository verification in root `AGENTS.md` exits 0, including `python -m pytest`. |

## Decisions

- "Project" on this surface means GitHub Projects v2 only. A Daidala workspace
  tuple is a registered GitHub repository plus its bound board.
- Start Mode A is no longer mounted-profile-only. Config already inventories
  every profile; the only live registration (`forgegod-daidala`) lives on
  `daidala-self-improvement`, so a dashboard mounted on another profile showed
  an empty Select… list.
- Browser may send a Hermes-validated `controller_profile` solely as the
  registration key. It still never sends a checkout, credential, or path.
  Start inventory may display the derived working directory so the operator
  can see where the workflow will run.
- Zero selectable registrations: explicit empty copy plus Register repository.
  One selectable: preselect. Several: pick among `owner/repo · profile · board`.
  Ineligible registrations stay visible outside the dropdown.
- Do not move the workflow ledger onto the registration's controller profile.
- Do not change GitHub Projects linking, Mode B/C, or CLI `daidala start`.
- A registration is selectable only when its board is `bound`. Otherwise Start
  lists it with one finite reason: `duplicate-repository`, `in-use`, `missing`,
  or `workdir-mismatch`, plus a path-free conclusion from the uniqueness table.

## Evidence

- Focused dashboard tests: 88 passed (`tests/test_dashboard_api.py`, `tests/test_dashboard_assets.py`).
- `python scripts/check_records.py .` passed (7 capabilities, 19 change records, 5 wireframes).
- `python scripts/check_md_links.py .` passed (109 files).
- Ineligible inventory: 89 focused dashboard tests passed; record and Markdown-link checks passed. Start also displays the working directory for the chosen workspace.
