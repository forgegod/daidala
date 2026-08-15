# CHG-0016: Workspace-tuple registration and start

**Status:** done
**Source request:** Direct operator request: "Creating a new workflow a GitHub Repository can be selected, but GitHub Repositories are 1:1 bound to a (controller) profile, so the selection for a new workflow could be to use the preselected GitHub Repository for this (controller) profile or to say, that no GitHub Repository is required for this workflow. Because a Hermes board is bound to a project directory, there is also a correlation with the GitHub Repository checkout path. Before we start designing the CHG the GitHub Repositories configuration need to be revisited. draft the CHG with the current concept and change"
**Affected capabilities:** CAP-0003, CAP-0004, CAP-0006
**Created:** 2026-08-15

## Outcome

Config → Registered projects registers a workspace tuple — GitHub repository,
derived checkout, and one unused Hermes board whose `default_workdir` is that
checkout — instead of stamping every repository with a profile-wide default
board. A GitHub Project remains an optional intake link on that tuple, not a
substitute for it. Start workflow then either consumes the tuple or starts
without registration against an existing unbound board whose workdir is
already a clean local git root, or initializes one new local project with
default committed Daidala policy.

## Scope

- Change repository registration so the operator binds or creates one unused
  board per repository. The server sets that board’s `default_workdir` from the
  derived checkout and writes that slug onto the registration.
- Retire `board` from profile-local `repository-registration-defaults.yaml`.
  Keep other defaults (credentials, attended target, evaluator, limits).
- Enforce uniqueness: per profile, unique `project_id` (already) and unique
  `repository_canonical`; installation-global among Daidala registrations,
  unique board slug.
- Rename the Config tab from GitHub Repositories to Registered projects so it
  matches Start Mode A. Keep the GitHub Projects tab name; that is a different
  GitHub product.
- Show Board and optional GitHub Project status on each Registered projects
  row. Board status is `bound`, `missing`, `workdir-mismatch`, or `in-use`.
  Project status is `linked` or `not linked`. Linking still happens on
  Config → GitHub Projects and still requires the registered `project_id`.
- Change Start workflow to three modes: registered project, existing unregistered
  project, or initialize local project. Remove the independent board picker from
  the registered path.
  Occupied boards are not a dead end: register creates a new board.
- Update CAP-0003, CAP-0004, and the CAP-0006 wireframe on the same Config tab
  in the implementation slices. Promote the Target documentation section into
  `docs/01-architecture.md`, with short operator restatements in
  `docs/07-runbook.md` and `docs/16-self-improvement-setup.md` section 6. Keep
  review layouts in this CHG until those slices exist. Do not allocate a new
  CAP ID.
- Update `dashboard/AGENTS.md`, `daidala/AGENTS.md` if the start or
  registration contract changes, `docs/07-runbook.md`, and focused tests.

Current facts a later session needs:

- A registration stores its board, derived checkout, and repository canonical
  together. Registration defaults do not own a board; the registration service
  creates or binds one tuple-specific board with the derived workdir.
- Dashboard start derives a registered project's board and checkout from the
  trusted tuple. It exposes clean, unregistered boards by slug only and starts
  against their server-resolved workdir.
- Local initialization derives `<checkouts.root>/<slug>`, creates the strict
  local policy and initial commit, creates one unbound board with that workdir,
  then admits the same confirmed workflow request. It creates neither a GitHub
  repository nor a registration.
- CLI `daidala start` remains available for any explicit absolute local Git
  root plus `--board`; dashboard selection never accepts a filesystem path.
- GitHub Project links are keyed by registered `project_id` and reject an
  unregistered id (`daidala/github_project_links.py:110-113`, `:177-179`).
  Intake uses the registration’s intake credential
  (`daidala/project_cycles.py:559-561`).

## Risk call-out

Existing healthy single-repo profiles keep working if their stored board
already matches the checkout. Multi-repo profiles that inherited one default
board are already `SI-BOARD` blocked; this change does not rewrite those
records. Recovery is `git checkout` of touched source, tests, CAPs, and
wireframes. Do not mark a phase done until its gate command exits 0.

## Phases

