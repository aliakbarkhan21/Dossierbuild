"""Phase 2: turning the master profile into a printable document.

The split here is deliberate and worth stating once:

* ``design``  -- the choices a person makes (template, page size, accent, type).
* ``context`` -- the profile flattened into exactly what a template needs.
* ``html``    -- Jinja2 turning the two into one self-contained HTML document.
* ``pdf``     -- headless Chromium printing that document.

Nothing in this package imports Streamlit. The renderer is a library the UI
calls, which keeps it testable from a plain script and means the same call
produces the same bytes whether it came from a button or a terminal.
"""

from .design import Design, TEMPLATES, load_design, save_design
from .html import render_html
from .pdf import PDFError, pdf_report, render_pdf

__all__ = [
    "Design",
    "TEMPLATES",
    "load_design",
    "save_design",
    "render_html",
    "render_pdf",
    "pdf_report",
    "PDFError",
]
