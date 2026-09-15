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
from dossier.render import design


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
    # Duplicating copies the design too, and the design module keeps its own
    # idea of where the designs live. Without this the copies would land in the
    # shared sandbox from conftest instead of in this directory.
    monkeypatch.setattr(design, "DESIGNS_DIR", tmp_path / "designs")
    monkeypatch.setattr(design, "LEGACY_DESIGN_PATH", tmp_path / "design.json")
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


def test_a_duplicate_carries_the_content_the_focus_and_the_look(home) -> None:
    """All three, because a CV is all three.

    The design is the one that would be missed quietly: a copy that came back
    on the default template looks like the feature worked until you print it.
    """
    _, first = registry.list_cvs()
    registry.set_focus(first, "research")
    registry.path_for(first).write_text(
        json.dumps({"schema_version": 4, "basics": {"name": "Priya Raman"}}),
        encoding="utf-8",
    )
    design.save_design(design.Design(fonts="slab", template="modern"), design.design_path(first))

    copy = registry.duplicate(first)

    assert registry.path_for(copy.id).read_bytes() == registry.path_for(first).read_bytes()
    assert copy.focus == "research"
    carried = design.load_design(design.design_path(copy.id))
    assert (carried.fonts, carried.template) == ("slab", "modern")


def test_a_duplicate_never_takes_the_profile_s_name(home) -> None:
    """The line the whole feature rests on.

    A work CV and an education CV are the same person, so both profiles carry
    the same name. If the copy were auto-named, the next autosave would rename
    it to that name and the switcher would show two rows reading "Priya Raman".
    """
    _, first = registry.list_cvs()
    copy = registry.duplicate(first)
    assert copy.auto_named is False

    registry.adopt_profile_name("Priya Raman", copy.id)

    entries, _ = registry.list_cvs()
    named = next(cv for cv in entries if cv.id == copy.id)
    assert named.name == "Priya Raman (copy)"


def test_duplicating_twice_gives_two_names_you_can_tell_apart(home) -> None:
    _, first = registry.list_cvs()
    assert registry.duplicate(first).name == "Priya Raman (copy)"
    assert registry.duplicate(first).name == "Priya Raman (copy 2)"

    # And a name already at the route's limit is trimmed at the stem, so the
    # suffix survives and the suggestion is still something the route accepts.
    long = registry.rename(first, "R" * registry.NAME_MAX)
    suggested = registry.duplicate(long.id).name
    assert len(suggested) <= registry.NAME_MAX
    assert suggested.endswith(" (copy)")


def test_a_duplicate_leaves_the_original_alone_and_opens_the_copy(home) -> None:
    _, first = registry.list_cvs()
    before = registry.path_for(first).read_bytes()

    copy = registry.duplicate(first, "Education CV")

    assert copy.name == "Education CV"
    assert registry.active_id() == copy.id
    assert registry.path_for(first).read_bytes() == before
    assert {cv.id for cv in registry.list_cvs()[0]} == {first, copy.id}


def test_duplicating_a_cv_that_is_not_here_is_refused(home) -> None:
    registry.list_cvs()  # the index is written on first read, not on setup
    before = registry.INDEX_PATH.read_text(encoding="utf-8")
    made = sorted(registry.CVS_DIR.iterdir())

    with pytest.raises(registry.CVError):
        registry.duplicate("0123456789ab")

    assert registry.INDEX_PATH.read_text(encoding="utf-8") == before
    assert sorted(registry.CVS_DIR.iterdir()) == made


def test_duplicate_over_http_returns_the_list_with_the_copy_active(home) -> None:
    client = TestClient(app)
    _, first = registry.list_cvs()

    response = client.post(f"/api/cvs/{first}/duplicate", json={"name": "Work CV"})

    assert response.status_code == 201
    body = response.json()
    assert len(body["cvs"]) == 2
    copy = next(cv for cv in body["cvs"] if cv["id"] != first)
    assert body["active"] == copy["id"]
    assert copy["name"] == "Work CV"
    assert copy["auto_named"] is False
    # An id that names nothing is a statement about the path, like `activate`.
    assert client.post("/api/cvs/0123456789ab/duplicate").status_code == 404
