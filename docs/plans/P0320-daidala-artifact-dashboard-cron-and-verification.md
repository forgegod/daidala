# Daidala artifact dashboard, cron, and verification

**Plan ID:** daidala-artifact-dashboard-cron-and-verification

**Execution slot:** P0320

**Created:** 2026-07-24

**Depends on:** daidala-artifact-curation

**Split from:** daidala-artifact-review-access-and-curation

**Plan family:** daidala-artifact-review

**Entry checkpoint:** P0310 completed with verified recoverable curation and idempotent failure recovery; P0240 completed the dashboard family and retained P0210/P0212's verified plan-approval, review-disposition, and revision-request evidence surfaces

**Context sources:** [UX concept and design contract](P0250-daidala-dashboard-ux-concept.md), [artifact current state](daidala-artifact-review-execution-contract.md#current-state), [risk call-out](daidala-artifact-review-execution-contract.md#risk-call-out), detailed [contract Phase 3](daidala-artifact-review-execution-contract.md#phase-3-add-authenticated-dashboard-review-and-curator-controls), [contract Phase 4](daidala-artifact-review-execution-contract.md#phase-4-add-opt-in-hermes-cron-scheduling), and [contract Phase 5](daidala-artifact-review-execution-contract.md#phase-5-reconcile-operator-docs-dox-package-contents-and-full-verification), plus the complete AGENTS chains for `daidala/`, `dashboard/`, `tests/`, and `docs/`

**Produces:** authenticated bounded artifact review/curator controls, opt-in profile-local cron curation, synchronized operator documentation and DOX, and installed-wheel end-to-end evidence

**Status:** completed — Phases 0, 1, and 2 verified

## Goal

Expose verified artifact review and reversible curator controls through the authenticated dashboard, add explicit opt-in Hermes Cron scheduling, and prove the complete artifact family through package and browser boundaries.

## Current state

- P0205 provides exact-ID resolution, P0300 provides CLI review/export, and P0310 provides deterministic curation.
- The authenticated dashboard exposes focused decision evidence plus a general
  path-free artifact browser with literal preview, verified download, and
  preview-confirm curator controls.
- Hermes Cron is the supported scheduler; Daidala must not add a daemon, nested agent, or model judgment.
- The shared contract pins authentication, bounded text/download behavior, confirmation, cron idempotency, documentation, package, and full verification requirements.

## Risk call-out

Dashboard requests may expose sensitive artifact content or trigger reversible storage mutation. Every content route is authenticated, ledger-bound, size-limited, and content-safe on error. Curator mutations require preview digest and literal confirmation. Cron output contains only IDs, counts, digests, and classified states; disabled policy performs no mutation.

## Phase table

| # | Phase | Status | Verification gate |
|---|---|---|---|
| 0 | Add authenticated dashboard review and curator controls | done (focused and full tests; isolated Chromium fixture) | Focused dashboard/access/curator tests pass and isolated-browser verification inspects an archived diff without an arbitrary-path parameter |
| 1 | Add opt-in Hermes Cron scheduling | done (focused/full tests; isolated public Hermes no-agent Cron lifecycle) | Focused cron-boundary tests pass; one isolated tick archives an eligible fixture, replay converges, and disabled policy performs no mutation |
| 2 | Reconcile operator docs, DOX, package contents, and full verification | done (full gates; fresh-wheel archive/restore; isolated browser and Cron probes) | The contract's repository gates pass and a fresh installed wheel lists, shows, exports, archives, and reads one fixture artifact |

Mark a phase `in-progress` while running it, `done (<evidence>)` once its gate passes, `pending` otherwise.

## Phase 0 — Add authenticated dashboard controls

**Goal:** Extend P0210's focused plan/review decision views into a general authenticated artifact browser where users can inspect verified metadata and bounded text, download verified bytes, and preview/confirm reversible curator operations.

Steps:

1. Read contract Phase 3, the complete risk call-out, and the dashboard/daidala/tests AGENTS chains.
2. Implement ledger-bound list/detail/text/download projections without arbitrary-path parameters or unauthenticated content, reusing the same verified escaped-text renderer and identity presentation as the P0210 plan-approval and review-disposition surfaces. Keep Version 1 format-neutral: Markdown, JSON, YAML, source, HTML, and diffs are literal text rather than semantically rendered content; binary or oversized artifacts are download-only.
3. Implement preview-digest/literal-confirm pin, unpin, archive, and restore controls over P0310 services.
4. Keep errors metadata-only and extend the closed dashboard route inventory and DOX in the same change.
5. Run the focused API/assets/access/curator tests and isolated-browser archived-diff journey from the contract.

Verification gate: The Phase 0 table predicate passes and no protected content enters logs or errors.

Phase 0 evidence:

- `pytest tests/test_dashboard_api.py tests/test_dashboard_assets.py tests/test_artifact_access.py tests/test_artifact_curator.py tests/test_dashboard.py` and the full `pytest` suite pass.
- `ruff check .`, `lefthook validate`, both pack validations, build, Twine, and release-content checks pass.
- Isolated Chromium loads `tests/fixtures/dashboard_phase0_browser_probe.html`, lists the archived implementation diff, renders `<script>` content as non-executable literal text, downloads bytes with SHA-256 `27772ec853c0c2b28a60a8c32cebdf405c49bec4f01bedde071e401a5f231005`, and submits restore with only operation, opaque archive ID, exact preview digest, and `confirm: true`.

## Phase 1 — Add opt-in Hermes Cron scheduling

**Goal:** Schedule deterministic profile-local curation through Hermes Cron with disabled-by-default policy and convergent replay.

Steps:

1. Read contract Phase 4 and current official Hermes Cron documentation before editing.
2. Add the bounded `daidala curator tick` entry point, dry-run-first `curator configure`, and `curator schedule setup|status|remove` lifecycle. Policy configuration requires the current state digest and literal desired policy digest. Setup installs the exact `$HERMES_HOME/scripts/daidala-artifact-curator.sh` Bash launcher and creates or updates only the recorded public Hermes script-only/no-agent Cron job; do not add a Daidala daemon or nested `hermes chat`.
3. Keep network and model use absent, output metadata-only, and policy disabled by default.
4. Exercise one isolated profile tick, replay, disabled policy, lock/concurrency, and failure recovery.
5. Update operator docs and owning DOX with the supported Cron lifecycle.

Verification gate: The Phase 1 table predicate passes with convergent replay and no disabled-policy mutation.

Required Phase 1 finding: Hermes executes non-shell Cron scripts with its host
Python interpreter, which is not the installed Daidala CLI identity. The
profile-local launcher is therefore a Bash script that executes `daidala
curator tick` from `PATH`; setup binds its exact name, digest, and entry point in
the preview and persisted schedule identity.

Required Phase 1 finding: curator policy state was service-only, so an operator
could register only a permanently disabled tick. The supported CLI lifecycle
must expose dry-run-first policy configuration before schedule setup; otherwise
the phase cannot produce operational age-based curation without direct state
edits.

Phase 1 evidence:

- Focused Cron, curator, and shared CLI tests pass; the full `pytest` suite,
  `ruff check .`, `lefthook validate`, both pack validations, build, Twine, and
  release-content checks pass.
- A disposable `HERMES_HOME` public-CLI probe confirms policy preview/apply,
  one script-only/no-agent job, successful direct execution, unchanged-setup
  replay to the same job, exact recorded-ID removal, and an empty final Cron
  inventory.
- An isolated eligible fixture transitions to observed, archives two verified
  source artifacts after the configured age, and produces no additional
  transition on replay; disabled-policy ticks remain silent and mutation-free.

## Phase 2 — Reconcile docs, package, and full verification

**Goal:** Make review and curation discoverable and prove the installed distribution preserves security, profile, archive, dashboard, and Cron boundaries.

Entry prerequisite: the repository-owned
`python scripts/check_md_links.py .` check passes all 65 Markdown files. The
seven earlier diagnostics came from running a separate checker against only
`docs/`: four valid links escaped that restricted scan root, two reported
targets exist, and one inline regex was misclassified as a reference link. No
document correction is required for those false positives.

Steps:

1. Read contract Phase 5 and re-check every changed path against its AGENTS chain.
2. Update the exact operator, lifecycle, state, setup, package-content, ownership, route, and test contracts named there; remove stale claims.
3. Run the full repository verification sequence in contract order.
4. Build and install a fresh wheel into an isolated environment and execute the list/show/export/archive/read fixture journey.
5. Exercise authenticated browser review and an opt-in isolated Cron tick, then verify no unintended repository or profile state remains.

Verification gate: Every Phase 2 table predicate and detailed contract gate passes.

Phase 2 evidence:

- `lefthook validate`, the full `pytest` suite, `ruff check .`, both pack
  validations, package build, Twine, release-content validation, the
  repository Markdown-link check, and `git diff --check` pass in contract
  order. The wheel contains the artifact access, curator, Cron, dashboard,
  pack, and bundled-skill resources; runtime archives and schedule state are
  absent.
- A clean temporary environment installs the freshly built wheel, lists two
  ledger artifacts by opaque ID, shows and exports exact active bytes, archives
  both files after an injected-clock transition, converges on replay, reads and
  exports the archived bytes with matching ledger and manifest digests, and
  restores both files with matching SHA-256 values. Exported bytes use mode
  `0600`.
- Authenticated dashboard route tests pass. Isolated Chromium opens the
  archived implementation artifact, displays the embedded `<script>` sequence
  as non-executable literal text, and previews restore using only the workflow
  ID, opaque archive ID, operation, and server-issued preview digest; no
  arbitrary path is sent.
- A disposable `HERMES_HOME` enables policy through the digest-confirmed CLI,
  creates exactly one public Hermes script-only/no-agent job for `daidala
  curator tick`, runs that exact job successfully, removes it by recorded ID,
  and finishes with no schedule record or matching Cron inventory entry. No
  real Hermes profile is modified.
- The owning root, runtime, dashboard, docs, runbook, setup, security, package,
  support-status, and UX contracts now describe the same active/archive,
  recovery, authenticated review, and explicitly opt-in scheduling behavior.

## Out of scope

- Do not expose arbitrary paths, unauthenticated bytes, credentials, or private destinations.
- Do not add automatic deletion, a daemon, nested agents, or model judgment.
- Do not commit, push, publish, or enable a recurring job without the required human gates.
