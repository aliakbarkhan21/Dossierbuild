"""The SQLite database: connection, pragmas, and its own migration chain.

**What is in here and what is not.** The master profile stays in
``profile.json``. It is one hand-typed document with a "never lose it"
invariant, it is read whole and written whole, and there is exactly one of
them -- spreading it over eight tables would buy joins to rebuild a single
Pydantic object, and a second place for schema migrations to go wrong.

What *is* here is the part that is actually relational: many applications,
each with the terms its posting asked for, each with tailoring runs, each run
with the rewrites it produced. That shape has rows, foreign keys and questions
worth asking across all of it -- "which required skill do I keep failing to
evidence" is a ``GROUP BY``, not a file.

**No ORM.** ``sqlite3`` is in the standard library, so this adds nothing to
``requirements.txt``, and the queries in ``applications.py`` are the point of
having a database at all -- an ORM would hide them behind configuration.

**Pragmas that matter**, both set on every connection because SQLite defaults
them off or to the wrong thing for this app:

* ``foreign_keys=ON`` -- off by default, for backwards compatibility with
  SQLite 3.6. Without it the ``REFERENCES`` clauses below are documentation,
  and deleting an application would leave its runs behind forever.
* ``journal_mode=WAL`` -- a reader no longer blocks a writer, which matters
  because the app renders a PDF (slow, and holds a read) while autosave may be
  writing. It is a persistent property of the file, but setting it is cheap
  and makes the requirement explicit rather than assumed.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Callable, Iterator

from .storage import DATA_DIR

DB_PATH = DATA_DIR / "dossier.db"

# Mirrors ``storage.SCHEMA_VERSION`` in spirit: the database has its own
# version and its own chain, because the two evolve for different reasons.
DB_VERSION = 3


def connect(path: Path | None = None) -> sqlite3.Connection:
    """Open the database, applying the pragmas and any pending migrations."""
    target = path or DB_PATH
    target.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(target, isolation_level=None)
    # Rows come back addressable by column name. Without this every query
    # result is a positional tuple, and adding a column silently shifts the
    # meaning of every index after it.
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    migrate(connection)
    return connection


# --------------------------------------------------------------------------
# Migrations
# --------------------------------------------------------------------------


# Same rule as the profile's: a schema change ships with a migration, even one
# a fresh database would not need. ``user_version`` is a SQLite built-in -- an
# integer in the file header, so the version cannot drift from the file the way
# a row in a table can be deleted.
#
# Each migration is a tuple of whole statements rather than one script. The
# obvious call, ``executescript``, issues an implicit COMMIT before it runs,
# which ends the migration's own transaction and makes the COMMIT afterwards
# fail. Splitting a script on ";" instead looks fine and is not: one of the
# comments below contains a semicolon, which cut a statement in half and
# produced a syntax error pointing at an English word. Statements are listed
# separately so nothing has to parse SQL to find their boundaries.

_V1_SCHEMA: tuple[str, ...] = (
    """
    CREATE TABLE applications (
        id          TEXT PRIMARY KEY,
        title       TEXT NOT NULL DEFAULT '',
        company     TEXT NOT NULL DEFAULT '',
        posting     TEXT NOT NULL DEFAULT '',
        source_url  TEXT NOT NULL DEFAULT '',
        -- Constrained here and not only in Python: the database is the last
        -- thing between a typo and a status that nothing on screen renders.
        status      TEXT NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft','applied','interview','offer','rejected')),
        coverage    INTEGER NOT NULL DEFAULT 0 CHECK (coverage BETWEEN 0 AND 100),
        notes       TEXT NOT NULL DEFAULT '',
        created_at  TEXT NOT NULL,
        updated_at  TEXT NOT NULL,
        applied_at  TEXT
    )
    """,
    # One row per term the posting asked for. A JSON blob could be displayed
    # but not counted across postings, and counting across postings is the
    # only reason any of this is in a database.
    """
    CREATE TABLE application_terms (
        application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
        term           TEXT NOT NULL,
        tier           TEXT NOT NULL CHECK (tier IN ('required','preferred','general')),
        weight         REAL NOT NULL DEFAULT 0,
        covered        INTEGER NOT NULL DEFAULT 0 CHECK (covered IN (0,1)),
        PRIMARY KEY (application_id, term)
    )
    """,
    """
    CREATE TABLE tailor_runs (
        id             TEXT PRIMARY KEY,
        application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
        model          TEXT NOT NULL DEFAULT '',
        created_at     TEXT NOT NULL
    )
    """,
    # Rejected rewrites are kept. A rejection is a judgement worth a record,
    # and the flagged ones are the only evidence of whether the fabrication
    # guard catches anything real.
    """
    CREATE TABLE rewrites (
        id              TEXT PRIMARY KEY,
        run_id          TEXT NOT NULL REFERENCES tailor_runs(id) ON DELETE CASCADE,
        block_id        TEXT NOT NULL,
        entry_label     TEXT NOT NULL DEFAULT '',
        before_text     TEXT NOT NULL DEFAULT '',
        after_text      TEXT NOT NULL DEFAULT '',
        accepted        INTEGER NOT NULL DEFAULT 0 CHECK (accepted IN (0,1)),
        invented        TEXT NOT NULL DEFAULT '[]',
        findings_before INTEGER NOT NULL DEFAULT 0,
        findings_after  INTEGER NOT NULL DEFAULT 0
    )
    """,
    # The first covers the recurring-gap GROUP BY, the second the pipeline
    # count. Both tables are small today and both queries run on a page load.
    "CREATE INDEX idx_terms_term     ON application_terms(term, covered)",
    "CREATE INDEX idx_apps_status    ON applications(status)",
    "CREATE INDEX idx_runs_app       ON tailor_runs(application_id)",
    "CREATE INDEX idx_rewrites_run   ON rewrites(run_id)",
    "CREATE INDEX idx_rewrites_block ON rewrites(block_id)",
)


# What was actually sent, kept whole.
#
# The two columns holding a profile and a design are JSON documents, not rows,
# and that is the same test applied the other way round: nobody asks a
# question *across* the bullets of old versions -- they ask "what did
# Northgate read". A version is one document with one reader, so it is stored
# as one document. The table around it is relational because there are many
# per application and they have to go when it does.
#
# Storing the design beside the profile is the point. A resume is the two
# together: the same facts at 92% type with the margins tight is a one-page
# document and at 108% it is two, and "the PDF they read" is meaningless
# without both.
_V2_SCHEMA: tuple[str, ...] = (
    """
    CREATE TABLE versions (
        id             TEXT PRIMARY KEY,
        application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
        label          TEXT NOT NULL DEFAULT '',
        profile        TEXT NOT NULL,
        design         TEXT NOT NULL,
        -- Measured from the PDF that was actually printed, not guessed from
        -- the markup, so the record says what came out of the printer.
        pages          INTEGER NOT NULL DEFAULT 0,
        words          INTEGER NOT NULL DEFAULT 0,
        created_at     TEXT NOT NULL
    )
    """,
    "CREATE INDEX idx_versions_app ON versions(application_id, created_at)",
)


def _v0_to_v1(connection: sqlite3.Connection) -> None:
    """The first schema: applications, what they asked for, and what we did."""
    for statement in _V1_SCHEMA:
        connection.execute(statement)


# A cover letter, kept the same way a version is: the letter itself as a JSON
# document, the design beside it so it reprints exactly, and the row relational
# because there are many per application and they must go when it does.
#
# The design is stored for the same reason it is stored with a version, and it
# matters more here: the letter is *set* in the resume's typeface on purpose,
# so a letter reprinted after the resume's design changed would come back in a
# face the employer never saw.
_V3_SCHEMA: tuple[str, ...] = (
    """
    CREATE TABLE letters (
        id             TEXT PRIMARY KEY,
        application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
        document       TEXT NOT NULL,
        design         TEXT NOT NULL,
        -- "" when the letter was written by hand rather than drafted.
        model          TEXT NOT NULL DEFAULT '',
        created_at     TEXT NOT NULL
    )
    """,
    "CREATE INDEX idx_letters_app ON letters(application_id, created_at)",
)


def _v1_to_v2(connection: sqlite3.Connection) -> None:
    """Versions: the exact document that went to one employer, on one date."""
    for statement in _V2_SCHEMA:
        connection.execute(statement)


def _v2_to_v3(connection: sqlite3.Connection) -> None:
    """Cover letters, filed against the application they were written for."""
    for statement in _V3_SCHEMA:
        connection.execute(statement)


MIGRATIONS: tuple[Callable[[sqlite3.Connection], None], ...] = (
    _v0_to_v1,
    _v1_to_v2,
    _v2_to_v3,
)


def migrate(connection: sqlite3.Connection) -> int:
    """Bring the file up to ``DB_VERSION``. Returns the version it ended at.

    Each step runs in a transaction of its own, so a migration that fails
    leaves the database at the last version that worked rather than half way
    through a new one.
    """
    current = connection.execute("PRAGMA user_version").fetchone()[0]
    for version in range(current, len(MIGRATIONS)):
        connection.execute("BEGIN")
        try:
            MIGRATIONS[version](connection)
            # PRAGMA does not accept a bound parameter, and this value is a
            # loop index over a module-level tuple, not user input.
            connection.execute(f"PRAGMA user_version = {version + 1}")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        connection.execute("COMMIT")
    return connection.execute("PRAGMA user_version").fetchone()[0]


def transaction(connection: sqlite3.Connection) -> "_Transaction":
    """A write that lands completely or not at all.

    Saving an application writes to three tables. Without this, a failure part
    way through would leave an application with half its terms -- and the
    recurring-gap count would be quietly wrong rather than visibly broken.
    """
    return _Transaction(connection)


class _Transaction:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def __enter__(self) -> sqlite3.Connection:
        self.connection.execute("BEGIN")
        return self.connection

    def __exit__(self, exc_type: object, *_: object) -> None:
        self.connection.execute("ROLLBACK" if exc_type else "COMMIT")


def rows(connection: sqlite3.Connection, sql: str, *params: object) -> Iterator[sqlite3.Row]:
    yield from connection.execute(sql, params)