| Phase | Status | Verification gate |
|---|---|---|
| Operator approval | done | Operator approved the tuple contract and the local-project initialization extension on 2026-08-15. |
| Local-only policy identity | done | `.venv/bin/python -m pytest tests/test_projects.py tests/test_repository_bootstrap.py -q` and `.venv/bin/python -m ruff check daidala/projects.py daidala/repository_bootstrap.py tests/test_projects.py tests/test_repository_bootstrap.py` exited 0 on 2026-08-15. |
| Config workspace tuple | done | `.venv/bin/python -m pytest tests/test_repository_registration.py tests/test_dashboard_api.py tests/test_dashboard_assets.py tests/test_prerequisites.py -q`, `python scripts/check_records.py .`, and `python scripts/check_md_links.py .` exited 0 on 2026-08-15. |
| Start workflow modes | done | `.venv/bin/python -m pytest tests/test_dashboard_api.py tests/test_dashboard_assets.py tests/test_setup_wizard.py tests/test_tools.py -q`, `.venv/bin/python scripts/check_records.py .`, `.venv/bin/python scripts/check_md_links.py .`, Ruff, and dashboard syntax checks exited 0 on 2026-08-15. |
| Closeout | done | `.venv/bin/python -m pytest` passed 769 tests; Ruff, Lefthook, records, Markdown links, `git diff --check`, pack validation, dashboard syntax checks, build, Twine, and wheel-release checks passed on 2026-08-15. |

Mark a phase `in-progress` while running it, `done` once its gate passes
(record evidence), `pending` otherwise. A pending CHG has no `in-progress`
phase.

## Decisions

- The workspace is one tuple: GitHub `owner/repo` ↔ derived checkout
  `<board-root>/<slug>` ↔ one Hermes board whose `default_workdir` is that
  checkout. The controller profile owns the records; it is not the
  workspace. A GitHub Project is an optional intake attachment on that
  tuple, never the workspace key. Implementers derive `<board-root>` from
  the profile-local `checkouts.root` setting.
- Reject the earlier “1:1 profile ↔ GitHub repository” framing. A profile
  may own many tuples. CHG-0015’s all-profile inventory stays.
- Retire `board` from `RegistrationDefaults`. Register preview/apply must
  name the board for this repository. Do not stamp `defaults.board` onto a
  new registration.
- Bind or create one unused board at register time. Create uses documented
  `hermes kanban boards create <slug> --default-workdir <derived-checkout>`.
  Bind accepts only a board that is unused by any Daidala registration and
  whose `default_workdir` is empty or already equals the derived checkout;
  bind then sets the workdir when empty. The browser never sends or
  receives a checkout path.
- Uniqueness: same `repository_canonical` cannot register twice in one
  profile. Same board slug cannot be stored on two registrations in any
  profile. The same GitHub repo may register under two profiles, each with
  its own board and checkout.
- Do not rewrite existing `registration.yaml` files. A stored board that is
  missing, archived, in use by another tuple, or workdir-mismatched is a
  row error. The operator binds a different unused board from Config.
- Config still groups by profile. The tab label is Registered projects.
  Each registered row shows Repository, Slug, Board, and GitHub Project
  (`linked` / `not linked`). “Register another project” remains. Inspect
  still accepts a GitHub repository link. Bootstrap stays
  classification-gated and still does not write a registration or board.
- A GitHub Project is not required to register or start. It cannot be
  linked without a registered project. Do not re-key links onto a board
  slug or offer Projects intake in Mode B. That would need a new identity
  and credential home; it is a later CHG, not this one.
- Occupied-board rule: every existing board may already be stored on a
  tuple. Register still proceeds by creating a new board and setting its
  `default_workdir` to the derived checkout. Mode B lists only unbound
  boards that already have a clean git workdir. If that list is empty,
  Start says so and points to Registered projects (create a tuple) or
  Hermes `kanban boards create … --default-workdir` (create an unbound
  board first). Hermes boards are not a fixed pool.
- CLI `daidala project register` gains an explicit board flag (create or
  existing slug) and stops reading `defaults.board`.
- Start Mode A: select one registered project on the mounted controller
  profile. Board is display-only from the registration. Zero registrations
  → Register a project. One → preselect. Several → pick among tuples.
  Preview fails if the stored board is missing, archived, or
  workdir-mismatched. Start does not create boards in this mode. A missing
  GitHub Project does not block start.
- Start Mode B: explicit “Existing unregistered project”. Select an existing
  Hermes board that has `default_workdir`, is a clean git root, and is not
  stored on any registration. Server uses that workdir as
  `target_repository`. Dashboard cannot create a board here because there
  is no derived checkout. Require only a clean git root, not
  `.daidala/project.yaml`. No GitHub repository, GitHub Project, intake,
  findings, or delivery authority.
