#!/usr/bin/env python3
"""Generate the canonical Wingstaff brand assets."""

from __future__ import annotations

import html
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

GOLD = "#ffc72c"
AMBER = "#f9a23a"
NAVY = "#1a1f3a"
MUTED = "#d8c995"
PALE = "#f6efdb"
OUT = Path(__file__).resolve().parent
FONT_PATH = OUT / "fonts" / "LibreBaskerville-wght.ttf"
WORDMARK = "WINGSTAFF"
# Shared band geometry for the mark and wordmark. Amber is painted only through
# clipped copies of their geometry; it never bridges transparent gaps.
# BAND_Y is the reference y-coordinate used to derive absolute lockup bands.
BAND_Y = 170
BAND_HEIGHT = 26
LOGO_MARK_Y = 8
LOGO_BAND_Y = BAND_Y + 3
MARK_ONLY_Y = 25
MARK_ONLY_BAND_Y = BAND_Y + 20
TAGLINE = (
    "Hermes-native orchestration.",
    "Specialist agents.",
    "Human-approved implementation.",
)
LIFECYCLE = "define → plan → approve → implement → verify → deliver"
BOUNDARY = "In-process with Hermes · no second orchestration server"


@lru_cache(maxsize=1)
def _font() -> TTFont:
    if not FONT_PATH.is_file():
        raise SystemExit(f"required bundled font not found: {FONT_PATH}")
    variable_font = TTFont(FONT_PATH, recalcBBoxes=False, recalcTimestamp=False)
    return instantiateVariableFont(variable_font, {"wght": 700}, inplace=False)


def _text_geometry(
    text: str,
    *,
    size: float,
    letter_spacing: float = 0,
) -> tuple[list[tuple[str, float]], float, float]:
    font = _font()
    head = cast(Any, font["head"])
    units_per_em = int(head.unitsPerEm)
    scale = size / units_per_em
    cmap = font.getBestCmap()
    if cmap is None:
        raise ValueError("bundled font has no Unicode character map")
    glyph_set = font.getGlyphSet()
    metrics = font["hmtx"].metrics
    cursor = 0.0
    glyphs: list[tuple[str, float]] = []

    for index, character in enumerate(text):
        if character == "→":
            path = "M100 240H650L480 410L560 490L900 240L560 -10L480 70L650 240H100Z"
            advance = 1000
        else:
            glyph_name = cmap.get(ord(character))
            if glyph_name is None:
                raise ValueError(f"bundled font has no glyph for {character!r}")
            pen = SVGPathPen(glyph_set)
            glyph_set[glyph_name].draw(pen)
            path = pen.getCommands()
            advance = metrics[glyph_name][0]
        if path:
            glyphs.append((path, cursor))
        cursor += advance
        if index < len(text) - 1:
            cursor += letter_spacing / scale

    return glyphs, cursor * scale, scale


def _path_group(
    text: str,
    *,
    x: float,
    baseline: float,
    size: float,
    fill: str,
    letter_spacing: float = 0,
    clip_id: str | None = None,
) -> tuple[str, float]:
    glyphs, width, scale = _text_geometry(text, size=size, letter_spacing=letter_spacing)
    paths = "".join(
        f'<path d="{path}" transform="translate({offset:.4f} 0)"/>'
        for path, offset in glyphs
    )
    group = (
        f'<g transform="translate({x} {baseline}) scale({scale:.8f} {-scale:.8f})" '
        f'fill="{fill}">{paths}</g>'
    )
    if clip_id:
        group = f'<g clip-path="url(#{clip_id})">{group}</g>'
    return group, width


MARK_WIDTH = 280
MARK_PATH_LEFT = (
    "M 140 78 C 112 42, 72 34, 30 54 "
    "C 56 64, 82 70, 106 82 "
    "C 72 74, 40 82, 18 104 "
    "C 51 99, 80 100, 110 96 "
    "C 76 102, 50 118, 34 144 "
    "C 67 132, 97 120, 122 106 L 140 114 Z"
)
MARK_PATH_RIGHT = (
    "M 140 78 C 168 42, 208 34, 250 54 "
    "C 224 64, 198 70, 174 82 "
    "C 208 74, 240 82, 262 104 "
    "C 229 99, 200 100, 170 96 "
    "C 204 102, 230 118, 246 144 "
    "C 213 132, 183 120, 158 106 L 140 114 Z"
)


def _staff_mark(
    *,
    x: int,
    y: int,
    band_y: float,
    band_height: float = BAND_HEIGHT,
    scale: float = 1.0,
    prefix: str,
) -> tuple[str, int]:
    """Return the staff mark SVG fragment and the rendered mark width."""
    transform = f"translate({x} {y}) scale({scale})"
    return (
        f"""
  <defs>
    <clipPath id="{prefix}-mark-band" clipPathUnits="userSpaceOnUse">
      <rect x="{x}" y="{band_y:.2f}" width="{MARK_WIDTH * scale:.2f}"
            height="{band_height:.2f}"/>
    </clipPath>
  </defs>
  <g transform="{transform}">
    <path d="{MARK_PATH_LEFT}" fill="{GOLD}"/>
    <path d="{MARK_PATH_RIGHT}" fill="{GOLD}"/>
    <circle cx="140" cy="38" r="22" fill="{GOLD}"/>
    <rect x="130" y="38" width="20" height="146" rx="10" fill="{GOLD}"/>
    <path d="M 112 184 L 168 184 L 154 202 L 126 202 Z" fill="{GOLD}"/>
  </g>
  <g clip-path="url(#{prefix}-mark-band)">
    <g transform="{transform}" fill="{AMBER}">
      <path d="{MARK_PATH_LEFT}"/>
      <path d="{MARK_PATH_RIGHT}"/>
      <circle cx="140" cy="38" r="22"/>
      <rect x="130" y="38" width="20" height="146" rx="10"/>
      <path d="M 112 184 L 168 184 L 154 202 L 126 202 Z"/>
    </g>
  </g>""",
        MARK_WIDTH,
    )


