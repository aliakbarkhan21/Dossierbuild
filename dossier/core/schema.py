"""The master profile data contract.

This module is the single source of truth for the shape of a resume's raw
facts. Templates render it, the AI tailor rewrites parts of it, the ATS check
scans text pulled out of it, and saved application versions reference it.

Two rules keep it useful:

1. It holds *facts only*. No colours, no fonts, no section ordering, no
   "include this in that application" flags. Presentation belongs to the
   template layer and per-application choices belong to the version layer.
   This file is the one thing maintained by hand, so nothing in it should go
   stale when a particular job comes and goes.

2. When a template needs a field that is not here, the field gets added here
   and ``SCHEMA_VERSION`` is bumped -- rather than the template working around
   the gap. Both templates read this exact schema.
"""

from __future__ import annotations

import re
from typing import Annotated, Iterator, Literal, Optional

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints

from .ids import new_id
from .markup import plain

SCHEMA_VERSION = 6


def normalise_tag(value: str) -> str:
    """One spelling for a tag, wherever it was typed.

    Lowercased and stripped of a leading hash, because people type "#backend"
    in one box and "Backend" in another and mean the same thing. Anything that
    normalises to nothing is no tag at all.

    Lives here rather than in ``render.design`` -- where it was until the
    focus screen needed it -- because how a tag is spelled is a fact about the
    profile, and ``core`` must not import ``render``.
    """
    return value.strip().lstrip("#").strip().lower()

# --------------------------------------------------------------------------
# Shared field types
# --------------------------------------------------------------------------

DATE_PATTERN = r"^\d{4}(-(0[1-9]|1[0-2]))?$"


def _blank_to_none(value: object) -> object:
    """Treat an empty or whitespace-only string as a missing value.

    The editor produces "" for a field the user has not filled in yet, but the
    schema wants ``None``. Normalising here means a half-finished entry still
    saves cleanly instead of failing validation on an empty date box.
    """
    if isinstance(value, str) and not value.strip():
        return None
    return value


PartialDate = Annotated[str, StringConstraints(max_length=40)]
OptDate = Annotated[Optional[PartialDate], BeforeValidator(_blank_to_none)]
"""When something happened, at whatever precision anybody actually has.

Deliberately a string rather than ``datetime.date``:

  * Resumes work in months, not days -- a date object would force an invented
    day-of-month into the data.
  * JSON has no date type, so dates would need custom encoders on every save.
  * The file stays readable and hand-editable.

**Three precisions, on purpose.** "2025-06" and "2025" are the structured
forms, and ``format_date`` renders each at the precision it has -- coercing a
year to January would invent a month and then print it on the PDF as though
somebody had stated it.

The third is whatever the writer typed. Resumes say "Summer 2024", "Expected
2026", "Ongoing", "2019 - Present"; a field that refuses those is a field
that makes people misstate their own history to satisfy a regex. So anything
short is accepted and printed as written.

What that costs is real and worth naming. A structured date can be reformatted
-- the design's Feb 2025 / 02/2025 switch only reaches dates the app can
read -- and the regex used to catch "2025-13" before it reached paper. The
first is a fair trade: a date written in words is a date the writer has
already formatted. The second moved to the writing standard, which flags a
broken month as a finding instead of refusing the keystroke. Blocking the
field was the wrong place for that check: it stopped the typo and everything
legitimate along with it.
"""


def is_month(value: str | None) -> bool:
    """Whether a stored date is one the app can read, rather than words."""
    return bool(value) and re.fullmatch(DATE_PATTERN, value or "") is not None

EmploymentType = Literal[
    "Internship",
    "Placement",
    "Part-time",
    "Full-time",
    "Freelance",
    "Volunteer",
    "Research",
    "Other",
]


class DBModel(BaseModel):
    """Base class carrying the settings every profile model shares."""

    model_config = ConfigDict(
        # Reject unknown keys. A typo in a hand-edited profile.json, or a
        # hallucinated field from an AI import, becomes a clear error at load
        # time instead of data that silently vanishes on the next save.
        extra="forbid",
        str_strip_whitespace=True,
    )


# --------------------------------------------------------------------------
# Leaf models
# --------------------------------------------------------------------------


