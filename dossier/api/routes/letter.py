"""Cover letters: draft one, print it, keep it.

Split across two prefixes for the same reason applications and versions are.
``/api/letter`` is the stateless half -- draft from a posting, preview the
markup, print a PDF -- and needs no application to exist. ``/api/applications
/{id}/letters`` is where one gets filed.

The drafting route is the only one that touches a model, and it is the only
one that can fail for want of a key. Everything else here works without one,
including writing a letter by hand and printing it, which is deliberate: a
person who does not want a model to write their letter should still get the
paper, the typeface and the PDF.
"""

from __future__ import annotations
from ...core.markup import plain

import sqlite3
from typing import Iterator

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from ...ai import letter as drafting
from ...core import jobspec
from ...core import letters as store
from ...core.db import connect
from ...core.schema import Profile
from ...core.storage import load_profile
from ...render.design import Design, load_design
from ...render.letter import LetterDocument, letter_filename, render_letter_html
from ...render.pdf import pdf_report, render_pdf

from ..downloads import attachment

router = APIRouter(prefix="/api/letter", tags=["letter"])
filed = APIRouter(prefix="/api/applications", tags=["letter"])


def db() -> Iterator[sqlite3.Connection]:
    connection = connect()
    try:
        yield connection
    finally:
        connection.close()


# --------------------------------------------------------------------------
# Wire shapes
# --------------------------------------------------------------------------


class LetterBody(BaseModel):
    """A letter as the screen holds it: editable text, not a model's output."""

    paragraphs: list[str] = Field(default_factory=list)
    greeting: str = ""
    closing: str = ""
    signature: str = ""
    recipient: str = ""
    company: str = ""
    role: str = ""
    date: str = ""
    invented: list[str] = Field(default_factory=list)
    """What the fabrication audit found when this was drafted."""
    model: str = ""
    """Which model wrote it, or "" for a letter written by hand."""

    def document(self, profile: Profile) -> LetterDocument:
        return LetterDocument(
            paragraphs=[p.strip() for p in self.paragraphs if p.strip()],
            greeting=self.greeting or drafting.greeting_for(self.recipient),
            closing=self.closing or drafting.closing_for(self.recipient),
            signature=self.signature or plain(profile.basics.name),
            recipient=self.recipient,
            company=self.company,
            role=self.role,
            date=self.date,
            invented=self.invented,
        )


class DraftRequest(BaseModel):
    """Name a saved application, or paste a posting. Not both, and one is
    better: the application already holds the advert, so sending it back up
    the wire would be shipping the same text twice."""

    application_id: str = ""
    text: str = ""
    company: str = ""
    role: str = ""
    recipient: str = ""
    note: str = ""
    profile: Profile | None = None


class RenderRequest(BaseModel):
    letter: LetterBody
    profile: Profile | None = None
    design: Design | None = None
    zoom: float = Field(default=0.0, ge=0.0, le=3.0)




class LetterOut(BaseModel):
    id: str
    application_id: str
    model: str
    created_at: str
    preview: str


class LetterDetail(LetterOut):
    letter: LetterBody
    design: Design


# --------------------------------------------------------------------------
# Drafting and printing
# --------------------------------------------------------------------------


