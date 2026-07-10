# Wingstaff brand assets

![Wingstaff](logo.svg)

Wingstaff is a Hermes-native staff of specialist agents that moves software work through interchangeable workflow packs and one explicit human approval gate—without introducing a second orchestration server.

The name carries two related meanings: Hermes' winged herald staff and a staff of specialists coordinating work for a human decision.

Short tagline:

> Hermes-native orchestration. Specialist agents. Human-approved implementation.

## Assets

| File | Use |
|---|---|
| `logo.svg` | Canonical transparent lockup. |
| `logo-mark.svg` | Canonical transparent winged-staff mark. |
| `logo-256.png`, `logo-512.png`, `logo-1024.png` | Raster lockup renders. |
| `social-card.svg`, `social-card.png` | Social preview with lifecycle and product boundary. |

The palette is gold `#ffc72c`, amber `#f9a23a`, and—on the social card only—navy `#1a1f3a`.

## Regeneration

Install development dependencies and ensure Inkscape is available, then run from any directory:

```bash
/path/to/wingstaff/.venv/bin/python /path/to/wingstaff/assets/build_brand_assets.py
```

`build_brand_assets.py` converts the bundled OFL-licensed Libre Baskerville font to SVG paths, writes the SVG sources, and renders PNG files from those sources. Generated files must not be hand-edited.
