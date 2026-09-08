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
from ..core.markup import plain
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
   Automated, Rewrote, Resolved, Instrumented. Never an -ing verb, never
   "Responsible for".
2. Names the specific thing -- the tool, the system, the audience -- in the
   words the person used.
3. Carries a mechanism: not only *what* was built but *what it was built with*
   and *what it acts on*. "Built a savings tracker" is a label. "Built a
   savings tracker in Python that parses bank statements into monthly
   categories" is a bullet. This is where the length comes from.
4. Says what changed, not what they were present for.
5. One line. Under 200 characters.

Precision is not the same as grandeur. A stronger line names a real component,
a real format, a real audience; it does not reach for a bigger adjective.
These are banned in any tense, and so is anything with their flavour:
{banned}. If a word could appear on any resume in the world, it is the wrong
word.

Return exactly one line, with no bullet character and no trailing full stop.
"""


def _profile_facts(profile: Profile) -> str:
    """Everything the profile already asserts, as one block.

    Used as the audit's source when drafting a summary: a summary legitimately
    draws on any fact already in the document, so all of them count as given.
    """
    parts = [plain(profile.basics.headline)]
    parts += [plain(block.text) for _section, _owner, block in iter_bullets(profile)]
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


def _entry_facts(profile: Profile, section: str, entry_id: str) -> tuple[str, str]:
    """``(label, facts)`` for the entry a bullet is being written for.

    This is what stops a suggestion being a paraphrase. Given only the user's
    sentence, the model can reword it and nothing more -- "I created a savings
    tracker with an AI chatbot" comes back as "Built a savings tracker
    featuring an AI chatbot", which is the same line in a different suit.

    The entry already holds real material: the stack the project was built
    with, the organisation the role was at, the modules a course covered. Those
    are the user's own facts, so using them is elaboration rather than
    invention -- and the audit already permits them, because
    ``_known_vocabulary`` draws from exactly the same places.
    """
    for entry in getattr(profile, section, None) or []:
        if entry.id != entry_id:
            continue

        lines: list[str] = []
        if section == "projects":
            lines.append(f"Project: {entry.name}")
            if entry.tagline:
                lines.append(f"What it is: {entry.tagline}")
            if entry.tech:
                lines.append(f"Built with: {', '.join(entry.tech)}")
            label = entry.name
        elif section == "education":
            lines.append(f"Course: {entry.credential} at {entry.institution}")
            if entry.coursework:
                lines.append(f"Modules: {', '.join(entry.coursework)}")
            label = f"{entry.credential} — {entry.institution}"
        else:
            lines.append(f"Role: {entry.role} at {entry.organisation}")
            if getattr(entry, "employment_type", ""):
                lines.append(f"Type: {entry.employment_type}")
            label = f"{entry.role} — {entry.organisation}"

        written = [plain(b.text) for b in entry.bullets if b.text.strip()]
        if written:
            lines.append("")
            lines.append("Bullets already written here. Do not repeat one:")
            lines += [f"- {t}" for t in written]

        return label, "\n".join(lines)

    return "", ""


def suggest_bullet(
    profile: Profile,
    note: str,
    *,
    entry_label: str = "",
    section: str = "",
    entry_id: str = "",
    model: str | None = None,
) -> Draft:
    """Turn a line of "here is what I did" into a resume bullet."""
    if len(note.strip()) < MIN_NOTE:
        raise ValueError(
            "Say a little more about what you did -- a sentence is enough. "
            "With less than that the model would be inventing the rest."
        )

    label, facts = _entry_facts(profile, section, entry_id)
    words = len(note.split())
    # A resume bullet earns its line by being more precise than the sentence
    # someone would say out loud, not by being the same sentence with better
    # verbs. Asking for a target length is blunt, but it is the instruction
    # the model actually follows -- "be more detailed" is not.
    target = f"{words + 8} to {words + 14}"

    prompt = "\n".join(
        part
        for part in [
            f"THE ENTRY THIS BULLET BELONGS TO:\n{facts}" if facts else "",
            f"THE ROLE: {entry_label or label}" if (entry_label or label) else "",
            "",
            "WHAT THEY DID, in their own words:",
            "---",
            note.strip(),
            "---",
            "",
            f"Their sentence is {words} words. Write about {target} words.",
            "",
            "You get the extra length from the entry above, not from",
            "imagination. Name the tools it was built with, what it acted on,",
            "and what it produced -- all of which are stated there. If the",
            "entry names a stack, say which parts of it did this. Do NOT add a",
            "number, a percentage, a duration or an outcome that appears",
            "nowhere above; if there is no metric, the line simply has none.",
            "",
            # Their own vocabulary, so the draft uses the spellings they use
            # rather than a synonym that reads as a different tool.
            "Spellings to match, where the entry uses them: "
            f"{', '.join(sorted(build_vocabulary(profile)))[:400]}",
            "",
            "Write the bullet.",
        ]
        if part != ""
    )
    drafted, used = generate(
        prompt,
        system=_standard(),
        schema=Drafted,
        temperature=0.4,
        model=model,
        task="bullet suggestion",
    )
    # The entry's own facts count as given: they are already in the profile,
    # which is what the audit checks against.
    return _finish(drafted.text, profile, f"{note}\n{facts}", used, is_summary=False)


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
            f"Name: {plain(profile.basics.name)}",
            f"Headline: {plain(profile.basics.headline)}",
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
