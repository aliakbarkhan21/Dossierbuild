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
    assert "start" in response.text


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
