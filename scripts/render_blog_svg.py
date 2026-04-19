#!/usr/bin/env python3
"""Render each recent blog post as its own standalone browser-card SVG.

Each post becomes img/blog/post-N.svg — a small macOS-style browser window
with traffic-light buttons, a faux URL bar, the post's og:image, and the
title below. SVGs are self-contained (images are base64-embedded) and
theme-aware via prefers-color-scheme.

The README block between BLOG-POSTS:START/END markers is rewritten to a
flex-wrapping <div> of per-post <a><img></a> pairs so each card is its
own hyperlink (GitHub strips HTML image maps, so that's the only way).
"""
from __future__ import annotations

import base64
import io
import pathlib
import re
import urllib.request
import xml.etree.ElementTree as ET
from html import escape

from PIL import Image

FEED_URL = "https://www.russ.cloud/rss.xml"
COUNT = 6
OUTPUT_DIR = pathlib.Path("img/blog")
README = pathlib.Path("README.md")
RAW_BASE = (
    "https://raw.githubusercontent.com/russmckendrick/russmckendrick/main/img/blog/"
)
MARKER_START = "<!-- BLOG-POSTS:START -->"
MARKER_END = "<!-- BLOG-POSTS:END -->"

CARD_W = 320
OG_H = 168  # 1200x630 scales to 320x168
CHROME_H = 26
TITLE_BAND_H = 48
CARD_H = CHROME_H + OG_H + TITLE_BAND_H

TRAFFIC_LIGHTS = [("#ff5f57", 14), ("#febc2e", 30), ("#28c840", 46)]

STYLE = """
    .title { font: 600 12px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; fill: #1f2328; }
    .chrome { fill: #ebecef; }
    .urlbar { fill: #ffffff; stroke: rgba(0,0,0,0.08); stroke-width: 1; }
    .urltext { font: 400 10px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; fill: #656d76; }
    .frame { fill: none; stroke: rgba(0,0,0,0.12); stroke-width: 1; }
    @media (prefers-color-scheme: dark) {
      .title { fill: #e6edf3; }
      .chrome { fill: #21262d; }
      .urlbar { fill: #0d1117; stroke: rgba(255,255,255,0.08); }
      .urltext { fill: #8b949e; }
      .frame { stroke: rgba(255,255,255,0.12); }
    }
""".strip()


def fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "russmckendrick-readme-bot"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def fetch_text(url: str) -> str:
    return fetch_bytes(url).decode("utf-8", errors="replace")


def og_image_url(post_url: str) -> str | None:
    try:
        html = fetch_text(post_url)
    except Exception:
        return None
    tag_boundary = r'(?=["\'\s>])'
    for pattern in (
        rf'<meta[^>]+property=["\']?og:image{tag_boundary}[^>]*\bcontent=["\']([^"\']+)["\']',
        rf'<meta[^>]+property=["\']?og:image{tag_boundary}[^>]*\bcontent=(\S+)',
        rf'<meta[^>]+\bcontent=["\']([^"\']+)["\'][^>]*\bproperty=["\']?og:image{tag_boundary}',
        rf'<meta[^>]+\bcontent=(\S+?)\s[^>]*\bproperty=["\']?og:image{tag_boundary}',
    ):
        m = re.search(pattern, html, re.IGNORECASE)
        if m:
            return m.group(1).strip().rstrip(">").strip('"\'')
    return None


