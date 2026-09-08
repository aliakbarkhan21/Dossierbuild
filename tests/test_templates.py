"""Every template renders the same facts, and the set stays whole.

Cheap structural checks only -- what a page *looks* like is measured in a
browser by ``scripts/check_phase2.py``, which is where the pagination and the
print/preview equality live. This file is the net under the registry: a
template whose file is missing, whose key disagrees with its own entry, or
which quietly drops a section, fails here in milliseconds rather than in a PDF
somebody has already sent.
"""

from __future__ import annotations

import re

import pytest

from dossier.core.markup import plain
from dossier.core.sample import sample_profile
from dossier.render.design import LAYOUTS, TEMPLATES, Design
from dossier.render.html import render_html

KEYS = sorted(TEMPLATES)


def text_of(html: str) -> str:
    """The page's words, with the markup taken out."""
    body = re.sub(r"(?s)<(script|style)\b.*?</\1>", " ", html)
    return re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", " ", body))


def test_the_registry_and_the_folder_agree() -> None:
    for key, spec in TEMPLATES.items():
        assert spec.key == key, f"{key} carries the key {spec.key!r}"
        assert spec.file.endswith(".html.j2"), spec.file
        assert spec.name and spec.blurb and spec.best_for, key
        # A two-column template cannot honestly claim to be parser-safe: a
        # side column interleaves a job title with a skills list in the text
        # layer, which is the one thing the flag is about.
        if spec.columns == "Two columns":
            assert not spec.ats, f"{key} claims ATS-safe with two columns"


@pytest.mark.parametrize("key", KEYS)
def test_every_template_prints_the_whole_person(key: str) -> None:
    """A layout may move a section. It may not lose one."""
    profile = sample_profile()
    words = text_of(render_html(profile, Design(template=key)))

    assert plain(profile.basics.name) in words
    assert plain(profile.basics.email) in words
    for entry in profile.experience:
        assert plain(entry.role) in words, (key, entry.role)
        assert plain(entry.organisation) in words, (key, entry.organisation)
    for entry in profile.experience:
        for bullet in entry.bullets:
            assert plain(bullet.text)[:40] in words, (key, bullet.text[:40])
    for group in profile.skills:
        for item in group.items:
            assert item in words, (key, item)


@pytest.mark.parametrize("key", KEYS)
def test_every_template_survives_an_empty_profile(key: str) -> None:
    """The blank first run. A template that only works when full is a trap."""
    from dossier.core.schema import Profile

    html = render_html(Profile.empty(), Design(template=key))
    assert "<html" in html and "</html>" in html


def test_every_template_composes_with_every_layout() -> None:
    """The two axes are independent, which is the whole reason there are two."""
    profile = sample_profile()
    seen = 0
    for key in KEYS:
        for layout in LAYOUTS:
            html = render_html(profile, Design(template=key, layout=layout))
            assert plain(profile.basics.name) in text_of(html), (key, layout)
            seen += 1
    assert seen == len(TEMPLATES) * len(LAYOUTS)


def test_a_pushed_block_cannot_be_left_behind_by_a_collapsing_margin() -> None:
    """The paginator moves a block by its own ``margin-top``.

    Adjacent vertical margins collapse, so that margin escaped to the parent
    and *won* against the parent's instead of adding to it -- every push
    landed short by exactly the entry's own margin, which put a title half
    under the seam band. The fix is a block formatting context, and this is
    what keeps it: it is one word, in a shared stylesheet, that looks like
    tidiness and is not.
    """
    base = (
        __import__("pathlib")
        .Path("dossier/render/templates/_base.html.j2")
        .read_text(encoding="utf-8")
    )
    entry = re.search(r"\n\.entry \{[^}]*\}", base)
    bullets = re.search(r"\nul\.bul \{[^}]*\}", base)
    assert entry and "flow-root" in entry.group(0), entry and entry.group(0)
    assert bullets and "flow-root" in bullets.group(0), bullets and bullets.group(0)
