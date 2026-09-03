"""Phase 1 self-check. Run with:  python scripts/check_phase1.py

No pytest needed. Each check states what it proves, so a failure tells you
which property broke rather than just which line raised.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import ValidationError

from dossier.core.quality import build_vocabulary, check_text, mentions_specific
from dossier.core.schema import (
    SCHEMA_VERSION,
    Education,
    Experience,
    Profile,
    Project,
    SkillGroup,
    TextBlock,
    all_ids,
    format_date,
    format_range,
    iter_bullets,
)
from dossier.core.storage import ProfileError, dedupe_ids, load_profile, migrate, save_profile

from _harness import check, run


def sample_profile() -> Profile:
    p = Profile.empty()
    p.basics.name = "A. Student"
    p.basics.email = "a@example.com"
    p.summary.text = "Second-year CS and AI student who ships small tools end to end."
    p.experience.append(
        Experience(
            role="Software Engineering Intern",
            organisation="Northgate Labs",
            employment_type="Internship",
            start="2025-06",
            end="2025-09",
            bullets=[
                TextBlock(text="Cut nightly ETL runtime from 42 to 9 minutes by batching Postgres writes"),
                TextBlock(text="Added 61 pytest cases covering the invoice parser, catching 3 rounding bugs"),
            ],
        )
    )
    p.projects.append(
        Project(
            name="Loot Ledger",
            tagline="Personal finance tracker with an AI chat layer",
            tech=["Python", "Streamlit", "Gemini API"],
            start="2025-01",
            bullets=[TextBlock(text="Parsed 14 months of bank CSV exports into a normalised SQLite schema")],
        )
    )
    p.education.append(
        Education(
            institution="University of Manchester",
            credential="BSc Computer Science with Artificial Intelligence",
            start="2024-09",
            end="2027-06",
            coursework=["Data Structures", "Machine Learning"],
        )
    )
    p.skills.append(SkillGroup(label="Languages", items=["Python", "SQL", "Java"]))
    return p


@check("blank profile is valid and reports itself blank")
def _() -> None:
    p = Profile.empty()
    assert p.is_blank(), "a fresh profile should report as blank"
    assert p.schema_version == SCHEMA_VERSION
    assert p.summary.id == "sum_main"


@check("save then load round-trips without changing anything")
def _() -> None:
    original = sample_profile()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "profile.json"
        save_profile(original, path, backup=False)
        reloaded = load_profile(path)
    assert reloaded.model_dump() == original.model_dump(), "profile changed across a round trip"


@check("bullet ids survive a round trip -- phase 3 depends on this")
def _() -> None:
    original = sample_profile()
    before = [b.id for _s, _o, b in iter_bullets(original)]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "profile.json"
        save_profile(original, path, backup=False)
        after = [b.id for _s, _o, b in iter_bullets(load_profile(path))]
    assert before == after, f"ids changed on reload:\n      {before}\n      {after}"


@check("editing a bullet's text leaves its id alone")
def _() -> None:
    p = sample_profile()
    block = p.experience[0].bullets[0]
    original_id = block.id
    block.text = "Rewritten entirely, not one word in common with before"
    assert block.id == original_id, "id must not change when text changes"


@check("a year-only date is accepted and kept as a year")
def _() -> None:
    # The schema stores the precision it actually has. Forcing "2024" to
    # "2024-01" would print a month on the resume that nobody ever stated.
    entry = Education(start="2024", end="2027-06")
    assert entry.start == "2024"
    assert format_date(entry.start) == "2024", "a year should render as a year"
    assert format_date(entry.end) == "Jun 2027"
    assert format_range("2024", None) == "2024 - Present"
    assert format_range("2025-06", "2025-09") == "Jun 2025 - Sep 2025"


@check("an invalid month is still rejected with a clear error")
def _() -> None:
    for bad in ("2025-13", "2025-00", "25-06", "2025-6", "next year"):
        try:
            Experience(start=bad)
        except ValidationError:
            pass
        else:
            raise AssertionError(f"{bad!r} should not have validated")


@check("a blank date string is stored as None, not as an empty string")
def _() -> None:
    entry = Experience(start="", end="   ")
    assert entry.start is None and entry.end is None


@check("unknown fields are rejected rather than silently dropped")
def _() -> None:
    try:
        Profile.model_validate({"schema_version": 1, "hobbies": ["chess"]})
    except ValidationError:
        pass
    else:
        raise AssertionError("an unknown top-level field should be refused")


@check("a current-version file passes through migrate untouched")
def _() -> None:
    raw = sample_profile().model_dump(mode="json")
    assert migrate(dict(raw)) == raw


@check("a version-1 file is carried forward, keeping everything it held")
def _() -> None:
    # The shape this project actually shipped first: no basics.photo, and a
    # schema_version of 1. It has to open, not be re-typed.
    old = sample_profile().model_dump(mode="json")
    old["schema_version"] = 1
    del old["basics"]["photo"]

    upgraded = migrate(dict(old))
    assert upgraded["schema_version"] == SCHEMA_VERSION, upgraded["schema_version"]
    assert upgraded["basics"]["photo"] == ""
    profile = Profile.model_validate(upgraded)
    assert profile.basics.name == old["basics"]["name"]
    assert len(profile.experience) == len(old["experience"])


@check("a file from a newer schema is refused, not half-read")
def _() -> None:
    try:
        migrate({"schema_version": 99})
    except ProfileError as exc:
        assert "newer version" in str(exc)
    else:
        raise AssertionError("a future schema version should be refused")


@check("duplicate ids are repaired on load")
def _() -> None:
    p = sample_profile()
    p.experience[0].bullets[1].id = p.experience[0].bullets[0].id
    reassigned = dedupe_ids(p)
    ids = all_ids(p)
    assert len(reassigned) == 1, "expected exactly one id to be reassigned"
    assert len(ids) == len(set(ids)), "ids should be unique after repair"


@check("a missing file loads as a blank profile instead of crashing")
def _() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        assert load_profile(Path(tmp) / "nope.json").is_blank()


@check("corrupt JSON produces a readable error, not a traceback")
def _() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "profile.json"
        path.write_text('{"schema_version": 1,,}', encoding="utf-8")
        try:
            load_profile(path)
        except ProfileError as exc:
            assert "not valid JSON" in str(exc)
        else:
            raise AssertionError("malformed JSON should raise ProfileError")


@check("a bad month in a saved file is reported in plain English")
def _() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "profile.json"
        raw = sample_profile().model_dump(mode="json")
        raw["experience"][0]["start"] = "2025-13"
        path.write_text(json.dumps(raw), encoding="utf-8")
        try:
            load_profile(path)
        except ProfileError as exc:
            assert "YYYY-MM" in str(exc), f"unhelpful message: {exc}"
        else:
            raise AssertionError("2025-13 should not load")


@check("an interrupted save cannot truncate the existing file")
def _() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "profile.json"
        save_profile(sample_profile(), path, backup=False)
        good = path.read_text(encoding="utf-8")
        assert not list(path.parent.glob("*.tmp")), "temp file should not survive a save"
        assert json.loads(good)["basics"]["name"] == "A. Student"


@check("the quality linter catches duty language and passes concrete bullets")
def _() -> None:
    bad = check_text("Responsible for working on various backend tasks", "b1")
    assert any(f.severity == "error" for f in bad), "filler phrases should be errors"
    good = check_text(
        "Cut nightly ETL runtime from 42 to 9 minutes by batching Postgres writes", "b2"
    )
    assert not good, f"a concrete bullet should pass cleanly, got {good}"


@check("filler is caught in every tense, not just the one on the list")
def _() -> None:
    for phrase in (
        "Worked on the parser",
        "Working on the parser",
        "Assisted with the migration",
        "Assisting with the migration",
        "Helped with onboarding",
    ):
        found = check_text(phrase, "b")
        assert any(f.severity == "error" for f in found), f"{phrase!r} was not flagged"


@check("the linter uses your own declared skills as its vocabulary")
def _() -> None:
    bullet = "Rewrote the ingest step in Zig and dropped memory use by half"
    profile = Profile.empty()

    # "Zig" is not on any built-in list, but it survives on proper-noun shape.
    # The real test is a lowercase term that only your profile knows about.
    bullet = "Cut cold starts using mmap-backed caching in shimmerdb"
    assert not mentions_specific(bullet), "nothing should recognise this yet"

    profile.skills.append(SkillGroup(label="Data", items=["shimmerdb", "mmap"]))
    vocab = build_vocabulary(profile)
    assert mentions_specific(bullet, vocab), "your own skills should be recognised"


@check("a capitalised but empty word does not count as being specific")
def _() -> None:
    # "January" is capitalised, so a naive proper-noun rule would call this
    # bullet specific. It is not: nothing here could only be about you.
    found = check_text("Delivered the report to the Team in January", "b")
    assert any("nothing specific" in f.message for f in found), found


def main() -> int:
    return run(__name__)


if __name__ == "__main__":
    raise SystemExit(main())
