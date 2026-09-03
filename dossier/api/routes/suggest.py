"""Drafting one block of prose on request.

Separate from ``/api/tailor`` because it answers a different question. Tailor
re-angles a whole profile at a posting; this writes one line the user is
looking at. Both return proposals that have been audited against their source
and linted, and neither writes anything.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...ai import suggest as ai_suggest
from ...core.schema import Profile
from ...core.storage import load_profile

router = APIRouter(prefix="/api/suggest", tags=["suggest"])


class SuggestRequest(BaseModel):
    kind: str
    """"bullet" or "summary"."""
    note: str = ""
    entry_label: str = ""
    section: str = ""
    entry_id: str = ""
    profile: Profile | None = None
    model: str | None = None


class DraftOut(BaseModel):
    text: str
    model: str
    invented: list[str]
    findings: list[str]


@router.post("", response_model=DraftOut)
def draft(request: SuggestRequest) -> DraftOut:
    profile = request.profile if request.profile is not None else load_profile()
    try:
        if request.kind == "summary":
            result = ai_suggest.suggest_summary(
                profile, note=request.note, model=request.model
            )
        elif request.kind == "bullet":
            result = ai_suggest.suggest_bullet(
                profile,
                request.note,
                entry_label=request.entry_label,
                section=request.section,
                entry_id=request.entry_id,
                model=request.model,
            )
        else:
            raise HTTPException(status_code=422, detail=f"Unknown kind {request.kind!r}.")
    except ValueError as exc:
        # The "you have not given me enough to work from" cases, which are
        # guidance rather than failures.
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return DraftOut(
        text=result.text,
        model=result.model,
        invented=result.invented,
        findings=result.findings,
    )
