"""Saved applications, and what they add up to.

One connection per request, opened and closed by a dependency. SQLite
connections are not safe to share across threads and FastAPI runs sync routes
in a threadpool, so a module-level connection would be a race the moment two
requests overlap -- and opening one is measured in microseconds against a file
on local disk.
"""

from __future__ import annotations

import sqlite3
from typing import Iterator

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from ...core import applications as store
from ...core import jobspec
from ...core import versions as archive
from ...core.db import connect
from ...core.schema import Profile
from ...core.storage import load_profile, migrate
from ...render.context import suggested_filename
from ...render.design import Design, load_design
from ...render.html import render_html
from ...render.pdf import pdf_report, render_pdf

router = APIRouter(prefix="/api/applications", tags=["applications"])

# Versions are addressed by their own id rather than through the application
# they belong to: everything that acts on one -- reading it, printing it,
# deleting it -- already has the version in hand and would only be repeating
# itself by naming the parent as well.
versions = APIRouter(prefix="/api/versions", tags=["applications"])


def db() -> Iterator[sqlite3.Connection]:
    connection = connect()
    try:
        yield connection
    finally:
        connection.close()


# --------------------------------------------------------------------------
# Wire shapes
# --------------------------------------------------------------------------


class SaveRequest(BaseModel):
    text: str
    title: str = ""
    company: str = ""
    source_url: str = ""
    notes: str = ""
    profile: Profile | None = None
    """Unsaved edits count towards coverage, as they do on the Tailor screen."""


class RunRequest(BaseModel):
    model: str = ""
    suggestions: list[dict] = Field(default_factory=list)


class StatusRequest(BaseModel):
    status: str


class ApplicationOut(BaseModel):
    id: str
    title: str
    company: str
    status: str
    coverage: int
    created_at: str
    updated_at: str
    applied_at: str | None
    notes: str
    source_url: str
    required_missing: list[str]
    runs: int
    accepted: int
    versions: int


class GapOut(BaseModel):
    term: str
    tier: str
    postings: int
    missing_in: int
    weight: float


class OverviewOut(BaseModel):
    applications: list[ApplicationOut]
    gaps: list[GapOut]
    pipeline: dict[str, int]
    trend: list[tuple[str, int]]
    guard: dict[str, int]


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------


@router.get("", response_model=OverviewOut)
def overview(connection: sqlite3.Connection = Depends(db)) -> OverviewOut:
    """Everything the Applications screen shows, in one round trip.

    Five queries against a local file are cheaper than five HTTP requests, and
    the screen is meaningless with only some of them.
    """
    listed = store.list_applications(connection=connection)
    kept = archive.counts(connection=connection)
    return OverviewOut(
        applications=[
            ApplicationOut(
                id=a.id,
                title=a.title,
                company=a.company,
                status=a.status,
                coverage=a.coverage,
                created_at=a.created_at,
                updated_at=a.updated_at,
                applied_at=a.applied_at,
                notes=a.notes,
                source_url=a.source_url,
                required_missing=a.required_missing,
                runs=a.runs,
                accepted=a.accepted,
                versions=kept.get(a.id, 0),
            )
            for a in listed
        ],
        gaps=[
            GapOut(
                term=g.term,
                tier=g.tier,
                postings=g.postings,
                missing_in=g.missing_in,
                weight=g.weight,
            )
            for g in store.recurring_gaps(connection=connection)
        ],
        pipeline=store.pipeline(connection=connection),
        trend=store.coverage_trend(connection=connection),
        guard=store.guard_record(connection=connection),
    )


@router.post("", response_model=dict)
def save(
    request: SaveRequest, connection: sqlite3.Connection = Depends(db)
) -> dict[str, str | int]:
    """Analyse a posting by rules and store it. No model involved."""
    if not request.text.strip():
        raise HTTPException(status_code=422, detail="There is no posting to save.")
    profile = request.profile if request.profile is not None else load_profile()
    report = jobspec.analyse(
        profile, request.text, title=request.title, company=request.company
    )
    app_id = store.save_application(
        report,
        connection=connection,
        source_url=request.source_url,
        notes=request.notes,
    )
    return {"id": app_id, "title": report.spec.title, "coverage": report.coverage}


@router.post("/{application_id}/runs", response_model=dict)
def add_run(
    application_id: str, request: RunRequest, connection: sqlite3.Connection = Depends(db)
) -> dict[str, str]:
    """Record a tailoring pass against a saved application."""
    if not _exists(connection, application_id):
        raise HTTPException(status_code=404, detail="No application with that id.")
    run_id = store.record_run(
        application_id, request.model, request.suggestions, connection=connection
    )
    return {"id": run_id}


@router.put("/{application_id}/status", response_model=dict)
def update_status(
    application_id: str, request: StatusRequest, connection: sqlite3.Connection = Depends(db)
) -> dict[str, str]:
    if not _exists(connection, application_id):
        raise HTTPException(status_code=404, detail="No application with that id.")
    try:
        store.set_status(application_id, request.status, connection=connection)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": request.status}


