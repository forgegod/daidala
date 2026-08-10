# tests/

## Purpose

Prove the deterministic pack and policy-ledger models, durable persistence, strict
tool boundaries, Hermes plugin registration contract, and packaged-resource
completeness without touching a real Hermes profile.

## Ownership

- Unit tests for pack loading and validation.
- Strict self-improvement project, registration, cycle, adapter, admission,
  reconciliation, and increment tests, including canonical identity, immutable
  snapshots, replay convergence, event-bound receipts, pre-mutation baseline
  checks, bounds, provenance, and fail-closed malformed external-input coverage.
- Reconciliation tests use fake inventories and command boundaries to prove
  stable issue ordering, no-candidate convergence, bounded claim recovery,
  immutable tick replay, and fail-closed inventory or notification errors.
- Shared CLI tests prove standalone/native artifact, Git-pinned plan admission,
  reconciliation, and attended-review parity, dry-run default behavior, exact
  preview-digest apply gates, bounded direct rationale input and output, and
  nonzero stale or missing-identity exits without live profile mutation.
- Artifact/archive tests prove exact-ID archive lookup, active/archive byte
  equivalence, supplemental-member exclusion, private-mode revalidation,
  bounded member reads, digest failure, and atomic mode-`0600` export.
- Artifact-curator tests prove terminal classification, deterministic age and
  pin transitions, compare-and-swap private state, preview-gated CLI parity,
  lock contention, verified archive-before-cleanup ordering, interruption
  convergence, tamper/collision rejection, safe restore, exact access wiring,
  and cross-profile isolation without a live Hermes profile.
- Curator-Cron tests use fake public CLI boundaries and disposable profile roots
  to prove exact script/job/policy identity, private schedule state, dry-run and
  literal-confirm apply gates, setup replay, exact-ID update/removal, silent
  disabled ticks, one-time archive convergence, and fail-closed policy/script
  drift without touching a live Hermes profile.
- Project-cycle admission tests prove standalone/native mode and candidate
  parity, comparison-mode candidate requirements, improve-mode rejection, and
  exact dry-run/apply forwarding before adapter mutation.
- Fresh-evaluator tests cover all three cycle modes, candidate/controller
  separation, isolation receipts, credential-free homes, durable baseline
  identity and ordering, immutable evidence, deterministic/repeated/
  observational verdicts, controlled lesson-reuse deltas, graph staleness,
  clean teardown, dirty-worktree quarantine, and exact blockers.
- Restricted-container tests pin image identity, dry-run/apply parity, denied
  network, fresh tmpfs home, bounded mounts/output, non-root execution,
  credential exclusion, image-volume rejection, and fail-closed probe output.
- Increment-reconciliation tests bind planned mutable paths, frozen diffs,
  observed content, artifact and activation identities, producers, and nearest
  owning DOX scope before retention can become eligible.
- Fake-context tests for plugin tool and skill registration.
- Temporary-repository tests for policy services and JSON tool handlers.
- Plan-admission tests use disposable Git repositories to prove exact-blob
  parsing, canonical packet round trips, pending-phase ordering, dependency
  graph rejection, immutable source-artifact replay, direct-parent checkpoint
  binding, and dirty/path/symlink/binary/tampered-evidence fail-closed behavior
  without mutating the operator checkout.
- Fake-inventory tests for exact external-skill prerequisites and host errors.
- Fake command/registry tests for dry-run installation, pinned revisions, content digests, post-apply verification, and refused recursive installation.
- Pack-service and dashboard-route tests prove declared-skill-only bounded
  content, validation/check parity, canonical preview identity, stale-preview
  rejection, literal confirmation, and post-install verification.
- Dashboard review-route, GitHub Project link, and asset tests prove path-free exact evidence,
  server-derived attended identity, literal diff rendering, preview/apply parity,
  single-ledger plan/review snapshot binding, stale or unchecked rejection, and
  successor-plan navigation without arbitrary dispatch, commit, or push authority.
  Artifact dashboard coverage additionally proves exact opaque selectors,
  path-free errors, digest-verified bytes, literal escaped text, authenticated
  download, and preview-confirm curator dispatch.
- Checkout lifecycle tests use fake Git boundaries and temporary working trees to
  prove bounded NUL status parsing, receipt-TTL decisions, clone/swap rollback,
  archive-before-wipe failure safety, clean unowned adoption, backup pruning, and
  path-free digest-confirmed dashboard actions.
