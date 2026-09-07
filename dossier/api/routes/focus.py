"""The tags that aim one profile at several kinds of job.

Three handlers over ``core.focus`` and ``core.cvs``: what each focus selects,
which CV opens with which, and renaming one across the whole profile.

Note what is *not* here. Setting the focus for a single printing is still the
Resume screen's dropdown writing ``design.focus``; this only sets the CV's
**default**, applied when you switch to it. Keeping those separate is what
lets one profile still be printed several ways without a second CV.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...core import cvs as registry
from ...core import focus as store
from ...core.storage import load_profile, save_profile

router = APIRouter(prefix="/api/focus", tags=["focus"])


class FocusOut(BaseModel):
    tag: str
    bullets: int
    skills: int
    #: Names of the CVs that open with this focus.
    cvs: list[str]


class CoverageOut(BaseModel):
    focuses: list[FocusOut]
    untagged_bullets: int
    untagged_skills: int
    #: The active CV's default, so the screen can show what is selected.
    active_cv: str
    active_focus: str


class FocusIn(BaseModel):
    focus: str = Field(default="", max_length=40)


class RenameIn(BaseModel):
    old: str = Field(min_length=1, max_length=40)
    #: Empty removes the tag from every line that carries it.
    new: str = Field(default="", max_length=40)


def _report() -> CoverageOut:
    profile = load_profile()
    try:
        entries, active = registry.list_cvs()
    except registry.CVError:
        entries, active = [], ""
    defaults = {cv.name: cv.focus for cv in entries if cv.focus}
    coverage = store.coverage(profile, defaults)
    return CoverageOut(
        focuses=[
            FocusOut(tag=f.tag, bullets=f.bullets, skills=f.skills, cvs=f.cvs)
            for f in coverage.focuses
        ],
        untagged_bullets=coverage.untagged_bullets,
        untagged_skills=coverage.untagged_skills,
        active_cv=active,
        active_focus=next((cv.focus for cv in entries if cv.id == active), ""),
    )


@router.get("", response_model=CoverageOut)
def index() -> CoverageOut:
    return _report()


@router.put("/default", response_model=CoverageOut)
def set_default(body: FocusIn) -> CoverageOut:
    """Which focus the CV you are on opens with. Empty prints everything."""
    try:
        registry.set_focus(registry.active_id(), body.focus)
    except registry.CVError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _report()


@router.post("/rename", response_model=CoverageOut)
def rename(body: RenameIn) -> CoverageOut:
    """Retag every line at once.

    The reason this exists: ``#bakend`` on nine bullets meant editing nine
    bullets, and the ninth is the one you miss.
    """
    profile = load_profile()
    try:
        updated, changed = store.rename(profile, body.old, body.new)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if changed:
        save_profile(updated)

    # A CV whose default was the old name follows it, or the default would
    # point at a tag that no longer exists anywhere.
    from ...core.schema import normalise_tag

    old, new = normalise_tag(body.old), normalise_tag(body.new)
    try:
        for cv in registry.list_cvs()[0]:
            if cv.focus == old:
                registry.set_focus(cv.id, new)
    except registry.CVError:
        pass
    return _report()
