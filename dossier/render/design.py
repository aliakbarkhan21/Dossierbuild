"""What the resume looks like -- kept entirely out of the profile schema.

``schema.py`` holds facts and nothing else, so every presentation decision has
to live somewhere. This is that somewhere: one small validated model covering
the choices a person actually wants to make, and nothing more.

**Curated, not open-ended.** There is no colour picker and no font box. A
resume is read for six seconds by someone deciding whether to keep reading;
the difference between a good one and a bad one is never the particular blue.
Six accents that all print legibly, nine type pairings known to sit well
together and a small type scale cover every real need and make a bad-looking
output hard to produce by accident.

Margins are the one exception, and the reason is arithmetic rather than taste:
the difference between spilling onto a second sheet and not is often two
millimetres, and the three presets step by four and five. So ``margin_mm``
keeps the presets and ``margin_custom_mm`` takes a value between
``MARGIN_MIN_MM`` and ``MARGIN_MAX_MM`` when someone needs the number in
between. A choice with a measurable right answer is not a matter of taste.

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
    Compact is the one that says no, and it says no on purpose -- it exists to
    buy back vertical space, and a portrait is the most expensive thing you
    can spend it on.

    Where the portrait is an addition rather than the point of the layout, the
    template draws it only when a real photograph exists: the monogram
    fallback belongs to the layouts built around a frame, where an empty frame
    is a hole in the page.
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
        photo=True,
    ),
    "modern": Template(
        key="modern",
        name="Modern",
        blurb="Accent header band with a side column for contact, skills and study.",
        file="modern.html.j2",
        ats=False,
        columns="Two columns",
        best_for="Sending straight to a person, or attaching to an email.",
        photo=True,
    ),
    "minimal": Template(
        key="minimal",
        name="Minimalist",
        blurb="Dates in a left gutter, no rules, generous air.",
        file="minimal.html.j2",
        ats=True,
        columns="Single column",
        best_for="Design-literate readers, and short sharp material.",
        photo=True,
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
        photo=True,
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
# Layouts
# --------------------------------------------------------------------------
#
# A template owns the top of the page. A layout owns everything below it: what
# a section heading looks like, where the section's name sits, and what
# carries the eye from one entry to the next.
#
# They are separate because they were not, and it showed. Eight templates all
# shared one body -- heading, entries, next heading -- so six named looks over
# those eight came out as one design in six colours, which is what a person
# clicking through them saw. Two axes make thirty-two page designs out of the
# same eight headers, and the difference between any two of them is
# structural rather than a matter of palette.
#
# The CSS is in templates/_layouts.html.j2, included after each template's own
# block so that the two compose in a defined order.

LAYOUTS: dict[str, tuple[str, str]] = {
    "stacked": ("Stacked", "Heading above its section, full width. The plain arrangement."),
    "gutter": ("Gutter", "Section names in a column down the left, content beside them."),
    "rail": ("Rail", "A hairline spine with a node at every entry."),
    "panel": ("Panel", "Headings in a tinted band, entries divided by a hairline."),
}

DEFAULT_LAYOUT = "stacked"


# --------------------------------------------------------------------------
# Page, margins, type
# --------------------------------------------------------------------------


def normalise_tag(value: str) -> str:
    """One spelling for a tag, wherever it was typed.

    Lowercased and stripped of a leading hash, because people type "#backend"
    in one box and "Backend" in another and mean the same thing. Anything that
    normalises to nothing is no tag at all.
    """
    return value.strip().lstrip("#").strip().lower()


@dataclass(frozen=True)
class Page:
    key: str
    name: str
    width_mm: float
    height_mm: float
    css: str


# The two that matter first, then the rest in the order somebody would reach
# for them. ``css`` is what goes in ``@page { size: ... }``: a CSS keyword
# where one exists, and a pair of lengths where it does not -- US Executive is
# a real paper size and not a CSS one, and Chromium takes the dimensions
# either way. The millimetres are what the app measures with, so a keyword and
# its numbers have to agree; `check_phase2` prints one PDF per size and reads
# the page box back out to prove they do.
PAGES: dict[str, Page] = {
    "a4": Page("a4", "A4", 210.0, 297.0, "A4"),
    "letter": Page("letter", "US Letter", 215.9, 279.4, "Letter"),
    "a5": Page("a5", "A5", 148.0, 210.0, "A5"),
    "b5": Page("b5", "B5", 176.0, 250.0, "B5"),
    "legal": Page("legal", "US Legal", 215.9, 355.6, "Legal"),
    "executive": Page(
        "executive", "US Executive", 184.15, 266.7, "184.15mm 266.7mm"
    ),
}

# Millimetres, because that is what a printer thinks in. 12mm is about as
# tight as a resume should go before it reads as crowded; 21mm is the widest
# that still leaves room for content.
MARGINS: dict[str, tuple[str, float]] = {
    "tight": ("Tight", 12.0),
    "normal": ("Normal", 16.0),
    "wide": ("Wide", 21.0),
}

# What the slider can ask for. 2mm is about the narrowest a consumer printer
# will put ink at -- below that the driver starts clipping -- and 20mm is
# already a wide letter margin; past it a resume is mostly paper. The named
# presets above stay: they are what the curated looks set, and "Tight" is a
# more useful thing for a look to say than "12".
MARGIN_MIN_MM = 2.0
MARGIN_MAX_MM = 20.0

# How a date prints. Two options rather than a format string: "Feb 2025" is
# the resume convention almost everywhere and is unambiguous to a parser,
# while "02/2025" is normal in Pakistan and much of Europe. A free-text format
# would let someone print a date no reader could parse.
DATE_FORMATS: dict[str, tuple[str, str]] = {
    "month": ("Feb 2025", "Month name. The usual resume convention."),
    "numeric": ("02/2025", "Numeric, month first."),
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
    "display": Pairing(
        key="display",
        name="Display serif",
        blurb="Playfair headings over Lato. High contrast; the name carries.",
        heading='"Playfair Display", Georgia, "Times New Roman", serif',
        body='"Lato", "Segoe UI", Helvetica, Arial, sans-serif',
        google="family=Playfair+Display:wght@400;600;700&family=Lato:wght@400;700",
    ),
    "grotesque": Pairing(
        key="grotesque",
        name="Grotesque",
        blurb="Space Grotesk headings over Inter. Reads as a product, not a form.",
        heading='"Space Grotesk", "Segoe UI", Helvetica, Arial, sans-serif',
        body='"Inter", "Segoe UI", Helvetica, Arial, sans-serif',
        google=(
            "family=Space+Grotesk:wght@400;500;600;700"
            "&family=Inter:wght@400;500;600;700"
        ),
    ),
    "slab": Pairing(
        key="slab",
        name="Slab",
        blurb="Roboto Slab headings over Roboto. Solid, engineering-adjacent.",
        heading='"Roboto Slab", Rockwell, Georgia, serif',
        body='"Roboto", "Segoe UI", Helvetica, Arial, sans-serif',
        google="family=Roboto+Slab:wght@400;600;700&family=Roboto:wght@400;500;700",
    ),
    "humanist": Pairing(
        key="humanist",
        name="Humanist",
        blurb="Lora headings over Open Sans. Warmer than the formal pairing.",
        heading='"Lora", Georgia, "Times New Roman", serif',
        body='"Open Sans", "Segoe UI", Helvetica, Arial, sans-serif',
        google="family=Lora:wght@400;600;700&family=Open+Sans:wght@400;600;700",
    ),
    "condensed": Pairing(
        key="condensed",
        name="Condensed",
        blurb="Archivo Narrow headings over Source Sans. Buys back a line or two.",
        heading='"Archivo Narrow", "Arial Narrow", "Segoe UI", sans-serif',
        body='"Source Sans 3", "Segoe UI", Helvetica, Arial, sans-serif',
        google=(
            "family=Archivo+Narrow:wght@400;600;700"
            "&family=Source+Sans+3:wght@400;600;700"
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
# A look is a family of four page designs, not a colour scheme and not one
# design. The four share the accent, the type pairing and the spacing -- that
# is what makes them a family -- and each one takes a different template *and*
# a different layout, so no two are the same document in another colour.
# Across the six, no two share an accent or a type pairing either.
#
# Twenty-four designs, from eight headers and four ways of setting the body.
# The alternative was twenty-four hand-written templates that would drift
# apart the first time a field was added to the schema.
#
# Every control stays available afterwards; a look is a starting point, not a
# mode.


@dataclass(frozen=True)
class Variant:
    """One of a look's four designs: which header, and how the body is set."""

    key: str
    name: str
    values: dict[str, Any]