- Fake host-dispatch tests for ledger-owned approval, worker rejection,
  restart-safe plan-parented post-gate graphs, and idempotent Kanban mapping.
- Review-disposition tests prove structured review bounds, exact evidence-tuple
  binding, worker-context rejection for attended decisions, and absence of a
  delivery card before exact attended acceptance.
- Review-revision tests prove mutation-free canonical previews, stale identity
  rejection, durable intent before host mutation, retry after archive/worktree
  failures, revision-addressed Plan cards, preserved historical evidence, and
  fresh plan approval before a new worktree or post-gate graph.
- Constraint-card tests prove policy-aware idempotency, global and phase-specific
  projection, explicit board and constraint-revision identity, explicit null
  identity, the exact 8,192-character rendered-body boundary, and fail-closed
  missing or oversized content.
- Bundled worker-contract tests for stage tool mapping, structured handoffs,
  external-versus-plugin-qualified skill names, blocking, retries, and immutable
  post-capture scope.
- Bundled setup-skill tests pin the current start schema, explicit confirmation
  boundary, and dashboard-independent request parity.
- Dashboard read-model tests keep router registration host-isolated and prove the
  finite recommendation vocabulary, exact approval identity, and absence of
  persisted live-card status, including concurrent first-request service
  initialization.
- Runbook tests prove sanitized health identity, complete runbook-section
  coverage, guidance-only host lifecycle commands, and exact-ID resume without
  a Start workflow request.
- Initialization tests prove zero-write preview, stale-digest rejection, literal
  confirmation, and idempotent schema creation; dashboard diagnosis tests prove
  trusted registration-derived inputs and reject browser-supplied paths.
- Dashboard asset tests pin the supported tab and slot, authenticated read-only
  polling, confirmation-gated setup writes, required empty/error/progress states,
  selected-workflow detail hydration without duplicate cards, and narrow
  host-theme styling.
- Setup wizard tests prove preview/decline non-mutation, exact start delegation,
  request validation, narrowly scoped Hermes inventory commands, and profile
  parsing when valid names overflow Hermes' display columns.
- Shared-parser and fake-command tests proving native Hermes and standalone CLI
  service calls, public Kanban command translation, JSON, and exit codes remain
  equivalent.
- Production-adapter tests use fake `gh` and `hermes send` boundaries to prove
  strict issue normalization, ready-actor authority, replay-safe claims and
  completed or not-planned closure, exact claim-label release, immutable
  completion and cancellation records,
  credential-minimal child environments, private-destination exclusion, and
  event-bound receipts. Project-cycle composition tests prove admission and
  completion/cancellation dry-run non-mutation and exact preview-identity
  rejection before claim, workflow, issue, notification, or terminal-artifact
  mutation. Completion-preview tests also prove repeated successful command
  outputs collapse to one canonical sorted digest identity.
- Strict credential-binding and prerequisite-report tests cover guide/CLI ID
  parity, redaction, pass/blocked/not-run/error aggregation, bounded `GH_TOKEN`
  child environments, and complete, missing, malformed, denied, unavailable,
  and partial host states.
- Temporary Git worktree tests for the approved end-to-end executable slice.
- Revision-addressed artifact tests cover policy and plan supersession, exact
  ledger references, historical-byte retention, create-or-verify replay,
  conflicting content, unsafe relative paths, and symlink rejection.
- Artifact-access tests cover deterministic opaque IDs, ledger-only catalogs,
  all active reference kinds, strict source-bound plan summaries, bounded
  digest-verified text, path/symlink/binary rejection, private collision-safe
  export, digest-equivalent download bytes, legacy readability, and mutation-free reads.
- Archive I/O tests cover deterministic verified tar/gzip round trips, strict
  member paths and bounds, source-file safety, tampering, interrupted writes,
  retry conflicts, and safe idempotent restore.
- Cross-pack fixture tests proving Addyosmani and AI-DLC use the same engine path
  and leave activation-gated structured handoff history across all executable
  cards.
- Subprocess tests for dependency-free repository verification scripts.
- `test_hermes_compatibility_probe.py` validates host-output parsing, boundary
  drift failures, complete explicit candidate identities, and isolated-home
  cleanup through subprocesses.