@router.delete("/{application_id}", response_model=dict)
def remove(
    application_id: str, connection: sqlite3.Connection = Depends(db)
) -> dict[str, bool]:
    if not _exists(connection, application_id):
        raise HTTPException(status_code=404, detail="No application with that id.")
    store.delete_application(application_id, connection=connection)
    return {"deleted": True}


# --------------------------------------------------------------------------
# Versions: what was actually sent
# --------------------------------------------------------------------------


class VersionRequest(BaseModel):
    label: str = ""
    profile: Profile | None = None
    design: Design | None = None
    """Unsaved edits are what was printed, so they are what gets kept."""


class VersionOut(BaseModel):
    id: str
    application_id: str
    label: str
    pages: int
    words: int
    created_at: str


@router.post("/{application_id}/versions", response_model=VersionOut)
def keep_version(
    application_id: str,
    request: VersionRequest,
    connection: sqlite3.Connection = Depends(db),
) -> VersionOut:
    """Keep the document as it stands, against this application.

    The PDF is printed here rather than trusting a page count from the client,
    for the same reason `pdf_report` reads its own output back: the record has
    to say what came out of the printer, and a number the browser sent is a
    number about something else.
    """
    if not _exists(connection, application_id):
        raise HTTPException(status_code=404, detail="No application with that id.")
    profile = request.profile or load_profile()
    design = request.design or load_design()
    report = pdf_report(
        render_pdf(
            render_html(profile, design),
            margin_mm=design.margin_mm,
            page_numbers=design.show_page_numbers,
        ),
        profile,
    )
    version_id = archive.save_version(
        application_id,
        profile.model_dump(mode="json"),
        design.model_dump(mode="json"),
        label=request.label,
        pages=report.pages,
        words=report.words,
        connection=connection,
    )
    kept = archive.load(version_id, connection=connection)
    assert kept is not None  # just written, in this transaction-less connection
    return _version_out(kept)


@router.get("/{application_id}/versions", response_model=list[VersionOut])
def list_versions(
    application_id: str, connection: sqlite3.Connection = Depends(db)
) -> list[VersionOut]:
    if not _exists(connection, application_id):
        raise HTTPException(status_code=404, detail="No application with that id.")
    return [
        _version_out(v) for v in archive.list_versions(application_id, connection=connection)
    ]


class VersionDetail(VersionOut):
    profile: Profile
    design: Design


@versions.get("/{version_id}", response_model=VersionDetail)
def read_version(
    version_id: str, connection: sqlite3.Connection = Depends(db)
) -> VersionDetail:
    """One version, ready to render.

    The stored profile goes through `storage.migrate` on the way out. A
    version written under schema 3 has to keep opening at schema 5 -- an
    archive that stops reading its own contents is not an archive.
    """
    profile, design, kept = _restore(version_id, connection)
    return VersionDetail(**_version_out(kept).model_dump(), profile=profile, design=design)


@versions.post("/{version_id}/pdf", response_class=Response)
def reprint(version_id: str, connection: sqlite3.Connection = Depends(db)) -> Response:
    """The same PDF again, from the stored document rather than from today's."""
    profile, design, _ = _restore(version_id, connection)
    data = render_pdf(
        render_html(profile, design),
        margin_mm=design.margin_mm,
        page_numbers=design.show_page_numbers,
    )
    report = pdf_report(data, profile)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{suggested_filename(profile, design)}"',
            "X-Pages": str(report.pages),
            "X-Words": str(report.words),
            "X-Machine-Readable": "1" if report.machine_readable else "0",
        },
    )


@versions.delete("/{version_id}", response_model=dict)
def forget_version(
    version_id: str, connection: sqlite3.Connection = Depends(db)
) -> dict[str, bool]:
    if archive.load(version_id, connection=connection) is None:
        raise HTTPException(status_code=404, detail="No version with that id.")
    archive.delete_version(version_id, connection=connection)
    return {"deleted": True}


def _version_out(version: archive.Version) -> VersionOut:
    return VersionOut(
        id=version.id,
        application_id=version.application_id,
        label=version.label,
        pages=version.pages,
        words=version.words,
        created_at=version.created_at,
    )


def _restore(
    version_id: str, connection: sqlite3.Connection
) -> tuple[Profile, Design, archive.Version]:
    kept = archive.load(version_id, connection=connection)
    if kept is None or kept.profile is None or kept.design is None:
        raise HTTPException(status_code=404, detail="No version with that id.")
    try:
        profile = Profile.model_validate(migrate(dict(kept.profile)))
    except Exception as exc:  # noqa: BLE001 -- any failure reads the same here
        raise HTTPException(
            status_code=422,
            detail="That saved version cannot be read by this build of Dossierbuild.",
        ) from exc
    return profile, Design.model_validate(kept.design), kept


def _exists(connection: sqlite3.Connection, application_id: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM applications WHERE id = ?", (application_id,)
        ).fetchone()
        is not None
    )
