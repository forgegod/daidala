# Phase 5D — UC-03 paired pack evaluation

Produce one valid, sequential `evaluate-pack` comparison of the pinned default
`addyosmani` pack against the pinned `aidlc` candidate from one frozen repository
baseline, one canonical package-resource migration fixture, identical evaluator
and model-routing identities, and separately approved live cycles.

**Status:** in-progress — Phase 0 is complete with 416 tests and the complete
repository/release gate passing. Phase 1 froze packet
[`c0cdfefb`](2026-07-21-daidala-phase-5d-uc03-experiment.json) after local
contract, fixture, issue, command, image, and pack preflight. Exact packet
approval, issue creation, controller installation, live cycle admission, plan
approval, cleanup, finding publication, retention, push, release, and promotion
remain separate.

**Parent plan:**
[`2026-07-13-daidala-self-improvement-loop.md`](2026-07-13-daidala-self-improvement-loop.md)

**Parent phase:** `5D — UC-03 pack evaluation`

## Current state

- Parent Phase 5C-R is complete at repository checkpoint `8f6ff7c`; exact
  detached controller `2595bf5` remains installed, reconciliation is paused, and
  native plus standalone diagnosis last passed 11/11.
- The versioned evaluation record agrees with the approved remediation evidence:
  controller `2595bf5`, ledger-owned approval, immutable revision artifacts,
  `TC-F06-01`/`TC-F07-01` pass, and issues #6/#7 completed.
- `ProjectCycleOperator` and standalone/native `project-cycle admit` now expose
  and preserve the pure admission model's exact mode and candidate identity.
  Comparison modes require a candidate, `improve` rejects one, and
  reconciliation remains `improve`-only.
- `.daidala/project.yaml` pins current/default pack `addyosmani` at revision
  `7ce442de03ddc1b72480c3b48d55c62880ea2a90`, digest
  `991faf8e26d1c472230dcbf2c29baae9925ad9b9e0cd954f1d90b374302b7832`, and
  candidate pack `aidlc` at revision
  `e49341dbeb8af82758dd85e96ed7fe9bcf38a447`, digest
  `e4e921b9e719eb54a7d5ec753418e2e451369a3ef50ffd7f52cf74a85d6a6b6a`.
- The operator selected a package-resource API migration grounded in the official
  Python `importlib.resources` documentation. The deprecated
  `contents(anchor)` implementation must be replaced with
  `files(anchor).iterdir()` while preserving exact sorted resource names.

## Risk call-out

Phases 2 and 3 mutate GitHub issue state, profile-local Daidala evidence, Hermes
Kanban, owned worktrees, and the attended channel. They run sequentially because
v1 permits one active cycle globally. Each mutation starts from a fresh dry-run,
exact digest approval, clean registered checkout, paused reconciliation, and
11/11 diagnosis. Any drift stops the phase. Partial cycles retain evidence and
use digest-bound cancellation or completion; never repair GitHub, Kanban,
worktree, or ledger state by inspection.

## Phase table

| # | Phase | Status | Verification gate |
|---|---|---|---|
| 0 | Restore evidence authority and expose exact comparison admission | done (416 tests + complete release gate) | Focused project-cycle/CLI tests and the complete repository/release gate pass; current source exposes `--mode evaluate-pack --candidate-identity`; no live state changes. |
| 1 | Freeze the paired experiment and install the exact controller | in-progress | One canonical experiment packet binds fixture bytes, baseline, packs, candidate, routing, limits, evaluator image, commands, metrics, and two approved intake bodies; exact detached installation passes native/standalone help parity and 11/11 diagnosis. |
| 2 | Run the Addyosmani control workflow | pending | One separately approved `evaluate-pack` cycle using `addyosmani` reaches accepted evidence-only delivery and terminal cleanup with the frozen fixture and no retention, commit, or push. |
| 3 | Run the Aidlc candidate workflow | pending | One separately approved `evaluate-pack` cycle using `aidlc` reaches accepted evidence-only delivery and terminal cleanup with identities equal to Phase 2 except the selected pack. |
| 4 | Compare, reconcile, and close Phase 5D | pending | Deterministic comparison eligibility passes or records `incomparable` for an exact missing identity; the result record and plans agree; no default, manifest, skill installation, controller, or remote ref changes automatically. |

