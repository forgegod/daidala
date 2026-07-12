# dashboard/

## Purpose

Provide the optional Wingstaff extension for the existing Hermes dashboard.

## Ownership

- `manifest.json` declares the `/wingstaff` tab, `sessions:top` slot, assets, and backend router.
- `plugin_api.py` mounts the profile-safe read model and narrowly scoped setup routes.
- `dist/index.js` renders workflow progress, pending decisions, and confirmation-gated setup.
- `dist/style.css` adapts the extension to host themes and narrow layouts.

## Local Contracts

- Register only documented Hermes dashboard SDK surfaces.
- Browser requests authenticate with the host-provided session token and call only scoped Wingstaff routes.
- Workflow polling is read-only. Setup may POST only board creation, preview, and confirmed start requests.
- Preview and declined setup must not mutate; start requires a literal checked confirmation.
- Poll no faster than every five seconds while visible, stop while hidden, and retain manual refresh.
- Treat API responses as snapshots; never authorize workflow operations from client state.

## Work Guidance

- Keep the JavaScript dependency-free and compatible with the React instance exposed by the Hermes plugin SDK.
- Keep the backend router thin; deterministic policy remains under `wingstaff/`.

## Verification

```bash
pytest tests/test_dashboard_assets.py tests/test_dashboard_api.py
```

Browser verification uses an isolated supported Hermes dashboard and desktop plus narrow Chromium screenshots.

## Child DOX Index

*(empty — `dist/` contains generated browser assets governed here.)*

See [`/AGENTS.md`](../AGENTS.md).
