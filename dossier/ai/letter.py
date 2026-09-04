"""A cover letter, drafted from the profile and the posting's own words.

The rule from `tailor.py` carries over unchanged and matters more here, not
less. A resume bullet is read as a claim about one job; a cover letter is read
as a claim about *you*, in the first person, and "I have five years building
Kubernetes operators" written by a model on behalf of someone who has never
run one is the single most expensive sentence this app could produce. So the
same audit runs: every number and every named thing in the draft is diffed
against the profile, and anything the profile does not evidence comes back
flagged before the letter can be printed.

**The posting is a brief, not a source of facts.** `core/jobspec.py` has
already read it by rules, so the model is told which requirements the profile
answers and which it does not, and is instructed to write about the first and
stay off the second. That is also what keeps the audit honest: the posting's
vocabulary is deliberately *not* added to the known list, so a letter that
picks up "Kubernetes" from the advert is flagged rather than waved through.

**The parts a model has no business choosing are not asked of it.** The
greeting, the sign-off and the date are computed here. There is no judgement
in "Dear Hiring Manager," and a model that occasionally returns "Dear Sir or
Madam" or a hallucinated recipient is a liability for no gain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from pydantic import BaseModel, Field

from ..core.jobspec import MatchReport
from ..core.quality import FILLER_PHRASES
from ..core.schema import Profile
from .client import generate
from .tailor import _known_vocabulary, audit

# Fewer words than this and the model has been given nothing to work from --
# no bullets, no skills -- and will write about enthusiasm instead.
MIN_FACTS = 40

# What a letter may run to before it stops being read. Three hundred words is
# roughly half a page at 10.5pt, which is where a hiring manager's attention
# actually ends.
MAX_WORDS = 300


class LetterDraft(BaseModel):
    paragraphs: list[str] = Field(
        description=(
            "Three or four paragraphs of the letter body. No greeting, no "
            "sign-off, no name -- those are added afterwards. Plain sentences, "
            "no bullet characters, no markdown."
        )
    )


@dataclass
class Letter:
    """A drafted letter, already audited against the profile."""

    greeting: str
    paragraphs: list[str]
    closing: str
    signature: str
    model: str = ""
    invented: list[str] = field(default_factory=list)
    """Numbers and names the letter asserts that the profile does not."""

    @property
    def is_safe(self) -> bool:
        return not self.invented

    @property
    def body(self) -> str:
        """The paragraphs as editable text, which is how the UI holds it."""
        return "\n\n".join(self.paragraphs)

    @property
    def words(self) -> int:
        return sum(len(p.split()) for p in self.paragraphs)


def greeting_for(recipient: str) -> str:
    return f"Dear {recipient.strip()}," if recipient.strip() else "Dear Hiring Manager,"


def closing_for(recipient: str) -> str:
    """British convention, and it is not arbitrary.

    "Yours sincerely" belongs to a letter that names its reader and "Yours
    faithfully" to one that does not. Getting it the wrong way round is a
    small thing that the sort of person who reads a lot of letters notices.
    """
    return "Yours sincerely," if recipient.strip() else "Yours faithfully,"


def _dossier(profile: Profile) -> str:
    """Everything the person has, laid out so the model can see the structure.

    A flat bag of sentences is enough for the *audit*, which only asks whether
    a word appears anywhere. Writing needs to know which bullet belongs to
    which job, because "at Northgate Labs I cut an ETL run from 42 minutes to
    9" is a letter and "I have experience with ETL" is not.
    """
    lines: list[str] = [f"Name: {profile.basics.name}"]
    if profile.basics.headline:
        lines.append(f"Headline: {profile.basics.headline}")
    if profile.basics.location:
        lines.append(f"Based in: {profile.basics.location}")
    if profile.summary.text:
        lines.append(f"Summary: {profile.summary.text}")

    if profile.experience:
        lines.append("\nEXPERIENCE")
        for entry in profile.experience:
            when = " to ".join(p for p in (entry.start, entry.end or "present") if p)
            lines.append(f"- {entry.role} at {entry.organisation} ({when})")
            lines += [f"    {b.text}" for b in entry.bullets if b.text.strip()]

    if profile.projects:
        lines.append("\nPROJECTS")
        for project in profile.projects:
            built = f" [built with {', '.join(project.tech)}]" if project.tech else ""
            lines.append(f"- {project.name}: {project.tagline}{built}")
            lines += [f"    {b.text}" for b in project.bullets if b.text.strip()]

    if profile.education:
        lines.append("\nEDUCATION")
        for entry in profile.education:
            grade = f", {entry.grade}" if entry.grade else ""
            lines.append(f"- {entry.credential}, {entry.institution}{grade}")
            if entry.coursework:
                lines.append(f"    Modules: {', '.join(entry.coursework)}")

    if profile.skills:
        lines.append("\nSKILLS")
        lines += [f"- {group.label}: {', '.join(group.items)}" for group in profile.skills]

    return "\n".join(lines)


def _system() -> str:
    banned = ", ".join(f'"{p}"' for p in FILLER_PHRASES[:18])
    return f"""\
