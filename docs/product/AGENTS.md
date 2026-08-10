# docs/product/

## Purpose

Own concise records of currently implemented material behavior and static visual references for primary human-facing capability surfaces.

## Ownership

- `README.md` is the capability index and record contract.
- `capabilities/CAP-*.md` files describe current falsifiable behavior and link runtime source, tests, and detailed contracts.
- `wireframes/` owns generated CAP-linked HTML review sources, PNG exports, the screen manifest, and the generator.
- `templates/capability.md` is the starting shape for a new capability record.

## Local Contracts

- A CAP is current behavior, never progress state or unverified intent.
- Every implemented CAP links at least one runtime source and one executable test file.
- CAP IDs are stable and unique; update the existing CAP when its material outcome changes.
- Primary human-facing capability surfaces link matching HTML and PNG wireframes generated from one repository-owned source.
- Detailed architecture, security, lifecycle, and operator rules remain in their existing numbered documentation owners.

## Work Guidance

- Read the affected CAP and active CHG before changing material behavior.
- Add behavior and evidence in the same vertical slice as implementation and tests.
- Use synthetic data in wireframes and keep generated HTML, PNG, index, and manifest synchronized.
- Do not create CAPs for formatting, dependency updates, or internal refactors that preserve observable behavior.

## Verification

```bash
python scripts/check_records.py .
python scripts/check_md_links.py .
```

For wireframes, regenerate artifacts and render the HTML at 1440 × 960 before running the checks.

## Child DOX Index

*(empty — capability records and wireframes are governed by this boundary.)*

See [`/AGENTS.md`](../../AGENTS.md), [`docs/AGENTS.md`](../AGENTS.md), and [`docs/changes/AGENTS.md`](../changes/AGENTS.md).
