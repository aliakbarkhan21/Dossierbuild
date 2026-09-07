"""The copies the app keeps, and getting one back.

The rule under all of this: restoring makes a *new* CV. The recovery path is
where somebody is already having a bad day, and it must not become a second
way to lose work.
"""

from __future__ import annotations

import json

import pytest

from dossier.core import backups, cvs
from dossier.core.storage import BACKUP_DIR


def write(stem: str, payload: dict | str) -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    text = payload if isinstance(payload, str) else json.dumps(payload)
    (BACKUP_DIR / f"{stem}.json").write_text(text, encoding="utf-8")


@pytest.fixture(autouse=True)
def clean():
    if BACKUP_DIR.exists():
        for f in BACKUP_DIR.glob("*.json"):
            f.unlink()
    yield


def a_profile(name: str = "Priya Raman", bullets: int = 2) -> dict:
    return {
        "schema_version": 4,
        "basics": {"name": name, "email": "a@b.co"},
        "experience": [
            {
                "role": "Engineer",
                "organisation": "Org",
                "start": "2025-06",
                "bullets": [{"text": f"Did thing {i}."} for i in range(bullets)],
            }
        ],
    }


def test_it_reads_the_time_out_of_the_filename() -> None:
    write("abc123-20260907-142233", a_profile())
    (found,) = backups.list_backups()
    # From the name, not the mtime: a copy moved between machines keeps the
    # time it was actually taken.
    assert found.taken == "2026-09-07T14:22:33"
    assert found.cv_id == "abc123"
    assert found.name == "Priya Raman"
    assert found.entries == 1
    assert found.bullets == 2


def test_a_deleted_cv_is_flagged_as_one() -> None:
    write("deleted-cv-abc123-20260907-142233", a_profile())
    (found,) = backups.list_backups()
    assert found.deleted_cv is True
    assert found.cv_id == "abc123"


def test_newest_first() -> None:
    write("a-20260901-090000", a_profile())
    write("a-20260907-090000", a_profile())
    write("a-20260903-090000", a_profile())
    assert [b.taken[:10] for b in backups.list_backups()] == [
        "2026-09-07", "2026-09-03", "2026-09-01",
    ]


def test_a_file_that_will_not_parse_is_listed_anyway() -> None:
    """Hiding it is how somebody concludes no copy was ever kept."""
    write("a-20260907-142233", "{ this is not json")
    (found,) = backups.list_backups()
    assert found.unreadable
    assert found.name == ""


def test_files_that_are_not_backups_are_ignored() -> None:
    write("not-stamped", a_profile())
    write("a-99999999-999999", a_profile())
    assert backups.list_backups() == []


def test_restoring_makes_a_new_cv_and_leaves_the_old_one_alone() -> None:
    entries_before, active_before = cvs.list_cvs()
    kept = cvs.path_for(active_before).read_bytes() if cvs.path_for(active_before).exists() else b""

    write("a-20260907-142233", a_profile("Sam Okafor"))
    new_id = backups.restore("a-20260907-142233")

    entries_after, active_after = cvs.list_cvs()
    assert len(entries_after) == len(entries_before) + 1
    assert active_after == new_id
    assert json.loads(cvs.path_for(new_id).read_text(encoding="utf-8"))["basics"]["name"] == (
        "Sam Okafor"
    )
    if kept:
        assert cvs.path_for(active_before).read_bytes() == kept


def test_the_restored_cv_is_named_for_the_moment_it_came_from() -> None:
    write("a-20260907-142233", a_profile("Sam Okafor"))
    new_id = backups.restore("a-20260907-142233")
    name = next(cv.name for cv in cvs.list_cvs()[0] if cv.id == new_id)
    assert "Sam Okafor" in name
    assert "2026-09-07" in name


def test_the_backup_file_survives_being_restored() -> None:
    write("a-20260907-142233", a_profile())
    backups.restore("a-20260907-142233")
    assert (BACKUP_DIR / "a-20260907-142233.json").exists()


def test_an_id_that_is_a_path_is_not_an_id() -> None:
    for bad in ("", "../profile", "a/b", "a\b", ".."):
        with pytest.raises(backups.BackupError):
            backups.path_for(bad)


def test_a_missing_backup_says_so() -> None:
    with pytest.raises(backups.BackupError):
        backups.read_backup("nothing-20260907-142233")
