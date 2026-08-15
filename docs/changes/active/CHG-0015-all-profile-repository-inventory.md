# CHG-0015: All-profile GitHub repository inventory

**Status:** in-progress
**Source request:** Direct operator request: "(1) The GitHub Repositories tab in "Config" of Daidala shoud be reworked, so that all profiles and their repositories are visible at once. (2) for a profile with a set repository the repo and the slug have to be shown, where the edit field is filled with the repository"
**Affected capabilities:** CAP-0004, CAP-0006
**Created:** 2026-08-15

## Outcome

Config → GitHub Repositories shows every Hermes-validated profile and that
profile's registered repositories in one inventory. A profile with a
registration displays `repository_canonical` as the repository and `project_id`
as the slug, and fills that row's GitHub repository link field with
`github.com/<repository_canonical>`. Preview, bootstrap, and apply stay
preview-confirmed, path-free, and bound to the row's profile.

## Scope

- Replace the Config → GitHub Repositories single-profile picker with one
  path-free inventory of all Hermes-validated profiles and their registrations.
- Keep CLI `daidala project register` / `bootstrap` and the existing
  preview/apply payloads `{github_url, controller_profile}` unchanged.
- Update CAP-0004 current behavior, the CAP-0004 wireframe, the CAP-0006
  bootstrap wireframe on the same tab, `dashboard/AGENTS.md`, focused dashboard
  API/asset tests, and the dashboard sentence in `docs/07-runbook.md`.
- Do not change registration writes, credential handling, checkout paths, or
  GitHub Projects.

Current facts a later session needs:

- The tab is `RepositoryRegistrationPanel` in
  `dashboard/dist/index.js:2518`. It loads
  `GET /repository-registration/profiles`, then one
  `GET /repository-registration/registrations?controller_profile=` for the
  selected name (`dashboard/dist/index.js:166`, `dashboard/plugin_api.py:606`).
- Changing the `<select>` labelled "Selected Hermes profile" refreshes only
  that profile's list and leaves `githubUrl` empty
  (`dashboard/dist/index.js:2579`, `:2528`, `:2666`).
- A selected profile's list already prints
  `repository_canonical · project_id` (`dashboard/dist/index.js:2664`) but
  other profiles are hidden until the operator switches.
- CAP-0004 still requires listing only the selected profile
  (`docs/product/capabilities/CAP-0004-github-repository-registration.md:27`).
- `dashboard/AGENTS.md` requires list requests to carry one selected name.
- `8c0b900` introduced that selected-profile scope.

## Risk call-out

Not destructive. The change is a read-model and browser-layout rewrite.
Recovery is `git checkout` of the touched dashboard, test, CAP, and wireframe
files. Do not mark a phase done until its gate command exits 0.

## Phases

| Phase | Status | Verification gate |
|---|---|---|
| Operator approval | done | 2026-08-15: operator selected “Approve CHG-0015 and execute”. |
| Vertical slice | done | `python -m pytest tests/test_dashboard_api.py tests/test_dashboard_assets.py -q` passed; `python scripts/check_records.py .` and `python scripts/check_md_links.py .` passed. |
| Closeout | in-progress | Repository verification in root `AGENTS.md` exits 0, including `python -m pytest`. |

Mark a phase `in-progress` while running it, `done` once its gate passes
(record evidence), `pending` otherwise. A pending CHG has no `in-progress`
phase.

## Decisions

- One new `GET /repository-registration/inventory` returns the Hermes profile
  list plus each profile's path-free registrations. The browser loads this tab
  with that one request. Keep the existing per-profile GET as the helper the
  inventory uses so unknown names are still rejected before root resolution
  (`dashboard/plugin_api.py:356`).
- Inventory rows expose only `controller_profile`, finite `status`
  (`ready` / `unavailable`), and `registrations[]` of
  `{project_id, repository_canonical}`. No profile root, checkout, alias,
  environment-variable name, token, or node ID.
- A single invalid registration store marks that profile `unavailable` with an
  empty list. It does not fail the whole inventory.
- Render one card per profile, all visible together. No profile `<select>`.
- Registered identity: label `Repository` with `repository_canonical` and
  `Slug` with `project_id`. Prefill that row's input with
  `github.com/<repository_canonical>`. Do not auto-inspect on load.
- Multiple registrations on one profile: one identity-plus-field row each.
  When any registration exists, keep one extra empty field on that card so a
  second repository can still be inspected without overwriting a filled row.
- Unregistered profile: visible name, explicit empty state, one empty field.
- Inspect, preview, bootstrap, and apply stay on the card that owned the
  request and still send that card's `controller_profile`.
- CAP-0006 behavior is unchanged except it no longer depends on a global
  selected-profile control. Update its wireframe so it does not resurrect the
  picker.
- Do not N+1 from the browser. Do not change CLI, registration apply writes,
  or Start-workflow profile selection.

Intended landing layout (synthetic data):

