"""Printing the document, and then checking what came out.

Two halves. ``render_pdf`` hands the HTML to Chromium in a subprocess and
returns bytes. ``pdf_report`` reads those bytes back with pypdf and answers
the questions that actually matter about a resume PDF: how many pages is it,
and can a machine read the text at all.

That second half is not decoration. The single worst outcome in this whole
pipeline is a PDF that looks perfect and parses as an empty document, because
nobody finds out until the application is already rejected. Reading the text
layer back is a three-line check that makes that failure impossible to ship.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from ..schema import Profile

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Windows opens a console window for a subprocess by default; the app is a
# GUI, so the flag suppresses the flash. Absent everywhere else.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class PDFError(RuntimeError):
    """Rendering failed, with a message worth showing a person."""


def chromium_ready() -> tuple[bool, str]:
    """Whether the browser Playwright needs is actually installed."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False, "Playwright is not installed. Run: pip install playwright"
    try:
        with sync_playwright() as p:
            path = Path(p.chromium.executable_path)
    except Exception as exc:  # noqa: BLE001
        return False, f"Playwright could not be started: {exc}"
    if not path.exists():
        return False, (
            "Playwright is installed but its Chromium build is not. "
            "Run: python -m playwright install chromium"
        )
    return True, str(path)


def render_pdf(
    html: str, *, margin_mm: float, page_numbers: bool = False, timeout: float = 120.0
) -> bytes:
    """HTML in, PDF bytes out. Raises ``PDFError`` with something readable.

    Takes the two values it actually uses rather than a whole ``Design``, so
    that the caller can memoise on them: two designs differing only in accent
    colour produce different HTML, and the HTML is what matters here.
    """
    options = {"margin_mm": margin_mm, "page_numbers": page_numbers}
    with tempfile.TemporaryDirectory(prefix="dossierbuild-") as tmp:
        folder = Path(tmp)
        html_file = folder / "resume.html"
        pdf_file = folder / "resume.pdf"
        html_file.write_text(html, encoding="utf-8")

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "dossierbuild.render.pdf_worker",
                    str(html_file),
                    str(pdf_file),
                    json.dumps(options),
                ],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=_NO_WINDOW,
            )
        except subprocess.TimeoutExpired as exc:
            raise PDFError(
                f"The browser took longer than {timeout:.0f}s and was stopped. "
                "This usually means it could not reach Google Fonts -- the "
                "resume will still print with fallback fonts if you try again."
            ) from exc

        if result.returncode != 0 or not pdf_file.exists():
            detail = (result.stderr or result.stdout or "").strip()
            ok, message = chromium_ready()
            if not ok:
                raise PDFError(message)
            raise PDFError(_short(detail) or "Chromium exited without writing a PDF.")

        return pdf_file.read_bytes()


def _short(text: str, limit: int = 400) -> str:
    """The last few lines of a traceback say more than the first few."""
    lines = [line for line in text.splitlines() if line.strip()]
    tail = "\n".join(lines[-4:])
    return tail[:limit]


# --------------------------------------------------------------------------
# Reading the result back
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Report:
    pages: int
    words: int
    characters: int
    size_bytes: int
    machine_readable: bool
    found: dict[str, bool] = field(default_factory=dict)
    text: str = ""

    @property
    def size_kb(self) -> int:
        return max(1, round(self.size_bytes / 1024))

    @property
    def missing(self) -> list[str]:
        return [label for label, ok in self.found.items() if not ok]


def pdf_report(pdf: bytes, profile: Profile) -> Report:
    """Page count, and proof that the text layer survived.

    ``found`` checks specific strings from the profile rather than a generic
    "is there text": a PDF can carry plenty of extracted text while the name
    itself sits in an image or a font with a broken encoding, which is exactly
    the case that ruins an application.
    """
    from io import BytesIO

    from pypdf import PdfReader

    reader = PdfReader(BytesIO(pdf))
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    flat = " ".join(text.split()).lower()

    checks: dict[str, bool] = {}
    name = profile.basics.name.strip()
    if name:
        # Compared word by word: extractors sometimes lose a space between
        # given and family name, and that is not a failure worth flagging.
        checks["Name"] = all(part.lower() in flat for part in name.split())
    if profile.basics.email.strip():
        checks["Email"] = profile.basics.email.strip().lower() in flat.replace(" ", "")
    if profile.basics.phone.strip():
        digits = "".join(c for c in profile.basics.phone if c.isdigit())
        checks["Phone"] = bool(digits) and digits[-6:] in "".join(
            c for c in flat if c.isdigit()
        )

    return Report(
        pages=len(reader.pages),
        words=len(flat.split()),
        characters=len(flat),
        size_bytes=len(pdf),
        machine_readable=len(flat) > 120,
        found=checks,
        text=text,
    )
