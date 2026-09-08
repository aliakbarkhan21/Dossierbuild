"""The profile: read it, replace it, measure it, and hang a portrait on it."""

from __future__ import annotations

from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel

from ...core.quality import Finding, build_vocabulary, check_text, summarise
from ...core.schema import LIST_SECTIONS, Profile, iter_bullets
from ...core import cvs
from ...core.storage import dedupe_ids, default_profile_path, load_profile, save_profile
from ...core.sample import sample_profile
from ...render import photo

router = APIRouter(prefix="/api/profile", tags=["profile"])


class SaveResult(BaseModel):
    saved: bool
    path: str
    schema_version: int


class FindingOut(BaseModel):
    block_id: str
    severity: str
    message: str
    icon: str


class QualityReport(BaseModel):
    """What the writing standard makes of the profile as it stands.

    Returned as one object rather than as three endpoints because the numbers
    have to agree with each other: computing the score from one walk over the
    bullets and the findings from another is how a UI ends up showing 8 clean
    bullets and 9 warnings at the same time.
    """

    findings: list[FindingOut]
    entries: int
    bullets: int
    words: int
    clean_bullets: int
    score: int
    errors: int
    warnings: int
    notes: int
    sections_filled: dict[str, bool]


@router.get("", response_model=Profile)
def read_profile() -> Profile:
    return load_profile()


@router.put("", response_model=SaveResult)
def write_profile(incoming: Profile) -> SaveResult:
    """Replace the stored profile.

    FastAPI validates the body against the schema before this runs, so a
    malformed profile never reaches the disk. ``save_profile`` writes
    atomically and leaves a timestamped backup behind.
    """
    # Ids first, then the write. The editor sends `id: ""` for a row somebody
    # has just added and reads the profile back expecting real ones; without
    # this the blank goes to disk, and for a custom section the id is the key
    # the design orders and renames by.
    dedupe_ids(incoming)
    path = save_profile(incoming)
    # A CV still carrying the name we gave it ("CV 2") takes the name of the
    # person in it the first time there is one, so the switcher is a list of
    # names rather than a list of numbers. A CV the user has named is left
    # alone -- see `cvs.adopt_profile_name`.
    cvs.adopt_profile_name(incoming.basics.name)
    return SaveResult(saved=True, path=str(path), schema_version=incoming.schema_version)


@router.get("/quality", response_model=QualityReport)
def quality(profile: Profile | None = None) -> QualityReport:
    stored = profile or load_profile()
    vocabulary = build_vocabulary(stored)

    findings: list[FindingOut] = []
    grouped: dict[str, list[Finding]] = {}
    blocks = 0
    words = 0

    for section, _owner, block in iter_bullets(stored):
        text = block.text.strip()
        if not text:
            continue
        blocks += 1
        words += len(text.split())
        found = check_text(
            text, block.id, is_summary=(section == "summary"), vocabulary=vocabulary
        )
        if found:
            grouped[block.id] = found
            findings += [
                FindingOut(
                    block_id=block.id, severity=f.severity, message=f.message, icon=f.icon
                )
                for f in found
            ]

    errors, warnings, notes = summarise(grouped)
    flagged = {
        bid
        for bid, items in grouped.items()
        if any(f.severity in ("error", "warning") for f in items)
    }
    clean = blocks - len(flagged)

    return QualityReport(
        findings=findings,
        entries=sum(len(getattr(stored, s)) for s in LIST_SECTIONS),
        bullets=blocks,
        words=words,
        clean_bullets=clean,
        score=round(100 * clean / blocks) if blocks else 0,
        errors=errors,
        warnings=warnings,
        notes=notes,
        sections_filled={
            "summary": bool(stored.summary.text.strip()),
            "basics": bool(stored.basics.name and stored.basics.email),
            **{section: bool(getattr(stored, section)) for section in LIST_SECTIONS},
        },
    )


class PhotoResult(BaseModel):
    photo: str


@router.get("/sample", response_model=Profile)
def sample() -> Profile:
    """A worked example, for trying the app before typing anything.

    Returned rather than saved: loading it goes through the client's normal
    edit path, so it lands in the undo stack and one Ctrl+Z puts back whatever
    was there. A route that wrote straight to disk would be the one action in
    the app you could not take back.
    """
    return sample_profile()


@router.get("/blank", response_model=Profile)
def blank() -> Profile:
    """An empty profile of the current shape.

    A route rather than a shape the client builds, for the same reason
    `sample` is: the blank has to agree with `schema.py` exactly, and the only
    thing that can guarantee that is `schema.py`.
    """
    return Profile.empty()


@router.post("/photo", response_model=PhotoResult)
async def upload_photo(file: UploadFile = File(...)) -> PhotoResult:
    """Store a portrait and point the profile at it.

    The profile is saved here rather than left for the client to PUT back:
    the file is already on disk, and a profile that does not mention it would
    leave an orphan nobody can see or delete.
    """
    name = photo.save_photo(await file.read())
    stored = load_profile()
    stored.basics.photo = name
    save_profile(stored)
    return PhotoResult(photo=name)


@router.delete("/photo", response_model=PhotoResult)
def delete_photo() -> PhotoResult:
    stored = load_profile()
    photo.remove_photo(stored.basics.photo)
    stored.basics.photo = ""
    # Only if this CV has been written before -- deleting a portrait should
    # not be what creates a file for an otherwise untouched CV. The check used
    # to be `PROFILE_PATH`, the single file every profile lived in; since
    # profiles moved into `data/cvs`, that named a path the active CV is not
    # at, so the save never happened and the portrait came back on reload.
    if default_profile_path().exists():
        save_profile(stored)
    return PhotoResult(photo="")
