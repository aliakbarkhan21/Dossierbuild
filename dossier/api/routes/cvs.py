"""Which CV the app is looking at.

Thin over ``core.cvs``: the registry decides everything, and these five
handlers only turn its errors into status codes. Nothing here takes a file
path from a request -- an id names a CV and the registry resolves it.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...core import cvs as registry
from ...core.storage import ProfileError, load_profile

router = APIRouter(prefix="/api/cvs", tags=["cvs"])


class CVOut(BaseModel):
    id: str
    name: str
    created: str
    updated: str
    #: Whether this CV has anything in it yet, so the list can say so.
    blank: bool


class CVList(BaseModel):
    cvs: list[CVOut]
    active: str


class NameIn(BaseModel):
    name: str = Field(default="", max_length=80)


def _describe(cv: registry.CV) -> CVOut:
    try:
        blank = load_profile(registry.path_for(cv.id)).is_blank()
    except ProfileError:
        # A CV whose file will not parse still belongs in the list -- hiding it
        # is how someone loses a document. Opening it reports what is wrong.
        blank = False
    return CVOut(id=cv.id, name=cv.name, created=cv.created, updated=cv.updated, blank=blank)


def _listing() -> CVList:
    entries, active = registry.list_cvs()
    return CVList(cvs=[_describe(cv) for cv in entries], active=active)


@router.get("", response_model=CVList)
def index() -> CVList:
    return _listing()


@router.post("", response_model=CVList, status_code=201)
def create(body: NameIn | None = None) -> CVList:
    """Start a blank CV and make it the active one.

    The CV being left needs no saving: autosave has already written it, and
    this touches nothing in it. That is why the button asks nothing.
    """
    registry.create(body.name if body else None)
    return _listing()


@router.put("/{cv_id}/active", response_model=CVList)
def activate(cv_id: str) -> CVList:
    try:
        registry.switch(cv_id)
    except registry.CVError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _listing()


@router.put("/{cv_id}", response_model=CVList)
def rename(cv_id: str, body: NameIn) -> CVList:
    try:
        registry.rename(cv_id, body.name)
    except registry.CVError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _listing()


@router.delete("/{cv_id}", response_model=CVList)
def remove(cv_id: str) -> CVList:
    try:
        registry.delete(cv_id)
    except registry.CVError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _listing()
