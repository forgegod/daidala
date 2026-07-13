# Daidala brand assets

![Daidala](logo.svg)

Daidala is a Hermes-native AI workshop that moves skill-backed work through
interchangeable workflow packs and one explicit human approval gate—without
introducing a second orchestration server.

The mark is a crafted `D` with a smooth bowl and a Greek-meander cut through its
lower edge. The ordered opening suggests staged work leaving the workshop as
delivery.

Short tagline:

> Your daily driver for crafted, human-approved work.

## Assets

| File | Use |
|---|---|
| `logo.svg` | Canonical transparent lockup. |
| `logo-mark.svg` | Canonical transparent crafted-D mark. |
| `logo-256.png`, `logo-512.png`, `logo-1024.png` | Raster lockup renders. |
| `social-card.svg`, `social-card.png` | Social preview with lifecycle and product boundary. |

The palette is gold `#ffc72c`, amber `#f9a23a`, and—on the social card only—navy `#1a1f3a`.

## Regeneration

Install development dependencies and ensure Inkscape is available, then run from any directory:

```bash
/path/to/daidala/.venv/bin/python /path/to/daidala/assets/build_brand_assets.py
```

`build_brand_assets.py` converts the bundled OFL-licensed Libre Baskerville font to SVG paths, writes the SVG sources, and renders PNG files from those sources. Generated files must not be hand-edited.
