"""Re-angling a profile at one job, and checking the model's work.

The rule this module exists to enforce: **tailoring re-angles facts, it never
adds them.** A resume is a claim someone will be asked about in an interview,
so a bullet that gained a number the original did not have is not an improved
bullet -- it is a lie the user has not yet noticed. Everything here is built
around that being caught mechanically rather than hoped away in a prompt.

Three things stop a rewrite being taken on trust:

1. **The model is never asked what the job requires.** ``core/jobspec.py`` has
   already read the posting by rules; the model receives that analysis as
   given. A hallucinated requirement would otherwise re-angle a whole resume
   towards something the employer never asked for.

2. **Every rewrite is diffed against its original** by ``audit``. Numbers that
   appear in the rewrite and not in the source are reported as invented, and
   so are specific names -- technologies, organisations, datasets -- that are
   in neither the original bullet nor anything the user has declared elsewhere
   in their profile. The UI shows these before the user can accept.

3. **Every rewrite goes back through ``core/quality.py``**, the same linter the
   Health screen uses. A rewrite that trades filler for different filler is
   visible as a score that did not move. The model is given the linter's own
   banned-phrase list in its instructions, so the standard and the check
   cannot drift apart.

Rewrites are keyed by the block id they replace. That is what ``TextBlock``'s
stable id was always for: a suggestion can be accepted, rejected or reverted
one bullet at a time, and nothing has to guess which line it came from.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from ..core.markup import plain
from ..core.jobspec import EXTRA_LEXICON, JobSpec, MatchReport
from ..core.quality import (
    COMMON_TECH,
    FILLER_PHRASES,
    build_vocabulary,
    check_text,
    expand_terms,
)
from ..core.schema import Profile, entry_label
from .client import generate

# How many of the posting's terms to put in front of the model. Past this it
# is reading boilerplate, and a long list dilutes the ones that matter.
MAX_TERMS = 25

# Bullets sent in one request. A whole profile in one call is cheaper, but a
# single failure then costs every rewrite; this is also roughly where the
# model starts losing track of which id belongs to which line.
MAX_BULLETS = 40


# --------------------------------------------------------------------------
# The shape the model fills in
# --------------------------------------------------------------------------


class RewrittenBullet(BaseModel):
    block_id: str = Field(description="Copy the id of the bullet being rewritten, exactly")
    text: str = Field(description="The rewritten bullet. Empty string to leave it alone.")
    reason: str = Field(default="", description="Under 12 words: what this change does for this job")


class TailorDraft(BaseModel):
    summary: str = Field(default="", description="Rewritten summary, or empty to leave it alone")
    summary_reason: str = ""
    bullets: list[RewrittenBullet] = Field(default_factory=list)


def _system_instruction() -> str:
    """Built from the linter's own list, so the two cannot drift apart."""
    banned = ", ".join(f'"{p}"' for p in FILLER_PHRASES[:18])
    return f"""\
You re-angle an existing resume at one specific job. You are an editor, not an
author.

THE ABSOLUTE RULE: every fact in your output must already be in the input. You
may reorder, compress, re-emphasise and change wording. You may NOT add a
number, a percentage, a duration, a team size, a technology, an employer, a
dataset or an outcome that is not in the bullet you were given. If a bullet
has no metric, it stays without one -- write the strongest honest version
instead. Inventing a plausible number is the single worst thing you can do
here, because the person will be asked about it in an interview.

What re-angling actually means:
1. Lead with the part of the fact this job cares about. If the posting asks for
   SQL and the bullet mentions SQL in passing, SQL moves to the front.
2. Use the posting's own vocabulary where it genuinely describes what was done.
   If the bullet says "data cleaning" and the posting says "data preparation",
   use the posting's phrase. If the posting says "Kubernetes" and the bullet
   does not, you may NOT introduce it.
3. Cut what this job does not care about, so the relevant part has room.
4. Open with a past-tense verb of result: Built, Cut, Shipped, Migrated,
   Automated, Reduced. Never with an -ing verb.
5. Under 200 characters. One line per thing that changed.

Banned as filler, in any tense: {banned}. Say what changed instead.

Return a rewrite only for bullets you are genuinely improving. Leave `text`
empty for any bullet that is already right for this job -- an unnecessary
rewrite wastes the reader's review and risks drift. Copy each `block_id`
exactly as given; it is how the rewrite is matched back to the line.
"""


