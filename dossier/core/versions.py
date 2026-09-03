"""What you actually sent, kept exactly as it went.

Six weeks after an application the recruiter calls, and the profile has moved
on: bullets rewritten for three jobs since, a section reordered, the type a
size smaller to save a page. The question "what did they read" had no answer.
A version answers it.

**The profile and the design, together.** A resume is both. The same facts at
92% type with tight margins is a one-page document and at 108% it is two, and
sections can be hidden by the design without touching a word of the profile.
Storing one without the other records something nobody ever sent.

**Stored as documents, inside a relational table.** The test in `db.py` runs
the other way here: nobody asks a question across the bullets of old versions,
they ask what one employer read. So the payload is JSON. The table around it
is still a table because there are many per application, they are ordered by
date, and they must go when the application goes.

**A version is read back through the profile's own migration chain**, which is
why `load` returns raw dicts rather than a `Profile`. A version saved at
schema 3 must still open at schema 5 -- otherwise the archive rots, which is
the one thing an archive may not do.

**Nothing here restores.** There is no "make this the profile again" and that
is deliberate: the master profile is everything you have done, a version is a
subset of it re-angled at one employer, and writing the second over the first
loses material that autosave would then commit to disk. The version can be
read, and it can be printed again exactly as it was.
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
class Version:
    id: str
    application_id: str
    label: str
    pages: int
    words: int
    created_at: str
    # Absent in a listing: twelve versions is twelve whole profiles, and a
    # list on screen shows a date and a page count.
    profile: dict[str, Any] | None = None
    design: dict[str, Any] | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def save_version(
    application_id: str,
    profile: dict[str, Any],
    design: dict[str, Any],
    *,
    label: str = "",
    pages: int = 0,
    words: int = 0,
    connection: sqlite3.Connection | None = None,
) -> str:
    """Store one sent document. Returns the new id."""
    conn = connection or connect()
    version_id = new_id("ver")
    conn.execute(
        """INSERT INTO versions
           (id, application_id, label, profile, design, pages, words, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            version_id,
            application_id,
            label.strip(),
            json.dumps(profile),
            json.dumps(design),
            int(pages),
            int(words),
            _now(),
        ),
    )
    return version_id


def list_versions(
    application_id: str, *, connection: sqlite3.Connection | None = None
) -> list[Version]:
    """Newest first, without the payloads."""
    conn = connection or connect()
    return [
        Version(
            id=row["id"],
            application_id=row["application_id"],
            label=row["label"],
            pages=row["pages"],
            words=row["words"],
            created_at=row["created_at"],
        )
        # rowid breaks the tie for the same reason it does in `applications`:
        # created_at is precise to the second, and two versions printed in one
        # sitting compare equal.
        for row in conn.execute(
            """SELECT * FROM versions
                WHERE application_id = ?
             ORDER BY created_at DESC, rowid DESC""",
            (application_id,),
        )
    ]


def counts(*, connection: sqlite3.Connection | None = None) -> dict[str, int]:
    """How many versions each application has, for the list to draw at once."""
    conn = connection or connect()
    return {
        row["application_id"]: row["n"]
        for row in conn.execute(
            "SELECT application_id, COUNT(*) AS n FROM versions GROUP BY application_id"
        )
    }


def load(version_id: str, *, connection: sqlite3.Connection | None = None) -> Version | None:
    """One version, payloads included, exactly as it was stored.

    The dicts come back raw. They are put through `storage.migrate` before
    validation by whoever asked for them, because a version written under an
    older profile schema has to keep opening.
    """
    conn = connection or connect()
    row = conn.execute("SELECT * FROM versions WHERE id = ?", (version_id,)).fetchone()
    if row is None:
        return None
    return Version(
        id=row["id"],
        application_id=row["application_id"],
        label=row["label"],
        pages=row["pages"],
        words=row["words"],
        created_at=row["created_at"],
        profile=json.loads(row["profile"]),
        design=json.loads(row["design"]),
    )


def delete_version(version_id: str, *, connection: sqlite3.Connection | None = None) -> None:
    conn = connection or connect()
    conn.execute("DELETE FROM versions WHERE id = ?", (version_id,))
