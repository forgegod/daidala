# assets/

## Purpose

Own the canonical Daidala identity, deterministic generator, review renders, and bundled font license.

## Ownership

- `build_brand_assets.py` is the only source of generated brand geometry and copy.
- `logo.svg` and `logo-mark.svg` are canonical vector assets.
- PNG files are deterministic renders generated from the SVG assets.
- `social-card.svg` owns the social-card composition and accessible text.
- `fonts/` contains only the bundled Libre Baskerville font and its OFL license.

## Local Contracts

- Keep the crafted-D mark and gold `#ffc72c` / amber `#f9a23a` palette.
- The mark is a smooth filled `D` with one meander-cut opening through its lower
  edge. The ordered opening suggests staged craft leaving as delivery. It must
  remain distinct from pixel art, a literal labyrinth, gear, robot, factory, or
  the former winged staff.
- Render amber only through clipped copies of the mark and wordmark geometry. Do not draw an amber background bridge through transparent gaps.
- Position the mark slightly below the fixed wordmark band so gold remains visible beneath the amber overlay at the glyph's bottom edge, matching the Irigate and Talaria layering rule.
- Use the bundled font through generated SVG paths. Do not depend on system fonts or silently substitute fonts.
- Keep the logo and mark backgrounds transparent.
- Keep the social card's human-approval message and no-second-orchestration-server boundary visible.
- Do not hand-edit generated SVG or PNG files; edit and run `build_brand_assets.py`.
- Do not add naming proposals, comparison boards, or alternative product identities.

## Work Guidance

- Run `.venv/bin/python assets/build_brand_assets.py` from any current working directory.
- Generate SVG first and render PNG only from those SVG files.

## Verification

- Run the generator twice and compare hashes from both runs.
- Confirm PNG dimensions, alpha content, accessible SVG titles, and approved copy.
- Inspect the logo, mark, and social card for clipping, overlap, contrast, and small-size legibility.

## Child DOX Index

| Path | Owns |
|---|---|
| `build_brand_assets.py` | Deterministic geometry, copy, and rendering. |
| `logo.svg`, `logo-mark.svg` | Canonical lockup and standalone mark. |
| `logo-*.png` | 256, 512, and 1024 pixel lockup renders. |
| `social-card.svg`, `social-card.png` | Canonical social-card source and render. |
| `fonts/` | Libre Baskerville font and OFL license. |

See [`/AGENTS.md`](../AGENTS.md).
