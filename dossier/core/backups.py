"""The copies the app has been keeping all along, made reachable.

``storage.save_profile`` writes a timestamped copy before every write and
keeps the last fifteen per CV; ``cvs.delete`` moves a deleted CV's whole file
here rather than unlinking it. Both were built so that nothing is ever
actually lost -- and neither was reachable from the interface. The sidebar
even said "a copy is kept in data/backups", which is an application telling
you to go and open a file manager.

So this is the door, not new machinery. It reads what is already on disk.

**Restoring never overwrites.** A restore creates a *new* CV from the copy.
The alternative -- writing it over the CV you are looking at -- makes recovery
itself the thing you can lose work to, and the recovery path is exactly where
somebody is already having a bad day. Two CVs and a delete is a worse outcome
than one wrong CV, but it is a recoverable one.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .storage import BACKUP_DIR, BACKUPS_TO_KEEP

__all__ = [
    "BACKUPS_TO_KEEP",
    "Backup",
    "BackupError",
    "list_backups",
    "path_for",
    "read_backup",
    "restore",
]

#: ``<stem>-20260907-142233.json``. The stem is a CV id, or ``profile`` for a
#: file written before CVs existed, or ``deleted-cv-<id>`` for a whole CV that
#: was removed.
STAMPED = re.compile(r"^(?P<stem>.+)-(?P<stamp>\d{8}-\d{6})$")
DELETED = re.compile(r"^deleted-cv-(?P<id>[^-]+)$")


class BackupError(RuntimeError):
    """Something is wrong with a backup file, said in a sentence."""


@dataclass(frozen=True)
class Backup:
    #: The filename stem. What the API takes to address one.
    id: str
    #: The CV it was taken from, when that can be told.
    cv_id: str
    #: True when the whole CV was deleted rather than merely edited.
    deleted_cv: bool
    #: ISO 8601, from the filename rather than the mtime -- a copy moved
    #: between machines keeps the time it was actually taken.
    taken: str
    #: Whose CV it is, read from inside the file.
    name: str
    headline: str
    #: Enough to tell a full CV from a nearly-empty one at a glance.
    entries: int
    bullets: int
    bytes: int
    #: Set when the file will not parse. Listed anyway: a backup you cannot
    #: read is still evidence of what existed, and hiding it is how somebody
    #: concludes the app never kept one.
    unreadable: str = ""


def _describe(path: Path) -> Backup | None:
    match = STAMPED.match(path.stem)
    if not match:
        return None
    stem, stamp = match.group("stem"), match.group("stamp")

    deleted = DELETED.match(stem)
    cv_id = deleted.group("id") if deleted else stem

    try:
        taken = datetime.strptime(stamp, "%Y%m%d-%H%M%S").isoformat(timespec="seconds")
    except ValueError:
        return None

    size = path.stat().st_size
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return Backup(
            id=path.stem, cv_id=cv_id, deleted_cv=bool(deleted), taken=taken,
            name="", headline="", entries=0, bullets=0, bytes=size,
            unreadable=f"This file will not parse: {exc}",
        )

    basics = raw.get("basics") or {}
    entries = 0
    bullets = 0
    for section in ("experience", "projects", "education"):
        rows = raw.get(section) or []
        if isinstance(rows, list):
            entries += len(rows)
            for row in rows:
                if isinstance(row, dict) and isinstance(row.get("bullets"), list):
                    bullets += len(row["bullets"])

    return Backup(
        id=path.stem,
        cv_id=cv_id,
        deleted_cv=bool(deleted),
        taken=taken,
        name=str(basics.get("name") or "").strip(),
        headline=str(basics.get("headline") or "").strip(),
        entries=entries,
        bullets=bullets,
        bytes=size,
    )


def path_for(backup_id: str) -> Path:
    """The file for an id, refusing anything that is not one of ours.

    Ids come from ``list_backups`` and go back out over HTTP, so they make the
    round trip through a request and are checked on the way back in.
    """
    if not backup_id or "/" in backup_id or "\\" in backup_id or ".." in backup_id:
        raise BackupError(f"{backup_id!r} is not a backup id.")
    path = BACKUP_DIR / f"{backup_id}.json"
    if not path.exists():
        raise BackupError("That backup is no longer here.")
    return path


def list_backups() -> list[Backup]:
    """Every copy on disk, newest first."""
    if not BACKUP_DIR.exists():
        return []
    found = [_describe(p) for p in BACKUP_DIR.glob("*.json")]
    return sorted((b for b in found if b), key=lambda b: b.taken, reverse=True)


def read_backup(backup_id: str) -> dict:
    """The profile inside a backup, for showing before restoring."""
    path = path_for(backup_id)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BackupError(f"That backup will not parse: {exc}") from exc


def restore(backup_id: str, name: str = "") -> str:
    """Copy a backup into a new CV and return its id.

    Deliberately additive. See the module docstring: recovery must not be
    something you can lose work to.
    """
    from . import cvs

    raw = read_backup(backup_id)
    described = _describe(path_for(backup_id))
    label = name.strip() or _restored_name(described)

    cv = cvs.create(label)
    cvs.path_for(cv.id).write_text(
        json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return cv.id


def _restored_name(backup: Backup | None) -> str:
    if backup is None:
        return "Restored CV"
    when = backup.taken[:16].replace("T", " ")
    who = backup.name or "Restored CV"
    return f"{who} ({when})"
