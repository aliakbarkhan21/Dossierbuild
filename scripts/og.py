"""Redraw the website's link preview. Run with:  python scripts/og.py

The headline is read from the hero in ``site/index.html`` rather than typed
into the template, so the preview cannot drift from the page it advertises.
``scripts/og.html`` is the layout; this fills it in, renders it at the
1200x630 size the og:image tags declare, and writes ``site/og.png``.
"""

from __future__ import annotations

import html
import re
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "site" / "index.html"
TEMPLATE = ROOT / "scripts" / "og.html"
OUT = ROOT / "site" / "og.png"


def hero_headline() -> str:
    page = PAGE.read_text(encoding="utf-8")
    match = re.search(r'<div class="hero[^"]*"[^>]*>.*?<h1>(.*?)</h1>', page, re.S)
    if not match:
        sys.exit("No <h1> found inside the hero in site/index.html.")
    # Keep the flag mark if the headline carries one; drop any other markup.
    inner = re.sub(r"<(?!/?span\b)[^>]+>", "", match.group(1))
    inner = re.sub(r'<span(?![^>]*class="flagged")[^>]*>(.*?)</span>', r"\1", inner, flags=re.S)
    return html.unescape(inner.replace("&nbsp;", " ")).strip()


def main() -> None:
    headline = hero_headline()
    filled = TEMPLATE.read_text(encoding="utf-8").replace("{{HEADLINE}}", headline)
    # Written next to the template so its relative image paths still resolve.
    with tempfile.NamedTemporaryFile("w", suffix=".html", dir=TEMPLATE.parent, delete=False, encoding="utf-8") as tmp:
        tmp.write(filled)
        filled_path = Path(tmp.name)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1200, "height": 630}, device_scale_factor=1)
            page.goto(filled_path.as_uri())
            page.wait_for_load_state("networkidle")
            page.evaluate("document.fonts.ready")
            page.screenshot(path=str(OUT))
            browser.close()
    finally:
        filled_path.unlink(missing_ok=True)
    print(f"Wrote {OUT.relative_to(ROOT)}: {headline!r}")


if __name__ == "__main__":
    main()
