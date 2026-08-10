# Change records

Change records are the sole repository-tracked progress authority for material behavior changes. Current behavior belongs in capability records; detailed architecture and operations remain in their existing documentation owners.

## Lifecycle

1. Classify the request and identify affected CAP IDs.
2. Create or resume one `active/CHG-NNNN-<slug>.md` before implementation.
3. Preserve an external ticket link or `Direct operator request: <verbatim request>`; never invent a ticket.
4. While the CHG status is `in-progress`, keep exactly one phase `in-progress`
   and run each phase's executable gate before marking it done.
5. Update affected CAPs, runtime behavior, tests, and qualifying wireframes in one vertical slice.
6. Run record validation, affected tests, and the repository gate.
7. Mark the CHG `done` and move it to `archive/` as an implementation receipt.

Existing files under [`docs/plans/`](../plans/AGENTS.md) are historical
provenance. Do not create new plan files or reuse them as mutable progress
authorities.

## Canonical shape

Each CHG contains:

1. `# CHG-NNNN: <title>`
2. `**Status:** pending`, `in-progress`, `blocked`, `done`, or `cancelled`
3. `**Source request:** <external link or direct operator request>`
4. `**Affected capabilities:** <comma-separated CAP IDs>`
5. `**Created:** YYYY-MM-DD`
6. `## Outcome`
7. `## Scope`
8. `## Phases` with phase, status, and verification gate columns
9. `## Decisions`
10. `## Evidence`

Active CHGs cannot be `done` or `cancelled`. Archived CHGs must be `done` or `cancelled`. IDs are stable and never reused.

## Verification

```bash
python scripts/check_records.py .
python scripts/check_md_links.py .
```
