"""Preview and print.

Both take an optional profile and an optional design in the body. That matters
for the editor: the preview has to show what the user is typing *now*, not
what was last saved, and forcing a save before every preview would make
autosave a correctness requirement rather than a convenience.
"""

from __future__ import annotations

from fastapi import APIRouter, Response
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ...core.schema import Profile
from ...core.storage import load_profile
from ...render.context import build_context, suggested_filename
from ...render.design import TEMPLATES, Design, load_design
from ...render.html import render_html, render_thumbnail
from ...render.pdf import pdf_report, render_pdf
from ...render.text import plain_text

from ..downloads import attachment

router = APIRouter(prefix="/api/render", tags=["render"])


class RenderRequest(BaseModel):
    profile: Profile | None = None
    design: Design | None = None
    zoom: float = Field(default=0.0, ge=0.0, le=3.0)
    fit: Literal["width", "page"] = "width"

    def resolve(self) -> tuple[Profile, Design]:
        return (self.profile or load_profile(), self.design or load_design())


class ThumbnailRequest(RenderRequest):
    template: str

    @field_validator("template")
    @classmethod
    def known(cls, value: str) -> str:
        # `Design` repairs an unknown template to the default, but this one
        # arrives as a plain string and reaches the template map through
        # `model_copy`, which does not re-validate. Unchecked, it was a
        # KeyError and a 500.
        if value not in TEMPLATES:
            raise ValueError(f"Unknown template {value!r}.")
        return value


@router.post("/preview", response_class=Response)
def preview(request: RenderRequest) -> Response:
    """The document with its desk, sheet and page-break rules, as HTML.

    Returned as a document rather than as JSON because the client displays it
    in an iframe: it is the same markup the printer gets, and wrapping it in a
    JSON string would only mean unwrapping it again.
    """
    profile, design = request.resolve()
    html = render_html(profile, design, preview=True, zoom=request.zoom, fit=request.fit)
    return Response(content=html, media_type="text/html; charset=utf-8")


@router.post("/thumbnail", response_class=Response)
def thumbnail(request: ThumbnailRequest) -> Response:
    profile, design = request.resolve()
    html = render_thumbnail(profile, design, request.template, request.zoom)
    return Response(content=html, media_type="text/html; charset=utf-8")


@router.post("/html", response_class=Response)
def print_html(request: RenderRequest) -> Response:
    """The self-contained document, for downloading or emailing."""
    profile, design = request.resolve()
    html = render_html(profile, design)
    filename = suggested_filename(profile, design, "html")
    return Response(
        content=html,
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": attachment(filename, fallback="Resume")},
    )


@router.post("/text", response_class=Response)
def text(request: RenderRequest) -> Response:
    """The profile as plain text, for application forms that take no file."""
    profile, design = request.resolve()
    filename = suggested_filename(profile, design, "txt")
    return Response(
        content=plain_text(profile, date_format=design.date_format),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": attachment(filename, fallback="Resume")},
    )


@router.post("/pdf", response_class=Response)
def pdf(request: RenderRequest) -> Response:
    """The printed PDF, with what we learned from reading it back in headers.

    Page count and the text-layer verdict travel as headers rather than in a
    JSON envelope so the body stays a real PDF the browser can save directly.
    A base64 envelope would cost a third more bytes and a decode step for
    facts that fit in three short strings.
    """
    profile, design = request.resolve()
    document = render_html(profile, design)
    data = render_pdf(
        document, margin_mm=design.margin_mm, page_numbers=design.show_page_numbers
    )
    report = pdf_report(data, profile)
    filename = suggested_filename(profile, design)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": attachment(filename, fallback="Resume"),
            "X-Pages": str(report.pages),
            "X-Words": str(report.words),
            "X-Machine-Readable": "1" if report.machine_readable else "0",
        },
    )


class FitReport(BaseModel):
    pages: int
    words: int
    size_kb: int
    machine_readable: bool
    found: dict[str, bool]
    missing: list[str]
    sections: list[str]


@router.post("/report", response_model=FitReport)
def report(request: RenderRequest) -> FitReport:
    """The same print, described rather than returned.

    For the case where the client wants the page count and the ATS verdict
    without downloading a megabyte it is going to throw away.
    """
    profile, design = request.resolve()
    document = render_html(profile, design)
    data = render_pdf(
        document, margin_mm=design.margin_mm, page_numbers=design.show_page_numbers
    )
    result = pdf_report(data, profile)
    return FitReport(
        pages=result.pages,
        words=result.words,
        size_kb=result.size_kb,
        machine_readable=result.machine_readable,
        found=result.found,
        missing=result.missing,
        sections=[s.key for s in build_context(profile, design).sections],
    )
