"""Getting existing career data in.

Three routes for three different levels of trust, and they stay separate on
purpose: extraction is exact, LinkedIn's export is exact, and the model's
reading of a resume is a proposal. The merge plan is what turns any of them
into a reviewable change rather than an overwrite.
"""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from ...ai import parse as ai_parse
from ...core.schema import Profile
from ...core.storage import load_profile
from ...ingest import extract as extractor
from ...ingest import linkedin
from ...ingest.merge import apply_merge_plan, build_merge_plan

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


class Extracted(BaseModel):
    text: str
    kind: str
    pages: int
    warnings: list[str]


@router.post("/extract", response_model=Extracted)
async def extract_file(file: UploadFile = File(...)) -> Extracted:
    result = extractor.extract(await file.read(), file.filename or "upload")
    return Extracted(
        text=result.text,
        kind=result.kind,
        pages=result.pages,
        warnings=list(result.warnings or []),
    )


class ParseRequest(BaseModel):
    text: str
    model: str | None = None


class Parsed(BaseModel):
    profile: Profile
    model: str
    notes: list[str] = []


@router.post("/parse", response_model=Parsed)
def parse_text(request: ParseRequest) -> Parsed:
    """Gemini reads unstructured resume text into the schema.

    Nothing here writes to the profile. The result is handed back for review,
    and only ``/plan`` + the client's acceptance turn it into a change.
    """
    try:
        result = ai_parse.parse_resume_text(request.text, model=request.model)
    except ValueError as exc:
        # An empty box is something the person can fix; say so rather than
        # handing them a 500.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Parsed(
        profile=result.profile,
        model=result.model,
        notes=[
            f"Parsed by {result.model}. It was told to transcribe, not rewrite -- "
            "check the bullets say what the resume actually said."
        ],
    )


@router.post("/linkedin", response_model=Parsed)
async def parse_linkedin(file: UploadFile = File(...)) -> Parsed:
    result = linkedin.parse_export(await file.read())
    notes = list(result.notes)
    if result.files_found:
        notes.append("Read: " + ", ".join(result.files_found))
    notes.append(
        'LinkedIn stores some dates as a year only. Those are kept as a year ("2027"), '
        "not turned into a month -- your resume will print the year."
    )
    return Parsed(profile=result.profile, model="none (deterministic)", notes=notes)


class PlanRequest(BaseModel):
    candidate: Profile
    source: str = "Import"


class ProposalOut(BaseModel):
    path: str
    label: str
    current: str
    proposed: str
    conflicts: bool


class CandidateOut(BaseModel):
    key: str
    section: str
    label: str
    detail: str
    is_duplicate: bool
    bullets: list[str]


class PlanOut(BaseModel):
    source: str
    notes: list[str]
    fields: list[ProposalOut]
    candidates: list[CandidateOut]


@router.post("/plan", response_model=PlanOut)
def plan(request: PlanRequest) -> PlanOut:
    """What an import would change, itemised, before anything changes."""
    plan = build_merge_plan(load_profile(), request.candidate, request.source)
    return PlanOut(
        source=plan.source,
        notes=list(plan.notes),
        fields=[
            ProposalOut(
                path=p.path, label=p.label, current=p.current,
                proposed=p.proposed, conflicts=p.conflicts,
            )
            for p in plan.fields
        ],
        candidates=[
            CandidateOut(
                key=c.key, section=c.section, label=c.label, detail=c.detail,
                is_duplicate=c.is_duplicate,
                bullets=[b.text for b in getattr(c.entry, "bullets", [])],
            )
            for c in plan.candidates
        ],
    )


class ApplyRequest(PlanRequest):
    accept_fields: list[str] = []
    accept_candidates: list[str] = []


class ApplyResult(BaseModel):
    profile: Profile
    changes: list[str]


@router.post("/apply", response_model=ApplyResult)
def apply(request: ApplyRequest) -> ApplyResult:
    """Fold the accepted parts of an import into the stored profile.

    Returns the merged profile without saving it: the client decides when to
    commit, and the same review screen that showed the plan gets to show the
    result first.
    """
    profile = load_profile()
    plan = build_merge_plan(profile, request.candidate, request.source)
    changes = apply_merge_plan(
        profile, plan, set(request.accept_fields), set(request.accept_candidates)
    )
    return ApplyResult(profile=profile, changes=changes)
