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
from typing import Any, Callable, Iterator

from pydantic import ValidationError

from .ids import new_id
from .schema import SCHEMA_VERSION, LIST_SECTIONS, Profile

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_ROOT.parent

# Where everything of the user's lives: the profile, its backups, the
# portrait, the saved design, UI preferences. Overridable by environment so a
# container can mount a volume at it -- the one piece of configuration that
# has to exist before the app can be deployed anywhere.
DATA_DIR = Path(os.environ.get("DOSSIER_DATA_DIR") or PROJECT_ROOT / "data")
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


def _v2_to_v3(raw: dict[str, Any]) -> dict[str, Any]:
    """Phase 3 split recognitions in two.

    ``awards`` kept its key and gained the heading "Honors"; ``achievements``
    is new and holds outcomes you produced rather than prizes you were given.
    Nothing moves between them automatically -- a machine cannot tell "Dean's
    List" from "Ranked 3rd of 400 teams" reliably, and guessing wrong would
    silently reclassify someone's record.
    """
    raw.setdefault("achievements", [])
    raw["schema_version"] = 3
    return raw


def _v3_to_v4(raw: dict[str, Any]) -> dict[str, Any]:
    """Bullets and skill groups gained ``tags``: which job families they suit.

    Both fields default to an empty list, so validation would accept a
    version-3 file untouched. The migration exists anyway, for the reason
    ``_v1_to_v2`` gives: the version number is what tells a future reader
    which shape a file is in, and a silent gap in the chain is how that
    guarantee is lost.

    Written explicitly rather than left to the defaults so that a file opened,
    saved and diffed after this upgrade shows the new field on every line it
    applies to, instead of appearing on whichever ones happened to be edited.
    """
    for block in _every_text_block(raw):
        block.setdefault("tags", [])
    for group in raw.get("skills") or []:
        if isinstance(group, dict):
            group.setdefault("tags", [])
    raw["schema_version"] = 4
    return raw


def _v4_to_v5(raw: dict[str, Any]) -> dict[str, Any]:
    """Sections the eight built-in ones have no name for.

    A resume heading that maps onto none of experience, projects, education,
    skills, certifications, honors or achievements used to be read and then
    dropped: the importer had nowhere to put it, so "Governance, Security and
    Risk Leadership" simply did not arrive. ``sections`` is where it goes now,
    heading and words kept as written.

    Nothing moves into it. An existing profile gains an empty list, because
    everything already in it was sorted into a real section by a person or by
    an import that person reviewed, and second-guessing that afterwards would
    reclassify a record nobody asked us to touch.
    """
    raw.setdefault("sections", [])
    raw["schema_version"] = 5
    return raw


def _v5_to_v6(raw: dict[str, Any]) -> dict[str, Any]:
    """Dates may be words.

    Every date was a validated "YYYY-MM" or "YYYY". Resumes say "Summer
    2024", "Expected 2026" and "Ongoing", and a field that refuses those
    makes people misstate their own history to satisfy a regex.

    Nothing changes on disk -- a widening needs no rewrite, and every date
    already stored is still one the app can read and reformat. The step
    exists because the *shape* changed, and the version number is what tells
    a future reader which shape a file is in. A file saved by this build may
    contain a date an earlier build would refuse, and the version is how it
    finds that out rather than by failing to load one entry.
    """
    raw["schema_version"] = 6
    return raw


def _every_text_block(raw: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Every rewritable block in a raw dict: the summary and every bullet."""
    summary = raw.get("summary")
    if isinstance(summary, dict):
        yield summary
    for section in ("experience", "projects", "education", "sections"):
        for entry in raw.get(section) or []:
            if not isinstance(entry, dict):
                continue
            for bullet in entry.get("bullets") or []:
                if isinstance(bullet, dict):
                    yield bullet


MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {
    1: _v1_to_v2,
    2: _v2_to_v3,
    3: _v3_to_v4,
    4: _v4_to_v5,
    5: _v5_to_v6,
}


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
    """Give a fresh id to anything sharing one or missing one.

    Ids are supposed to be unique across the document, which matters because
    the tailoring step addresses bullets by id alone. Duplicates can creep in
    from hand-editing, copy-pasting an entry, or an AI import that echoes an
    id twice.

    **Blank counts as missing.** The editor sends ``id: ""`` for a row the
    person has just added, on the understanding that the server mints the real
    one -- the store even says so where it reads the profile back. It did not:
    an empty id is not a duplicate of anything, so a single new entry kept it
    forever. That was invisible for years because nothing addressed an entry
    by its id.

    A custom section made it visible immediately, because there the id *is*
    the key the design orders, hides and renames by. A section with no id
    could not be moved, hidden or renamed, and the row for it sat permanently
    in its own rename box -- ``editing === key`` is true for every row when
    both sides are "".
    """
    seen: set[str] = set()
    reassigned: list[str] = []

    def claim(obj: Any, prefix: str) -> None:
        if not obj.id or obj.id in seen:
            old = obj.id
            obj.id = new_id(prefix)
            reassigned.append(old)
        seen.add(obj.id)

    # The summary keeps its well-known id rather than being minted a new one:
    # saved versions and accepted rewrites reference it by name.
    if not profile.summary.id:
        profile.summary.id = "sum_main"
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
        "achievements": "ach",
        "sections": "cus",
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


def default_profile_path() -> Path:
    """Where the profile lives when the caller does not say.

    The CV in front of the user, which is a file in ``data/cvs``. Resolved
    through one function rather than a constant because there is now more than
    one profile in a data directory, and every existing caller of
    ``load_profile()`` should follow the switch without knowing about it.

    Imported inside the function on purpose: ``cvs`` needs ``DATA_DIR`` and
    ``PROFILE_PATH`` from this module, so a top-level import either way is a
    cycle.
    """
    from .cvs import active_path

    return active_path()


def load_profile(path: Path | None = None) -> Profile:
    """Load and validate the profile, returning a blank one if none exists."""
    path = path or default_profile_path()
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
    path = path or default_profile_path()
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
