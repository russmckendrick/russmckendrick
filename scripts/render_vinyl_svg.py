#!/usr/bin/env python3
"""Render the five most recently added records into a single SVG card.

Fetches russ.fm's collection.json, base64-embeds each cover, and writes
img/vinyl.svg. The SVG is theme-aware (light/dark via prefers-color-scheme)
and self-contained — no external image references at render time.
"""
from __future__ import annotations

import base64
import io
import json
import pathlib
import urllib.request
from html import escape

from PIL import Image

import re

COLLECTION_URL = "https://www.russ.fm/collection.json"
RELEASE_BASE = "https://www.russ.fm"
ASSET_BASE = "https://assets.russ.fm"
COUNT = 5
OUTPUT = pathlib.Path("img/vinyl.svg")
README = pathlib.Path("README.md")
SVG_URL = "https://raw.githubusercontent.com/russmckendrick/russmckendrick/master/img/vinyl.svg"
FALLBACK_URL = "https://www.russ.fm/"
MARKER_START = "<!-- VINYL:START -->"
MARKER_END = "<!-- VINYL:END -->"
MAP_NAME = "vinyl-map"

COVER = 160
PEEK = 42  # how far the record sticks out to the right of the sleeve
GAP = 18
TEXT_GAP = 16
TITLE_H = 18
ARTIST_H = 16
UNIT_W = COVER + PEEK
UNIT_H = COVER + TEXT_GAP + TITLE_H + ARTIST_H
WIDTH = COUNT * UNIT_W + (COUNT + 1) * GAP
HEIGHT = UNIT_H + 2 * GAP


def fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "russmckendrick-readme-bot"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def fetch_json(url: str):
    return json.loads(fetch_bytes(url))


