"""Which CV the app is looking at.

Thin over ``core.cvs``: the registry decides everything, and these seven
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
    #: Whose CV this is. The switcher groups on it.
    person: str
    #: Which of that person's CVs. Empty means the one they started with.
    label: str
    #: Both halves on one line, for anywhere there is only one line.
    name: str
    created: str
    updated: str
    #: The focus this CV opens with. A default, not a lock.
    focus: str
    #: Whether this CV has anything in it yet, so the list can say so.
    blank: bool
    #: True while the name is one we generated. The client uses it to know
    #: whether saving a profile could rename this CV under it.
    auto_named: bool


class CVList(BaseModel):
    cvs: list[CVOut]
    active: str


class NameIn(BaseModel):
    """One name. What it names depends on the route -- a person, or a label."""

    name: str = Field(default="", max_length=80)


class PersonIn(BaseModel):
    """Renaming somebody addresses them by name, because a person is not a row."""

    old: str = Field(min_length=1, max_length=80)
    new: str = Field(min_length=1, max_length=80)


def _describe(cv: registry.CV) -> CVOut:
    try:
        blank = load_profile(registry.path_for(cv.id)).is_blank()
    except ProfileError:
        # A CV whose file will not parse still belongs in the list -- hiding it
        # is how someone loses a document. Opening it reports what is wrong.
        blank = False
    return CVOut(
        id=cv.id,
        person=cv.person,
        label=cv.label,
        name=cv.name,
        created=cv.created,
        updated=cv.updated,
        blank=blank,
        auto_named=cv.auto_named,
        focus=cv.focus,
    )


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


@router.post("/{cv_id}/duplicate", response_model=CVList, status_code=201)
def duplicate(cv_id: str, body: NameIn | None = None) -> CVList:
    """Copy a CV -- content, design and focus -- and make the copy active.

    A copy rather than a new CV: two accounts of one life are easier to start
    from each other than from nothing. The copy keeps the name it is given and
    never takes one from a profile saved into it afterwards.

    404 rather than 400, like ``activate``: the only thing that can be wrong
    here is the id in the path.
    """
    try:
        registry.duplicate(cv_id, body.name if body else "")
    except registry.CVError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _listing()


@router.put("/{cv_id}/active", response_model=CVList)
def activate(cv_id: str) -> CVList:
    try:
        registry.switch(cv_id)
    except registry.CVError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _listing()


@router.put("/person", response_model=CVList)
def rename_person(body: PersonIn) -> CVList:
    """Rename somebody across every CV of theirs.

    Declared above ``/{cv_id}`` so the literal path wins the match -- otherwise
    "person" arrives here as a CV id and 404s.

    A person rather than an id because the person is what groups the list:
    renaming it on one CV and not the others would leave somebody's three CVs
    showing as two entries under two spellings of one name.
    """
    try:
        registry.rename_person(body.old, body.new)
    except registry.CVError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _listing()


@router.put("/{cv_id}", response_model=CVList)
def rename(cv_id: str, body: NameIn) -> CVList:
    """Label one of a person's CVs. An empty name clears it back to their main one."""
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