- `test_hermes_plugin_compatibility_probe.py` validates public plugin inventory,
  fresh native/standalone pack and admission-preview parity, preview mutation
  rejection, directory/entry-point evidence, active-home exclusion, and cleanup
  through subprocesses.
- `test_hermes_dashboard_compatibility_probe.py` validates dashboard discovery,
  exact packaged asset serving, router auth gating, literal-confirmation behavior,
  explicit candidate identity, and isolated cleanup through subprocesses.
- `test_hermes_support_matrix.py` validates exact-wheel preflight, complete host
  tuples, two runs of the core, entry-point, directory, and dashboard probes,
  byte-identical repetition output, entry-point metadata restoration, fail-closed
  core and admission field-level evidence checks, private canonical output,
  active-home exclusion, and cleanup on failure.
- `test_release_workflow.py` keeps the exact-wheel matrix release-only, pins the
  documented Hermes checkout and tracking identity, transfers one checked wheel,
  prevents editable-Daidala drift, and requires the pinned host dashboard build.
- Release-content regressions for forbidden runtime paths, secret signatures,
  and superseded project identity in source and wheel paths or content.
- Build/install smoke tests for directory entry points, wheel resources, and Hermes entry-point metadata.
- `fixtures/uc03_pack_eval/` is the frozen Phase 5D package-resource baseline.
  Its eight packet-addressed files are experiment inputs; only
  `resource_fixture/catalog.py` may change inside an approval-owned evaluation
  worktree. Tests and resource bytes remain immutable across both pack legs.
- `fixtures/dashboard_phase0_browser_probe.html` is the host-isolated artifact
  browser fixture. It mocks only authenticated Hermes SDK and Daidala API
  boundaries and never reads or mutates a real profile.

## Local Contracts

- Tests must not mutate `~/.hermes`, start a gateway, use network services, or call a live model.
- Use real package resources and temporary files; mock only the Hermes host boundary.

## Work Guidance

- Every new policy operation requires positive, policy-violation, and persistence tests.
- Plan-source tests must cover canonical packet serialization plus malformed
  headers/status evidence, duplicate or cyclic dependencies, source revision,
  tree entry, path, encoding, and working-tree drift rejection.
- Checkpoint tests must use temporary Git history and prove the exact predecessor
  identity, one-parent source revision, delivered non-plan diff, reserved plan
  path/status projection, and digest-verified review/delivery evidence; never
  substitute mutable checkout state or inferred artifact paths.
- Pure schema phases require round-trip, canonical digest, unknown-field,
  duplicate/collision, bound, and stale-identity tests without live services.
- Skill activation coverage must prove strict serialization, exact pack-stage
  decisions, linear supersession, pending/finalized recovery, exclusive artifact
  creation, and fail-closed evidence operations for missing, pending, or blocked
  manifests.
- Activation tool tests set real Kanban worker environment context and prove
  absent, wrong-board, wrong-card, matching-card, and unrelated handler `task_id` behavior.
- The shared worker-evidence validator has wrong-board and stale-card regression coverage.
- Constraint revisions must prove prior cards and activation manifests are stale
  while their immutable history remains serialized.
- Constraint replacement coverage must prove exact approval binding, durable
  invalidation before host mutation, owned-worktree cleanup, obsolete-card
  archival, fresh define/plan creation, idempotent retry, and cross-pack behavior.
- Review revision coverage must prove the revision/successor artifact digests,
  exact source tuple, no arbitrary-path forwarding, durable retry markers,
  recovery after artifact-write, recorded-ID archive, owned-worktree, and
  successor-card failures without duplicate retry effects, historical evidence,
  successor Plan activation, and no direct phase-rewind surface.
- Tool and CLI constraint-source coverage must prove inline/file parity, exact
  skill-directory digest verification, strict single-fence extraction, and
  identical standalone/native service dispatch.
- Artifact persistence coverage must prove every stage resolves its current
  policy/plan directory and that retries never overwrite or infer historical
  evidence.
- Every new packaged resource requires a wheel-content assertion.

## Verification

```bash
pytest
python3 -m unittest discover -s tests/fixtures/uc03_pack_eval -p 'test_*.py'
```

## Child DOX Index

*(empty — `tests/` is a flat leaf.)*

See [`/AGENTS.md`](../AGENTS.md).
