"""Aiming a profile at one job.

Three endpoints for three levels of trust, kept apart for the same reason the
ingest routes are:

``/analyse`` is arithmetic. It reads the posting and matches it against the
profile with no model involved, so the gap report works with no API key, with
Gemini down, and inside a test.

``/rewrite`` is a proposal. It calls a model and returns suggestions that have
already been audited against their originals; it writes nothing.

``/apply`` turns accepted suggestions into a profile the client can hand to its
editor. It does not save either -- the user still presses Save, and undo still
covers it.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...ai import tailor as ai_tailor
from ...core import jobspec
from ...core.schema import Profile
from ...core.storage import load_profile

router = APIRouter(prefix="/api/tailor", tags=["tailor"])


# --------------------------------------------------------------------------
# Wire shapes
# --------------------------------------------------------------------------


class PostingRequest(BaseModel):
    text: str
    title: str = ""
    company: str = ""
    profile: Profile | None = None
    """Unsaved edits win over what is on disk, exactly as the render routes do.
    Someone who has just typed a bullet expects it to count towards coverage."""


class RewriteRequest(PostingRequest):
    entry_ids: list[str] | None = None
    model: str | None = None


class TermOut(BaseModel):
    text: str
    key: str
    weight: float
    count: int
    tier: str


class EvidenceOut(BaseModel):
    section: str
    entry_id: str
    entry_label: str
    block_id: str
    text: str


class EntryScoreOut(BaseModel):
    section: str
    entry_id: str
    label: str
    score: float
    matched: list[str]


class MatchOut(BaseModel):
    title: str
    company: str
    coverage: int
    terms: list[TermOut]
    covered: dict[str, list[EvidenceOut]]
    missing: list[TermOut]
    entries: list[EntryScoreOut]
    declared_only: list[str]


class SuggestionOut(BaseModel):
    block_id: str
    section: str
    entry_label: str
    before: str
    after: str
    reason: str
    invented: list[str]
    findings_before: int
    findings_after: int
    terms_added: list[str]


class RewriteOut(BaseModel):
    model: str
    summary: SuggestionOut | None
    suggestions: list[SuggestionOut]
    notes: list[str]


class ApplyRequest(BaseModel):
    profile: Profile | None = None
    accepted: dict[str, str] = Field(default_factory=dict)


class ApplyOut(BaseModel):
    profile: Profile
    changed: int


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------


def _profile(supplied: Profile | None) -> Profile:
    return supplied if supplied is not None else load_profile()


def _term(term: jobspec.Term) -> TermOut:
    return TermOut(text=term.text, key=term.key, weight=term.weight, count=term.count, tier=term.tier)


def _suggestion(s: ai_tailor.Suggestion) -> SuggestionOut:
    return SuggestionOut(
        block_id=s.block_id,
        section=s.section,
        entry_label=s.entry_label,
        before=s.before,
        after=s.after,
        reason=s.reason,
        invented=s.invented,
        findings_before=s.findings_before,
        findings_after=s.findings_after,
        terms_added=s.terms_added,
    )


@router.post("/analyse", response_model=MatchOut)
def analyse(request: PostingRequest) -> MatchOut:
    """Read a posting and report the gap. No model, no key, no network."""
    report = jobspec.analyse(
        _profile(request.profile), request.text, title=request.title, company=request.company
    )
    return MatchOut(
        title=report.spec.title,
        company=report.spec.company,
        coverage=report.coverage,
        terms=[_term(t) for t in report.spec.terms],
        covered={
            key: [
                EvidenceOut(
                    section=e.section,
                    entry_id=e.entry_id,
                    entry_label=e.entry_label,
                    block_id=e.block_id,
                    text=e.text,
                )
                for e in hits
            ]
            for key, hits in report.covered.items()
        },
        missing=[_term(t) for t in report.missing],
        entries=[
            EntryScoreOut(
                section=e.section,
                entry_id=e.entry_id,
                label=e.label,
                score=round(e.score, 2),
                matched=e.matched,
            )
            for e in report.entries
        ],
        declared_only=report.declared_only,
    )


@router.post("/rewrite", response_model=RewriteOut)
def rewrite(request: RewriteRequest) -> RewriteOut:
    """Propose rewrites. Writes nothing; every suggestion arrives audited."""
    profile = _profile(request.profile)
    report = jobspec.analyse(profile, request.text, title=request.title, company=request.company)
    try:
        result = ai_tailor.tailor(
            profile,
            report,
            entry_ids=set(request.entry_ids) if request.entry_ids else None,
            model=request.model,
        )
    except ValueError as exc:
        # "There is nothing to tailor yet" is advice, not a failure. Reaching
        # here through an empty profile used to produce a 500.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return RewriteOut(
        model=result.model,
        summary=_suggestion(result.summary) if result.summary else None,
        suggestions=[_suggestion(s) for s in result.suggestions],
        notes=result.notes,
    )


@router.post("/apply", response_model=ApplyOut)
def apply(request: ApplyRequest) -> ApplyOut:
    """Write accepted rewrites into a profile and hand it back unsaved."""
    updated, changed = ai_tailor.apply_suggestions(_profile(request.profile), request.accepted)
    return ApplyOut(profile=updated, changed=changed)
