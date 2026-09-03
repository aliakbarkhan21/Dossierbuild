"""Drafting one block of prose, on request, from facts the user supplies.

The difference between this and ``ai/tailor.py`` is what it is aimed at.
Tailoring re-angles an existing profile at one posting; this drafts a single
bullet or summary the user is sitting in front of, with no job in mind. What
they have in common is the rule that matters: **the model may only phrase
facts it was given.**

For a bullet that is stricter than it sounds, because the input is one line
the user typed -- "fixed printers and set up accounts for the office". A model
handed that will happily return "Resolved 200+ hardware tickets, cutting
downtime 35%", and every number in it is invented. So the same audit the
tailor uses runs here, with the user's own sentence as the source: anything
asserted that is neither in that sentence nor anywhere in their profile comes
back flagged, and the UI shows it before they can insert it.

The writing standard is not restated here. It is built from
``core/quality.FILLER_PHRASES``, the same list the Health screen lints
against, so a suggestion cannot be written to a standard the app then marks
down -- and every draft is run back through ``check_text`` before it is
returned, so the caller can see what the linter still thinks.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from ..core.quality import FILLER_PHRASES, build_vocabulary, check_text
from ..core.schema import Profile, iter_bullets
from .client import generate
from .tailor import _known_vocabulary, audit

# Long enough to have said something. Below this the model has nothing to work
# from and will fill the gap itself, which is the failure this module exists
# to avoid.
MIN_NOTE = 12


class Drafted(BaseModel):
    text: str = Field(description="The suggested line. No leading bullet character.")


@dataclass
class Draft:
    """A suggestion, already linted and audited."""

    text: str
    model: str
    invented: list[str] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)

    @property
    def is_safe(self) -> bool:
        return not self.invented


def _standard() -> str:
    banned = ", ".join(f'"{p}"' for p in FILLER_PHRASES[:18])
    return f"""\
You draft one line of a resume. You are a writer working from dictation, not
an author.

THE ABSOLUTE RULE: every fact in your output must be in the input you were
given. You may not add a number, a percentage, a team size, a duration, a
technology, an employer or an outcome that the person did not state. If they
gave you no metric, write the strongest honest line without one. A plausible
invented number is the worst thing you can produce here, because they will be
asked about it in an interview and will not be able to answer.

What a good line does:
1. Opens with a past-tense verb of result: Built, Cut, Shipped, Migrated,
   Automated, Rewrote, Resolved. Never an -ing verb, never "Responsible for".
2. Names the specific thing -- the tool, the system, the audience -- in the
   words the person used.
3. Says what changed, not what they were present for.
4. Runs to one line. Under 200 characters, and shorter is better.

Banned as filler, in any tense: {banned}.

Return exactly one line, with no bullet character and no trailing full stop.
"""


def _profile_facts(profile: Profile) -> str:
    """Everything the profile already asserts, as one block.

    Used as the audit's source when drafting a summary: a summary legitimately
    draws on any fact already in the document, so all of them count as given.
    """
    parts = [profile.basics.headline]
    parts += [block.text for _section, _owner, block in iter_bullets(profile)]
    for entry in profile.experience:
        parts += [entry.role, entry.organisation]
    for project in profile.projects:
        parts += [project.name, project.tagline, *project.tech]
    for education in profile.education:
        parts += [education.credential, education.institution, education.grade, *education.coursework]
    for group in profile.skills:
        parts += group.items
    return "\n".join(p for p in parts if p)


def _finish(
    text: str,
    profile: Profile,
    source: str,
    model: str,
    *,
    is_summary: bool,
) -> Draft:
    text = text.strip().lstrip("-•* ").strip()
    return Draft(
        text=text,
        model=model,
        invented=audit(source, text, known=_known_vocabulary(profile)),
        findings=[
            f.message
            for f in check_text(
                text, "draft", is_summary=is_summary, vocabulary=build_vocabulary(profile)
            )
        ],
    )


def suggest_bullet(
    profile: Profile,
    note: str,
    *,
    entry_label: str = "",
    model: str | None = None,
) -> Draft:
    """Turn a line of "here is what I did" into a resume bullet."""
    if len(note.strip()) < MIN_NOTE:
        raise ValueError(
            "Say a little more about what you did -- a sentence is enough. "
            "With less than that the model would be inventing the rest."
        )

    prompt = "\n".join(
        [
            f"THE ROLE: {entry_label}" if entry_label else "",
            "",
            "WHAT THEY DID, in their own words. This is the only source of",
            "facts you have. Do not add to it:",
            "---",
            note.strip(),
            "---",
            "",
            # Their own vocabulary, so the draft uses the spellings they use
            # rather than introducing a synonym that reads as a different tool.
            "Technologies this person has listed elsewhere, for spelling and",
            "capitalisation only -- do NOT introduce one that is not in the",
            f"sentence above: {', '.join(sorted(build_vocabulary(profile)))[:600]}",
            "",
            "Write the bullet.",
        ]
    )
    drafted, used = generate(
        prompt,
        system=_standard(),
        schema=Drafted,
        temperature=0.4,
        model=model,
        task="bullet suggestion",
    )
    return _finish(drafted.text, profile, note, used, is_summary=False)


def suggest_summary(profile: Profile, *, note: str = "", model: str | None = None) -> Draft:
    """Draft the professional summary from what the profile already says.

    No note is required: unlike a bullet, the summary has a whole profile to
    draw on, and asking someone to describe themselves before the app will
    describe them is the wrong way round.
    """
    facts = _profile_facts(profile)
    if not facts.strip():
        raise ValueError(
            "There is nothing to summarise yet. Add a role or a project with a "
            "bullet or two, then come back -- a summary is a précis of the "
            "profile, not a substitute for one."
        )

    prompt = "\n".join(
        [
            "Write this person's professional summary: three or four lines,",
            "in the first person implied (no 'I'), naming what they work on,",
            "what they have built, and what they are looking for.",
            "",
            "Everything you may use is below. Do not add to it.",
            "---",
            f"Name: {profile.basics.name}",
            f"Headline: {profile.basics.headline}",
            facts[:4000],
            "---",
            f"\nWhat they want emphasised: {note.strip()}" if note.strip() else "",
            "",
            "Three or four lines. Specific enough that nobody else could have",
            "written it about themselves.",
        ]
    )
    drafted, used = generate(
        prompt,
        system=_standard().replace(
            "Return exactly one line, with no bullet character and no trailing full stop.",
            "Return three or four sentences as a single paragraph.",
        ),
        schema=Drafted,
        temperature=0.4,
        model=model,
        task="summary suggestion",
    )
    # The note is part of the source: a person saying "emphasise the data work"
    # has told you they do data work.
    return _finish(drafted.text, profile, f"{facts}\n{note}", used, is_summary=True)
