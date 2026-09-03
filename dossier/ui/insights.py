"""Readouts over the master profile: strength, timeline, search, export.

Nothing here edits anything. Every function takes a ``Profile`` and returns
either numbers or markup, which keeps this module free of Streamlit state and
makes each piece testable on its own.

The theme running underneath these is the same one the writing standard uses:
a resume is judged on whether its bullets name something specific and land in
a readable length, not on how many of them there are. So the meters below
measure quality of material, not volume of it -- a profile with six sharp
bullets should read stronger here than one with thirty vague ones.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

import streamlit as st

from ..core.quality import MAX_CHARS, MIN_CHARS, NUMBER_RE, build_vocabulary, mentions_specific
from ..core.schema import (
    LIST_SECTIONS,
    Profile,
    entry_label,
    format_range,
    iter_bullets,
)

# --------------------------------------------------------------------------
# Strength
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Meter:
    """One measured dimension, as a percentage with its raw counts."""

    label: str
    pct: int
    detail: str
    hint: str


def strength(profile: Profile) -> list[Meter]:
    """Four things worth knowing about the writing, as percentages.

    Percentages rather than counts because the useful question is "what
    proportion of what I have is pulling its weight", which stays meaningful
    whether the profile holds five bullets or fifty.
    """
    blocks = [b for _s, _o, b in iter_bullets(profile) if b.text.strip()]
    vocabulary = build_vocabulary(profile)
    total = len(blocks)

    def pct(n: int) -> int:
        return round(100 * n / total) if total else 0

    quantified = sum(1 for b in blocks if NUMBER_RE.search(b.text))
    specific = sum(1 for b in blocks if mentions_specific(b.text, vocabulary))
    in_range = sum(1 for b in blocks if MIN_CHARS <= len(b.text.strip()) <= MAX_CHARS)
    filled = sum(1 for _k, ok in section_fill(profile) if ok)
    sections = len(SECTION_LABELS)

    return [
        Meter(
            "Quantified",
            pct(quantified),
            f"{quantified} of {total} bullets",
            "Bullets carrying a number: a size, a count, a duration, a percentage.",
        ),
        Meter(
            "Specific",
            pct(specific),
            f"{specific} of {total} bullets",
            "Bullets naming a real technology, tool or place from your own profile.",
        ),
        Meter(
            "Well-sized",
            pct(in_range),
            f"{in_range} of {total} bullets",
            f"Between {MIN_CHARS} and {MAX_CHARS} characters -- long enough to say "
            "something, short enough to be read.",
        ),
        Meter(
            "Sections",
            round(100 * filled / sections) if sections else 0,
            f"{filled} of {sections} filled",
            "How much of the master profile exists at all.",
        ),
    ]


SECTION_LABELS: dict[str, str] = {
    "basics": "Contact",
    "summary": "Summary",
    "experience": "Experience",
    "projects": "Projects",
    "education": "Education",
    "skills": "Skills",
    "certifications": "Certifications",
    "awards": "Awards",
}


def section_fill(profile: Profile) -> list[tuple[str, bool]]:
    """One (label, has content) pair per section, in editor order."""
    out: list[tuple[str, bool]] = []
    for key, label in SECTION_LABELS.items():
        if key == "basics":
            ok = bool(profile.basics.name and profile.basics.email)
        elif key == "summary":
            ok = bool(profile.summary.text.strip())
        else:
            ok = bool(getattr(profile, key, None))
        out.append((label, ok))
    return out


def render_strength(meters: list[Meter]) -> None:
    bars = "".join(
        f'<div class="db-meter" title="{m.hint}">'
        f'<div class="db-meter-head"><span>{m.label}</span>'
        f'<span class="db-meter-pct">{m.pct}%</span></div>'
        f'<div class="db-meter-track"><span style="width:{m.pct}%"></span></div>'
        f'<div class="db-meter-detail">{m.detail}</div>'
        f"</div>"
        for m in meters
    )
    st.markdown(f'<div class="db-meters">{bars}</div>', unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Timeline
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Span:
    label: str
    kind: str
    start: float
    end: float
    ongoing: bool
    text: str


def _as_year(value: str | None) -> float | None:
    """"2025-06" -> 2025.42. Partial dates are the norm here, not an edge case."""
    if not value:
        return None
    match = re.match(r"^(\d{4})(?:-(\d{2}))?$", str(value).strip())
    if not match:
        return None
    year = int(match.group(1))
    month = int(match.group(2)) if match.group(2) else 1
    return year + (month - 1) / 12


def spans(profile: Profile) -> list[Span]:
    """Everything with dates, flattened into comparable bars.

    An entry with no start date is skipped rather than guessed at: a bar
    placed at an invented time would be worse than no bar.
    """
    today = date.today()
    now = today.year + (today.month - 1) / 12
    out: list[Span] = []
    for kind in ("experience", "education", "projects"):
        for entry in getattr(profile, kind, []):
            start = _as_year(entry.start)
            if start is None:
                continue
            end = _as_year(entry.end)
            out.append(
                Span(
                    label=entry_label(entry) or kind.title(),
                    kind=kind,
                    start=start,
                    end=end if end is not None else now,
                    ongoing=entry.end is None,
                    text=format_range(entry.start, entry.end),
                )
            )
    return sorted(out, key=lambda s: s.start, reverse=True)


def render_timeline(profile: Profile) -> bool:
    """Bars on a shared year axis. Returns False if there was nothing to draw.

    Laid out in plain HTML rather than with a chart library: it is a handful
    of absolutely positioned divs, and keeping it in the stylesheet means it
    inherits the theme's colours in both modes for free.
    """
    items = spans(profile)
    if not items:
        return False

    today = date.today()
    now = today.year + (today.month - 1) / 12

    lo = min(s.start for s in items)
    # A degree that runs to 2029 would otherwise set the scale, squeezing six
    # years of actual history into the left third of the chart to make room
    # for empty future. The axis stops a year past today; anything reaching
    # beyond that is drawn as ongoing, which is what it is.
    horizon = now + 1.0
    hi = min(max(s.end for s in items), horizon)
    hi = max(hi, lo + 0.75)  # a single short entry still deserves a full axis

    span = hi - lo
    lo -= span * 0.03
    hi += span * 0.03
    span = hi - lo

    def pos(value: float) -> float:
        return 100 * (min(max(value, lo), hi) - lo) / span

    rows = []
    for item in items:
        left = pos(item.start)
        width = pos(item.end) - left
        beyond = item.ongoing or item.end > hi
        rows.append(
            f'<div class="db-tl-row">'
            f'<span class="db-tl-label" title="{item.label}">{item.label}</span>'
            f'<span class="db-tl-track">'
            f'<span class="db-tl-bar {item.kind}{" ongoing" if beyond else ""}" '
            f'style="left:{left:.2f}%;width:{width:.2f}%" '
            f'title="{item.label} -- {item.text}"></span>'
            f"</span>"
            f'<span class="db-tl-dates">{item.text}</span>'
            f"</div>"
        )

    # One tick per year while that stays readable, then every second or fifth,
    # so a long history does not turn the axis into a solid row of digits.
    years = [y for y in range(int(lo) + 1, int(hi) + 2) if lo <= y <= hi]
    step = 1 if len(years) <= 8 else (2 if len(years) <= 16 else 5)
    ticks = "".join(
        f'<span class="db-tl-tick" style="left:{pos(year):.2f}%">{year}</span>'
        for year in years
        if year % step == 0 or step == 1
    )

    st.markdown(
        f'<div class="db-timeline">{"".join(rows)}'
        f'<div class="db-tl-row db-tl-axis"><span class="db-tl-label"></span>'
        f'<span class="db-tl-track">{ticks}</span>'
        f'<span class="db-tl-dates"></span></div></div>',
        unsafe_allow_html=True,
    )
    _legend_row(items)
    return True


def _legend_row(items: list[Span]) -> None:
    """The legend *is* the navigation.

    There were two of these: an HTML legend in the corner of the chart and a
    row of jump buttons under it, saying the same three words twice and
    overlapping each other. One row now carries the colour key and opens the
    section it names.
    """
    kinds = [k for k in ("experience", "education", "projects") if any(s.kind == k for s in items)]
    if not kinds:
        return

    columns = st.columns([*[0.16] * len(kinds), max(0.08, 1 - 0.16 * len(kinds))])
    for column, kind in zip(columns, kinds):
        with column, st.container(key=f"db_tl_{kind}"):
            st.markdown(
                f'<span class="db-tl-dot {kind}"></span>', unsafe_allow_html=True
            )
            if st.button(
                SECTION_LABELS.get(kind, kind.title()),
                type="tertiary",
                key=f"db_tljump_{kind}",
                help=f"Open {kind} in the editor",
            ):
                st.session_state.db_section = kind
                st.rerun()


# --------------------------------------------------------------------------
# Search
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Hit:
    section: str
    owner: str
    text: str


def search(profile: Profile, query: str) -> list[Hit]:
    """Every bullet containing ``query``, with the entry it belongs to.

    Case-insensitive substring rather than anything cleverer: on a few dozen
    bullets that is exactly as good as a ranked search and never surprises the
    person who typed an exact phrase they remember writing.
    """
    needle = query.strip().lower()
    if not needle:
        return []

    # iter_bullets yields the owner's *id*, so the readable label has to be
    # looked up. Building the map once keeps this linear.
    owners: dict[str, str] = {}
    for section in LIST_SECTIONS:
        for entry in getattr(profile, section, []):
            owners[entry.id] = entry_label(entry)

    hits: list[Hit] = []
    for section, owner_id, block in iter_bullets(profile):
        if needle in block.text.lower():
            hits.append(
                Hit(
                    section=SECTION_LABELS.get(section, section.title()),
                    owner=owners.get(owner_id, ""),
                    text=block.text,
                )
            )
    return hits


def highlight(text: str, query: str) -> str:
    """Wrap matches in a mark. Escaped, because bullets are user text."""
    safe = (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
    needle = query.strip()
    if not needle:
        return safe
    pattern = re.compile(re.escape(needle), re.IGNORECASE)
    return pattern.sub(lambda m: f"<mark>{m.group(0)}</mark>", safe)


# --------------------------------------------------------------------------
# Plain-text export
# --------------------------------------------------------------------------


def plain_text(profile: Profile) -> str:
    """The whole profile as readable text.

    Useful before the PDF pipeline exists: it is what you paste into an email,
    a text box on an application form, or a message to someone reviewing your
    material. It is deliberately not a resume layout -- it is everything,
    unabridged, in profile order.
    """
    out: list[str] = []
    b = profile.basics
    if b.name:
        out += [b.name.upper(), "=" * len(b.name)]
    contact = " | ".join(x for x in (b.email, b.phone, b.location) if x)
    if contact:
        out.append(contact)
    if getattr(b, "links", None):
        out.append(" | ".join(f"{ln.label}: {ln.url}" for ln in b.links if ln.url))
    if profile.summary.text.strip():
        out += ["", "SUMMARY", "-------", profile.summary.text.strip()]

    for key in LIST_SECTIONS:
        entries = getattr(profile, key, [])
        if not entries:
            continue
        title = SECTION_LABELS.get(key, key.title()).upper()
        out += ["", title, "-" * len(title)]
        for entry in entries:
            head = entry_label(entry)
            dates = format_range(getattr(entry, "start", None), getattr(entry, "end", None))
            out.append(f"{head}{f'  ({dates})' if dates else ''}")
            for item in getattr(entry, "items", []) or []:
                out.append(f"  {item}")
            for block in getattr(entry, "bullets", []) or []:
                if block.text.strip():
                    out.append(f"  - {block.text.strip()}")
    return "\n".join(out).strip() + "\n"


# --------------------------------------------------------------------------
# Session changes
# --------------------------------------------------------------------------


def changes(before: dict, after: dict) -> list[str]:
    """Plain sentences describing what moved between two profile snapshots.

    Compared on the serialised dicts rather than the models: a snapshot has to
    be taken at boot anyway, and dicts make the comparison total -- a field
    added to the schema later is included without touching this function.

    Entries are matched by id, so an edit reads as an edit rather than as a
    delete plus an add.
    """
    lines: list[str] = []

    if before.get("summary", {}).get("text") != after.get("summary", {}).get("text"):
        lines.append("Summary rewritten")

    if before.get("basics") != after.get("basics"):
        lines.append("Contact details changed")

    for key in LIST_SECTIONS:
        old = {e["id"]: e for e in before.get(key, []) if isinstance(e, dict)}
        new = {e["id"]: e for e in after.get(key, []) if isinstance(e, dict)}
        label = SECTION_LABELS.get(key, key.title())

        added = len(new.keys() - old.keys())
        removed = len(old.keys() - new.keys())
        edited = sum(1 for i in old.keys() & new.keys() if old[i] != new[i])

        if added:
            lines.append(f"{added} added to {label}")
        if removed:
            lines.append(f"{removed} removed from {label}")
        if edited:
            lines.append(f"{edited} edited in {label}")

    return lines
