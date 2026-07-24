# Daidala dashboard user configuration, packs, start UX, constraints, and GitHub Projects linking

**Status:** proposed — consistency/completeness review and incorporation of
implementer-facing refinements are complete; human approval is still required
before Phase 0 creates a fresh `daidala-dashboard` profile, installs the
local-checkout plugin link, starts implementation, or makes any implementation
edit.

**Last review:** 2026-07-23

For the implementing agent: read `/AGENTS.md`, `docs/AGENTS.md`,
`daidala/AGENTS.md`, `dashboard/AGENTS.md`, `tests/AGENTS.md`, this plan,
and the completed
`docs/plans/2026-07-12-dashboard-integration-and-guided-setup.md`. Also read the
[Hermes integration guide](../08-hermes-integration.md), the normative
[setup prerequisite guide](../16-self-improvement-setup.md), and the current
official Hermes [dashboard extension documentation](https://hermes-agent.nousresearch.com/docs/user-guide/features/extending-the-dashboard).
Stop when any gate fails.

This plan was reviewed against the live Hermes CLI installed on the
implementing machine (`hermes profile`, `hermes plugins enable`,
`hermes dashboard`, `gh project view`) on 2026-07-23. CLI flags below are
pinned against the verified outputs; if any `--help` text drifts, treat the
local CLI as authoritative and stop.

## Goal

Extend the existing Hermes dashboard Daidala extension so a user can, from
the browser, (1) browse installed packs read-only and run the installed
`packs check` or preview/apply installation actions, (2) create or select the
board and launch a `hermes daidala start` invocation through a guided form,
(3) watch and supervise that workflow through its existing approval, Kanban,
and cancellation boundaries, (4) configure and verify the Daidala setup,
including the `checkouts.root` directory and TTL mode, (5) author and manage
workflow constraints, and (6) link each registered `project_id` to at most one
GitHub Projects v2 board identified by owner, project number, and verified node
ID, with a three-mode checkout TTL refresh policy (`disabled` /
`wipe-if-clean` / `backup-then-wipe`) — without weakening the deterministic
policy ledger, exact approval gate, or existing read-only workflow views.

After installation, a new user should be able to follow the same sequence as
`docs/00-getting-started.md` without translating CLI arguments into dashboard
concepts: verify the plugin and pack, create or choose a board, start and watch
the workflow, inspect the pending plan and digest, approve that exact digest,
follow implementation through delivery, remediate a blocked card, or cancel the
workflow. Destructive or authority-bearing actions remain explicit,
previewed/confirmed, and backed by the existing Daidala or Hermes command
surfaces.

The dashboard wizard is an alternative presentation over the same validated
`daidala.setup_wizard.SetupRequest` and `confirmed_start` path used by
`daidala:setup`; it is not a second setup model. It calls
`SetupRequest.from_payload`, then the existing `WorkflowService.start` through
`dashboard.plugin_api.wizard_start`. The plan does not change that engine,
the CLI surface, the registration schema, or Kanban authority. It adds UI
affordances over services that already exist or are added in clearly bounded
phases.

## Current state

- The dashboard already exposes `/health`, `/prerequisites`, `/workflows`,
  `/workflows/{id}`, `/workflows/{id}/decisions`,
  `/workflows/{id}/recommendations`, `/constraints/preview`,
  `/constraints/replace`, and `/wizard/{inventory,boards,preview,start}`
  (`dashboard/plugin_api.py:85-251`).
- `/health` currently returns `read_only: true`, but the plugin already exposes
  scoped board, setup, and constraint mutations. Phase 2 narrows that misleading
  capability label to `read_model: true`; it does not make the plugin read-only.
- A `SetupWizard` UI component already exists with a minimal board, repo,
  goal form, `Preview mutations`, and `Start workflow` confirmation
  (`dashboard/dist/index.js:467-531`).
- Pack payloads including skills, sources, lifecycle, and digest are already
  returned by `/prerequisites` (`daidala/dashboard_backend.py:118-165`) but
  the dashboard UI only surfaces the `workflow_count` field today.
- Constraint preview/replace is exposed read-mostly and the backend uses
  compare-and-swap; there is no authoring UI for new constraint content yet.
- GitHub intake already supports `read-organization`, `read-project`, and
  `read-public-repository` (`daidala/AGENTS.md:109-110`) and is wired
  through `live_adapters.GitHubIssueIntakeAdapter`
  (`daidala/live_adapters.py:101-105`). There is no current UI for managing
  a registration-to-GitHub-Projects-v2 binding or checkout TTL. Repository
  identity, verified remote, and intake alias already belong to the registration
  and must not be duplicated in the new link.
- `project_cycles.ProjectCycleOperator.admit` already orchestrates a
  registered project cycle with one explicit named board, pack, and
  constraints (`daidala/project_cycles.py`); the dashboard does not expose
  this entry point today.
- `registrations.ControllerRegistration` carries `checkout`,
  `controller_profile`, `board`, `verified_remote`, and credential aliases
  (`daidala/registrations.py:74-127`); writing or editing these is a
  profile-local mutation, not a Kanban mutation.
- No checkout management, no stale-time re-clone, and no per-registration GitHub
  Projects v2 link UI exist anywhere yet.

## Open design questions — resolved

The operator answered the original open questions on 2026-07-23. The consistency
review added the fail-closed checkout/registration equality invariant; it is part
of the recommended plan submitted for the remaining human approval. Decisions are
pinned here so the corresponding phases consume them directly.

**Operator pinning (2026-07-23):**

- **Target Hermes profile:** **`daidala-dashboard`**, a fresh, dedicated
  profile to be created solely for the development and testing
  of this dashboard plan. `daidala-dashboard` is *not* a published
  Daidala controller profile and does not own any workflow ledger,
  registrations, or notification authority — it exists to host the
  dashboard under isolated conditions. The existing
  `daidala-self-improvement` controller profile and the everyday-chat
  `hermes-vc` profile are left untouched.
  Phase 0 creates the new profile through `hermes profile create`,
  installs Daidala into it as a local-checkout symlink, launches its isolated
  dashboard process, and verifies the mount evidence.

- **Browser-test controller state:** stateful browser integration runs against a
  freshly created disposable fixture controller profile/data root named
  `daidala-dashboard-fixture-<UTC YYYYMMDDTHHMMSSZ>` (UTC ISO-8601 basic
  format, `Z` suffix, generated at creation), seeded with one strict
  controller registration and non-secret explicit credential-alias bindings.
  The fixture gets its own local-checkout plugin symlink. Run an isolated
  Hermes dashboard process under the fixture profile on an OS-assigned
  port (`hermes -p <fixture> dashboard --isolated --port 0 --no-open`),
  and terminate that exact owned process before deleting the fixture. Do
  not rely on SPA profile selection: `plugin_api.py` resolves and caches
  backend state from the dashboard process's `HERMES_HOME` and has no
  documented request-profile API. The long-lived dashboard host profile
  remains `daidala-dashboard` and stays registration-free. After the
  browser gate, `hermes profile delete <fixture> -y` removes the fixture
  and all of its profile-local state (`-y` is the documented skip-confirm
  flag on this CLI; `--yes` is rejected). The existing
  `daidala-self-improvement` profile is never read or changed. Any later
  phase that needs stateful browser evidence recreates a fresh timestamped
  fixture and isolated dashboard by this same recipe; no phase relies on
  state from a deleted fixture.

- **Profile-local checkout state:** `<resolved-data-root>/checkouts.yaml`
  (mode `0600`) owns the strict `daidala.checkouts/v1` object with one
  `checkouts` mapping containing exactly `root`, `mode`, and `ttl_hours`.
  `<resolved-data-root>/github-project-links.yaml` (mode `0600`) owns the strict
  `daidala.github-project-links/v1` object and its `GitHubProjectLink` rows.
  Existing registration records remain at
  `projects/<project_id>/registration.yaml` and are not rewritten by either
  service. The two new files reject unknown fields and duplicate keys.

- **Concurrency boundary:** extend the existing process-local dashboard service
  container rather than creating route-local singleton stores. Initialize all new
  stores exactly once under the same first-request lock as the dashboard backend;
  serialize each store's compare-and-swap read/verify/write sequence with its own
  lock. Concurrent first reads and conflicting writes must not race initialization
  or lose an update.

- **Browser mutation allowlist:** the complete authority-bearing HTTP surface is
  confirmed pack installation; `POST /wizard/boards`; `POST /wizard/start`;
  `POST /constraints/replace`; workflow approve, card comment/unblock, and cancel;
  `PUT /github-project-links/{project_id}`; `PUT /checkout-root`; checkout adopt,
  refresh, and named-backup prune; and `PUT /checkouts/policy`. Preview, verify,
  inventory, readiness, sweep, and status calls are non-mutating even when HTTP
  transport uses `POST`. No general command/tool dispatch route is permitted.

- **Credential boundary:** a link stores no credential alias. Link verification
  derives the existing `ControllerRegistration.intake_credential` and its
  binding for the same `project_id`. Dashboard and API payloads never accept,
  persist, log, or return a GitHub token or resolved credential value.

- **Checkout-root change:** replacing `checkouts.root` returns `409 Conflict`
  while any owned checkout directory exists under the current root. GitHub
  Project links do not own checkout paths and do not block a root change. The
  operator must explicitly remove or migrate owned checkout directories before
  changing the root; the service never moves, re-clones, or orphans a checkout
  automatically. Existing registrations remain immutable: configuration is
  valid only when every `ControllerRegistration.checkout` equals
  `<checkouts.root>/<project_id>`. A mismatch is a blocking verification error,
  never a second dashboard-managed clone.

- **Collision-safety marker:** the on-disk sidecar
  `<checkouts.root>/<project_id>/.daidala-owner` written mode `0600`.
  Ownership is captured directly on the checkout directory. The strict
  registration plus configured root derive the authoritative checkout path; the
  sidecar is the durable on-disk witness. It is written only after a successful
  clone/swap and refreshed only after a successful checkout refresh. A GitHub
  Project link never creates or owns a checkout path.

- **Backup retention:** persistent, prune-on-demand only. Backups in
  `<checkouts.root>/_backups/` are never auto-deleted. The TTL manager
  lists eligible backups through a `POST
  /api/plugins/daidala/checkouts/_backups/prune` endpoint that requires
  an explicit named-backup payload and literal `confirm: true`. A
  `backup_retention_hours` knob is *not* introduced in v1 — pruning is
  an explicit operator action.

**Operator-visible precondition (verified 2026-07-23 against the live
Hermes dashboard on `http://127.0.0.1:9119`):**

A `daidala-dashboard` Hermes profile does not yet exist; `hermes
profile list` does not include it. Daidala already installs cleanly
under `daidala-self-improvement`; that install stays put. The
`hermes-vc` profile used for everyday chat is also left untouched.
Before any user-facing capability below is realised, Phase 0 must (a)
create the `daidala-dashboard` profile, (b) install Daidala into it
through the `Per-profile installation` recipe in
`docs/08-hermes-integration.md#per-profile-installation` (the symlink
path is the verified one for a local working tree), and (c) verify manifest and
asset discovery separately from a session-authenticated health request. Do not
pin the status of an unauthenticated plugin-route request: supported host builds
and current upstream documentation differ at that boundary.

Two related facts shape the implementation, not just the install:

- `/plugins?profile=<name>` is the SPA shell, not a JSON manifest.
  Hermes discovers plugins client-side from `window.__HERMES_PLUGINS__`
  (Daidala's `dist/index.js` already consumes `window.__HERMES_PLUGIN_SDK__`
  and assumes React); the JSON manifest endpoint is
  `/api/dashboard/plugins` and is auth-gated (returns `401` without a session
  token even when the plugin is mounted).
- The official dashboard-extension contract exposes React through
  `window.__HERMES_PLUGIN_SDK__.React`; plugins do not bundle React. Phase 1
  verifies that contract on the supported host. Missing `SDK.React` is a host
  compatibility failure: stop and report it rather than adding a Vue fallback or
  bundling another framework.

- **Q1 — Where do project checkouts live?** Resolved.
  - **(a)** Daidala maintains an explicit, user-configurable root
    directory — by default `<profile>/work/` (resolved through the
    existing `locations.resolve_data_root()` helper
    in `daidala/locations.py`), overridable through a profile-local
    `checkouts.yaml` key `checkouts.root`.
  - **(b)** A registered project's checkout lives at
    `<checkouts.root>/<project_id>/`, where `project_id` is the strict
    registration slug already enforced by
    `daidala/registrations.py:96` and `daidala/projects.py:240`.
    The manager requires this derived path to equal the existing
    `ControllerRegistration.checkout`; it never creates or refreshes a separate
    cache checkout and never rewrites registration state.
  - **Collision safety.** `project_id` is already validated as
    `^[a-z0-9]+(?:-[a-z0-9]+)*$` in `daidala/projects.py`; the same
    slug is reused on disk so two registrations with different
    `verified_remote` values can never share a checkout directory.
    `<checkouts.root>/<project_id>/.daidala-owner` (mode `0600`) is the
    durable on-disk witness: it carries the `project_id` that owns the
    path and is written or refreshed only after a successful checkout clone or
    replacement. The data model
    rejects a path whose `.daidala-owner` disagrees with the incoming
    `project_id`. The UI surfaces the resolved absolute path before any
    preview is generated.
  - GitHub Projects v2 links are independent profile-local metadata keyed by
    `project_id`. They bind an owner plus project number to the node ID returned
    by a bounded `gh project view` probe. Repository identity, verified remote,
    credential alias, and checkout path remain registration/configuration data,
    not link fields. A new task against a different registration never touches
    another project's checkout.

- **Q2 — Stale-checkout behaviour is a configurable policy.** Resolved.
  - The TTL manager exposes three explicit modes; default is `disabled`.
  - **`wipe-if-clean`** — only re-clones if `git status --porcelain
    --untracked-files=all --ignored=matching` has no row other than the separately
    validated exact `?? .daidala-owner` witness and the head age exceeds the TTL;
    otherwise aborts with a 409 and classified tracked/untracked/ignored paths.
    The marker is never treated as user work.
  - **`backup-then-wipe`** — tar/gzips the working tree into
    `<checkouts.root>/_backups/<project_id>.<unix-ts>.tar.gz` (root-owned
    directory with mode `0700`), prepares and verifies a replacement clone, then
    swaps it into place. Clone failure leaves the old checkout intact.
  - **`disabled`** — checkout TTL is ignored; only the manual "Refresh
    now" button can re-clone, and only via the same
    `git status --porcelain` abort.
  - **Backup retention is persistent.** `_backups/` is never
    auto-pruned by the TTL manager. A `POST
    /api/plugins/daidala/checkouts/_backups/prune` endpoint lists
    eligible backups and deletes *only the backups named in the
    request body* after literal `confirm: true`. No
    `backup_retention_hours` knob in v1.
  - The selected mode and TTL value are stored in profile-local
    `checkouts.yaml` so they survive restarts and are visible in the
    Phase 8 configuration verification panel.
  - **Trigger boundary:** v1 refresh is manual from the dashboard only. A
    later Hermes cron job may invoke `daidala_checkouts_status`, but that
    tool is hard-locked to a report-only dry run and never changes
    checkouts, backups, GitHub Project links, or registration state.

The remaining plan treats these decisions as pinned: `daidala-dashboard` is
the registration-free dashboard host; browser state uses an isolated dashboard
process under only the disposable fixture controller profile; `checkouts.yaml`
and `github-project-links.yaml` are separate profile-local stores; existing
registration storage is untouched; link verification derives the registration's
intake alias without persisting it; root changes block rather than migrate;
manual refresh is the only mutating trigger; and cron uses only the report-only
tool. If any change, Phases 0–9 must be re-read against this section before it
is touched.

**Phase ordering (2026-07-23):** Phases 0–1 establish the mounted dashboard
and a ready pack. Phase 2 starts a first workflow through the same
`SetupRequest` path as `daidala:setup`; Phase 3 then makes the resulting
workflow observable and controllable through its existing authority boundaries.
Configuration and data work follows in Phases 4–8, with closeout in Phase 9.
This is proposed scope only; it requires a fresh approval before Phase 0 starts.

**Implementer discipline (binding across every phase).**

- The DOX pass must happen **before** any implementation commit, not after.
  When a phase introduces a new dashboard route, a new mutation surface, a
  new module under `daidala/`, or any change to the `_run_command`-adjacent
  subprocess adapter count, the matching DOX updates (`dashboard/AGENTS.md`
  mutation allowlist, `daidala/AGENTS.md` Ownership table, `docs/AGENTS.md`
  if scope shifts, and `plugin.yaml` tool inventory) ship in the same
  commit as the source change. Phase 9 catches only what slipped through;
  it is not the primary DOX surface.
- New modules under `daidala/` are pre-registered in the `daidala/AGENTS.md`
  Ownership table *before* their first commit. Phase 4 will add
  `checkout_root.py` and `github_project_links.py`; Phase 6 will add
  `checkouts.py`. The Phase 6 step 8 `daidala_checkouts_status` tool
  (renamed from `daidala_checkout_sweep` to match its report-only contract)
  pre-registers in `daidala/AGENTS.md` Ownership and `plugin.yaml`'s
  `provides_tools` in the same commit as `daidala/__init__.py`'s
  `register(ctx)` entry, with `tests/test_plugin.py` proving exact
  parity.
- The route table under `/api/plugins/daidala/` is a **closed set**. Each
  phase's commit extends the inventory assertion in
  `tests/test_dashboard_api.py` (`test_router_exports_all_phase_two_routes`
  and its successors). Any route added outside that inventory fails the
  test and blocks the commit; no general tool-dispatch endpoint is
  permitted.
- Evidence that lives outside the repository (Phase 0 install logs,
  browser screenshots) is captured under
  `${DAIDALA_DASHBOARD_LOG_DIR:-${XDG_STATE_HOME:-~/.local/state}/daidala}/dashboard-setup/`,
  not in repo-tracked paths. The plan references but does not embed those
  artifacts.
- The plan's verification commands run in the order pinned in Phase 9 step
  5. Reordering a verification step is a phase-change and requires
  re-approval.

## Risk call-out

Four phases touch the filesystem or perform destructive cleanup; the
recovery path and safe default are pinned here so a future reader cannot
miss them.

- **Phase 3 — workflow cancellation.** The dashboard only confirms and invokes
  the existing `WorkflowService.cancel` path; that service archives cards and
  removes a Daidala-owned worktree when one exists. The router never deletes a
  path itself. The detail projection must name the affected worktree before the
  confirmation action is enabled.
- **Phase 6 — manual refresh and three-mode TTL policy.** The manager must
  never delete uncommitted local work: inventory tracked, untracked, and ignored
  paths and separately validate/exclude the exact `?? .daidala-owner` witness.
  Tracked or untracked rows always return 409. Ignored-only rows return 409 for
  `disabled`/`wipe-if-clean`; `backup-then-wipe` may proceed only after archiving
  them. A clean `wipe-if-clean` refresh replaces only a stale checkout;
  `backup-then-wipe` retains a tar.gz under
  `<checkouts.root>/_backups/` until explicit pruning; `disabled` disables
  TTL-triggered refresh only. A manual refresh in `disabled` mode is still
  dry-run-first, requires literal `confirm: true`, and follows the clean-tree
  path.
- **Phase 5 — GitHub Projects v2 link edit.** A link mutation is profile-local
  metadata in v1 and never invokes or changes `project-cycle admit`. Preview
  resolves the owner/project-number pair through the registration-derived intake
  credential, captures the returned node ID, and shows the exact strict
  `github-project-links.yaml` replacement. Replace occurs only after a fresh
  verification, matching preview digest, and literal confirmation, and preserves
  the previous file until the atomic mode-`0600` write succeeds.
- **Phase 4 — Root directory and collision safety.** The configured
  `<checkouts.root>` and every `<root>/<project_id>/` checkout must be
  validated as absolute, normalized POSIX paths with no `..` or `.`
  components, mirroring the existing `_require_absolute_checkout` rule
  in `daidala/registrations.py:251-257`. Every derived path must equal the
  corresponding immutable `ControllerRegistration.checkout`. Refusing a path that already
  exists and is owned by a different `project_id` prevents accidental
  cross-project wipeouts.

## Phase table

| # | Phase | Status | Verification gate |
|---|---|---|---|
| 0 | Create the registration-free dashboard profile and disposable fixture profile, install Daidala, verify both mounts | pending | SPA, manifest, and packaged asset checks pass; session-authenticated health identifies Daidala without pinning unauthenticated status; fixture profile has an independent local symlink, seeded non-secret state, and passes the stateful browser gate; teardown removes the fixture |
| 1 | Pack browser and readiness actions | pending | `dashboard/dist/index.js` renders both packs and their readiness; check and install-plan actions invoke installed Daidala services, external installation requires preview then confirmation, and focused dashboard tests pass |
| 2 | First-workflow setup wizard UX | pending | Wizard is an alternative UI over the exact `SetupRequest`/`daidala:setup` path; it verifies prerequisites, creates or selects a board, renders profile/pack/repository/goal/stage/constraint controls, and preserves preview-then-confirm start semantics |
| 3 | Workflow supervision actions | pending | Workflow views expose read-only watch/refresh, exact-digest approval, blocked-card comment/unblock recovery, and previewed cancellation through existing authority surfaces |
| 4 | Checkout configuration + GitHub Projects v2 link data model | pending | New `daidala/checkout_root.py` and `daidala/github_project_links.py` modules own separate strict mode-`0600` stores, collision safety, root-change blocking, and verified owner/number/node-ID links; focused model tests pass |
| 5 | GitHub Projects v2 link UI | pending | New section reads/writes one verified Projects v2 link per registered `project_id`; mutation requires a fresh bounded GitHub read, matching preview digest, and literal `confirm: true`; repository remote and intake alias are displayed only as registration-derived context |
| 6 | Manual checkout TTL manager and report-only cron hook | pending | `GET /checkouts`, confirmed adopt/refresh/prune actions, and read-only `daidala_checkouts_status`; preflight verifies registration path, owner marker, origin, symlink-free path, and classified Git status; ignored-only files require backup mode; `checkouts.yaml` defaults to disabled TTL |
| 7 | Constraint authoring UI | pending | Author modal renders schema-validated YAML editor with live preview, error list, and digest impact; preview feeds the existing `/constraints/preview` endpoint; replace path unchanged |
| 8 | Configuration verification panel | pending | Configuration remains read-only and verifies persisted root, TTL, registration, checkout, and GitHub Projects v2 link state without supervising a workflow or exposing secrets/private destinations |
| 9 | DOX pass and verification | pending | Owning AGENTS files and `plugin.yaml` are updated; all root verification commands pass; intended-path diff is clean except for the approved implementation changes |

Mark a phase `in-progress` while running it, `done (<evidence>)` once its
gate passes, `pending` otherwise.

Every implementation phase ends with the root-required DOX pass for the paths it
changed. Update the nearest owning `AGENTS.md` in that phase when contracts,
responsibilities, routes, tools, or structure changed; do not defer stale contract
text to Phase 9. Phase 9 is the final cross-tree consistency check.

## Phase 0 — Create `daidala-dashboard` profile, install Daidala, verify the dashboard mount

**Goal:** Bring up a fresh, isolated Hermes profile named
`daidala-dashboard`, install the Daidala dashboard plugin into it as
a local-checkout symlink, and pin the mount evidence so Phase 1 has a
known-good starting point. This phase produces no repository files or source
changes; its transient operational evidence remains outside the repository.

**Steps:**

1. Confirm the host is one of the supported Hermes versions — v0.18.2 or
   v0.19.0 within the bundled pack range `>=0.18.2,<0.20.0` — using
   `docs/08-hermes-integration.md`. Then create the new profile using the
   documented Hermes CLI. If the host identity is outside that exact support
   set, stop and report it before creating the profile or symlink. The profile is
   empty and ready to receive plugins:

   ```bash
   hermes profile create daidala-dashboard
   hermes profile list                                # daidala-dashboard must appear
   ```

2. Symlink the working tree into the new profile's `plugins/`
   directory and enable the plugin. `hermes plugins enable` prompts unless
   one of `--allow-tool-override` or `--no-allow-tool-override` is
   passed; Daidala does not declare built-in tool overrides, so the
   non-override flag is the correct choice and prevents an interactive
   hang under non-TTY execution:

   ```bash
   mkdir -p ~/.hermes/profiles/daidala-dashboard/plugins
   ln -s "$PWD" ~/.hermes/profiles/daidala-dashboard/plugins/daidala
   hermes -p daidala-dashboard plugins enable daidala --no-allow-tool-override
   # daidala must appear enabled; record the version-specific source label.
   hermes -p daidala-dashboard plugins list
   ```

3. Launch a dedicated dashboard process for this profile and retain its exact
   process handle for teardown. Do not restart the profile gateway: dashboard
   plugin APIs are mounted by `hermes dashboard`, and backend routes are loaded
   only at dashboard-process startup. `--isolated` is meaningful only when
   combined with `-p <profile>`; `--port 0` lets the OS assign a free
   loopback port and is the safe default for fixture work:

   ```bash
   hermes -p daidala-dashboard dashboard --isolated --port 0 --no-open
   ```

   Capture the printed loopback URL as `DASHBOARD_URL`. A plugin rescan can
   reload frontend assets later, but it cannot mount a newly added backend
   router; restart only this owned process when backend discovery changes.

4. Verify the dashboard mount without using an unauthenticated plugin-route
   response as capability evidence. First verify the SPA shell and compare the
   three served plugin files with the working tree:

   ```bash
   curl -fsSI "$DASHBOARD_URL/plugins?profile=daidala-dashboard"
   # expect: HTTP/1.1 200 OK (SPA shell still served; client-side mounts the Daidala tab)
   for asset in manifest.json dist/index.js dist/style.css; do
     curl -fsS "$DASHBOARD_URL/dashboard-plugins/daidala/$asset" \
       | cmp - "dashboard/$asset"
   done
   ```

   In the authenticated dashboard session, call both
   `/api/dashboard/plugins` and `/api/plugins/daidala/health` through
   `window.__HERMES_PLUGIN_SDK__.fetchJSON`. Confirm the manifest contains the
   `daidala` tab and that health returns `success: true` and `plugin: "daidala"`.
   Record but do not gate on an unauthenticated request's status. Phase 0 runs
   before the Phase 2 health-field rename, so it also does not pin the old
   `read_only` capability key.

5. In a browser, open
   `$DASHBOARD_URL/plugins?profile=daidala-dashboard` and
   confirm the `Daidala` tab appears in the navigation. If it does
   not, stop and surface the failure — do not fall through into
   Phase 1.
6. Create the timestamped fixture profile through the same documented
   per-profile installation recipe; install the local-checkout symlink into
   that profile too. The profile alias supplies its own `HERMES_HOME`; Daidala
   has no separate `DAIDALA_DATA_ROOT` variable. Populate temporary non-secret
   `registration.yaml` and
   `credential-bindings.yaml` fixture state, then launch a second isolated
   dashboard under that fixture with `--port 0 --no-open`. Run the stateful
   browser gate only against the second process's printed URL. Do not attempt to
   reach fixture state by changing `?profile=` on the host process, and do not
   source, copy, or display a real credential value. The fixture name must
   contain the generated timestamp.
7. Tear down the two isolated dashboard processes started by this phase and
   verify their ports no longer answer. Record
   `git status --porcelain` in the normal repository
   checkout, run `hermes profile list`, and verify the exact timestamped
   fixture name. Delete only that name with `hermes profile delete
   <fixture> -y`; then confirm the repository status is unchanged. This
   supports existing operator worktree changes and does not require a
   globally clean checkout.
8. Record the command output and browser result outside the repository's tracked
   files. This plan is not an evidence log and Phase 0 does not create a commit.

**Verification gate:** This phase is `done` only when the SPA shell, manifest,
and three served asset comparisons pass; session-authenticated SDK requests
discover the Daidala manifest and return health with `success: true` and
`plugin: "daidala"`; the browser shows the `Daidala` tab for the
registration-free host and
the stateful fixture on its own isolated dashboard process; both owned dashboard
processes have stopped; the fixture has been deleted after an exact-name check; and
`daidala-dashboard` does not own any Daidala workflow ledger, registration, or
notification state. No commit is created by this phase.

## Phase 1 — Pack browser and readiness actions

**Goal:** Surface both packs on the `/daidala` tab so the user can review their
provenance and determine whether each is ready before starting a workflow. The
bundled `aidlc` path is check-only; `addyosmani` exposes the same preview then
explicit-apply external-skill installation sequence documented in Getting
started.

**Steps:**

1. Read `/prerequisites` once on mount and feed `packs` into a new
   `PackBrowser` React component in `dashboard/dist/index.js`. Confirm
   `window.__HERMES_PLUGIN_SDK__` exposes `React.createElement` and the
   documented event hooks. If not, stop as a supported-host compatibility
   failure; do not bundle React or introduce an alternate framework.
2. Render one card per pack with name, source, source revision (40-hex),
   Hermes version constraint, lifecycle stage list, and a per-stage skill
   table with activation mode (`required`/`conditional`), bundled vs.
   external flag, and content digest.
3. The pack operations currently live behind the CLI's private
   `_run_pack_operation`; there is no dashboard-callable pack service yet.
   Extract a typed service that returns the same `PackInstallPlan` projection,
   and keep the CLI as one adapter over it. Add only the bounded routes `POST
   /packs/{name}/check`, `POST /packs/{name}/install/preview`, and `POST
   /packs/{name}/install`. Do not shell out to `hermes daidala` from the router
   and do not expose arbitrary pack operation or command fields.
4. Add a canonical preview digest over pack name, source, pinned and resolved
   revisions, Hermes constraint and observed version, install actions, current
   content digests, mismatches, and blockers. Check displays missing exact skills
   and digest mismatches next to the affected stage rather than a generic
   failure. Confirmed apply requires literal `confirm: true` and the matching
   preview digest, reruns resolution and inventory, and returns `409 Conflict`
   before installation if any bound input changed.
5. For packs with external skills, expose `Preview installation` and a separate
   confirmed `Apply installation` action backed by that service. Render the exact
   pinned install target and expected content digest before enabling apply.
   Never auto-install on page load or as part of workflow start. Packs with no
   external install action remain check-only.
6. Style the card to match existing host themes via the existing
   `dist/style.css` tokens.
7. Extend `tests/test_dashboard_assets.py`'s source-contract assertions for the
   dependency-free IIFE bundle: both pack names, the pack fields above, and the
   `/prerequisites` request must be present. Extend API tests for check,
   installation preview, stale-digest conflict, refusal without confirmation,
   and confirmed apply. Add service/CLI parity tests so extraction cannot drift.
   Do not introduce a JavaScript DOM harness merely for this panel.
   Phases 5 and 6 follow the same asset-contract pattern for their new
   panels (`GitHubProjectLinksPanel`, `CheckoutManager`); their verification
   gates name the regex or string-match assertions explicitly.

**Verification gate:** `pytest tests/test_dashboard_assets.py
tests/test_dashboard_api.py -q` exits 0; the bundle/API contract includes both
pack names and non-empty skills supplied by `/prerequisites`; `aidlc` reports
ready on a correctly installed fixture; and `addyosmani` cannot apply external
skill installation without a fresh matching preview and literal confirmation.

## Phase 2 — First-workflow setup wizard UX

**Goal:** Replace the minimal three-field wizard with the post-install first-run
path from `docs/00-getting-started.md`: verify readiness, create or select a
board, choose execution profiles and a ready pack, preview the exact start
request, and confirm creation of the workflow graph.

**Steps:**

1. Add a prerequisite step that shows plugin health, supported Hermes range,
   target-repository cleanliness, gateway reachability, selected pack readiness,
   and assigned-profile availability. `SetupRequest.preview()` currently checks
   payload shape only; it does not run repository or skill preflight. Extract the
   non-mutating prefix of `WorkflowService.start` (today: board slug validation
   and pack readiness checks that gate policy-ledger creation) as one typed
   start-readiness service and make both start and `POST /wizard/readiness` call
   it, so the UI cannot invent a weaker duplicate check. This is a new method on
   `WorkflowService` (e.g. `_validate_start_preflight(...)`) consumed by both
   the existing `confirmed_start` path and the new dashboard endpoint; the
   existing `tests/test_setup_wizard.py` and dashboard-API tests must be
   updated together so the wizard and CLI cannot diverge. The preview must not
   initialize a ledger schema, create artifacts/worktrees/cards, install
   skills, or create a board. Each failed item links to its actionable
   dashboard section; start remains disabled while a required check fails, and
   the disabled reason names the failing prerequisite by its stable backend
   check ID.
2. Extend the `SetupWizard` form state to carry `board_slug`,
   `target_repository`, `goal`, `pack`, `stage_profiles` (per-stage
   override), `workflow_id`, and the mutually exclusive
   `constraints_content` / `constraints_skill` +
   `constraints_skill_digest` triple
   (`daidala/setup_wizard.py:19-98`). The wizard form always supplies a
   stable, user-visible `workflow_id` (defaulted to a slug-safe variant
   derived from `goal`, editable, and shown alongside the preview) because
   `daidala/schemas.py::START` (`workflow_id` in the `required` list,
   lines 57-63) refuses a `null` value. `SetupRequest.from_payload`
   accepts `None` (`daidala/setup_wizard.py:81`), so the form forwards
   the user-edited value as-is and the wizard UX never relies on a
   server-side default.
3. Render `board_slug` as a `<select>` fed from `/wizard/inventory.boards`, plus
   a `Create board` action for the Getting started path. The existing
   `/wizard/boards` route mutates immediately and must be replaced with `POST
   /wizard/boards/preview` plus a confirmed `POST /wizard/boards`. Creation
   requires an explicit slug and display name; preview returns a canonical digest
   over the exact Hermes Kanban command and current board inventory. Apply
   requires that digest plus literal `confirm: true`, reruns inventory, and
   returns conflict if the slug now exists. Refresh inventory and select the new
   board after success.
4. Render
   `pack` as a `<select>` fed from `prerequisites.packs`, and a
   per-stage profile `<select>` per executable stage fed from
   `/wizard/inventory.profiles`. The form must submit all six executable stages
   exactly once because `SetupRequest` has no `default_profile` field; preselect
   the actual profile named `default` only when inventory contains it, otherwise
   require an explicit selection. Do not model the CLI's convenience
   `--default-profile` flag as a seventh dashboard field.
5. Render a constraint source tab group: "Write YAML", "Reference skill
   (name + digest)", or "No constraints". A new workflow has no currently bound
   constraint revision; the last option sends all three constraint fields as
   `null`/absent.
6. Preserve endpoint and payload parity with `daidala:setup`: `/wizard/preview`
   must validate with `SetupRequest.from_payload` and return that request's
   `SetupRequest.preview()` projection plus a canonical digest over the normalized
   request and start-readiness evidence. `/wizard/start` accepts that digest as a
   route envelope field, reruns readiness, returns conflict if the digest changed,
   then calls `confirmed_start(payload, service.start)` with the existing setup
   fields and literal `confirm: true`. The browser must not introduce a
   dashboard-only setup schema or second start path. Before invoking start, the
   server checks a supplied stable `workflow_id`; if a ledger already exists, it
   does not invoke start and returns `409 Conflict` with a safe reference to the
   existing workflow. The browser treats that response as "open existing", not
   as successful creation. The new `/wizard/readiness` route from step 1 and
   `/wizard/boards/preview` from step 3 each extend the route inventory
   assertion in `tests/test_dashboard_api.py` (the
   `test_router_exports_all_phase_two_routes` harness).
7. On success, route directly to the created workflow and show the next user
   action: keep the gateway running and watch `define` then `plan`.
8. Extend the existing Python API and source-contract tests rather than adding a
   JavaScript DOM harness: assert the serialized wizard request matches
   `schemas.py::START` and that the server rejects `confirm: false` before it
   constructs the workflow service.
9. Correct the stale GET-only claims in the `dashboard/dist/index.js` header and
   `tests/test_dashboard_assets.py` module docstring: the existing setup and
   constraint preview/confirmation flows already use scoped `postJson()` calls.
   Keep the read model and polling read-only, and update the existing asset
   assertions to describe the bounded mutation allowlist rather than claiming
   the whole bundle never sends POST.
10. Replace `/health`'s misleading `read_only: true` field with
    `read_model: true`. Update `dashboard/plugin_api.py`, its health assertion in
    `tests/test_dashboard_api.py`,
    `scripts/probe_hermes_dashboard_compatibility.py`, and the per-profile
    installation table in `docs/08-hermes-integration.md` together. The probe
    must continue to use a dashboard session token for plugin API calls and must
    not assert any unauthenticated status. Assert that the new response contains
    `read_model: true` and no `read_only` key.

**Verification gate:** the affected `tests/test_dashboard_api.py` and
`tests/test_dashboard_assets.py` cases pass; board creation and workflow start
both fail without fresh matching preview/confirmation; readiness is mutation-free
and shares start's preflight; a clean repository and ready
pack can create a board and start one workflow; and manual review confirms the
rendered form covers every field accepted by `SetupRequest` and preserves the
semantics of the CLI conveniences documented in `daidala/AGENTS.md:178-198`.
The updated dashboard compatibility probe passes with `read_model: true` while
preserving its manifest, packaged-asset, preview, and declined-start
non-mutation checks.

## Phase 3 — Workflow supervision actions

**Goal:** Immediately after a workflow starts, give the user the remaining
Getting started actions without making the dashboard a second workflow engine:
watch live card state, inspect the pending plan, approve its exact digest,
remediate a blocked card, or preview and confirm cancellation.

**Steps:**

1. Extend the existing workflow detail view with a stage timeline from
   `DashboardBackend.workflow_view`, `/decisions`, and `/recommendations`. Show
   the current card, live Kanban availability, run/comment diagnostics, artifact
   references, and the finite next action. Poll only while the view is visible,
   no faster than the existing five-second dashboard contract; manual refresh is
   read-only.
   The implementation must retain the existing hidden-tab pause and snapshot-only
   client authorization rules in `dashboard/AGENTS.md`.
2. When planning completes, render the plan artifact reference, full
   64-character pending digest, and scope/risk/verification prompt. `Approve
   exact plan` requires the displayed digest plus a literal confirmation and
   calls `POST /workflows/{workflow_id}/approve` with `{plan_digest,
   confirm: true}`. That route delegates to `WorkflowService.approve`, the same
   service used by `daidala_approve`. A stale digest fails closed; generic Kanban
   unblock is never presented as approval.
3. For a blocked card, show its comment and run history. Provide distinct
   `Comment remediation` and `Unblock for retry` actions through the public
   `hermes kanban` CLI boundary only. Add two private adapters beside
   `dashboard.plugin_api._run_command`, rather than extending the generic
   `daidala/cli.py` dispatch table: it currently supports `kanban_comment` but
   not `kanban_unblock`, and the dashboard needs no general dispatch surface.
   The adapters run exactly `hermes kanban --board <derived-board> comment
   <card_id> <comment>` or `hermes kanban --board <derived-board> unblock
   <card_id> --reason <reason>` after server-side workflow/card validation.
   Expose `POST
   /workflows/{workflow_id}/cards/{card_id}/comment` and `POST
   /workflows/{workflow_id}/cards/{card_id}/unblock`. Comment accepts
   `{comment: string, confirm: true}`; unblock accepts `{reason: string,
   confirm: true}`. Both text fields must be non-empty. The server loads the
   current workflow ledger, verifies `card_id` belongs to that workflow, and
   derives the board slug from durable state; it never accepts a board selector
   from the browser. Neither action changes Daidala approval state or rewrites
   captured evidence. Invoke argv without a shell, fail closed on timeout or
   nonzero exit, and bound captured subprocess output before returning a sanitized
   route error.
4. Add `Cancel workflow` as a dashboard-composed preview followed by confirmed
   mutation. The existing read-only workflow detail projection supplies the
   affected cards and Daidala-owned worktree, but the action must also compute a
   canonical cancellation preview digest over workflow ID, current ledger token,
   card identities, owned worktree identity, and normalized reason. Submit
   `POST /workflows/{workflow_id}/cancel` with that digest and literal `confirm:
   true`; the router recomputes it and returns conflict if state changed. No
   second engine is needed: after the compare-and-swap check, the route delegates
   to the same `WorkflowService.cancel` used by `daidala_cancel`. The policy and
   artifact ledger remain. Do not expose commit or push controls; delivery
   remains `committed: false` and `pushed: false`.
5. This phase extends the current mutation allowlist — board creation,
   confirmed setup, and compare-and-swap constraint replacement — with the
   confirmed approval, comment/unblock, and cancellation routes above. Each route
   is server-side authorized from current durable state, not client state. Along
   with the preview/confirm actions explicitly named in Phases 1 and 4–7, these
   are the complete browser mutation surface; no route may proxy an arbitrary
   Daidala tool or Hermes command. The `_run_command`-adjacent subprocess
   adapter count rises from 0 to 2 (`kanban_comment`, `kanban_unblock`); future
   phases that add a third must update this count. The `dashboard/dist/index.js`
   header and the `tests/test_dashboard_assets.py` module docstring currently
   claim a GET-only bundle even though the existing Phase 2 setup and
   constraint flows already use `postJson()`; correct both stale statements as
   part of Phase 2, then extend the asset contract for these named Phase 3
   POST requests. Do not add a general tool-dispatch endpoint. Update
   `dashboard/AGENTS.md` **before** this source commit so its mutation
   allowlist matches this boundary.
6. Keep supervision as a presentation layer over existing read, approval,
   cancellation, and public Kanban boundaries. It must not create a scheduler,
   persist live card status, access the Kanban database directly, or expose the
   self-improvement `doctor` diagnostic.
7. Add the four named workflow-action routes to `dashboard/plugin_api.py` as
   thin adapters only: validate the literal confirmation and route-specific text
   fields, resolve the current service, then call the existing Daidala service or
   public Hermes Kanban adapter. Do not reimplement approval, cancellation, or
   Kanban state transitions in the router.

**Verification gate:** Add focused dashboard API and asset-contract coverage for
read-only watch/refresh; the exact-digest approval payload and stale/unchecked
rejection; public-Kanban comment/unblock forwarding with required text,
confirmation, and workflow-owned-card checks; and cancellation with a required
reason, fresh preview digest, confirmation, and detail projection that names the
affected cards and owned worktree. The affected `tests/test_dashboard_api.py` and
`tests/test_dashboard_assets.py` cases pass; unblocking cannot approve a plan;
and no dashboard route commits or pushes.

## Phase 4 — Checkout configuration + GitHub Projects v2 link model

**Goal:** Add strict, audit-friendly checkout configuration and bind at most one
verified GitHub Projects v2 board to each registered project without duplicating
or weakening `ControllerRegistration`.

**Steps:**

1. Add `daidala/checkout_root.py` with a frozen `CheckoutConfig` record and
   strict `daidala.checkouts/v1` serialization. **Phase 4 owns the entire
   `daidala.checkouts/v1` document** (`schema` and `checkouts` keys; root,
   mode, ttl_hours fields); Phase 6 writes only `mode`/`ttl_hours` through
   the preview/confirmed `/checkouts/policy` route and preserves the
   `root` field. Both phases call `checkout_root.read()` so the same
   record serves both root mutation and policy mutation. The document
   contains exactly `schema` and `checkouts`; `checkouts` contains
   exactly absolute `root`, `mode`, and `ttl_hours`. Phase 4 validates and
   persists all three fields so Phase 6 does not require a schema
   migration, but only root/path helpers are operational here. Defaults
   are `<resolve_data_root()>/work`, `disabled`, and `0`. Validate root
   through the same POSIX-path rules as `_require_absolute_checkout`
   (`daidala/registrations.py:251-257`), derive
   `<root>/<project_id>/`, and reject `.`/`..` and symlink components.
   For every existing registration, require that derived path to equal
   its immutable `checkout`; otherwise configuration preview is blocked
   with both paths and no file is written. The disk witness
   (`<root>/<project_id>/.daidala-owner`) and the derived-path equality
   are two separate invariants: the sidecar proves the *on-disk* path is
   reusable; the derived-path equality is the fail-closed registration
   invariant. Both must hold before any phase accepts the configuration
   as valid.
2. Add collision-safety helpers that refuse a pre-existing project path unless
   its mode-`0600` `.daidala-owner` contains the same strict `project_id` and its
   Git `origin` equals the registration's `verified_remote`. A missing marker on
   a pre-existing directory is unowned and must fail closed; Phase 4 never
   adopts it. A tracked or ignored `.daidala-owner` is invalid; the witness must
   be the exact untracked file written by Daidala. Root replacement returns
   conflict while any owned checkout exists
   beneath the current root or any existing registration would not match its
   derived path under the proposed root. GitHub Project links are independent
   and do not block root replacement.
3. Add `daidala/github_project_links.py` with a frozen `GitHubProjectLink`
   dataclass containing exactly `project_id`, canonical GitHub `owner`,
   positive `project_number`, and bounded `project_node_id`. `owner`
   is validated by a strict regex equivalent to
   `^[A-Za-z0-9][A-Za-z0-9-]{0,38}$` (GitHub user/org login shape, ≤
   39 chars) so the field is symmetric with the `_REPOSITORY` regex in
   `daidala/registrations.py:27`. The strict
   `daidala.github-project-links/v1` store holds zero or one row per registered
   `project_id`, rejects unknown fields and duplicate YAML keys/rows, and lives
   only at `<resolved-data-root>/github-project-links.yaml` mode `0600`.
   Repository identity, verified remote, checkout path, and credential alias are
   never persisted in a link; they remain registration/configuration data.
4. Add a bounded verifier that resolves the registration's existing
   intake alias through `credential-bindings.yaml`, exposes it to only
   the child call as `GH_TOKEN`, and runs
   `gh project view <number> --owner <owner> --format json`. The intake
   alias is the **Hermes Kanban intake alias** bound to
   `read_credential_alias` in `credential-bindings.yaml`; the GitHub
   Projects v2 read uses the same alias, not a dedicated Projects-only
   binding. Pre-flight: the verifier asserts `gh --version` is on `PATH`
   and parses `--help` for the `project view --owner --format json`
   triple before the first live read. `gh project view` is not currently
   exercised by `live_adapters.py` (`daidala/live_adapters.py:101-105`
   shows only `gh issue` invocations); the verifier therefore needs its
   own binary-shape proof. Require the registration's declared intake
   capabilities to contain `read-project`; otherwise return a blocked
   result before resolving credentials. Build a credential-minimal
   child environment carrying `GH_TOKEN=<resolved>`,
   `GH_PROMPT_DISABLED=1`, `GIT_TERMINAL_PROMPT=0`, `NO_COLOR=1`, and
   `PATH` (so `gh` resolves); do not copy the whole dashboard
   environment. Respect `${HTTPS_PROXY}` / `${NO_PROXY}` when set.
   Give the child a 30-second timeout and accept at most 64 KiB combined
   output. Parse strict JSON, require the returned node ID and
   owner/number identity, and retain no token or raw output. Preview
   accepts only `project_id`, owner, and number; the server, not the
   browser, supplies the node ID.
5. Add `GET /api/plugins/daidala/github-project-links`, `POST
   /api/plugins/daidala/github-project-links/preview`, and `PUT
   /api/plugins/daidala/github-project-links/{project_id}`, plus read-only `POST
   /api/plugins/daidala/github-project-links/{project_id}/verify`. Preview performs the
   bounded read, returns sanitized Project title/URL plus node ID, canonical YAML
   diff, target path/mode, and digest, and makes no mutation. Upsert requires
   literal `confirm: true`, reruns the GitHub read, and requires the same preview
   digest. Removal is local-only but still requires a dedicated removal preview,
   matching digest, and confirmation. Verify performs the same bounded live read
   against a persisted row but never writes. Stale identity returns `409
   Conflict` for mutation and a structured unhealthy result for verify.
   Add read-only `GET /api/plugins/daidala/registrations` for the selectors used
   by Phases 5 and 6. Return only project ID, checkout, repository identity,
   verified remote, board, intake alias, and declared capabilities from strict
   registrations; never return bindings, environment-variable names, or values.
   The route resolves registrations from the **active dashboard profile's**
   `<data-root>/projects/<project_id>/registration.yaml` (controller-profile
   data, not the registration-store surface); on `daidala-dashboard` the
   response is always `[]` because that profile is registration-free, and on
   the disposable fixture the response lists the seeded registration.
6. Add `GET /api/plugins/daidala/checkout-root`, `POST
   /api/plugins/daidala/checkout-root/preview`, and `PUT
   /api/plugins/daidala/checkout-root`. Preview exposes the resolved old/new root
   and owned paths. Apply requires its expected digest and literal `confirm:
   true`, atomically writes mode `0600`, and returns conflict rather than moving
   data whenever an owned checkout exists under the current root. With no
   registrations and no owned checkout, an absent file resolves to the defaults
   and a confirmed root replacement is allowed.

**Verification gate:** New `tests/test_checkout_root.py` covers defaults, exact
schema, mode-`0600` round-trip, POSIX/symlink rejection, unowned-directory
refusal, origin/marker mismatch, and root-change blocking while an owned checkout
exists. New `tests/test_github_project_links.py` covers strict one-link-per-
registration parsing, owner/number/node-ID validation, duplicate and unknown
field rejection, bounded credential-minimal `gh project view`, no secret/raw
output retention, no registration-file writes, fresh preview/confirmation for
upsert and removal, stale-node-ID conflict, safe registration projection, and
concurrent first-read/write serialization across all new stores. Both test files
exit 0.

## Phase 5 — GitHub Projects v2 link UI

**Goal:** Add a configuration section that lists, verifies, adds, edits, and
removes one GitHub Projects v2 link per registered `project_id`, gated by the
preview/replace compare-and-swap pattern.

**Steps:**

1. Render a `GitHubProjectLinksPanel` grouped by `project_id`. Each row displays
   Projects owner, project number, and verified node ID. An explicit `Verify`
   action calls the read-only live endpoint and displays sanitized title/URL and
   a session-only result; the result is not persisted. Display repository identity, verified remote,
   intake alias, and resolved checkout path in a separate "registration context"
   block so the UI does not imply they are duplicated link fields.
2. The "Add link" form requires only `project_id` (chosen from the Phase 4
   `/registrations` projection), owner, and project number. Submit to
   `/github-project-links/preview`, show the live-resolved Project identity and
   canonical diff, then send `PUT /github-project-links/{project_id}` with the
   matching digest and literal `confirm: true`. Never accept a credential alias,
   remote, token, or node ID from browser form state.
3. Render distinct blocked states for missing registration/bindings, failed
   Project read capability, nonexistent/inaccessible Project, stale node ID, and
   missing or ownership-invalid checkout. A checkout warning does not prevent an
   otherwise valid Projects link because the two records have separate authority.
4. The mutation never invokes or changes `project-cycle admit`; v1 uses the link
   for configuration/verification display only.

**Verification gate:** the affected `tests/test_dashboard_api.py` and
`tests/test_dashboard_assets.py` cases pass; the panel renders every current
link, accepts only owner/number input, verifies without mutation, refuses
edits/removals without a fresh
matching preview digest and literal confirmation, never returns a credential
value, and surfaces a "no GitHub Project configured" empty state.

## Phase 6 — Manual checkout refresh, TTL policy, and report-only cron hook

**Goal:** Add a bounded dashboard checkout-refresh path and persisted TTL
policy. `disabled` is the default and disables automatic/TTL-triggered refresh;
an explicit operator refresh remains allowed and uses the same dry-run,
confirmation, and clean-tree safeguards. This phase does not alter admission.

**Steps:**

1. Add `daidala/checkouts.py` with checkout status and lifecycle operations over
   Phase 4's persisted `CheckoutConfig`. A `TtlPolicy` projection exposes
   (`mode: "disabled" | "wipe-if-clean" | "backup-then-wipe"`,
   `ttl_hours: int`) plus a `CheckoutStatus` projection (path exists, last
   `git log -1 --format=%ct` age in hours, and classified
   tracked/untracked/ignored status counts). Default is `mode="disabled",
   ttl_hours=0`.
   `checkouts.py` owns status, refresh, backup, and report-only sweep behavior; it
   consumes but does not redefine `checkout_root.py`'s schema and remains
   independent of `github_project_links.py`.
2. Add `GET /api/plugins/daidala/checkouts` that returns status for every
   registered project and a clear `missing_checkout` state when its derived path
   does not exist. GitHub Project linkage is irrelevant. The read verifies the
   sidecar and `origin` locally but never contacts GitHub or mutates the
   filesystem.
3. Add `POST /api/plugins/daidala/checkouts/{project_id}/refresh` that:
   - refuses an unknown project, loads its strict registration, and clones only
     that registration's `verified_remote`; it never accepts a remote URL or
     checkout path in the refresh payload;
   - preflights `git status --porcelain --untracked-files=all
     --ignored=matching` by parsing `git --version` output and inspecting
     `git status --help`; if the requested flag combination is not
     advertised, the manager returns `409 Conflict` rather than running
     the refresh against an unsupported git version;
   - for a missing checkout, returns the planned clone in dry run and clones
     only after literal `confirm: true`;
   - for an existing checkout, revalidates the symlink-free derived path,
     mode-`0600` owner marker, exact registration checkout, and exact `origin`,
     then runs `git status --porcelain --untracked-files=all --ignored=matching`
     through `subprocess.run(argv, …)` only (no `import git`, no `GitPython`:
     the no-private-import contract from `daidala/AGENTS.md:171-173`
     applies equally to `git`);
     discard only the exact untracked marker row after validating its bytes/mode.
     Any tracked/untracked row returns 409 before backup, clone, rename, or
     deletion. Ignored-only rows also abort `disabled`/`wipe-if-clean`; under
     `backup-then-wipe` they must be included in the archive before replacement;
   - on `disabled`, permits this explicitly requested refresh after the clean
     check, ignores `ttl_hours`, and uses the `wipe-if-clean` cleanup path;
   - on `wipe-if-clean` or `backup-then-wipe`, re-clones only when a clean
     checkout head age exceeds `ttl_hours`; otherwise returns an unchanged,
     successful no-op report;
   - on `backup-then-wipe`, tar/gzips the clean working tree into
     `<checkouts.root>/_backups/<project_id>.<unix-ts>.tar.gz` with the
     `_backups` directory mode `0700` before the verified replacement swap;
   - clones into a fresh sibling temporary directory first, validates its exact
     `origin` and checkout shape, then uses a bounded same-parent swap so a clone
     failure leaves the old checkout intact; cleanup touches only paths created
     and marked by this operation;
   - treats omitted or `confirm: false` as dry run and requires literal
     `confirm: true` plus a fresh preview digest for every clone, swap, backup,
     or sidecar write.
4. Add preview/confirmed `POST
   /api/plugins/daidala/checkouts/{project_id}/adopt` for an existing unowned
   registration checkout. Adoption requires exact registration/derived-path and
   origin equality, no symlink component, no tracked/ignored marker, and a fully
   clean tracked/untracked inventory. It writes only the mode-`0600` witness
   after a fresh matching digest and literal confirmation; there is no force or
   arbitrary-path form.
5. Add `POST /api/plugins/daidala/checkouts/_backups/prune` that lists
   `<checkouts.root>/_backups/*.tar.gz` and deletes *only* request-named
   backups after literal `confirm: true` and matching preview digest. Reject
   absolute paths, separators, `..`, symlinks, non-regular files, and names not
   returned by the preview. Backups are never auto-deleted; no
   `backup_retention_hours` knob is introduced. Return remaining filenames.
6. Add `POST /api/plugins/daidala/checkouts/policy/preview` and `PUT
   /api/plugins/daidala/checkouts/policy`. They preview then atomically replace
   only `mode` and `ttl_hours` inside Phase 4's strict mode-`0600`
   `daidala.checkouts/v1` document while preserving `root`, using an expected
   digest and literal `confirm: true`. Every `/checkouts` read loads its live
   policy from that file.
7. Render a `CheckoutManager` component with a mode selector (`disabled` by
   default), TTL number input, explicit policy preview/save confirmation,
   per-row adopt/dry-run/apply refresh actions, and named-backup pruning.
8. Add a zero-argument `daidala_checkouts_status` plugin tool for
   future Hermes cron consumption (renamed from
   `daidala_checkout_sweep` so the name reflects the report-only
   contract; v1 ships the tool without a cron schedule, so the name
   must not imply one exists). Add its schema, handler mapping,
   runtime registration, **Ownership-table entry in
   `daidala/AGENTS.md`**, and `plugin.yaml` `provides_tools` entry
   together in `daidala/schemas.py`, `daidala/tools.py`,
   `daidala/__init__.py`, `daidala/AGENTS.md`, and `plugin.yaml`;
   `tests/test_plugin.py` must continue to prove exact
   manifest/runtime parity. Its input schema is an object with no
   properties and `additionalProperties: false`; its handler follows
   the plugin contract by returning a JSON string and never leaking
   exceptions. `plugin.yaml` inventories only this Hermes tool; HTTP
   routes remain owned by `dashboard/plugin_api.py`. It returns
   checkout status projections only: no clone, marker write, backup,
   prune, link change, or policy change. This phase creates no cron
   schedule.

**Verification gate:** `pytest tests/test_checkouts.py tests/test_plugin.py
tests/test_tools.py -q` exits 0. Tests prove a disabled-policy explicit refresh
is dry-run-first and proceeds only for a clean checkout after confirmation;
tracked/untracked changes, marker/origin mismatches, and symlink paths abort every
mode; ignored-only files require `backup-then-wipe` and appear in its archive;
safe adoption requires a fresh confirmed preview; a failed replacement clone
retains the old checkout; stale `wipe-if-clean` and `backup-then-wipe`
behave as specified; missing checkouts need confirmation; only named backups
are pruned after confirmation; policy persists across service reinstantiation;
unsupported `git status` flag combinations return 409 without refresh; and
`daidala_checkouts_status` is registered with no mutation path.

## Phase 7 — Constraint authoring UI

**Goal:** Add a guided authoring surface for new constraints so the user
can author content, preview the canonical digest, and only then apply the
compare-and-swap replacement.

**Steps:**

1. Add a `ConstraintEditor` component with a YAML `<textarea>`, an
   "Insert schema skeleton" button, and an inline error pane fed by the response
   of `/constraints/preview`. `/prerequisites.schema_limits.schema` currently
   contains only the schema identifier string (`CONSTRAINTS_SCHEMA` in
   `daidala/dashboard_backend.py:163`), not a JSON schema or template.
   Extend the backend projection with a bounded `constraint_template` generated
   from the implemented `WorkflowConstraints` shape and use that exact field;
   the template content must match the starter-template paragraph in
   `docs/14-workflow-constraints.md` (inlined here verbatim so the editor
   never drifts from the docs and the implementer does not hand-author a
   second template). Pin the field as
   `{ "kind": "yaml-template", "source": "docs/14-workflow-constraints.md#starter-template",
   "content": "..." }`.
2. The editor shows the canonical content returned by `/constraints/preview`
   so the user sees exactly what the ledger will store
   (`daidala/dashboard_backend.py:287-377`).
3. The "Apply replacement" button is disabled until the editor emits a
   `valid: true` preview and a checked confirmation; it calls
   `/constraints/replace` with the displayed `current_digest` to enforce
   the compare-and-swap contract.
4. Add a "Reference skill (name + digest)" mode that mirrors
   `setup_wizard.SetupRequest.constraints_skill` and
   `constraints_skill_digest` (`daidala/setup_wizard.py:54-74`).

**Verification gate:** extend the existing `tests/test_dashboard_api.py` and
`tests/test_dashboard_assets.py` contracts. The cases pass while proving the
editor rejects apply without a fresh valid preview, matching current digest, or
literal `confirm: true`, and
surfaces the schema bounds (`global_max`, `phase_max`, `constraint_bytes`,
`canonical_bytes`) from `daidala/dashboard_backend.py:158-164`.

## Phase 8 — Configuration verification panel

**Goal:** Render the current Daidala configuration as a read-only verification
panel for persisted checkout, registration, GitHub Projects v2 link, intake,
evaluator, notification, and checkout-status state. Workflow watch, approval, recovery,
and cancellation belong only to Phase 3.

**Steps:**

1. Add a read-only `DashboardBackend.configuration` projection and `GET
   /api/plugins/daidala/configuration`. It returns `checkouts.root`, every
   registered `(project_id, <root>/<project_id>/)` pair, the persisted
   `checkouts.yaml` mapping (`root`, `mode`, `ttl_hours`), each zero-or-one GitHub Project
   owner/number/node-ID state, intake capability declaration, evaluator backend
   + network, notification adapter + target alias + destination-presence boolean,
   and `CheckoutStatus` summaries. The route is added to the closed route
   inventory assertion in `tests/test_dashboard_api.py` alongside the other
   `/configuration` consumers. It must not return environment-variable
   values, tokens, raw probe output, or the private notification destination.
   It labels GitHub Project links as profile-local metadata that does not drive
   intake or admission in v1.
2. Render the panel as a labeled list with a green/red status pill per
   item; failures cite the exact missing element rather than a generic
   "unreachable" banner.
3. Render a yellow banner when `mode != "disabled"` warning that a confirmed
   manual stale refresh may wipe or back up clean local data; never say it runs
   during admission.
4. The panel never mutates; a "Run verification again" button is the
   only action and it is a `GET`.

**Verification gate:** extend `tests/test_dashboard_api.py`'s existing
`load_api()` harness for the new `GET /configuration` route and add only the
needed source-contract assertion in `tests/test_dashboard_assets.py`. The cases
pass while proving the projection renders every section, reports the resolved
root and each registration's checkout/link state, exposes mode + TTL from the
strict nested `checkouts` mapping, and
shows a "no registrations" empty state when the controller profile is empty and
a per-registration "no GitHub Project configured" state when only the link is
absent.
The yellow warning appears only when `mode != "disabled"`. The panel issues no
mutation request.

## Phase 9 — DOX pass and verification

**Goal:** Update the relevant AGENTS.md files and run the documented
verification surface.

**Steps:**

1. Update `dashboard/AGENTS.md` to reflect the new components
   (`PackBrowser`, `SetupWizard` overhaul, `GitHubProjectLinksPanel`,
   `CheckoutManager`, `ConstraintEditor`, configuration verification
   panel, and workflow actions) and the new read-only /
   preview-then-confirm split. Verify that the Phase 2 GET-only-claim corrections
   persisted and that Phase 3's explicit mutation allowlist is documented;
   remove any contradictory language.
2. Confirm the phase-local DOX passes updated `daidala/AGENTS.md` ownership for the separate
   `checkout_root.py`, `github_project_links.py`, and `checkouts.py`
   responsibilities; document the `/github-project-links/*`, `/checkout-root/*`, `/checkouts/*`, and
   `/configuration` routes, three TTL modes, and report-only
   `daidala_checkouts_status` tool. Confirm Phase 6 updated `plugin.yaml` together
   with runtime tool registration so their inventories remain exact, and that
   `tests/test_plugin.py` re-asserts the manifest/runtime parity.
3. Confirm `docs/08-hermes-integration.md` and
   `scripts/probe_hermes_dashboard_compatibility.py` describe and verify the
   session-authenticated `read_model: true` health contract without pinning an
   unauthenticated plugin-route status.
4. Re-read `docs/AGENTS.md`, `dashboard/AGENTS.md`, and `daidala/AGENTS.md`
   after implementation; update each only when its owned purpose, structure, or
   contract changed. Refresh any affected Child DOX Index; do not add a child
   index entry merely because an existing folder gained a file.
5. Run the documented verification in dependency order: `lefthook validate`,
   `pytest`, `ruff check .`, `daidala packs validate addyosmani`, `daidala packs
   validate aidlc`, `python -m build`, `python -m twine check dist/*`, then
   `python scripts/check_release_contents.py . --wheel dist/*.whl`, and finally
   `python scripts/check_md_links.py .` and
   `python scripts/probe_hermes_dashboard_compatibility.py`. `python -m build`
   must produce the wheel before either wheel-consuming command runs.
   `probe_hermes_dashboard_compatibility.py` requires the pinned Hermes
   checkout's web distribution to be built once (see
   `scripts/AGENTS.md`); on a non-interactive machine or in CI, invoke it
   with `--skip-build`. These are the complete root/docs verification
   surfaces for Phase 9, not Phase 0 teardown checks.

