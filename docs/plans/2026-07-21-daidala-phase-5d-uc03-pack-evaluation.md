# Phase 5D — UC-03 paired pack evaluation

Produce one valid, sequential `evaluate-pack` comparison of the pinned default
`addyosmani` pack against the pinned `aidlc` candidate from one frozen repository
baseline, one canonical package-resource migration fixture, identical evaluator
and model-routing identities, and separately approved live cycles.

**Status:** complete — Phases 0 through 4 are complete. Two control attempts were
canceled before plan approval: issue #9 could not expose packet v1 to workers;
issue #11 exposed packet v2 but proved baseline `3ce1bfc` lacked the fixture.
Dedicated clean fixture baseline `c53ba52` now passes the frozen behavior and
repository gates. Packet
[`7139cf3e`](2026-07-21-daidala-phase-5d-uc03-experiment-v3.json) binds that
baseline while preserving fixture identity. Control cycle `cycle-c037e2b…`
completed issue #12 with accepted evidence-only delivery and no commit, push, or
retention. Candidate cycle `cycle-39a46010…` completed issue #10 after immutable
review recovery through plan revision 1, also with accepted evidence-only delivery
and no commit, push, or retention. Retained comparison `99c45ed` records
`incomparable` because the two admission candidate-identity strings are
byte-unequal. No implementation retention, remote publication, or promotion
occurred.

**Parent plan:**
[`2026-07-13-daidala-self-improvement-loop.md`](2026-07-13-daidala-self-improvement-loop.md)

**Parent phase:** `5D — UC-03 pack evaluation`

## Current state

- Parent Phase 5C-R is complete at repository checkpoint `8f6ff7c`; exact
  detached controller `3ce1bfc` is installed with rollback `2595bf5`,
  reconciliation is paused, and native plus standalone diagnosis pass 11/11.
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
- Invalid control cycle
  `cycle-8cbe191f34e879a24fc9888e1d00d7d85624fdf2758cb90c2b66e05861ea3de2`
  is terminally canceled at digest `e606f24c`; issue #9 is closed not planned,
  issue #10 was kept unready, no owned worktree existed, and diagnosis returned
  to 11/11.
- Invalid replacement cycle
  `cycle-54b9b3f253d7a3dee883f146b446bad239c31819e8bdbf48ce05e62f154ab738`
  is terminally canceled at digest `fc865175`; issue #11 is closed not planned,
  issue #10 was kept unready, and no worktree or implementation existed.
- Valid control cycle
  `cycle-c037e2b69532105d79b7c1d0707e3e3663c1822a449ff538353ef5c8dedbc081`
  binds plan `15607a5f`, accepted review `4074ae25`, delivery `422b88f9`, and
  terminal completion `a7a668ca`; issue #12 is closed completed, receipt
  `telegram:64` is retained, its claim/worktree are released, and exact controller
  `3ce1bfc` is restored with native plus standalone diagnosis at 11/11.