Mark a phase `in-progress` while running it, `done (<evidence>)` only after its
gate passes, and leave every later row `pending`.

## Canonical experiment contract

- **Mode:** `evaluate-pack` for both cycles.
- **Current pack:** pinned `addyosmani` identity from `.daidala/project.yaml`.
- **Candidate:** pinned `aidlc` identity from `.daidala/project.yaml`; use one
  canonical candidate-identity string derived from its name, source revision,
  and content digest in both admissions.
- **External source:**
  `https://docs.python.org/3.11/library/importlib.resources.html`, specifically
  the Python 3.11 deprecation of `contents(package)` in favor of traversable
  `files(package).iterdir()`. Do not bind the moving `/3/` URL, whose current
  content no longer retains this deprecated API section.
- **Repository baseline:** exact Phase 0 checkpoint
  `3ce1bfc15c5102d75d54e846ea6ddb8520b6eed8`. The packet is committed on the
  active branch, then the same registered checkout path is detached at this
  baseline before readiness or admission. The branch checkpoint is restored only
  after both cycles release ownership. This avoids a self-referential packet
  commit without changing registration or Kanban workdir identity.
- **Fixture:** one bounded package under
  `tests/fixtures/uc03_pack_eval/` containing a resource package, two `.txt`
  resources, one non-matching resource, one nested directory, legacy catalog
  code using `contents()`, and frozen `unittest` coverage for sorted names,
  extension filtering, and directory exclusion.
- **Goal:** replace only the legacy catalog implementation with the traversable
  API; preserve behavior; do not change fixture tests, resources, project
  defaults, packs, or runtime policy.
- **Deterministic metrics:** identical fixture digest; identical frozen repository
  baseline; exact allowed changed paths; behavioral tests pass; candidate source
  contains no call to `contents()`; evaluator, command, expected exit, limits,
  controller, Hermes route, and verification identities match.
- **Repeated metric:** run the frozen behavioral verification three times with
  zero failures per pack.
- **Observational metrics:** ambiguity, recovery quality, handoff quality, turns,
  model calls when available, delegated workers, research calls, and wall time.
- **Decision:** `improved`, `equivalent`, `regressed`, or `incomparable`; never
  infer a pack preference from observational evidence or update the default.

## Phase 0 — Restore evidence authority and expose exact comparison admission

**Goal:** Make the repository truth and dry-run-first production admission
surface capable of representing the already-implemented strict
`evaluate-pack` identity without touching live controller or adapter state.

Steps:

1. Reconcile `docs/evaluation-results/v1/daidala-self-improvement.md` to the
   approved Phase 5C-R record: controller `2595bf5`, both control cases `pass`,
   issues #6/#7 completed, paused cron, 11/11 diagnosis, and Phase 5D unstarted.
2. Add `mode` and `candidate_identity` parameters to
   `ProjectCycleOperator.preview()`, `admit()`, and their private preparation
   path. Forward both unchanged to `AdmissionCoordinator.preview()` and
   `admit()` so the exact cycle identity is recomputed before apply.
3. Add `project-cycle admit --mode {improve,regress,evaluate-pack}` with default
   `improve`, plus `--candidate-identity`. Keep reconciliation explicitly
   `improve`-only.
4. Add focused tests proving native/standalone parity, dry-run/apply forwarding,
   `evaluate-pack` candidate binding, missing candidate rejection before
   mutation, and rejection of a candidate on `improve`.
5. Update `daidala/AGENTS.md`, `tests/AGENTS.md`, and
   `docs/15-self-improvement.md` for the exact comparison admission contract.
