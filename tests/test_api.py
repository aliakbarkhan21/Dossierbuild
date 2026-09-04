"""The HTTP layer: does each route do the thing, and fail the way it should.

These run against a throwaway data directory (see conftest), so they really
do write profiles and really do print a PDF -- which is the point. A test that
mocks the renderer would pass on the day Chromium goes missing.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from dossier.api import app
from dossier.core.schema import SCHEMA_VERSION

client = TestClient(app)


def sample() -> dict:
    return {
        "basics": {
            "name": "A. Student",
            "headline": "Second-year Computer Science student",
            "email": "a@example.com",
            "phone": "+44 7700 900412",
            "location": "Manchester, UK",
            "links": [],
        },
        "summary": {"id": "sum_main", "text": "Ships small tools end to end."},
        "experience": [
            {
                "role": "Software Engineering Intern",
                "organisation": "Northgate Labs",
                "employment_type": "Internship",
                "start": "2025-06",
                "end": "2025-09",
                "bullets": [{"text": "Cut nightly ETL runtime from 42 to 9 minutes."}],
            }
        ],
        "skills": [{"label": "Languages", "items": ["Python", "SQL"]}],
    }


# --------------------------------------------------------------------------
# Meta
# --------------------------------------------------------------------------


def test_health_reports_what_the_app_can_actually_do() -> None:
    body = client.get("/api/health").json()
    assert body["ok"] is True
    assert body["schema_version"] == SCHEMA_VERSION
    # Whether these are true depends on the machine; that they are *answered*
    # is what makes the endpoint worth having.
    assert set(body) >= {"pdf_available", "ai_available", "data_dir"}


# --------------------------------------------------------------------------
# Profile
# --------------------------------------------------------------------------


def test_profile_round_trips_through_disk() -> None:
    saved = client.put("/api/profile", json=sample())
    assert saved.status_code == 200, saved.text
    assert saved.json()["saved"] is True

    back = client.get("/api/profile").json()
    assert back["basics"]["name"] == "A. Student"
    assert back["experience"][0]["organisation"] == "Northgate Labs"
    # Ids are minted server-side rather than trusted from the client.
    assert back["experience"][0]["id"].startswith("exp_")


def test_a_malformed_profile_is_refused_before_it_reaches_the_disk() -> None:
    broken = sample()
    broken["experience"][0]["start"] = "2025-13"  # no thirteenth month
    response = client.put("/api/profile", json=broken)
    assert response.status_code == 422

    body = response.json()
    # Names the place in the words on screen, one-based like the entry
    # headings, and states the shape wanted rather than quoting the regex.
    assert "Experience" in body["error"]
    assert "entry 1" in body["error"]
    assert "Start" in body["error"]
    assert "06/2025" in body["error"]
    assert "pattern" not in body["error"]
    assert body["fix"]


def test_a_half_typed_date_is_refused_the_same_way() -> None:
    """The exact shape autosave used to post mid-keystroke."""
    broken = sample()
    broken["experience"][0]["end"] = "2025-"
    response = client.put("/api/profile", json=broken)
    assert response.status_code == 422
    assert "End" in response.json()["error"]


def test_quality_report_agrees_with_itself() -> None:
    client.put("/api/profile", json=sample())
    body = client.get("/api/profile/quality").json()
    assert body["bullets"] == 2, body  # the summary counts as a block
    assert body["clean_bullets"] + len(
        {f["block_id"] for f in body["findings"] if f["severity"] in ("error", "warning")}
    ) == body["bullets"]
    assert body["sections_filled"]["experience"] is True
    assert body["sections_filled"]["projects"] is False


# --------------------------------------------------------------------------
# Design
# --------------------------------------------------------------------------


def test_design_round_trips_and_repairs_nonsense() -> None:
    response = client.put("/api/design", json={"template": "gothic", "accent": "navy", "scale": 400})
    assert response.status_code == 200
    body = response.json()
    assert body["template"] == "classic"  # unknown template repaired
    assert body["accent"] == "navy"
    assert body["scale"] == 112  # clamped
    assert client.get("/api/design").json()["accent"] == "navy"


def test_options_describe_everything_the_frontend_needs() -> None:
    body = client.get("/api/design/options").json()
    assert len(body["templates"]) == 8
    assert {t["key"] for t in body["templates"]} >= {"classic", "sidebar", "editorial"}
    assert any(t["photo"] for t in body["templates"])
    assert all(a["hex"].startswith("#") for a in body["accents"])
    assert len(body["looks"]) >= 5
    assert body["scale"]["steps"][0] < 100


# --------------------------------------------------------------------------
# Render
# --------------------------------------------------------------------------


def test_preview_is_html_carrying_the_person_in_the_body() -> None:
    response = client.post("/api/render/preview", json={"profile": sample()})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "A. Student" in response.text
    assert 'class="sheet"' in response.text


def test_preview_uses_the_posted_profile_not_the_saved_one() -> None:
    """The editor previews unsaved typing; this is the property that allows it."""
    client.put("/api/profile", json=sample())
    unsaved = sample()
    unsaved["basics"]["name"] = "Someone Else Entirely"
    response = client.post("/api/render/preview", json={"profile": unsaved})
    assert "Someone Else Entirely" in response.text
    assert client.get("/api/profile").json()["basics"]["name"] == "A. Student"


def test_pdf_is_a_pdf_and_says_how_many_pages_it_is() -> None:
    response = client.post("/api/render/pdf", json={"profile": sample()})
    assert response.status_code == 200, response.text
    assert response.content[:5] == b"%PDF-"
    assert int(response.headers["X-Pages"]) >= 1
    assert response.headers["X-Machine-Readable"] == "1"
    assert "A-Student-Resume" in response.headers["content-disposition"]


def test_report_answers_without_sending_the_file() -> None:
    body = client.post("/api/render/report", json={"profile": sample()}).json()
    assert body["pages"] >= 1
    assert body["machine_readable"] is True
    assert body["found"] == {"Name": True, "Email": True, "Phone": True}
    assert "experience" in body["sections"]


# --------------------------------------------------------------------------
# Ingest
# --------------------------------------------------------------------------


def test_extract_reads_a_text_file() -> None:
    files = {"file": ("cv.txt", b"Jane Doe\nEngineer\n", "text/plain")}
    body = client.post("/api/ingest/extract", files=files).json()
    assert "Jane Doe" in body["text"]
    assert body["kind"] == "text"


def test_an_unreadable_file_gets_a_sentence_and_a_fix_not_a_traceback() -> None:
    files = {"file": ("resume.xyz", b"nonsense", "application/octet-stream")}
    response = client.post("/api/ingest/extract", files=files)
    assert response.status_code == 422
    body = response.json()
    assert "Cannot read" in body["error"]
    assert body["fix"]


def test_a_plan_itemises_a_change_before_anything_changes() -> None:
    client.put("/api/profile", json=sample())
    candidate = sample()
    candidate["experience"].append(
        {
            "role": "Teaching Assistant",
            "organisation": "University of Manchester",
            "employment_type": "Part-time",
            "start": "2025-01",
            "bullets": [{"text": "Ran weekly labs for 30 first-years on CS1101."}],
        }
    )
    plan = client.post("/api/ingest/plan", json={"candidate": candidate}).json()
    labels = {c["label"]: c for c in plan["candidates"]}
    assert any("Teaching Assistant" in label for label in labels)
    assert any(c["is_duplicate"] for c in plan["candidates"]), "the existing role should be seen"

    keys = [c["key"] for c in plan["candidates"] if not c["is_duplicate"]]
    applied = client.post(
        "/api/ingest/apply", json={"candidate": candidate, "accept_candidates": keys}
    ).json()
    assert len(applied["profile"]["experience"]) == 2
    assert applied["changes"]
    # Applying does not save: the client decides when to commit.
    assert len(client.get("/api/profile").json()["experience"]) == 1


# --------------------------------------------------------------------------
# Portrait
# --------------------------------------------------------------------------


def test_portrait_upload_stores_the_file_and_points_the_profile_at_it() -> None:
    from io import BytesIO

    from PIL import Image

    client.put("/api/profile", json=sample())
    buffer = BytesIO()
    Image.new("RGB", (900, 1200), "#8899AA").save(buffer, format="PNG")

    files = {"file": ("me.png", buffer.getvalue(), "image/png")}
    body = client.post("/api/profile/photo", files=files).json()
    assert body["photo"] == "photo.jpg"
    assert client.get("/api/profile").json()["basics"]["photo"] == "photo.jpg"

    # And a template with a place for one now carries it.
    html = client.post(
        "/api/render/preview",
        json={"profile": client.get("/api/profile").json(), "design": {"template": "sidebar"}},
    ).text
    assert "data:image/jpeg;base64," in html

    assert client.delete("/api/profile/photo").json()["photo"] == ""
    assert client.get("/api/profile").json()["basics"]["photo"] == ""


@pytest.mark.parametrize("payload", [b"", b"not an image at all"])
def test_a_bad_portrait_is_refused_politely(payload: bytes) -> None:
    files = {"file": ("me.png", payload, "image/png")}
    response = client.post("/api/profile/photo", files=files)
    assert response.status_code == 400
    assert response.json()["fix"]


# --------------------------------------------------------------------------
# Plain text
# --------------------------------------------------------------------------


def test_plain_text_carries_the_whole_profile() -> None:
    """The format that exists for application forms with no file upload."""
    client.put("/api/profile", json=sample())
    response = client.post("/api/render/text", json={})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert ".txt" in response.headers["content-disposition"]

    body = response.text
    assert "A. STUDENT" in body
    assert "a@example.com" in body
    # Unabridged on purpose: a section the design happens to hide is still
    # material the person may want to paste.
    assert "Cut nightly ETL runtime from 42 to 9 minutes." in body
    assert "Northgate Labs" in body


# --------------------------------------------------------------------------
# Applications
# --------------------------------------------------------------------------


POSTING = """
Backend Engineer, Northgate Labs

