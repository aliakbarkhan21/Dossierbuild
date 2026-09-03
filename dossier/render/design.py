"""What the resume looks like -- kept entirely out of the profile schema.

``schema.py`` holds facts and nothing else, so every presentation decision has
to live somewhere. This is that somewhere: one small validated model covering
the choices a person actually wants to make, and nothing more.

**Curated, not open-ended.** There is no colour picker, no font box, no margin
slider. A resume is read for six seconds by someone deciding whether to keep
reading; the difference between a good one and a bad one is never the
particular blue. Six accents that all print legibly, four type pairings known
to sit well together, three margin widths and a small type scale cover every
real need and make a bad-looking output hard to produce by accident.

The design is stored beside the UI preferences rather than inside
``profile.json``: the profile is the material, this is how one rendering of it
is dressed. Phase 5 will save several of these, one per application, which is
another reason to keep them separable.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..core.storage import DATA_DIR

DESIGN_PATH = DATA_DIR / "design.json"

MM_PER_INCH = 25.4
CSS_DPI = 96.0


def mm_to_px(mm: float) -> float:
    """CSS pixels for a physical millimetre, at the 96dpi CSS reference."""
    return mm * CSS_DPI / MM_PER_INCH


# --------------------------------------------------------------------------
# Templates
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Template:
    key: str
    name: str
    blurb: str
    file: str
    ats: bool
    columns: str
    best_for: str
    photo: bool = False
    """Whether this layout has a place for a portrait.

    Kept per template rather than as a global switch: a photo dropped into a
    layout with nowhere to put it does not look neutral, it looks broken.
    """


# ``ats`` is stated honestly rather than flattered. An applicant tracking
# system reads the PDF's text layer in document order; a single column comes
# out in the order it was written, while a side column can interleave a job
# title with a skills list. Every template here produces real selectable text
# -- no images, no text inside tables -- so the flag is about reading *order*,
# which is the part a two-column layout genuinely risks.
TEMPLATES: dict[str, Template] = {
    "classic": Template(
        key="classic",
        name="Classic",
        blurb="Centred header, ruled section headings, serif throughout.",
        file="classic.html.j2",
        ats=True,
        columns="Single column",
        best_for="Applications through a portal, and anything conservative.",
    ),
    "modern": Template(
        key="modern",
        name="Modern",
        blurb="Accent header band with a side column for contact, skills and study.",
        file="modern.html.j2",
        ats=False,
        columns="Two columns",
        best_for="Sending straight to a person, or attaching to an email.",
    ),
    "minimal": Template(
        key="minimal",
        name="Minimalist",
        blurb="Dates in a left gutter, no rules, generous air.",
        file="minimal.html.j2",
        ats=True,
        columns="Single column",
        best_for="Design-literate readers, and short sharp material.",
    ),
    "compact": Template(
        key="compact",
        name="Compact",
        blurb="Tight leading and paired skill columns, for fitting a lot on one page.",
        file="compact.html.j2",
        ats=True,
        columns="Single column",
        best_for="When there is more material than page.",
    ),
    "executive": Template(
        key="executive",
        name="Executive",
        blurb="Name set large in the accent, ruled headings, skills in a grid.",
        file="executive.html.j2",
        ats=True,
        columns="Single column",
        best_for="Industry roles where the title should land before the dates.",
        photo=True,
    ),
    "gazette": Template(
        key="gazette",
        name="Gazette",
        blurb="Centred masthead, banded headings, dotted leaders to the dates.",
        file="gazette.html.j2",
        ats=True,
        columns="Single column",
        best_for="Formal applications, and anywhere a page should read like print.",
    ),
    "sidebar": Template(
        key="sidebar",
        name="Sidebar",
        blurb="Full-height accent column carrying the portrait, contact and skills.",
        file="sidebar.html.j2",
        ats=False,
        columns="Two columns",
        best_for="European CVs and anything sent directly to a person.",
        photo=True,
    ),
    "editorial": Template(
        key="editorial",
        name="Editorial",
        blurb="Centred portrait, small-caps side column, entries on a dotted rail.",
        file="editorial.html.j2",
        ats=False,
        columns="Two columns",
        best_for="Design-adjacent roles, where the layout is part of the pitch.",
        photo=True,
    ),
}

DEFAULT_TEMPLATE = "classic"


# --------------------------------------------------------------------------
# Page, margins, type
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Page:
    key: str
    name: str
    width_mm: float
    height_mm: float
    css: str


PAGES: dict[str, Page] = {
    "a4": Page("a4", "A4", 210.0, 297.0, "A4"),
    "letter": Page("letter", "US Letter", 215.9, 279.4, "Letter"),
}

# Millimetres, because that is what a printer thinks in. 12mm is about as
# tight as a resume should go before it reads as crowded; 21mm is the widest
# that still leaves room for content.
MARGINS: dict[str, tuple[str, float]] = {
    "tight": ("Tight", 12.0),
    "normal": ("Normal", 16.0),
    "wide": ("Wide", 21.0),
}

LEADING: dict[str, tuple[str, float]] = {
    "tight": ("Tight", 1.28),
    "normal": ("Normal", 1.42),
    "airy": ("Airy", 1.58),
}

# Print colours, not screen colours. Each is dark enough to stay legible when
# a recruiter prints in greyscale -- the most common way a "designed" resume
# falls apart.
ACCENTS: dict[str, tuple[str, str]] = {
    "ink": ("Ink", "#1B1B1F"),
    "navy": ("Navy", "#1F3A63"),
    "teal": ("Teal", "#1C5A57"),
    "forest": ("Forest", "#2A5238"),
    "burgundy": ("Burgundy", "#6E2436"),
    "bronze": ("Bronze", "#7A4A1E"),
}


@dataclass(frozen=True)
class Pairing:
    key: str
    name: str
    blurb: str
    heading: str
    body: str
    google: str


# Every stack ends in a face that ships with Windows and macOS, so a failed
# webfont fetch degrades to something chosen rather than to Times New Roman.
PAIRINGS: dict[str, Pairing] = {
    "serif_sans": Pairing(
        key="serif_sans",
        name="Serif & Sans",
        blurb="Serif headings, sans body. The standard formal pairing.",
        heading='"Source Serif 4", Georgia, "Times New Roman", serif',
        body='"Source Sans 3", "Segoe UI", Helvetica, Arial, sans-serif',
        google=(
            "family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700"
            "&family=Source+Sans+3:wght@400;600;700"
        ),
    ),
    "sans": Pairing(
        key="sans",
        name="All sans",
        blurb="Inter throughout. Cleanest scan, safest through any parser.",
        heading='"Inter", "Segoe UI", Helvetica, Arial, sans-serif',
        body='"Inter", "Segoe UI", Helvetica, Arial, sans-serif',
        google="family=Inter:wght@400;500;600;700",
    ),
    "book": Pairing(
        key="book",
        name="Book serif",
        blurb="EB Garamond throughout. Reads like a page, not a form.",
        heading='"EB Garamond", Garamond, Georgia, serif',
        body='"EB Garamond", Garamond, Georgia, serif',
        google="family=EB+Garamond:wght@400;500;600;700",
    ),
    "technical": Pairing(
        key="technical",
        name="Technical",
        blurb="IBM Plex Sans, with a mono for dates and labels.",
        heading='"IBM Plex Sans", "Segoe UI", Helvetica, Arial, sans-serif',
        body='"IBM Plex Sans", "Segoe UI", Helvetica, Arial, sans-serif',
        google=(
            "family=IBM+Plex+Sans:wght@400;500;600;700"
            "&family=IBM+Plex+Mono:wght@400;500"
        ),
    ),
}

MONO_STACK = '"IBM Plex Mono", "JetBrains Mono", Consolas, monospace'

# Section keys the resume can show, in the default order. ``basics`` is not
# here: the header is not optional, and a resume without a name on it is not a
# document anyone wants.
RESUME_SECTIONS: tuple[tuple[str, str], ...] = (
    ("summary", "Summary"),
    ("experience", "Experience"),
    ("projects", "Projects"),
    ("education", "Education"),
    ("skills", "Skills"),
    ("certifications", "Certifications"),
    ("awards", "Honors"),
    ("achievements", "Achievements"),
)

SECTION_KEYS: tuple[str, ...] = tuple(key for key, _label in RESUME_SECTIONS)
SECTION_LABELS: dict[str, str] = dict(RESUME_SECTIONS)


# --------------------------------------------------------------------------
# Looks
# --------------------------------------------------------------------------
#
# Six controls, each independently sensible, still make thirty-odd
# combinations -- and a few of those combinations are much better than the
# rest. A look is one of the good ones, named: template, colour, type and
# spacing set together the way someone who does this for a living would set
# them. Every control stays available afterwards; a look is a starting point,
# not a mode.


@dataclass(frozen=True)
class Look:
    key: str
    name: str
    blurb: str
    values: dict[str, Any]


LOOKS: tuple[Look, ...] = (
    Look("formal", "Formal", "Classic, ink, serif headings. The safe default.",
         {"template": "classic", "accent": "ink", "fonts": "serif_sans",
          "leading": "normal", "margin": "normal", "scale": 100}),
    Look("press", "Press", "Gazette set in Garamond with room to breathe.",
         {"template": "gazette", "accent": "ink", "fonts": "book",
          "leading": "airy", "margin": "wide", "scale": 100}),
    Look("corporate", "Corporate", "Executive in navy, all sans.",
         {"template": "executive", "accent": "navy", "fonts": "sans",
          "leading": "normal", "margin": "normal", "scale": 100}),
    Look("studio", "Studio", "Editorial in burgundy, with a portrait.",
         {"template": "editorial", "accent": "burgundy", "fonts": "book",
          "leading": "normal", "margin": "normal", "scale": 100, "show_photo": True}),
    Look("continental", "Continental", "The European CV: side column, photo, teal.",
         {"template": "sidebar", "accent": "teal", "fonts": "sans",
          "leading": "normal", "margin": "tight", "scale": 96, "show_photo": True}),
    Look("dense", "Dense", "Compact, tight everything, for a long history.",
         {"template": "compact", "accent": "ink", "fonts": "sans",
          "leading": "tight", "margin": "tight", "scale": 96}),
)


# --------------------------------------------------------------------------
# The model
# --------------------------------------------------------------------------


class Design(BaseModel):
    """One resume's presentation. Validated, so a stale file cannot break a render."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    template: str = DEFAULT_TEMPLATE
    page: str = "a4"
    margin: str = "normal"
    leading: str = "normal"
    accent: str = "ink"
    fonts: str = "serif_sans"
    scale: int = 100
    order: list[str] = Field(default_factory=lambda: list(SECTION_KEYS))
    hidden: list[str] = Field(default_factory=list)
    show_links: bool = True
    show_headline: bool = True
    show_page_numbers: bool = False
    show_photo: bool = True
    photo_shape: str = "circle"

    # Every validator below repairs rather than raises. A design that cannot
    # be honoured should quietly fall back to something printable -- losing a
    # colour choice is not worth an error screen in front of the resume.
    @field_validator("template")
    @classmethod
    def _template(cls, v: str) -> str:
        return v if v in TEMPLATES else DEFAULT_TEMPLATE

    @field_validator("page")
    @classmethod
    def _page(cls, v: str) -> str:
        return v if v in PAGES else "a4"

    @field_validator("margin")
    @classmethod
    def _margin(cls, v: str) -> str:
        return v if v in MARGINS else "normal"

    @field_validator("leading")
    @classmethod
    def _leading(cls, v: str) -> str:
        return v if v in LEADING else "normal"

    @field_validator("accent")
    @classmethod
    def _accent(cls, v: str) -> str:
        return v if v in ACCENTS else "ink"

    @field_validator("fonts")
    @classmethod
    def _fonts(cls, v: str) -> str:
        return v if v in PAIRINGS else "serif_sans"

    @field_validator("scale")
    @classmethod
    def _scale(cls, v: int) -> int:
        return max(90, min(112, int(v)))

    @field_validator("order")
    @classmethod
    def _order(cls, v: list[str]) -> list[str]:
        """Keep known keys in the given order, then append anything missing.

        A section added to the schema in a later version therefore appears at
        the end of an old saved design instead of silently disappearing.
        """
        deduped = list(dict.fromkeys(k for k in v if k in SECTION_KEYS))
        return deduped + [k for k in SECTION_KEYS if k not in deduped]

    @field_validator("hidden")
    @classmethod
    def _hidden(cls, v: list[str]) -> list[str]:
        return [k for k in dict.fromkeys(v) if k in SECTION_KEYS]

    @field_validator("photo_shape")
    @classmethod
    def _photo_shape(cls, v: str) -> str:
        return v if v in ("circle", "square") else "circle"

    # -- derived values the templates read ---------------------------------

    @property
    def template_spec(self) -> Template:
        return TEMPLATES[self.template]

    @property
    def page_spec(self) -> Page:
        return PAGES[self.page]

    @property
    def margin_mm(self) -> float:
        return MARGINS[self.margin][1]

    @property
    def leading_value(self) -> float:
        return LEADING[self.leading][1]

    @property
    def accent_hex(self) -> str:
        return ACCENTS[self.accent][1]

    @property
    def pairing(self) -> Pairing:
        return PAIRINGS[self.fonts]

    @property
    def wants_photo(self) -> bool:
        """A portrait is drawn only where the layout has a place for one."""
        return self.show_photo and self.template_spec.photo

    def is_look(self, look: "Look") -> bool:
        """Whether this design still matches a look, field for field."""
        return all(getattr(self, field) == value for field, value in look.values.items())

    def with_look(self, look: "Look") -> "Design":
        return self.model_copy(update=dict(look.values))

    def visible_sections(self) -> list[str]:
        return [key for key in self.order if key not in self.hidden]

    def with_moved(self, key: str, delta: int) -> "Design":
        """A copy with one section moved up or down the order."""
        order = list(self.order)
        if key not in order:
            return self
        index = order.index(key)
        target = max(0, min(len(order) - 1, index + delta))
        if target == index:
            return self
        order.insert(target, order.pop(index))
        return self.model_copy(update={"order": order})

    def with_toggled(self, key: str) -> "Design":
        hidden = (
            [k for k in self.hidden if k != key]
            if key in self.hidden
            else [*self.hidden, key]
        )
        return self.model_copy(update={"hidden": hidden})


# --------------------------------------------------------------------------
# Persistence
# --------------------------------------------------------------------------
#
# Same stance as settings.py, for the same reason: this file holds
# preferences, not irreplaceable data. A missing or corrupt design costs a
# fallback to the defaults, never an error the user has to deal with.


def load_design(path: Path | None = None) -> Design:
    path = path or DESIGN_PATH
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return Design.model_validate(raw)
    except Exception:  # noqa: BLE001 -- missing, corrupt, outdated: same answer
        return Design()


def save_design(design: Design, path: Path | None = None) -> None:
    path = path or DESIGN_PATH
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(design.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8"
        )
        os.replace(tmp, path)
    except Exception:  # noqa: BLE001
        pass


def design_key(design: Design) -> str:
    """A stable string to cache a render against."""
    payload: dict[str, Any] = design.model_dump(mode="json")
    return json.dumps(payload, sort_keys=True)
