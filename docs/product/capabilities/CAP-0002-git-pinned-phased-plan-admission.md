# CAP-0002: Git-pinned phased-plan admission

**Status:** implemented
**Primary surface:** none; CLI and dashboard adapters present the service behavior

## Outcome

An operator can admit one pending phase from an exact committed Git plan, approve its immutable source identity, and advance to a later phase only through a verified delivery checkpoint and fresh approval.

## Behavior

- Admission reads one repository-relative UTF-8 plan blob from an exact source revision and rejects dirty drift, path traversal, symlinks, malformed phase state, and invalid dependencies.
- Preview is non-mutating and apply requires the exact preview digest; admitted metadata excludes private checkout paths and source bytes.
- Approval binds the imported plan digest and source-packet digest, so approval for one source revision or phase cannot authorize another.
- A successor phase requires a direct-child checkpoint containing delivered changes plus the allowed plan-status projection, durable review/delivery evidence, and a fresh workflow approval.

## Evidence

### Runtime

- [`daidala/plan_admission.py`](../../../daidala/plan_admission.py) — strict Git-object parsing, phase selection, and checkpoint validation.
- [`daidala/service.py`](../../../daidala/service.py) — preview-gated imported-plan persistence and post-approval graph creation.
- [`daidala/workflow.py`](../../../daidala/workflow.py) — canonical source packets and exact packet-bound approval.
- [`daidala/cli.py`](../../../daidala/cli.py) — standalone and native `start-from-plan` preview/apply boundary.

### Tests

- [`tests/test_plan_admission.py`](../../../tests/test_plan_admission.py) — exact-blob admission, malformed input rejection, checkpoint validation, and two-phase fresh-approval chain.
- [`tests/test_cli.py`](../../../tests/test_cli.py) — native/standalone preview and apply parity.
- [`tests/test_tools.py`](../../../tests/test_tools.py) — private source handling and mutation-free preview behavior.

## Contracts

- [Getting started](../../00-getting-started.md)
- [Workflow state and authority](../../02-workflow-state.md)
- [Operator runbook](../../07-runbook.md)

## Links

- [Initial records-adoption receipt](../../changes/archive/CHG-0001-adopt-application-records.md)
