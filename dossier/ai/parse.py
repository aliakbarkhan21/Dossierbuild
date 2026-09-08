"""Turning resume text into structured profile data with Gemini.

This is the first place a model appears in Dossierbuild, and it is worth being
precise about what it is being asked to do: **transcribe and structure, never
compose.** Reading an old resume is a sorting job -- every fact is already on
the page. The model's task is to work out that "Northgate Labs" is an employer
and "Jun 2025 - Sep 2025" is that job's dates. It is explicitly told not to
improve the writing, because rewriting belongs to phase 3 where the result is
reviewed against a job description.

Two structural safeguards, not just prompt wording:

**Structured output.** The model is handed a JSON schema and constrained to it,
so it cannot return a shape the app fails to load. It is not being asked
politely for JSON and then parsed hopefully.

**The model never mints ids.** The schema it fills in has no id fields at all.
Ids are assigned here, afterwards, by the same generator the editor uses. A
model inventing identifiers would be a quiet source of collisions, and ids are
what phase 3's accept/revert depends on.
"""

from __future__ import annotations

from typing import get_args

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field

from ..core.schema import (
    Achievement,
    Award,
    Basics,
    Certification,
    CustomSection,
    Education,
    EmploymentType,
    Experience,
    Link,
    Profile,
    Project,
    SkillGroup,
    TextBlock,
)
from ..ingest.linkedin import parse_date
from .client import (
    API_KEY_VARS,
    DEFAULT_MODEL,
    MissingAPIKey,
    api_key_present,
    generate,
)

# Re-exported because the API layer and the import self-checks have always
# imported them from here, and moving the machinery is not a reason to move
# everyone's import line.
__all__ = [
    "API_KEY_VARS",
    "DEFAULT_MODEL",
    "MissingAPIKey",
    "ParseResult",
    "RawResume",
    "api_key_present",
    "parse_resume_text",
    "remember_api_key",
    "to_profile",
    "use_api_key",
    "verify_api_key",
]

# --------------------------------------------------------------------------
# The shape the model fills in
# --------------------------------------------------------------------------
#
# Deliberately a separate, flatter set of models from dossier.core.schema:
#   * no id fields, so ids stay ours to assign
#   * plain strings everywhere, with "" for missing -- structured-output
#     handles a required string far more reliably than a nullable union
#   * bullets as list[str], since the model has no reason to see TextBlock


class RawExperience(BaseModel):
    role: str = ""
    organisation: str = ""
    location: str = ""
    employment_type: str = Field(
        default="",
        description="One of: Internship, Placement, Part-time, Full-time, Freelance, Volunteer, Research",
    )
    start: str = Field(default="", description='"YYYY-MM", or "YYYY" if only a year is stated, or "" if absent')
    end: str = Field(default="", description='"YYYY-MM" or "YYYY"; "" if ongoing or not stated')
    bullets: list[str] = Field(default_factory=list)


class RawProject(BaseModel):
    name: str = ""
    tagline: str = ""
    tech: list[str] = Field(default_factory=list)
    url: str = ""
    start: str = ""
    end: str = ""
    bullets: list[str] = Field(default_factory=list)


class RawEducation(BaseModel):
    institution: str = ""
    credential: str = Field(default="", description="Degree and field, e.g. BSc Computer Science")
    location: str = ""
    start: str = ""
    end: str = ""
    grade: str = ""
    coursework: list[str] = Field(default_factory=list)
    bullets: list[str] = Field(default_factory=list)


class RawSkillGroup(BaseModel):
    label: str = Field(default="", description="Category heading, e.g. Languages")
    items: list[str] = Field(default_factory=list)


class RawCertification(BaseModel):
    name: str = ""
    issuer: str = ""
    issued: str = ""
    url: str = ""


class RawAward(BaseModel):
    title: str = ""
    awarded_by: str = ""
    date: str = ""
    note: str = ""


