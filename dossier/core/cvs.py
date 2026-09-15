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

**A CV is named in two halves.** ``person`` is whose it is and ``label`` is
which of theirs it is. One field held both until five people with three CVs
each produced fifteen rows, five of them reading the same name, and
``duplicate`` had to invent "(copy 2)" suffixes to tell apart what was really
two different documents. The person comes free -- ``adopt_profile_name`` takes
it from the profile as it is saved -- and the label is the only thing anybody
types. The switcher then lists people, and one person's CVs open beside them.

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
#: v1 named a CV in one field. v2 splits that into who it belongs to and which
#: of their CVs it is -- see ``_migrate_index``.
INDEX_VERSION = 2

#: A name we chose rather than one the user did, and so one we may replace.
DEFAULT_NAME_PREFIX = "CV "

#: What separates the two halves when a CV has to be named in one line.
NAME_JOIN = " — "

#: The route caps a name at 80 characters. A name suggested here that overflowed
#: it would be refused by the very endpoint that asked for it, so suggestions
#: are built to fit.
NAME_MAX = 80


class CVError(RuntimeError):
    """Something is wrong with the CV registry, said in a sentence."""


@dataclass(frozen=True)
class CV:
    id: str
    #: Whose CV this is. Follows the profile's ``basics.name`` while
    #: ``auto_named``, which is how five people's CVs sort themselves into five
    #: groups without anybody typing a name twice.
    person: str
    #: Which of that person's CVs this is -- "Education", "Professional". Empty
    #: means the one they started with, and is the common case: somebody with a
    #: single CV should never have to invent a word for it.
    label: str
    created: str
    updated: str
    #: True while the *person* is still one we took from the profile, so a
    #: profile saved into this CV may keep claiming it. The label is never
    #: automatic -- it is the half the user chose. See ``adopt_profile_name``.
    auto_named: bool
    #: The focus tag this CV opens with. A *default*, not a lock: the picker
    #: on the Resume screen still overrides it for one printing. Binding the
    #: focus rigidly to the CV would undo the reason focus tags exist -- one
    #: profile printed several ways without a second CV to keep in step.
    focus: str = ""

    @property
    def name(self) -> str:
        """The whole thing on one line, for a toast or a confirmation.

        The switcher shows the two halves on two lines and never needs this.
        """
        return f"{self.person}{NAME_JOIN}{self.label}" if self.label else self.person

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "person": self.person,
            "label": self.label,
            # Written as well as derived, and deliberately. A build from before
            # the split reads `name` and nothing else; keeping it here means a
            # rollback finds a list it can still show, which is the same
            # bargain `_adopt` strikes with `data/profile.json`. Nothing reads
            # it back -- `_entries` prefers `person`.
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
    person = "My CV"
    # "My CV" is a placeholder, not a choice, so it stays claimable: on a
    # fresh install the first profile saved gives this CV its person. A name
    # read out of an existing profile below is the user's own and is not.
    auto = True
    if PROFILE_PATH.exists():
        shutil.copy2(PROFILE_PATH, path_for(cv_id))
        try:
            raw = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
            existing = str(raw.get("basics", {}).get("name", "")).strip()
            if existing:
                person = existing
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
            CV(
                id=cv_id,
                person=person,
                # No label. The first CV of the only person here does not need
                # a word to tell it apart from CVs that do not exist yet.
                label="",
                created=now,
                updated=now,
                auto_named=auto,
                focus="",
            ).as_dict()
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
    return _migrate_index(data)


def _migrate_index(data: dict[str, object]) -> dict[str, object]:
    """Bring an older index up to the shape the rest of this module expects.

    v1 gave a CV one name field, and everything anyone ever put in it was a
    person's name -- there was nowhere else to put one. So the whole value
    becomes ``person`` and the label starts empty, which reads as "the CV they
    already had" and needs no word invented for it.

    Done in memory on every read and written back by the next operation that
    writes anything. Rewriting the file here would mean a rollback met a v2
    index the moment somebody merely opened the app.
    """
    if int(data.get("version") or 1) >= INDEX_VERSION:
        return data
    for row in data.get("cvs", []):  # type: ignore[union-attr]
        if isinstance(row, dict) and "person" not in row:
            row["person"] = row.get("name") or "Untitled"
            row["label"] = ""
    data["version"] = INDEX_VERSION
    return data


