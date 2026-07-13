# docs/evaluation-results/

## Purpose

Own versioned, redacted self-improvement evaluation definitions and result records.

## Ownership

- `v1/experiment-limits.yaml` defines the bounded first evaluation envelope.
- `v1/daidala-self-improvement.md` records the stable case matrix and observed results.

## Local Contracts

- Result records never invent live evidence; unexecuted cases remain `not-run` and unavailable prerequisites remain `blocked`.
- Evidence references are content-addressed and contain no credentials, connection strings, profile dumps, private Kanban data, or unbounded logs.
- Stable `TC-Fxx-nn` IDs are not renumbered after evidence cites them.
- Versioned results record observations; they do not override runtime policy, the project manifest, trusted registration, or applicable DOX contracts.

## Work Guidance

- Keep experiment limits separate from Hermes provider/model configuration and credentials.
- Record exact non-secret identities, commands, exit codes, digests, receipts, and prohibited side effects.
- Reconcile every retained repository document with its increment manifest and owning DOX chain.

## Verification

```bash
python scripts/check_md_links.py .
```

## Child DOX Index

*(empty — version directories contain records, not independent work contracts.)*

See [`docs/AGENTS.md`](../AGENTS.md) and [`/AGENTS.md`](../../AGENTS.md).
