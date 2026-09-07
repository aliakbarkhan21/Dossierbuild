"""Downloading a document whose owner is not called A. Student.

Every fixture in the rest of the suite has an ASCII name, which is how a
cover letter named for 李明 reached production returning HTTP 500: the name
went into a ``Content-Disposition`` header, Starlette encodes headers as
latin-1, and nothing caught the ``UnicodeEncodeError``. The resume path
avoided the crash by deleting the characters, so "Ünsal Öztürk" arrived as
``nsal-zt-rk``.

These are cheap tests for a defect class that is invisible until someone who
is not you uses the app.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from dossier.api import app
from dossier.api.downloads import attachment
from dossier.render.naming import ascii_stem, safe_stem

client = TestClient(app)

HAN = "李明"                      # 李明
ARABIC = "محمد"       # محمد
TURKISH = "Ünsal Öztürk"   # Ünsal Öztürk


# --------------------------------------------------------------------------
# Naming
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "given, expected",
    [
        ("A. Student", "A-Student"),
        (TURKISH, "Ünsal-Öztürk"),   # kept, not stripped
        (HAN, HAN),
        ("Priya  Raman ", "Priya-Raman"),
        ("Ada/Lovelace", "Ada-Lovelace"),           # a path separator is not a name
        ('He said "hi"', "He-said-hi"),             # nor is a quote that ends the header
        # Emoji are not letters, so they separate rather than survive.
        ("Priya \U0001f389 Raman", "Priya-Raman"),
        ("Jo\U0001f600e", "Jo-e"),
        ("", ""),
    ],
)
def test_safe_stem_keeps_the_alphabet_and_drops_the_hazards(given, expected) -> None:
    assert safe_stem(given) == expected


@pytest.mark.parametrize(
    "given, expected",
    [
        (TURKISH, "Unsal-Ozturk"),   # folded, so the name is still recognisable
        ("Renée", "Renee"),
        ("A. Student", "A-Student"),
        (HAN, "Resume"),             # nothing to fold: the fallback stands in
        (ARABIC, "Resume"),
    ],
)
def test_ascii_stem_folds_rather_than_deletes(given, expected) -> None:
    assert ascii_stem(given, fallback="Resume") == expected


# --------------------------------------------------------------------------
# The header
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", [HAN, ARABIC, TURKISH, "A. Student", "\U0001f600"])
def test_the_header_always_survives_latin_1(name) -> None:
    """The encoding Starlette will actually do, done here first."""
    header = attachment(f"{name}-Resume.pdf", fallback="Resume")
    header.encode("latin-1")


def test_the_header_carries_the_real_name_as_well_as_a_readable_one() -> None:
    header = attachment(f"{HAN}-Cover-Letter.pdf", fallback="Cover-Letter")
    # The plain half is readable and has no dash left dangling where the name
    # folded away to nothing.
    assert 'filename="Cover-Letter.pdf"' in header
    # The real characters travel percent-encoded, per RFC 6266.
    assert "filename*=UTF-8''%E6%9D%8E%E6%98%8E-Cover-Letter.pdf" in header


def test_an_accented_name_stays_legible_in_both_halves() -> None:
    header = attachment(f"{safe_stem(TURKISH)}-Resume.pdf", fallback="Resume")
    assert 'filename="Unsal-Ozturk-Resume.pdf"' in header
    assert "%C3%9Cnsal-%C3%96zt%C3%BCrk" in header


# --------------------------------------------------------------------------
# End to end: the route that used to return 500
# --------------------------------------------------------------------------


def profile_named(name: str) -> dict:
    return {
        "basics": {
            "name": name,
            "headline": "Backend engineer",
            "email": "a@example.com",
            "phone": "+44 7700 900412",
            "location": "Manchester, UK",
            "links": [],
        },
        "experience": [
            {
                "role": "Software Engineer",
                "organisation": "Northgate Labs",
                "employment_type": "Full-time",
                "start": "2025-06",
                "bullets": [{"text": "Cut nightly ETL runtime from 42 to 9 minutes."}],
            }
        ],
    }


@pytest.mark.parametrize("name", [HAN, ARABIC, TURKISH])
def test_a_resume_downloads_whatever_the_applicant_is_called(name) -> None:
    response = client.post("/api/render/pdf", json={"profile": profile_named(name)})
    assert response.status_code == 200
    assert response.content[:4] == b"%PDF"
    disposition = response.headers["content-disposition"]
    assert "filename*=UTF-8''" in disposition
    # And the name is in there, rather than deleted on the way out.
    assert "Resume" in disposition


@pytest.mark.parametrize("name", [HAN, TURKISH])
def test_the_plain_text_export_too(name) -> None:
    response = client.post("/api/render/text", json={"profile": profile_named(name)})
    assert response.status_code == 200
    assert "filename*=UTF-8''" in response.headers["content-disposition"]
