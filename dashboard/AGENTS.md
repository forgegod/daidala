# dashboard/

## Purpose

Provide the optional Daidala extension for the existing Hermes dashboard.

## Ownership

- `manifest.json` declares the `/daidala` tab, `sessions:top` slot, assets, and backend router.
- `plugin_api.py` mounts the profile-safe read model and narrowly scoped setup routes.
- `dist/index.js` renders workflow progress, pending decisions, and confirmation-gated setup.
- `dist/style.css` adapts the extension to host themes and narrow layouts.

## Local Contracts

- Register only documented Hermes dashboard SDK surfaces.
- Browser requests use the host SDK's authenticated `fetchJSON` helper and call
  only scoped Daidala routes; never read the host session token directly.
- `plugin_api.py` imports the stable `daidala` package exposed by both pip and
  the repository-root directory entry point.
- Initialize the process-local dashboard service exactly once under concurrent
  first requests; route threads must not race SQLite schema initialization.
- Workflow polling is read-only. Mutations are limited to board creation,
  confirmed setup, and compare-and-swap constraint replacement.
- Preview and declined setup must not mutate; start requires a literal checked confirmation.
- Constraint preview is non-mutating; replacement requires the displayed current
  digest and explicit invalidation confirmation.
- Poll no faster than every five seconds while visible, stop while hidden, and retain manual refresh.
- Treat API responses as snapshots; never authorize workflow operations from client state.

## Work Guidance

- Keep the JavaScript dependency-free and compatible with the React instance exposed by the Hermes plugin SDK.
- Keep the backend router thin; deterministic policy remains under `daidala/`.

## Verification

```bash
pytest tests/test_dashboard_assets.py tests/test_dashboard_api.py
```

Browser verification uses an isolated supported Hermes dashboard and desktop plus narrow Chromium screenshots.

## Child DOX Index

*(empty — `dist/` contains generated browser assets governed here.)*

See [`/AGENTS.md`](../AGENTS.md).