@dataclass(frozen=True)
class Look:
    key: str
    name: str
    blurb: str
    shared: dict[str, Any]
    """Colour, type and spacing. This is what makes the four one family."""

    variants: tuple[Variant, ...]
    """Four page designs. Each takes a different template *and* a different
    layout, so no two of them are the same document in another colour."""

    def design_values(self, variant_key: str = "") -> dict[str, Any]:
        """Everything a design needs for one variant, the first by default."""
        chosen = next(
            (v for v in self.variants if v.key == variant_key), self.variants[0]
        )
        return {**self.shared, **chosen.values}

    @property
    def values(self) -> dict[str, Any]:
        return self.design_values()


LOOKS: tuple[Look, ...] = (
    Look(
        "formal", "Formal", "Ink and a serif. What a portal expects to receive.",
        {"accent": "ink", "fonts": "serif_sans", "leading": "normal",
         "margin": "normal", "scale": 100, "show_photo": False,
         "date_format": "month"},
        (
            Variant("ruled", "Ruled", {"template": "classic", "layout": "stacked"}),
            Variant("gutter", "Gutter", {"template": "minimal", "layout": "gutter"}),
            Variant("banded", "Banded", {"template": "executive", "layout": "panel"}),
            Variant("spine", "Spine", {"template": "gazette", "layout": "rail"}),
        ),
    ),
    Look(
        "press", "Press", "A Playfair masthead, wide margins, room to breathe.",
        {"accent": "burgundy", "fonts": "display", "leading": "airy",
         "margin": "wide", "scale": 100, "show_photo": False,
         "date_format": "month"},
        (
            Variant("masthead", "Masthead", {"template": "gazette", "layout": "stacked"}),
            Variant("column", "Column", {"template": "minimal", "layout": "gutter"}),
            Variant("banded", "Banded", {"template": "classic", "layout": "panel"}),
            Variant("spine", "Spine", {"template": "executive", "layout": "rail"}),
        ),
    ),
    Look(
        "corporate", "Corporate", "Navy and Space Grotesk, with a portrait.",
        {"accent": "navy", "fonts": "grotesque", "leading": "normal",
         "margin": "normal", "scale": 100, "show_photo": True,
         "date_format": "numeric"},
        (
            Variant("ruled", "Ruled", {"template": "executive", "layout": "stacked"}),
            Variant("gutter", "Gutter", {"template": "classic", "layout": "gutter"}),
            Variant("panel", "Panel", {"template": "modern", "layout": "panel"}),
            Variant("spine", "Spine", {"template": "compact", "layout": "rail"}),
        ),
    ),
    Look(
        "studio", "Studio", "Bronze and Lora, set large. The layout is part of it.",
        {"accent": "bronze", "fonts": "humanist", "leading": "airy",
         "margin": "normal", "scale": 104, "show_photo": True,
         "date_format": "month"},
        (
            Variant("editorial", "Editorial", {"template": "editorial", "layout": "stacked"}),
            Variant("column", "Column", {"template": "minimal", "layout": "gutter"}),
            Variant("banded", "Banded", {"template": "gazette", "layout": "panel"}),
            Variant("spine", "Spine", {"template": "modern", "layout": "rail"}),
        ),
    ),
    Look(
        "continental", "Continental", "The European CV: teal, a portrait, tight margins.",
        {"accent": "teal", "fonts": "sans", "leading": "normal",
         "margin": "tight", "scale": 96, "show_photo": True,
         "date_format": "numeric"},
        (
            Variant("side", "Side column", {"template": "sidebar", "layout": "stacked"}),
            Variant("gutter", "Gutter", {"template": "modern", "layout": "gutter"}),
            Variant("panel", "Panel", {"template": "editorial", "layout": "panel"}),
            Variant("spine", "Spine", {"template": "classic", "layout": "rail"}),
        ),
    ),
    Look(
        "dense", "Dense", "Forest and condensed type, for more history than page.",
        {"accent": "forest", "fonts": "condensed", "leading": "tight",
         "margin": "tight", "scale": 92, "show_photo": False,
         "date_format": "numeric"},
        (
            Variant("compact", "Compact", {"template": "compact", "layout": "stacked"}),
            Variant("gutter", "Gutter", {"template": "compact", "layout": "gutter"}),
            Variant("banded", "Banded", {"template": "minimal", "layout": "panel"}),
            Variant("spine", "Spine", {"template": "executive", "layout": "rail"}),
        ),
    ),
)


