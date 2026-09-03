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

import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field

from ..schema import (
    Award,
    Basics,
    Certification,
    Education,
    Experience,
    Link,
    Profile,
    Project,
    SkillGroup,
    TextBlock,
)
from .linkedin import parse_date

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")

# Tried in order when the chosen model is unreachable. Two things this guards
# against, both of which have already happened here: Google retires a model for
# new keys (gemini-2.5-flash returned 404 NOT_FOUND, "no longer available to
# new users"), and a current model is temporarily saturated (gemini-3.6-flash
# returned 503 UNAVAILABLE, "experiencing high demand"). Neither is worth
# failing an import over when a sibling model does the same job -- this is
# structured extraction, not a task where the exact model matters.
FALLBACK_MODELS = (
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    # The lite tier is last but genuinely useful: it carries far less traffic,
    # so it answers when the flash models are saturated, and transcription into
    # a fixed schema is well within what it can do.
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
)

# Error text that means "try again" rather than "stop". 503 and 429 are
# congestion and 504 is a slow response -- all temporary, all worth another
# pass. 404 means the model is gone for this key, so only the *other* models
# are worth trying.
RETRYABLE = (
    "404", "NOT_FOUND",
    "503", "UNAVAILABLE",
    "429", "RESOURCE_EXHAUSTED",
    "504", "DEADLINE_EXCEEDED",
)

# One pass over the models takes seconds when they are all busy, which is not
# a real attempt at all. Keep circling back until this budget is spent.
RETRY_BUDGET_SECONDS = 75

# A stalled request should fail visibly rather than spin. Measured: a healthy
# call is under 10 seconds with thinking held down.
REQUEST_TIMEOUT_MS = 45_000

API_KEY_VARS = ("GEMINI_API_KEY", "GOOGLE_API_KEY")


class MissingAPIKey(RuntimeError):
    pass


# --------------------------------------------------------------------------
# The shape the model fills in
# --------------------------------------------------------------------------
#
# Deliberately a separate, flatter set of models from dossierbuild.schema:
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


class RawLink(BaseModel):
    label: str = ""
    url: str = ""


class RawResume(BaseModel):
    """Everything a resume can contain, as the model returns it."""

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
   break in the middle of a sentence.
3. Dates become "YYYY-MM". "Jun 2025" is "2025-06". If the resume states only
   a year, return just the year ("2024") -- do not invent a month for it.
   "Present", "Current" and "Ongoing" mean the end date is an empty string.
4. Split each role's description into its individual bullet points. One bullet
   per achievement, as the resume laid them out.
5. Sort skills into the category headings the resume itself uses. If it lists
   skills without headings, use one group labelled "Skills".
6. A project belongs in projects, not experience, even if it is described in
   detail. Coursework and modules belong to the education entry.
7. If the text is garbled or interleaved (common with two-column PDFs), extract
   what is unambiguous and leave the rest empty rather than guessing at it.
