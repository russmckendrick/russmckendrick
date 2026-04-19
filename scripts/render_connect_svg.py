#!/usr/bin/env python3
"""Render per-service 'connect' tiles as individual brand-coloured SVGs.

For each service in SERVICES, fetch its Simple Icons glyph, embed it into a
rounded-rect tile at the service's brand colour, and write to
img/connect/<slug>.svg. The README block between CONNECT:START/END is
rewritten to four categorised rows of individually-linked tiles (GitHub
strips HTML image maps, so each tile must be its own <a><img>).

Run manually when the service list changes — the data is static.
"""
from __future__ import annotations

import base64
import pathlib
import re
import urllib.request
from html import escape

OUTPUT_DIR = pathlib.Path("img/connect")
README = pathlib.Path("README.md")
RAW_BASE = (
    "https://raw.githubusercontent.com/russmckendrick/russmckendrick/main/img/connect/"
)
MARKER_START = "<!-- CONNECT:START -->"
MARKER_END = "<!-- CONNECT:END -->"
SIMPLEICONS_BASE = (
    "https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/"
)

TILE_W = 180
TILE_H = 48
ICON_SIZE = 22
ICON_X = 16
LABEL_X = 48

CATEGORIES = ["Code", "Social", "Music", "Writing"]

SERVICES = [
    {"slug": "github",      "label": "GitHub",      "url": "https://github.com/russmckendrick",                         "category": "Code",    "color": "#181717", "icon": "github"},
    {"slug": "docker",      "label": "Docker",      "url": "https://hub.docker.com/u/russmckendrick/",                  "category": "Code",    "color": "#0DB7ED", "icon": "docker"},
    {"slug": "bluesky",     "label": "Bluesky",     "url": "https://bsky.app/profile/russmckendrick.bsky.social",       "category": "Social",  "color": "#0285FF", "icon": "bluesky"},
    {"slug": "mastodon",    "label": "Mastodon",    "url": "https://social.mckendrick.io/@russ",                        "category": "Social",  "color": "#6364FF", "icon": "mastodon"},
    {"slug": "linkedin",    "label": "LinkedIn",    "url": "https://www.linkedin.com/in/russmckendrick/",               "category": "Social",  "color": "#0077B5", "icon": "linkedin"},
    {"slug": "instagram",   "label": "Instagram",   "url": "https://www.instagram.com/russmckendrick/",                 "category": "Social",  "color": "#E1306C", "icon": "instagram"},
    {"slug": "russ-social", "label": "russ.social", "url": "https://www.russ.social/",                                  "category": "Social",  "color": "#6E44FF", "icon": "linktree"},
    {"slug": "discogs",     "label": "Discogs",     "url": "https://www.discogs.com/user/russmck/collection?header=1",  "category": "Music",   "color": "#333333", "icon": "discogs"},
    {"slug": "spotify",     "label": "Spotify",     "url": "https://open.spotify.com/user/russmckendrick",              "category": "Music",   "color": "#1DB954", "icon": "spotify"},
    {"slug": "lastfm",      "label": "Last.fm",     "url": "https://www.last.fm/user/RussMckendrick",                   "category": "Music",   "color": "#D51007", "icon": "lastdotfm"},
    {"slug": "russ-cloud",  "label": "russ.cloud",  "url": "https://www.russ.cloud/",                                   "category": "Writing", "color": "#ffffff", "icon_url": "https://www.russ.cloud/images/logo.svg", "text_color": "#2c3e50"},
    {"slug": "medium",      "label": "Medium",      "url": "https://russmckendrick.medium.com/",                        "category": "Writing", "color": "#000000", "icon": "medium"},
    {"slug": "amazon",      "label": "Amazon",      "url": "https://www.amazon.com/author/russmckendrick",              "category": "Writing", "color": "#FF9900", "icon": "amazon"},
]

