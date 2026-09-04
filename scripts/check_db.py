"""Database self-check. Run with:  python scripts/check_db.py

Every check runs against a fresh in-memory or temporary database, so none of
them touch ``data/dossier.db`` and they can run in any order.

What is worth checking in a schema, as against in code:

* **The constraints are real.** A CHECK that Python also enforces is only
  useful if the database would refuse the write on its own, so the tests go
  behind the repository layer and try the bad write directly.
* **The cascades fire.** ``ON DELETE CASCADE`` does nothing unless
  ``PRAGMA foreign_keys`` is on, and it is off by default in SQLite. That is a
  one-line mistake that leaves orphaned rows accumulating silently, so it gets
  a test rather than a comment.
* **The aggregate queries answer the question asked of them.** The recurring
  gap report is the reason the terms are rows rather than a JSON blob; if it
  is wrong, the database has no purpose.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dossier.core import applications as apps
from dossier.core import db, jobspec
from dossier.core import letters as correspondence
from dossier.core import versions as archive
from dossier.core.schema import Experience, Profile, SkillGroup, TextBlock

from _harness import check, run


def fresh() -> sqlite3.Connection:
    """A migrated database with no rows, held in memory."""
    connection = sqlite3.connect(":memory:", isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    db.migrate(connection)
    return connection


def sample_profile() -> Profile:
    profile = Profile.empty()
    profile.skills = [SkillGroup(label="Languages", items=["Python"])]
    profile.experience = [
        Experience(
            id="exp_1",
            role="Data Intern",
            organisation="Acme",
            bullets=[TextBlock(id="blt_1", text="Cleaned 8,400 rows with pandas")],
        )
    ]
    return profile


def seed(connection: sqlite3.Connection) -> list[str]:
    """Three postings against one profile -- enough for a cross-posting query."""
    profile = sample_profile()
    postings = [
        ("Data Intern", "Requirements:\n- Python and pandas\n- SQL and PostgreSQL\n- Docker\n"),
        ("ML Intern", "Requirements:\n- Python, PyTorch\n- SQL\n- Docker\n"),
        ("Analyst", "Requirements:\n- SQL and Excel\n- Python\n"),
    ]
    return [
        apps.save_application(jobspec.analyse(profile, text, title=title), connection=connection)
        for title, text in postings
    ]


# --------------------------------------------------------------------------
# Schema and migration
# --------------------------------------------------------------------------


@check("migrating an empty file builds the schema and stamps the version")
def test_migrate() -> None:
    connection = fresh()
    tables = {
        row["name"]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"applications", "application_terms", "tailor_runs", "rewrites"} <= tables, tables
    assert connection.execute("PRAGMA user_version").fetchone()[0] == db.DB_VERSION


@check("migrating twice is a no-op rather than an error")
def test_migrate_idempotent() -> None:
    connection = fresh()
    assert db.migrate(connection) == db.DB_VERSION
    assert db.migrate(connection) == db.DB_VERSION


@check("every migration in the chain is reachable from an empty database")
def test_migration_chain() -> None:
    """The profile's rule, applied here: the version number has to mean
    something, so the chain must run from zero without a gap."""
    connection = sqlite3.connect(":memory:", isolation_level=None)
    connection.row_factory = sqlite3.Row
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 0
    assert db.migrate(connection) == len(db.MIGRATIONS) == db.DB_VERSION


@check("the indexes the hot queries need are actually created")
def test_indexes() -> None:
    connection = fresh()
    names = {
        row["name"]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='index'")
    }
    assert "idx_terms_term" in names, names
    assert "idx_apps_status" in names, names
    assert "idx_versions_app" in names, names
    assert "idx_letters_app" in names, names


# --------------------------------------------------------------------------
# Constraints the database enforces on its own
# --------------------------------------------------------------------------


@check("the database refuses a status nothing can render")
def test_status_check() -> None:
    connection = fresh()
    app_id = seed(connection)[0]
    try:
        connection.execute("UPDATE applications SET status = 'ghosted' WHERE id = ?", (app_id,))
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("SQLite accepted a status outside the CHECK constraint")

    # And the repository refuses it before it ever reaches SQL.
    try:
        apps.set_status(app_id, "ghosted", connection=connection)
    except ValueError:
        pass
    else:
        raise AssertionError("set_status accepted an unknown status")


@check("a term cannot be recorded twice against one application")
def test_term_primary_key() -> None:
    connection = fresh()
    app_id = seed(connection)[0]
    try:
        connection.execute(
            "INSERT INTO application_terms (application_id, term, tier, weight, covered)"
            " VALUES (?, 'python', 'required', 1.0, 0)",
            (app_id,),
        )
    except sqlite3.IntegrityError:
        return
    raise AssertionError("a duplicate term was accepted")


@check("a run cannot point at an application that does not exist")
def test_foreign_key() -> None:
    connection = fresh()
    try:
        connection.execute(
            "INSERT INTO tailor_runs (id, application_id, model, created_at)"
            " VALUES ('run_x', 'app_missing', 'test', '2026-01-01T00:00:00+00:00')"
        )
    except sqlite3.IntegrityError:
        return
    raise AssertionError("foreign keys are not being enforced -- check the PRAGMA")


@check("deleting an application takes its terms, runs and rewrites with it")
def test_cascade() -> None:
    connection = fresh()
    app_id = seed(connection)[0]
    apps.record_run(
        app_id,
        "test-model",
        [{"block_id": "blt_1", "before": "a", "after": "b", "accepted": True, "invented": []}],
        connection=connection,
    )

    def counts() -> tuple[int, int, int]:
        """Rows belonging to this application only -- the other two seeded
        applications must survive, which is half of what a cascade means."""
        return (
            connection.execute(
                "SELECT COUNT(*) FROM application_terms WHERE application_id = ?", (app_id,)
            ).fetchone()[0],
            connection.execute(
                "SELECT COUNT(*) FROM tailor_runs WHERE application_id = ?", (app_id,)
            ).fetchone()[0],
            connection.execute(
                """SELECT COUNT(*) FROM rewrites w
                     JOIN tailor_runs r ON r.id = w.run_id
                    WHERE r.application_id = ?""",
                (app_id,),
            ).fetchone()[0],
        )

    assert all(n > 0 for n in counts()), counts()
    apps.delete_application(app_id, connection=connection)
    assert counts() == (0, 0, 0), f"orphans left behind: {counts()}"
    # The siblings are untouched.
    assert connection.execute("SELECT COUNT(*) FROM applications").fetchone()[0] == 2


@check("a filed letter is editable, and goes with its application")
def test_letters() -> None:
    connection = fresh()
    app_id, other_id = seed(connection)[:2]

    first = correspondence.save_letter(
        app_id,
        {"paragraphs": ["I am applying for the backend role.", "And here is why."],
         "recipient": "Ms Okafor"},
        {"template": "classic", "fonts": "slab"},
        model="gemini-test",
        connection=connection,
    )
    elsewhere = correspondence.save_letter(other_id, {"paragraphs": ["Other."]}, {},
                                           connection=connection)

    listed = correspondence.list_letters(app_id, connection=connection)
    assert len(listed) == 1, listed
    # A listing carries the opening line, not four paragraphs each.
    assert listed[0].preview.startswith("I am applying")
    assert listed[0].document is None

    loaded = correspondence.load(first, connection=connection)
    assert loaded is not None
    assert loaded.document["recipient"] == "Ms Okafor"
    # The design travels with it: the letter is set in the resume's typeface
    # on purpose, so reprinting after a design change must not restyle it.
    assert loaded.design == {"template": "classic", "fonts": "slab"}

    # A draft is meant to be rewritten.
    assert correspondence.update_letter(first, {"paragraphs": ["Rewritten."]},
                                        connection=connection)
    assert not correspondence.update_letter("let_nope", {}, connection=connection)
    after = correspondence.load(first, connection=connection)
    assert after is not None and after.document["paragraphs"] == ["Rewritten."]
    # Editing the words is not a reason to restyle the page.
    assert after.design == {"template": "classic", "fonts": "slab"}

    assert correspondence.counts(connection=connection) == {app_id: 1, other_id: 1}

    apps.delete_application(app_id, connection=connection)
    assert correspondence.load(first, connection=connection) is None
    assert correspondence.load(elsewhere, connection=connection) is not None


@check("a kept version is readable exactly as stored, and goes with its application")
def test_versions() -> None:
    connection = fresh()
    app_id, other_id = seed(connection)[:2]

    first = archive.save_version(
        app_id,
        {"schema_version": 3, "basics": {"name": "A. Student"}},
        {"template": "classic", "scale": 92},
        label="what they read",
        pages=1,
        words=180,
        connection=connection,
    )
    archive.save_version(app_id, {"basics": {}}, {}, connection=connection)
    kept_elsewhere = archive.save_version(other_id, {"basics": {}}, {}, connection=connection)

    listed = archive.list_versions(app_id, connection=connection)
    assert len(listed) == 2, listed
    # Newest first, and the tie broken by rowid: created_at is precise to the
    # second, so two written in one loop compare equal.
    assert listed[-1].id == first
    assert listed[-1].label == "what they read"
    # A listing carries no payloads: twelve versions is twelve whole profiles.
    assert listed[0].profile is None

    loaded = archive.load(first, connection=connection)
    assert loaded is not None
    # Byte for byte what went in. A version that comes back re-shaped is not a
    # record of anything.
    assert loaded.profile == {"schema_version": 3, "basics": {"name": "A. Student"}}
    assert loaded.design == {"template": "classic", "scale": 92}
    assert loaded.pages == 1 and loaded.words == 180

    assert archive.counts(connection=connection) == {app_id: 2, other_id: 1}

    apps.delete_application(app_id, connection=connection)
    assert archive.list_versions(app_id, connection=connection) == []
    assert archive.load(first, connection=connection) is None
    # The other application's version survives, which is the half of a cascade
    # that a DELETE with no WHERE would also pass.
    assert archive.load(kept_elsewhere, connection=connection) is not None


# --------------------------------------------------------------------------
# Writing and reading
# --------------------------------------------------------------------------


@check("saving an application stores every term the posting asked for")
def test_save() -> None:
    connection = fresh()
    profile = sample_profile()
    report = jobspec.analyse(
        profile, "Requirements:\n- Python and pandas\n- SQL\n- Docker\n", title="Data Intern"
    )
    app_id = apps.save_application(report, connection=connection)

    stored = {
        row["term"]: row["covered"]
        for row in connection.execute(
            "SELECT term, covered FROM application_terms WHERE application_id = ?", (app_id,)
        )
    }
    assert set(stored) == {t.key for t in report.spec.terms}, stored
    # The profile names Python and pandas; it says nothing about Docker.
    assert stored["python"] == 1, stored
    assert stored["docker"] == 0, stored


@check("a saved application starts as a draft with no applied date")
def test_status_lifecycle() -> None:
    connection = fresh()
    app_id = seed(connection)[0]
    row = connection.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone()
    assert row["status"] == "draft" and row["applied_at"] is None, dict(row)

    apps.set_status(app_id, "applied", connection=connection)
    applied = connection.execute(
        "SELECT applied_at FROM applications WHERE id = ?", (app_id,)
    ).fetchone()["applied_at"]
    assert applied, "moving to applied should stamp a date"

    # Moving further along must not rewrite the date you applied -- a follow-up
    # is counted from that day, not from the day you heard back.
    apps.set_status(app_id, "interview", connection=connection)
    assert (
        connection.execute(
            "SELECT applied_at FROM applications WHERE id = ?", (app_id,)
        ).fetchone()["applied_at"]
        == applied
    )

    # Back to draft is a correction, and clears it.
    apps.set_status(app_id, "draft", connection=connection)
    assert (
        connection.execute(
            "SELECT applied_at FROM applications WHERE id = ?", (app_id,)
        ).fetchone()["applied_at"]
        is None
    )


@check("listing applications joins their counts without a query per row")
def test_list() -> None:
    connection = fresh()
    ids = seed(connection)
    apps.record_run(
        ids[0],
        "test-model",
        [
            {"block_id": "b1", "before": "a", "after": "b", "accepted": True, "invented": []},
            {"block_id": "b2", "before": "c", "after": "d", "accepted": False, "invented": ["AWS"]},
        ],
        connection=connection,
    )
    listed = apps.list_applications(connection=connection)
    assert len(listed) == 3, listed
    first = next(a for a in listed if a.id == ids[0])
    assert first.runs == 1 and first.accepted == 1, first
    assert "docker" in first.required_missing, first.required_missing
    # Newest first.
    assert [a.id for a in listed] == list(reversed(ids)), [a.id for a in listed]


# --------------------------------------------------------------------------
# The queries the database exists for
# --------------------------------------------------------------------------


@check("the recurring gap counts one term across every posting that asked for it")
def test_recurring_gaps() -> None:
    connection = fresh()
    seed(connection)
    gaps = {g.term: g for g in apps.recurring_gaps(connection=connection)}

    # All three postings ask for SQL and the profile evidences none of it.
    # This is the sentence the whole feature exists to produce.
    assert gaps["sql"].postings == 3, gaps["sql"]
    assert gaps["sql"].missing_in == 3, gaps["sql"]
    assert gaps["sql"].tier == "required", gaps["sql"]

    # Two postings ask for Docker.
    assert gaps["docker"].missing_in == 2, gaps["docker"]

    # Python is in every posting and the profile has it, so it is not a gap.
    assert "python" not in gaps, "a covered term was reported as missing"

    # Ordered by how often it is missing.
    ordered = apps.recurring_gaps(connection=connection)
    assert ordered == sorted(ordered, key=lambda g: -g.missing_in), ordered


@check("an empty database answers every aggregate without dividing by zero")
def test_empty_aggregates() -> None:
    connection = fresh()
    assert apps.recurring_gaps(connection=connection) == []
    assert apps.list_applications(connection=connection) == []
    assert apps.coverage_trend(connection=connection) == []
    assert apps.pipeline(connection=connection) == {s: 0 for s in apps.STATUSES}
    assert apps.guard_record(connection=connection) == {
        "suggested": 0,
        "accepted": 0,
        "flagged": 0,
        "accepted_flagged": 0,
    }


@check("the pipeline counts every status, including the ones with nothing in them")
def test_pipeline() -> None:
    connection = fresh()
    ids = seed(connection)
    apps.set_status(ids[0], "applied", connection=connection)
    apps.set_status(ids[1], "rejected", connection=connection)
    counts = apps.pipeline(connection=connection)
    assert counts == {"draft": 1, "applied": 1, "interview": 0, "offer": 0, "rejected": 1}, counts


@check("the guard record counts what the fabrication check actually caught")
def test_guard_record() -> None:
    connection = fresh()
    app_id = seed(connection)[0]
    apps.record_run(
        app_id,
        "test-model",
        [
            {"block_id": "b1", "before": "a", "after": "b", "accepted": True, "invented": []},
            {"block_id": "b2", "before": "c", "after": "d", "accepted": False, "invented": ["AWS"]},
            {"block_id": "b3", "before": "e", "after": "f", "accepted": True, "invented": ["40%"]},
        ],
        connection=connection,
    )
    record = apps.guard_record(connection=connection)
    assert record == {
        "suggested": 3,
        "accepted": 2,
        "flagged": 2,
        # The one the user accepted anyway, which is the number worth watching.
        "accepted_flagged": 1,
    }, record


@check("a rejected rewrite is kept, because a rejection is a record too")
def test_rejected_rewrites_kept() -> None:
    connection = fresh()
    app_id = seed(connection)[0]
    apps.record_run(
        app_id,
        "test-model",
        [{"block_id": "b1", "before": "a", "after": "b", "accepted": False, "invented": ["AWS"]}],
        connection=connection,
    )
    row = connection.execute("SELECT * FROM rewrites").fetchone()
    assert row["accepted"] == 0 and row["invented"] == '["AWS"]', dict(row)


@check("a failed save leaves no half-written application behind")
def test_transaction_rollback() -> None:
    connection = fresh()
    try:
        with db.transaction(connection) as tx:
            tx.execute(
                "INSERT INTO applications (id, title, created_at, updated_at)"
                " VALUES ('app_bad', 'Half', '2026-01-01', '2026-01-01')"
            )
            raise RuntimeError("something went wrong mid-save")
    except RuntimeError:
        pass
    assert connection.execute("SELECT COUNT(*) FROM applications").fetchone()[0] == 0


def main() -> int:
    return run(__name__)


if __name__ == "__main__":
    raise SystemExit(main())