class RawAchievement(BaseModel):
    title: str = ""
    context: str = ""
    date: str = ""
    note: str = ""


class RawLink(BaseModel):
    label: str = ""
    url: str = ""


class RawSection(BaseModel):
    """A section of the resume that fits none of the eight the app knows.

    Deliberately the last thing the schema offers and the last rule in the
    prompt. A model handed a free-form escape hatch will use it -- experience
    under an unusual heading would land here rather than in `experience`,
    where the dates, the employer and the duplicate check all live. So the
    rule that governs it is a rule about *not* using it.
    """

    title: str = Field(default="", description="The heading, exactly as written")
    text: str = Field(default="", description="Any prose under it, verbatim")
    bullets: list[str] = Field(default_factory=list)


class RawHeadings(BaseModel):
    """The resume's own wording for each section it has.

    Asked for separately from the content so the writer's headings survive the
    import. A CV that says CORE EXPERTISE should not come back saying
    "Skills": the app knows where the facts belong, and the writer knows what
    to call them.
    """

    summary: str = ""
    experience: str = ""
    projects: str = ""
    education: str = ""
    skills: str = ""
    certifications: str = ""
    awards: str = ""
    achievements: str = ""


class RawResume(BaseModel):
    """Everything a resume can contain, as the model returns it."""

    headings: RawHeadings = Field(default_factory=RawHeadings)

    name: str = ""
    headline: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    links: list[RawLink] = Field(default_factory=list)
    summary: str = ""
    experience: list[RawExperience] = Field(default_factory=list)
    projects: list[RawProject] = Field(default_factory=list)
    education: list[RawEducation] = Field(default_factory=list)
    skills: list[RawSkillGroup] = Field(default_factory=list)
    certifications: list[RawCertification] = Field(default_factory=list)
    awards: list[RawAward] = Field(default_factory=list)
    achievements: list[RawAchievement] = Field(default_factory=list)
    sections: list[RawSection] = Field(default_factory=list)


SYSTEM_INSTRUCTION = """\
You extract structured data from a resume. You are a transcriber, not a writer.

Rules, in order of importance:

1. Copy facts as written. Never invent an employer, date, grade, metric,
   technology or achievement that is not in the text. If a field is not stated,
   leave it as an empty string. An empty field is correct; a plausible guess is
   a fabrication.
2. Do not rewrite, improve, shorten or expand bullet points. Reproduce each one
   close to verbatim, with only obvious extraction artefacts cleaned up:
   hyphenation split across lines, a stray leading bullet character, a line
   break in the middle of a sentence, and -- most commonly -- a space the PDF
   extractor inserted inside a word. Text pulled out of a PDF routinely
   arrives broken that way: "Conc urrently" is "Concurrently", "large- scale"
   is "large-scale", "decision- making" is "decision-making". Join them back
   into the word that was written. This is not rewriting: those spaces are
   not in the resume, they are in the extraction of it.
3. Dates become "YYYY-MM". "Jun 2025" is "2025-06". If the resume states only
   a year, return just the year ("2024") -- do not invent a month for it.
   "Present", "Current" and "Ongoing" mean the end date is an empty string.
4. Split each role's description into its individual bullet points. One bullet
   per achievement, as the resume laid them out.
5. Sort skills into the category headings the resume itself uses, and keep
   the resume's own wording for the group label. A great many resumes never
   use the word "skills" for this section: "Core Expertise", "Core
   Competencies", "Areas of Expertise", "Technical Skills", "Key Skills",
   "Capabilities", "Competencies", "Technologies", "Tools" and "Specialisms"
   all mean the same thing and all belong in `skills`. So does a list of
   capabilities separated by pipes, commas, bullets or slashes under any
   heading of that kind -- split it on the separator, one item each. If a
   resume lists skills with no heading at all, use one group labelled
   "Skills". Losing this section entirely is a common and serious failure:
   for a senior candidate it is often the densest part of the document.
6. A project belongs in projects, not experience, even if it is described in
   detail. Coursework and modules belong to the education entry.
7. If the text is garbled or interleaved (common with two-column PDFs), extract
   what is unambiguous and leave the rest empty rather than guessing at it.
8. Honors (`awards`) are conferred by someone else: prizes, scholarships,
   dean's list, "Employee of the Month". Achievements are outcomes the person
   produced: a ranking, a competition placing, a record, a published result.
   If a line does not clearly say which it is, put it in `awards` -- that is
   where a reader will look first, and moving one entry is easier than
   noticing it went missing.
9. Fill in `headings` with the resume's own wording for each section you
   found, exactly as written but in normal capitals: "CORE EXPERTISE" is
   "Core Expertise", "EXECUTIVE PROFILE" is "Executive Profile". Leave a
   heading empty if the resume has no section of that kind, or if it uses the
   ordinary word for it. These are what the rebuilt resume will print, so a
   writer who called it "Areas of Expertise" gets that back rather than being
   told it is "Skills". Match the section by what it contains, not by its
   name: a heading you have never seen before still belongs to whichever of
   the eight its content fits.
10. Only when a heading's content fits none of the eight, put it in
    `sections` with its heading and its words as written. This is a last
    resort and most resumes need none: check every one of the eight first,
    and remember that a heading naming a skill area is `skills`, a heading
    listing employers is `experience`, and a heading listing prizes is
    `awards` -- however it is worded. Use `sections` for a genuinely
    different kind of content: "Selected Publications", "Board and Advisory
    Roles", "Sector Coverage", "Languages Spoken", "Speaking Engagements",
    "Patents", "References". Put prose in `text` and a bulleted list in
    `bullets`; a section with both keeps both. Never put a section here as
    well as in one of the eight -- that prints the same facts twice on the
    page.
"""


