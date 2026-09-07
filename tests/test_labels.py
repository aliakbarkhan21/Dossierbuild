"""Section headings in the writer's own words.

Resumes do not agree on these. "Skills" is "Core Expertise" on one CV and
"Technical Proficiencies" on the next; "Honors" is "Awards" nearly everywhere
outside the US. A fixed heading meant the app quietly renamed a section its
writer had already named.
"""

from __future__ import annotations

from dossier.ai.parse import ParseResult, RawHeadings, RawResume
from dossier.core.schema import Profile
from dossier.core.sample import sample_profile
from dossier.render.design import SECTION_LABELS, Design, section_label
from dossier.render.html import render_html
from dossier.render.text import plain_text


def design(labels: dict[str, str]) -> Design:
    return Design.model_validate({"labels": labels})


def test_an_override_is_what_prints() -> None:
    assert section_label("skills", {"skills": "Core Expertise"}) == "Core Expertise"
    assert section_label("skills", {}) == SECTION_LABELS["skills"]
    assert section_label("skills") == SECTION_LABELS["skills"]


def test_a_label_equal_to_the_default_is_not_stored() -> None:
    """A design that agrees with a default should carry nothing.

    Otherwise a later change to a default never reaches the people who never
    disagreed with it.
    """
    assert design({"skills": SECTION_LABELS["skills"]}).labels == {}


def test_whitespace_is_tidied_and_length_capped() -> None:
    assert design({"summary": "  Executive   Profile  "}).labels == {"summary": "Executive Profile"}
    assert len(design({"summary": "x" * 200}).labels["summary"]) == 40


def test_an_unknown_section_is_dropped_rather_than_rejected() -> None:
    """A design written by a build with a section this one lacks still loads."""
    assert design({"nonesuch": "Whatever", "skills": "Core Expertise"}).labels == {
        "skills": "Core Expertise"
    }


def test_an_empty_label_clears_rather_than_prints_nothing() -> None:
    assert design({"skills": "   "}).labels == {}


def test_the_heading_reaches_the_rendered_document() -> None:
    html = render_html(sample_profile(), design({"skills": "Core Expertise"}))
    assert "Core Expertise" in html


def test_the_heading_reaches_the_plain_text_export() -> None:
    text = plain_text(sample_profile(), labels={"skills": "Core Expertise"})
    assert "CORE EXPERTISE" in text
    assert "\nSKILLS\n" not in text


def result(**headings: str) -> ParseResult:
    return ParseResult(
        profile=Profile.empty(), model="m", raw=RawResume(headings=RawHeadings(**headings))
    )


def test_an_import_reports_the_resume_s_own_headings() -> None:
    found = result(summary="Executive Profile", skills="Core Expertise").headings
    assert found == {"summary": "Executive Profile", "skills": "Core Expertise"}


def test_one_heading_is_adopted_by_one_section() -> None:
    """A CV routinely runs two of our sections under a single heading.

    "Education and Certifications" is one heading over two things the app
    keeps apart, and adopting it for both would print the same words twice.
    """
    found = result(
        education="Education and Certifications",
        certifications="Education and Certifications",
    ).headings
    assert found == {"education": "Education and Certifications"}


def test_blank_headings_are_left_at_their_defaults() -> None:
    assert result(summary="  ", skills="Core Expertise").headings == {"skills": "Core Expertise"}
