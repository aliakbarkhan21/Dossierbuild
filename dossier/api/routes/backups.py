"""Reaching the copies the app has always been keeping.

Four handlers over ``core.backups``: list them, read one, restore one, and
say how many to keep. Nothing here takes a path from a request -- an id names
a backup and the registry resolves it.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...core import backups as store
from ...core import cvs as registry
from ...core.schema import Profile

router = APIRouter(prefix="/api/backups", tags=["backups"])


class BackupOut(BaseModel):
    id: str
    cv_id: str
    cv_name: str
    deleted_cv: bool
    taken: str
    name: str
    headline: str
    entries: int
    bullets: int
    bytes: int
    unreadable: str


class BackupList(BaseModel):
    backups: list[BackupOut]
    #: How many are kept per CV, so the screen can say why old ones vanish.
    keep: int


class RestoreIn(BaseModel):
    name: str = Field(default="", max_length=80)


def _cv_names() -> dict[str, str]:
    try:
        entries, _ = registry.list_cvs()
    except registry.CVError:
        return {}
    return {cv.id: cv.name for cv in entries}


def _listing() -> BackupList:
    names = _cv_names()
    return BackupList(
        keep=store.BACKUPS_TO_KEEP,
        backups=[
            BackupOut(
                id=b.id,
                cv_id=b.cv_id,
                # Blank when the CV is gone, which is exactly the case where
                # the backup matters most.
                cv_name=names.get(b.cv_id, ""),
                deleted_cv=b.deleted_cv,
                taken=b.taken,
                name=b.name,
                headline=b.headline,
                entries=b.entries,
                bullets=b.bullets,
                bytes=b.bytes,
                unreadable=b.unreadable,
            )
            for b in store.list_backups()
        ],
    )


@router.get("", response_model=BackupList)
def index() -> BackupList:
    return _listing()


@router.get("/{backup_id}", response_model=Profile)
def read(backup_id: str) -> Profile:
    """What is inside one, so it can be looked at before it is restored.

    Run through the same migration and validation as any profile: a backup
    written by an older schema opens, which is most of the point of keeping
    one for six weeks.
    """
    from ...core.storage import migrate

    try:
        raw = store.read_backup(backup_id)
    except store.BackupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        return Profile.model_validate(migrate(raw))
    except Exception as exc:  # noqa: BLE001 -- reported, not swallowed
        raise HTTPException(
            status_code=422,
            detail=f"That backup is from a version this build cannot read: {exc}",
        ) from exc


@router.post("/{backup_id}/restore", response_model=dict)
def restore(backup_id: str, body: RestoreIn | None = None) -> dict:
    """Copy it into a new CV. Never over the one you are looking at."""
    try:
        cv_id = store.restore(backup_id, body.name if body else "")
    except store.BackupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"cv_id": cv_id}
