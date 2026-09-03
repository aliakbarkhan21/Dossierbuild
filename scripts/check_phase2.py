"""Phase 2 self-check. Run with:  python scripts/check_phase2.py

Covers the render pipeline: design validation, the profile -> template
context, the HTML both modes produce, and -- if Chromium is installed -- a
real PDF, its page count and its text layer.

The last group is the one that matters most. A resume PDF that looks perfect
and contains no readable text is the failure nobody notices until an
application has already been rejected, so it is checked here rather than
trusted.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dossierbuild.render.context import build_context, display_url, normalise_url, suggested_filename
from dossierbuild.render.design import ACCENTS, PAIRINGS, TEMPLATES, Design, load_design, save_design
from dossierbuild.render.html import render_html, render_thumbnail
from dossierbuild.render.pdf import chromium_ready, pdf_report, render_pdf
from dossierbuild.schema import Basics, Education, Experience, Link, Profile, Project, SkillGroup, TextBlock

PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str):
    def decorator(fn):
        try:
            fn()
        except AssertionError as exc:
            FAILED.append(f"{name}\n      {exc}")
        except Exception as exc:  # noqa: BLE001
            FAILED.append(f"{name}\n      unexpected {type(exc).__name__}: {exc}")
        else:
            PASSED.append(name)
        return fn

    return decorator


def sample() -> Profile:
    return Profile(
        basics=Basics(
            name="A. Student",
            headline="Second-year Computer Science & AI student",
            email="a@example.com",
            phone="+44 7700 900412",
            location="Manchester, UK",
            links=[Link(label="github.com/astudent", url="github.com/astudent")],
        ),
        summary=TextBlock(id="sum_main", text="Ships small tools end to end."),
        experience=[
            Experience(
                role="Software Engineering Intern",
                organisation="Northgate Labs",
                employment_type="Internship",
                start="2025-06",
                end="2025-09",
                bullets=[TextBlock(text="Cut nightly ETL runtime from 42 to 9 minutes.")],
            )
        ],
        projects=[
            Project(
                name="Loot Ledger",
                tagline="Finance tracker",
                tech=["Python", "Streamlit"],
                start="2025-01",
                bullets=[TextBlock(text="Reconciles 2,400 transactions across 6 CSV formats.")],
            )
        ],
        education=[
            Education(
                institution="University of Manchester",
                credential="BSc Computer Science",
                start="2024-09",
                end="2027-06",
                grade="Predicted First (79%)",
                coursework=["Algorithms"],
            )
        ],
        skills=[SkillGroup(label="Languages", items=["Python", "SQL"])],
    )


# --------------------------------------------------------------------------
# Design
# --------------------------------------------------------------------------


@check("a nonsense design repairs itself instead of raising")
def _() -> None:
    d = Design.model_validate(
        {"template": "gothic", "page": "a3", "accent": "chartreuse", "scale": 400,
         "fonts": "comic", "order": ["skills", "skills", "nonsense"]}
    )
    assert d.template in TEMPLATES, d.template
    assert d.page == "a4" and d.accent == "ink" and d.fonts in PAIRINGS
    assert d.scale == 112, d.scale
    # Deduplicated, unknown keys dropped, missing ones appended.
    assert d.order[0] == "skills" and len(set(d.order)) == len(d.order)
    assert set(d.order) == {"summary", "experience", "projects", "education",
                            "skills", "certifications", "awards"}


@check("moving and hiding sections produce new designs, not mutations")
def _() -> None:
    d = Design()
    moved = d.with_moved("experience", -1)
    assert d.order[0] == "summary", "the original was mutated"
    assert moved.order[0] == "experience", moved.order
    hidden = moved.with_toggled("awards")
    assert "awards" in hidden.hidden and "awards" not in hidden.visible_sections()
    assert hidden.with_toggled("awards").hidden == [], "toggle is not reversible"


@check("a missing or corrupt design file falls back to defaults")
def _() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        missing = Path(tmp) / "nope.json"
        assert load_design(missing) == Design()
        broken = Path(tmp) / "broken.json"
        broken.write_text("{not json", encoding="utf-8")
        assert load_design(broken) == Design()
        good = Path(tmp) / "good.json"
        save_design(Design(template="modern", accent="navy"), good)
        assert load_design(good).template == "modern"


# --------------------------------------------------------------------------
# Context
# --------------------------------------------------------------------------


@check("a URL without a scheme becomes a link a browser will follow")
def _() -> None:
    assert normalise_url("linkedin.com/in/x") == "https://linkedin.com/in/x"
    assert normalise_url("https://a.com") == "https://a.com"
    assert normalise_url("") == ""
    assert display_url("https://www.github.com/x/") == "github.com/x"


@check("empty sections never reach the page")
def _() -> None:
    context = build_context(sample(), Design())
    keys = [s.key for s in context.sections]
    assert "certifications" not in keys and "awards" not in keys, keys
    assert keys[0] == "summary", keys


@check("hiding a section removes it; reordering moves it")
def _() -> None:
    design = Design().with_toggled("projects").with_moved("skills", -6)
    keys = [s.key for s in build_context(sample(), design).sections]
    assert "projects" not in keys, keys
    assert keys[0] == "skills", keys


@check("a grade containing brackets is not wrapped in more brackets")
def _() -> None:
    context = build_context(sample(), Design())
    education = context.get("education")
    entry = education.entries[0]
    assert entry.detail == "Predicted First (79%)", entry.detail
    assert "((" not in render_html(sample(), Design())


@check("the download is named for the reader, not for us")
def _() -> None:
    name = suggested_filename(sample(), Design(template="modern"))
    assert name == "A-Student-Resume-Modern.pdf", name


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------


@check("every template renders, and none of them lose the name")
def _() -> None:
    profile = sample()
    for key in TEMPLATES:
        html = render_html(profile, Design(template=key))
        assert "A. Student" in html, key
        assert "Northgate Labs" in html, key
        assert "<style>" in html and "</html>" in html, key


@check("profile text is escaped, not interpreted")
def _() -> None:
    profile = sample()
    profile.experience[0].bullets[0].text = 'Broke <script>alert("x")</script> nothing'
    html = render_html(profile, Design())
    assert "<script>alert" not in html, "user text reached the document as markup"
    assert "&lt;script&gt;" in html


@check("print mode carries no preview furniture, and preview mode does")
def _() -> None:
    profile = sample()
    printed = render_html(profile, Design())
    preview = render_html(profile, Design(), preview=True)
    assert "pagebreak" not in printed and "fitbar" not in printed
    assert "class=\"sheet\"" in printed, "the sheet wrapper is shared by both"
    assert "pagebreak" in preview and "fit-left" in preview
    # The one property the whole preview claim rests on.
    assert "flex: none" in preview, "the sheet could shrink and break lines early"


@check("every accent and every pairing reaches the stylesheet")
def _() -> None:
    profile = sample()
    for key, (_name, value) in ACCENTS.items():
        assert value in render_html(profile, Design(accent=key)), key
    for key, pairing in PAIRINGS.items():
        html = render_html(profile, Design(fonts=key))
        # The stylesheet must carry the stack *unescaped*: CSS does not decode
        # HTML entities, so an escaped quote silently disables the font.
        assert pairing.body in html, f"{key}: font stack was escaped"
        # The stylesheet link is an HTML attribute, where & is correctly &amp;.
        assert pairing.google.replace("&", "&amp;") in html, key


@check("a thumbnail is a real render, without the page furniture")
def _() -> None:
    html = render_thumbnail(sample(), Design(), "compact", 0.0)
    assert "A. Student" in html
    # The script that draws them is still there; what must be absent is the
    # furniture itself.
    assert '<div class="fitbar">' not in html
    assert "breaks = false" in html.replace("var breaks = ", "breaks = ")


# --------------------------------------------------------------------------
# PDF -- skipped, loudly, if Chromium is not installed
# --------------------------------------------------------------------------

READY, WHY = chromium_ready()

if READY:

    @check("Chromium prints a PDF whose text a parser can read")
    def _() -> None:
        profile = sample()
        html = render_html(profile, Design())
        pdf = render_pdf(html, margin_mm=16)
        assert pdf[:5] == b"%PDF-", pdf[:12]
        report = pdf_report(pdf, profile)
        assert report.pages >= 1
        assert report.machine_readable, "the PDF has no usable text layer"
        assert all(report.found.values()), report.found
        assert "Northgate Labs" in report.text

    @check("the two-column template still produces readable text")
    def _() -> None:
        profile = sample()
        pdf = render_pdf(render_html(profile, Design(template="modern")), margin_mm=16)
        report = pdf_report(pdf, profile)
        assert report.machine_readable and all(report.found.values()), report.found

    @check("contact details print as real, clickable links")
    def _() -> None:
        # Chromium turns anchors into PDF link annotations, which is why the
        # header is marked up as links rather than styled text: an email in a
        # PDF that cannot be clicked is a phone number you have to retype.
        from io import BytesIO

        from pypdf import PdfReader

        profile = sample()
        pdf = render_pdf(render_html(profile, Design()), margin_mm=16)
        uris = []
        for page in PdfReader(BytesIO(pdf)).pages:
            for annotation in page.get("/Annots") or []:
                action = annotation.get_object().get("/A") or {}
                if action.get("/URI"):
                    uris.append(str(action["/URI"]))
        assert any(u.startswith("mailto:") for u in uris), uris
        assert any(u.startswith("tel:") for u in uris), uris
        assert any("github.com/astudent" in u for u in uris), uris


    @check("page size follows the design")
    def _() -> None:
        from io import BytesIO

        from pypdf import PdfReader

        for key, expected_mm in (("a4", 297.0), ("letter", 279.4)):
            design = Design(page=key)
            pdf = render_pdf(render_html(sample(), design), margin_mm=design.margin_mm)
            box = PdfReader(BytesIO(pdf)).pages[0].mediabox
            # PDF points: 72 to the inch.
            height_mm = float(box.height) * 25.4 / 72
            assert abs(height_mm - expected_mm) < 1.5, (key, height_mm)


def main() -> int:
    for name in PASSED:
        print(f"  ok    {name}")
    for name in FAILED:
        print(f"  FAIL  {name}")
    if not READY:
        print(f"  skip  PDF checks -- {WHY}")
    print()
    print(f"{len(PASSED)} passed, {len(FAILED)} failed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