def embed_image(url: str, width: int, height: int, quality: int = 78) -> str:
    raw = fetch_bytes(url)
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    im.thumbnail((width * 2, height * 2), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def wrap_title(text: str, per_line: int, max_lines: int = 2) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    i = 0
    while i < len(words) and len(lines) < max_lines:
        word = words[i]
        candidate = (current + " " + word).strip() if current else word
        if len(candidate) <= per_line:
            current = candidate
            i += 1
        elif current:
            lines.append(current)
            current = ""
        else:
            lines.append(word[: per_line - 1] + "…")
            i += 1
    if current and len(lines) < max_lines:
        lines.append(current)
    if i < len(words) and lines:
        last = lines[-1]
        if len(last) > per_line - 1:
            last = last[: per_line - 1].rstrip()
        lines[-1] = last + "…"
    return lines or [text[:per_line]]


def render_card_svg(title: str, og_uri: str) -> str:
    radius = 8
    lights = "".join(
        f'<circle cx="{cx}" cy="{CHROME_H / 2}" r="5.5" fill="{color}"/>'
        for color, cx in TRAFFIC_LIGHTS
    )
    domain = "www.russ.cloud"
    url_bar_x = 64
    url_bar_w = CARD_W - 76
    url_bar = (
        f'<rect x="{url_bar_x}" y="5" width="{url_bar_w}" height="{CHROME_H - 10}" rx="4" class="urlbar"/>'
        f'<text x="{url_bar_x + url_bar_w / 2}" y="{CHROME_H / 2 + 4}" class="urltext" text-anchor="middle">{escape(domain)}</text>'
    )
    chrome = (
        f'<path d="M 0 {radius} Q 0 0 {radius} 0 '
        f'L {CARD_W - radius} 0 Q {CARD_W} 0 {CARD_W} {radius} '
        f'L {CARD_W} {CHROME_H} L 0 {CHROME_H} Z" class="chrome"/>'
        f"{lights}{url_bar}"
    )
    og = (
        f'<image href="{og_uri}" x="0" y="{CHROME_H}" '
        f'width="{CARD_W}" height="{OG_H}" preserveAspectRatio="xMidYMid slice"/>'
    )
    title_y = CHROME_H + OG_H + 20
    lines = wrap_title(title, per_line=42, max_lines=2)
    tspans = "".join(
        f'<tspan x="{CARD_W / 2}" dy="{0 if idx == 0 else 18}">{escape(line)}</tspan>'
        for idx, line in enumerate(lines)
    )
    title_el = (
        f'<text x="{CARD_W / 2}" y="{title_y}" class="title" text-anchor="middle">{tspans}</text>'
    )
    outline = (
        f'<rect x="0" y="0" width="{CARD_W}" height="{CHROME_H + OG_H}" '
        f'rx="{radius}" class="frame"/>'
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {CARD_W} {CARD_H}" width="{CARD_W}" height="{CARD_H}" '
        f'role="img" aria-label="{escape(title, quote=True)}">'
        f"<style>{STYLE}</style>{chrome}{og}{outline}{title_el}"
        f"</svg>\n"
    )


def load_posts() -> list[tuple[str, str, str]]:
    root = ET.fromstring(fetch_text(FEED_URL))
    items = root.findall("./channel/item")[:COUNT]
    out: list[tuple[str, str, str]] = []
    for item in items:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        og = og_image_url(link) or ""
        og_uri = embed_image(og, CARD_W, OG_H) if og else ""
        out.append((title, link, og_uri))
    return out


def build_readme_block(posts) -> str:
    cells_per_row = 3
    total_rows = (len(posts) + cells_per_row - 1) // cells_per_row
    rows = []
    for r in range(total_rows):
        cells = []
        for c in range(cells_per_row):
            i = r * cells_per_row + c
            if i >= len(posts):
                cells.append("<td></td>")
                continue
            title, link, _ = posts[i]
            cells.append(
                f'<td align="center"><a href="{escape(link, quote=True)}" target="_blank">'
                f'<img src="{RAW_BASE}post-{i}.svg" width="240" '
                f'alt="{escape(title, quote=True)}"/></a></td>'
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
    posts = load_posts()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for stale in OUTPUT_DIR.glob("post-*.svg"):
        stale.unlink()
    for i, (title, _, og_uri) in enumerate(posts):
        svg = render_card_svg(title, og_uri)
        out = OUTPUT_DIR / f"post-{i}.svg"
        out.write_text(svg)
        print(f"Wrote {out} ({len(svg):,} bytes)")
    update_readme(build_readme_block(posts))
    print(f"Updated {README}")


if __name__ == "__main__":
    main()
