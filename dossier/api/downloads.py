"""Getting a filename across an HTTP header intact.

``Content-Disposition`` is a header, and Starlette encodes headers as latin-1.
A cover letter named for 李明 raised ``UnicodeEncodeError`` inside the route,
which nothing caught, so **an applicant with a Chinese, Japanese, Korean,
Arabic, Hebrew or Devanagari name could not download a cover letter at all** --
they got a 500. The resume path dodged the crash by deleting the characters
instead, which is not better; see ``render.naming``.

RFC 6266 asks for both forms in one header: a plain ``filename=`` any client
can read, and ``filename*=`` carrying the real characters as percent-encoded
UTF-8. Modern browsers prefer the second; anything that does not understand it
falls back to the first and still gets something meaningful rather than
nothing.
"""

from __future__ import annotations

from urllib.parse import quote

from ..render.naming import ascii_stem


def attachment(filename: str, *, fallback: str) -> str:
    """A ``Content-Disposition`` value that survives any name inside it.

    ``fallback`` is the generic stem for this kind of document -- "Resume",
    "Cover-Letter" -- used when the real name has nothing latin-1 can carry.
    """
    stem, dot, suffix = filename.rpartition(".")
    if not dot:
        stem, suffix = filename, ""
    ext = f".{suffix}" if suffix else ""

    plain = f"{ascii_stem(stem, fallback=fallback)}{ext}"
    # Belt and braces: this half of the header has to be encodable whatever
    # was passed in, or the response raises on its way out the door.
    plain = plain.encode("ascii", "ignore").decode("ascii") or f"{fallback}{ext}"

    return f'attachment; filename="{plain}"; filename*=UTF-8\'\'{quote(filename, safe="")}'
