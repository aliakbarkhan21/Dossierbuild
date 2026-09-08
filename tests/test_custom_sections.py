"""Sections the eight built-in ones have no name for.

The failure this replaced was silent: a heading the importer could not place
was read, dropped, and never mentioned. The writer got a shorter resume and no
reason for it. So the tests here are mostly about *arriving* -- into the
profile, into the order, into every template, and into the plain-text export.
"""

from __future__ import annotations

from dossier.core.schema import (
    Basics,
    CustomSection,
    Profile,
    TextBlock,
    entry_label,
    iter_bullets,
)
from dossier.core.storage import dedupe_ids, migrate
from dossier.ingest.merge import apply_merge_plan, build_merge_plan
from dossier.render.context import build_context
from dossier.render.design import LAYOUTS, TEMPLATES, Design, is_custom
from dossier.render.html import render_html
from dossier.render.text import plain_text


def profile_with(*sections: CustomSection) -> Profile:
    profile = Profile.empty()
    profile.basics = Basics(name="M Harris Sufian", email="h@example.com")
    profile.sections = list(sections)
    return profile


def qualifications() -> CustomSection:
    return CustomSection(
        title="Executive Qualifications",
        bullets=[
            TextBlock(text="22+ years of technology leadership in CIO positions."),
            TextBlock(text="Directed national technology initiatives at NCOC."),
        ],
    )


def governance() -> CustomSection:
    return CustomSection(
        title="Governance, Security and Risk Leadership",
        text="Advised regulators on national platform risk across three jurisdictions.",
    )


# --------------------------------------------------------------------------
# The schema
# --------------------------------------------------------------------------


def test_a_custom_section_takes_a_key_the_design_can_carry() -> None:
    """The key is the section's own id, which is what lets ``order`` hold it.

    The design is loaded and validated with no profile in hand. A validator
    that dropped every key it could not verify against a profile would delete
    a section's position on every read.
    """
    assert is_custom(qualifications().id)


def test_a_custom_section_may_hold_prose_and_a_list_at_once() -> None:
    """Splitting them would print a heading the writer never used."""
    both = CustomSection(title="Coverage", text="Asia-Pacific.", bullets=[TextBlock(text="EMEA")])
    assert both.text and both.bullets


def test_its_bullets_are_held_to_the_same_standard_as_every_other_line() -> None:
    """They reach the linter and the tailor, or the section is quietly exempt."""
    profile = profile_with(qualifications())
    found = [block.text for _section, _owner, block in iter_bullets(profile)]
    assert "Directed national technology initiatives at NCOC." in found


def test_entry_label_names_one_by_its_heading() -> None:
    assert entry_label(qualifications()) == "Executive Qualifications"
    assert entry_label(CustomSection()) == "Untitled section"


def test_ids_are_deduped_like_everything_else() -> None:
    profile = profile_with(qualifications(), qualifications())
    profile.sections[1].id = profile.sections[0].id
    dedupe_ids(profile)
    assert profile.sections[0].id != profile.sections[1].id


def test_the_migration_adds_the_list_and_moves_nothing_into_it() -> None:
    raw = migrate({"schema_version": 4, "basics": {}, "awards": [{"id": "a", "title": "Prize"}]})
    assert raw["sections"] == []
    assert raw["awards"] == [{"id": "a", "title": "Prize"}]


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


def test_it_prints_under_its_own_heading_in_every_template_and_layout() -> None:
    """Thirty-two page designs, one shared macro. The point of checking all of
    them is that the two-column templates split sections between a side column
    and a main column by a fixed list of keys -- and a key not on that list
    could have fallen down the gap rather than into the main column."""
    profile = profile_with(governance(), qualifications())
    missing = []
    for template in TEMPLATES:
        for layout in LAYOUTS:
            html = render_html(profile, Design(template=template, layout=layout))
            for needle in (
                "Governance, Security and Risk Leadership",
                "Executive Qualifications",
                "Advised regulators on national platform risk",
                "Directed national technology initiatives at NCOC.",
            ):
                if needle not in html:
                    missing.append((template, layout, needle))
    assert missing == []


def test_a_section_the_design_has_never_heard_of_still_prints() -> None:
    """It is created in the Profile editor, and the design is written
    elsewhere. Waiting for the two to meet would mean a section that exists,
    has content, and appears nowhere."""
    profile = profile_with(governance())
    design = Design(order=["summary", "experience"])  # no mention of it
    keys = [s.key for s in build_context(profile, design).sections]
    assert profile.sections[0].id in keys


def test_hiding_one_hides_it() -> None:
    profile = profile_with(governance())
    design = Design(hidden=[profile.sections[0].id])
    assert build_context(profile, design).sections == []