@dataclass
class ParseResult:
    profile: Profile
    model: str
    raw: RawResume

    @property
    def headings(self) -> dict[str, str]:
        """The writer's own section names, for the design to adopt.

        One heading, one section: the first to claim a heading keeps it. See
        ``covered`` for what happens to the others.
        """
        return self._split()[0]

    @property
    def covered(self) -> dict[str, str]:
        """``{section: the section whose heading already covers it}``.

        Resumes routinely run two of ours together -- "Education and
        Certifications" is one heading over two things the app keeps apart.
        The first fix here was to let the first section claim the heading and
        the rest fall back to their defaults, which printed

            CERTIFICATIONS
            ...
            EDUCATION AND CERTIFICATIONS

        and reads as a mistake, because it is one: the word appears twice and
        the writer wrote it once. What the CV actually says is that these are
        one section, so the second prints with no heading of its own and the
        import sets it directly beneath the first. One heading over both,
        which is the page the writer already has.
        """
        return self._split()[1]

    def _split(self) -> tuple[dict[str, str], dict[str, str]]:
        claimed: dict[str, str] = {}
        headings: dict[str, str] = {}
        covered: dict[str, str] = {}
        for key, value in self.raw.headings.model_dump().items():
            text = " ".join(str(value).split())
            if not text:
                continue
            winner = claimed.get(text.casefold())
            if winner is None:
                claimed[text.casefold()] = key
                headings[key] = text
            else:
                covered[key] = winner
        return headings, covered


def parse_resume_text(
    text: str,
    *,
    model: str | None = None,
    on_attempt: Callable[[str, str], None] | None = None,
) -> ParseResult:
    """Send resume text to Gemini and get a candidate profile back.

    ``ParseResult.model`` reports which model answered, and the review screen
    prints it -- so a fallback is visible rather than silent.
    """
    if not text.strip():
        raise ValueError("There is no text to parse.")

    raw, model_used = generate(
        f"Extract this resume.\n\n---\n{text}\n---",
        system=SYSTEM_INSTRUCTION,
        schema=RawResume,
        # Low but not zero. Extraction wants the most likely reading of an
        # ambiguous line, not creative variety.
        temperature=0.1,
        model=model,
        on_attempt=on_attempt,
        task="resume parse",
    )
    return ParseResult(profile=to_profile(raw), model=model_used, raw=raw)


