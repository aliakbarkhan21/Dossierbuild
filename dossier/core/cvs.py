"""More than one CV in the same data directory.

The app was built around a single master profile, and that is still the right
default: one set of facts, tailored per posting by the design and the focus
tags rather than by keeping several near-identical documents in step. But a
graduate applying for a research post and a support role is not tailoring one
document -- those are two different accounts of a life, and forcing them into
one profile means every edit to either risks the other.

So: a small registry beside the profile. Each CV is a profile file of exactly
the format ``storage`` already reads and writes, so every migration, every
validation and the atomic write apply unchanged; the only new thing is which
file ``load_profile()`` reaches for when nobody names one.

**What is per-CV and what is not.** The facts are. The design is not -- it is
a house style, and someone who has settled on a typeface wants it on both
documents; the design panel is where that gets changed, per printing. Neither
are the applications, the saved versions or the letters: those are a record of
a job search, not of a document, and a letter filed against an application
should not vanish because you switched CV to write another one.

**The previous CV is saved by never being touched.** Autosave has already
written it before the switch -- there is no unsaved buffer here to flush --
which is why creating one asks nothing and loses nothing.
"""

from __future__ import annotations

import json
import os
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .storage import DATA_DIR, PROFILE_PATH

CVS_DIR = DATA_DIR / "cvs"
INDEX_PATH = DATA_DIR / "cvs.json"
INDEX_VERSION = 1

#: A name we chose rather than one the user did, and so one we may replace.
DEFAULT_NAME_PREFIX = "CV "


class CVError(RuntimeError):
    """Something is wrong with the CV registry, said in a sentence."""


@dataclass(frozen=True)
class CV:
    id: str
    name: str
    created: str
    updated: str
    #: True while the name is still one we generated, so a profile saved into
    #: this CV may claim it. See ``adopt_profile_name``.
    auto_named: bool
    #: The focus tag this CV opens with. A *default*, not a lock: the picker
    #: on the Resume screen still overrides it for one printing. Binding the
    #: focus rigidly to the CV would undo the reason focus tags exist -- one
    #: profile printed several ways without a second CV to keep in step.
    focus: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "created": self.created,
            "updated": self.updated,
            "auto_named": self.auto_named,
            "focus": self.focus,
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def path_for(cv_id: str) -> Path:
    # The id is generated here and never taken from a request, but a path
    # built from an identifier is worth pinning down anyway: anything with a
    # separator or a dot in it is not one of ours.
    if not cv_id or "/" in cv_id or "\\" in cv_id or "." in cv_id:
        raise CVError(f"{cv_id!r} is not a CV id.")
    return CVS_DIR / f"{cv_id}.json"