def _entries(data: dict[str, object]) -> list[CV]:
    out: list[CV] = []
    for row in data["cvs"]:  # type: ignore[union-attr]
        if not isinstance(row, dict) or not row.get("id"):
            continue
        out.append(
            CV(
                id=str(row["id"]),
                # `name` is the v1 spelling and the fallback for a row that
                # somehow reached here unmigrated.
                person=str(row.get("person") or row.get("name") or "Untitled"),
                label=str(row.get("label") or ""),
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


def create(person: str | None = None, label: str = "") -> CV:
    """Start a blank CV for somebody new and switch to it.

    A *new person*, not another CV for one who is already here -- that is what
    ``duplicate`` is for, and it is the commoner request. So no label: the
    first CV of a person does not need a word telling it apart from CVs that
    do not exist.

    Nothing is done to the one being left. It is a file on disk that autosave
    has already written; not touching it is what "the previous one is saved"
    means here, and it is why this needs no confirmation -- there is nothing
    to lose and one click to go back.
    """
    data = _index()
    entries = _entries(data)
    cv_id = uuid.uuid4().hex[:12]
    now = _now()
    chosen = (person or "").strip()[:NAME_MAX]
    cv = CV(
        id=cv_id,
        person=chosen or f"{DEFAULT_NAME_PREFIX}{len(entries) + 1}",
        label=label.strip()[:NAME_MAX],
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


def duplicate(cv_id: str, label: str = "") -> CV:
    """Another CV for the same person -- facts, design and focus -- and open it.

    This is what "a work CV and an education CV" asks for. Those two documents
    share a life and differ in emphasis, so starting the second from the first
    is starting from almost all of it; starting from ``create`` is retyping a
    history you have already typed once.

    The copy keeps ``source.person`` and takes a new ``label``, which is the
    whole reason the name was split in two. Before the split this had to invent
    "(copy)" and "(copy 2)" suffixes, because two CVs of one person had one
    field between them to be different in.

    **The copy is never auto-named.** ``adopt_profile_name`` re-takes the
    person from the profile on every save for any CV still flagged, and both
    copies carry the same profile name -- so leaving the flag set would drag
    the copy back into the group under a name the user did not choose. The
    label it is given here is the user's, and stays.

    Ordered so nothing is ever half-made: the profile is on disk, then the
    design, and only then the single atomic index write that both lists the
    copy and makes it active. ``create`` cannot be reused for this -- it flips
    ``active`` in the same write that creates the placeholder, so a failure
    during the copy would leave you standing on an empty CV wearing the copy's
    label. An interruption here leaves an unreferenced file in ``data/cvs``,
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
    chosen = (label or "").strip()[:NAME_MAX]
    cv = CV(
        id=new_id,
        person=source.person,
        label=chosen
        or _copy_label(
            source.label,
            # Only this person's labels. "Education" under one name has no
            # quarrel with "Education" under another, and counting across
            # everybody would hand somebody a "Copy 4" for their first copy.
            {row.label for row in entries if row.person == source.person},
        ),
        created=now,
        updated=now,
        auto_named=False,
        focus=source.focus,
    )
    data["cvs"] = [*data["cvs"], cv.as_dict()]  # type: ignore[list-item]
    data["active"] = new_id
    _write_index(data)
    return cv


def _copy_label(source: str, taken: set[str]) -> str:
    """A label for a copy nobody has named yet. "Copy", then "Copy 2".

    Only a fallback. The interface asks for the label before it makes the copy,
    precisely so that this is not what ends up in the list -- somebody wanting
    a second CV wants "Education", not "Copy". It exists for a caller that does
    not ask, and for the label to still be unique when one does not.

    ``taken`` is scoped to one person by the caller, so the numbering counts
    that person's CVs rather than everybody's.
    """
    # The *stem* is trimmed to fit, never the finished string. Truncating the
    # whole candidate would cut off the " 2" that makes each one different, and
    # the loop below would then propose the same label for ever.
    stem = source[: NAME_MAX - 10].rstrip()
    candidate = f"{stem} copy".strip() if stem else "Copy"
    number = 2
    while candidate in taken:
        candidate = f"{stem} copy {number}".strip() if stem else f"Copy {number}"
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


def rename(cv_id: str, label: str) -> CV:
    """Name this one of a person's CVs. The person is not touched.

    An empty label is allowed and means "their main one" -- the state every CV
    starts in. Clearing a label is a thing somebody down to one CV would
    reasonably want, and refusing it would leave them stuck with a word that
    no longer distinguishes anything.
    """
    return _update(cv_id, label=label.strip()[:NAME_MAX])


def rename_person(old: str, new: str) -> int:
    """Rename somebody across every CV of theirs, returning how many moved.

    The person is what groups the list, so renaming it on one CV and not the
    others would split a group in half -- somebody's three CVs becoming two
    entries under two spellings of one name, which is the failure this whole
    structure exists to prevent. That is why this takes a person rather than a
    CV id, and why it is not reachable from the panel that renames a label.

    ``auto_named`` is cleared on every row it touches: a name typed by hand is
    not one ``adopt_profile_name`` may overwrite at the next save.

    One write. A loop calling ``_update`` per row would read, modify and write
    the index once per CV, and an interruption partway would leave exactly the
    half-renamed group this function exists to make impossible.
    """
    old = old.strip()
    new = new.strip()[:NAME_MAX]
    if not new:
        raise CVError("A person needs a name.")
    data = _index()
    if not any(cv.person == old for cv in _entries(data)):
        raise CVError(f"Nobody here is called {old!r}.")

    now = _now()
    moved = 0
    for row in data["cvs"]:  # type: ignore[union-attr]
        if isinstance(row, dict) and (row.get("person") or row.get("name")) == old:
            row["person"] = new
            row["auto_named"] = False
            row["updated"] = now
            # The flat `name` is written for a rollback to read; keep it honest.
            row["name"] = f"{new}{NAME_JOIN}{row['label']}" if row.get("label") else new
            moved += 1
    _write_index(data)
    return moved


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
    """Let a CV take its *person* from the profile saved into it.

    This is what makes the grouping free. Save a profile for Priya and her CV
    files itself under Priya without anybody typing the name a second time, so
    five people sort themselves into five groups as their profiles are written.

    Only the person, and only while it is still one we generated. The label is
    never touched -- that half is always the user's word, and somebody who
    called a CV "Research" does not want it renamed because they corrected a
    typo in their own name. Somebody who named nothing should not be left
    picking "CV 2" out of a list of four.
    """
    name = name.strip()[:NAME_MAX]
    if not name:
        return
    data = _index()
    target = cv_id or str(data.get("active") or "")
    for cv in _entries(data):
        if cv.id == target and cv.auto_named:
            _update(target, person=name, auto_named=True)
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
    person: str | None = None,
    label: str | None = None,
    auto_named: bool | None = None,
    focus: str | None = None,
) -> CV:
    data = _index()
    found: CV | None = None
    rows = []
    for row in data["cvs"]:  # type: ignore[union-attr]
        if isinstance(row, dict) and row.get("id") == cv_id:
            if person is not None:
                row["person"] = person
            if label is not None:
                row["label"] = label
            if auto_named is not None:
                row["auto_named"] = auto_named
            if focus is not None:
                row["focus"] = focus
            row["updated"] = _now()
            found = CV(
                id=cv_id,
                person=str(row.get("person") or row.get("name") or "Untitled"),
                label=str(row.get("label") or ""),
                created=str(row.get("created") or ""),
                updated=str(row["updated"]),
                auto_named=bool(row.get("auto_named", False)),
                focus=str(row.get("focus") or ""),
            )
            # The flat `name` exists only for a build that predates the split.
            # Rewritten from the halves rather than edited, so it cannot drift.
            row["name"] = found.name
        rows.append(row)
    if found is None:
        raise CVError("That CV is not in this data directory.")
    data["cvs"] = rows
    _write_index(data)
    return found