def _wordmark(
    *,
    x: float,
    baseline: float,
    size: float,
    prefix: str,
    band_y: float = BAND_Y,
    band_height: float = BAND_HEIGHT,
) -> tuple[str, float]:
    """Return the wordmark SVG fragment and its rendered width.

    ``band_y`` and ``band_height`` are absolute lockup coordinates so the clip
    aligns with the independently transformed mark.
    """
    gold, width = _path_group(
        WORDMARK,
        x=x,
        baseline=baseline,
        size=size,
        fill=GOLD,
        letter_spacing=10 * size / 168,
    )
    amber, _ = _path_group(
        WORDMARK,
        x=x,
        baseline=baseline,
        size=size,
        fill=AMBER,
        letter_spacing=10 * size / 168,
        clip_id=f"{prefix}-word-band",
    )
    return (
        f"""
  <defs>
    <clipPath id="{prefix}-word-band" clipPathUnits="userSpaceOnUse">
      <rect x="{x - 4:.2f}" y="{band_y:.2f}" width="{width + 8:.2f}"
            height="{band_height:.2f}"/>
    </clipPath>
  </defs>
  {gold}
  {amber}""",
        width,
    )


def _logo_svg() -> str:
    word_x = 390
    word, width = _wordmark(
        x=word_x,
        baseline=207,
        size=168,
        prefix="wingstaff",
        band_y=LOGO_BAND_Y,
    )
    mark, _ = _staff_mark(
        x=54,
        y=LOGO_MARK_Y,
        band_y=LOGO_BAND_Y,
        prefix="wingstaff",
    )
    total_width = round(word_x + width + 70)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_width} 284"
  role="img" aria-labelledby="title">
  <title id="title">Wingstaff</title>
{mark}{word}
</svg>
"""


def _mark_svg() -> str:
    mark, _ = _staff_mark(
        x=28,
        y=MARK_ONLY_Y,
        band_y=MARK_ONLY_BAND_Y,
        prefix="wingstaff-mark",
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 336 250"
  role="img" aria-labelledby="title">
  <title id="title">Wingstaff winged-staff mark</title>
{mark}
</svg>
"""


def _solid_text(text: str, *, x: float, baseline: float, size: float, fill: str) -> str:
    group, _ = _path_group(text, x=x, baseline=baseline, size=size, fill=fill)
    return group


def _social_card_svg() -> str:
    mark_scale = 0.72
    mark_x, mark_y = 54, 42
    band_y = BAND_Y * mark_scale + 38
    band_height = BAND_HEIGHT * mark_scale
    word, _ = _wordmark(
        x=300,
        baseline=190,
        size=112,
        prefix="social",
        band_y=band_y,
        band_height=band_height,
    )
    mark, _ = _staff_mark(
        x=mark_x,
        y=mark_y,
        band_y=band_y,
        band_height=band_height,
        scale=mark_scale,
        prefix="social",
    )
    tagline = "".join(
        _solid_text(line, x=78, baseline=310 + index * 48, size=30, fill=PALE)
        for index, line in enumerate(TAGLINE)
    )
    lifecycle = _solid_text(LIFECYCLE, x=78, baseline=500, size=22, fill=MUTED)
    boundary = _solid_text(BOUNDARY, x=78, baseline=565, size=20, fill=AMBER)
    description = html.escape(" ".join(TAGLINE) + " " + LIFECYCLE + ". " + BOUNDARY + ".")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630"
  role="img" aria-labelledby="title description">
  <title id="title">Wingstaff — Hermes-native orchestration</title>
  <desc id="description">{description}</desc>
  <rect width="1200" height="630" fill="{NAVY}"/>
{mark}{word}
  <rect x="78" y="248" width="1044" height="3" fill="{AMBER}"/>
  {tagline}
  {lifecycle}
  <rect x="78" y="528" width="1044" height="1" fill="#4a4f67"/>
  {boundary}
</svg>
"""


def _render(svg_path: Path, png_path: Path, *, width: int) -> None:
    subprocess.run(
        [
            "inkscape",
            str(svg_path),
            "--export-type=png",
            f"--export-filename={png_path}",
            f"--export-width={width}",
        ],
        check=True,
        cwd=OUT,
    )


def main() -> None:
    logo_svg = OUT / "logo.svg"
    mark_svg = OUT / "logo-mark.svg"
    social_svg = OUT / "social-card.svg"

    logo_svg.write_text(_logo_svg(), encoding="utf-8")
    mark_svg.write_text(_mark_svg(), encoding="utf-8")
    social_svg.write_text(_social_card_svg(), encoding="utf-8")

    for width in (256, 512, 1024):
        _render(logo_svg, OUT / f"logo-{width}.png", width=width)
    _render(social_svg, OUT / "social-card.png", width=1200)


if __name__ == "__main__":
    main()