# --------------------------------------------------------------------------
# The result
# --------------------------------------------------------------------------


@dataclass
class Suggestion:
    """One proposed rewrite, already checked."""

    block_id: str
    section: str
    entry_label: str
    before: str
    after: str
    reason: str

    invented: list[str] = field(default_factory=list)
    """Numbers and names present in the rewrite and in nothing it came from.

    Not necessarily a lie -- a model sometimes spells out a figure the bullet
    implied -- but always worth a human's eye, so the UI blocks nothing and
    flags everything."""

    findings_before: int = 0
    findings_after: int = 0
    terms_added: list[str] = field(default_factory=list)
    """Posting terms the rewrite now carries that the original did not. This
    is the whole point of the exercise, stated as a number."""

    @property
    def is_safe(self) -> bool:
        return not self.invented

    @property
    def is_improvement(self) -> bool:
        return bool(self.terms_added) or self.findings_after < self.findings_before


@dataclass
class TailorResult:
    model: str
    summary: Suggestion | None
    suggestions: list[Suggestion]
    notes: list[str] = field(default_factory=list)

    @property
    def flagged(self) -> int:
        return sum(1 for s in self.suggestions if not s.is_safe)


# --------------------------------------------------------------------------
# Checking the model's work
# --------------------------------------------------------------------------

NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?%?")

# Shapes that are a specific name whatever the word is: acronyms, internal
# capitals, dotted module names. Ordinary capitalised words are excluded here
# on purpose -- a rewrite legitimately re-capitalises a sentence, and flagging
# "Built" as an invented entity would make the warning worthless.
NAME_RE = re.compile(r"\b(?:[A-Z][a-z]+[A-Z][A-Za-z]*|[A-Z]{2,}|[a-z]+\.(?:js|py|ts|io|ai|sh))\b")

WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#.\-]*")

# The gap the shape rules leave: "Kubernetes", "Docker", "React" and "Django"
# are ordinary capitalised words, and a model inserting one is the most likely
# fabrication there is, since the posting is full of them. Checked by name
# rather than by shape.
_TECH = COMMON_TECH | EXTRA_LEXICON

# Below this a prefix match is coincidence rather than the same product.
MIN_PREFIX = 4


def _numbers(text: str) -> set[str]:
    """Numbers, normalised so "1,200" and "1200" are the same claim."""
    return {match.group(0).replace(",", "").rstrip("%") for match in NUMBER_RE.finditer(text)}


def _is_known(key: str, known: frozenset[str]) -> bool:
    """Whether the user has declared this, allowing for how products get named.

    Someone whose skills say "Postgres" writing "PostgreSQL" has not invented
    anything, and a warning that fires on that teaches people to ignore
    warnings. Matched by prefix in either direction, with a floor that stops
    "Go" matching "Google".
    """
    if key in known:
        return True
    return any(
        len(term) >= MIN_PREFIX and (term.startswith(key) or key.startswith(term))
        for term in known
    )


def audit(before: str, after: str, *, known: frozenset[str]) -> list[str]:
    """What the rewrite asserts that its source did not.

    ``known`` is everything the user has declared anywhere in their profile, so
    a bullet that names a technology listed in their skills is not flagged --
    they do know it, and moving it into the sentence is legitimate re-angling.
    A name in neither place is the model importing something from the posting,
    which is exactly what it was told not to do.
    """
    invented: list[str] = []

    source_numbers = _numbers(before)
    for number in sorted(_numbers(after)):
        if number not in source_numbers:
            invented.append(number)

    lowered_before = before.lower()
    seen: set[str] = set()

    def consider(name: str) -> None:
        key = name.lower().strip(".-")
        if key in seen or key in lowered_before or _is_known(key, known):
            return
        # A word already inside the original, in any casing, is not new.
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(key)}(?![A-Za-z0-9])", lowered_before):
            return
        seen.add(key)
        invented.append(name)

    for match in NAME_RE.finditer(after):
        consider(match.group(0))
    for match in WORD_RE.finditer(after):
        if match.group(0).lower().strip(".-") in _TECH:
            consider(match.group(0))

    return invented


