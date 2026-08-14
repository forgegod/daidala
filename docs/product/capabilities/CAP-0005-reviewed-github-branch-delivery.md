# CAP-0005: Reviewed GitHub branch delivery

**Status:** implemented
**Primary surface:** Daidala workflow detail → Branch delivery

## Outcome

After an attended actor accepts a non-blocking exact review, they can preview and
explicitly commit the reviewed diff to one Daidala-owned branch, push that exact
commit, and receive a path-free branch/commit receipt.

## Behavior

- `daidala deliver <workflow-id>` and the workflow-detail Branch delivery panel
  use one deterministic delivery service. Both are preview-only until the exact
  preview digest and explicit confirmation are supplied.
- Delivery requires one unique trusted registration for the target checkout, its
  unchanged verified remote and committed manifest, `release.allow_commit: true`,
  `release.allow_push: true`, an accepted non-blocking review disposition, an
  activated Deliver card, and an owned reviewed worktree whose diff and changed
  paths still match captured implementation evidence.
- The service derives only `daidala/<workflow-id>` and commits only the reviewed
  changed paths. It rejects a conflicting local or remote branch, a stale
  preview, changed evidence, an unavailable credential binding, or a nonmatching
  recorded commit.
- The only accepted credential binding is the profile-local
  `github-repository-delivery` alias. Its resolved value is passed only through a
  temporary `GIT_ASKPASS` environment for bounded Git remote inspection/push; it
  never appears in URLs, command arguments, Git configuration, ledger receipts,
  dashboard responses, or CLI JSON.
- The alias is bound into the canonical preview and durable authorization that
  control delivery, but public CLI/dashboard preview output exposes only whether
  the credential is available.
- A retry resumes only the same preview-bound commit and verifies the remote ref.
  It recovers a post-commit persistence interruption without creating a second
  commit. After the confirmed push, Daidala records the receipt, completes the
  Deliver card, and releases only the owned worktree. A retry after an interrupted
  worktree release requires the live Deliver card's sole completed run to carry
  that exact non-secret branch/commit receipt; unrelated completed-run metadata
  fails closed. It never opens a pull request, merges, updates a default branch,
  creates a release, or publishes.

## Evidence

### Runtime

- [`daidala/delivery.py`](../../../daidala/delivery.py) — preview-bound branch, reviewed-diff, credential, Git, remote-ref, and retry boundary.
- [`daidala/service.py`](../../../daidala/service.py) — durable authorization, delivery receipt, Kanban completion, and owned-worktree release.
- [`daidala/cli.py`](../../../daidala/cli.py) — native and standalone `deliver` preview/apply adapter.
- [`dashboard/plugin_api.py`](../../../dashboard/plugin_api.py) — exact path-free dashboard preview/apply boundary.
- [`dashboard/dist/index.js`](../../../dashboard/dist/index.js) — Branch delivery evidence, confirmation, unavailable, and completed states.

### Tests

- [`tests/test_delivery.py`](../../../tests/test_delivery.py) — exact local branch commit/push, absent credential, conflicting remote, commit-persistence and worktree-release recovery, completed-run receipt validation, and token-redaction coverage.
- [`tests/test_cli.py`](../../../tests/test_cli.py) — native/standalone delivery command contract.
- [`tests/test_dashboard.py`](../../../tests/test_dashboard.py) — path-free completed-delivery projection.
- [`tests/test_dashboard_api.py`](../../../tests/test_dashboard_api.py) — exact delivery request and response boundary.
- [`tests/test_dashboard_assets.py`](../../../tests/test_dashboard_assets.py) — browser credential/path exclusion and preview-confirm contract.

## Contracts

- [Architecture](../../01-architecture.md)
- [Workflow state and authority](../../02-workflow-state.md)
- [Security](../../06-security.md)
- [Operator runbook](../../07-runbook.md)

## Links

- [CHG-0009](../../changes/archive/CHG-0009-github-repository-registration-and-delivery.md)
- [HTML wireframe](../wireframes/html/CAP-0005-reviewed-github-branch-delivery.html)
- [PNG wireframe](../wireframes/exports/CAP-0005-reviewed-github-branch-delivery.png)
