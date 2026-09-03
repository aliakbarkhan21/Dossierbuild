"""Reading and writing the master profile.

Three jobs, in order of how much they matter:

1. **Never lose the file.** The master profile is hand-typed data that exists
   nowhere else. Writes are atomic and every save leaves a timestamped backup.
2. **Never fail to load an older file.** ``migrate`` upgrades a profile written
   by an earlier version of the schema before validation runs, so adding a
   field later does not strand the data already entered.
3. **Fail readably.** A malformed profile produces a sentence a person can act
   on, not a Pydantic traceback.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

from .ids import new_id
from .schema import SCHEMA_VERSION, LIST_SECTIONS, Profile

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent
DATA_DIR = PROJECT_ROOT / "data"
PROFILE_PATH = DATA_DIR / "profile.json"
BACKUP_DIR = DATA_DIR / "backups"
BACKUPS_TO_KEEP = 15


class ProfileError(Exception):
    """A profile file exists but could not be loaded."""


# --------------------------------------------------------------------------
# Migration
# --------------------------------------------------------------------------

# Each entry upgrades a raw dict from version N to version N+1, and the loader
# walks the chain before validation runs -- so a profile written months ago
# opens without being re-typed.


def _v1_to_v2(raw: dict[str, Any]) -> dict[str, Any]:
    """Phase 2 added ``basics.photo``: a file name for templates that use one.

    The field has a default, so validation would accept a version-1 file
    untouched. The migration exists anyway because the version number is what
    tells a future reader which shape a file is in, and a silent gap in the
    chain is how that guarantee gets lost.
    """
    basics = raw.setdefault("basics", {})
    basics.setdefault("photo", "")
    raw["schema_version"] = 2
    return raw


MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {1: _v1_to_v2}


def migrate(raw: dict[str, Any]) -> dict[str, Any]:
    """Bring a raw profile dict up to the current schema version."""
    version = raw.get("schema_version", 1)
    if not isinstance(version, int):
        raise ProfileError(f"schema_version should be a whole number, found {version!r}.")
    if version > SCHEMA_VERSION:
        raise ProfileError(
            f"This profile was written by a newer version of Dossierbuild "
            f"(schema {version}, this build understands {SCHEMA_VERSION})."
        )
    while version < SCHEMA_VERSION:
        step = MIGRATIONS.get(version)
        if step is None:
            raise ProfileError(f"No migration available from schema version {version}.")
        raw = step(raw)
        version = raw.get("schema_version", version + 1)
    return raw


# --------------------------------------------------------------------------
# Id hygiene
# --------------------------------------------------------------------------


def dedupe_ids(profile: Profile) -> list[str]:
    """Give a fresh id to anything sharing one, returning the ids reassigned.

    Ids are supposed to be unique across the document, which matters because
    the tailoring step in phase 3 addresses bullets by id alone. Duplicates can
    creep in from hand-editing, copy-pasting an entry, or an AI import that
    echoes an id twice. Repairing on load is cheap insurance.
    """
    seen: set[str] = set()
    reassigned: list[str] = []

    def claim(obj: Any, prefix: str) -> None:
        if obj.id in seen:
            old = obj.id
            obj.id = new_id(prefix)
            reassigned.append(old)
        seen.add(obj.id)

    claim(profile.summary, "blt")
    for link in profile.basics.links:
        claim(link, "lnk")
    prefixes = {
        "experience": "exp",
        "projects": "prj",
        "education": "edu",
        "skills": "skg",
        "certifications": "crt",
        "awards": "awd",
    }
    for section in LIST_SECTIONS:
        for entry in getattr(profile, section):
            claim(entry, prefixes[section])
            for block in getattr(entry, "bullets", []):
                claim(block, "blt")
    return reassigned


# --------------------------------------------------------------------------
# Load / save
# --------------------------------------------------------------------------


def format_validation_error(exc: ValidationError) -> str:
    """Turn a Pydantic error into something worth showing a person."""
    lines = []
    for err in exc.errors():
        location = " > ".join(str(part) for part in err["loc"]) or "profile"
        message = err["msg"]
        if err["type"] == "string_pattern_mismatch":
            message = 'should be a month written as "YYYY-MM", for example "2025-06"'
        elif err["type"] == "extra_forbidden":
            message = "is not a field this schema knows about"
        lines.append(f"  - {location}: {message}")
    count = len(lines)
    header = f"{count} problem{'s' if count != 1 else ''} in the profile file:"
    return "\n".join([header, *lines])


def load_profile(path: Path | None = None) -> Profile:
    """Load and validate the profile, returning a blank one if none exists."""
    path = path or PROFILE_PATH
    if not path.exists():
        return Profile.empty()

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProfileError(
            f"{path.name} is not valid JSON (line {exc.lineno}, column {exc.colno}): {exc.msg}"
        ) from exc

    if not isinstance(raw, dict):
        raise ProfileError(f"{path.name} should contain a JSON object at the top level.")

    raw = migrate(raw)

    try:
        profile = Profile.model_validate(raw)
    except ValidationError as exc:
        raise ProfileError(format_validation_error(exc)) from exc

    dedupe_ids(profile)
    return profile


def save_profile(profile: Profile, path: Path | None = None, *, backup: bool = True) -> Path:
    """Write the profile to disk atomically, keeping a timestamped backup.

    The write goes to a temporary file in the same directory and is then moved
    into place with ``os.replace``, which is atomic on both Windows and POSIX.
    Without this, a crash or a full disk part-way through writing would leave a
    truncated profile.json -- and the truncated file would be the only copy.
    """
    path = path or PROFILE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    if backup and path.exists():
        _write_backup(path)

    payload = json.dumps(profile.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)
    return path


def _write_backup(path: Path) -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(path, BACKUP_DIR / f"{path.stem}-{stamp}.json")
    backups = sorted(BACKUP_DIR.glob(f"{path.stem}-*.json"))
    for stale in backups[:-BACKUPS_TO_KEEP]:
        stale.unlink(missing_ok=True)