6. Run the focused and complete repository/release gates. Create one source
   checkpoint; do not install it or mutate GitHub, profiles, Kanban, cron,
   evaluator, worktree, or attended state.

Verification gate:

```bash
pytest -q tests/test_controller.py tests/test_project_cycles.py tests/test_cli.py
ruff check daidala tests
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

Both standalone and native `project-cycle admit --help` must expose `--mode` and
`--candidate-identity`; the repository stays clean after the source checkpoint,
and no live state changes.

Observed gate: focused controller, project-cycle, and CLI tests exited 0; Ruff
and the 44-file Markdown link check passed; the complete gate passed with 416
tests, both pack validators, build, Twine, release contents, Lefthook, and staged
diff checks. No live controller, profile, GitHub, Kanban, cron, evaluator,
worktree, attended destination, or remote ref changed.

## Phase 1 — Freeze the paired experiment and install the exact controller

**Goal:** Materialize one immutable experiment packet and install only the
separately approved Phase 0 checkpoint before any issue or cycle exists.

Steps:

1. Create a canonical JSON packet under `docs/plans/` with exact fixture bytes,
   source URL and captured source digest, baseline revision, controller revision,
   both pack identities, candidate identity, stage/model routing identity,
   evaluator image, commands, expected exits, limits, metrics, allowed paths,
   issue titles/bodies/labels, and stop conditions.
2. Verify the packet digest and dry-run both issue bodies locally. Commit the
   immutable packet as an intermediate approval checkpoint, then obtain separate
   approval for that exact packet digest, two issue creations, and controller
   installation; do not combine that approval with admission.
3. Install the clean detached Phase 0 checkpoint under rollback protection,
   restart the controller gateway, and verify standalone/native admit help,
   both packs, paused cron, no active cycle, and 11/11 diagnosis.
4. Create exactly two structured, unready issues with byte-identical titles,
   bodies, and protocol-valid compatibility/priority labels only after approval.
   The packet run role and eventual issue ID distinguish control from candidate;
   selected pack remains an admission argument so the normalized goals stay
   equal. No unapproved pack-specific GitHub labels are created. Obtain separate
   approval before applying readiness to either issue.

Verification gate: the canonical packet and its SHA-256 read back exactly; the
installed controller equals the approved source checkpoint; both help routes and
packs agree; diagnosis is 11/11; cron is paused; no cycle or owned worktree
exists; and the two issue identities are retained without admission.

Prepared approval packet:

- path:
  [`2026-07-21-daidala-phase-5d-uc03-experiment.json`](2026-07-21-daidala-phase-5d-uc03-experiment.json)
- packet SHA-256:
  `c0cdfefb6740752d96dd2864f751c5fda25292bb26d889764e593fccf2c8645e`
- contract SHA-256:
  `357f6eff03c92b659a67e33a26ada687fa114a0ab57b886ce51917d3e4e0e09e`
- fixture SHA-256:
  `4198f672861d7279aa9f5325a4e6fe1af54aa770f2c454fdd8c46d5d1478239d`
- source capture: versioned Python 3.11 documentation, 39,388 bytes, raw
  SHA-256 `2105a3a8fd602ffcadc87eabaa3fbfc1160a5d4f35c1084656cf0e9e4ac39b69`
- local preflight: packet and nested digests recompute; issue payloads and
  normalized goal inputs are equal and unready; baseline and representative
  migrated behavior exit 0; migration policy exits 0; evaluator image is local;
  both packs validate
- live precondition: controller `2595bf5`, checkout `3ce1bfc`, paused cron, no
  active cycle or owned worktree, and native 11/11 diagnosis

The normative setup guide now agrees with that live precondition. No controller,
gateway, profile evidence, GitHub issue, Kanban task, cron job, worktree,
attended destination, or remote ref changed while preparing the packet.

## Phase 2 — Run the Addyosmani control workflow

**Goal:** Produce one terminal control result from the frozen current/default
pack without retaining repository changes.

Steps:

1. Apply readiness only to the approved Addyosmani issue; verify it is the only
   eligible issue and the Aidlc issue remains unready. Before readiness, record
   the active branch checkpoint, detach the same registered checkout at exact
   baseline `3ce1bfc15c5102d75d54e846ea6ddb8520b6eed8`, and rerun 11/11 diagnosis.
2. Run a dry-run admission with `--mode evaluate-pack`, selected pack
   `addyosmani`, and the exact candidate identity. Obtain separate approval for
   the fresh cycle ID and intake digest.
3. Apply and replay admission; run definition and planning; stop for exact plan
   digest approval.
4. After separate plan approval, create the canonical fixture only in the owned
   worktree/evaluator, retain baseline evidence before implementation, execute
   the pack, and collect deterministic, repeated, and observational evidence.
5. Review and deliver evidence only with commit/push false. Complete or cancel
   by exact preview approval, release the claim/worktree, and return diagnosis
   to 11/11 with cron paused.

Verification gate: one terminal Addyosmani cycle binds the experiment packet,
fixture, repository baseline, candidate identity, evaluator, routing, limits,
commands, and metrics; immutable evidence is complete; no retention, commit,
push, publication, default change, or second cycle occurred.

## Phase 3 — Run the Aidlc candidate workflow

**Goal:** Produce one terminal candidate result whose comparison inputs match
Phase 2 except for the selected workflow pack.

Steps:

1. Confirm Phase 2 terminal ownership release, 11/11 diagnosis, paused cron,
   clean baseline, and unchanged packet.
2. Apply readiness only to the approved Aidlc issue. Dry-run admission with
   `--mode evaluate-pack`, selected pack `aidlc`, and the same exact candidate
   identity; obtain separate cycle approval.
3. Apply/replay admission, run definition and planning, and obtain separate exact
   plan approval.
4. Recreate the fixture byte-for-byte from the packet, retain baseline first,
   execute Aidlc, and collect the same metrics under the same evaluator, routing,
   limits, and commands.
5. Review and deliver evidence only. Complete or cancel by exact preview
   approval, release ownership, and restore 11/11 diagnosis with cron paused.

Verification gate: one terminal Aidlc cycle has every comparison identity equal
to Phase 2 except selected pack identity; immutable evidence is complete; no
retention, commit, push, publication, default change, or third cycle occurred.

## Phase 4 — Compare, reconcile, and close Phase 5D

**Goal:** Record one evidence-supported pack conclusion without promoting either
pack or changing project defaults.

Steps:

1. Recompute all packet, admission, plan, fixture, evaluator, metric, review,
   delivery, terminal, and receipt digests for both cycles.
2. Require exact equality for baseline, fixture, candidate, routing, limits,
   evaluator, commands, and metric definitions. Record `incomparable` for any
   mismatch rather than inferring a pack effect.
3. Compare deterministic and repeated metrics first; observational/resource
   proxies may explain but never decide the result alone.
4. Update the versioned result record, `docs/15-self-improvement.md`, this child
   plan, and the parent plan after restoring the recorded branch checkpoint at
   the same checkout path. Keep any promotion or actionable finding in a
   separately approval-gated later phase.
5. Run the complete repository and release gate and create the closeout
   checkpoint. Do not push.

Verification gate: both terminal workflows and all content addresses verify; the
record names a valid verdict and its basis; parent Phase 5D and this child are
done; Phase 6 remains unstarted; controller/default pack/manifest/skills/cron and
remote refs are unchanged.

## Out of scope

- Do not install an unpinned external skill set; `aidlc` is the one approved
  candidate already pinned by the project manifest.
- Do not evaluate a candidate Hermes version; that remains parent Phase 6.
- Do not auto-promote a pack, change `.daidala/project.yaml`, retain fixture
  changes, enable reconciliation, push, release, deploy, or publish findings.
- Do not run both cycles concurrently or reuse one cycle's worktree/evaluator.
- Do not use the web-search failure as experiment evidence; only retained primary
  source content and its digest may ground the fixture.
