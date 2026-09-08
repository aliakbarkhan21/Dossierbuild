"""Folding imported data into the profile that already exists.

The rule this module exists to enforce: **an import adds, it never silently
replaces.** The master profile is hand-curated data. A LinkedIn export or a
model's reading of an old PDF is a proposal, and proposals get reviewed.

So importing is two steps, not one:

1. ``build_merge_plan`` compares the candidate profile against the current one
   and produces a plan -- a list of single-field proposals and a list of whole
   entries, each flagged if it looks like something already present.
2. ``apply_merge_plan`` applies only what was ticked.

Nothing here mutates the profile until step 2.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..core.markup import plain
from ..core.schema import LIST_SECTIONS, Profile, SkillGroup, entry_label, format_date, format_range


# --------------------------------------------------------------------------
# Plan objects
# --------------------------------------------------------------------------


@dataclass
class FieldProposal:
    """One scalar field the import wants to set."""

    path: str  # "basics.name", "summary"
    label: str
    current: str
    proposed: str

    @property
    def conflicts(self) -> bool:
        """True when accepting this would overwrite something you wrote."""
        return bool(self.current.strip()) and self.current.strip() != self.proposed.strip()

    @property
    def is_noop(self) -> bool:
        return self.current.strip() == self.proposed.strip()


@dataclass
class MergeCandidate:
    """One whole entry the import wants to add."""

    key: str
    section: str
    entry: Any
    label: str
    detail: str
    duplicate_of: str | None = None  # id of the existing entry it resembles

    @property
    def is_duplicate(self) -> bool:
        return self.duplicate_of is not None


@dataclass
class MergePlan:
    source: str
    fields: list[FieldProposal] = field(default_factory=list)
    candidates: list[MergeCandidate] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def new_candidates(self) -> list[MergeCandidate]:
        return [c for c in self.candidates if not c.is_duplicate]

    @property
    def duplicate_candidates(self) -> list[MergeCandidate]:
        return [c for c in self.candidates if c.is_duplicate]

    def default_selection(self) -> set[str]:
        """Ticked by default: everything new, nothing that looks duplicated."""
        return {c.key for c in self.new_candidates}


# --------------------------------------------------------------------------
# Duplicate detection
# --------------------------------------------------------------------------


def _norm(text: str) -> str:
    """Lowercase, strip punctuation and collapse spaces, for comparison only.

    Formatting comes out first. Without that, ``<b>`` reduces to the word "b"
    and a line somebody has emboldened since importing it stops matching the
    line it came from -- so re-importing the same resume would offer it again
    as new.
    """
    return re.sub(r"[^a-z0-9]+", " ", plain(text or "").lower()).strip()


def _identity(section: str, entry: Any) -> str:
    """A comparison key for an entry -- what makes it 'the same thing'.

    Deliberately ignores dates and bullet text. Re-importing a LinkedIn export
    after editing the bullets on a role should still recognise the role.
    """
    if section == "experience":
        return f"{_norm(entry.role)}|{_norm(entry.organisation)}"
    if section == "projects":
        return _norm(entry.name)
    if section == "education":
        return f"{_norm(entry.institution)}|{_norm(entry.credential)}"
    if section == "skills":
        return _norm(entry.label)
    if section == "certifications":
        return f"{_norm(entry.name)}|{_norm(entry.issuer)}"
    if section == "awards":
        return f"{_norm(entry.title)}|{_norm(entry.awarded_by)}"
    if section == "achievements":
        return f"{_norm(entry.title)}|{_norm(entry.context)}"
    if section == "sections":
        # The heading alone. Two imports of the same CV should not stack two
        # copies of "Executive Qualifications", and the body is the part most
        # likely to have been edited since -- which is exactly what the rest
        # of this function deliberately ignores.
        return _norm(entry.title)
    return _norm(str(entry))


# The review screen is part of the dashboard, not the resume, so it follows
# the dashboard's numeric convention rather than the design's -- there is no
# design in play at import time anyway.
DASHBOARD_DATES = "numeric"


def _detail(section: str, entry: Any) -> str:
    """A one-line preview for the review UI."""
    if section == "sections":
        # The words themselves. Nothing else about a custom section is worth
        # previewing -- it has no dates and no issuer -- and the whole question
        # a reviewer is answering here is "is this really on my CV".
        head = " ".join(entry.text.split())
        if not head and entry.bullets:
            head = " ".join(entry.bullets[0].text.split())
        count = len(entry.bullets)
        tail = f" (+{count} bullets)" if count else ""
        return (head[:110] + ("…" if len(head) > 110 else "")) + tail or "no detail"
    if section == "skills":
        items = ", ".join(entry.items[:8])
        more = f" (+{len(entry.items) - 8} more)" if len(entry.items) > 8 else ""
        return items + more
    bullets = getattr(entry, "bullets", [])
    span = ""
    if getattr(entry, "start", None):
        span = format_range(entry.start, getattr(entry, "end", None), style=DASHBOARD_DATES)
    else:
        # Certifications carry `issued`, awards carry `date` -- single points in
        # time rather than ranges.
        single = getattr(entry, "issued", None) or getattr(entry, "date", None)
        if single:
            span = format_date(single, blank="", style=DASHBOARD_DATES)

    extras = []
    issuer = (
        getattr(entry, "issuer", "")
        or getattr(entry, "awarded_by", "")
        or getattr(entry, "context", "")
    )
    if issuer:
        extras.append(issuer)
    if bullets:
        extras.append(f"{len(bullets)} bullets")

    parts = [p for p in (span, *extras) if p]
    return "  ".join(parts) or "no dates or detail"


# --------------------------------------------------------------------------
# Building the plan
# --------------------------------------------------------------------------


def build_merge_plan(current: Profile, candidate: Profile, source: str) -> MergePlan:
    """Compare an imported profile against the current one."""
    plan = MergePlan(source=source)

    scalar_fields = [
        ("basics.name", "Name", current.basics.name, candidate.basics.name),
        ("basics.headline", "Headline", current.basics.headline, candidate.basics.headline),
        ("basics.email", "Email", current.basics.email, candidate.basics.email),
        ("basics.phone", "Phone", current.basics.phone, candidate.basics.phone),
        ("basics.location", "Location", current.basics.location, candidate.basics.location),
        ("summary", "Summary", current.summary.text, candidate.summary.text),
    ]
    for path, label, now, proposed in scalar_fields:
        if not (proposed or "").strip():
            continue
        proposal = FieldProposal(path, label, now or "", proposed)
        if not proposal.is_noop:
            plan.fields.append(proposal)

    for section in LIST_SECTIONS:
        existing = {_identity(section, e): e.id for e in getattr(current, section)}
        for index, entry in enumerate(getattr(candidate, section)):
            identity = _identity(section, entry)
            plan.candidates.append(
                MergeCandidate(
                    # Deliberately not the entry id: ids are minted by default_factory,
                    # so parsing the same candidate JSON twice produces different
                    # ones. A client that asks for a plan and then posts back the
                    # keys it accepted would match nothing. Section and position
                    # are stable for the same input, and unique within a plan.
                    key=f"{section}:{index}",
                    section=section,
                    entry=entry,
                    label=entry_label(entry),
                    detail=_detail(section, entry),
                    duplicate_of=existing.get(identity) if identity.strip("| ") else None,
                )
            )

    return plan


# --------------------------------------------------------------------------
# Applying the plan
# --------------------------------------------------------------------------


def apply_merge_plan(
    profile: Profile,
    plan: MergePlan,
    accepted_fields: set[str],
    accepted_candidates: set[str],
) -> list[str]:
    """Apply the ticked parts of a plan. Returns a human-readable changelog."""
    changes: list[str] = []

    for proposal in plan.fields:
        if proposal.path not in accepted_fields:
            continue
        if proposal.path == "summary":
            profile.summary.text = proposal.proposed
        else:
            _, attr = proposal.path.split(".", 1)
            setattr(profile.basics, attr, proposal.proposed)
        changes.append(f"Set {proposal.label.lower()}")

    added: dict[str, int] = {}
    for candidate in plan.candidates:
        if candidate.key not in accepted_candidates:
            continue
        if candidate.section == "skills":
            _merge_skill_group(profile, candidate.entry)
        else:
            getattr(profile, candidate.section).append(candidate.entry)
        added[candidate.section] = added.get(candidate.section, 0) + 1

    for section, count in added.items():
        changes.append(f"Added {count} to {section}")

    return changes


def _merge_skill_group(profile: Profile, group: SkillGroup) -> None:
    """Fold a skill group into a same-named existing group if there is one.

    Skills are the one section where appending a duplicate group is clearly
    wrong -- two groups both called "Languages" would render as two lines. Items
    are compared case-insensitively so "python" does not join "Python".
    """
    target = next((g for g in profile.skills if _norm(g.label) == _norm(group.label)), None)
    if target is None:
        profile.skills.append(group)
        return
    seen = {_norm(item) for item in target.items}
    for item in group.items:
        if _norm(item) not in seen:
            target.items.append(item)
            seen.add(_norm(item))
