"""A one-sheet interview brief, built from what is already on this machine.

Everything here is rules over `jobspec`'s existing read of the posting: the
requirements it named, which of your bullets already answer each one, and
which it asked for that nothing in your profile evidences. No model is
involved, which is the point — a brief you read the night before an interview
should say the same thing every time you open it, and should work on a train
with no signal.

**The questions are prompts, not predictions.** They are assembled from
templates keyed on what the posting asked for and whether you can evidence it.
Nobody can tell you what an interviewer will ask; what a brief can honestly do
is put the obvious question in front of you while there is still time to
prepare an answer. The wording says so.

**A gap is not a reason not to apply.** Half the value of this sheet is the
bridge line for each thing you have not done, because "I have not used
Terraform; I have written the Ansible that does the same job here" is an
answer, and silence is not.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .jobspec import Evidence, MatchReport, Term

# How many requirements a sheet can carry before it stops being one sheet.
# A brief nobody finishes reading is worse than a shorter one.
TOP_REQUIREMENTS = 12
GAPS_SHOWN = 6


@dataclass
class Answered:
    """One requirement, and the lines in your profile that already back it."""

    term: str
    tier: str
    weight: float
    evidence: list[Evidence] = field(default_factory=list)
    """Empty for a gap. Present, this is what you say when they ask."""

    prompts: list[str] = field(default_factory=list)
    """Questions worth having an answer ready for."""

    bridge: str = ""
    """For a gap: the honest shape of an answer, rather than a shrug."""


@dataclass
class Brief:
    title: str
    company: str
    coverage: int
    strengths: list[Answered]
    gaps: list[Answered]
    declared_only: list[str]
    """Named in your skills and described in no bullet. The weakest claim you
    can make, and exactly what a posting asking for it will expose."""


def _prompts_for_strength(term: str, evidence: list[Evidence]) -> list[str]:
    """What they will ask about something you can evidence."""
    where = evidence[0].entry_label if evidence else "your work"
    return [
        f"Walk me through the {term} work at {where}. What was the problem?",
        f"What went wrong with {term}, and what did you change afterwards?",
    ]


def _prompts_for_gap(term: str, tier: str) -> list[str]:
    """What they will ask about something you cannot."""
    if tier == "required":
        return [
            f"This role uses {term} daily. How much have you done?",
            f"How would you get up to speed on {term} in your first month?",
        ]
    return [
        f"Have you worked with {term} at all?",
        f"What would you reach for instead of {term}, and why?",
    ]


def _bridge(term: str, tier: str) -> str:
    """The honest shape of an answer to a gap.

    Not a script. A person reading their own brief needs the *form* of the
    answer -- name the nearest thing you have actually done, then say how you
    would close the distance -- because the failure in the room is going quiet,
    not using the wrong words.
    """
    if tier == "required":
        return (
            f"Name the nearest thing you have shipped, say plainly that you have not "
            f"used {term}, and finish with how you would pick it up. Do not claim it."
        )
    return (
        f"Say what you used instead of {term} and why it was the right call there. "
        f"A considered alternative reads better than a gap you talked around."
    )


def build_brief(report: MatchReport) -> Brief:
    """Turn a posting's analysis into a sheet you can read before an interview."""
    ranked = sorted(report.spec.terms, key=lambda t: (-t.weight, t.key))
    missing = {t.key for t in report.missing}

    strengths: list[Answered] = []
    gaps: list[Answered] = []

    for term in ranked:
        evidence = report.covered.get(term.key, [])
        # Three states, not two. `covered` holds a key with an *empty* list
        # when a term is declared in your skills and described in no bullet --
        # a weak claim, but not a gap. Calling it one would put "you have not
        # used Python" on the sheet of somebody who lists Python, which is
        # both false and the kind of thing that loses an interview. Those
        # belong to `declared_only`, which says what they actually are.
        weakly_covered = term.key in report.covered and not evidence
        if weakly_covered:
            continue
        if term.key in missing:
            if len(gaps) < GAPS_SHOWN:
                gaps.append(
                    Answered(
                        term=term.text,
                        tier=term.tier,
                        weight=term.weight,
                        prompts=_prompts_for_gap(term.text, term.tier),
                        bridge=_bridge(term.text, term.tier),
                    )
                )
        elif evidence and len(strengths) < TOP_REQUIREMENTS:
            strengths.append(
                Answered(
                    term=term.text,
                    tier=term.tier,
                    weight=term.weight,
                    # Two lines at most: this is a prompt sheet, not a
                    # reprint of the resume they already have.
                    evidence=evidence[:2],
                    prompts=_prompts_for_strength(term.text, evidence),
                )
            )

    return Brief(
        title=report.spec.title,
        company=report.spec.company,
        coverage=report.coverage,
        strengths=strengths,
        gaps=gaps,
        declared_only=report.declared_only[:8],
    )