# --------------------------------------------------------------------------
# Raw -> schema
# --------------------------------------------------------------------------

#: The schema's own spellings, keyed by their lowercase form. Derived from
#: ``EmploymentType`` rather than retyped, so a value added to the schema
#: cannot go missing here -- which is the bug this replaced.
def _key(value: str) -> str:
    """One spelling for a kind of employment, however it was written.

    "Full-time", "Full Time", "full  time" and "FULL-TIME" are one answer, and
    a resume will use all four. Spaces and underscores collapse to the hyphen
    the schema uses.
    """
    return "-".join(value.strip().lower().replace("_", " ").replace("-", " ").split())


EMPLOYMENT = {_key(value): value for value in get_args(EmploymentType)}


def _date(value: str) -> str | None:
    """Normalise whatever the model produced into a valid date, or None.

    The model is asked for "YYYY-MM" (or "YYYY" when only a year is stated) and
    usually complies, but its output goes through the same parser used for
    LinkedIn dates anyway. A date the schema would reject becomes None rather
    than blocking the whole import.
    """
    value = (value or "").strip()
    if not value:
        return None
    # What the model produced, normalised if it is a date and kept verbatim if
    # it is words. This used to return None for anything unparseable, so a CV
    # reading "Summer 2024" imported with no date at all -- the one outcome
    # worse than an odd-looking one, because nothing on screen said a fact had
    # been dropped.
    return parse_date(value) or value[:40]


def _blocks(lines: list[str]) -> list[TextBlock]:
    """Wrap plain strings in TextBlocks, minting ids here rather than there."""
    return [TextBlock(text=line.strip()) for line in lines if line and line.strip()]


def _employment(value: str) -> str:
    """Whatever the model called it, in the spelling the schema accepts.

    This used to be ``value.title()``, which capitalises after *every*
    non-letter -- so "full-time" became "Full-Time" and the schema, which
    spells it "Full-time", rejected it. The two hyphenated values are the two
    most common kinds of employment there are, and an import naming either one
    failed on a raw Pydantic error. Nothing else in the set has a hyphen,
    which is why it stayed hidden.

    Matching against the schema's own values fixes the class of bug rather
    than the instance: there is now no second list to keep in step.
    """
    return EMPLOYMENT.get(_key(value), "Other")


def to_profile(raw: RawResume) -> Profile:
    """Convert the model's answer into a real, validated Profile."""
    profile = Profile.empty()

    profile.basics = Basics(
        name=raw.name,
        headline=raw.headline,
        email=raw.email,
        phone=raw.phone,
        location=raw.location,
        links=[Link(label=l.label, url=l.url) for l in raw.links if l.url or l.label],
    )
    profile.summary = TextBlock(id="sum_main", text=raw.summary)

    profile.experience = [
        Experience(
            role=e.role,
            organisation=e.organisation,
            location=e.location,
            employment_type=_employment(e.employment_type),
            start=_date(e.start),
            end=_date(e.end),
            bullets=_blocks(e.bullets),
        )
        for e in raw.experience
        if e.role or e.organisation
    ]

    profile.projects = [
        Project(
            name=p.name,
            tagline=p.tagline,
            tech=[t for t in p.tech if t.strip()],
            url=p.url,
            start=_date(p.start),
            end=_date(p.end),
            bullets=_blocks(p.bullets),
        )
        for p in raw.projects
        if p.name
    ]

    profile.education = [
        Education(
            institution=e.institution,
            credential=e.credential,
            location=e.location,
            start=_date(e.start),
            end=_date(e.end),
            grade=e.grade,
            coursework=[c for c in e.coursework if c.strip()],
            bullets=_blocks(e.bullets),
        )
        for e in raw.education
        if e.institution or e.credential
    ]

    profile.skills = [
        SkillGroup(label=s.label or "Skills", items=[i for i in s.items if i.strip()])
        for s in raw.skills
        if any(i.strip() for i in s.items)
    ]

    profile.certifications = [
        Certification(name=c.name, issuer=c.issuer, issued=_date(c.issued), url=c.url)
        for c in raw.certifications
        if c.name
    ]

    profile.awards = [
        Award(title=a.title, awarded_by=a.awarded_by, date=_date(a.date), note=a.note)
        for a in raw.awards
        if a.title
    ]

    profile.achievements = [
        Achievement(title=a.title, context=a.context, date=_date(a.date), note=a.note)
        for a in raw.achievements
        if a.title
    ]

    # A heading with nothing under it is a heading the extractor mis-read, not
    # a section: kept, it would print an empty band on the page.
    profile.sections = [
        CustomSection(title=s.title.strip(), text=s.text.strip(), bullets=_blocks(s.bullets))
        for s in raw.sections
        if s.title.strip() and (s.text.strip() or any(b.strip() for b in s.bullets))
    ]

    return profile