def _covered_terms(text: str, spec: JobSpec) -> set[str]:
    lowered = text.lower()
    return {
        term.key
        for term in spec.terms
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(term.key)}(?![A-Za-z0-9])", lowered)
    }


def _known_vocabulary(profile: Profile) -> frozenset[str]:
    """Everything the user has declared, in any form, lowercased.

    Wider than ``quality.build_vocabulary`` on purpose: that one answers "is
    this bullet specific", and this one answers "could this person legitimately
    have written this word", so employers, roles and institutions count too.
    """
    terms: set[str] = set(build_vocabulary(profile))
    declared: list[str] = [plain(profile.basics.name), plain(profile.basics.headline)]
    for entry in profile.experience:
        declared += [entry.role, entry.organisation, entry.location]
    for project in profile.projects:
        declared += [project.name, project.tagline, *project.tech]
    for education in profile.education:
        declared += [education.institution, education.credential, *education.coursework]
    for group in profile.skills:
        declared += [group.label, *group.items]
    for certification in profile.certifications:
        declared += [certification.name, certification.issuer]
    return frozenset(terms | expand_terms(declared))


# --------------------------------------------------------------------------
# Building the request
# --------------------------------------------------------------------------


def _bullet_rows(profile: Profile, report: MatchReport, only: set[str] | None) -> list[dict]:
    """The bullets to send, most relevant entry first.

    Ordered by the entry relevance already computed, so when a profile has more
    bullets than one request should carry, the ones that get rewritten are the
    ones this job is about.
    """
    rank = {entry.entry_id: index for index, entry in enumerate(report.entries)}
    rows: list[dict] = []

    for section in ("experience", "projects", "education"):
        for entry in getattr(profile, section):
            if only is not None and entry.id not in only:
                continue
            for block in entry.bullets:
                if not block.text.strip():
                    continue
                rows.append(
                    {
                        "block_id": block.id,
                        "section": section,
                        "entry_id": entry.id,
                        "entry": entry_label(entry),
                        "text": plain(block.text),
                        "rank": rank.get(entry.id, 999),
                    }
                )

    rows.sort(key=lambda row: row["rank"])
    return rows[:MAX_BULLETS]


def build_prompt(profile: Profile, report: MatchReport, rows: list[dict]) -> str:
    spec = report.spec
    wanted = spec.terms[:MAX_TERMS]

    required = ", ".join(t.text for t in wanted if t.tier == "required") or "(none stated)"
    preferred = ", ".join(t.text for t in wanted if t.tier != "required") or "(none stated)"
    missing = ", ".join(t.text for t in report.missing[:15]) or "(nothing)"

    lines = [
        f"THE JOB: {spec.title or 'Untitled role'}"
        + (f" at {spec.company}" if spec.company else ""),
        "",
        f"What it requires: {required}",
        f"What it prefers: {preferred}",
        "",
        "Terms this posting asks for that the profile does not currently evidence: "
        f"{missing}.",
        "Do NOT insert these. They are listed so you can recognise the ones a bullet",
        "already demonstrates under a different name, and use the posting's wording",
        "for those.",
        "",
        "THE POSTING, in full:",
        "---",
        spec.text.strip()[:6000],
        "---",
        "",
    ]

    if profile.summary.text.strip():
        lines += [
            "CURRENT SUMMARY (rewrite it for this job, same facts only):",
            plain(profile.summary.text).strip(),
            "",
        ]

    lines.append("BULLETS TO CONSIDER. Each has an id you must copy exactly:")
    current_entry = ""
    for row in rows:
        if row["entry"] != current_entry:
            current_entry = row["entry"]
            lines.append(f"\n## {current_entry} ({row['section']})")
        lines.append(f"[{row['block_id']}] {row['text']}")

    return "\n".join(lines)


# --------------------------------------------------------------------------
# The call
# --------------------------------------------------------------------------


