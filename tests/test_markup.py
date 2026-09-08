"""Bold, italic and underline, and the promise that nothing else gets through.

The tests worth having here are the ones about what a resume *carries*: an
ampersand in an employer's name, an angle bracket in a C++ template, a tag
somebody pasted out of a web page. All of those existed in profiles before
this feature did, and none of them may change meaning because of it.
"""

from __future__ import annotations

from html import unescape

import pytest

from dossier.core.markup import ALLOWED, plain, rich


def test_the_three_marks_survive() -> None:
    assert str(rich("Cut runtime <b>68%</b>")) == "Cut runtime <b>68%</b>"
    assert str(rich("<i>Ad hoc</i> review")) == "<i>Ad hoc</i> review"
    assert str(rich("<u>Lead</u> author")) == "<u>Lead</u> author"


@pytest.mark.parametrize(
    "text",
    [
        "Rolls-Royce & Partners",
        "std::vector<int> throughput",
        "A < B and B > C",
        "50% of a & b",
    ],
)
def test_the_characters_a_resume_already_carried_are_untouched(text: str) -> None:
    """The whole reason the stored form is plain text rather than escaped HTML.

    Every profile written before this feature existed contains raw ampersands
    and angle brackets. Had the format been "escaped HTML", each of these
    would have started printing as ``&amp;`` the day the feature shipped --
    on documents nobody had edited.
    """
    assert plain(text) == text
    # Unescaped rather than string-matched: what matters is that the browser
    # ends up displaying the characters that were typed, not how the entity
    # for them happens to be spelled on the way there.
    assert unescape(str(rich(text))) == text


def test_a_tag_that_is_not_one_of_the_three_prints_as_characters() -> None:
    out = str(rich('<script>alert(1)</script> and <img src=x onerror=y>'))
    assert "<script" not in out
    assert "<img" not in out
    assert "&lt;script&gt;" in out


def test_an_attribute_cannot_ride_in_on_an_allowed_tag() -> None:
    """``<b onclick=...>`` is not ``<b>``, and the match is exact.

    This is the one that makes the allowlist an allowlist rather than a
    suggestion: the pattern runs against the *escaped* text, so anything that
    is not character-for-character one of the six stays escaped.
    """
    out = str(rich('<b onclick="steal()">x</b>'))
    assert "onclick" not in out or "&lt;b onclick" in out
    assert "<b onclick" not in out


def test_an_unclosed_mark_is_closed() -> None:
    """Otherwise it bleeds into the rest of the document.

    An unterminated ``<b>`` inside a list item does not stop at the item: the
    HTML parser re-opens it in everything that follows, so one stray tag in
    one bullet emboldens the remainder of the page.
    """
    assert str(rich("unclosed <b>bold")) == "unclosed <b>bold</b>"


def test_a_mark_that_was_never_opened_is_dropped() -> None:
    """A stray closer would otherwise close a tag belonging to the template."""
    assert str(rich("stray </b> closer")) == "stray  closer"


def test_crossed_marks_come_out_nested() -> None:
    """Balanced is not enough; it has to nest, or the parser repairs it for us."""
    assert str(rich("<b>a <i>b</b> c</i>")) == "<b>a <i>b</i></b> c"


def test_plain_takes_the_marks_out_and_leaves_the_words() -> None:
    assert plain("Cut runtime <b>68%</b> in <i>six</i> weeks") == "Cut runtime 68% in six weeks"


def test_plain_is_case_insensitive() -> None:
    """A hand-edited profile.json, or a paste, can carry capitals."""
    assert plain("<B>x</B> <I>y</I> <U>z</U>") == "x y z"


def test_plain_leaves_a_line_that_has_no_marks_exactly_as_it_was() -> None:
    line = "Managed technology organizations exceeding 90 professionals"
    assert plain(line) is not None
    assert plain(line) == line


def test_empty_and_none_are_survivable() -> None:
    assert plain("") == ""
    assert str(rich("")) == ""
    assert plain(None) == ""  # type: ignore[arg-type]


def test_the_vocabulary_is_three_marks_and_stays_three() -> None:
    """A guard on scope, not on behaviour.

    Sizes, colours and typefaces belong to the design, where changing one
    changes the whole document. Widening this tuple is how a resume ends up
    with one bullet in 14pt red.
    """
    assert ALLOWED == ("b", "i", "u")