@router.post("/draft", response_model=LetterBody)
def draft(
    request: DraftRequest, connection: sqlite3.Connection = Depends(db)
) -> LetterBody:
    """Draft a letter from the posting and the profile. Uses a model."""
    posting = request.text
    company = request.company
    role = request.role
    if request.application_id:
        row = connection.execute(
            "SELECT posting, company, title FROM applications WHERE id = ?",
            (request.application_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="No application with that id.")
        posting = row["posting"]
        company = company or row["company"]
        role = role or row["title"]
    if not posting.strip():
        raise HTTPException(status_code=422, detail="There is no posting to write about.")
    request = request.model_copy(update={"text": posting, "company": company, "role": role})
    profile = request.profile if request.profile is not None else load_profile()
    # Read by rules first, exactly as the Tailor screen does, so the model is
    # briefed with which requirements this person can actually evidence rather
    # than being handed the advert and trusted.
    report = jobspec.analyse(profile, request.text, company=request.company)
    try:
        written = drafting.draft_letter(
            profile,
            report,
            recipient=request.recipient,
            company=request.company,
            role=request.role,
            note=request.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return LetterBody(
        paragraphs=written.paragraphs,
        greeting=written.greeting,
        closing=written.closing,
        signature=written.signature,
        recipient=request.recipient,
        company=request.company or report.spec.company,
        role=request.role or report.spec.title,
        invented=written.invented,
        model=written.model,
    )


@router.post("/preview", response_class=Response)
def preview(request: RenderRequest) -> Response:
    """The letter with its desk and sheet, for the iframe."""
    profile = request.profile or load_profile()
    design = request.design or load_design()
    html = render_letter_html(
        profile, design, request.letter.document(profile), preview=True, zoom=request.zoom
    )
    return Response(content=html, media_type="text/html; charset=utf-8")


@router.post("/pdf", response_class=Response)
def pdf(request: RenderRequest) -> Response:
    profile = request.profile or load_profile()
    design = request.design or load_design()
    document = request.letter.document(profile)
    if not document.paragraphs:
        raise HTTPException(status_code=422, detail="The letter has no words in it yet.")
    return _printed(profile, design, document)


# --------------------------------------------------------------------------
# Filing one against an application
# --------------------------------------------------------------------------


@filed.post("/{application_id}/letters", response_model=LetterOut)
def keep(
    application_id: str,
    request: RenderRequest,
    connection: sqlite3.Connection = Depends(db),
) -> LetterOut:
    _require(connection, application_id)
    profile = request.profile or load_profile()
    design = request.design or load_design()
    document = request.letter.document(profile)
    if not document.paragraphs:
        raise HTTPException(status_code=422, detail="The letter has no words in it yet.")
    letter_id = store.save_letter(
        application_id,
        _as_body(document).model_dump(mode="json"),
        design.model_dump(mode="json"),
        # Which model wrote it travels on the letter, so a hand-written one
        # is recorded as hand-written without the caller having to say so.
        model=request.letter.model,
        connection=connection,
    )
    kept = store.load(letter_id, connection=connection)
    assert kept is not None
    return _out(kept)


@filed.get("/{application_id}/letters", response_model=list[LetterOut])
def listing(
    application_id: str, connection: sqlite3.Connection = Depends(db)
) -> list[LetterOut]:
    _require(connection, application_id)
    return [_out(letter) for letter in store.list_letters(application_id, connection=connection)]


@router.get("/{letter_id}", response_model=LetterDetail)
def read(letter_id: str, connection: sqlite3.Connection = Depends(db)) -> LetterDetail:
    kept = _load(letter_id, connection)
    return LetterDetail(
        **_out(kept).model_dump(),
        letter=LetterBody.model_validate(kept.document),
        design=Design.model_validate(kept.design),
    )


@router.put("/{letter_id}", response_model=LetterOut)
def edit(
    letter_id: str, request: RenderRequest, connection: sqlite3.Connection = Depends(db)
) -> LetterOut:
    """Save an edit to a filed letter. A draft is meant to be rewritten."""
    _load(letter_id, connection)
    profile = request.profile or load_profile()
    store.update_letter(
        letter_id,
        _as_body(request.letter.document(profile)).model_dump(mode="json"),
        connection=connection,
    )
    kept = store.load(letter_id, connection=connection)
    assert kept is not None
    return _out(kept)


@router.post("/{letter_id}/pdf", response_class=Response)
def reprint(letter_id: str, connection: sqlite3.Connection = Depends(db)) -> Response:
    """The same letter again, in the design it was written in."""
    kept = _load(letter_id, connection)
    profile = load_profile()
    design = Design.model_validate(kept.design)
    document = LetterBody.model_validate(kept.document).document(profile)
    return _printed(profile, design, document)


@router.delete("/{letter_id}", response_model=dict)
def forget(letter_id: str, connection: sqlite3.Connection = Depends(db)) -> dict[str, bool]:
    _load(letter_id, connection)
    store.delete_letter(letter_id, connection=connection)
    return {"deleted": True}


# --------------------------------------------------------------------------
# Shared
# --------------------------------------------------------------------------


def _printed(profile: Profile, design: Design, document: LetterDocument) -> Response:
    """The letter as a PDF, with its text layer read back before it is sent.

    The same guarantee the resume has, for the same reason: a letter that
    looks perfect and parses as an empty document fails silently, and the
    person who sent it never finds out. Reported in headers rather than an
    envelope so the body stays a real PDF the browser can save.
    """
    data = render_pdf(
        render_letter_html(profile, design, document),
        margin_mm=design.margin_mm,
        # A one-page letter numbered "1" looks like a form. Never numbered,
        # whatever the resume is set to.
        page_numbers=False,
    )
    report = pdf_report(data, profile)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": attachment(
                letter_filename(profile, document), fallback="Cover-Letter"
            ),
            "X-Pages": str(report.pages),
            "X-Words": str(report.words),
            "X-Machine-Readable": "1" if report.machine_readable else "0",
        },
    )


def _as_body(document: LetterDocument) -> LetterBody:
    return LetterBody(
        paragraphs=document.paragraphs,
        greeting=document.greeting,
        closing=document.closing,
        signature=document.signature,
        recipient=document.recipient,
        company=document.company,
        role=document.role,
        date=document.date,
        invented=document.invented,
    )


def _out(letter: store.StoredLetter) -> LetterOut:
    return LetterOut(
        id=letter.id,
        application_id=letter.application_id,
        model=letter.model,
        created_at=letter.created_at,
        preview=letter.preview,
    )


def _load(letter_id: str, connection: sqlite3.Connection) -> store.StoredLetter:
    kept = store.load(letter_id, connection=connection)
    if kept is None or kept.document is None:
        raise HTTPException(status_code=404, detail="No letter with that id.")
    return kept


def _require(connection: sqlite3.Connection, application_id: str) -> None:
    found = connection.execute(
        "SELECT 1 FROM applications WHERE id = ?", (application_id,)
    ).fetchone()
    if found is None:
        raise HTTPException(status_code=404, detail="No application with that id.")