- Start Mode C: explicit “Initialize local project”. The browser sends only a
  kebab-case project slug and display name; the server derives the new empty
  directory as `<checkouts.root>/<slug>`. Preview names `git init`, both default
  `.daidala` policy files, the initial commit, and board creation with that
  derived directory as `default_workdir`; apply repeats every precondition,
  requires the exact preview digest and confirmation, then performs those
  mutations before the ordinary workflow start. It uses the same strict default
  policy renderer as repository bootstrap, with local-only identity and release
  flags disabled. Do not accept a browser filesystem path, GitHub identity,
  credential, or remote. A later remote attachment/registered-tuple conversion
  is a separate CHG.
- Local-only policy uses `repository.forge: local`, canonical identity
  `local/<project-slug>`, and an empty `allowed_remote_urls` list. It remains a
  strict `daidala.project/v1` manifest, but cannot validate or grant GitHub
  registration, intake, findings, or delivery authority.
- CLI `daidala start` remains the explicit-path escape hatch.
- Review layouts stay in this CHG. Regenerate CAP-linked HTML/PNG only in
  the implementation slice that changes that surface.

## Target documentation

No current numbered document states this map. Fragments only: boards are
installation-global in `docs/16-self-improvement-setup.md` section 6;
profile/board/workflow composition is in `docs/01-architecture.md`
(Workflow constraint topology); `SI-BOARD` is a check ID, not an identity
model.

Implementation promotes this section into `docs/01-architecture.md` as
**Workspace identity**. Add a short operator restatement to
`docs/07-runbook.md` (Registered projects / Start) and section 6 of
`docs/16-self-improvement-setup.md`. CAPs state outcomes only; they do not
own the topology. Do not publish this as current behavior until the Config
slice lands.

### Actors

| Actor | Authority | Scope |
|---|---|---|
| Hermes controller profile | Owns registration files, credential bindings, and Project links | Profile-local |
| Hermes board | Owns cards and `default_workdir` | Installation-global |
| Derived checkout | Local git root `<board-root>/<slug>` | Profile-local path, never in the browser |
| GitHub repository | Canonical `owner/repo` on the registration | One per registered project in a profile |
| GitHub Project | Optional intake link on the registration | Profile-local; keyed by `project_id` |

A Hermes board is not a GitHub Project. The board is the workspace. The
GitHub repository and GitHub Project hang off that workspace.

### Registered project

```text
Hermes board  --default_workdir-->  derived checkout  <-->  GitHub repository
        ^
        |  stored slug
controller registration
        |
        +---- optional GitHub Project link
```

### Uniqueness

Hermes does not give each profile its own board copy. Boards are
installation-global: one slug, one database, visible from every profile.
A controller registration stores only that slug. Profile isolation does
not create board isolation.

Cards on that shared board are assigned to Hermes profiles. Daidala’s
stage map (`define`, `plan`, `implement`, `verify`, `review`, `deliver`)
sets each card’s assignee. Those worker profiles claim and run cards; they
do not own the board. One board may therefore have cards assigned to
several profiles, including a controller profile that is not a worker.

The table below is a different axis. It is Daidala registration binding
(which GitHub repository may store which board slug), not Hermes card
assignment. Two worker profiles on one board is normal. Two GitHub
repository registrations storing the same board slug is not.

| Pair | Same profile | Two profiles | Conclusion | Usecase | Checkout |
|---|---|---|---|---|---|
| One Hermes board, two GitHub repositories | no | no | Never. Each GitHub repository gets its own Hermes board. | Not a team setup. One board has one `default_workdir`, so two repos would share cards and collide on checkout. The rule keeps each product’s graph and workdir isolated. | No valid layout. One board cannot have two checkouts. |
| Two Hermes boards, one GitHub repository | no | yes | Only across profiles, as two checkouts. One profile cannot register the same repo twice. | Two operators or environments on the same codebase, each with a private checkout and board. Shared remote, isolated approval and worktrees. | One clone per board: `<board-root>/<slug>`. |
| Two Hermes boards, two GitHub repositories, one GitHub Project | yes | yes | Allowed. A GitHub Project is optional intake and is not unique-keyed. | A team tracks issues from several repos in one GitHub Project, while each repo executes on its own Hermes board and checkout. Shared intake, isolated implementation. | One clone per board: `<board-root>/<slug>`. |
| Two Hermes boards, one GitHub repository, one GitHub Project | no | yes | Only across profiles. Same-profile repo uniqueness already forbids this. | Two operators share one issue queue for the same repo, but run on separate boards and checkouts. Intake claims must stay profile-local so both do not take the same item. | One clone per board: `<board-root>/<slug>`. |