class TextBlock(DBModel):
    """A stretch of rewritable prose with a stable id.

    Used for both bullet points and the professional summary. They share one
    class on purpose: to the AI tailoring step in phase 3 they are the same
    kind of thing -- prose that can be rewritten, and that must stay traceable
    back to whatever it replaced.
    """

    id: str = Field(default_factory=lambda: new_id("blt"))
    text: str = ""
    tags: list[str] = Field(default_factory=list)
    """Which job families this line is for. Empty means "always".

    A fact about the material, not a styling choice, which is why it belongs
    here rather than in ``design.py``: "I did this, and it is the kind of
    thing a backend team cares about" is a property of the work. What the
    design layer decides is which tag to *print* for a given application --
    that is `Design.focus`, and it holds no tags of its own.

    Empty is deliberately the common case. A profile where every line has to
    be labelled before any of it prints is a profile nobody finishes tagging,
    so an untagged line is core material and appears whatever the focus.
    """


class Link(DBModel):
    id: str = Field(default_factory=lambda: new_id("lnk"))
    label: str = ""
    url: str = ""


class Basics(DBModel):
    name: str = ""
    headline: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    links: list[Link] = Field(default_factory=list)
    photo: str = ""
    """A file name inside ``data/``, not the image itself.

    Several templates place a portrait, so this is a fact about you and
    belongs in the profile rather than in the design. The *bytes* do not:
    profile.json is hand-editable, diffed, and copied into a backup on every
    save, and a base64 portrait would add a quarter of a megabyte of noise to
    all three. The file lives beside it and this points at it.

    Worth knowing before turning one on: a photo is conventional on a CV in
    much of Europe and Asia, and is discouraged in the US, UK and Canada,
    where many employers discard resumes carrying one to limit bias claims.
    """


class Experience(DBModel):
    id: str = Field(default_factory=lambda: new_id("exp"))
    role: str = ""
    organisation: str = ""
    location: str = ""
    employment_type: EmploymentType = "Internship"
    start: OptDate = None
    end: OptDate = None  # None means ongoing; templates render "Present"
    bullets: list[TextBlock] = Field(default_factory=list)


class Project(DBModel):
    id: str = Field(default_factory=lambda: new_id("prj"))
    name: str = ""
    tagline: str = ""
    tech: list[str] = Field(default_factory=list)
    url: str = ""
    start: OptDate = None
    end: OptDate = None
    bullets: list[TextBlock] = Field(default_factory=list)


class Education(DBModel):
    id: str = Field(default_factory=lambda: new_id("edu"))
    institution: str = ""
    credential: str = ""
    location: str = ""
    start: OptDate = None
    end: OptDate = None
    grade: str = ""
    coursework: list[str] = Field(default_factory=list)
    bullets: list[TextBlock] = Field(default_factory=list)


class SkillGroup(DBModel):
    """Skills are grouped, not flat.

    Templates render "Languages: Python, SQL" style lines, and the ATS check
    benefits from knowing which category a keyword sits in. A grouped list can
    always be flattened; a flat list cannot be un-flattened later.
    """

    id: str = Field(default_factory=lambda: new_id("skg"))
    label: str = ""
    items: list[str] = Field(default_factory=list)
    levels: dict[str, int] = Field(default_factory=dict)
    """``{item: 1..5}`` for the skills that have been rated. Optional.

    A side table rather than turning ``items`` into a list of objects, for two
    reasons. Every stored profile, every import and every AI parse already
    writes ``items`` as a list of strings, and changing its shape would make
    all of them a migration. And a level is genuinely optional in a way a name
    is not -- most people rate a handful of skills and leave the rest alone,
    and a rating nobody set should take up no room in the file and print
    nothing on the page.

    Keyed by the item's own text, so reordering a group keeps the ratings
    attached to the right skills; renaming one drops its rating, which is the
    honest outcome, since a renamed skill is a different claim.
    """

    tags: list[str] = Field(default_factory=list)
    """Same rule as a bullet's: empty means the group always prints."""


class Certification(DBModel):
    id: str = Field(default_factory=lambda: new_id("crt"))
    name: str = ""
    issuer: str = ""
    issued: OptDate = None
    url: str = ""


class Award(DBModel):
    """A recognition someone else conferred: a prize, a scholarship, a place
    on a dean's list. Displayed as "Honors"; the key stays ``awards`` because
    renaming a stored field to change a heading is a migration that buys
    nothing -- the label lives in the presentation layer, where labels go."""

    id: str = Field(default_factory=lambda: new_id("awd"))
    title: str = ""
    awarded_by: str = ""
    date: OptDate = None
    note: str = ""


