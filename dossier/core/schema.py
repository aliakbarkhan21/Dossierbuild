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

from typing import Annotated, Iterator, Literal, Optional

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints

from .ids import new_id

SCHEMA_VERSION = 3

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


PartialDate = Annotated[str, StringConstraints(pattern=DATE_PATTERN)]
OptDate = Annotated[Optional[PartialDate], BeforeValidator(_blank_to_none)]
"""A date at whatever precision is actually known: "2025-06" or "2025".

Deliberately a validated string rather than ``datetime.date``:

  * Resumes work in months, not days -- a date object would force an invented
    day-of-month into the data.
  * JSON has no date type, so dates would need custom encoders on every save.
  * The file stays readable and hand-editable.

**Two precisions, on purpose.** Plenty of real sources only know the year --
LinkedIn stores education dates that way, and people write "2024" on a resume.
Coercing those to January would be inventing a fact, and the invented month
would then be printed on the PDF as though it were real. Storing "2025" keeps
the uncertainty visible, and ``format_date`` renders it honestly.

Both forms still sort correctly as plain strings, and the regex still catches
real typos such as "2025-13".
"""

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

    The style is a presentation choice and arrives from the design, never from
    the profile: the same stored date prints both ways depending on the resume
    it is going onto.
    """
    if not value:
        return blank
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
    left = format_date(start, blank="", style=style)
    right = format_date(end, blank="Present", style=style)
    return f"{left} - {right}" if left else right


def entry_label(entry: object) -> str:
    """A short human label for an entry, for UI headings and logs."""
    if isinstance(entry, Experience):
        return " - ".join(p for p in (entry.role, entry.organisation) if p) or "Untitled role"
    if isinstance(entry, Project):
        return entry.name or "Untitled project"
    if isinstance(entry, Education):
        return " - ".join(p for p in (entry.credential, entry.institution) if p) or "Untitled study"
    if isinstance(entry, SkillGroup):
        return entry.label or "Untitled group"
    if isinstance(entry, Certification):
        return entry.name or "Untitled certification"
    if isinstance(entry, Award):
        return entry.title or "Untitled honor"
    if isinstance(entry, Achievement):
        return entry.title or "Untitled achievement"
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
    }
)