def test_the_design_may_rename_it_without_touching_the_profile() -> None:
    """Same split as every other section: the profile holds what it is called,
    the design holds what this printing calls it."""
    profile = profile_with(governance())
    key = profile.sections[0].id
    design = Design(labels={key: "Risk and Governance"})
    section = build_context(profile, design).get(key)
    assert section is not None and section.label == "Risk and Governance"
    assert profile.sections[0].title == "Governance, Security and Risk Leadership"


def test_an_empty_one_is_not_given_a_heading() -> None:
    """A heading with nothing under it is a band of blank paper."""
    profile = profile_with(CustomSection(title="Referees"))
    assert build_context(profile, Design()).sections == []


def test_its_bullets_follow_the_focus_like_any_others() -> None:
    profile = profile_with(
        CustomSection(
            title="Coverage",
            bullets=[
                TextBlock(text="Backend work", tags=["backend"]),
                TextBlock(text="Always printed"),
            ],
        )
    )
    section = build_context(profile, Design(focus="research")).sections[0]
    assert [str(line.text) for line in section.lines] == ["Always printed"]


def test_the_plain_text_export_gives_it_its_own_heading() -> None:
    """Not a shared "SECTIONS" banner. That would invent a level of hierarchy
    the resume does not have and bury the writer's heading a line down."""
    text = plain_text(profile_with(governance(), qualifications()))
    assert "GOVERNANCE, SECURITY AND RISK LEADERSHIP" in text
    assert "EXECUTIVE QUALIFICATIONS" in text
    assert "SECTIONS" not in text


def test_formatting_inside_one_reaches_the_page_and_leaves_the_export() -> None:
    profile = profile_with(
        CustomSection(title="Coverage", bullets=[TextBlock(text="Grew <b>40%</b>")])
    )
    assert "<b>40%</b>" in render_html(profile, Design())
    assert "Grew 40%" in plain_text(profile)


# --------------------------------------------------------------------------
# Importing
# --------------------------------------------------------------------------


def test_an_import_offers_one_for_review_like_any_other_entry() -> None:
    plan = build_merge_plan(Profile.empty(), profile_with(qualifications()), "a PDF")
    proposed = [c for c in plan.candidates if c.section == "sections"]
    assert [c.label for c in proposed] == ["Executive Qualifications"]
    assert "22+ years" in proposed[0].detail


def test_re_importing_the_same_resume_does_not_offer_it_twice() -> None:
    current = profile_with(qualifications())
    plan = build_merge_plan(current, profile_with(qualifications()), "a PDF")
    proposed = [c for c in plan.candidates if c.section == "sections"]
    assert proposed and proposed[0].is_duplicate


def test_accepting_one_adds_it() -> None:
    profile = Profile.empty()
    plan = build_merge_plan(profile, profile_with(governance()), "a PDF")
    key = next(c.key for c in plan.candidates if c.section == "sections")
    apply_merge_plan(profile, plan, set(), {key})
    assert [s.title for s in profile.sections] == ["Governance, Security and Risk Leadership"]


# --------------------------------------------------------------------------
# Ids
# --------------------------------------------------------------------------


def test_a_new_entry_arrives_without_an_id_and_is_given_one() -> None:
    """The editor sends ``id: ""`` and reads the profile back for the real one.

    That contract was written down in the store and not honoured here: an
    empty id is not a duplicate of anything, so ``dedupe_ids`` walked past it
    and the blank went to disk. Harmless everywhere else and fatal for a
    custom section, whose id *is* the key the design orders and renames by.
    """
    profile = Profile.empty()
    profile.sections = [CustomSection(id="", title="Board and Advisory Roles")]
    dedupe_ids(profile)
    assert is_custom(profile.sections[0].id)


def test_two_new_entries_do_not_get_the_same_id() -> None:
    profile = Profile.empty()
    profile.sections = [CustomSection(id=""), CustomSection(id="")]
    dedupe_ids(profile)
    assert profile.sections[0].id != profile.sections[1].id


def test_a_blank_summary_id_goes_back_to_its_well_known_one() -> None:
    """Saved versions and accepted rewrites reference the summary by name."""
    profile = Profile.empty()
    profile.summary.id = ""
    dedupe_ids(profile)
    assert profile.summary.id == "sum_main"


def test_saving_through_the_api_hands_back_real_ids() -> None:
    """The round trip the editor actually performs."""
    from fastapi.testclient import TestClient

    from dossier.api.app import app

    with TestClient(app) as client:
        profile = Profile.empty().model_dump(mode="json")
        profile["sections"] = [
            {"id": "", "title": "Selected Publications", "text": "Three papers.", "bullets": []}
        ]
        assert client.put("/api/profile", json=profile).status_code == 200
        stored = client.get("/api/profile").json()
        assert is_custom(stored["sections"][0]["id"])
