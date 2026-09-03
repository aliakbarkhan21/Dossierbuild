"""Chromium, in its own process. Run as ``python -m dossierbuild.render.pdf_worker``.

This exists as a subprocess rather than a function call for one practical
reason: Playwright's synchronous API refuses to start inside a thread that
already has a running asyncio event loop, and Streamlit runs every script in
exactly such a thread. Isolating the browser also means a hung render can be
killed on a timeout without taking the app with it.

Contract: argv is ``<html file> <pdf out> <options json>``. Anything printed
to stdout is JSON; anything wrong is a non-zero exit with a readable message
on stderr.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

FOOTER = (
    '<div style="width:100%;font-family:Arial,Helvetica,sans-serif;font-size:8px;'
    'color:#767680;padding:0 {pad}mm;text-align:right;">'
    '<span class="pageNumber"></span> / <span class="totalPages"></span></div>'
)
EMPTY = '<span style="display:none"></span>'


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: pdf_worker <html> <out.pdf> <options-json>", file=sys.stderr)
        return 2

    html_path, out_path, options_json = argv
    options = json.loads(options_json)
    margin_mm = float(options.get("margin_mm", 16))
    margin = f"{margin_mm}mm"

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--disable-gpu", "--font-render-hinting=none"])
        try:
            page = browser.new_page()
            # A file:// URL rather than set_content so relative links and the
            # font stylesheet behave the way they would in a real browser.
            page.goto(Path(html_path).resolve().as_uri(), wait_until="load", timeout=25_000)
            # Webfonts arrive after load. Printing before they land silently
            # swaps in the fallback face and changes every line break, so the
            # PDF would not match the preview.
            try:
                page.wait_for_load_state("networkidle", timeout=6_000)
            except Exception:  # noqa: BLE001 -- offline is fine, fallbacks apply
                pass
            try:
                page.evaluate("() => document.fonts && document.fonts.ready")
            except Exception:  # noqa: BLE001
                pass

            page.pdf(
                path=out_path,
                # The size comes from the document's own @page rule, so the
                # HTML stays the single source of truth. Margins are passed
                # explicitly because Chromium's header/footer mode otherwise
                # substitutes its own.
                prefer_css_page_size=True,
                print_background=True,
                margin={"top": margin, "bottom": margin, "left": margin, "right": margin},
                display_header_footer=bool(options.get("page_numbers")),
                header_template=EMPTY,
                footer_template=FOOTER.format(pad=round(margin_mm, 1)),
            )
        finally:
            browser.close()

    print(json.dumps({"ok": True, "path": out_path}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
