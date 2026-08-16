# CAP-0001: Approval-gated workflow execution

**Status:** implemented
**Primary surface:** none; operator presentation is owned by CAP-0003

## Outcome

An operator can execute a workflow through deterministic lifecycle gates while exact approval, verification, attended review, and delivery authority remain explicit and independently enforced.

## Behavior

- A workflow ledger records policy facts and immutable artifact identities while Hermes Kanban owns live card status.
- Plan approval binds the exact current plan revision, plan digest, constraint revision and digest, and any admitted source-packet digest; replacing the plan or constraints invalidates prior authority.
- Implementation cannot start before approval, and unsuccessful verification cannot advance to accepted delivery.
- Automated review is evidence only. An attended disposition is required before delivery or a revision-addressed successor plan is authorized.
- Start refuses to create or resume a graph when a selected worker profile's Hermes gateway is not running, or when a live card assignee does not match the workflow-bound stage profile.

## Evidence

### Runtime

- [`daidala/workflow.py`](../../../daidala/workflow.py) — pure policy transitions including exact approval and verification gates.
- [`daidala/service.py`](../../../daidala/service.py) — approval-gated card graph, worktree, review, revision, delivery coordination, worker-gateway start preflight, and assignee/stage-profile alignment.
- [`daidala/execution.py`](../../../daidala/execution.py) — revision-addressed artifacts and detached implementation worktrees.

### Tests

- [`tests/test_workflow.py`](../../../tests/test_workflow.py) — exact approval, invalidation, post-gate facts, and serialization behavior.
- [`tests/test_execution.py`](../../../tests/test_execution.py) — approval-gated execution and failed-verification delivery rejection.
- [`tests/test_review_disposition.py`](../../../tests/test_review_disposition.py) — exact attended review binding and delivery authority.
- [`tests/test_gateway.py`](../../../tests/test_gateway.py) — worker-gateway status classification and probe.
- [`tests/test_assignee_alignment.py`](../../../tests/test_assignee_alignment.py) — start preflight and activation fail-closed on assignee/stage-profile mismatch.

## Contracts

- [Workflow state and authority](../../02-workflow-state.md)
- [Lifecycle stages](../../05-lifecycle-stages.md)
- [Operator runbook](../../07-runbook.md)

## Links

- [Initial records-adoption receipt](../../changes/archive/CHG-0001-adopt-application-records.md)