"""


@dataclass
class ParseResult:
    profile: Profile
    model: str
    raw: RawResume


def _client():
    try:
        from google import genai
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("google-genai is not installed. Run: pip install google-genai") from exc

    key = next((os.environ[v] for v in API_KEY_VARS if os.environ.get(v)), None)
    if not key:
        raise MissingAPIKey(
            "No Gemini API key found. Paste one into the Import page "
            "(get one free at aistudio.google.com/apikey), or set "
            "GEMINI_API_KEY in .env."
        )
    from google.genai import types

    return genai.Client(
        api_key=key,
        http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS),
    )


def _candidates(model: str | None) -> list[str]:
    """The model to try, then the fallbacks, without repeats.

    An explicitly requested model still gets the fallbacks behind it: the
    caller is expressing a preference, not a requirement that the import fail
    because that one model happens to be down.
    """
    ordered = [model or DEFAULT_MODEL, *FALLBACK_MODELS]
    unique: list[str] = []
    for name in ordered:
        if name not in unique:
            unique.append(name)
    return unique


def _short(message: str) -> str:
    """The first meaningful line of an API error, for a status line."""
    first = message.strip().splitlines()[0]
    for token in ("UNAVAILABLE", "RESOURCE_EXHAUSTED", "DEADLINE_EXCEEDED", "NOT_FOUND"):
        if token in first:
            return token.replace("_", " ").lower()
    return first[:60]


def parse_resume_text(
    text: str,
    *,
    model: str | None = None,
    on_attempt: Callable[[str, str], None] | None = None,
) -> ParseResult:
    """Send resume text to Gemini and get a candidate profile back.

    Circles the model list until one answers or the retry budget runs out.
    A single pass is not a real attempt: when the flash tier is busy every
    model returns 503 within a second or two, and giving up there reports
    failure after three seconds of not really trying. Waiting between passes
    is what actually gets the import through a congested minute.

    ``on_attempt(model, state)`` is called as each request starts and finishes,
    so the caller can show progress instead of an opaque spinner.
    ``ParseResult.model`` reports which model answered, and the review screen
    prints it -- so a fallback is visible rather than silent.
    """
    from google.genai import types

    if not text.strip():
        raise ValueError("There is no text to parse.")

    client = _client()
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=RawResume,
        # Low but not zero. Extraction wants the most likely reading of an
        # ambiguous line, not creative variety.
        temperature=0.1,
        # Transcription needs no deliberation, and the default budget doubles
        # the wait: measured at 19s against 8.8s on the same input, with the
        # long version sometimes exceeding the request deadline outright.
        thinking_config=types.ThinkingConfig(thinking_level="LOW"),
    )
    prompt = f"Extract this resume.\n\n---\n{text}\n---"

    candidates = _candidates(model)
    failures: dict[str, str] = {}
    last_error: Exception | None = None
    deadline = time.monotonic() + RETRY_BUDGET_SECONDS
    round_number = 0

    while True:
        round_number += 1
        for name in candidates:
            if on_attempt:
                on_attempt(name, "trying")
            try:
                response = client.models.generate_content(
                    model=name, contents=prompt, config=config
                )
            except Exception as exc:  # noqa: BLE001 -- inspected, then re-raised
                message = str(exc)
                if not any(token in message for token in RETRYABLE):
                    raise
                failures[name] = _short(message)
                last_error = exc
                if on_attempt:
                    on_attempt(name, failures[name])
                continue

            raw = response.parsed
            if raw is None:
                raise RuntimeError(
                    "The model returned nothing usable. This usually means the text was "
                    "too short or was blocked; try pasting the text in manually."
                )
            return ParseResult(profile=to_profile(raw), model=name, raw=raw)

        # A model that is gone for this key will not come back this minute.
        candidates = [n for n in candidates if failures.get(n) != "not found"]
        remaining = deadline - time.monotonic()
        if not candidates or remaining <= 0:
            break
        pause = min(round_number * 3, int(remaining) or 1, 10)
        if on_attempt:
            on_attempt("", f"all busy -- waiting {pause}s before another pass")
        time.sleep(pause)

    tried = "; ".join(f"{name} ({reason})" for name, reason in failures.items())
    raise RuntimeError(
        f"Gemini is not answering right now. Tried {tried} over "
        f"{RETRY_BUDGET_SECONDS} seconds. This is congestion on Google's side, "
        "not your key or your file -- wait a minute and press Parse again, or "
        "set GEMINI_MODEL in .env to pin a quieter model."
    ) from last_error


# --------------------------------------------------------------------------
# Raw -> schema
# --------------------------------------------------------------------------

VALID_EMPLOYMENT = {
    "internship", "placement", "part-time", "full-time",
    "freelance", "volunteer", "research",
}


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
    return parse_date(value)


def _blocks(lines: list[str]) -> list[TextBlock]:
    """Wrap plain strings in TextBlocks, minting ids here rather than there."""
    return [TextBlock(text=line.strip()) for line in lines if line and line.strip()]


def _employment(value: str) -> str:
    return value.strip().title() if value.strip().lower() in VALID_EMPLOYMENT else "Other"


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

    return profile


def api_key_present() -> bool:
    return any(os.environ.get(v) for v in API_KEY_VARS)


# --------------------------------------------------------------------------
# Supplying the key
# --------------------------------------------------------------------------
#
# The key can arrive two ways: from the environment (a shell variable, or the
# .env this project loads at startup), or typed into the app. Typing it sets
# the process environment, which is all _client() reads -- so a key entered
# mid-session works immediately, with no restart.


ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


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
    except Exception as exc:  # noqa: BLE001 -- surfaced to the user verbatim
        detail = str(exc).strip().splitlines()[0][:200]
        return f"That key was refused: {detail}"
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
