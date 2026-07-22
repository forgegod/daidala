# Phase 6 — Hermes v0.19.0 version-aware re-evaluation

Compare Daidala 0.2.0 against one exact last-known-good Hermes host and one
exact Hermes v0.19.0 candidate in isolated environments, retain reproducible
host-boundary evidence, and produce a supported-range proposal without changing
the active Hermes runtime or persistent Daidala controller.

**Status:** in-progress — Phases 0 through 2 are complete. Exact baseline and
candidate hosts passed the repeated isolated matrix with the same Daidala wheel,
and Phase 3 comparison is next. Candidate code ran only in temporary evaluators.

**Parent plan:**
[`2026-07-13-daidala-self-improvement-loop.md`](2026-07-13-daidala-self-improvement-loop.md)

**Parent phase:** `6 — Version-aware re-evaluation`

## Current state

- Phase 5D is complete at repository checkpoint `b74994f`; its paired pack
  comparison is terminally `incomparable`, controller Daidala revision
  `3ce1bfc15c5102d75d54e846ea6ddb8520b6eed8` is restored, reconciliation cron
  `1847b1b1e14b` is paused, and native plus correctly profile-bound standalone
  diagnosis pass 11/11.
- Daidala's reproducible last-known-good Hermes probe baseline is v0.18.2 build
  `2026.7.7.2`, source commit
  `4281151ae859241351ba14d8c7682dc67ff4c126`. This is the exact post-tag commit
  pinned by `.github/workflows/release.yml`, not the v0.18.2 tag's peeled commit.
- The active Hermes installation is separately identified as v0.18.2 at source
  commit `36f2a966c7f9f69987494b867c3dcf96b69a5766`. Its source tree has a pre-existing
  untracked `tinker-atropos/` path. Phase 6 treats the installation as read-only
  and compares before/after HEAD and porcelain status without reading that path.
- The proposed candidate is official release v0.19.0 build `2026.7.20`, annotated
  tag object `c7d08de287556b3d339df336b180a39d4980ebd7`, peeled source commit
  `3ef6bbd201263d354fd83ec55b3c306ded2eb72a`, published at
  <https://github.com/NousResearch/hermes-agent/releases/tag/v2026.7.20>.
- Core, plugin, and dashboard probes retain the supported baseline defaults and
  accept only a complete explicit candidate identity. The packaged-plugin probe
  covers entry-point and directory discovery plus native/standalone pack parity;
  the dashboard probe retains its isolated minimal fixture boundary.
- The stable matrix still records `TC-F11-01` packaging, `TC-F12-01` Hermes
  routes, and `TC-F14-01` version comparison as `not-run`. Candidate evaluation
  must not promote a row that its retained evidence does not exercise.

## Risk call-out

Hermes v0.19.0 changes plugin listing, Kanban behavior, dashboard internals,
approvals, delegation, and credential handling. Running it against the active
Hermes home could migrate or rewrite operator state and invalidate the comparison.
Both host revisions must therefore run from detached temporary clones, separate
virtual environments, and fresh `HERMES_HOME` directories with no imported
profile credentials. The active Hermes checkout, controller profile, gateway,
cron, board, registration, and Daidala evidence are snapshot-only boundaries.
Any candidate process that resolves an active profile path, starts a gateway,
changes the active source tree, or cannot prove exact source identity stops the
phase and produces no compatibility verdict.

## Phase table

| # | Phase | Status | Verification gate |
|---|---|---|---|
| 0 | Approve the candidate and experiment contract | done (plan `826b07a`; candidate `3ef6bbd2…`; exact operator approval) | Remote tag resolution, baseline/candidate/active identities, active-state snapshots, selected matrix rows, and this committed plan are exact; the operator approves candidate commit `3ef6bbd2…` and the plan checkpoint. |
| 1 | Repair the candidate-aware host probe boundary | done (428 tests; exact baseline wheel probe passed) | Focused probe tests pass; default invocations still require baseline `0.18.2`/`2026.7.7.2`/`4281151a`; explicit candidate arguments require all three v0.19.0 identity fields; a fresh-process probe loads the packaged Daidala plugin and native CLI without active-profile access. |
| 2 | Execute the isolated baseline and candidate matrix | done (input `b92098b3`; file `dd587216`; active snapshot `b3ca20b4`) | Both detached host clones and Daidala artifact identities verify; every approved probe emits bounded JSON; temporary homes are removed; active Hermes/controller/cron/repository snapshots are byte-identical before and after. |
| 3 | Compare results and range compatibility findings | pending | One content-addressed comparison classifies every selected matrix row as `pass`, `fail`, `blocked`, or `incomparable`; any actionable failure is added to the parent phase sequence before remote mutation. |
| 4 | Propose the supported range and close Phase 6 | pending | Parent/child plans and the versioned result record agree; any range change is proposal-only; the complete repository/release gate passes; Phase 7 remains unstarted. |

