# Daidala brand cutover implementation plan

> Status: **Approved for phase-gated execution. Phases 0–2 are complete; Phase 3 is next.**
>
> This is a hard public rename. Do not add compatibility packages, import shims,
> CLI aliases, tool aliases, skill aliases, schema fallbacks, or data migration.

## Goal

Rename the complete project identity from Wingstaff to **Daidala**, including the
Python distribution and package, Hermes plugin, command and tool surfaces,
bundled skill namespace, persisted schema identities, runtime paths, dashboard,
repository, documentation, tests, release probes, and generated brand assets.
Add the story and pronunciation of Daidala to the root `README.md`.

## Name and narrative decision

Use these canonical forms everywhere:

| Surface | Canonical value |
|---|---|
| Product | `Daidala` |
| Pronunciation | `DYE-dah-lah` |
| Python distribution | `daidala` |
| Python package/import | `daidala` |
| Standalone executable | `daidala` |
| Hermes plugin and CLI command | `daidala`; `hermes daidala` |
| Tool prefix/toolset | `daidala_`; `daidala` |
| Bundled skill namespace | `daidala:<skill>` |
| Dashboard tab/API namespace | `/daidala`; `/api/plugins/daidala` |
| Runtime data directory | `$HERMES_HOME/daidala` |
| GitHub repository | `forgegod/daidala` |
| Landing-page candidates | `daidala.io`, `daidala.dev` |
| Breaking-release version | `0.2.0` |

The README should place this concise section immediately after the opening
product description, before the feature inventory:

> ## Why Daidala
>
> **Daidala** (pronounced *DYE-dah-lah*) is an Ancient Greek name for
> skillfully crafted or fashioned works. The word belongs to the tradition of
> Daedalus, the legendary maker, and the wondrous craft associated with
> Hephaestus.
>
> The name fits a Hermes-native AI workshop built around disciplined craft
> rather than unconstrained automation. Daidala brings specialist agents and
> skills into an ordered process: a goal is defined, planned, approved by a
> human, implemented in isolation, verified, reviewed, and delivered with
> evidence. Skills provide the craft, workflow constraints shape the work, and
> Hermes supplies the agent runtime.

