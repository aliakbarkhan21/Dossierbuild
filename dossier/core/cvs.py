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

**What is per-CV and what is not.** The facts are, and so is the design: it
was one file for all of them right up until somebody kept two CVs for two
different people and setting a typeface on one silently reset the other. So is
the focus tag a CV opens with. ``duplicate`` copies all three together, because
a design whose section order refers to a profile's custom sections is only
valid against the profile it was written for.

Not per-CV: the applications, the saved versions and the letters. Those are a
record of a job search rather than of a document, and a letter filed against an
application should not vanish because you switched CV to write another one.

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

#: The route caps a name at 80 characters. A name suggested here that overflowed
#: it would be refused by the very endpoint that asked for it, so suggestions
#: are built to fit.
NAME_MAX = 80


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


def duplicate(cv_id: str, name: str = "") -> CV:
    """Copy a CV -- its facts, its design and its focus -- and open the copy.

    This is what "a work CV and an education CV" asks for. Those two documents
    share a life and differ in emphasis, so starting the second from the first
    is starting from almost all of it; starting from ``create`` is retyping a
    history you have already typed once.

    **The copy is never auto-named.** ``adopt_profile_name`` renames any CV
    still carrying a generated name every time a profile is saved into it, so
    an auto-named copy would snap back to the person's own name at the next
    autosave and leave two rows in the switcher reading the same words. Naming
    it is what makes it a second document rather than a second copy of the
    first, which is why the flag is cleared here whether or not a name was
    supplied.

    Ordered so nothing is ever half-made: the profile is on disk, then the
    design, and only then the single atomic index write that both lists the
    copy and makes it active. ``create`` cannot be reused for this -- it flips
    ``active`` in the same write that creates the placeholder, so a failure
    during the copy would leave you standing on an empty CV wearing the copy's
    name. An interruption here leaves an unreferenced file in ``data/cvs``,
    which nobody ever sees.
    """
    data = _index()
    entries = _entries(data)
    source = next((cv for cv in entries if cv.id == cv_id), None)
    if source is None:
        raise CVError("That CV is not in this data directory.")

    new_id = uuid.uuid4().hex[:12]
    CVS_DIR.mkdir(parents=True, exist_ok=True)
    src_path = path_for(source.id)
    dst_path = path_for(new_id)
    if src_path.exists():
        # Copied byte for byte, like `_adopt`, and without parsing it first. A
        # profile too broken to read is still a profile, and the registry is
        # not the place that decides which documents deserve to be copied.
        shutil.copy2(src_path, dst_path)
    else:
        # A CV whose file somebody removed by hand is an empty CV, and an empty
        # copy is the honest answer -- more use than an error about a file no
        # one deleted on purpose.
        dst_path.write_text('{"schema_version": 4}\n', encoding="utf-8")

    _copy_design(source.id, new_id)

    now = _now()
    chosen = (name or "").strip()[:NAME_MAX]
    cv = CV(
        id=new_id,
        name=chosen or _copy_name(source.name, {row.name for row in entries}),
        created=now,
        updated=now,
        auto_named=False,
        focus=source.focus,
    )
    data["cvs"] = [*data["cvs"], cv.as_dict()]  # type: ignore[list-item]
    data["active"] = new_id
    _write_index(data)
    return cv


def _copy_name(source: str, taken: set[str]) -> str:
    """"X (copy)", and then "X (copy 2)".

    Two copies of one CV is precisely the case this feature exists for, and a
    list whose rows read the same words is a list nobody can choose from.
    """
    # The *stem* is trimmed to fit, never the finished string. Truncating the
    # whole candidate would cut off the "(copy 2)" that makes each one
    # different, and the loop below would then propose the same name for ever.
    # " (copy 999)" is eleven characters.
    stem = source[: NAME_MAX - 12].rstrip()
    candidate = f"{stem} (copy)"
    number = 2
    while candidate in taken:
        candidate = f"{stem} (copy {number})"
        number += 1
    return candidate


def _copy_design(src_id: str, dst_id: str) -> None:
    """Carry the look across with the facts.

    Imported inside the function for the reason ``design_path`` gives for doing
    the same in reverse: that module reaches back into this one for the active
    id, and a module-level import in either direction makes ``core`` depend on
    ``render``.

    A source with no design file of its own is inheriting the legacy shared
    one, and so will the copy -- there is nothing to write, and writing the
    resolved defaults out would freeze a look that is meant to keep following.
    """
    from ..render.design import design_path

    src = design_path(src_id)
    if not src.exists():
        return
    try:
        dst = design_path(dst_id)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    except OSError:
        # A designs directory that will not take a write should cost a typeface
        # you can set again, not the copy of the CV you asked for.
        pass


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