def _write_index(data: dict[str, object]) -> None:
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    tmp = INDEX_PATH.with_suffix(".json.tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, INDEX_PATH)


def _adopt() -> dict[str, object]:
    """First run: make the profile that is already here into CV one.

    Copied rather than moved, and the original left where it is. If this
    version is ever rolled back, ``data/profile.json`` is still the profile it
    was -- which matters more than a duplicate file, because the alternative
    is someone's only CV living somewhere the old build cannot find.
    """
    CVS_DIR.mkdir(parents=True, exist_ok=True)
    cv_id = uuid.uuid4().hex[:12]
    name = "My CV"
    # "My CV" is a placeholder, not a choice, so it stays claimable: on a
    # fresh install the first profile saved gives this CV its name. A name
    # read out of an existing profile below is the user's own and is not.
    auto = True
    if PROFILE_PATH.exists():
        shutil.copy2(PROFILE_PATH, path_for(cv_id))
        try:
            raw = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
            existing = str(raw.get("basics", {}).get("name", "")).strip()
            if existing:
                name = existing
                auto = False
        except (json.JSONDecodeError, AttributeError, TypeError):
            # A profile too broken to read its own name is still a profile
            # worth keeping; `load_profile` will report what is wrong with it.
            pass

    now = _now()
    data = {
        "version": INDEX_VERSION,
        "active": cv_id,
        "cvs": [
            CV(id=cv_id, name=name, created=now, updated=now, auto_named=auto, focus="").as_dict()
        ],
    }
    _write_index(data)
    return data


def _index() -> dict[str, object]:
    if not INDEX_PATH.exists():
        return _adopt()
    try:
        data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CVError(
            f"cvs.json is not valid JSON (line {exc.lineno}, column {exc.colno})."
        ) from exc
    if not isinstance(data, dict) or not isinstance(data.get("cvs"), list):
        raise CVError("cvs.json should hold an object with a list of CVs.")
    if not data["cvs"]:
        return _adopt()
    return data


def _entries(data: dict[str, object]) -> list[CV]:
    out: list[CV] = []
    for row in data["cvs"]:  # type: ignore[union-attr]
        if not isinstance(row, dict) or not row.get("id"):
            continue
        out.append(
            CV(
                id=str(row["id"]),
                name=str(row.get("name") or "Untitled"),
                created=str(row.get("created") or ""),
                updated=str(row.get("updated") or ""),
                auto_named=bool(row.get("auto_named", False)),
                focus=str(row.get("focus") or ""),
            )
        )
    return out


def list_cvs() -> tuple[list[CV], str]:
    """Every CV, newest last, and the id of the one in front of the user."""
    data = _index()
    entries = _entries(data)
    active = str(data.get("active") or "")
    if active not in {cv.id for cv in entries}:
        active = entries[0].id
        data["active"] = active
        _write_index(data)
    return entries, active


def active_id() -> str:
    return list_cvs()[1]


def active_path() -> Path:
    """Where ``load_profile()`` and ``save_profile()`` go when nobody says."""
    return path_for(active_id())


def create(name: str | None = None) -> CV:
    """Start a blank CV and switch to it.

    Nothing is done to the one being left. It is a file on disk that autosave
    has already written; not touching it is what "the previous one is saved"
    means here, and it is why this needs no confirmation -- there is nothing
    to lose and one click to go back.
    """
    data = _index()
    entries = _entries(data)
    cv_id = uuid.uuid4().hex[:12]
    now = _now()
    chosen = (name or "").strip()
    cv = CV(
        id=cv_id,
        name=chosen or f"{DEFAULT_NAME_PREFIX}{len(entries) + 1}",
        created=now,
        updated=now,
        auto_named=not chosen,
        focus="",
    )
    CVS_DIR.mkdir(parents=True, exist_ok=True)
    # An empty file rather than no file: `load_profile` copes with a missing
    # one, but a CV you can see in a list and cannot find on disk is a worse
    # thing to debug than one extra write.
    path_for(cv_id).write_text('{"schema_version": 4}\n', encoding="utf-8")

    data["cvs"] = [*data["cvs"], cv.as_dict()]  # type: ignore[list-item]
    data["active"] = cv_id
    _write_index(data)
    return cv


def switch(cv_id: str) -> CV:
    data = _index()
    entries = _entries(data)
    match = next((cv for cv in entries if cv.id == cv_id), None)
    if match is None:
        raise CVError("That CV is not in this data directory.")
    data["active"] = cv_id
    _write_index(data)
    return match


def rename(cv_id: str, name: str) -> CV:
    name = name.strip()
    if not name:
        raise CVError("A CV needs a name.")
    return _update(cv_id, name=name, auto_named=False)


def delete(cv_id: str) -> str:
    """Remove a CV, returning the id now active. The last one cannot go."""
    data = _index()
    entries = _entries(data)
    if len(entries) <= 1:
        raise CVError("This is the only CV. Clear it instead of deleting it.")
    if not any(cv.id == cv_id for cv in entries):
        raise CVError("That CV is not in this data directory.")

    path = path_for(cv_id)
    if path.exists():
        # Kept, not unlinked. Deleting a CV is the one action here that cannot
        # be undone from the interface, so the file goes where the profile
        # backups go and can be brought back by hand.
        graveyard = DATA_DIR / "backups"
        graveyard.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.move(str(path), str(graveyard / f"deleted-cv-{cv_id}-{stamp}.json"))

    data["cvs"] = [row for row in data["cvs"] if row.get("id") != cv_id]  # type: ignore[union-attr]
    if data.get("active") == cv_id:
        data["active"] = _entries(data)[0].id
    _write_index(data)
    return str(data["active"])


def adopt_profile_name(name: str, cv_id: str | None = None) -> None:
    """Let a CV take its name from the profile saved into it.

    Only while the name is still one we generated. Someone who has named a CV
    "Research" does not want it renamed every time they correct a typo in
    their own name, and someone who has not named it at all should not be left
    picking "CV 2" out of a list of four.
    """
    name = name.strip()
    if not name:
        return
    data = _index()
    target = cv_id or str(data.get("active") or "")
    for cv in _entries(data):
        if cv.id == target and cv.auto_named:
            _update(target, name=name, auto_named=True)
            return


def touch(cv_id: str | None = None) -> None:
    """Record that the active CV changed, for the "last edited" column."""
    data = _index()
    _update(cv_id or str(data.get("active") or ""))


def set_focus(cv_id: str, focus: str) -> CV:
    """Which focus this CV opens with. Empty means "print everything"."""
    from .schema import normalise_tag

    return _update(cv_id, focus=normalise_tag(focus))


def _update(
    cv_id: str,
    *,
    name: str | None = None,
    auto_named: bool | None = None,
    focus: str | None = None,
) -> CV:
    data = _index()
    found: CV | None = None
    rows = []
    for row in data["cvs"]:  # type: ignore[union-attr]
        if isinstance(row, dict) and row.get("id") == cv_id:
            if name is not None:
                row["name"] = name
            if auto_named is not None:
                row["auto_named"] = auto_named
            if focus is not None:
                row["focus"] = focus
            row["updated"] = _now()
            found = CV(
                id=cv_id,
                name=str(row.get("name") or "Untitled"),
                created=str(row.get("created") or ""),
                updated=str(row["updated"]),
                auto_named=bool(row.get("auto_named", False)),
                focus=str(row.get("focus") or ""),
            )
        rows.append(row)
    if found is None:
        raise CVError("That CV is not in this data directory.")
    data["cvs"] = rows
    _write_index(data)
    return found