You write a cover letter on behalf of one person, from their record. You are
a writer working from a file, not an advocate and not an author.

THE ABSOLUTE RULE: every claim about the writer must be evidenced in the
record you are given. You may not add a number, a duration, a team size, an
employer, a technology or an outcome that is not there. You may not say they
have experience with something the record does not show. If the job asks for
something they have not done, the letter does not mention it -- it does not
claim it, and it does not apologise for it either. A plausible invented claim
is the worst thing you can produce, because they will be asked about it in an
interview and will not be able to answer.

WHAT A GOOD LETTER DOES:
1. Opens by saying what they are applying for and the single most relevant
   thing they have actually done. Never "I am writing to apply for the
   position of", which spends the only sentence anyone is guaranteed to read
   on information already in the subject line.
2. Spends the middle on evidence: one or two specific things they built or
   changed, named with the tool and the effect, drawn straight from the
   record. Prefer the ones the posting asks for.
3. Connects that evidence to what the posting says the work is -- their
   problem, in their words, answered by something already done.
4. Closes briefly. No "I look forward to hearing from you at your earliest
   convenience"; say what they would bring and stop.

HOW IT SOUNDS: like the person wrote it in one sitting and meant it. Plain,
declarative, first person, active voice. Contractions are fine. No adjectives
about themselves -- the evidence does that work. Never these, in any tense,
and nothing with their flavour: {banned}. If a sentence could appear in any
cover letter in the world, delete it.

LENGTH: three or four paragraphs, {MAX_WORDS} words at the very most. Short is
read; long is skimmed.

Return only the body paragraphs. The greeting, the sign-off and the name are
added afterwards and must not appear in your output.
"""


def _brief(report: MatchReport, company: str, role: str) -> str:
    """What the posting asks for, split by what the profile can answer.

    The `missing` list is handed over as a prohibition rather than withheld.
    A model given only the covered terms tends to reach for the posting's
    other words anyway; a model told "these are the things they asked for that
    this person cannot evidence, do not claim them" reaches for them markedly
    less -- and either way the audit catches what gets through.
    """
    covered = [term.text for term in report.spec.terms if term.key in report.covered]
    missing = [term.text for term in report.missing]
    lines = [f"THE ROLE: {role or report.spec.title or 'the advertised role'}"]
    if company:
        lines.append(f"THE EMPLOYER: {company}")
    if covered:
        lines.append(
            "\nWHAT THEY ASK FOR THAT THIS PERSON CAN EVIDENCE -- build the "
            "letter on these:\n" + ", ".join(covered[:24])
        )
    if missing:
        lines.append(
            "\nWHAT THEY ASK FOR THAT THIS PERSON CANNOT EVIDENCE -- do not "
            "claim any of these, and do not mention that they are missing:\n"
            + ", ".join(missing[:24])
        )
    lines.append("\nTHE POSTING, in their own words:\n---\n" + report.spec.text[:6000] + "\n---")
    return "\n".join(lines)


def draft_letter(
    profile: Profile,
    report: MatchReport,
    *,
    recipient: str = "",
    company: str = "",
    role: str = "",
    note: str = "",
    model: str | None = None,
) -> Letter:
    """Draft a letter for one posting. Raises ``ValueError`` if there is nothing to write from."""
    facts = _dossier(profile)
    if len(facts.split()) < MIN_FACTS:
        raise ValueError(
            "There is not enough in the profile to write a letter from. Add a role "
            "or a project with a couple of bullets, then come back."
        )

    company = company or report.spec.company
    prompt = "\n".join(
        part
        for part in [
            _brief(report, company, role),
            "",
            "THEIR RECORD. Every claim in the letter must come from here:",
            "---",
            facts,
            "---",
            "",
            f"WHAT THEY WANT SAID, in their words: {note.strip()}" if note.strip() else "",
            "",
            "Write the body paragraphs.",
        ]
        if part != ""
    )

    drafted, used = generate(
        prompt,
        system=_system(),
        schema=LetterDraft,
        # The same as the tailoring pass: 0.1 writes the same four sentences
        # for every job, and a letter that reads as a template is worse than
        # no letter.
        temperature=0.45,
        # Choosing which two of nine bullets answer this posting is the
        # judgement the latency buys.
        thinking="MEDIUM",
        model=model,
        task="cover letter",
    )

    paragraphs = [p.strip() for p in drafted.paragraphs if p.strip()]
    return Letter(
        greeting=greeting_for(recipient),
        paragraphs=paragraphs,
        closing=closing_for(recipient),
        signature=profile.basics.name,
        model=used,
        # Audited as one block against the record. The company and the role
        # are given, so they are added to what counts as known -- naming the
        # employer you are writing to is not a claim about yourself.
        invented=audit(
            f"{facts}\n{company}\n{role}\n{recipient}",
            "\n".join(paragraphs),
            known=_known_vocabulary(profile),
        ),
    )