- Valid candidate cycle
  `cycle-39a46010db3f45c4cc2e4bfc541f18481ff6b3c2c478eb1a9f8d892926267842`
  binds terminal plan revision 1 digest `ebfadd7b`, accepted review `5786d828`,
  delivery `d7c7a63f`, and terminal completion `a3722356`; issue #10 is closed
  completed, receipt `telegram:73` is retained, its claim/worktree are released,
  and exact controller `3ce1bfc` is restored with native plus standalone diagnosis
  at 11/11.

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
| 1 | Freeze the paired experiment and install the exact controller | done (packet `c0cdfefb`; controller `3ce1bfc`; issues #9/#10) | Packet and nested digests verify; controller/help/packs agree; native/standalone diagnosis pass 11/11; cron is paused; issues are exact and unready; no cycle or owned worktree exists. |
| 2 | Run the Addyosmani control workflow | done (cycle `cycle-c037e2b…`; completion `a7a668ca`; receipt `telegram:64`) | The separately approved `evaluate-pack` cycle using `addyosmani` started from fixture baseline `c53ba52`, read packet `7139cf3e`, passed all exact verification commands, reached accepted evidence-only delivery, completed issue #12, and cleaned up with no retention, commit, or push. |
| 3 | Run the Aidlc candidate workflow | done (cycle `cycle-39a46010…`; completion `a3722356`; receipt `telegram:73`) | The separately approved `evaluate-pack` cycle using `aidlc` started from fixture baseline `c53ba52`, retained three behavior runs and the migration-policy result, recovered an immutable rejected review through plan revision 1, reached accepted evidence-only delivery, completed issue #10, and cleaned up with no retention, commit, or push. |
| 4 | Compare, reconcile, and close Phase 5D | done (comparison `99c45ed`; verdict `incomparable`) | Nine deterministic metrics pass; exact `candidate_identity_equal` fails because control and candidate admissions use byte-unequal serializations. The result record and plans agree; no default, manifest, skill installation, controller, cron, implementation retention, or remote ref changed. |

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
- **Repository baseline:** exact fixture checkpoint
  `c53ba5285a34e8af7ac0c4eccf7466ee6e9589c4`. The packet is committed on the
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
- pre-install live precondition: controller `2595bf5`, checkout `3ce1bfc`, paused
  cron, no active cycle or owned worktree, and native 11/11 diagnosis

The approved Phase 1 apply installed controller `3ce1bfc` through a verified
local detached clone, retained clean rollback `2595bf5`, atomically rebound both
mode-`0600` controller evidence files, restarted the gateway, and created exact
open issue #9 for packet role `current-control`/selected pack `addyosmani` and
issue #10 for packet role `candidate`/selected pack `aidlc`, without ready or
claimed labels/events. Their GitHub payloads remain byte-identical; selected pack
is bound only at admission. Standalone and native
help expose strict comparison admission; both packs validate; both live diagnosis
routes pass 11/11; reconciliation job `1847b1b1e14b` is paused; no cycle or owned
worktree exists. No readiness, admission, plan approval, attended delivery,
retention, commit/push of experiment output, finding publication, release,
promotion, or remote-ref change occurred.

## Phase 2 — Run the Addyosmani control workflow

**Goal:** Produce one terminal control result from the frozen current/default
pack without retaining repository changes.

Steps:

0. Materialize packet v3 byte-for-byte at its mode-`0600` profile-local path,
   verify embedded contract/fixture digests, update candidate issue #10 to the
   byte-identical v3 payload, and create one replacement control issue only after
   exact approval. The prior issues #9/#11 and cycles remain terminal evidence.
1. Apply readiness only to the approved replacement Addyosmani issue; verify it
   is the only eligible issue and the Aidlc issue remains unready. Before
   readiness, record the active branch checkpoint, detach the same registered
   checkout at exact baseline `3ce1bfc15c5102d75d54e846ea6ddb8520b6eed8`,
   and rerun 11/11 diagnosis.
2. Run a dry-run admission with `--mode evaluate-pack`, selected pack
   `addyosmani`, and the exact candidate identity. Obtain separate approval for
   the fresh cycle ID and intake digest.
3. Apply and replay admission; run definition and planning; stop for exact plan
   digest approval. Both stage cards must read packet v3 from the approved
   profile-local path before emitting an artifact; missing or mismatched bytes
   block the card.
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

Canceled attempts:

- cycle:
  `cycle-8cbe191f34e879a24fc9888e1d00d7d85624fdf2758cb90c2b66e05861ea3de2`
- immutable definition:
  `a580a0be950ac0e6bdd81e4f58b9cc5d73cd8d59e46612d419c5470b766d6331`
- mismatch: definition guessed `python -m unittest ... -v`; packet v1 binds
  `python3 -m unittest ...` without `-v`
- cancellation preview/digest:
  `679cf1d9d0ba901f850e217e7211c44c07b83bfba4191a6b68b946420e50e7cb` /
  `e606f24c787d1e9c024f13c39c8d953baffda0e6644c6072c26b07562b175c44`
- receipt: `telegram:57`; issue #9 closed not planned; both cards archived;
  claim released; no worktree or implementation; diagnosis 11/11; cron paused
- replacement cycle:
  `cycle-54b9b3f253d7a3dee883f146b446bad239c31819e8bdbf48ce05e62f154ab738`
- packet-correct definition:
  `651ea6bae12274b3a05065ba161fe83379ac57d1fac5bfdaa9c31bbb4fd58c05`
- mismatch: baseline `3ce1bfc` contained none of the eight fixture paths, so
  baseline behavior could not run and later materialization would have violated
  the one-path implementation contract
- cancellation preview/digest:
  `4379078f5c9dba503fa6d5dc4f60787b0acc732ea2286efa8ce7893eb01951d0` /
  `fc8651757bb9c258a9b15507ff6f14344b65bf47a8a8044d811c23c3546491fe`
- receipt: `telegram:59`; issue #11 closed not planned; both cards archived;
  claim released; no worktree or implementation; diagnosis restored to 11/11
  after exact evaluator image `32209923` was restored; cron paused

Prepared remediation packet:

- path:
  [`2026-07-21-daidala-phase-5d-uc03-experiment-v2.json`](2026-07-21-daidala-phase-5d-uc03-experiment-v2.json)
- packet SHA-256:
  `eb02da7c4f714eac03b2486d78c18922a77f5893aaad0548449c037af14c17aa`
- unchanged contract/fixture SHA-256:
  `357f6eff03c92b659a67e33a26ada687fa114a0ab57b886ce51917d3e4e0e09e` /
  `4198f672861d7279aa9f5325a4e6fe1af54aa770f2c454fdd8c46d5d1478239d`
- runtime path:
  `/home/raphael/.hermes/profiles/daidala-self-improvement/projects/forgegod-daidala/uc03-experiment-packet-v2.json`
- packet v2 changes only distribution and byte-identical intake guidance; baseline,
  controller, packs, candidate, source, fixture, evaluator, routing, limits,
  commands, metrics, and stop conditions remain unchanged

The approved v2 remediation copied those exact bytes to the runtime path, updated
candidate issue #10, and created control issue #11. Its packet visibility worked,
but planning exposed the missing-baseline-fixture contradiction and canceled the
cycle without a worktree or implementation.

Prepared final remediation packet:

- fixture baseline:
  `c53ba5285a34e8af7ac0c4eccf7466ee6e9589c4`; exact frozen `unittest` command,
  full `pytest`, Ruff, and Markdown links pass
- path:
  [`2026-07-21-daidala-phase-5d-uc03-experiment-v3.json`](2026-07-21-daidala-phase-5d-uc03-experiment-v3.json)
- packet/contract/fixture SHA-256:
  `7139cf3e1b4fd16d36eed4ea36061a92ab33429f1fbbf7155ba27759afbd0409` /
  `a92ddca55d44203a9d275aa3d846bbef2d03cb9eb4a1209157b67bfd1ab0afff` /
  `4198f672861d7279aa9f5325a4e6fe1af54aa770f2c454fdd8c46d5d1478239d`
- runtime path:
  `/home/raphael/.hermes/profiles/daidala-self-improvement/projects/forgegod-daidala/uc03-experiment-packet-v3.json`
- v3 changes baseline/distribution/intake guidance only; controller, packs,
  candidate, source, fixture bytes, evaluator, routing, limits, commands,
  metrics, and stop conditions remain unchanged

The approved v3 distribution installed those exact bytes mode `0600`, updated
candidate issue #10, and created replacement control issue #12 with byte-identical
payloads. The control admission bound canonical packet and candidate identity to
workflow `cycle-c037e2b…`; exact plan `15607a5f` changed only
`tests/fixtures/uc03_pack_eval/resource_fixture/catalog.py`. Three behavioral runs
and the migration-policy command passed. Review `4074ae25` accepted immutable diff
`56e2cb08`; delivery `422b88f9` recorded commit/push false and removed the owned
worktree.

Terminal completion initially exposed a controller contradiction: approval is a
ledger-owned gate with no Kanban card, while completion required an approval card.
Regression checkpoint `e20e3e8` removes only that impossible card requirement and
retains checks for done implement, verify, review, and deliver cards. The exact fix
was installed temporarily, completion preview `deb7d47b` applied and replayed to
digest `a7a668ca`, and issue #12 closed completed with receipt `telegram:64`.
Controller `3ce1bfc` and its evidence were then restored before candidate work;
both diagnosis routes passed 11/11. Control evidence files are mode `0600` and
evidence directories are mode `0700`.

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

Candidate issue #10 admitted as workflow `cycle-39a46010…` with receipt
`telegram:66`. Original plan `9095050a` produced the required one-path migration
and three successful behavior executions, but the worker persisted rejection
`3592ffd9` before the repeated evidence was fully represented in the ledger. The
accepted retry could not overwrite immutable `review.md`. Supported plan
replacement preserved all revision-0 evidence, archived its post-gate cards,
removed its worktree, and invalidated approval. Separately approved revision 1
`ebfadd7b` recreated the same one-path migration as diff `e68e33c1`, retained
three distinct behavior rows plus migration-policy row `e3b0c442`, and reached
accepted review `5786d828` and delivery `d7c7a63f` with commit/push false.

Exact completion preview `2b206ef9` applied and replayed to terminal digest
`a3722356`; issue #10 closed completed, its claim/worktree were released, and
receipt `telegram:73` was retained. Completion used the already verified narrow
controller fix `e20e3e8` temporarily. Controller `3ce1bfc` and both mode-`0600`
evidence files were restored afterward; native and standalone diagnosis pass
11/11, cron `1847b1b1e14b` remains disabled, and candidate evidence files and
directories are restricted to `0600`/`0700` without content changes.

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

Retained profile-local comparison
`uc03-paired-comparison.json` is mode `0600` with SHA-256
`99c45ed69d371343ea0e004e70dcd4e1b0b9ab5d0b12b06fa11840ed7fbf004e`.
Nine deterministic metrics pass: fixture, repository baseline, routing,
evaluator binding, limits, commands, exact changed path, behavioral exits, and
migration-policy exits. Exact candidate identity does not:

- control: `pack:aidlc@e49341dbeb8af82758dd85e96ed7fe9bcf38a447#sha256:e4e921b9e719eb54a7d5ec753418e2e451369a3ef50ffd7f52cf74a85d6a6b6a`
- candidate: `pack:aidlc:revision:e49341dbeb8af82758dd85e96ed7fe9bcf38a447:digest:e4e921b9e719eb54a7d5ec753418e2e451369a3ef50ffd7f52cf74a85d6a6b6a`

The strings encode the same pack inputs but are not byte-equal. The frozen
contract requires exact equality and does not permit semantic normalization, so
the only valid verdict is `incomparable`. Observational differences — including
the candidate's immutable review recovery and longer wall time — cannot override
that deterministic failure. No preferred pack, default change, retained
implementation, finding publication, push, release, promotion, or cron resume is
authorized. A later paired rerun must pass the packet's one canonical candidate
identity byte-for-byte to both admissions.

## Out of scope

- Do not install an unpinned external skill set; `aidlc` is the one approved
  candidate already pinned by the project manifest.
- Do not evaluate a candidate Hermes version; that remains parent Phase 6.
- Do not auto-promote a pack, change `.daidala/project.yaml`, retain fixture
  changes, enable reconciliation, push, release, deploy, or publish findings.
- Do not run both cycles concurrently or reuse one cycle's worktree/evaluator.
- Do not use the web-search failure as experiment evidence; only retained primary
  source content and its digest may ground the fixture.
