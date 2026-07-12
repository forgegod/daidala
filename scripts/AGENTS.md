# scripts/

## Purpose

Own dependency-free development and repository verification utilities.

## Ownership

- `check_md_links.py` validates local Markdown file links and heading anchors.
- `check_release_contents.py` rejects runtime state and high-confidence secret
  signatures from tracked source and wheel payloads.
- `probe_hermes_compatibility.py` creates an isolated `HERMES_HOME` and verifies
  the pinned release host's exact identity, policy-skill digest boundary, public
  Kanban lifecycle, and worker-context body limits.

## Local Contracts

- Scripts must run on Python 3.11 or newer with no project-runtime side effects.
- Verification scripts return zero on success and non-zero with actionable file
  and line diagnostics on failure.
- The live Hermes compatibility probe is release-only. It must clean its isolated
  home on success and failure and must not create profiles, gateways, or files in
  the operator's active Hermes configuration.
- Ignore generated, virtual-environment, VCS, and cache directories.
- Markdown checking supports fenced and indented code exclusion, UTF-8 BOMs,
  headings indented by up to three spaces, duplicate/custom anchors, reference
  links, images, external URLs, and quoted or parenthesized link titles.

## Verification

```bash
python scripts/check_md_links.py .
python scripts/check_release_contents.py .
python scripts/probe_hermes_compatibility.py
pytest
ruff check scripts
```

## Child DOX Index

*(empty — `scripts/` is a flat leaf.)*

See [`/AGENTS.md`](../AGENTS.md).
