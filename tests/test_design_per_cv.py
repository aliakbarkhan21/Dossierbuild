"""A design belongs to the CV, not to the app.

It was one file for all of them, on the reasoning that the *look* is a habit
of the person rather than a fact about the document. That holds right up until
somebody keeps two CVs for two different people, at which point setting a
typeface on one silently reset the other -- reported exactly that way: "my
uncle's CV settings have been applied to my CV as well".

Section order is the sharper version of the same problem: it can name a custom
section, and a custom section belongs to exactly one profile.
"""

from __future__ import annotations

import json

from dossier.core import cvs
from dossier.render.design import (
    LEGACY_DESIGN_PATH,
    Design,
    design_path,
    load_design,
    save_design,
)


def test_two_cvs_keep_two_designs() -> None:
    first = cvs.active_id()
    second = cvs.create("Uncle").id

    cvs.switch(second)
    save_design(Design(fonts="grotesque", template="modern"))

    cvs.switch(first)
    save_design(Design(fonts="book", template="classic"))
    assert (load_design().fonts, load_design().template) == ("book", "classic")

    cvs.switch(second)
    assert (load_design().fonts, load_design().template) == ("grotesque", "modern")


def test_each_design_is_its_own_file() -> None:
    first = cvs.active_id()
    second = cvs.create().id
    assert design_path(first) != design_path(second)


def test_a_cv_with_no_design_of_its_own_inherits_the_shared_one() -> None:
    """The migration, and the reason there is no migration step.

    A CV that has never been styled reads the file every CV used to share, so
    the look somebody spent an afternoon on is still there the first time they
    open it. The moment they change anything it is written to their own file
    and the two stop moving together.
    """
    LEGACY_DESIGN_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEGACY_DESIGN_PATH.write_text(
        json.dumps(Design(fonts="times", template="gazette").model_dump(mode="json")),
        encoding="utf-8",
    )
    fresh = cvs.create().id
    cvs.switch(fresh)
    assert not design_path(fresh).exists()
    assert (load_design().fonts, load_design().template) == ("times", "gazette")


def test_styling_one_cv_never_writes_the_shared_file() -> None:
    """Or the inheritance would become the bug it was meant to fix."""
    LEGACY_DESIGN_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEGACY_DESIGN_PATH.write_text(
        json.dumps(Design(fonts="times").model_dump(mode="json")), encoding="utf-8"
    )
    before = LEGACY_DESIGN_PATH.read_text(encoding="utf-8")

    cvs.switch(cvs.create().id)
    save_design(Design(fonts="slab"))

    assert LEGACY_DESIGN_PATH.read_text(encoding="utf-8") == before
    assert load_design().fonts == "slab"


def test_a_new_cv_does_not_take_the_previous_one_s_design() -> None:
    first = cvs.active_id()
    save_design(Design(fonts="condensed"))
    second = cvs.create().id
    cvs.switch(second)
    assert load_design().fonts != "condensed" or not design_path(second).exists()
    cvs.switch(first)
    assert load_design().fonts == "condensed"


def test_a_duplicate_starts_from_the_original_s_design() -> None:
    """The one case that inverts the rule above.

    A new CV deliberately does not take the previous one's design. A *copy* is
    the opposite request: it exists to be the same document until you change
    something, and a copy that came back on the default template would make
    the user redo the look before they could start on the difference.
    """
    first = cvs.active_id()
    save_design(Design(fonts="condensed", template="modern"))

    copy = cvs.duplicate(first)

    assert design_path(copy.id).exists()
    assert (load_design().fonts, load_design().template) == ("condensed", "modern")


def test_duplicating_a_cv_that_was_never_styled_writes_no_design() -> None:
    """There is nothing of its own to copy, and both still inherit.

    Writing the resolved defaults out here would freeze a look that is meant
    to keep following the shared file.
    """
    LEGACY_DESIGN_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEGACY_DESIGN_PATH.write_text(
        json.dumps(Design(fonts="times", template="gazette").model_dump(mode="json")),
        encoding="utf-8",
    )
    fresh = cvs.create().id
    assert not design_path(fresh).exists()

    copy = cvs.duplicate(fresh)

    assert not design_path(copy.id).exists()
    assert (load_design().fonts, load_design().template) == ("times", "gazette")