Mark a phase `in-progress` while running it, `done (<evidence>)` only after its
gate passes, and leave later phases `pending`.

## Canonical comparison contract

- **Daidala source:** one clean committed checkpoint produced by Phase 1 and used
  byte-for-byte for both host legs.
- **Baseline host:** Hermes v0.18.2, build `2026.7.7.2`, source
  `4281151ae859241351ba14d8c7682dc67ff4c126`.
- **Candidate host:** Hermes v0.19.0, build `2026.7.20`, source
  `3ef6bbd201263d354fd83ec55b3c306ded2eb72a`.
- **Active runtime:** snapshot only; v0.18.2 source `36f2a966…` and controller
  Daidala `3ce1bfc…` must remain unchanged.
- **Isolation:** separate detached host clone, Python virtual environment,
  `HERMES_HOME`, dashboard port, and temporary output directory per leg. Do not
  source the controller profile environment or copy its config, auth, sessions,
  skills, plugins, Kanban database, cron data, or evidence.
- **Host pinning:** set each temporary clone's local `origin/main` tracking ref to
  its evaluated commit and replace `origin` with an unavailable local URL before
  invoking Hermes so update checks cannot drift identity evidence.
- **Daidala artifact:** build one wheel after Phase 1; verify its SHA-256 and wheel
  contents once; install that exact wheel into both host environments.
- **Selected stable rows:** `TC-F03-01`, `TC-F03-02`, `TC-F04-01`,
  `TC-F11-01`, `TC-F14-01`, and `TC-F15-01`. Keep `TC-F12-01` `not-run` unless
  separately approved route-specific probes exercise default, fallback, MoA,
  goal, auxiliary, and delegation paths without live credentials.
- **Host boundaries:** exact version output; entry-point and directory plugin
  discovery; exact registered Daidala tools and bundled skills; standalone/native
  CLI parity; dry-run setup; policy-skill digest; public Kanban create/show/
  comment/link/complete/archive; 8,192/8,300 worker-context behavior; dashboard
  manifest/assets/API auth; process exit; and temporary-state cleanup.
- **Verdict:** each boundary is `pass`, `fail`, `blocked`, or `incomparable`.
  Observational release-note differences never override a deterministic mismatch.
- **No automatic action:** passing evidence may support a bounded Hermes range
  proposal. It does not update pack ranges, release workflow pins, documentation,
  the active runtime, controller installation, or GitHub findings without the
  later exact gate that owns that mutation.

## Phase 0 — Approve the candidate and experiment contract

**Goal:** Bind one immutable candidate identity and one executable comparison
contract before candidate code is installed or run.

Steps:

1. Re-resolve `v2026.7.20` from the official Hermes repository and require the
   annotated tag object and peeled commit recorded above.
2. Recompute the current baseline workflow pin, active Hermes HEAD and porcelain
   status, Daidala branch checkpoint, controller revision, 11/11 diagnosis,
   paused cron identity, and absence of active cycle/worktree ownership.
3. Review the v0.19.0 release notes only as risk input. Do not infer compatibility
   from release notes.
4. Commit this child plan and its parent link as a planning-only checkpoint.
5. Obtain explicit operator approval for the exact child-plan checkpoint and
   candidate commit `3ef6bbd201263d354fd83ec55b3c306ded2eb72a`.

Verification gate: all identities resolve exactly, the active runtime snapshot is
retained without content from its untracked path, the repository is clean at the
planning checkpoint, and no candidate clone, environment, process, profile,
plugin, or evidence exists before approval.

Observed gate: official tag `v2026.7.20` resolved again to annotated object
`c7d08de2…` and peeled commit `3ef6bbd2…`; planning checkpoint `826b07a` was
clean with plan SHA-256 `6cfc7f06…`; active Hermes remained v0.18.2 at
`36f2a966…`; controller `3ce1bfc…`, both 11/11 diagnosis routes, paused cron
`1847b1b1e14b`, and no active cycle/worktree were verified. The operator then
approved checkpoint `826b07a` and full candidate commit `3ef6bbd201263d354fd83ec55b3c306ded2eb72a`
verbatim. No candidate clone, environment, process, profile, plugin, or evidence
was created.