A registration checkout is a full clone at `<board-root>/<slug>`.
`slug` is the Config Slug / directory name. It is not a GitHub Project.
`board-root` is the parent of the board’s `default_workdir`. After
register those two paths are one: `<board-root>/<slug>` is the board
`default_workdir`.

Two profiles have different `board-root` values because each controller
profile has its own Hermes profile directory. The default is that
profile’s `work/` folder:

`<hermes-home>/profiles/<profile>/work`

so two profiles registering the same GitHub repository look like:

`<hermes-home>/profiles/profile-a/work/<slug>`
`<hermes-home>/profiles/profile-b/work/<slug>`

The exact profile directory comes from `hermes profile show <profile>`
(`Path:`). An operator may replace the default by setting `checkouts.root`
in that profile’s `checkouts.yaml`. Pointing two profiles at the same
absolute directory is a misconfiguration, not a shared checkout.

A GitHub Project never changes this path. Two profiles on one GitHub
repository therefore still have two clones, not one directory split with
`git worktree`. After plan approval, Daidala already adds a third path: a
detached worktree under the controller profile at
`worktrees/<workflow-id>`, parented from that board checkout. Worktrees
isolate one workflow from its baseline. They are not the mechanism that
separates two registrations. Sharing one checkout between two boards
would fail the clean-baseline gate and collide `default_workdir`.

An unbound Hermes board (Start Mode B) has a clean-git `default_workdir` and no
registration, so no GitHub repository and no GitHub Project. Start Mode C creates
that local Git root, its default policy, and its unbound board together; it does
not create a registration.

Occupied boards are not a fixed pool. Register creates a new Hermes board
and sets `default_workdir` from the derived checkout. Mode B lists only
unbound boards; if none exist, create one in Hermes first.

Intended Config layout (synthetic, review-only):

```text
CONFIG / REGISTERED PROJECTS                              [Refresh]

Each row is one workspace: GitHub repository, derived checkout, and board.
A GitHub Project is optional intake on that row. Daidala does not accept
credentials or filesystem paths.

PROFILE  daidala-self-improvement
  Repository     forgegod/daidala
  Slug           forgegod-daidala
  Board          daidala-forgegod-daidala · bound
  GitHub Project linked
  GitHub repository link
  [ github.com/forgegod/daidala                      ] [Inspect]
  Register another project
  [                                                  ] [Inspect]

PROFILE  daidala-dashboard
  No project registered
  GitHub repository link
  [                                                  ] [Inspect]
```

After a registerable inspect, the confirmation names the board to create or
bind. After a needs-bootstrap inspect, the existing bootstrap confirmation
is unchanged.

Intended Start layout (synthetic, review-only):

```text
START WORKFLOW

Mounted controller profile
daidala-self-improvement

Workspace
( ) Registered project
    [ forgegod-daidala · forgegod/daidala · daidala-forgegod-daidala ]
( ) Existing unregistered project
    Board · existing workdir   [ Select… ]
    All listed boards are unbound. If none exist, register a project
    or create a Hermes board with a default workdir first.
( ) Initialize local project
    Project slug               [ example-app                         ]
    Board display name         [ Example app                         ]
    Creates a new local Git repository, default `.daidala` policy,
    initial commit, and unbound board. No GitHub repository is created.

Pack · readiness               [ addyosmani · ready ]
Requested outcome / Prompt
[                                                           ]
```

## Evidence

The operator approved this CHG and its local-project initialization extension on
2026-08-15. Start workflow modes is the active implementation phase.

## Execution notes

Fresh-session context: this CHG, root `AGENTS.md`, `dashboard/AGENTS.md`,
`daidala/AGENTS.md`, `docs/changes/AGENTS.md`, `docs/product/AGENTS.md`,
CAP-0003, CAP-0004, CAP-0006, `daidala/repository_registration.py`,
`daidala/registrations.py`, `daidala/prerequisites.py`,
`dashboard/plugin_api.py` registration and wizard routes. Do not load
archived CHG-0009 or CHG-0015 in full.

### Operator approval

**Goal:** Human approval of this CHG before any runtime, test, CAP, or wireframe
edit.

**Steps:**

1. Present this file and the locked Decisions layouts.
2. Record the operator's approval, including the local-project initialization
   extension, before moving Config workspace tuple to `in-progress`.

**Verification gate:** Operator approves this CHG, including the locked tuple,
uniqueness, Config board bind/create, Start Mode A/B, and local-project
initialization.

### Config workspace tuple

