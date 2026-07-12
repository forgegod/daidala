# tests/

## Purpose

Prove the deterministic pack and policy-ledger models, durable persistence, strict
tool boundaries, Hermes plugin registration contract, and packaged-resource
completeness without touching a real Hermes profile.

## Ownership

- Unit tests for pack loading and validation.
- Fake-context tests for plugin tool and skill registration.
- Temporary-repository tests for policy services and JSON tool handlers.
- Fake-inventory tests for exact external-skill prerequisites and host errors.
- Fake command/registry tests for dry-run installation, pinned revisions, content digests, post-apply verification, and refused recursive installation.
- Fake host-dispatch tests for approval-gated, restart-safe, idempotent Kanban mapping.
- Constraint-card tests prove policy-aware idempotency, global and phase-specific
  projection, approval-card exclusion, explicit board and constraint-revision
  identity, explicit null identity, and fail-closed missing content.
- Bundled worker-contract tests for stage tool mapping, structured handoffs,
  external-versus-plugin-qualified skill names, blocking, retries, and immutable
  post-capture scope.
- Bundled setup-skill tests pin the current start schema, explicit confirmation
  boundary, and dashboard-independent request parity.
- Dashboard read-model tests keep router registration host-isolated and prove the
  finite recommendation vocabulary, exact approval identity, and absence of
  persisted live-card status.
- Dashboard asset tests pin the supported tab and slot, authenticated read-only
  polling, confirmation-gated setup writes, required empty/error/progress states,
  and narrow host-theme styling.
- Setup wizard tests prove preview/decline non-mutation, exact start delegation,
  request validation, and narrowly scoped Hermes inventory commands.
- Shared-parser and fake-command tests proving native Hermes and standalone CLI
  service calls, public Kanban command translation, JSON, and exit codes remain
  equivalent.
- Temporary Git worktree tests for the approved end-to-end executable slice.
- Cross-pack fixture tests proving Addyosmani and AI-DLC use the same engine path
  and leave activation-gated structured handoff history across all executable
  cards.
- Subprocess tests for dependency-free repository verification scripts.
- `test_hermes_compatibility_probe.py` validates host-output parsing, boundary
  drift failures, and isolated-home cleanup through subprocesses.
- `test_hermes_dashboard_compatibility_probe.py` validates dashboard discovery,
  asset serving, API auth gating, and isolated cleanup through subprocesses.
- `test_release_workflow.py` keeps the live probe release-only and pinned to the
  documented supported Hermes upstream revision.
- Release-content regressions for forbidden runtime paths and secret signatures.
- Build/install smoke tests for directory entry points, wheel resources, and Hermes entry-point metadata.

## Local Contracts

- Tests must not mutate `~/.hermes`, start a gateway, use network services, or call a live model.
- Use real package resources and temporary files; mock only the Hermes host boundary.

## Work Guidance

- Every new policy operation requires positive, policy-violation, and persistence tests.
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
- Tool and CLI constraint-source coverage must prove inline/file parity, exact
  skill-directory digest verification, strict single-fence extraction, and
  identical standalone/native service dispatch.
- Every new packaged resource requires a wheel-content assertion.

## Verification

```bash
pytest
```

## Child DOX Index

*(empty — `tests/` is a flat leaf.)*

See [`/AGENTS.md`](../AGENTS.md).