**Verification gate:** Every command in the root AGENTS.md verification
block exits 0; `dashboard/AGENTS.md` and `daidala/AGENTS.md` reflect the
new components, endpoints, ownership, and three-mode TTL policy;
`git diff --check` exits 0; and the final status is reviewed against the
Phase 0 baseline so pre-existing operator changes are neither modified nor
mistaken for implementation output.

## Out of scope

- Editing the underlying `daidala_start` tool schema, the
  `setup_wizard.SetupRequest` shape, or any CLI flag. The wizard maps onto
  them as-is.
- Replacing the wizard with a chat-driven setup. The dashboard extension
  remains a presentation surface, not a model client.
- Auto-applying `project-cycle admit --apply` from the browser. Admission
  remains operator-driven through the documented operator CLI or the
  `daidala:orchestrate` skill.
- Reading or writing the Hermes Kanban database directly. All mutations go
  through the documented `hermes kanban` boundary or the Daidala policy
  ledger.
- Adding new workflow packs. Phase 1 surfaces the existing two; pack
  authoring remains a CLI/disk activity.
- Silent checkout deletion. Refresh classifies tracked, untracked, and ignored
  rows after excluding only a separately validated untracked owner marker.
  Tracked/untracked work always blocks replacement; ignored-only files require
  `backup-then-wipe`; every mutation requires a fresh preview digest and literal
  `confirm: true`. `disabled` blocks automatic/TTL-triggered refresh only. A
  failed replacement clone leaves the existing checkout intact.
- Auto-pruning the `_backups/` directory. Pruning requires an explicit
  named-backups `POST …/checkouts/_backups/prune` call with
  `confirm: true`.
- Starting or supervising the gateway from the dashboard. The UI reports
  gateway readiness and tells the user to keep the existing Hermes gateway
  running; Daidala still adds no service or dispatcher.
- Treating Kanban unblock as plan approval. Exact-digest approval remains a
  separate Daidala action.
- Any dashboard mutation other than the named, confirmation-gated board creation,
  setup, constraint replacement, approval, card comment/unblock, cancellation,
  checkout, GitHub Project-link, and TTL-policy operations in this plan. In particular,
  the dashboard never exposes a general tool dispatcher.
- Commit or push controls. Delivery remains evidence-only with
  `committed: false` and `pushed: false`.