# Simple Icons drops brands whose guidelines conflict with its licence. Inline
# fallback path data (from simple-icons tag 11.11.0, MIT-licensed) for those.
FALLBACK_PATHS = {
    "linkedin": "M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z",
    "amazon": "M.045 18.02c.072-.116.187-.124.348-.022 3.636 2.11 7.594 3.166 11.87 3.166 2.852 0 5.668-.533 8.447-1.595l.315-.14c.138-.06.234-.1.293-.13.226-.088.39-.046.525.13.12.174.09.336-.12.48-.256.19-.6.41-1.006.654-1.244.743-2.64 1.316-4.185 1.726a17.617 17.617 0 01-10.951-.577 17.88 17.88 0 01-5.43-3.35c-.1-.074-.151-.15-.151-.22 0-.047.021-.09.051-.13zm6.565-6.218c0-1.005.247-1.863.743-2.577.495-.71 1.17-1.25 2.04-1.615.796-.335 1.756-.575 2.912-.72.39-.046 1.033-.103 1.92-.174v-.37c0-.93-.105-1.558-.3-1.875-.302-.43-.78-.65-1.44-.65h-.182c-.48.046-.896.196-1.246.46-.35.27-.575.63-.675 1.096-.06.3-.206.465-.435.51l-2.52-.315c-.248-.06-.372-.18-.372-.39 0-.046.007-.09.022-.15.247-1.29.855-2.25 1.82-2.88.976-.616 2.1-.975 3.39-1.05h.54c1.65 0 2.957.434 3.888 1.29.135.15.27.3.405.48.12.165.224.314.283.45.075.134.15.33.195.57.06.254.105.42.135.51.03.104.062.3.076.615.01.313.02.493.02.553v5.28c0 .376.06.72.165 1.036.105.313.21.54.315.674l.51.674c.09.136.136.256.136.36 0 .12-.06.226-.18.314-1.2 1.05-1.86 1.62-1.963 1.71-.165.135-.375.15-.63.045a6.062 6.062 0 01-.526-.496l-.31-.347a9.391 9.391 0 01-.317-.42l-.3-.435c-.81.886-1.603 1.44-2.4 1.665-.494.15-1.093.227-1.83.227-1.11 0-2.04-.343-2.76-1.034-.72-.69-1.08-1.665-1.08-2.94l-.05-.076zm3.753-.438c0 .566.14 1.02.425 1.364.285.34.675.512 1.155.512.045 0 .106-.007.195-.02.09-.016.134-.023.166-.023.614-.16 1.08-.553 1.424-1.178.165-.28.285-.58.36-.91.09-.32.12-.59.135-.8.015-.195.015-.54.015-1.005v-.54c-.84 0-1.484.06-1.92.18-1.275.36-1.92 1.17-1.92 2.43l-.035-.02zm9.162 7.027c.03-.06.075-.11.132-.17.362-.243.714-.41 1.05-.5a8.094 8.094 0 011.612-.24c.14-.012.28 0 .41.03.65.06 1.05.168 1.172.33.063.09.099.228.099.39v.15c0 .51-.149 1.11-.424 1.8-.278.69-.664 1.248-1.156 1.68-.073.06-.14.09-.197.09-.03 0-.06 0-.09-.012-.09-.044-.107-.12-.064-.24.54-1.26.806-2.143.806-2.64 0-.15-.03-.27-.087-.344-.145-.166-.55-.257-1.224-.257-.243 0-.533.016-.87.046-.363.045-.7.09-1 .135-.09 0-.148-.014-.18-.044-.03-.03-.036-.047-.02-.077 0-.017.006-.03.02-.063v-.06z",
}

STYLE_TEMPLATE = """
        .tile {{ stroke: rgba(0,0,0,0.15); stroke-width: 1; }}
        .label {{ font: 600 14px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; fill: {text_color}; }}
        @media (prefers-color-scheme: dark) {{
          .tile {{ stroke: rgba(255,255,255,0.18); }}
        }}
""".strip()


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "russmckendrick-readme-bot"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def icon_path(icon_slug: str) -> str:
    if icon_slug in FALLBACK_PATHS:
        return FALLBACK_PATHS[icon_slug]
    svg = fetch_text(SIMPLEICONS_BASE + icon_slug + ".svg")
    m = re.search(r'\bd="([^"]+)"', svg)
    if not m:
        raise SystemExit(f"No <path d=…> found in simpleicons svg for {icon_slug}")
    return m.group(1)


def icon_data_uri(url: str) -> str:
    raw = urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "russmckendrick-readme-bot"}),
        timeout=30,
    ).read()
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"


def render_tile_svg(svc: dict) -> str:
    radius = 10
    icon_y = (TILE_H - ICON_SIZE) / 2
    text_color = svc.get("text_color", "#ffffff")
    icon_fill = svc.get("icon_fill", "#ffffff")

    if svc.get("icon_url"):
        href = icon_data_uri(svc["icon_url"])
        icon_el = (
            f'<image href="{href}" x="{ICON_X}" y="{icon_y}" '
            f'width="{ICON_SIZE}" height="{ICON_SIZE}" '
            f'preserveAspectRatio="xMidYMid meet"/>'
        )
    else:
        scale = ICON_SIZE / 24
        d_path = icon_path(svc["icon"])
        icon_el = (
            f'<g transform="translate({ICON_X} {icon_y}) scale({scale})" fill="{icon_fill}">'
            f'<path d="{d_path}"/>'
            f"</g>"
        )

    label = (
        f'<text x="{LABEL_X}" y="{TILE_H / 2 + 5}" class="label">'
        f"{escape(svc['label'])}</text>"
    )
    tile = (
        f'<rect x="0" y="0" width="{TILE_W}" height="{TILE_H}" '
        f'rx="{radius}" class="tile" fill="{svc["color"]}"/>'
    )
    style = STYLE_TEMPLATE.format(text_color=text_color)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {TILE_W} {TILE_H}" width="{TILE_W}" height="{TILE_H}" '
        f'role="img" aria-label="{escape(svc["label"])}">'
        f"<style>{style}</style>{tile}{icon_el}{label}"
        f"</svg>\n"
    )


def build_readme_block() -> str:
    cells_per_row = 5
    total_rows = (len(SERVICES) + cells_per_row - 1) // cells_per_row
    rows = []
    for r in range(total_rows):
        cells = []
        for c in range(cells_per_row):
            i = r * cells_per_row + c
            if i >= len(SERVICES):
                cells.append("<td></td>")
                continue
            svc = SERVICES[i]
            cells.append(
                f'<td><a href="{escape(svc["url"], quote=True)}" target="_blank">'
                f'<img src="{RAW_BASE}{svc["slug"]}.svg" width="160" '
                f'alt="{escape(svc["label"])}"/></a></td>'
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
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for svc in SERVICES:
        svg = render_tile_svg(svc)
        out = OUTPUT_DIR / f"{svc['slug']}.svg"
        out.write_text(svg)
        print(f"Wrote {out} ({len(svg):,} bytes)")
    update_readme(build_readme_block())
    print(f"Updated {README}")


if __name__ == "__main__":
    main()
