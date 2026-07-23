# scripts/

## Purpose

Own dependency-free development and repository verification utilities.

## Ownership

- `check_md_links.py` validates local Markdown file links and heading anchors.
- `check_release_contents.py` rejects runtime state and high-confidence secret
  signatures from tracked source and wheel payloads.
- `probe_hermes_compatibility.py` creates an isolated `HERMES_HOME` and verifies
  an exact expected host identity, policy-skill digest boundary, public Kanban
  lifecycle, and worker-context body limits. The expected identity defaults to
  the pinned release host and requires a complete three-field override.
- `probe_hermes_plugin_compatibility.py` verifies public plugin inventory where
  exposed, fresh-process native CLI loading, standalone/native pack and
  admission-preview parity, and entry-point or isolated directory discovery
  without using an active profile.
- `probe_hermes_dashboard_compatibility.py` proves the pinned release host's
  dashboard extension surface using the packaged manifest, assets, and router;
  it also proves preview and declined setup remain non-mutating.
- `run_hermes_support_matrix.py` preflights one exact wheel, installs it into
  complete explicit Hermes host tuples, and runs every compatibility probe twice
  per host before bounded canonical evidence and cleanup.

## Local Contracts

- Scripts must run on Python 3.11 or newer with no project-runtime side effects.
- Verification scripts return zero on success and non-zero with actionable file
  and line diagnostics on failure.
- Release-content verification rejects the superseded project identity in
  tracked paths, decodable tracked content, wheel paths, and decodable wheel
  content without retaining that identity in the checker source.
- Hermes compatibility probes must clean their isolated homes on success and
  failure, reject roots inside an inherited active `HERMES_HOME`, and must not
  create profiles, gateways, or files in the operator's active configuration.
- The dashboard compatibility probe requires the pinned Hermes checkout's web
  distribution to be built before invocation; the probe uses `--skip-build` and
  must not install or build host frontend dependencies itself.
- Exact-wheel matrix runs require a caller-supplied SHA-256 digest, successful
  Twine and release-content checks, complete host identity tuples, fresh probe
  homes, and literal-confirmation plus preview-mutation evidence.
- Ignore generated, virtual-environment, VCS, and cache directories.
- Markdown checking supports fenced and indented code exclusion, UTF-8 BOMs,
  headings indented by up to three spaces, duplicate/custom anchors, reference
  links, images, external URLs, and quoted or parenthesized link titles.

## Verification

```bash
python scripts/check_md_links.py .
python scripts/check_release_contents.py .
python scripts/probe_hermes_compatibility.py
python scripts/probe_hermes_plugin_compatibility.py
python scripts/probe_hermes_dashboard_compatibility.py
pytest
ruff check scripts
```

## Child DOX Index

*(empty — `scripts/` is a flat leaf.)*

See [`/AGENTS.md`](../AGENTS.md).
