"""Applications: saving one, and asking questions across all of them.

This is the module the database exists for. Reading one posting's gap is
something a JSON file could do; asking *which requirement I keep failing to
evidence, across every job I have gone for* is a ``GROUP BY``, and that
question is the useful one -- a gap that shows up once is a job you were not
quite right for, and a gap that shows up in nine is the next thing to learn.

Nothing here calls a model. An application is saved from an analysis that
``core/jobspec.py`` already produced by rules, so the history is reproducible
and does not silently change meaning when a model does.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .db import connect, transaction
from .ids import new_id
from .jobspec import MatchReport

STATUSES: tuple[str, ...] = ("draft", "applied", "interview", "offer", "rejected")


def _now() -> str:
    """UTC, ISO 8601, to the second.

    Stored as text because SQLite has no date type, and in UTC because a
    resume built on a laptop that crosses a timezone should not reorder its
    own history.
    """
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Application:
    id: str
    title: str
    company: str
    status: str
    coverage: int
    created_at: str
    updated_at: str
    applied_at: str | None = None
    notes: str = ""
    source_url: str = ""
    posting: str = ""
    required_missing: list[str] = field(default_factory=list)
    runs: int = 0
    accepted: int = 0


@dataclass
class Gap:
    """One term, counted across every application that asked for it."""

    term: str
    tier: str
    postings: int
    """How many applications named it."""
    missing_in: int
    """How many of those your profile did not evidence."""
    weight: float


# --------------------------------------------------------------------------
# Writing
# --------------------------------------------------------------------------


def save_application(
    report: MatchReport,
    *,
    connection: sqlite3.Connection | None = None,
    source_url: str = "",
    notes: str = "",
) -> str:
    """Store a posting and the gap analysis of it. Returns the new id.

    The terms go in as rows rather than as a JSON blob on the application,
    which is the whole reason this is a database: a blob can be displayed, but
    only rows can be counted across postings.
    """
    conn = connection or connect()
    app_id = new_id("app")
    stamp = _now()

    covered = set(report.covered)
    with transaction(conn) as tx:
        tx.execute(
            """INSERT INTO applications
               (id, title, company, posting, source_url, status, coverage,
                notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?)""",
            (
                app_id,
                report.spec.title,
                report.spec.company,
                report.spec.text,
                source_url,
                report.coverage,
                notes,
                stamp,
                stamp,
            ),
        )
        tx.executemany(
            """INSERT INTO application_terms
               (application_id, term, tier, weight, covered)
               VALUES (?, ?, ?, ?, ?)""",
            [
                (app_id, term.key, term.tier, term.weight, 1 if term.key in covered else 0)
                for term in report.spec.terms
            ],
        )
    return app_id


def record_run(
    application_id: str,
    model: str,
    suggestions: list[dict],
    *,
    connection: sqlite3.Connection | None = None,
) -> str:
    """Store one tailoring pass and every rewrite it proposed.

    Rejected rewrites are kept. A rejection is a judgement worth having a
    record of, and the flagged ones are the only evidence of whether the
    fabrication guard is catching anything real.
    """
    conn = connection or connect()
    run_id = new_id("run")

    with transaction(conn) as tx:
        tx.execute(
            "INSERT INTO tailor_runs (id, application_id, model, created_at) VALUES (?, ?, ?, ?)",
            (run_id, application_id, model, _now()),
        )
        tx.executemany(
            """INSERT INTO rewrites
               (id, run_id, block_id, entry_label, before_text, after_text,
                accepted, invented, findings_before, findings_after)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    new_id("rw"),
                    run_id,
                    s.get("block_id", ""),
                    s.get("entry_label", ""),
                    s.get("before", ""),
                    s.get("after", ""),
                    1 if s.get("accepted") else 0,
                    json.dumps(s.get("invented", [])),
                    int(s.get("findings_before", 0)),
                    int(s.get("findings_after", 0)),
                )
                for s in suggestions
            ],
        )
        tx.execute(
            "UPDATE applications SET updated_at = ? WHERE id = ?", (_now(), application_id)
        )
    return run_id


def set_status(
    application_id: str, status: str, *, connection: sqlite3.Connection | None = None
) -> None:
    if status not in STATUSES:
        raise ValueError(f"{status!r} is not one of {', '.join(STATUSES)}")
    conn = connection or connect()
    # Stamped the first time it reaches "applied" and not overwritten after:
    # the date you applied is the one a follow-up is counted from, and moving
    # to "interview" three weeks later should not erase it.
    conn.execute(
        """UPDATE applications
              SET status = ?,
                  updated_at = ?,
                  applied_at = CASE
                      WHEN ? = 'draft' THEN NULL
                      WHEN applied_at IS NULL THEN ?
                      ELSE applied_at
                  END
            WHERE id = ?""",
        (status, _now(), status, _now(), application_id),
    )


def delete_application(
    application_id: str, *, connection: sqlite3.Connection | None = None
) -> None:
    """Terms, runs and rewrites go with it -- see the ON DELETE CASCADE."""
    conn = connection or connect()
    conn.execute("DELETE FROM applications WHERE id = ?", (application_id,))


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------