**Goal:** Registration preview/apply bind or create one unused board,
defaults no longer carry `board`, Config rows show Board and path-free
status, and CAP-0004/0006 plus the Config wireframe describe that
behavior.

**Steps:**

1. Remove `board` from `RegistrationDefaults` and its parser/tests. Fail
   closed if an old defaults file still contains `board`.
2. Extend registration preview/apply with an explicit board create-or-bind
   identity. Recompute uniqueness and `default_workdir` on apply. Reject
   stale preview digests.
3. Expose path-free board status and GitHub Project linked/not-linked
   on the inventory. Keep checkout paths, remotes, aliases, node IDs,
   and tokens out of browser payloads.
4. Rename the tab to Registered projects and update it to the locked
   layout, including Board and GitHub Project status. Keep
   inspect/bootstrap/apply on the owning profile card. Do not move
   Project link mutations onto this tab.
5. Update CLI `daidala project register` to require the board identity.
6. Extend focused registration, dashboard, and `SI-BOARD` tests.
7. Update CAP-0004, the CAP-0004/0006 generator screens, owning DOX, and
   the runbook sentence. Promote **Target documentation** into
   `docs/01-architecture.md` and restate section 6 of
   `docs/16-self-improvement-setup.md` so the dogfood board is an instance
   of the tuple, not a second model. Regenerate HTML/PNG/index/manifest.
   Do not hand-edit generated outputs.
8. Run the phase gate. Record command evidence here before the
   implementation commit.

**Verification gate:** `python -m pytest tests/test_repository_registration.py tests/test_dashboard_api.py tests/test_dashboard_assets.py tests/test_prerequisites.py -q` exits 0; `python scripts/check_records.py .` and `python scripts/check_md_links.py .` exit 0.

### Start workflow modes

**Goal:** Start consumes a registered tuple, an existing unregistered board
workdir, or a newly initialized local project. Independent repo-plus-board
selection is gone.

**Steps:**

1. Change wizard inventory so registered projects carry
   `project_id`, `repository`, `board`, board status, and whether a
   GitHub Project is linked. Add unregistered boards that already have
   a clean git workdir. An empty Mode B list is a stated empty state,
   not a forced Mode A.
2. Change preview/start so Mode A derives board and checkout from the
   registration, and Mode B derives `target_repository` from the selected
   board’s `default_workdir`. Reject Mode B boards that are registered or
   lack a clean git root.
3. Rewrite `StartWorkflow` to the locked two-mode layout. Drop the
   independent board dropdown from Mode A. Do not offer create-board in
   Mode B. Add Mode C's derived-path local-project preview/confirm flow; it
   must initialize Git, write the strict default policy, create the initial
   commit, create the unbound board with that workdir, and delegate only then
   to the existing start path.
4. Keep browser-local defaults non-authoritative and revalidated.
5. Update CAP-0003, its wireframe, dashboard DOX, and focused wizard/asset
   tests. Restate Start Mode A/B against the promoted architecture
   section; do not invent a second identity model.
6. Run the phase gate. Record command evidence here before the
   implementation commit.

**Verification gate:** `python -m pytest tests/test_dashboard_api.py tests/test_dashboard_assets.py tests/test_setup_wizard.py tests/test_tools.py -q` exits 0; `python scripts/check_records.py .` and `python scripts/check_md_links.py .` exit 0.

### Closeout

**Goal:** Repository gate passes and this CHG can move to `archive/`.

**Steps:**

1. Confirm CAP-0003/0004/0006 describe merged behavior and link tests.
2. Run the root `AGENTS.md` verification block with `python -m pytest`
   rather than a bare `pytest` launcher.
3. Mark every phase `done` with evidence, set this CHG `done`, and move it
   to `docs/changes/archive/`.

**Verification gate:** Repository verification in root `AGENTS.md` exits 0, including `python -m pytest`.

## Out of scope

- Do not accept paths, credential aliases, tokens, or environment-variable
  names in the browser.
- Do not rewrite existing registration or defaults files in place.
- Do not link a GitHub Project without a registered project_id, re-key links
  onto a board, or give Mode B/C intake/findings/delivery.
- Do not attach a GitHub remote, register a local project, or convert it to a
  tuple during Mode C.
- Do not change checkout-root policy, delivery, packs, or credential
  alias resolution. Config → GitHub Projects stays the link/verify
  surface.
- Do not require `.daidala/project.yaml` for Mode B.
- Do not add an MCP server, dashboard HTTP daemon, or nested `hermes chat`.
- Do not create a second plan under `docs/plans/` or the Hermes profile.
