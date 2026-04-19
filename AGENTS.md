# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

`russmckendrick/russmckendrick` is a GitHub *profile* repository — its only deliverable is `README.md`, which renders on the user's GitHub profile page. There is no application, package, or test suite. Everything here exists to keep that README fresh.

## Important constraint: no image maps

GitHub's markdown renderer strips `<map>`/`<area>` tags. That means a single SVG with an HTML image map will only ever have one working link (the outer `<a>`). For every clickable "card" to link somewhere different, each must be its **own** SVG wrapped in its **own** `<a>`. The three scripts below therefore emit a *directory* of SVGs, not a single combined one.

## How the README stays fresh

Three Python scripts render SVGs and rewrite chunks of the README between sentinel comments. They share the same shape: fetch data, base64-embed any images, write per-item SVGs, rewrite a marker block in `README.md`.

- `scripts/render_blog_svg.py` → `img/blog/post-{0..5}.svg` + `<!-- BLOG-POSTS:START/END -->`. Pulls `https://www.russ.cloud/rss.xml`, fetches each post's `og:image`. Run hourly by `.github/workflows/blog-post-workflow.yml`.
- `scripts/render_vinyl_svg.py` → `img/vinyl/record-{0..7}.svg` + `<!-- VINYL:START/END -->`. Pulls `https://www.russ.fm/collection.json`. Run every 6 hours by `.github/workflows/vinyl-update.yml`.
- `scripts/render_connect_svg.py` → `img/connect/<slug>.svg` × 13 + `<!-- CONNECT:START/END -->`. Fetches Simple Icons glyphs (with `FALLBACK_PATHS` for brands removed from the develop branch, currently LinkedIn and Amazon). Run manually — the service list is static.

All three scripts are self-contained (stdlib + Pillow, except connect which is stdlib only) and base64-embed any images so the output SVGs have no external refs.

A fourth workflow, `.github/workflows/snake.yml`, uses `Platane/snk@v3` to regenerate `img/github-snake.svg` + `img/github-snake-dark.svg` from contribution history on a daily cron. The stats section of the README references those two files through a `<picture>` element so the snake switches with GitHub's light/dark theme.

## README marker convention

Each script edits the README between sentinel comments and fails loudly if they're missing:

- Blog: `<!-- BLOG-POSTS:START -->` / `<!-- BLOG-POSTS:END -->`
- Vinyl: `<!-- VINYL:START -->` / `<!-- VINYL:END -->`
- Connect: `<!-- CONNECT:START -->` / `<!-- CONNECT:END -->`

Inside each block the script writes a `<div align="center">` or `<p align="center">` of `<a target="_blank"><img></a>` pairs. `align="center"` is what GitHub preserves; most other HTML layout hints get stripped. Each `<img src="…">` points at the raw-URL of the per-item SVG on `main`.

## Running locally

```bash
pip install Pillow
python3 scripts/render_blog_svg.py
python3 scripts/render_vinyl_svg.py
python3 scripts/render_connect_svg.py
```

Scripts must run from the repo root (paths like `img/blog/` and `README.md` are relative). They mutate `README.md` and the `img/<kind>/` directories in place — diff before committing. Each script clears its target subdirectory's stale items before writing new ones (so dropping `COUNT` doesn't leave orphan files).

## Asset URL base

Per-item SVGs are referenced via `https://raw.githubusercontent.com/russmckendrick/russmckendrick/main/img/…`. The `RAW_BASE` constants in each render script carry the branch name — if the default branch ever changes, update all three scripts *and* re-run them so the README's `<img src>` URLs are rewritten.
