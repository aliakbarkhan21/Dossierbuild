"""Bold, italic and underline inside a line of a resume -- and nothing else.

A resume is not a document with rich text in it; it is a plain document with
the occasional emphasised number. So this is deliberately the smallest
formatting layer that does the job, and the design decision worth explaining
is the storage format.

**A stored line is still plain text.** The six substrings ``<b>``, ``</b>``,
``<i>``, ``</i>``, ``<u>`` and ``</u>`` mean formatting; every other character,
``<`` and ``&`` included, is literal and prints as itself. The alternative --
storing HTML-escaped text -- would have been marginally tidier and quietly
catastrophic: every existing profile, every AI rewrite, every import and every
LinkedIn export writes raw text into these fields, and the first ``&`` in an
employer's name would have printed as ``&amp;``. This way, a profile written
before any of this existed contains none of the six substrings and therefore
means exactly what it always meant.

The cost is one edge: somebody who genuinely wants the characters ``<b>`` on
their resume gets bold instead. On a CV that is a price worth paying.

**Nothing here ever trusts the input.** ``rich`` escapes the whole string
first and then re-permits only the allowed tags, so an unlisted tag cannot
survive by construction rather than by a filter remembering to catch it. It
also balances what it emits: an unclosed ``<b>`` inside a list item does not
stop at the item -- the HTML parser's adoption agency algorithm carries it
into everything after it, and one stray tag would embolden the rest of the
page.

In ``core`` rather than in ``render``, for the reason ``normalise_tag`` is:
what a line of prose *says* is a fact about the profile, and the writing
standard, the posting matcher and the duplicate check all want the words
without the markup long before anything is rendered. ``core`` must not import
``render``, so the module both layers need lives in the lower one.
"""

from __future__ import annotations

import re

from markupsafe import Markup, escape

#: The whole vocabulary. Bold and italic are what a resume uses; underline is
#: here because Word has trained people to expect the third button, and its
#: absence reads as a missing feature rather than as a considered omission.
ALLOWED = ("b", "i", "u")

#: Matched against the *escaped* text, so this is the only route from input to
#: markup and an unlisted tag has no way through.
_ESCAPED = re.compile(r"&lt;(/?)(%s)&gt;" % "|".join(ALLOWED))

#: Matched against raw stored text, for callers that want the words alone.
_RAW = re.compile(r"</?(%s)>" % "|".join(ALLOWED), re.IGNORECASE)


def plain(text: str) -> str:
    """The words with the formatting taken out.

    Everything that reads a line as *language* wants this: the writing
    standard counting words, the model being asked to rewrite a bullet, the
    duplicate check comparing two imports, the plain-text export. A ``<b>``
    left in is a word to a linter, a token to a model, and a difference to a
    comparison -- three wrong answers from one stray tag.
    """
    return _RAW.sub("", text or "")


def rich(text: str) -> Markup:
    """A line as safe HTML, with only the allowed tags surviving, balanced."""
    return Markup(_balance(_ESCAPED.sub(_open_tag, str(escape(text or "")))))


def _open_tag(match: re.Match[str]) -> str:
    return f"<{match.group(1)}{match.group(2)}>"


def _balance(html: str) -> str:
    """Close what was left open, and drop what was never opened.

    Both halves matter. A trailing ``<b>`` bleeds forward into the rest of the
    document; a stray ``</b>`` closes a tag that belongs to the template
    around it. Neither is something a person could diagnose from the printed
    page, which is why this is not left to the browser to sort out.
    """
    out: list[str] = []
    stack: list[str] = []
    for piece in re.split(r"(</?(?:%s)>)" % "|".join(ALLOWED), html):
        if not piece:
            continue
        opening = re.fullmatch(r"<(%s)>" % "|".join(ALLOWED), piece)
        closing = re.fullmatch(r"</(%s)>" % "|".join(ALLOWED), piece)
        if opening:
            stack.append(opening.group(1))
            out.append(piece)
        elif closing:
            name = closing.group(1)
            if name not in stack:
                continue  # never opened: dropping it is the whole repair
            # Close everything opened inside it, innermost first, so the
            # result nests properly rather than merely balancing.
            while stack:
                top = stack.pop()
                out.append(f"</{top}>")
                if top == name:
                    break
        else:
            out.append(piece)
    while stack:
        out.append(f"</{stack.pop()}>")
    return "".join(out)