## Phase 1 — Repair the candidate-aware host probe boundary

**Goal:** Make host identity an explicit evaluator input and add the missing real
Daidala plugin-load boundary without weakening the supported-release defaults.

Steps:

1. Extend `scripts/probe_hermes_compatibility.py` with an immutable expected-host
   value object and explicit `--expected-semver`, `--expected-build`, and
   `--expected-upstream` arguments. All three must be supplied together or not at
   all; no arguments retains the current v0.18.2 constants exactly.
2. Forward the same expected identity through
   `scripts/probe_hermes_dashboard_compatibility.py`; keep its baseline defaults,
   isolated home, cleanup, and `--skip-build` behavior unchanged.
3. Add a fresh-process packaged-plugin probe that enables the exact Daidala wheel
   only inside a fresh `HERMES_HOME`, verifies public inventory when exposed,
   native command loading, and native/standalone CLI parity, then removes the
   home. Pin exact tool/skill registration through the manifest and repository
   registration test. Use public Hermes CLI/plugin surfaces; do not import Hermes
   internals.
4. Add positive baseline/candidate, incomplete-identity, wrong-identity,
   plugin-load failure, active-path exclusion, and cleanup regressions under
   `tests/test_hermes_compatibility_probe.py` and
   `tests/test_hermes_dashboard_compatibility_probe.py` or one focused sibling
   test file if the packaged-plugin probe is separate.
5. Correct `docs/08-hermes-integration.md` so it distinguishes the existing
   Kanban/body-limit probe from the new real plugin-load evidence. Update
   `scripts/AGENTS.md` and `tests/AGENTS.md` for the new durable contract.
6. Run focused tests, Ruff, Markdown links, the default baseline probes, and the
   complete repository/release gate. Create one source checkpoint; do not install
   it into the active Hermes runtime.

Verification gate:

```bash
pytest -q tests/test_hermes_compatibility_probe.py \
  tests/test_hermes_dashboard_compatibility_probe.py \
  tests/test_installation.py tests/test_cli.py
ruff check scripts tests
python scripts/check_md_links.py .
lefthook validate
pytest
ruff check .
daidala packs validate addyosmani
daidala packs validate aidlc
python -m build
python -m twine check dist/*
python scripts/check_release_contents.py . --wheel dist/*.whl
git diff --check
```

The default release path remains pinned to the last-known-good baseline; the
candidate identity is accepted only when all three explicit fields match.

Observed gate: `HostIdentity` is immutable; core, plugin, and dashboard probes
require either all three expected-host arguments or none; defaults remain
`0.18.2`/`2026.7.7.2`/`4281151a`. `plugin.yaml` now matches all 12 tools and all
three runtime-registered skills. A fresh Python 3.11 venv installed the built
Daidala wheel with exact baseline Hermes `4281151a`; public inventory reported
the entry-point plugin enabled and native/standalone JSON matched for Addyosmani
and Aidlc. The full gate passed with 428 tests, Lefthook, Ruff, both pack
validators, Markdown links, build, Twine, release contents, and clean diffs. All
temporary evaluator/probe roots were removed; no candidate code or active-state
mutation occurred.

## Phase 2 — Execute the isolated baseline and candidate matrix

**Goal:** Produce bounded, content-addressed evidence for the same Daidala wheel
on both exact Hermes hosts without touching active state.

Steps:

1. Snapshot active Hermes HEAD/status, active Daidala branch/status, controller
   revision, native and profile-bound standalone diagnosis, cron state, active
   cycle ownership, and gateway process identity. Retain only bounded non-secret
   identities and digests.
2. Build the Phase 1 Daidala wheel once; retain its SHA-256 and release-content
   result. Create separate temporary roots for baseline and candidate.
3. Clone the official Hermes repository into each root, detach at the exact host
   commit, pin its local tracking ref, disable network updates, build the required
   dashboard web distribution with Node 22, and install Hermes plus the same
   Daidala wheel into a root-local Python 3.11 virtual environment. Do not use the
   repository's ambient Python 3.14; baseline Hermes requires Python `<3.14`.