def tailor(
    profile: Profile,
    report: MatchReport,
    *,
    entry_ids: set[str] | None = None,
    model: str | None = None,
    on_attempt: Callable[[str, str], None] | None = None,
) -> TailorResult:
    """Ask a model to re-angle this profile at this posting, then check it.

    Nothing is written anywhere. The result is a list of proposals, each
    already audited against its original and re-scored by the linter, for the
    caller to accept one at a time.
    """
    rows = _bullet_rows(profile, report, entry_ids)
    if not rows and not profile.summary.text.strip():
        raise ValueError(
            "There is nothing to tailor yet. Add a role or a project with at least "
            "one bullet, then come back."
        )

    draft, model_used = generate(
        build_prompt(profile, report, rows),
        system=_system_instruction(),
        schema=TailorDraft,
        # Higher than extraction, and deliberately: this is a writing task and
        # 0.1 produces the same flat phrasing on every bullet. Still low enough
        # that the wording stays close to the source.
        temperature=0.4,
        # Rewriting against a list of constraints is where thinking earns its
        # latency, unlike transcription.
        thinking="MEDIUM",
        model=model,
        on_attempt=on_attempt,
        task="tailoring pass",
    )

    known = _known_vocabulary(profile)
    by_id = {row["block_id"]: row for row in rows}
    vocabulary = build_vocabulary(profile)

    def make(block_id: str, section: str, label: str, before: str, after: str, reason: str) -> Suggestion:
        return Suggestion(
            block_id=block_id,
            section=section,
            entry_label=label,
            before=before,
            after=after,
            reason=reason.strip(),
            invented=audit(before, after, known=known),
            findings_before=len(
                check_text(before, block_id, is_summary=(section == "summary"), vocabulary=vocabulary)
            ),
            findings_after=len(
                check_text(after, block_id, is_summary=(section == "summary"), vocabulary=vocabulary)
            ),
            terms_added=sorted(
                _covered_terms(after, report.spec) - _covered_terms(before, report.spec)
            ),
        )

    suggestions: list[Suggestion] = []
    seen: set[str] = set()
    unknown = 0

    for item in draft.bullets:
        after = item.text.strip()
        row = by_id.get(item.block_id)
        if row is None:
            # A model that invents an id has nothing to rewrite. Counted and
            # reported rather than dropped silently, because a rise here would
            # mean the prompt has stopped being followed.
            if after:
                unknown += 1
            continue
        if not after or after == row["text"].strip() or item.block_id in seen:
            continue
        seen.add(item.block_id)
        suggestions.append(
            make(item.block_id, row["section"], row["entry"], row["text"], after, item.reason)
        )

    summary = None
    new_summary = draft.summary.strip()
    if new_summary and new_summary != profile.summary.text.strip():
        summary = make(
            profile.summary.id, "summary", "Summary",
            profile.summary.text, new_summary, draft.summary_reason,
        )

    notes: list[str] = [
        f"Rewritten by {model_used}. It was told to re-angle, never to add -- "
        "every number and name below was checked against the bullet it came from."
    ]
    if unknown:
        notes.append(
            f"{unknown} rewrite{'s' if unknown > 1 else ''} came back against an id that is "
            "not in your profile, and were discarded."
        )
    flagged = sum(1 for s in suggestions if not s.is_safe) + (
        1 if summary and not summary.is_safe else 0
    )
    if flagged:
        notes.append(
            f"{flagged} rewrite{'s' if flagged > 1 else ''} introduced a number or name that is "
            "not in the original. Those are marked -- read them before accepting."
        )

    return TailorResult(model=model_used, summary=summary, suggestions=suggestions, notes=notes)


def apply_suggestions(profile: Profile, accepted: dict[str, str]) -> tuple[Profile, int]:
    """Return a copy of the profile with ``{block_id: text}`` written in.

    A copy, not a mutation: the caller hands the result back to the editor as a
    proposed state, which is what keeps undo working and keeps an unsaved
    tailoring pass discardable.
    """
    updated = profile.model_copy(deep=True)
    changed = 0

    if updated.summary.id in accepted:
        updated.summary.text = accepted[updated.summary.id]
        changed += 1

    for section in ("experience", "projects", "education"):
        for entry in getattr(updated, section):
            for block in entry.bullets:
                if block.id in accepted:
                    block.text = accepted[block.id]
                    changed += 1

    return updated, changed
