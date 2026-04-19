#!/usr/bin/env python3
"""Render the five most recent blog posts into a single SVG strip.

Each post is drawn as a small browser-window card: traffic-light buttons,
a faux URL bar showing the domain, the post's og:image as the content,
and the title below. Everything is self-contained — images are base64
embedded at render time — and the SVG is theme-aware.
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
COLS = 3
ROWS = 2
COUNT = COLS * ROWS
OUTPUT = pathlib.Path("img/blog.svg")

CARD_W = 320
OG_H = 168  # 1200x630 scales to 320x168
CHROME_H = 26
TITLE_BAND_H = 48
GAP = 20
UNIT_H = CHROME_H + OG_H + TITLE_BAND_H
WIDTH = COLS * CARD_W + (COLS + 1) * GAP
HEIGHT = ROWS * UNIT_H + (ROWS + 1) * GAP

TRAFFIC_LIGHTS = [("#ff5f57", 14), ("#febc2e", 30), ("#28c840", 46)]


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


def render_card(i: int, title: str, link: str, og_uri: str) -> str:
    row, col = divmod(i, COLS)
    unit_x = GAP + col * (CARD_W + GAP)
    unit_y = GAP + row * (UNIT_H + GAP)
    radius = 8

    lights = "".join(
        f'<circle cx="{unit_x + cx}" cy="{unit_y + CHROME_H / 2}" r="5.5" fill="{color}"/>'
        for color, cx in TRAFFIC_LIGHTS
    )
    domain = "www.russ.cloud"
    url_bar_x = unit_x + 64
    url_bar_w = CARD_W - 76
    url_bar = (
        f'<rect x="{url_bar_x}" y="{unit_y + 5}" '
        f'width="{url_bar_w}" height="{CHROME_H - 10}" rx="4" class="urlbar"/>'
        f'<text x="{url_bar_x + url_bar_w / 2}" y="{unit_y + CHROME_H / 2 + 4}" '
        f'class="urltext" text-anchor="middle">{escape(domain)}</text>'
    )

    chrome = (
        f'<path d="M {unit_x} {unit_y + radius} '
        f'Q {unit_x} {unit_y} {unit_x + radius} {unit_y} '
        f'L {unit_x + CARD_W - radius} {unit_y} '
        f'Q {unit_x + CARD_W} {unit_y} {unit_x + CARD_W} {unit_y + radius} '
        f'L {unit_x + CARD_W} {unit_y + CHROME_H} '
        f'L {unit_x} {unit_y + CHROME_H} Z" class="chrome"/>'
        f"{lights}{url_bar}"
    )

    og_y = unit_y + CHROME_H
    og = (
        f'<image href="{og_uri}" x="{unit_x}" y="{og_y}" '
        f'width="{CARD_W}" height="{OG_H}" preserveAspectRatio="xMidYMid slice"/>'
    )

    title_y = og_y + OG_H + 20
    lines = wrap_title(title, per_line=42, max_lines=2)
    title_tspans = "".join(
        f'<tspan x="{unit_x + CARD_W / 2}" dy="{0 if idx == 0 else 18}">{escape(line)}</tspan>'
        for idx, line in enumerate(lines)
    )
    title_el = (
        f'<text x="{unit_x + CARD_W / 2}" y="{title_y}" '
        f'class="title" text-anchor="middle">{title_tspans}</text>'
    )

    # outline for the content area so it reads as a windowed screenshot
    outline = (
        f'<rect x="{unit_x}" y="{unit_y}" width="{CARD_W}" height="{CHROME_H + OG_H}" '
        f'rx="{radius}" class="frame"/>'
    )

    return (
        f'<a href="{escape(link, quote=True)}" target="_blank">'
        f"{chrome}{og}{outline}{title_el}"
        f"</a>"
    )


def render(posts) -> str:
    cards = "".join(
        render_card(i, title, link, og) for i, (title, link, og) in enumerate(posts)
    )
    style = """
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
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" width="{WIDTH}" height="{HEIGHT}" '
        f'role="img" aria-label="Five most recent blog posts">'
        f"<style>{style}</style>{cards}</svg>\n"
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


def main() -> None:
    posts = load_posts()
    svg = render(posts)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(svg)
    print(f"Wrote {OUTPUT} ({len(svg):,} bytes)")


if __name__ == "__main__":
    main()
