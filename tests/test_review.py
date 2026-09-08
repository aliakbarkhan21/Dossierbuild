"""The Review screen: what it says about a document, and about a line in it.

Two complaints drove this. The findings were "the same for everyone" -- every
one of them a general rule about writing, none of them about *this* resume.
And some were simply wrong: a 1,017-character summary was told that "over
about 200 this will wrap badly", which is a bullet's rule read out over a
paragraph.
"""

from __future__ import annotations

from dossier.core.quality import LENGTH, check_document, check_text
from dossier.core.sample import sample_profile
from dossier.core.schema import Basics, CustomSection, Profile, TextBlock


def messages(findings) -> str:
    return " | ".join(f.message for f in findings)


# --------------------------------------------------------------------------
# A line is judged as the kind of line it is
# --------------------------------------------------------------------------


def test_a_summary_is_not_measured_by_a_bullet_s_length() -> None:
    """The reported bug, in one assertion.

    A summary is a paragraph. Telling it that 200 characters is the limit is
    advice for a different kind of writing, and following it would leave a
    summary of two lines.
    """
    summary = "Executive with two decades in national digital government. " * 6
    assert 200 < len(summary) < LENGTH["summary"][1]
    assert "wrap badly" not in messages(check_text(summary, kind="summary"))
    assert "characters" not in messages(check_text(summary, kind="summary"))


def test_a_summary_that_really_is_too_long_is_still_flagged() -> None:
    text = "Executive with two decades in national digital government. " * 20
    said = messages(check_text(text, kind="summary"))
    assert "long for a summary" in said


def test_a_bullet_over_its_own_limit_is_flagged() -> None:
    said = messages(check_text("Cut the runtime. " * 20, kind="bullet"))
    assert "before it wraps" in said


def test_a_full_stop_is_a_note_on_a_bullet_and_nothing_on_prose() -> None:
    """The note said "bullets read cleaner without" while firing on a summary,
    which announced its own mistake. A paragraph ends with a full stop."""
    assert "full stop" in messages(check_text("Built the ingest service.", kind="bullet"))
    assert "full stop" not in messages(check_text("Built the ingest service.", kind="summary"))
    assert "full stop" not in messages(check_text("Built the ingest service.", kind="prose"))


def test_the_opening_verb_rule_is_a_bullet_rule() -> None:
    """A bullet is expected to open on a result. A paragraph is not.

    "Used" rather than "helped with": the latter is caught as filler first,
    and would have proved nothing about the rule under test.
    """
    line = "Used Postgres across the reporting stack"
    assert "weak opening verb" in messages(check_text(line, kind="bullet"))
    assert "weak opening verb" not in messages(check_text(line, kind="summary"))


def test_is_summary_still_means_what_it_meant() -> None:
    """Every caller that passed it meant `kind="summary"`."""
    text = "Executive with two decades in national digital government. " * 6
    assert check_text(text, is_summary=True) == check_text(text, kind="summary")


# --------------------------------------------------------------------------
# The document, as against the writing in it
# --------------------------------------------------------------------------


def test_a_sound_profile_produces_no_document_findings() -> None:
    """The half that makes the other half worth reading: these must be silent
    on a resume that does not have the problem, or they are noise."""
    assert check_document(sample_profile()) == []


def test_a_resume_nobody_can_reply_to() -> None:
    profile = sample_profile()
    profile.basics = Basics(name="Priya Raman")
    said = messages(check_document(profile))
    assert "no email address" in said
    assert "no phone number" in said


def test_a_job_that_ends_before_it_starts() -> None:
    profile = sample_profile()
    profile.experience[0].start = "2024-06"
    profile.experience[0].end = "2023-01"
    said = messages(check_document(profile))
    assert "ends Jan 2023 but starts Jun 2024" in said


def test_a_date_written_in_words_is_not_mistaken_for_a_bad_one() -> None:
    """"Summer 2024" cannot be compared, and must not be reported as broken."""
    profile = sample_profile()
    profile.experience[0].start = "Summer 2024"
    profile.experience[0].end = "Ongoing"
    assert "ends" not in messages(check_document(profile))


def test_the_same_bullet_pasted_twice() -> None:
    profile = sample_profile()
    profile.experience[0].bullets.append(
        TextBlock(text=profile.experience[0].bullets[0].text)
    )
    assert "the same line appears twice" in messages(check_document(profile))


def test_a_heading_with_nothing_under_it() -> None:
    """It does not print at all, and nothing else would have said so."""
    profile = sample_profile()
    profile.sections = [CustomSection(title="Referees")]
    said = messages(check_document(profile))
    assert "a heading with nothing under it" in said


def test_an_entry_with_no_dates_at_all() -> None:
    profile = sample_profile()
    profile.experience[0].start = None
    profile.experience[0].end = None
    assert "no dates" in messages(check_document(profile))


def test_findings_name_the_place_they_are_about() -> None:
    """There is no block to jump to, so the place has to be in the finding."""
    profile = sample_profile()
    profile.experience[1].start = "2024-06"
    profile.experience[1].end = "2020-01"
    where = [f.where for f in check_document(profile) if "ends" in f.message]
    assert where == ["Experience, entry 2"]


def test_an_empty_profile_does_not_bury_the_reader() -> None:
    """The first run. Enough to be useful, not a wall."""
    found = check_document(Profile.empty())
    assert 2 <= len(found) <= 6, messages(found)
    assert "no name" in messages(found)


def test_the_document_findings_reach_the_api() -> None:
    from fastapi.testclient import TestClient

    from dossier.api.app import app

    with TestClient(app) as client:
        profile = sample_profile()
        profile.basics.email = ""
        assert client.put("/api/profile", json=profile.model_dump(mode="json")).status_code == 200
        body = client.get("/api/profile/quality").json()
        assert any("no email address" in f["message"] for f in body["document"])
        assert all(f["where"] for f in body["document"])
