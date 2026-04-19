#!/usr/bin/env python3
"""Render each recently-added record as its own standalone SVG.

Each record becomes img/vinyl/record-N.svg — a sleeve cover with a vinyl
disc peeking out to the right, plus title and artist. SVGs are theme-aware
via prefers-color-scheme and self-contained (cover art is base64-embedded).

The README block between VINYL:START/END markers is rewritten to a single
<p align="center"> containing one <a><img></a> per record, so each is
individually clickable (GitHub strips HTML image maps).
"""
from __future__ import annotations

import base64
import io
import json
import pathlib
import re
import urllib.request
from html import escape

from PIL import Image

COLLECTION_URL = "https://www.russ.fm/collection.json"
RELEASE_BASE = "https://www.russ.fm"
ASSET_BASE = "https://assets.russ.fm"
COUNT = 8
OUTPUT_DIR = pathlib.Path("img/vinyl")
README = pathlib.Path("README.md")
RAW_BASE = (
    "https://raw.githubusercontent.com/russmckendrick/russmckendrick/main/img/vinyl/"
)
MARKER_START = "<!-- VINYL:START -->"
MARKER_END = "<!-- VINYL:END -->"

COVER = 160
PEEK = 42
TEXT_GAP = 16
TITLE_H = 18
ARTIST_H = 16
UNIT_W = COVER + PEEK
UNIT_H = COVER + TEXT_GAP + TITLE_H + ARTIST_H + 2

LABEL_PALETTE = [
    ("#d4342a", "#7a1612"),
    ("#f4a93b", "#8c5a12"),
    ("#2f7d7b", "#124d4b"),
    ("#3a4bbd", "#1a2078"),
    ("#8b3ea8", "#4c1560"),
]

STYLE = """
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
    r = COVER / 2
    return (
        f'<g transform="translate({cx} {cy})" class="record">'
        f'<circle r="{r}" class="vinyl"/>'
        + "".join(
            f'<circle r="{gr}" class="groove"/>'
            for gr in (r - 4, r - 14, r - 24, r - 34, r - 44, r - 54)
        )
        + f'<circle r="22" class="label" fill="url(#{label_id})"/>'
        + f'<path d="M -{r * 0.75} -{r * 0.15} A {r} {r} 0 0 1 {r * 0.55} -{r * 0.65}" class="shine"/>'
        + '<circle r="2" class="spindle"/>'
        + "</g>"
    )


def render_record_svg(rec: dict, i: int) -> str:
    label_id = f"label-{i}"
    c1, c2 = LABEL_PALETTE[i % len(LABEL_PALETTE)]
    defs = (
        f'<radialGradient id="{label_id}" cx="0.4" cy="0.4" r="0.7">'
        f'<stop offset="0%" stop-color="{c1}"/>'
        f'<stop offset="100%" stop-color="{c2}"/>'
        f"</radialGradient>"
    )
    cover_url = ASSET_BASE + rec["images_uri_release"]["medium"]
    data_uri = embed_image(cover_url)
    title = truncate(rec["release_name"], 22)
    artist = truncate(rec["release_artist"], 24)
    aria = rec["release_name"] + " by " + rec["release_artist"]

    record_cx = COVER / 2 + PEEK
    record_cy = COVER / 2
    title_y = COVER + TEXT_GAP
    artist_y = title_y + ARTIST_H + 2

    card = (
        record_group(record_cx, record_cy, label_id)
        + f'<image href="{data_uri}" x="0" y="0" width="{COVER}" height="{COVER}" '
          f'preserveAspectRatio="xMidYMid slice"/>'
        + f'<rect x="0" y="0" width="{COVER}" height="{COVER}" class="sleeve-edge"/>'
        + f'<text x="{COVER / 2}" y="{title_y + TITLE_H - 2}" '
          f'class="title" text-anchor="middle">{escape(title)}</text>'
        + f'<text x="{COVER / 2}" y="{artist_y + ARTIST_H - 2}" '
          f'class="artist" text-anchor="middle">{escape(artist)}</text>'
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {UNIT_W} {UNIT_H}" width="{UNIT_W}" height="{UNIT_H}" '
        f'role="img" aria-label="{escape(aria, quote=True)}">'
        f"<defs>{defs}</defs><style>{STYLE}</style>{card}"
        f"</svg>\n"
    )


def build_readme_block(records) -> str:
    cells_per_row = 4
    total_rows = (len(records) + cells_per_row - 1) // cells_per_row
    rows = []
    for r in range(total_rows):
        cells = []
        for c in range(cells_per_row):
            i = r * cells_per_row + c
            if i >= len(records):
                cells.append("<td></td>")
                continue
            rec = records[i]
            href = RELEASE_BASE + rec["uri_release"]
            alt = rec["release_name"] + " by " + rec["release_artist"]
            cells.append(
                f'<td align="center"><a href="{escape(href, quote=True)}" target="_blank">'
                f'<img src="{RAW_BASE}record-{i}.svg" width="150" '
                f'alt="{escape(alt, quote=True)}"/></a></td>'
            )
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return (
        '<div align="center"><table><tbody>'
        + "".join(rows)
        + "</tbody></table></div>"
    )


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
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for stale in OUTPUT_DIR.glob("record-*.svg"):
        stale.unlink()
    for i, rec in enumerate(records):
        svg = render_record_svg(rec, i)
        out = OUTPUT_DIR / f"record-{i}.svg"
        out.write_text(svg)
        print(f"Wrote {out} ({len(svg):,} bytes)")
    update_readme(build_readme_block(records))
    print(f"Updated {README}")


if __name__ == "__main__":
    main()