class Achievement(DBModel):
    """Something you did, as against something you were given.

    Distinct from ``Award`` on purpose. "Dean's List" is conferred by an
    institution and belongs under Honors; "Ranked 3rd of 400 teams" is an
    outcome you produced, and reads as a boast in the wrong section and as
    evidence in the right one. Keeping them apart also keeps the two headings
    honest when only one has anything in it.
    """

    id: str = Field(default_factory=lambda: new_id("ach"))
    title: str = ""
    context: str = ""
    date: OptDate = None
    note: str = ""


class CustomSection(DBModel):
    """A section of the resume that none of the eight built-in ones is.

    Every other model here is a *kind* of thing the app understands -- a job,
    a degree, a prize -- and understanding it is what lets the app sort, date
    and lay it out. This one is the opposite: it is the section the app does
    not understand, kept anyway.

    It exists because the eight are a good description of most resumes and a
    complete description of none. A senior CV carries "Governance, Security
    and Risk Leadership"; a researcher carries "Selected Publications"; a
    consultant carries "Sector Coverage". Before this, an import read those,
    found no field to put them in, and dropped them -- silently, which is the
    worst way to lose something. The writer saw a shorter resume and no reason
    for it.

    So the deal is narrow and honest: the app keeps the heading and the words
    exactly as written, prints them in the order you choose, and claims
    nothing else. No dates to sort by, no organisation to match against a
    posting, no duplicate detection worth the name -- all of which are
    services the eight buy with their structure and this one does not.

    ``text`` and ``bullets`` are not alternatives and either may be empty. A
    prose paragraph, a list of lines, or a paragraph followed by a list are
    all things real resumes do under one heading, and refusing the third would
    mean splitting a section the writer wrote as one.
    """

    id: str = Field(default_factory=lambda: new_id("cus"))
    title: str = ""
    """The heading, in the writer's own words. Unlike every other section's,
    this one has no default to fall back on -- it is the only name it has."""

    text: str = ""
    bullets: list[TextBlock] = Field(default_factory=list)


# --------------------------------------------------------------------------
# The profile
# --------------------------------------------------------------------------


class Profile(DBModel):
    schema_version: int = SCHEMA_VERSION
    basics: Basics = Field(default_factory=Basics)
    summary: TextBlock = Field(default_factory=lambda: TextBlock(id="sum_main"))
    experience: list[Experience] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    skills: list[SkillGroup] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    awards: list[Award] = Field(default_factory=list)
    achievements: list[Achievement] = Field(default_factory=list)
    sections: list[CustomSection] = Field(default_factory=list)

    @classmethod
    def empty(cls) -> "Profile":
        """A valid, blank profile -- what a first run starts from."""
        return cls()

    def is_blank(self) -> bool:
        return not (
            self.basics.name
            or self.summary.text
            or self.experience
            or self.projects
            or self.education
            or self.skills
            or self.certifications
            or self.awards
            or self.achievements
            or self.sections
        )


# Section keys in their default resume order, with display labels. The template
# layer will let this order be overridden per resume; this is the fallback.
SECTION_ORDER: tuple[tuple[str, str], ...] = (
    ("summary", "Summary"),
    ("experience", "Experience"),
    ("projects", "Projects"),
    ("education", "Education"),
    ("skills", "Skills"),
    ("certifications", "Certifications"),
    ("awards", "Honors"),
    ("achievements", "Achievements"),
)

LIST_SECTIONS: tuple[str, ...] = (
    "experience",
    "projects",
    "education",
    "skills",
    "certifications",
    "awards",
    "achievements",
    # Last on purpose. Everything above is a kind of thing; this is the
    # catch-all, and code that walks the list -- id hygiene, the merge plan,
    # the "what is filled in" counts -- should reach the understood sections
    # before the ones held verbatim.
    "sections",
)

BULLET_SECTIONS: tuple[str, ...] = ("experience", "projects", "education")

ENTRY_MODELS: dict[str, type[DBModel]] = {}  # populated below


# --------------------------------------------------------------------------
# Traversal helpers
# --------------------------------------------------------------------------