4. Run the version, packaged-plugin, policy/Kanban/body-limit, dashboard, `init`
   dry-run, and standalone/native CLI probes with exact expected-host arguments.
   Capture bounded stdout, stderr digest, exit code, command identity, host commit,
   Python/Node identity, Daidala wheel digest, and cleanup result.
   `setup` is not a CLI command; `init` is the documented mutation-free default
   and is the `TC-F04-01` boundary used here.
5. Repeat deterministic probes once per leg from a second fresh home. Any
   within-leg mismatch is `incomparable`, not a retry-adjusted pass.
6. Remove both temporary roots and rerun the active-state snapshot. Stop if any
   active identity or status changes.
7. Retain one mode-`0600` comparison input under the controller project's bounded
   evidence directory and add a redacted content-addressed result record under
   `docs/evaluation-results/v1/`. Never retain temporary homes or unbounded logs.

Verification gate: baseline and candidate evidence use the same Daidala wheel and
comparison contract; exact host identities differ only as declared; all temporary
state is gone; repeated results agree; active-state snapshots are identical.

Observed gate: exact hosts `4281151a` and `3ef6bbd2` used Daidala checkpoint
`a62f029` wheel `6f43947f…` under Python 3.11.15 and Node 22.22.1. Both repeated
legs produced identical zero-exit version, core policy/Kanban/body-limit,
entry-point plugin, directory plugin, dashboard, and native/standalone `init`
results; neither dry run created SQLite state. Evaluator cleanup completed and
before/after active snapshots are byte-identical at `b3ca20b4…`. Canonical input
`b92098b3…` is retained as mode-`0600` file SHA-256 `dd587216…` beside the exact
evaluator and snapshot helpers. Phase 3 owns classification; matrix statuses and
support policy remain unchanged here.

## Phase 3 — Compare results and range compatibility findings

**Goal:** Classify the candidate from deterministic evidence and schedule every
actionable incompatibility without mutating GitHub implicitly.

Steps:

1. Recompute all source, wheel, command, output, and retained-evidence digests.
2. Compare selected stable rows and host boundaries. Missing identity, differing
   Daidala wheel, incomplete cleanup, or active-state drift forces
   `incomparable` regardless of successful subchecks.
3. Update `docs/evaluation-results/v1/daidala-self-improvement.md` with exact
   statuses and evidence. Do not promote `TC-F12-01` without its separately
   approved route coverage.
4. For each deterministic candidate failure, update or add a named remediation
   row in the parent phase sequence. If a GitHub issue should be reopened or
   created, prepare its exact payload and require a separate preview approval
   before remote mutation.
5. Record one candidate verdict: `compatible`, `incompatible`, `blocked`, or
   `incomparable`. Release-note observations may explain but never determine it.

Verification gate: the retained comparison reproduces from exact inputs, every
selected row has one grounded status, every actionable failure is ranged in the
parent plan, and GitHub remains unchanged unless a later exact mutation gate was
approved.

## Phase 4 — Propose the supported range and close Phase 6

**Goal:** Close the evaluation with a bounded support proposal while leaving
actual support-policy changes to Phase 7.

Steps:

1. If every required host boundary passes, propose the narrowest supported Hermes
   range containing the tested baseline and candidate. If any required boundary
   fails or is incomparable, retain the current range and name the blocker.
2. Update this child plan and the parent Phase 6 row with exact evidence and
   verdict. Set parent Phase 7 to `pending` only after this gate passes.
3. Update normal documentation only with observed current facts; keep proposed
   range changes clearly unimplemented until Phase 7.
4. Run the complete repository/release gate and both live 11/11 diagnosis routes;
   verify the cron remains paused and the active Hermes/controller snapshots are
   unchanged.
5. Create the Phase 6 closeout commit. Do not push, merge, release, publish,
   install, or restart the active runtime.

Verification gate: the child and parent agree, all evidence digests verify, the
proposal follows the deterministic verdict, the complete gate passes, and active
Hermes, controller Daidala, gateway, cron, board, profile, and remote refs remain
unchanged.

## Out of scope

- Do not run `hermes update`, install v0.19.0 into any active profile, or switch
  the persistent controller host.
- Do not broaden pack `supported_hermes` ranges or change the release workflow pin
  during Phase 6; Phase 6 produces evidence and a proposal.
- Do not exercise credentialed model routes, `TC-F12-01`, gateway delivery, or
  live issue mutation without their own exact approval and bounded contract.
- Do not reuse UC-03 pack evidence as host-version evidence.
- Do not push, merge, release, publish, promote, resume reconciliation, or retain
  candidate implementation changes automatically.
