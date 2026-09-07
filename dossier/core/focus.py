"""The tags that aim one profile at several kinds of job.

A bullet or a skill group can carry ``#backend``; setting a focus on the
resume prints the lines tagged with it plus every untagged line. That has
worked since 1.1 and had no home: you tag a bullet in the Profile editor, you
pick a focus from a dropdown on Resume, and nothing anywhere shows you which
tags exist, how much each one actually selects, or which CV uses which.

Two consequences this module exists to fix.

**A focus nobody has tagged much prints the same document as any other.** If
``#research`` is on two bullets out of forty, the "research" resume differs
from the "backend" one by two lines. That is the failure mode of the whole
feature and nothing surfaced it -- the output looks fine, it is just not
tailored. Counting is the fix: see the number, see the problem.

**A tag could not be renamed.** ``#bakend`` on nine bullets meant editing nine
bullets, and the ninth is the one you miss. Renaming is a single pass over the
profile here.
"""

from __future__ import annotations

from dataclasses import dataclass

from .schema import Profile, normalise_tag

#: Sections whose entries carry taggable bullets.
ENTRY_SECTIONS = ("experience", "projects", "education")


@dataclass(frozen=True)
class Focus:
    """One tag, and how much of the profile it actually selects."""

    tag: str
    #: Bullets carrying this tag, across every entry section.
    bullets: int
    #: Skill groups carrying it.
    skills: int
    #: The CVs that open with this focus by default.
    cvs: list[str]

    @property
    def total(self) -> int:
        return self.bullets + self.skills


@dataclass(frozen=True)
class Coverage:
    """What every focus selects, plus what is common to all of them."""

    focuses: list[Focus]
    #: Bullets and skill groups carrying no tag at all. These print under
    #: every focus, and are usually most of the CV -- which is the point, and
    #: also why a thinly-tagged focus changes so little.
    untagged_bullets: int
    untagged_skills: int


def _bullets(profile: Profile):
    for section in ENTRY_SECTIONS:
        for entry in getattr(profile, section, []) or []:
            for bullet in getattr(entry, "bullets", []) or []:
                yield bullet


def coverage(profile: Profile, defaults: dict[str, str] | None = None) -> Coverage:
    """Count what each tag selects. ``defaults`` maps a CV name to its focus."""
    counts: dict[str, list[int]] = {}
    untagged_bullets = 0
    untagged_skills = 0

    for bullet in _bullets(profile):
        tags = {normalise_tag(t) for t in (getattr(bullet, "tags", []) or []) if t.strip()}
        if not tags:
            untagged_bullets += 1
        for tag in tags:
            counts.setdefault(tag, [0, 0])[0] += 1

    for group in profile.skills or []:
        tags = {normalise_tag(t) for t in (getattr(group, "tags", []) or []) if t.strip()}
        if not tags:
            untagged_skills += 1
        for tag in tags:
            counts.setdefault(tag, [0, 0])[1] += 1

    # A CV can default to a focus nobody has tagged anything with yet -- that
    # is a focus in the making, not an error, so it belongs in the list at
    # zero rather than being dropped.
    by_focus: dict[str, list[str]] = {}
    for cv_name, tag in (defaults or {}).items():
        if tag:
            by_focus.setdefault(normalise_tag(tag), []).append(cv_name)
            counts.setdefault(normalise_tag(tag), [0, 0])

    focuses = [
        Focus(tag=tag, bullets=n[0], skills=n[1], cvs=sorted(by_focus.get(tag, [])))
        for tag, n in counts.items()
    ]
    focuses.sort(key=lambda f: (-f.total, f.tag))
    return Coverage(
        focuses=focuses,
        untagged_bullets=untagged_bullets,
        untagged_skills=untagged_skills,
    )


def rename(profile: Profile, old: str, new: str) -> tuple[Profile, int]:
    """Retag the whole profile, returning the new profile and how many changed.

    ``new`` empty removes the tag instead. Both are one pass, which is the
    entire reason this is here: doing it by hand across nine bullets means
    missing the ninth.
    """
    old = normalise_tag(old)
    new = normalise_tag(new)
    if not old:
        raise ValueError("Say which focus to rename.")
    if old == new:
        return profile, 0

    changed = 0
    updated = profile.model_copy(deep=True)

    def retag(tags: list[str]) -> tuple[list[str], bool]:
        seen = [normalise_tag(t) for t in tags if t.strip()]
        if old not in seen:
            return tags, False
        out: list[str] = []
        for tag in seen:
            replacement = new if tag == old else tag
            # `dict.fromkeys` order-preserving dedupe: renaming onto a tag the
            # line already carries must not leave it there twice.
            if replacement and replacement not in out:
                out.append(replacement)
        return out, True

    for bullet in _bullets(updated):
        tags, hit = retag(getattr(bullet, "tags", []) or [])
        if hit:
            bullet.tags = tags
            changed += 1

    for group in updated.skills or []:
        tags, hit = retag(getattr(group, "tags", []) or [])
        if hit:
            group.tags = tags
            changed += 1

    return updated, changed
