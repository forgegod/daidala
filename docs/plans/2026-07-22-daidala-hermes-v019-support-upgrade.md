# Hermes v0.19 support upgrade plan

Produce a reviewed Daidala checkpoint and release gate that support both exact
Hermes v0.18.2 and v0.19.0 hosts, widen both bundled pack constraints to
`>=0.18.2,<0.20.0` only after the complete compatibility matrix passes, and
retain reproducible evidence without changing the active Hermes runtime.

**Status:** in progress — Phases 0 through 2 are complete locally; Phase 2 awaits
its documentation checkpoint. Push, merge, active-runtime change, and
publication remain separately gated.

## Current state

- Hermes Agent v0.19.0 is an official signed release: tag `v2026.7.20`, build
  `2026.7.20`, tag object `c7d08de287556b3d339df336b180a39d4980ebd7`, and
  source commit `3ef6bbd201263d354fd83ec55b3c306ded2eb72a`. Its package requires
  Python `>=3.11,<3.14`. Sources:
  [release](https://github.com/NousResearch/hermes-agent/releases/tag/v2026.7.20),
  [plugin API](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins/),
  [CLI](https://hermes-agent.nousresearch.com/docs/reference/cli-commands), and
  [Kanban](https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban).
- The completed Phase 6 evaluation already ran the same Daidala wheel twice on
  exact Hermes v0.18.2 and v0.19.0. Version, policy-skill, public Kanban,
  worker-context, entry-point plugin, directory plugin, native/standalone pack,
  dashboard-fixture, `init`, cleanup, and controller-isolation probes passed
  (`docs/plans/2026-07-22-daidala-phase-6-hermes-v019-evaluation.md:238-246`).
- Comparison `5482aeb4…` was `incomparable`, not incompatible. `TC-F04-01` lacked
  actual setup/admission preview and literal-confirmation evidence;
  `TC-F11-01` lost the exact evaluated wheel before release-content inspection;
  `TC-F14-01` was blocked by those two gaps
  (`docs/evaluation-results/v1/daidala-self-improvement.md:200-209`).
- Both packs still declare `>=0.18.2,<0.19.0` in
  `daidala/packs/addyosmani.yaml` and `daidala/packs/aidlc.yaml`.
  `scripts/probe_hermes_compatibility.py` defaults to v0.18.2 build
  `2026.7.7.2`, upstream `4281151a`; explicit three-field host overrides are
  already supported by all three compatibility probes.
- `.github/workflows/release.yml` now transfers the package job's exact checked
  distribution into the release-only compatibility job, rejects ambiguous wheel
  selection, records its SHA-256, and runs the support matrix without an editable
  Daidala install. The v0.18.2 host pin remains unchanged; the second supported
  host is still reserved for Phase 4 after the Phase 2 verdict.
- Phase 2 produced a `compatible` verdict for exact Hermes v0.18.2 and v0.19.0
  using one Daidala wheel at source checkpoint `98254ea…`, SHA-256 `ea0ee80b…`.
  Both four-probe repetitions per host are byte-identical; both loaders report
  exact 12-tool and three-skill inventory; setup/admission, exact-wheel, cleanup,
  and normalized active-runtime isolation gates pass.
- The plugin and dashboard probes now exercise packaged native/standalone
  admission parity, the packaged manifest/assets/router, normalized setup
  preview, literal confirmation rejection, and mutation-free state. The matrix
  preflights one exact wheel and runs all three probes twice per explicit host.
- Branch `feat/hermes-v019-support` contains the Phase 0 checkpoint and the
  reviewed Phase 1 working batch. Any future push still requires its own exact
  outgoing-range approval.
- The active Hermes installation changed independently before this plan began.
  It now reports v0.19.0 build `2026.7.20` at
  `de5ece994415276d215976836161f871f1d6d8f5`, with local `main` equal to its
  tracking ref and the pre-existing untracked `tinker-atropos/` path. The sticky
  profile remains `hermes-vc`; the exact release candidate under test remains
  the distinct source commit `3ef6bbd201263d354fd83ec55b3c306ded2eb72a`.
- The installed controller checkout remains clean and detached at
  `3ce1bfc15c5102d75d54e846ea6ddb8520b6eed8`, the gateway service is running,
  reconciliation cron `1847b1b1e14b` remains paused, and `SI-ACTIVE-CYCLE`
  passes with no board, admission, worktree, evaluator, or claim owner.
  However, Daidala is absent from the controller profile's `plugins.enabled`
  list after the host update. Native `hermes ... daidala` is unavailable and
  standalone live diagnosis is blocked on `SI-PROFILE`, `SI-REPOSITORY`,
  `SI-PACKS`, and `SI-EVALUATOR`; the repository blocker is this untracked plan.
  Phase 7 ranges restoration before any reconciliation resume or new cycle.
- The persistent controller and active operator profiles remain snapshot-only
  during support evaluation. The bounded Phase 0 snapshot is mode `0600` at
  `/tmp/daidala-hermes-v019-phase0-active-snapshot.json`, 4,218 bytes, SHA-256
  `ac8ec4ddc459f1054a5340782123eb65a9fcef372ecfca0d2dafa46e285d1344`.

## Risk call-out

The support declaration is executable policy: widening the pack constraints or
release pin before closing the two evidence gaps would turn an `incomparable`
result into an unsupported compatibility claim. Keep the existing range and
v0.18.2 release pin until Phase 2 produces a complete `compatible` verdict.

All host execution must use detached temporary Hermes checkouts, separate
Python 3.11 virtual environments, fresh `HERMES_HOME` roots, and the same
content-addressed Daidala wheel. Verify that wheel with Twine and
`check_release_contents.py` before any evaluator cleanup. Snapshot the active
Hermes checkout, controller revision, gateway, cron, repository, and active
cycle before and after the matrix; any drift stops the plan.

Remote operations are a separate risk. Local and remote `main` are synchronized
at Phase 0, but Phase 6 may not push or open a pull request until the operator
approves the then-current exact outgoing commit range. Merge, public-Git
installation, tag, release, and publication each remain separately gated.

## Phase table

| # | Phase | Status | Verification gate |
|---|---|---|---|
| 0 | Freeze the release and execution contract | done (operator-approved plan `a03d4e7f…`; local plan-only checkpoint) | Exact v0.19 tag/build/source, baseline source, Daidala checkpoint, active-state snapshot, outgoing Git range, and plan digest are recorded; the operator explicitly approves the plan and branch creation. |
| 1 | Close the probe and exact-wheel evidence gaps | done (`63dd099e…` wheel; `c4fc1792…` baseline matrix evidence) | Focused probe/workflow tests pass; actual packaged setup and admission previews are mutation-free; unconfirmed setup is rejected; the exact wheel is inspected before cleanup. |
| 2 | Execute the two-host compatibility matrix | done (`c202459b…` matrix; `f09febde…` isolation) | Repeated v0.18.2 and v0.19.0 legs use one verified wheel, all required rows pass, retained evidence reproduces, temporary roots are gone, and active runtime projections are identical. |
| 3 | Remediate deterministic host incompatibilities | pending | Every candidate failure is fixed without weakening v0.18.2, approval, isolation, or evidence contracts; focused and complete gates pass, or the plan stops with support unchanged. |
| 4 | Widen support policy and make CI enforce it | pending | Both packs accept 0.18.2 and 0.19.0 but reject 0.20.0; release CI pins and probes both exact hosts with one verified wheel; current docs agree. |
| 5 | Run the complete local release gate and checkpoint | pending | Repository, docs, test, lint, pack, build, Twine, wheel-content, and fresh-wheel smoke gates exit 0; reviewed commits are clean; no runtime or remote mutation occurred. |
| 6 | Verify remote CI and public Git installation | pending | Separately approved push/merge scope, exact-SHA two-host CI, and a post-merge isolated v0.19 public-Git install all pass before any tag or release. |
| 7 | Restore and harden active controller operations | pending — deferred; enter only before reconciliation resumes or a new cycle is admitted, with separate runtime approval | The exact detached controller is enabled and healthy on the then-current host; native and standalone diagnosis pass 11/11; restricted-container availability is restored; startup delivery and non-loopback API exposure are reviewed; cron remains paused and no cycle is admitted. |

Mark a phase `in-progress` while running it, `done (<sha-or-evidence>)` only
after its gate passes, and leave it `pending` otherwise.

## Phase 0 — Freeze the release and execution contract

**Goal:** Bind one immutable implementation scope and obtain the mandatory human
approval before creating a feature branch or changing support behavior.

Steps:

1. Re-read the root, `daidala/`, `scripts/`, `tests/`, `dashboard/`, `docs/`, and
   `docs/evaluation-results/` DOX chains.
2. Require this plan to be the only working-tree change and record:
   - `git status --short --branch`;
   - `git rev-parse HEAD main origin/main`;
   - `git rev-list --left-right --count origin/main...main`;
   - the exact commits that a future feature-branch push would publish.
3. Re-resolve official Hermes tag `v2026.7.20`; require tag object
   `c7d08de287556b3d339df336b180a39d4980ebd7`, peeled source
   `3ef6bbd201263d354fd83ec55b3c306ded2eb72a`, version `0.19.0`, build
   `2026.7.20`, and Python `>=3.11,<3.14`.
4. Retain exact baseline Hermes v0.18.2 build `2026.7.7.2`, source
   `4281151ae859241351ba14d8c7682dc67ff4c126`; widening support preserves the
   already-supported baseline rather than silently dropping it.
5. Snapshot only bounded, non-secret identities for the active Hermes checkout,
   active Daidala checkout, installed controller, gateway, reconciliation cron,
   and active-cycle/worktree state. Do not read credential values or untracked
   active-runtime content.
6. Review this plan, compute its SHA-256, and obtain explicit operator approval
   for the exact plan digest, v0.19 source commit, proposed range
   `>=0.18.2,<0.20.0`, branch name `feat/hermes-v019-support`, local
   branch/commit work, and the recorded degraded-but-snapshot-only controller
   state. Phase 0 approval does not authorize repairing or changing the active
   runtime. Any later outgoing range still requires separate Phase 6 approval.
7. After approval, create `feat/hermes-v019-support` from the approved `main`
   checkpoint, commit only this plan, and require the branch to be clean. Do
   not push it.

Observed pre-approval evidence: official tag `v2026.7.20` resolves to annotated
object `c7d08de287556b3d339df336b180a39d4980ebd7` and peeled source
`3ef6bbd201263d354fd83ec55b3c306ded2eb72a`; that source declares version
`0.19.0`, build `2026.7.20`, and Python `>=3.11,<3.14`. Baseline source
`4281151ae859241351ba14d8c7682dc67ff4c126` exists in the official repository
and declares version `0.18.2`, build `2026.7.7.2`, and the same Python bound.
The Daidala checkpoint and both `main` refs are `c091ec4…`, divergence is `0/0`,
and the active-state snapshot identity is recorded above. No branch, commit,
candidate checkout, evaluator, profile mutation, push, or runtime change has
occurred.

Observed gate: on 2026-07-23 the operator explicitly approved plan SHA-256
`a03d4e7f33644a1ab0b074479d896f60b381d1db1f340afc0e5b4e5fa2c15cfb`,
candidate source `3ef6bbd201263d354fd83ec55b3c306ded2eb72a`, proposed range
`>=0.18.2,<0.20.0`, branch `feat/hermes-v019-support`, the local plan-only
checkpoint, and the recorded degraded-but-snapshot-only controller state. The
approval authorizes implementation under this phase sequence but no push,
merge, active-runtime repair, tag, release, or publication.

Verification gate: all identities and snapshots are exact; the approved plan
checkpoint contains no implementation; the operator approval binds the full
plan digest and branch scope; no host clone, evaluator, branch, or source change
predates that approval.

Suggested checkpoint: `docs(plan): approve Hermes v0.19 support upgrade`.

## Phase 1 — Close the probe and exact-wheel evidence gaps

**Goal:** Turn the two prior evidence blockers into deterministic regressions
without changing the supported range yet.

Steps:

1. Extend `scripts/probe_hermes_plugin_compatibility.py` so an isolated packaged
   Daidala installation exercises both standalone and native
   `project-cycle admit` dry runs against the same bounded fixture:
   - a clean temporary Git repository with committed `.daidala/project.yaml`;
   - a strict profile-local registration and credential-alias fixture containing
     no secrets;
   - fake, bounded `gh` and attended-delivery command boundaries;
   - one structured maintainer-ready issue;
   - exact pack, constraints, baseline, stage-profile, cycle, and intake digest
     comparison;
   - byte-identical registration, issue, ledger, Kanban, and artifact state
     before and after both previews.
   Native and standalone JSON plus exit codes must match. No `--apply` path is
   exercised here.
2. Replace the support-decision path in
   `scripts/probe_hermes_dashboard_compatibility.py` with the actual packaged
   Daidala dashboard manifest, assets, and router. A minimal synthetic plugin may
   remain only as a narrow Hermes-SDK fixture test, not as support evidence.
3. Through the host-mounted Daidala router, exercise `/wizard/preview` with an
   exact setup request, then call `/wizard/start` without literal
   `confirm: true`. Require the preview to report `confirmed: false`, require the
   unconfirmed request to fail, and prove that no policy ledger or Kanban graph
   was created. Do not exercise confirmed setup in this compatibility phase.
4. Add the exact-wheel orchestration boundary
   `scripts/run_hermes_support_matrix.py`, which:
   - accepts one existing Daidala wheel path and complete expected-host tuples;
   - records the wheel SHA-256 before installation;
   - runs `python -m twine check <wheel>` and
     `python scripts/check_release_contents.py . --wheel <wheel>` on those exact
     bytes before cleanup;
   - installs that same path into each isolated host environment;
   - runs every approved probe twice per host and emits one bounded canonical
     JSON result;
   - removes temporary hosts/homes only after evidence and artifact checks are
     complete; and
   - never reads or writes the active `HERMES_HOME`.
   Keep it dependency-free apart from repository development tools.
5. Update focused tests in:
   - `tests/test_hermes_compatibility_probe.py`;
   - `tests/test_hermes_plugin_compatibility_probe.py`;
   - `tests/test_hermes_dashboard_compatibility_probe.py`;
   - new `tests/test_hermes_support_matrix.py`; and
   - `tests/test_release_workflow.py` for exact-wheel ordering.
   Cover partial host identities, wrong wheel digest, content-check failure,
   preview mutation, native/standalone mismatch, missing literal confirmation,
   cleanup on failure, and roots nested inside active `HERMES_HOME`.
6. Update `scripts/AGENTS.md` and `tests/AGENTS.md` with the durable probe and
   exact-wheel contracts. Do not edit pack ranges, support docs, default probe
   identity, or the release host pin in this phase.
7. Run:

   ```bash
   pytest -q tests/test_hermes_compatibility_probe.py \
     tests/test_hermes_plugin_compatibility_probe.py \
     tests/test_hermes_dashboard_compatibility_probe.py \
     tests/test_hermes_support_matrix.py tests/test_release_workflow.py
   ruff check scripts tests
   python scripts/check_md_links.py .
   git diff --check
   ```

Verification gate: the focused commands exit 0; the actual packaged dashboard
and native/standalone admission previews are mutation-free; missing confirmation
fails; one exact wheel is hashed and content-checked before cleanup; support
still remains `>=0.18.2,<0.19.0`.

Observed gate on 2026-07-23: the focused probe, matrix, workflow, and dashboard
tests, Ruff, Markdown-link check, and diff check exit 0. One source-built wheel
passed Twine and release-content inspection at SHA-256
`63dd099e67c5b0370c50af7d4cba5c3083001cb8c36035bb22d66f41e42cd639`.
An isolated Python 3.11 host at exact Hermes v0.18.2 build `2026.7.7.2`, pinned
tracking identity `4281151a`, ran all three probes twice successfully. Its
7,583-byte mode-`0600` canonical evidence has SHA-256
`c4fc179283ea1eea9056bd96272e9500deb92e94c7a866dee16adfe674a72d0c`.
The matrix rejected an initial Python 3.14 host, exposed and fixed virtualenv
symlink resolution, required an independent clone to bind Hermes' tracking-ref
identity, and verified normalized setup-preview bytes. Temporary host, wheel,
and matrix roots were removed after inspection. This baseline-only integration
proves the Phase 1 boundary; it does not start the two-host Phase 2 evaluation.

Suggested checkpoint: `test(compat): close Hermes support evidence gaps`.

## Phase 2 — Execute the two-host compatibility matrix

**Goal:** Produce a reproducible verdict for the same Daidala wheel on exact
Hermes v0.18.2 and v0.19.0 without touching active state.

Steps:

1. Start only from the clean Phase 1 checkpoint. Snapshot the bounded active
   identities from Phase 0 again and stop on drift, an active cycle, an owned
   worktree, a running reconciliation job, or a dirty registered checkout.
2. Build Daidala once under Python 3.11. Record the source commit, wheel path,
   SHA-256, Twine result, and release-content result before creating or deleting
   evaluator roots.
3. Create separate detached Hermes clones, virtual environments, dashboards,
   ports, and `HERMES_HOME` roots for:
   - v0.18.2 / `2026.7.7.2` /
     `4281151ae859241351ba14d8c7682dc67ff4c126`; and
   - v0.19.0 / `2026.7.20` /
     `3ef6bbd201263d354fd83ec55b3c306ded2eb72a`.
   Pin each clone's local tracking ref to its evaluated commit, replace `origin`
   with an unavailable local URL, use Python 3.11 and Node 22, and build the
   host dashboard distribution.
4. Install the same Daidala wheel bytes into both hosts. Run each leg twice from
   a second fresh home. Required support boundaries are:
   - exact host version/build/upstream identity;
   - policy-skill inventory and content digest;
   - public named-board create/show/comment/link/complete/archive behavior and
     8,192/8,300 worker-context boundary;
   - entry-point and directory plugin discovery with no plugin error, exact 12
     tools, exact three bundled skills, and both pack validations;
   - native/standalone command JSON and exit-code parity;
   - actual packaged dashboard manifest/assets/router/auth boundary;
   - mutation-free setup preview plus rejected unconfirmed start;
   - mutation-free native/standalone project-cycle admission preview;
   - exact-wheel Twine and release-content verification; and
   - evaluator cleanup and active-controller isolation.
5. Treat any repeated-output mismatch, incomplete cleanup, changed active
   snapshot, missing exact wheel, or required boundary without evidence as
   `incomparable`. Treat an observed contract mismatch as `incompatible`. Do not
   retry with adjusted fixtures until the result passes.
6. Retain the canonical bounded matrix input and result mode `0600` under the
   controller project's evidence directory. Update
   `docs/evaluation-results/v1/daidala-self-improvement.md` with redacted exact
   identities, digests, commands, row statuses, and verdict. Do not retain temp
   homes, credentials, issue bodies, private destinations, or unbounded logs.
7. Remove evaluator roots, rerun the active-state snapshot, and require it to be
   byte-identical. Keep reconciliation paused.

Result: source checkpoint `98254eac06579b67d8e71581542a3090d7b387fd`
produced exact wheel SHA-256 `ea0ee80b8cf0a934a5d8741ee6a56f291d55b91f655b7371ade901412e0c5053`.
Both repetitions of all four probes pass byte-identically on both exact hosts.
Fresh-process inventory confirms exact 12 tools and three bundled skills.
Canonical input `6957614a…`, matrix result `c202459b…`, inventory `e7c227b1…`,
and isolation result `f09febde…` are retained mode `0600`. The evaluator root,
matrix roots, and diagnostic files are removed; entry-point metadata is restored
and both ports are closed. Raw snapshots differ only at `SI-REPOSITORY` and its
derived `SI-REGISTRATION` aggregate because the repository became clean after
checkpointing. The projection retaining every runtime-owned check is
byte-identical at `7d4f42d2…`. The verdict is `compatible`; no deterministic
candidate remediation is required.
Full pytest, Ruff, Lefthook, both pack validators, the 46-file Markdown link
check, and diff hygiene pass at closeout.

Verification gate: both repetitions for both hosts use one verified wheel and
agree byte-for-byte; `TC-F03-01`, `TC-F03-02`, `TC-F04-01`, `TC-F11-01`,
`TC-F14-01`, and `TC-F15-01` pass; no required support row is blocked or
incomparable; the verdict is `compatible`; cleanup and active-state identity
checks pass.

Stop condition: if the verdict is not `compatible`, do not enter Phase 4. Enter
Phase 3 only for deterministic, locally remediable failures already inside this
plan's boundaries; otherwise stop with the old support range.

Suggested checkpoint: `docs(evaluation): verify Hermes v0.19 compatibility`.

## Phase 3 — Remediate deterministic host incompatibilities

**Goal:** Correct any v0.19 host-boundary failure without weakening v0.18.2 or
expanding the approved scope silently.

Steps:

1. If Phase 2 has no deterministic candidate failure, record this phase as
   `done (no remediation required)` and create no source-only commit.
2. For every deterministic failure, name the expected contract, observed v0.19
   behavior, affected source and tests, and why it is a Daidala defect rather
   than missing evidence. Add a failing regression before changing production
   code.
3. Limit changes to the proven boundary. Likely surfaces are:
   - `daidala/__init__.py` and `plugin.yaml` for registration inventory;
   - `daidala/cli.py` for native callback/exit-code parity;
   - `daidala/kanban.py` for documented public Kanban JSON/command drift;
   - `dashboard/manifest.json`, `dashboard/plugin_api.py`, or `dashboard/dist/`
     for documented dashboard SDK drift; and
   - compatibility probes/tests for evidence parsing, never for accepting a
     failing runtime result.
4. Do not remove the v0.18.2 `SystemExit` compatibility behavior, loosen exact
   tool/skill counts, bypass plugin errors, reduce approval requirements, write
   Hermes SQLite directly, or add Hermes as a Python dependency merely to make
   v0.19 green.
5. If a fix changes a public or durable Daidala contract, update the nearest
   owning AGENTS.md and normal documentation in the same checkpoint.
6. Run the focused regression, all adjacent tests, both pack validators, and the
   complete repository gate. Then rerun Phase 2 from a newly built exact wheel;
   prior evidence cannot approve changed source.
7. If remediation requires undocumented Hermes internals, active-profile
   mutation, credentialed model routes, or a contract expansion outside this
   plan, stop and amend/reapprove the plan instead of improvising.

Verification gate: every candidate failure has a regression and narrow fix;
v0.18.2 and v0.19.0 matrix legs both pass from the same rebuilt wheel; complete
verification passes; approval, isolation, and host-public-API contracts remain
intact.

Suggested checkpoints: one semantic `fix(compat): …` commit per independent
host-boundary failure, followed by refreshed evaluation evidence in a separate
`docs(evaluation): …` commit.

## Phase 4 — Widen support policy and make CI enforce it

**Goal:** Change the support declaration only after the compatible two-host
verdict exists, and prevent future releases from dropping either host silently.

Steps:

1. Change `hermes_version_constraint` in
   `daidala/packs/addyosmani.yaml` and `daidala/packs/aidlc.yaml` to
   `>=0.18.2,<0.20.0`.
2. Update `tests/test_skill_installation.py` and adjacent pack tests to prove:
   - `0.18.1` is rejected;
   - `0.18.2` and a later `0.18.x` are accepted;
   - `0.19.0` and a later `0.19.x` are accepted; and
   - `0.20.0` is rejected.
   Keep exact bounded semantics; do not replace the constraint with an
   unbounded minimum.
3. Make v0.19.0 the default last-known-good identity in
   `scripts/probe_hermes_compatibility.py`, while retaining complete explicit
   host overrides so v0.18.2 remains testable. Update all three probe test files.
4. Change `.github/workflows/release.yml` and
   `tests/test_release_workflow.py` so the release-only compatibility job:
   - uses a two-row exact host matrix for the v0.18.2 and v0.19.0 identities;
   - builds or downloads one exact Daidala wheel, records its digest, verifies
     those exact bytes, and installs that wheel rather than `pip install -e .`;
   - runs core, packaged-plugin, directory-plugin, actual dashboard/setup, and
     admission-preview probes with complete expected-host arguments;
   - pins each Hermes checkout/tracking ref and disables update fetches; and
   - fails if either host row, cleanup, or artifact verification fails.
5. Update current support documentation:
   - `README.md`;
   - `docs/README.md`;
   - `docs/03-pack-reference.md`;
   - `docs/08-hermes-integration.md`;
   - `docs/15-self-improvement.md`; and
   - `docs/evaluation-results/v1/daidala-self-improvement.md`.
   State v0.18.2 and v0.19.0 as supported exact hosts within the bounded range,
   distinguish current active-controller identity from supported-host policy,
   cite the new comparison, and remove the superseded blocker claim from current
   docs. Preserve the completed Phase 6 plan as historical observed evidence;
   this plan supersedes its support conclusion rather than rewriting its run.
6. Keep `docs/16-self-improvement-setup.md` factual: if the active controller
   still runs v0.18.2, retain that observed operational identity and add only the
   new supported-host policy where needed. Do not claim the active runtime was
   upgraded.
7. Do not add Hermes to `pyproject.toml` dependencies. It remains the separately
   installed plugin host.
8. Run focused pack, probe, release-workflow, docs-link, and diff checks.

Verification gate: both pack validators report the widened exact range; tests
accept the two supported minor lines and reject 0.20.0; CI structurally pins and
runs both host commits against one exact wheel; all normal docs agree with the
new evidence and do not claim an active-runtime upgrade.

Suggested checkpoint: `feat(compat): support Hermes v0.19` followed by
`docs(compat): document Hermes v0.19 support` if the reviewed diff separates
policy/CI from documentation cleanly.

## Phase 5 — Run the complete local release gate and checkpoint

**Goal:** Produce a clean, reviewable local support-upgrade checkpoint before any
remote operation.

Steps:

1. Perform the required DOX pass across every changed path. Update child indexes
   only if structure or ownership changed; do not add diary entries.
2. Run the complete repository and release gate:

   ```bash
   lefthook validate
   pytest
   ruff check .
   daidala packs validate addyosmani
   daidala packs validate aidlc
   python scripts/check_md_links.py .
   python -m build
   python -m twine check dist/*
   python scripts/check_release_contents.py . --wheel dist/*.whl
   git diff --check
   ```

3. Install the exact final wheel into a fresh Python 3.11 venv. Verify the
   module-valued Hermes plugin entry point, standalone CLI, both pack
   validations, manifest, dashboard assets, all 12 tools, and all three bundled
   skills without using the active profile.
4. Re-run the Phase 2 matrix against the final committed source if any byte in
   probes, runtime, packs, dashboard, packaging, or support policy changed after
   its compatible verdict.
5. Review staged scope by semantic seam: probe/evaluator contract, any narrow
   runtime remediation, support policy/CI, current docs/evidence, and plan
   closeout. Use the repository-local identity
   `hephaistos <hephaistos@grewety.com>` and the commit-message skill for every
   commit.
6. Verify:

   ```bash
   git status --short --branch
   git log --format='%h %s%nAuthor: %an <%ae>%nCommit: %cn <%ce>' -6
   git diff main...HEAD --check
   ```

7. Update this phase table with exact commits, test counts, wheel digest, matrix
   digest, and clean-state evidence. Do not push.

Verification gate: all commands exit 0, the final wheel smoke and repeated
matrix pass, commits match the approved semantic seams and author identity, the
branch is clean, and active plus remote state remain unchanged.

Suggested checkpoint: `docs(plan): complete Hermes v0.19 support gate`.

## Phase 6 — Verify remote CI and public Git installation

**Goal:** Prove the release transport on exact remote commits without tagging or
publishing a release.

Steps:

1. Display the exact outgoing range and obtain separate operator approval to
   push `feat/hermes-v019-support`. Phase 0 began with local and remote `main`
   synchronized, but approval must cover every commit the feature branch makes
   reachable at push time. A prior local-implementation approval does not
   authorize this push.
2. Push only the feature branch, open a pull request to `main`, and record the
   exact remote head SHA. Do not merge.
3. Manually dispatch the release workflow on that exact feature-branch SHA.
   Require both v0.18.2 and v0.19.0 compatibility matrix jobs, ordinary test
   jobs, packaging, wheel-content inspection, and fresh-wheel smoke to pass.
4. Review the pull request and exact CI evidence. Obtain separate operator
   approval before merge. Do not infer merge approval from push or CI approval.
5. After approved merge and before any tag, create a fresh isolated v0.19.0
   `HERMES_HOME` and run the documented public transport:

   ```bash
   hermes plugins install forgegod/daidala --enable
   ```

   In a fresh process require plugin enabled with no error, exact 12 tools,
   exact three bundled skills, native `hermes daidala`, both pack validations,
   dashboard manifest/router discovery, setup preview, and no unexpected
   profile files. Record the exact Daidala remote commit and Hermes host identity.
6. If public installation fails, do not tag or release. Open a bounded
   remediation branch and restore truthful support documentation before any
   publication.
7. Record remote CI and public-install evidence in this plan and current
   integration documentation. Delete the feature branch only after the merged
   commit and evidence are recoverable.

Verification gate: exact-SHA CI passes both host rows; the separately approved
merge is on remote `main`; a fresh v0.19 public-Git installation exposes the
complete Daidala surface without errors; no tag, GitHub release, TestPyPI/PyPI
publication, active-controller upgrade, or reconciliation resume occurred.

## Phase 7 — Restore and harden active controller operations

**Goal:** Repair the operational state that drifted during the independent
Hermes host update, without coupling controller mutation to the compatibility
claim.

Entry condition: enter only after separate operator approval and only before
reconciliation resumes or a new cycle is admitted. This phase is not required
to declare support for the isolated v0.18.2/v0.19.0 host matrix.

Steps:

1. Re-snapshot the active Hermes checkout, controller revision, profile plugin
   allow-list, gateway, cron, repository, and active-cycle ownership. Stop on a
   changed controller revision, active cycle, running cron, or unreviewed state.
2. Determine why the v0.19 host update omitted `daidala` from
   `plugins.enabled`. Preview the exact profile-local config change and obtain
   runtime approval before enabling the existing detached controller; do not
   reinstall, update, or replace its revision implicitly.
3. Restore the documented restricted-container prerequisite without pulling an
   arbitrary image or weakening denied-network isolation.
4. Diagnose the gateway's degraded Telegram startup delivery and review whether
   the API server's `0.0.0.0` bind is restricted to trusted clients. Require a
   sandbox or firewall/bind correction before any untrusted network exposure.
5. Run native and correctly profile-bound standalone `doctor --live`; require
   all eleven checks to pass with exact controller revision `3ce1bfc…`, paused
   cron `1847b1b1e14b`, no active cycle, and no owned worktree.

Verification gate: the controller plugin is enabled and healthy at the exact
approved revision, both diagnosis routes pass 11/11, evaluator and attended
delivery boundaries pass, the API exposure decision is recorded, cron remains
paused, and no cycle, GitHub mutation, release, or publication occurred.

## Out of scope

- Do not run `hermes update`, downgrade, reinstall, or otherwise change the
  active operator or persistent-controller host as part of the support proof.
  It already runs an independently updated v0.19.0 source distinct from the
  exact release candidate under evaluation.
- Do not drop v0.18.2 support; the target range deliberately covers both tested
  minor lines.
- Do not declare compatibility with Hermes v0.20 or an untested v0.19 source
  commit.
- Do not add Hermes as a Daidala Python dependency or import Hermes internals.
- Do not weaken exact tool/skill inventories, human approval, dry-run defaults,
  active-home exclusion, Kanban authority, or release-content checks to obtain a
  passing result.
- Do not run credentialed model-route case `TC-F12-01`; it remains a separate
  approval and does not block the host/plugin support boundary defined here.
- Do not resume reconciliation, create a self-improvement cycle, mutate GitHub
  issues, or change the installed controller during compatibility evaluation.
- Do not tag, create a GitHub release, publish to TestPyPI/PyPI, or deploy from
  this plan. Those require a separate release approval after Phase 6.

## Risks & open questions

- Phase 0 found local and remote `main` synchronized, superseding the authored
  55-commit-gap warning. Phase 6 still requires approval of its exact outgoing
  range because branch history can change before push.
- The independent active Hermes update left the existing controller disabled,
  evaluator unavailable, startup delivery degraded, and a non-loopback API
  warning. Phase 7 owns those separately approved runtime repairs before any
  reconciliation resume or new cycle; isolated support evaluation must preserve
  this exact baseline rather than silently repairing it.
- The actual v0.19 public-Git install can only be proven against the updated
  default remote branch after an approved merge. This is intentionally a
  post-merge, pre-tag gate with a hard stop on failure.
