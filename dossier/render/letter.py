"""A cover letter on the same paper as the resume.

Everything here leans on `html.py`: the same Jinja environment, the same
`_variables`, the same `_base` template, so the letter gets the sheet at exact
paper size, the page-break markers, the fit script and the print/preview
equality without a line of its own. What it adds is one template and the
handful of fields a letter has that a resume does not.

**It takes the resume's `Design` on purpose.** A letter in a different
typeface from the CV attached to it looks like two people applied. There is no
separate letter design, and adding one would be a way to make that mistake.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from ..core.schema import Profile
from .context import build_context
from .naming import safe_stem
from .design import Design
from .html import _env, _variables

# A letter's body is the whole document, so it is set slightly larger than a
# resume's dense column and given more air. The multiplier rides on top of the
# design's own scale rather than replacing it.
LETTER_SCALE = 1.06
LETTER_LEADING = 1.5


@dataclass
class LetterDocument:
    """What the template needs. Plain strings, already audited and edited."""

    paragraphs: list[str]
    greeting: str = "Dear Hiring Manager,"
    closing: str = "Yours faithfully,"
    signature: str = ""
    recipient: str = ""
    company: str = ""
    role: str = ""
    date: str = ""
    invented: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.date:
            # Written out rather than numeric: 03/09/2026 is two different
            # days depending on which side of the Atlantic reads it, and a
            # letter is the one document with a date on the face of it.
            self.date = date.today().strftime("%-d %B %Y") if _supports_dash() else _long_date()


def _supports_dash() -> bool:
    """glibc understands ``%-d``; the Windows C runtime does not."""
    try:
        date(2026, 9, 3).strftime("%-d")
    except ValueError:
        return False
    return True


def _long_date() -> str:
    today = date.today()
    return f"{today.day} {today:%B %Y}"


def render_letter_html(
    profile: Profile,
    design: Design,
    letter: LetterDocument,
    *,
    preview: bool = False,
    zoom: float = 0.0,
    fit: str = "width",
    fitbar: bool = True,
) -> str:
    """The letter as one self-contained HTML document."""
    # The letter reads as prose, not as a dense column, so it is set a little
    # larger and looser than whatever the resume is at -- while still tracking
    # the design, so a person who chose 92% gets a proportionally smaller
    # letter rather than a fixed one.
    roomier = design.model_copy(
        update={"scale": round(design.scale * LETTER_SCALE), "leading": "airy"}
    )
    variables = _variables(
        roomier,
        preview=preview,
        zoom=zoom,
        breaks=True,
        fitbar=fitbar,
        fit=fit,
        scroll=True,
        desk_pad=16,
        desk_bg="#EDEDF1",
    )
    variables["leading"] = LETTER_LEADING
    template = _env().get_template("letter.html.j2")
    return template.render(
        r=build_context(profile, roomier),
        letter=letter,
        **variables,
    )


def letter_filename(profile: Profile, letter: LetterDocument) -> str:
    """Named for the reader, the way `suggested_filename` names the resume."""
    parts = (profile.basics.name, "Cover Letter", letter.company)
    stem = "-".join(s for s in (safe_stem(p) for p in parts) if s)
    return f"{stem or 'Cover-Letter'}.pdf"
