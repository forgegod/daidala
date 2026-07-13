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
- `probe_hermes_dashboard_compatibility.py` proves the pinned release host's
  dashboard extension surface (manifest discovery, static asset serving, plugin
  API mount with auth gating) against an isolated profile.

## Local Contracts

- Scripts must run on Python 3.11 or newer with no project-runtime side effects.
- Verification scripts return zero on success and non-zero with actionable file
  and line diagnostics on failure.
- Release-content verification rejects the superseded project identity in
  tracked paths, decodable tracked content, wheel paths, and decodable wheel
  content without retaining that identity in the checker source.
- The live Hermes compatibility probe is release-only. It must clean its isolated
  home on success and failure and must not create profiles, gateways, or files in
  the operator's active Hermes configuration.
- The dashboard compatibility probe requires the pinned Hermes checkout's web
  distribution to be built before invocation; the probe uses `--skip-build` and
  must not install or build host frontend dependencies itself.
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