# --------------------------------------------------------------------------
# The model
# --------------------------------------------------------------------------


class Design(BaseModel):
    """One resume's presentation. Validated, so a stale file cannot break a render."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    template: str = DEFAULT_TEMPLATE
    layout: str = DEFAULT_LAYOUT
    page: str = "a4"
    margin: str = "normal"
    margin_custom_mm: float | None = None
    """An exact margin in millimetres, or None to use the named preset.

    Two fields rather than replacing ``margin`` with a number, because the
    two are asked for by different things. A look says "Tight" -- a judgement
    that should keep meaning the right amount if the presets are ever
    retuned -- while someone dragging the slider means 13mm and nothing else.
    The number wins when it is set, and applying a look clears it, so the
    look's own choice is what shows.
    """
    leading: str = "normal"
    accent: str = "ink"
    fonts: str = "serif_sans"
    scale: int = 100
    order: list[str] = Field(default_factory=lambda: list(SECTION_KEYS))
    hidden: list[str] = Field(default_factory=list)
    focus: str = ""
    """Which job family this printing is aimed at. "" prints everything.

    The tags themselves live on the profile, because "this line is the kind
    of thing a backend team cares about" is a fact about the work. Which one
    to *print* is a presentation decision and lives here -- the same split as
    ``hidden``, which holds section keys rather than putting a "show me" flag
    on every section in ``schema.py``.

    Free text rather than a validated enum, because the tags are the user's
    own vocabulary. A focus nobody has tagged anything with simply prints the
    untagged core, which is a coherent resume rather than an error.
    """
    show_links: bool = True
    show_headline: bool = True
    show_page_numbers: bool = False
    show_photo: bool = True
    date_format: str = "month"

    # Every validator below repairs rather than raises. A design that cannot
    # be honoured should quietly fall back to something printable -- losing a
    # colour choice is not worth an error screen in front of the resume.
    @field_validator("template")
    @classmethod
    def _template(cls, v: str) -> str:
        return v if v in TEMPLATES else DEFAULT_TEMPLATE

    @field_validator("layout")
    @classmethod
    def _layout(cls, v: str) -> str:
        return v if v in LAYOUTS else DEFAULT_LAYOUT

    @field_validator("page")
    @classmethod
    def _page(cls, v: str) -> str:
        return v if v in PAGES else "a4"

    @field_validator("margin")
    @classmethod
    def _margin(cls, v: str) -> str:
        return v if v in MARGINS else "normal"

    @field_validator("margin_custom_mm")
    @classmethod
    def _margin_custom_mm(cls, v: float | None) -> float | None:
        # Clamped rather than rejected: a design saved by a build with a wider
        # range should open with the nearest margin this one can print, not
        # fail to load and take the whole design with it.
        if v is None:
            return None
        return round(min(MARGIN_MAX_MM, max(MARGIN_MIN_MM, float(v))), 1)

    @field_validator("date_format")
    @classmethod
    def _date_format(cls, v: str) -> str:
        return v if v in DATE_FORMATS else "month"

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

    @field_validator("focus")
    @classmethod
    def _focus(cls, v: str) -> str:
        # Normalised the way the editor writes them, so "#Backend" typed in
        # one place matches "backend" stored in another.
        return normalise_tag(v)

    @field_validator("hidden")
    @classmethod
    def _hidden(cls, v: list[str]) -> list[str]:
        return [k for k in dict.fromkeys(v) if k in SECTION_KEYS]

    # -- derived values the templates read ---------------------------------

    @property
    def template_spec(self) -> Template:
        return TEMPLATES[self.template]

    @property
    def page_spec(self) -> Page:
        return PAGES[self.page]

    @property
    def margin_mm(self) -> float:
        if self.margin_custom_mm is not None:
            return self.margin_custom_mm
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