def iter_bullets(profile: Profile) -> Iterator[tuple[str, str, TextBlock]]:
    """Yield ``(section_key, owner_id, block)`` for every rewritable block.

    One uniform walk over all the prose in a profile. The bullet field is named
    ``bullets`` in experience, projects and education specifically so that this
    function -- and therefore the tailoring prompt builder, the ATS text
    extractor and the quality linter -- needs no per-section special cases.
    """
    yield ("summary", "summary", profile.summary)
    for section in BULLET_SECTIONS:
        for entry in getattr(profile, section):
            for block in entry.bullets:
                yield (section, entry.id, block)
    # Custom sections are held verbatim, but their bullets are still prose the
    # writer wrote: the quality linter should read them, the tailor should be
    # able to rewrite them, and leaving them out would make a section quietly
    # exempt from the standard the rest of the resume is held to.
    for custom in profile.sections:
        for block in custom.bullets:
            yield ("sections", custom.id, block)


MONTH_NAMES = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)


def format_date(value: str | None, *, blank: str = "Present", style: str = "month") -> str:
    """Render a stored date for display, at the precision it actually has.

    "2025-06" becomes "Jun 2025", or "06/2025" with ``style="numeric"``.
    "2025" stays "2025" either way -- the whole point of allowing year-only
    dates is not to print a month nobody stated, and that holds in both
    formats. ``None`` becomes ``blank``, which is "Present" for an end date
    and should be passed as "" for a start date.

    Anything else is words, and words are printed exactly as they were typed.
    "Summer 2024" has no month to reformat and no reading to improve on; the
    writer already decided how that date should look.

    The style is a presentation choice and arrives from the design, never from
    the profile: the same stored date prints both ways depending on the resume
    it is going onto.
    """
    if not value:
        return blank
    if not is_month(value):
        return value
    if len(value) == 4:
        return value
    year, month = value.split("-")
    if style == "numeric":
        return f"{month}/{year}"
    return f"{MONTH_NAMES[int(month) - 1]} {year}"


def format_range(start: str | None, end: str | None, *, style: str = "month") -> str:
    """Render a date span, e.g. "Jun 2025 - Sep 2025" or "2024 - Present"."""
    if not start and not end:
        return ""
    # A start written in words with nothing after it is already the whole
    # span. Somebody who types "2019 - Present" into one box has said what
    # they mean, and appending our own "- Present" to it prints
    # "2019 - Present - Present". A structured start with no end still means
    # ongoing, which is what the empty End box has always meant.
    if not end and not is_month(start):
        return (start or "").strip()
    left = format_date(start, blank="", style=style)
    right = format_date(end, blank="Present", style=style)
    return f"{left} - {right}" if left else right


def entry_label(entry: object) -> str:
    """A short human label for an entry, for UI headings and logs.

    Always the words, never the markup. This is the one function every part of
    the app reaches for when it needs to *name* an entry -- the tailoring
    prompt, the posting matcher, the guard record in the database, the
    interview brief, the import review -- so stripping here is what keeps a
    bolded job title from arriving at a model as "<b>Founder</b> & CEO" or
    being written into a table as a label nobody can search for.
    """
    def words(*parts: str) -> str:
        return " - ".join(plain(p) for p in parts if p)

    if isinstance(entry, Experience):
        return words(entry.role, entry.organisation) or "Untitled role"
    if isinstance(entry, Project):
        return plain(entry.name) or "Untitled project"
    if isinstance(entry, Education):
        return words(entry.credential, entry.institution) or "Untitled study"
    if isinstance(entry, SkillGroup):
        return plain(entry.label) or "Untitled group"
    if isinstance(entry, Certification):
        return plain(entry.name) or "Untitled certification"
    if isinstance(entry, Award):
        return plain(entry.title) or "Untitled honor"
    if isinstance(entry, Achievement):
        return plain(entry.title) or "Untitled achievement"
    if isinstance(entry, CustomSection):
        return plain(entry.title) or "Untitled section"
    return "Entry"


def all_ids(profile: Profile) -> list[str]:
    """Every id in the document, in document order. Used to detect collisions."""
    ids: list[str] = [profile.summary.id]
    ids += [link.id for link in profile.basics.links]
    for section in LIST_SECTIONS:
        for entry in getattr(profile, section):
            ids.append(entry.id)
            ids += [b.id for b in getattr(entry, "bullets", [])]
    return ids


ENTRY_MODELS.update(
    {
        "experience": Experience,
        "projects": Project,
        "education": Education,
        "skills": SkillGroup,
        "certifications": Certification,
        "awards": Award,
        "achievements": Achievement,
        "sections": CustomSection,
    }
)