```text
CONFIG / GITHUB REPOSITORIES                              [Refresh]

Every existing Hermes profile and its registered repositories.
Daidala does not accept credentials.

PROFILE  daidala-self-improvement
  Repository  forgegod/daidala
  Slug        forgegod-daidala
  GitHub repository link
  [ github.com/forgegod/daidala                      ] [Inspect]
  Register another repository
  [                                                  ] [Inspect]

PROFILE  daidala-dashboard
  No repository registered
  GitHub repository link
  [                                                  ] [Inspect]
```

## Evidence

- 2026-08-15: operator approved CHG-0015 (“Approve CHG-0015 and execute”).
- `GET /repository-registration/inventory` projects every Hermes-validated
  profile with path-free registrations and isolates one invalid store.
- Config → GitHub Repositories renders one card per profile, labels
  Repository and Slug, and prefills `github.com/<repository_canonical>`.
- CAP-0004 and CAP-0006 wireframes were regenerated and visually reviewed:
  both profiles are visible, the registered field is prefilled, the empty
  profile stays empty, and no clipping or overlap was observed.
- `python -m pytest tests/test_dashboard_api.py tests/test_dashboard_assets.py -q`
  passed. `python scripts/check_records.py .` and
  `python scripts/check_md_links.py .` passed.

## Execution notes

Fresh-session context: this CHG, root `AGENTS.md`, `dashboard/AGENTS.md`,
`docs/changes/AGENTS.md`, `docs/product/AGENTS.md`, CAP-0004, CAP-0006, and
`dashboard/plugin_api.py` registration routes. Do not load archived CHG-0009
in full.

### Operator approval

**Goal:** Human approval of this CHG before any runtime, test, CAP, or
wireframe edit.

**Steps:**

1. Present this file and the locked Decisions layout.
2. Do not edit `dashboard/`, `daidala/`, tests, CAPs, or wireframes until the
   operator approves.

**Verification gate:** Operator approves this CHG, including the locked
inventory layout and per-profile prefill rule.

### Vertical slice

**Goal:** Inventory API, Config UI, tests, CAP-0004/0006 records, CAP-linked
wireframes, and owning DOX describe the same behavior.

**Steps:**

1. Add `GET /repository-registration/inventory` in
   `dashboard/plugin_api.py`. Revalidate every name with `list_profiles`
   before `resolve_profile_root`. Isolate per-profile store errors.
2. Rewrite `RepositoryRegistrationPanel` in `dashboard/dist/index.js` to the
   locked layout. Drop "Selected Hermes profile". Prefill registered rows.
   Keep preview/bootstrap/apply payloads and path-free constraints.
3. Extend `tests/test_dashboard_api.py` for the inventory: two profiles, one
   registered / one empty, unknown names never resolved, one bad store does
   not hide the other profile, no private paths or aliases.
4. Update `tests/test_dashboard_assets.py` so the bundle requires the
   inventory route, visible repository and slug labels, prefilled
   `github.com/` values, and no selected-profile picker.
5. Update CAP-0004 behavior from "selected profile" to the all-profile
   inventory and prefill rule. Link this CHG. Adjust CAP-0006 only if its
   surface wording still assumes a global picker.
6. Edit `docs/product/wireframes/generate.mjs` CAP-0004 and CAP-0006 screens
   to the locked layout. Regenerate HTML/PNG/index/manifest. Do not
   hand-edit generated outputs.
7. Update `dashboard/AGENTS.md` so the browser contract names the inventory
   route instead of "list requests carry one selected name". Update the
   Config → Repositories sentence in `docs/07-runbook.md`.
8. Run the phase gate. Record command evidence here before the
   implementation commit.

**Verification gate:** `python -m pytest tests/test_dashboard_api.py tests/test_dashboard_assets.py -q` exits 0; `python scripts/check_records.py .` and `python scripts/check_md_links.py .` exit 0.

### Closeout

**Goal:** Repository gate passes and this CHG can move to `archive/`.

**Steps:**

1. Confirm CAP-0004/0006 describe merged behavior and link tests.
2. Run the root `AGENTS.md` verification block with `python -m pytest`
   rather than a bare `pytest` launcher.
3. Mark every phase `done` with evidence, set this CHG `done`, and move it
   to `docs/changes/archive/`.

**Verification gate:** Repository verification in root `AGENTS.md` exits 0, including `python -m pytest`.

## Out of scope

- Do not change `daidala project register` or `bootstrap` CLI flags.
- Do not accept paths, credential aliases, tokens, or environment-variable
  names in the browser.
- Do not auto-inspect or auto-register from a prefilled field.
- Do not change Start workflow's mounted-controller inventory.
- Do not change GitHub Projects, checkouts, packs, or delivery.
- Do not add an MCP server, dashboard HTTP daemon, or nested `hermes chat`.
- Do not create a second plan under `docs/plans/` or the Hermes profile.
