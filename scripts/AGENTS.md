# scripts/

## Purpose

Own dependency-free development and repository verification utilities.

## Ownership

- `check_md_links.py` validates local Markdown file links and heading anchors.

## Local Contracts

- Scripts must run on Python 3.11 or newer with no project-runtime side effects.
- Verification scripts return zero on success and non-zero with actionable file
  and line diagnostics on failure.
- Ignore generated, virtual-environment, VCS, and cache directories.

## Verification

```bash
python scripts/check_md_links.py .
ruff check scripts
```

## Child DOX Index

*(empty — `scripts/` is a flat leaf.)*

See [`/AGENTS.md`](../AGENTS.md).
