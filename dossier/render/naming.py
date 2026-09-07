"""Naming a document for the person who will open it.

It lands in a stranger's downloads folder next to forty others called
``resume.pdf``, so it carries the owner's name -- and a name is the one field
guaranteed to be written in whatever alphabet its owner uses.

This used to be ``[^A-Za-z0-9]`` replaced with dashes, which meant "Ünsal
Öztürk" downloaded as ``nsal-zt-rk`` and a name written in Han characters was
deleted outright, leaving a file named after a template. Unicode is kept here.
Getting it safely across an HTTP header is ``api.downloads``'s problem.
"""

from __future__ import annotations

import re
import unicodedata

#: Characters no filesystem should be asked to take, plus the two that would
#: end a quoted header string early.
_ILLEGAL = frozenset('/\\:*?"<>|\r\n\t')


def safe_stem(text: str, *, fallback: str = "") -> str:
    """A filename fragment: letters and digits in any script, joined by dashes.

    Unicode is kept. Filesystem-hostile and control characters are not. Emoji
    fall out because they are neither letters nor digits, which is the right
    answer for a filename.
    """
    kept = "".join(
        c if (c.isalnum() or c in " -_") and c not in _ILLEGAL else " " for c in text
    )
    return _joined(kept) or fallback


def ascii_stem(text: str, *, fallback: str) -> str:
    """The same name with its accents folded off, for a header that takes no more.

    NFKD splits an accented letter into a base letter and a combining mark;
    dropping the mark leaves the letter, so ``Ünsal Öztürk`` becomes
    ``Unsal-Ozturk`` -- a name someone would still recognise as theirs. A name
    with no ASCII skeleton at all returns ``fallback``, and the real
    characters travel in ``filename*`` instead.
    """
    folded = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in folded if not unicodedata.combining(c))
    kept = "".join(c if c.isascii() and (c.isalnum() or c in " -") else " " for c in stripped)
    return _joined(kept) or fallback


def _joined(text: str) -> str:
    """Words to dashes, with no run of dashes and none left dangling.

    Needed because a fold can empty a whole word: ``ascii_stem`` on
    "李明-Cover-Letter" leaves the separator behind, and a file called
    ``-Cover-Letter.pdf`` looks like a bug to the person who downloaded it.
    """
    return "-".join(part for part in re.split(r"[-\s]+", text) if part)