Requirements:
- Strong Python
- Docker and Kubernetes in production
- Experience with PostgreSQL

Nice to have:
- Go
"""

SECOND_POSTING = """
Platform Engineer, Ridgeway

Requirements:
- Python service development
- Docker, and Kubernetes for orchestration
- Terraform
"""


def _save(text: str, company: str) -> str:
    response = client.post(
        "/api/applications",
        json={"text": text, "company": company, "profile": sample()},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _clear() -> None:
    """These tests share one database with every other test in the session."""
    for application in client.get("/api/applications").json()["applications"]:
        client.delete(f"/api/applications/{application['id']}")


def test_a_saved_posting_keeps_its_requirements_as_rows() -> None:
    _clear()
    app_id = _save(POSTING, "Northgate Labs")

    body = client.get("/api/applications").json()
    saved = next(a for a in body["applications"] if a["id"] == app_id)
    assert saved["status"] == "draft"
    assert saved["applied_at"] is None
    assert 0 <= saved["coverage"] <= 100
    # The profile in `sample()` has Python and SQL and nothing else, so the
    # container stack is the gap -- and it is the *stated* requirements that
    # come back, not every word in the advert.
    assert "docker" in saved["required_missing"]
    _clear()


def test_the_same_gap_in_two_postings_is_what_recurring_gaps_counts() -> None:
    """The query the database exists for, over HTTP.

    One posting missing Docker says the job was not a match; two say the
    profile is. Nothing else in the app can tell those apart, because nothing
    else looks at more than one posting at a time.
    """
    _clear()
    _save(POSTING, "Northgate Labs")
    _save(SECOND_POSTING, "Ridgeway")

    gaps = {g["term"]: g for g in client.get("/api/applications").json()["gaps"]}
    assert gaps["docker"]["postings"] == 2
    assert gaps["docker"]["missing_in"] == 2
    assert gaps["docker"]["tier"] == "required"
    # Named by one posting only: it must not outrank the one named by both.
    assert gaps["terraform"]["postings"] == 1
    _clear()


def test_status_stamps_the_date_you_applied_and_does_not_move_it() -> None:
    _clear()
    app_id = _save(POSTING, "Northgate Labs")

    assert client.put(f"/api/applications/{app_id}/status", json={"status": "applied"}).status_code == 200
    applied_at = _one(app_id)["applied_at"]
    assert applied_at

    client.put(f"/api/applications/{app_id}/status", json={"status": "interview"})
    after = _one(app_id)
    assert after["status"] == "interview"
    # A follow-up is counted from the day you applied, not the day you
    # progressed, so moving on must not rewrite it.
    assert after["applied_at"] == applied_at

    assert client.put(
        f"/api/applications/{app_id}/status", json={"status": "hired"}
    ).status_code == 422
    _clear()


def test_a_recorded_run_counts_towards_the_guard_record() -> None:
    _clear()
    app_id = _save(POSTING, "Northgate Labs")
    response = client.post(
        f"/api/applications/{app_id}/runs",
        json={
            "model": "gemini-test",
            "suggestions": [
                {"block_id": "b1", "before": "Cut ETL runtime.", "after": "Cut ETL runtime by 78%.",
                 "accepted": False, "invented": ["78%"]},
                {"block_id": "b2", "before": "Built a tracker.", "after": "Built a CSV tracker.",
                 "accepted": True, "invented": []},
            ],
        },
    )
    assert response.status_code == 200

    body = client.get("/api/applications").json()
    assert body["guard"] == {
        "suggested": 2,
        "accepted": 1,
        "flagged": 1,
        # The number that matters: a flagged rewrite that was kept anyway.
        "accepted_flagged": 0,
    }
    assert _one(app_id)["runs"] == 1
    assert _one(app_id)["accepted"] == 1
    _clear()


def test_deleting_an_application_takes_its_runs_with_it() -> None:
    _clear()
    app_id = _save(POSTING, "Northgate Labs")
    client.post(
        f"/api/applications/{app_id}/runs",
        json={"model": "m", "suggestions": [{"block_id": "b", "accepted": True, "invented": []}]},
    )
    assert client.delete(f"/api/applications/{app_id}").status_code == 200

    body = client.get("/api/applications").json()
    assert all(a["id"] != app_id for a in body["applications"])
    # Decorative ON DELETE CASCADE is the failure this guards: the rows would
    # survive their application and go on counting.
    assert body["guard"]["suggested"] == 0
    assert client.delete(f"/api/applications/{app_id}").status_code == 404


def test_a_version_keeps_the_document_while_the_profile_moves_on() -> None:
    """The whole point of the archive, in one test.

    A version is printed, the profile is then edited, and the version prints
    again -- with the old wording. If this ever fails the archive is not an
    archive, it is a second view of the current profile.
    """
    _clear()
    app_id = _save(POSTING, "Northgate Labs")

    sent = sample()
    sent["experience"][0]["bullets"] = [{"text": "Cut nightly ETL runtime from 42 to 9 minutes."}]
    kept = client.post(
        f"/api/applications/{app_id}/versions",
        json={"label": "What Northgate read", "profile": sent},
    )
    assert kept.status_code == 200, kept.text
    version_id = kept.json()["id"]
    # Printed here rather than taken on trust from the client: the record has
    # to say what came out of the printer.
    assert kept.json()["pages"] >= 1
    assert kept.json()["words"] > 0

    moved_on = sample()
    moved_on["experience"][0]["bullets"] = [{"text": "Rewrote the whole thing for another job."}]
    assert client.put("/api/profile", json=moved_on).status_code == 200

    body = client.get(f"/api/versions/{version_id}").json()
    assert body["label"] == "What Northgate read"
    assert body["profile"]["experience"][0]["bullets"][0]["text"].startswith("Cut nightly ETL")
    # And the design travelled with it: a resume is both, and the same facts
    # at a different size are a different number of pages.
    assert body["design"]["page"]

    printed = client.post(f"/api/versions/{version_id}/pdf")
    assert printed.status_code == 200
    assert printed.content[:5] == b"%PDF-"
    assert printed.headers["content-disposition"].startswith("attachment")

    listing = client.get(f"/api/applications/{app_id}/versions").json()
    assert [v["id"] for v in listing] == [version_id]
    assert _one(app_id)["versions"] == 1
    _clear()


def test_a_version_goes_when_its_application_does() -> None:
    _clear()
    app_id = _save(POSTING, "Northgate Labs")
    version_id = client.post(
        f"/api/applications/{app_id}/versions", json={"profile": sample()}
    ).json()["id"]

    client.delete(f"/api/applications/{app_id}")
    # Without PRAGMA foreign_keys the row would outlive its application and go
    # on being listed against an id nothing else knows about.
    assert client.get(f"/api/versions/{version_id}").status_code == 404
    assert client.post(f"/api/versions/{version_id}/pdf").status_code == 404


def test_versions_are_newest_first_and_deletable_one_at_a_time() -> None:
    _clear()
    app_id = _save(POSTING, "Northgate Labs")
    first = client.post(
        f"/api/applications/{app_id}/versions", json={"label": "first", "profile": sample()}
    ).json()["id"]
    second = client.post(
        f"/api/applications/{app_id}/versions", json={"label": "second", "profile": sample()}
    ).json()["id"]

    listing = client.get(f"/api/applications/{app_id}/versions").json()
    # created_at is precise to the second, so two printed in one sitting
    # compare equal -- rowid is what makes this order real rather than lucky.
    assert [v["label"] for v in listing] == ["second", "first"]

    assert client.delete(f"/api/versions/{second}").status_code == 200
    assert client.delete(f"/api/versions/{second}").status_code == 404
    assert [v["id"] for v in client.get(f"/api/applications/{app_id}/versions").json()] == [first]
    _clear()


def test_a_version_of_an_older_schema_still_opens() -> None:
    """An archive that stops reading its own contents is not an archive.

    The stored dict goes back through `storage.migrate`, so a profile written
    before the current schema version opens rather than failing validation.
    """
    import json as _json
    import sqlite3

    from dossier.core.db import connect
    from dossier.core.schema import SCHEMA_VERSION

    _clear()
    app_id = _save(POSTING, "Northgate Labs")
    version_id = client.post(
        f"/api/applications/{app_id}/versions", json={"profile": sample()}
    ).json()["id"]

    # Rewrite the payload as a version-1 document. The stamp is what makes
    # this test real: validating a v1 dict directly returns schema_version 1,
    # so a 3 coming back is proof the chain ran and not a model default.
    ancient = sample()
    ancient["schema_version"] = 1
    connection: sqlite3.Connection = connect()
    connection.execute(
        "UPDATE versions SET profile = ? WHERE id = ?", (_json.dumps(ancient), version_id)
    )
    connection.close()

    body = client.get(f"/api/versions/{version_id}")
    assert body.status_code == 200, body.text
    assert body.json()["profile"]["schema_version"] == SCHEMA_VERSION
    _clear()


def test_an_empty_posting_is_refused_with_a_sentence() -> None:
    response = client.post("/api/applications", json={"text": "   "})
    assert response.status_code == 422
    assert "posting" in response.json()["detail"].lower()


def _one(app_id: str) -> dict:
    body = client.get("/api/applications").json()
    return next(a for a in body["applications"] if a["id"] == app_id)


def test_the_interview_brief_maps_evidence_and_names_the_gaps() -> None:
    """Built from rules over the stored posting. No model, no network."""
    _clear()
    app_id = _save(POSTING, "Northgate Labs")
    # The profile on disk is what the brief reads, because the interview is
    # weeks after the application and what matters is what you can evidence
    # today, not what you could when you applied.
    evidenced = sample()
    evidenced["experience"][0]["bullets"] = [
        {"text": "Cut nightly ETL runtime from 42 to 9 minutes by batching PostgreSQL writes."}
    ]
    client.put("/api/profile", json=evidenced)

    brief = client.get(f"/api/applications/{app_id}/brief")
    assert brief.status_code == 200, brief.text
    body = brief.json()

    terms = {s["term"].lower() for s in body["strengths"]}
    gaps = {g["term"].lower() for g in body["gaps"]}
    assert "postgresql" in terms, terms
    assert "docker" in gaps, gaps
    assert not (terms & gaps), "a requirement cannot be both answered and missing"
    # Python is in the skills list and in no bullet. That is a weak claim, not
    # a gap: telling someone who lists Python that they have not used it is
    # false, and the sort of thing that loses an interview.
    assert "python" not in gaps
    assert any("python" in d.lower() for d in body["declared_only"]), body["declared_only"]

    strength = next(s for s in body["strengths"] if s["term"].lower() == "postgresql")
    assert strength["evidence"], "an answered requirement has to say where"
    assert strength["prompts"], "and what they will ask about it"

    gap = next(g for g in body["gaps"] if g["term"].lower() == "docker")
    assert gap["evidence"] == []
    assert len(gap["prompts"]) >= 2
    # A gap is not a reason not to apply: the sheet says what to say.
    assert "not" in gap["bridge"].lower()

    assert client.get("/api/applications/no_such_id/brief").status_code == 404
    _clear()


def test_the_brief_stays_one_sheet() -> None:
    """A brief nobody finishes reading is worse than a shorter one."""
    from dossier.core.interview import GAPS_SHOWN, TOP_REQUIREMENTS

    _clear()
    extra = "\n".join(f"- Requirement number {n} in {n}" for n in range(60))
    wordy = POSTING + extra
    app_id = _save(wordy, "Northgate Labs")
    body = client.get(f"/api/applications/{app_id}/brief").json()
    assert len(body["strengths"]) <= TOP_REQUIREMENTS
    assert len(body["gaps"]) <= GAPS_SHOWN
    _clear()


def test_notes_are_editable_and_come_back_on_the_brief() -> None:
    _clear()
    app_id = _save(POSTING, "Northgate Labs")
    assert client.put(
        f"/api/applications/{app_id}/notes", json={"notes": "Ask about on-call."}
    ).status_code == 200

    assert client.get(f"/api/applications/{app_id}/brief").json()["notes"] == "Ask about on-call."
    assert _one(app_id)["notes"] == "Ask about on-call."
    assert client.put(
        "/api/applications/no_such_id/notes", json={"notes": "x"}
    ).status_code == 404
    _clear()


# --------------------------------------------------------------------------
# Cover letters
# --------------------------------------------------------------------------


HAND_WRITTEN = {
    "paragraphs": [
        "I am applying for the backend engineer role at Northgate Labs.",
        "At Northgate Labs I cut a nightly ETL run from 42 minutes to 9.",
        "I would bring the same to your data platform.",
    ],
    "recipient": "Ms Okafor",
    "company": "Northgate Labs",
    "role": "Backend Engineer",
}


def test_a_letter_prints_without_a_model_anywhere_near_it() -> None:
    """The whole letter pipeline works with no API key.

    Drafting needs a model; writing one by hand and printing it does not, and
    a person who does not want a model writing their letter should still get
    the paper, the typeface and the PDF.
    """
    printed = client.post(
        "/api/letter/pdf", json={"letter": HAND_WRITTEN, "profile": sample()}
    )
    assert printed.status_code == 200, printed.text
    assert printed.content[:5] == b"%PDF-"
    # Named for the reader, like the resume is.
    assert "Northgate-Labs" in printed.headers["content-disposition"]

    html = client.post(
        "/api/letter/preview", json={"letter": HAND_WRITTEN, "profile": sample()}
    )
    assert html.status_code == 200
    body = html.text
    # The parts a model is never asked for, because there is no judgement in
    # them: a named recipient takes "Yours sincerely".
    assert "Dear Ms Okafor," in body
    assert "Yours sincerely," in body
    assert "A. Student" in body
    assert "cut a nightly ETL run from 42 minutes to 9" in body


def test_an_unnamed_reader_gets_yours_faithfully() -> None:
    """British convention, and the sort of thing a letter-reader notices."""
    anonymous = {**HAND_WRITTEN, "recipient": ""}
    body = client.post(
        "/api/letter/preview", json={"letter": anonymous, "profile": sample()}
    ).text
    assert "Dear Hiring Manager," in body
    assert "Yours faithfully," in body
    assert "Yours sincerely," not in body


def test_an_empty_letter_is_refused_rather_than_printed_blank() -> None:
    empty = {**HAND_WRITTEN, "paragraphs": ["", "   "]}
    response = client.post("/api/letter/pdf", json={"letter": empty, "profile": sample()})
    assert response.status_code == 422
    assert "no words" in response.json()["detail"]


def test_a_letter_is_set_in_the_resumes_typeface() -> None:
    """Not a cosmetic choice: two documents an employer opens on the same
    afternoon should look like one person sent them."""
    body = client.post(
        "/api/letter/preview",
        json={
            "letter": HAND_WRITTEN,
            "profile": sample(),
            "design": {"fonts": "slab", "accent": "burgundy"},
        },
    ).text
    assert "Roboto Slab" in body
    assert "#6E2436" in body


def test_a_letter_is_filed_edited_reprinted_and_forgotten() -> None:
    _clear()
    app_id = _save(POSTING, "Northgate Labs")

    kept = client.post(
        f"/api/applications/{app_id}/letters",
        json={"letter": HAND_WRITTEN, "profile": sample(), "model": "gemini-test"},
    )
    assert kept.status_code == 200, kept.text
    letter_id = kept.json()["id"]
    # The listing says which letter this is without carrying four paragraphs.
    assert kept.json()["preview"].startswith("I am applying")
    assert _one(app_id)["letters"] == 1

    read = client.get(f"/api/letter/{letter_id}").json()
    assert read["letter"]["recipient"] == "Ms Okafor"
    assert read["design"]["template"]

    # A draft is meant to be rewritten; the archive keeps the edit, not the
    # model's first attempt.
    edited = {**HAND_WRITTEN, "paragraphs": ["Rewritten by hand, entirely."]}
    assert client.put(
        f"/api/letter/{letter_id}", json={"letter": edited, "profile": sample()}
    ).status_code == 200
    again = client.get(f"/api/letter/{letter_id}").json()
    assert again["letter"]["paragraphs"] == ["Rewritten by hand, entirely."]

    reprinted = client.post(f"/api/letter/{letter_id}/pdf")
    assert reprinted.status_code == 200
    assert reprinted.content[:5] == b"%PDF-"

    assert client.delete(f"/api/letter/{letter_id}").status_code == 200
    assert client.get(f"/api/letter/{letter_id}").status_code == 404
    assert _one(app_id)["letters"] == 0
    _clear()


def test_a_letter_goes_when_its_application_does() -> None:
    _clear()
    app_id = _save(POSTING, "Northgate Labs")
    letter_id = client.post(
        f"/api/applications/{app_id}/letters",
        json={"letter": HAND_WRITTEN, "profile": sample()},
    ).json()["id"]

    client.delete(f"/api/applications/{app_id}")
    # Without PRAGMA foreign_keys the row would outlive its application.
    assert client.get(f"/api/letter/{letter_id}").status_code == 404


def test_drafting_without_a_posting_says_so() -> None:
    response = client.post("/api/letter/draft", json={"text": "   "})
    assert response.status_code == 422
    assert "posting" in response.json()["detail"].lower()


# --------------------------------------------------------------------------
# Serving the built frontend
# --------------------------------------------------------------------------


def test_an_unknown_api_path_stays_json() -> None:
    """The SPA catch-all must not answer a missing endpoint with HTML.

    Returning the shell would surface in the frontend as a JSON parse error
    pointing at '<', which says nothing about the real mistake.
    """
    response = client.get("/api/no-such-thing")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")


def test_a_client_route_serves_the_app_when_it_is_built() -> None:
    """A reload on /resume is a GET for a path with no file behind it."""
    from dossier.api import static

    if not static.build_present():
        pytest.skip("web/dist not built; nothing to serve")

    response = client.get("/resume")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<div id=\"root\"" in response.text