# --------------------------------------------------------------------------
# Supplying the key
# --------------------------------------------------------------------------
#
# The key can arrive two ways: from the environment (a shell variable, or the
# .env this project loads at startup), or typed into the app. Typing it sets
# the process environment, which is all client() reads -- so a key entered
# mid-session works immediately, with no restart.


# Overridable so a test -- or a second copy of the app pointed at its own data
# directory -- cannot write over the key belonging to the real one. It defaults
# to the project's own .env, which is where it has always been.
ENV_PATH = Path(os.environ.get("DOSSIER_ENV_FILE") or Path(__file__).resolve().parents[2] / ".env")


def use_api_key(key: str) -> None:
    """Make ``key`` the key for the rest of this process."""
    os.environ["GEMINI_API_KEY"] = key.strip()


def verify_api_key(key: str) -> str | None:
    """Return None if the key works, otherwise a message saying why not.

    A key is checked before it is stored rather than after: a typo saved to
    .env would come back as a failure on every later parse, at which point the
    cause is much less obvious.
    """
    try:
        from google import genai
    except ImportError:  # pragma: no cover
        return "google-genai is not installed. Run: pip install google-genai"
    try:
        client = genai.Client(api_key=key.strip())
        next(iter(client.models.list()), None)
    except Exception as exc:  # noqa: BLE001 -- surfaced to the user
        # `str()` on the SDK's error is the whole JSON body -- status, code,
        # a @type URL and a metadata dict -- which is a wall of punctuation to
        # someone who has just mistyped a key. `.message` is the one sentence
        # Google wrote for a person, so prefer it and fall back to the first
        # line only when there is nothing better.
        detail = str(getattr(exc, "message", "") or "").strip()
        if not detail:
            detail = str(exc).strip().splitlines()[0]
        return f"That key was refused: {detail[:200]}"
    return None


def remember_api_key(key: str, path: Path | None = None) -> Path:
    """Write the key into .env so the next launch picks it up.

    .env is in .gitignore, which is the point: the key lives beside the
    project without ever being a candidate for a commit. An existing
    GEMINI_API_KEY line is replaced rather than appended to, so repeated saves
    do not stack up.
    """
    target = path or ENV_PATH
    header = "# Written by Dossierbuild. This file is gitignored -- keep it that way."
    lines = [f"GEMINI_API_KEY={key.strip()}"]
    if target.exists():
        kept = [
            ln
            for ln in target.read_text(encoding="utf-8").splitlines()
            if not ln.strip().startswith("GEMINI_API_KEY=")
        ]
        while kept and not kept[-1].strip():
            kept.pop()
        lines = [*kept, *lines]
    else:
        lines = [header, *lines]
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target