def embed_image(url: str, size: int = 320, quality: int = 80) -> str:
    raw = fetch_bytes(url)
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    im.thumbnail((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def record_group(cx: float, cy: float, label_id: str) -> str:
    """A vinyl disc centered at (cx, cy), same diameter as the cover."""
    r = COVER / 2
    return (
        f'<g transform="translate({cx} {cy})" class="record">'
        # main disc
        f'<circle r="{r}" class="vinyl"/>'
        # grooves
        + "".join(
            f'<circle r="{gr}" class="groove"/>'
            for gr in (r - 4, r - 14, r - 24, r - 34, r - 44, r - 54)
        )
        # label
        + f'<circle r="22" class="label" fill="url(#{label_id})"/>'
        # reflective highlight
        + f'<path d="M -{r * 0.75} -{r * 0.15} A {r} {r} 0 0 1 {r * 0.55} -{r * 0.65}" '
          f'class="shine"/>'
        # spindle hole
        + '<circle r="2" class="spindle"/>'
        + "</g>"
    )


LABEL_PALETTE = [
    ("#d4342a", "#7a1612"),
    ("#f4a93b", "#8c5a12"),
    ("#2f7d7b", "#124d4b"),
    ("#3a4bbd", "#1a2078"),
    ("#8b3ea8", "#4c1560"),
]


def render(records) -> str:
    cards = []
    defs = []
    for i, rec in enumerate(records):
        unit_x = GAP + i * (UNIT_W + GAP)
        cover_x = unit_x
        cover_y = GAP
        record_cx = unit_x + COVER / 2 + PEEK
        record_cy = GAP + COVER / 2
        label_id = f"label-{i}"
        c1, c2 = LABEL_PALETTE[i % len(LABEL_PALETTE)]
        defs.append(
            f'<radialGradient id="{label_id}" cx="0.4" cy="0.4" r="0.7">'
            f'<stop offset="0%" stop-color="{c1}"/>'
            f'<stop offset="100%" stop-color="{c2}"/>'
            f"</radialGradient>"
        )

        cover_url = ASSET_BASE + rec["images_uri_release"]["medium"]
        data_uri = embed_image(cover_url)
        href = RELEASE_BASE + rec["uri_release"]
        title = truncate(rec["release_name"], 22)
        artist = truncate(rec["release_artist"], 24)

        title_y = cover_y + COVER + TEXT_GAP
        artist_y = title_y + ARTIST_H + 2

        cards.append(
            f'<a href="{escape(href, quote=True)}" target="_blank" class="card">'
            # record first so the cover draws on top
            f"{record_group(record_cx, record_cy, label_id)}"
            # cover — square, rounded corners
            f'<image href="{data_uri}" x="{cover_x}" y="{cover_y}" '
            f'width="{COVER}" height="{COVER}" '
            f'preserveAspectRatio="xMidYMid slice"/>'
            # subtle edge on the sleeve so it reads as separate from the disc
            f'<rect x="{cover_x}" y="{cover_y}" width="{COVER}" height="{COVER}" '
            f'class="sleeve-edge"/>'
            f'<text x="{cover_x + COVER / 2}" y="{title_y + TITLE_H - 2}" '
            f'class="title" text-anchor="middle">{escape(title)}</text>'
            f'<text x="{cover_x + COVER / 2}" y="{artist_y + ARTIST_H - 2}" '
            f'class="artist" text-anchor="middle">{escape(artist)}</text>'
            f"</a>"
        )

    style = """
    .title { font: 600 13px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; fill: #1f2328; }
    .artist { font: 400 12px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; fill: #656d76; }
    .vinyl { fill: #111; }
    .groove { fill: none; stroke: #2a2a2a; stroke-width: 0.6; }
    .shine { fill: none; stroke: rgba(255,255,255,0.08); stroke-width: 1.5; }
    .spindle { fill: #0d0d0d; }
    .sleeve-edge { fill: none; stroke: rgba(0,0,0,0.12); stroke-width: 1; }
    @media (prefers-color-scheme: dark) {
      .title { fill: #e6edf3; }
      .artist { fill: #8b949e; }
      .sleeve-edge { stroke: rgba(255,255,255,0.12); }
      .groove { stroke: #333; }
    }
    """.strip()

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" width="{WIDTH}" height="{HEIGHT}" '
        f'role="img" aria-label="Five most recently added records">'
        f"<defs>{''.join(defs)}</defs>"
        f"<style>{style}</style>"
        + "".join(cards)
        + "</svg>\n"
    )


def build_image_map(records) -> str:
    areas = []
    for i, rec in enumerate(records):
        unit_x = GAP + i * (UNIT_W + GAP)
        unit_y = GAP
        x2 = unit_x + UNIT_W
        y2 = unit_y + UNIT_H
        href = RELEASE_BASE + rec["uri_release"]
        title = rec["release_name"] + " by " + rec["release_artist"]
        areas.append(
            f'<area shape="rect" coords="{unit_x},{unit_y},{x2},{y2}" '
            f'href="{escape(href, quote=True)}" '
            f'alt="{escape(title, quote=True)}" target="_blank">'
        )
    img_tag = (
        f'<p align="center"><a href="{FALLBACK_URL}">'
        f'<img src="{SVG_URL}" alt="Five most recently added records" '
        f'usemap="#{MAP_NAME}"/></a></p>'
    )
    map_tag = f'<map name="{MAP_NAME}">' + "".join(areas) + "</map>"
    return f"{img_tag}\n{map_tag}"


def update_readme(html: str) -> None:
    text = README.read_text()
    block = f"{MARKER_START}\n{html}\n{MARKER_END}"
    pattern = re.compile(
        re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END),
        re.DOTALL,
    )
    updated, n = pattern.subn(block, text)
    if n == 0:
        raise SystemExit(f"Markers {MARKER_START}/{MARKER_END} not found in README.md")
    README.write_text(updated)


def main() -> None:
    data = fetch_json(COLLECTION_URL)
    records = sorted(data, key=lambda r: r.get("date_added", ""), reverse=True)[:COUNT]
    svg = render(records)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(svg)
    print(f"Wrote {OUTPUT} ({len(svg):,} bytes)")
    update_readme(build_image_map(records))
    print(f"Updated {README}")


if __name__ == "__main__":
    main()