def list_applications(*, connection: sqlite3.Connection | None = None) -> list[Application]:
    """Every application, newest first, with its counts already joined on.

    Aggregated in SQL rather than by looping in Python: the alternative is one
    query per application for its runs and another for its missing terms,
    which is the N+1 that makes people think databases are slow.
    """
    conn = connection or connect()
    query = """
        SELECT a.*,
               (SELECT COUNT(*) FROM tailor_runs r
                 WHERE r.application_id = a.id)                         AS runs,
               (SELECT COUNT(*) FROM rewrites w
                  JOIN tailor_runs r ON r.id = w.run_id
                 WHERE r.application_id = a.id AND w.accepted = 1)       AS accepted,
               (SELECT GROUP_CONCAT(t.term, ', ') FROM application_terms t
                 WHERE t.application_id = a.id
                   AND t.covered = 0
                   AND t.tier = 'required')                             AS gaps
          FROM applications a
        -- rowid breaks the tie. created_at is only precise to the second, so
        -- three applications saved from one sitting compare equal and SQLite
        -- is free to return them in any order -- which it does, differently
        -- on different runs. rowid rises with insertion, so this is "newest
        -- first" even when the clock cannot tell them apart.
      ORDER BY a.created_at DESC, a.rowid DESC
    """
    return [
        Application(
            id=row["id"],
            title=row["title"],
            company=row["company"],
            status=row["status"],
            coverage=row["coverage"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            applied_at=row["applied_at"],
            notes=row["notes"],
            source_url=row["source_url"],
            required_missing=[t for t in (row["gaps"] or "").split(", ") if t],
            runs=row["runs"],
            accepted=row["accepted"],
        )
        for row in conn.execute(query)
    ]


def recurring_gaps(
    *, limit: int = 12, connection: sqlite3.Connection | None = None
) -> list[Gap]:
    """The requirements you keep not evidencing, across every application.

    The query the database is here for. A term missing from one posting says
    little; the same term missing from most of the jobs you want is the single
    most useful sentence this app can produce -- and it cannot be computed from
    one posting, which is exactly why the terms are rows.

    Ordered by how often it is missing, then by weight, so a stated requirement
    outranks a passing mention that happens to recur.
    """
    conn = connection or connect()
    query = """
        SELECT term,
               COUNT(*)                                   AS postings,
               SUM(CASE WHEN covered = 0 THEN 1 ELSE 0 END) AS missing_in,
               AVG(weight)                                AS weight,
               -- The strongest way any posting asked for it. A term that is
               -- required anywhere is a required term.
               MIN(CASE tier WHEN 'required' THEN 1 WHEN 'preferred' THEN 2 ELSE 3 END) AS rank
          FROM application_terms
      GROUP BY term
        HAVING missing_in > 0
      ORDER BY missing_in DESC, rank ASC, weight DESC
         LIMIT ?
    """
    tiers = {1: "required", 2: "preferred", 3: "general"}
    return [
        Gap(
            term=row["term"],
            tier=tiers[row["rank"]],
            postings=row["postings"],
            missing_in=row["missing_in"],
            weight=round(row["weight"], 2),
        )
        for row in conn.execute(query, (limit,))
    ]


def pipeline(*, connection: sqlite3.Connection | None = None) -> dict[str, int]:
    """How many applications sit at each status, including the empty ones."""
    conn = connection or connect()
    counts = {status: 0 for status in STATUSES}
    for row in conn.execute("SELECT status, COUNT(*) AS n FROM applications GROUP BY status"):
        counts[row["status"]] = row["n"]
    return counts


def coverage_trend(*, connection: sqlite3.Connection | None = None) -> list[tuple[str, int]]:
    """``(created_at, coverage)`` oldest first -- is the profile catching up?"""
    conn = connection or connect()
    return [
        (row["created_at"], row["coverage"])
        for row in conn.execute(
            "SELECT created_at, coverage FROM applications ORDER BY created_at ASC"
        )
    ]


def guard_record(*, connection: sqlite3.Connection | None = None) -> dict[str, int]:
    """What the fabrication guard has actually caught, over every run.

    Kept because a check nobody measures is a check nobody can defend. If
    ``flagged`` stays at zero over dozens of rewrites, the audit is either
    working perfectly or not working at all, and this is the number that
    starts that conversation.
    """
    conn = connection or connect()
    row = conn.execute(
        """SELECT COUNT(*)                                                AS suggested,
                  SUM(CASE WHEN accepted = 1 THEN 1 ELSE 0 END)           AS accepted,
                  SUM(CASE WHEN invented != '[]' THEN 1 ELSE 0 END)       AS flagged,
                  SUM(CASE WHEN invented != '[]' AND accepted = 1
                           THEN 1 ELSE 0 END)                             AS accepted_flagged
             FROM rewrites"""
    ).fetchone()
    return {key: row[key] or 0 for key in ("suggested", "accepted", "flagged", "accepted_flagged")}
