"""Cover letters, filed against the application they were written for.

The same shape as `versions.py`, for the same reasons: the letter is one
document with one reader, so it is stored as JSON, and the table around it is
relational because there are many per application, they are ordered by date,
and they must go when the application goes.

The design is stored beside it. That matters more for a letter than for a
resume version, because the letter is deliberately set in the resume's
typeface — a letter reprinted after the design changed would come back in a
face the employer never saw, which defeats the point of matching them.

Nothing here calls a model. `ai/letter.py` drafts; this keeps.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .db import connect
from .ids import new_id


@dataclass
class StoredLetter:
    id: str
    application_id: str
    model: str
    created_at: str
    # Absent in a listing, present in a load -- a list on screen shows a date
    # and the first line, not four paragraphs each.
    document: dict[str, Any] | None = None
    design: dict[str, Any] | None = None
    preview: str = ""
    """The opening words, for a list that has to say which letter this is."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _opening(document: dict[str, Any]) -> str:
    """The first thing the reader sees, trimmed to a line."""
    paragraphs = document.get("paragraphs") or []
    first = paragraphs[0] if paragraphs else ""
    return first[:120]


def save_letter(
    application_id: str,
    document: dict[str, Any],
    design: dict[str, Any],
    *,
    model: str = "",
    connection: sqlite3.Connection | None = None,
) -> str:
    conn = connection or connect()
    letter_id = new_id("let")
    conn.execute(
        """INSERT INTO letters (id, application_id, document, design, model, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (letter_id, application_id, json.dumps(document), json.dumps(design), model, _now()),
    )
    return letter_id


def update_letter(
    letter_id: str,
    document: dict[str, Any],
    *,
    connection: sqlite3.Connection | None = None,
) -> bool:
    """Save an edit. Returns False if there is no such letter.

    A drafted letter is a draft: the whole point is that it gets rewritten
    before it is sent, and an archive of the model's first attempt is not what
    anyone wants to keep. The design is left alone -- editing the words is not
    a reason to restyle the page.
    """
    conn = connection or connect()
    cursor = conn.execute(
        "UPDATE letters SET document = ? WHERE id = ?", (json.dumps(document), letter_id)
    )
    return cursor.rowcount > 0


def list_letters(
    application_id: str, *, connection: sqlite3.Connection | None = None
) -> list[StoredLetter]:
    """Newest first, with the opening line but not the whole letter."""
    conn = connection or connect()
    return [
        StoredLetter(
            id=row["id"],
            application_id=row["application_id"],
            model=row["model"],
            created_at=row["created_at"],
            preview=_opening(json.loads(row["document"])),
        )
        # rowid breaks the tie: created_at is precise to the second, and two
        # drafts made in one sitting compare equal.
        for row in conn.execute(
            """SELECT * FROM letters
                WHERE application_id = ?
             ORDER BY created_at DESC, rowid DESC""",
            (application_id,),
        )
    ]


def counts(*, connection: sqlite3.Connection | None = None) -> dict[str, int]:
    """How many letters each application has, for the list to draw at once."""
    conn = connection or connect()
    return {
        row["application_id"]: row["n"]
        for row in conn.execute(
            "SELECT application_id, COUNT(*) AS n FROM letters GROUP BY application_id"
        )
    }


def load(letter_id: str, *, connection: sqlite3.Connection | None = None) -> StoredLetter | None:
    conn = connection or connect()
    row = conn.execute("SELECT * FROM letters WHERE id = ?", (letter_id,)).fetchone()
    if row is None:
        return None
    document = json.loads(row["document"])
    return StoredLetter(
        id=row["id"],
        application_id=row["application_id"],
        model=row["model"],
        created_at=row["created_at"],
        document=document,
        design=json.loads(row["design"]),
        preview=_opening(document),
    )


def delete_letter(letter_id: str, *, connection: sqlite3.Connection | None = None) -> None:
    conn = connection or connect()
    conn.execute("DELETE FROM letters WHERE id = ?", (letter_id,))
