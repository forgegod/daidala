# docs/changes/

## Purpose

Own active material-change progress and archived implementation receipts.

## Ownership

- `README.md` defines the CHG lifecycle and canonical shape.
- `active/CHG-*.md` files are the sole mutable progress authority for current material changes.
- `archive/CHG-*.md` files are completed or cancelled implementation receipts.
- `templates/change.md` is the starting shape for a new change record.

## Local Contracts

- Create or resume one active CHG before implementation changes material behavior.
- Every CHG preserves its source request and references valid affected CAP IDs.
- An `in-progress` CHG has exactly one `in-progress` phase. A pending CHG has no
  active phase, and a blocked CHG marks the blocking phase `blocked`; completed
  phase status requires recorded verification evidence.
- Active CHGs are never `done` or `cancelled`; archived CHGs are only `done` or `cancelled`.
- CHGs own progress, not current product behavior. CAPs, runtime source, and tests own the implemented result.
- Existing `docs/plans/` files remain historical and never compete with CHG status.

## Work Guidance

- Update the active CHG before scope, sequencing, decisions, or verification gates change.
- Keep short-lived implementation reasoning here; promote only durable cross-cutting rules to their live contract owner.
- Archive the CHG only after affected CAPs and qualifying wireframes are current and the full repository gate passes.

## Verification

```bash
python scripts/check_records.py .
python scripts/check_md_links.py .
```

## Child DOX Index

*(empty — active, archive, and template directories are governed by this boundary.)*

See [`/AGENTS.md`](../../AGENTS.md), [`docs/AGENTS.md`](../AGENTS.md), and [`docs/product/AGENTS.md`](../product/AGENTS.md).
