"""Focus tags: what each selects, and renaming one everywhere.

The counting matters more than it looks. A focus tagged on two bullets out of
forty prints a document two lines different from every other one -- it looks
tailored and is not -- and the count is the only thing that shows it.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from dossier.api import app
from dossier.core import focus as store
from dossier.core.schema import Profile

client = TestClient(app)


def profile(*bullet_tags: list[str], skill_tags: list[str] | None = None) -> Profile:
    return Profile.model_validate(
        {
            "schema_version": 4,
            "basics": {"name": "A. Student", "email": "a@b.co"},
            "experience": [
                {
                    "role": "Intern",
                    "organisation": "Northgate",
                    "start": "2025-06",
                    "bullets": [{"text": f"Did thing {i}.", "tags": t} for i, t in enumerate(bullet_tags)],
                }
            ],
            "skills": [{"label": "Languages", "items": ["Python"], "tags": skill_tags or []}],
        }
    )


def test_it_counts_what_each_focus_selects() -> None:
    report = store.coverage(profile(["backend"], ["backend", "ai"], []))
    counts = {f.tag: f.bullets for f in report.focuses}
    assert counts == {"backend": 2, "ai": 1}
    # The line carrying no tag prints under every focus, which is why a
    # thinly-tagged focus barely changes the document.
    assert report.untagged_bullets == 1


def test_a_tag_is_one_spelling_however_it_was_typed() -> None:
    report = store.coverage(profile(["#Backend"], ["backend"], ["  BACKEND "]))
    assert [f.tag for f in report.focuses] == ["backend"]
    assert report.focuses[0].bullets == 3


def test_a_cv_default_appears_even_with_nothing_tagged_yet() -> None:
    """A focus in the making is not an error."""
    report = store.coverage(profile([]), {"Research CV": "research"})
    assert [(f.tag, f.bullets, f.cvs) for f in report.focuses] == [("research", 0, ["Research CV"])]


def test_renaming_changes_every_line_in_one_pass() -> None:
    before = profile(["bakend"], ["bakend", "ai"], ["ai"])
    after, changed = store.rename(before, "bakend", "backend")
    assert changed == 2
    counts = {f.tag: f.bullets for f in store.coverage(after).focuses}
    assert counts == {"backend": 2, "ai": 2}


def test_renaming_onto_a_tag_a_line_already_has_does_not_duplicate_it() -> None:
    after, _ = store.rename(profile(["bakend", "backend"]), "bakend", "backend")
    tags = after.experience[0].bullets[0].tags
    assert tags == ["backend"]


def test_an_empty_new_name_removes_the_tag() -> None:
    after, changed = store.rename(profile(["backend"], ["backend", "ai"]), "backend", "")
    assert changed == 2
    assert {f.tag for f in store.coverage(after).focuses} == {"ai"}


def test_renaming_to_itself_changes_nothing() -> None:
    before = profile(["backend"])
    after, changed = store.rename(before, "backend", "#Backend")
    assert changed == 0
    assert after is before


def test_renaming_nothing_is_refused() -> None:
    with pytest.raises(ValueError):
        store.rename(profile(["backend"]), "  ", "x")


def test_the_route_reports_and_renames() -> None:
    client.put("/api/profile", json=profile(["bakend"], ["bakend"]).model_dump(mode="json"))
    body = client.get("/api/focus").json()
    assert {f["tag"]: f["bullets"] for f in body["focuses"]} == {"bakend": 2}

    body = client.post("/api/focus/rename", json={"old": "bakend", "new": "backend"}).json()
    assert {f["tag"]: f["bullets"] for f in body["focuses"]} == {"backend": 2}

    # And it stuck: the profile on disk was rewritten, not just the report.
    assert {f["tag"] for f in client.get("/api/focus").json()["focuses"]} == {"backend"}


def test_a_cv_default_is_set_and_follows_a_rename() -> None:
    client.put("/api/profile", json=profile(["bakend"]).model_dump(mode="json"))
    body = client.put("/api/focus/default", json={"focus": "#Bakend"}).json()
    assert body["active_focus"] == "bakend"

    # Renaming the tag must carry the default with it, or the CV would open
    # with a focus that no longer exists anywhere.
    body = client.post("/api/focus/rename", json={"old": "bakend", "new": "backend"}).json()
    assert body["active_focus"] == "backend"

    client.put("/api/focus/default", json={"focus": ""})
