"""The profile as plain text.

The third output format, beside HTML and PDF. It exists because a large share
of application forms do not accept a file at all: they give you a textarea and
expect pasted content, and a PDF's text layer pasted straight out of a viewer
arrives with the columns interleaved and the bullets turned into glyphs.

Deliberately not a resume layout. It is everything in the profile, unabridged,
in profile order -- the design's section ordering and visibility are
presentation choices, and this format has no presentation. Anyone pasting into
a form wants their whole history available to trim by hand, not a document
already cut to one page.
"""

from __future__ import annotations

from ..core.schema import LIST_SECTIONS, Profile, entry_label, format_range
from .design import SECTION_LABELS


def plain_text(profile: Profile, *, date_format: str = "month") -> str:
    """The whole profile as readable text, ending in a newline.

    Takes the date style rather than a whole design: this format has no
    layout to speak of, but a date that reads one way in the PDF and another
    in the text pasted beside it is the kind of inconsistency a reader
    notices and a person cannot explain.
    """
    out: list[str] = []
    b = profile.basics

    if b.name:
        out += [b.name.upper(), "=" * len(b.name)]

    contact = " | ".join(x for x in (b.email, b.phone, b.location) if x)
    if contact:
        out.append(contact)
    if b.links:
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
            dates = format_range(
                getattr(entry, "start", None),
                getattr(entry, "end", None),
                style=date_format,
            )
            out.append(f"{head}{f'  ({dates})' if dates else ''}")
            # Skill groups carry ``items``; the narrative sections carry
            # ``bullets``. No entry has both, so the two loops never collide.
            for item in getattr(entry, "items", []) or []:
                out.append(f"  {item}")
            for block in getattr(entry, "bullets", []) or []:
                if block.text.strip():
                    out.append(f"  - {block.text.strip()}")

    return "\n".join(out).strip() + "\n"
