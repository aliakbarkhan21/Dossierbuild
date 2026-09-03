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

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...core import applications as store
from ...core import jobspec
from ...core.db import connect
from ...core.schema import Profile
from ...core.storage import load_profile

router = APIRouter(prefix="/api/applications", tags=["applications"])


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


def _exists(connection: sqlite3.Connection, application_id: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM applications WHERE id = ?", (application_id,)
        ).fetchone()
        is not None
    )