Link “skillfully crafted or fashioned works” to the supporting discussion in
[The Fall of the Tektōn and the Rise of the Architect](https://journal.eahn.org/articles/10.5334/ah.239/).
Keep this as product narrative, not an etymology essay. Do not describe Daidala
as a separate orchestration service or autonomous model runtime.

## Current context

- The repository is on `main`, clean, and tracks
  `git@github.com:forgegod/hermes-wingstaff.git` as `origin`.
- The project is a pre-alpha Hermes plugin at version `0.1.0`.
- The current survey found 625 `Wingstaff`, 924 `wingstaff`, and one
  `WINGSTAFF` occurrence across 86 tracked text files.
- The name is embedded in behavior, not only prose:
  - package/distribution/import and executable names;
  - native Hermes CLI registration;
  - 12 agent-facing tool names and the toolset;
  - plugin-qualified skills;
  - constraint, activation, artifact, and handoff schema IDs;
  - Kanban card titles and idempotency keys;
  - profile-local data and worktree roots;
  - dashboard manifest, tab, asset, and API routes;
  - isolated compatibility probes and release workflow paths;
  - generated SVG/PNG metadata and geometry IDs.
- Two tracked implementation-plan filenames and the `wingstaff/` source
  directory contain the old name.
- `plugin.yaml` is already stale: it advertises obsolete `wingstaff_validate`
  and `wingstaff_modify` tools while the runtime registers
  `wingstaff_replace_constraints` and `wingstaff_record_skill_activation`.
  The rename must reconcile the manifest to the actual 12-tool runtime.
- Package, command, repository, and domain checks performed during preflight found:
  - no PyPI `daidala` project;
  - no local `daidala` executable;
  - `daidala.dev` is reserved for this project and RDAP resolves its registration;
  - `daidala.io` could not be reserved by the operator and is not required for
    the approved local cutover.
  Recheck software and repository namespaces immediately before publishing
  because availability can change independently of this repository.
- `https://github.com/forgegod/daidala` has now been created as an empty public
  repository. SSH read access is verified; it has no default branch or commits,
  and no source has been pushed.

## Scope and non-goals

### In scope

- One atomic public identity cutover with no legacy runtime surface.
- Source-directory and import-path rename using `git mv`.
- Public schema and persisted-identity rename.
- Fresh Daidala runtime state under the new plugin/data namespace.
- Updated generated branding and root README narrative.
- Repository and installation URL cutover.
- Complete tests, build, package inspection, isolated Hermes probes, and DOX
  reconciliation.

### Out of scope

- Building or deploying a landing page.
- Registering domains from an agent session; the operator must purchase them.
- Publishing to PyPI, tagging a release, pushing, or renaming the GitHub
  repository without separate explicit authorization.
- Migrating or importing old policy-ledger databases, artifacts, worktrees,
  Kanban cards, activation manifests, or constraint documents.
- Retaining a tombstone package or executable under the old distribution name.
- Changing the six-stage lifecycle, approval policy, pack semantics, or Hermes
  host boundary.

## Cutover policy and stop conditions

1. **Human approval gate:** stop after this plan until the user approves it.
2. **Name reservation gate:** before public repository metadata or release work,
   recheck and reserve at least one of `daidala.io` or `daidala.dev`. Prefer
   reserving both. Stop if neither is available and ask for a naming decision.
3. **Namespace gate:** recheck PyPI `daidala`, the ownership and empty state of
   `forgegod/daidala`, and the local command path immediately before
   implementation. Stop on a material software/AI collision or unexpected
   content in the destination repository.
4. **Active-workflow gate:** enumerate current workflows and worktrees in every
   profile where the plugin is enabled. Finish or explicitly cancel them before
   installing Daidala. Do not strand live cards behind removed tool and skill
   names.
5. **Fresh-state gate:** Daidala starts with `$HERMES_HOME/daidala`; it must not
   inspect, move, copy, or delete `$HERMES_HOME/wingstaff`. Old state remains
   inert for manual retention or later deletion.
6. **Dirty-tree gate:** implementation starts only from a clean target tree.
7. **Verification gate:** any missing skill, invalid structured output, stale
   old-name runtime reference, failed test, failed build, or failed live Hermes
   probe blocks completion.
8. **External-action gate:** repository rename, remote URL update, commit, push,
   tag, package publication, and domain registration each require explicit
   authorization.

## Proposed approach

Perform the rename as a sequence of independently reviewable phases while
keeping the repository buildable at each completed phase where practical. A
package-directory rename necessarily breaks imports between intermediate edits,
so source, imports, metadata, and focused tests belong in one phase. Do not use a
blind repository-wide replacement: each old-name occurrence must be classified
as product prose, executable contract, serialized identity, path, generated
asset, test fixture, or historical plan content.

At final closeout, convert this plan to current-state wording (“Daidala brand
cutover”) and remove its explicit old-brand tokens so the tracked repository can
pass the zero-old-name audit. Git history, not permanent compatibility prose,
will retain the prior identity.

## Phase 0 — Approval, reservation, and operational preflight

**Status: Done.** The user approved the default plan decisions and confirmed
`daidala.dev` is reserved for this project. RDAP resolves the registration;
PyPI, the local command path, and the empty `forgegod/daidala` repository remain
clear. No enabled Wingstaff installation, active Kanban task, policy ledger, or
owned worktree was found across the inspected Hermes profiles.

### Files

- `docs/plans/2026-07-13-daidala-brand-cutover.md`
- no runtime files

### Steps

1. Obtain explicit human approval for this plan.
2. Re-run:
   - PyPI JSON lookup for `daidala`;
   - exact GitHub repository/name searches;
   - `gh repo view forgegod/daidala` and confirm it remains empty;
   - `command -v daidala`;
   - RDAP and registrar checks for `daidala.io` and `daidala.dev`.
3. Have the operator reserve the selected domains before public announcement.
4. Inventory enabled installations, named boards, active cards, policy ledgers,
   and owned worktrees across affected Hermes profiles.
5. Finish or explicitly cancel every active workflow. Record only the fact that
   the gate passed; do not copy live workflow data into the repository.
6. Re-run `git status --short --branch` and confirm a clean tree.

### Gate

Proceed only when the plan is approved, the software namespace remains clear,
at least one landing-page domain is secured, no old-brand workflow is active,
and the Git tree is clean.

## Phase 1 — Rename the Python distribution, package, and plugin entry points

**Status: Done.** The distribution, package, directory and pip plugin entry
points, standalone and native commands, 12-tool registration inventory, imports,
CI paths, and wheel metadata use Daidala. The focused gate passed with 27 tests,
Ruff, build, Twine, and a wheel-member/entry-point audit; the full phase gate
passed with 228 tests. A fresh isolated Hermes directory load registered the
`daidala` plugin with 12 tools and no error.

### Files

- `wingstaff/` → `daidala/` via `git mv`
- root `__init__.py`
- `pyproject.toml`
- `plugin.yaml`
- `.github/workflows/release.yml`
- all Python imports in `dashboard/`, `scripts/`, and `tests/`
- `scripts/check_md_links.py`

### Steps

1. Rename the package directory with `git mv wingstaff daidala` so history is
   preserved.
2. Change project metadata to distribution `daidala`, version `0.2.0`, console
   script `daidala = "daidala.cli:main"`, Hermes entry point
   `daidala = "daidala"`, package discovery `daidala*`, and Daidala package data.
3. Update the root directory-plugin entry point to import `.daidala` or
   top-level `daidala` exactly as the current dual discovery paths require.
4. Register native command `hermes daidala`; provide no `hermes wingstaff`
   alias.
5. Rename all internal and external Python imports to `daidala.*`.
6. Change the plugin manifest name and description, then reconcile
   `provides_tools` to the exact 12 tools actually registered by
   `daidala.__init__.register`:
   - `daidala_pack_info`
   - `daidala_start`
   - `daidala_status`
   - `daidala_replace_constraints`
   - `daidala_approve`
   - `daidala_cancel`
   - `daidala_submit_artifact`
   - `daidala_prepare_implementation`
   - `daidala_capture_implementation`
   - `daidala_record_skill_activation`
   - `daidala_record_verification`
   - `daidala_deliver`
   Rename the matching schema names, handler-map keys, and toolset in this phase
   so the manifest and runtime cannot diverge at the checkpoint.
7. Rename CI temporary paths and executable invocations to `daidala`.
8. Replace the ignored build-metadata directory `wingstaff.egg-info` with
   `daidala.egg-info` in the Markdown checker.
9. Clean stale `build/`, `dist/`, and old `*.egg-info` output before testing so
   an obsolete package cannot survive into release inspection.

### Tests and gate

Run focused installation and registration tests after updating their assertions:

```bash
pytest tests/test_installation.py tests/test_plugin.py tests/test_cli.py
ruff check daidala dashboard scripts tests
python -m build
python -m twine check dist/*
```

Inspect the wheel and require `daidala/` resources, `daidala-*.dist-info`, the
`daidala = daidala` Hermes entry point, and no `wingstaff/` package members.

## Phase 2 — Rename every executable Hermes contract and serialized identity

**Status: Done.** Runtime schemas, bundled skill namespaces, Kanban identities,
ownership text, worker instructions, compatibility fixtures, and profile-local
data roots use Daidala exclusively. Regression coverage proves the old package,
executable, tool prefix, schema, and data root are absent or rejected. The
focused suite passed with 146 tests and the full phase gate passed with 230
tests, Ruff, both pack validators, build, Twine, and diff checks.

### Files

- `daidala/__init__.py`
- `daidala/schemas.py`
- `daidala/tools.py`
- `daidala/cli.py`
- `daidala/kanban.py`
- `daidala/service.py`
- `daidala/workflow.py`
- `daidala/state.py`
- `daidala/constraints.py`
- `daidala/execution.py`
- `daidala/locations.py`
- `daidala/packs/*.yaml`
- `daidala/skills/*/SKILL.md`
- affected tests and fixtures

### Steps

1. Complete the tool-name cutover in worker instructions, prompts, examples,
   and remaining tests. The 12 schemas, handler-map keys, toolset registration,
   manifest, and exact-inventory regression are Phase 1 prerequisites.
2. Rename plugin-qualified bundled skills to `daidala:orchestrate`,
   `daidala:setup`, and `daidala:aidlc-adapter`; update pack YAML references and
   all card-skill assertions. External skill names remain unchanged.
3. Rename serialized schema identities as one hard break:
   - `daidala.workflow-constraints/v1`
   - `daidala.workflow-constraints-artifact/v1`
   - `daidala.skill-activation/v1`
   - `daidala.handoff/v1`
4. Rename Kanban card-title prefixes, approval/cancellation text, metadata prose,
   and idempotency keys to `daidala:`. Do not accept old idempotency keys as
   equivalent.
5. Rename runtime ownership and error text to Daidala.
6. Change all runtime roots from `$HERMES_HOME/wingstaff` to
   `$HERMES_HOME/daidala`, including worktrees and policy-ledger construction.
   Keep the generic `policy-ledger.sqlite3`, `workflows/`, `worktrees/`, and
   artifact filenames unless they themselves expose the product name.
7. Ensure readers reject old schema IDs rather than silently accepting or
   rewriting them.
8. Update reusable policy-skill examples and compatibility fixtures to emit only
   the Daidala constraint schema.
9. Preserve the Phase 1 regression that enumerates the registered tools and
   manifest tools and requires exact equality.
10. Add tests proving old CLI names, tool names, skill namespaces, and schema IDs
    are absent or rejected; do not implement compatibility behavior merely to
    satisfy those tests.

### Tests and gate

```bash
pytest tests/test_tools.py tests/test_worker_contract.py tests/test_constraints.py \
  tests/test_workflow.py tests/test_kanban.py tests/test_execution.py
ruff check daidala tests
daidala packs validate addyosmani
daidala packs validate aidlc
```

Stop if any fixture still depends on the old runtime namespace.

## Phase 3 — Rename the dashboard and browser contract

### Files

- `dashboard/manifest.json`
- `dashboard/plugin_api.py`
- `dashboard/dist/index.js`
- `dashboard/dist/style.css`
- `daidala/dashboard_backend.py`
- `daidala/recommendations.py`
- `daidala/setup_wizard.py`
- `scripts/probe_hermes_dashboard_compatibility.py`
- dashboard tests

### Steps

1. Change manifest name/label and tab path to `daidala`, `Daidala`, and
   `/daidala`.
2. Change the mounted API namespace and all browser requests to
   `/api/plugins/daidala/...`.
3. Rename DOM IDs, CSS classes, storage keys, test fixture names, and diagnostic
   labels containing the old brand. Preserve generic workflow field names.
4. Update backend imports, health payload `plugin` identity, module docs, and
   error copy.
5. Update the compatibility probe to request Daidala manifest assets and API
   routes from an isolated profile.
6. Do not retain the old dashboard tab or API route as an alias.

### Tests and gate

```bash
pytest tests/test_dashboard_assets.py tests/test_dashboard_api.py \
  tests/test_recommendations.py tests/test_setup_wizard.py \
  tests/test_hermes_dashboard_compatibility_probe.py
```

Run browser verification against an isolated debug Chrome profile, checking the
Daidala tab at desktop and narrow widths and confirming no old-brand label or URL
appears.

## Phase 4 — Replace the brand assets and tell the name story

### Files

- `README.md`
- `assets/build_brand_assets.py`
- `assets/logo.svg`
- `assets/logo-mark.svg`
- `assets/logo-*.png`
- `assets/social-card.svg`
- `assets/social-card.png`
- `assets/README.md`
- `assets/AGENTS.md`

### Steps

1. Rewrite the opening README description around Daidala while preserving the
   accurate Hermes-native plugin boundary.
2. Insert the approved “Why Daidala” section from this plan after the opening
   description.
3. Replace the winged-staff-specific brand contract. Recommended mark: a compact
   crafted `D` built from a Greek-meander path whose ordered segments suggest
   staged work and whose open end suggests delivery. Avoid a generic gear,
   robot, factory silhouette, or literal labyrinth that implies confusion.
4. Keep the existing gold/amber palette and bundled Libre Baskerville font unless
   the visual review rejects them; they remain legible and are not tied to the
   former name.
5. Change generator constants, geometry IDs, accessible titles/descriptions,
   wordmark, social-card copy, and asset documentation to Daidala.
6. Generate all SVG and PNG assets from `assets/build_brand_assets.py`; never
   hand-edit generated outputs.
7. Review logo, mark, and social card visually at full size and small-icon size.
   Stop for human approval if the new mark is not clearly distinct from the old
   winged staff.

### Tests and gate

```bash
.venv/bin/python assets/build_brand_assets.py
sha256sum assets/logo.svg assets/logo-mark.svg assets/logo-*.png \
  assets/social-card.svg assets/social-card.png
.venv/bin/python assets/build_brand_assets.py
sha256sum assets/logo.svg assets/logo-mark.svg assets/logo-*.png \
  assets/social-card.svg assets/social-card.png
```

The two hash sets must match. Verify PNG dimensions and alpha, SVG accessible
text, README rendering, and the external etymology link.

## Phase 5 — Rename all documentation, DOX contracts, and plan paths

### Files

- root `AGENTS.md`
- `daidala/AGENTS.md`
- `dashboard/AGENTS.md`
- `docs/AGENTS.md`
- `tests/AGENTS.md`
- `scripts/AGENTS.md`
- `assets/AGENTS.md`
- `docs/*.md`
- `docs/plans/*.md`
- plan files whose filenames contain the old brand, renamed with `git mv`

### Steps

1. Update every current architecture, operator, security, integration, pack,
   workflow, constraint, and use-case document to Daidala terminology and exact
   executable commands.
2. Rename old-brand plan filenames with `git mv`; rewrite current contract and
   path references inside plans so they remain executable under Daidala.
3. Update all Child DOX Index rows, ownership tables, local contracts,
   cross-document bindings, verification commands, and package paths.
4. Remove the obsolete winged-staff brand requirement from `assets/AGENTS.md`
   and replace it with the approved Daidala mark contract.
5. Update installation examples to
   `hermes plugins install forgegod/daidala --enable`, native commands to
   `hermes daidala ...`, standalone commands to `daidala ...`, tools to
   `daidala_*`, and skills to `daidala:*`.
6. Rewrite support-version evidence as Daidala evidence only after the renamed
   probes pass. Do not claim that a probe passed merely because its old-brand
   predecessor passed.
7. Update this plan to current-state terminology and remove explicit old-brand
   tokens before final zero-name verification.
8. Do not add a migration-history section to the README or normal docs. The name
   story explains Daidala; Git history records the rename.

### Tests and gate

```bash
python scripts/check_md_links.py .
```

Manually verify that Mermaid diagrams still place Daidala inside the existing
Hermes process and that every command snippet matches the renamed schemas and
CLI parser.

## Phase 6 — Release, isolated-host, and zero-old-name verification

### Files

- `.github/workflows/release.yml`
- `scripts/probe_hermes_compatibility.py`
- `scripts/probe_hermes_dashboard_compatibility.py`
- `scripts/check_release_contents.py`
- release and compatibility tests
- generated `dist/` artifacts, not committed

### Steps

1. Delete stale build output and rebuild from a clean output directory.
2. Run the full project verification with renamed commands:

```bash
lefthook validate
pytest
ruff check .
daidala packs validate addyosmani
daidala packs validate aidlc
python scripts/check_md_links.py .
python scripts/check_release_contents.py .
python -m build
python -m twine check dist/*
python scripts/check_release_contents.py . --wheel dist/*.whl
```

3. Run both isolated live-host probes against the pinned supported Hermes
   revision:

```bash
python scripts/probe_hermes_compatibility.py
python scripts/probe_hermes_dashboard_compatibility.py
```

4. Install the wheel into a fresh temporary virtual environment and verify:

```bash
python -m venv /tmp/daidala-release
/tmp/daidala-release/bin/pip install dist/*.whl
/tmp/daidala-release/bin/daidala packs validate addyosmani
/tmp/daidala-release/bin/daidala packs validate aidlc
```

5. Inspect the wheel and source tree for stale package members, metadata, tools,
   skill namespaces, URLs, schema IDs, generated titles, cache files, and old
   build output.
6. Run an exact case-sensitive and case-insensitive old-name search over tracked
   filenames and decodable tracked file content. Acceptance is zero hits after
   this plan has been converted to current-state wording.
7. Run `git diff --check`, inspect `git diff --stat`, and verify every rename is
   intentional. Generated asset changes are expected to make this more than a
   symmetric textual replacement.
8. Perform the final DOX pass across every changed path and confirm all child
   indexes, ownership, commands, and verification sections describe Daidala.

### Gate

The cutover is complete only when all verification passes, the built wheel and
fresh install expose only Daidala surfaces, the live Hermes probes pass, and the
tracked repository contains zero old-brand names or paths.

## Phase 7 — Populate the Daidala repository

Creating the empty public destination repository is complete. Changing remotes,
pushing source, repository metadata changes, tags, and publication remain
external side effects and require separate explicit approval.

### Steps

1. Confirm `forgegod/daidala` is still empty and owned by `forgegod` immediately
   before the first push.
2. Preserve the current repository as a temporary `legacy` remote, add
   `git@github.com:forgegod/daidala.git` as the new `origin`, and verify SSH
   access to both. Do not alter the old repository during this step.
3. With explicit push authorization, push the fully verified renamed `main`
   branch to `forgegod/daidala`; verify the new default branch and remote HEAD.
4. Update the new repository description, topics, social preview, and website URL to the
   chosen Daidala domain.
5. Re-run the public Git installation probe using
   `forgegod/daidala` from a fresh isolated `HERMES_HOME`.
6. Only with explicit publication authorization, tag and publish version `0.2.0`
   and verify the installed plugin registers the Daidala command, tools, skills,
   dashboard, and fresh data root.
7. Do not publish or update an old-name package as a redirect/tombstone unless
   the user reverses the no-compatibility decision.
8. Archive or otherwise change the old GitHub repository only under a separate
   explicit instruction; the Daidala cutover must not silently mutate it.

### Gate

Verify the public clone/install URL, repository metadata, selected domain, and
fresh Hermes installation before announcing the rename.

## Files likely to change

The exact list is the set of tracked files containing the old name plus paths
whose package directory changes. The principal groups are:

- `pyproject.toml`, `plugin.yaml`, root `__init__.py`, release workflow;
- package directory and all Python modules, packs, and bundled skills;
- dashboard manifest, backend, browser assets, and dashboard probes;
- all tests and fixtures that import the package or assert public identities;
- root README, all numbered docs, implementation plans, and every applicable
  `AGENTS.md`;
- deterministic brand generator and all generated logo/social assets.

Do not touch unrelated dependency versions, workflow semantics, pack mappings,
or host compatibility constraints.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Existing workflows call removed tools or skills | Active-workflow gate; finish or cancel before cutover; no migration promise. |
| Old profile data is accidentally interpreted as Daidala state | New data root and schema IDs; no scanning or fallback to the old root. |
| Mechanical replacement changes unrelated prose or third-party attribution | Classify occurrences by surface; preserve external project names and licensed text unless they refer to this package. |
| Manifest and runtime tool inventory drift again | Exact manifest-versus-registration regression test. |
| Old package files survive in `dist/` | Delete build output and old egg-info before every package gate; inspect wheel members. |
| Dashboard uses mixed old/new routes | Manifest/API/browser change in one phase plus isolated dashboard probe. |
| GitHub rename breaks installation docs | Rename remote only after local release passes; repeat the public Git install probe. |
| New mark keeps the obsolete winged-staff story | Replace the mark contract and require deterministic render plus human visual approval. |
| README overstates Greek etymology | Use one sourced, restrained paragraph and avoid claims beyond “crafted or fashioned works.” |
| Domain or package name is taken mid-cutover | Recheck immediately before implementation/publication and stop on collision. |

## Acceptance criteria

- Product, package, command, plugin, tool, toolset, skill, schema, runtime,
  dashboard, repository, documentation, and generated asset identities are all
  Daidala.
- `README.md` contains the approved pronunciation and name story and still leads
  with the Hermes-native, approval-gated product boundary.
- No compatibility alias or data migration exists.
- No active workflow was abandoned during cutover.
- The plugin manifest exactly matches the 12 registered Daidala tools.
- A clean wheel contains only the `daidala` package and Daidala entry points.
- Both bundled packs validate through the `daidala` executable.
- Unit, integration, documentation, package, release-content, and isolated Hermes
  compatibility checks pass.
- Tracked paths and decodable tracked content contain zero old-brand references.
- DOX ownership and verification commands are current.
- External repository/domain/publication actions are either verified complete or
  explicitly left pending because authorization was not granted.

## Open decisions

Only two decisions remain for the approval gate:

1. Confirm the recommended crafted-meander `D` mark, or select a different
   Daidala visual direction before Phase 4.
2. Confirm whether external Phase 7 should be executed in the same approved work
   session or stopped after the fully verified local cutover.

Default if the user approves without amendments: use the crafted-meander `D`,
complete Phases 1–6 locally, and stop before every Phase 7 external side effect.
