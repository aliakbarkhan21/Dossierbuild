"""More than one CV in a data directory, and getting rid of one.

The registry decides everything here, so most of this tests it directly
rather than through HTTP. It gets its own data directory -- not the shared
one from conftest -- because every test in this file changes which CV is
active, and that is the one piece of state the profile tests depend on.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from dossier.api import app
from dossier.core import cvs as registry


@pytest.fixture()
def home(tmp_path, monkeypatch):
    """A data directory of our own, with a profile already in it."""
    profile = tmp_path / "profile.json"
    profile.write_text(
        json.dumps({"schema_version": 4, "basics": {"name": "Priya Raman"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(registry, "DATA_DIR", tmp_path)
    monkeypatch.setattr(registry, "CVS_DIR", tmp_path / "cvs")
    monkeypatch.setattr(registry, "INDEX_PATH", tmp_path / "cvs.json")
    monkeypatch.setattr(registry, "PROFILE_PATH", profile)
    return tmp_path


def test_the_profile_already_here_becomes_the_first_cv(home) -> None:
    entries, active = registry.list_cvs()
    assert len(entries) == 1
    assert entries[0].id == active
    # Named from the profile, and so not a name we may later replace.
    assert entries[0].name == "Priya Raman"
    assert entries[0].auto_named is False
    # Copied, not moved: a rollback must still find the profile where it was.
    assert (home / "profile.json").exists()
    assert json.loads(registry.path_for(active).read_text(encoding="utf-8"))["basics"]


def test_a_new_cv_is_blank_and_active_and_leaves_the_old_one_alone(home) -> None:
    _, first = registry.list_cvs()
    before = registry.path_for(first).read_bytes()

    made = registry.create()
    entries, active = registry.list_cvs()
    assert active == made.id
    assert {cv.id for cv in entries} == {first, made.id}
    assert registry.path_for(first).read_bytes() == before
    assert json.loads(registry.path_for(made.id).read_text(encoding="utf-8")) == {
        "schema_version": 4
    }


def test_deleting_the_open_cv_moves_it_aside_and_opens_another(home) -> None:
    _, first = registry.list_cvs()
    made = registry.create()

    now_active = registry.delete(made.id)

    assert now_active == first
    assert registry.active_path() == registry.path_for(first)
    assert not registry.path_for(made.id).exists()
    # Kept rather than unlinked: this is the one action with no undo button.
    kept = list((home / "backups").glob(f"deleted-cv-{made.id}-*.json"))
    assert len(kept) == 1
    assert json.loads(kept[0].read_text(encoding="utf-8")) == {"schema_version": 4}


def test_deleting_another_cv_does_not_move_you(home) -> None:
    _, first = registry.list_cvs()
    made = registry.create()
    registry.switch(first)

    registry.delete(made.id)

    assert registry.active_id() == first


def test_the_last_cv_cannot_be_deleted(home) -> None:
    _, only = registry.list_cvs()
    with pytest.raises(registry.CVError):
        registry.delete(only)
    assert registry.path_for(only).exists()


def test_an_id_that_is_a_path_is_not_an_id(home) -> None:
    for bad in ("", "../profile", "a/b", "a\\b", "profile.json"):
        with pytest.raises(registry.CVError):
            registry.path_for(bad)


def test_delete_over_http_returns_the_list_without_it(home) -> None:
    client = TestClient(app)
    _, first = registry.list_cvs()
    made = registry.create()

    body = client.delete(f"/api/cvs/{made.id}").json()

    assert [cv["id"] for cv in body["cvs"]] == [first]
    assert body["active"] == first
    # And the last one is refused rather than half-done.
    assert client.delete(f"/api/cvs/{first}").status_code == 400
    assert registry.path_for(first).exists()
