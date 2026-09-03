"""The master profile editor.

Two decisions drive the shape of this file.

**Bullets are one widget each, not a textarea split on newlines.** A textarea
would be less code, but every keystroke would rebuild the bullet list from
scratch and mint new ids -- destroying the stable-id property that phase 3's
accept/revert diff depends on. One widget per bullet keeps each id attached to
its text for the life of the entry.

**Widget keys are derived from entry ids, never from list positions.** Streamlit
identifies a widget by its key and remembers state against it. Keyed by
position, moving an entry up would leave its typed values behind in the old
slot. Keyed by id, state travels with the entry.
"""

from __future__ import annotations

from typing import Any, Callable

import streamlit as st

from ..core import quality
from ..core.schema import (
    Award,
    Certification,
    Education,
    Experience,
    Link,
    Profile,
    Project,
    SkillGroup,
    TextBlock,
    entry_label,
)
from . import theme

EMPLOYMENT_TYPES = [
    "Internship",
    "Placement",
    "Part-time",
    "Full-time",
    "Freelance",
    "Volunteer",
    "Research",
    "Other",
]


# --------------------------------------------------------------------------
# Small shared widgets
# --------------------------------------------------------------------------


def _wk(key: str) -> str:
    """A widget key, stamped with the current editor revision.

    Widget values live in the browser as well as in session state, and the
    browser re-sends them on every rerun. That makes a keyed widget win any
    argument with the model behind it -- which is exactly wrong after an undo
    or a restore, where the model is the thing that just changed.

    Bumping ``editor_rev`` changes every key at once, so Streamlit sees a new
    set of widgets with no history and initialises them from the model. It is
    the one reliable way to make the model win.
    """
    return f"{key}#{st.session_state.get('editor_rev', 0)}"


def current_vocabulary(profile: Profile) -> frozenset[str]:
    """The declared vocabulary, including edits not yet written back to the model.

    Streamlit renders this page top to bottom, so the Experience tab is drawn
    before the Skills tab. Reading the vocabulary from the model alone would
    therefore always be one interaction stale: type a new skill, and the
    experience bullets would not recognise it until the *next* rerun.

    Widget state is current at all times, though, so this reads the raw text out
    of the skills / tech / coursework boxes as well as the model. Same source of
    truth, just observed before this run has written it back.
    """
    items: list[str] = []
    for key, value in st.session_state.items():
        if not isinstance(key, str) or not isinstance(value, str):
            continue
        if key.split("#")[0].endswith((":items", ":tech", ":course")):
            items.extend(part for part in value.split(",") if part.strip())
    return frozenset(quality.build_vocabulary(profile) | quality.expand_terms(items))


def _month_input(label: str, value: str | None, key: str, help: str | None = None) -> str | None:
    """A date box accepting "YYYY-MM" or "YYYY". Blank means missing/ongoing.

    Year-only is allowed deliberately: if you only know you finished in 2024,
    writing "2024" is honest and the PDF will print "2024". Writing "2024-01"
    would put a month on your resume that you never claimed.
    """
    raw = st.text_input(
        label, value=value or "", key=_wk(key), placeholder="YYYY-MM or YYYY", help=help
    )
    raw = raw.strip()
    return raw or None


def _csv_input(label: str, values: list[str], key: str, placeholder: str = "") -> list[str]:
    """Edit a list of short strings as one comma-separated box.

    Safe to do here precisely because these items have no ids -- nothing
    downstream needs to track an individual skill across an edit.
    """
    raw = st.text_input(label, value=", ".join(values), key=_wk(key), placeholder=placeholder)
    return [part.strip() for part in raw.split(",") if part.strip()]


def _render_findings(findings: list[quality.Finding]) -> None:
    for finding in findings:
        st.markdown(
            f'<div class="db-finding {finding.severity}">{finding.icon} {finding.message}</div>',
            unsafe_allow_html=True,
        )


def _bullet_editor(
    entry: Any,
    *,
    key_prefix: str,
    vocabulary: frozenset[str] = frozenset(),
    label: str = "Bullet points",
) -> None:
    """Render one text area per bullet, with per-bullet linting and delete.

    ``vocabulary`` is the set of terms this person has already declared in
    their skills, project tech and coursework. Passing it in means the
    specificity check recognises the tools *they* actually use, rather than
    only the ones on a fixed list.
    """
    st.markdown(f"**{label}**")

    if not entry.bullets:
        theme.muted("No bullets yet. Each one should name a technology and, where you can, a number.")

    remove_id: str | None = None
    for block in entry.bullets:
        text_col, del_col = st.columns([0.94, 0.06])
        with text_col:
            block.text = st.text_area(
                "bullet",
                value=block.text,
                key=_wk(f"{key_prefix}:{block.id}:text"),
                height=70,
                label_visibility="collapsed",
            )
        with del_col:
            st.markdown('<div style="height:.45rem"></div>', unsafe_allow_html=True)
            if st.button("x", key=_wk(f"{key_prefix}:{block.id}:del"), help="Delete this bullet"):
                remove_id = block.id
        _render_findings(quality.check_text(block.text, block.id, vocabulary=vocabulary))

    if remove_id is not None:
        entry.bullets = [b for b in entry.bullets if b.id != remove_id]
        st.rerun()

    if st.button("Add bullet", key=_wk(f"{key_prefix}:addbullet")):
        entry.bullets.append(TextBlock())
        st.rerun()


def _entry_controls(items: list[Any], index: int, key_prefix: str) -> bool:
    """Move-up / move-down / delete row. Returns True if the list changed."""
    up, down, _spacer, delete = st.columns([0.1, 0.1, 0.6, 0.2])
    changed = False
    with up:
        if st.button("Up", key=_wk(f"{key_prefix}:up"), disabled=index == 0):
            items[index - 1], items[index] = items[index], items[index - 1]
            changed = True
    with down:
        if st.button("Down", key=_wk(f"{key_prefix}:down"), disabled=index == len(items) - 1):
            items[index + 1], items[index] = items[index], items[index + 1]
            changed = True
    with delete:
        if st.button("Delete entry", key=_wk(f"{key_prefix}:delete")):
            items.pop(index)
            changed = True
    return changed


def _section(
    title: str,
    section_key: str,
    items: list[Any],
    render_entry: Callable[[Any, str], None],
    factory: Callable[[], Any],
    add_label: str,
    empty_hint: str,
) -> None:
    """Generic list-section scaffold: header, entries, add button."""
    theme.section_label(title, section_key)

    if not items:
        theme.muted(empty_hint)

    for index, entry in enumerate(list(items)):
        heading = entry_label(entry)
        with st.expander(heading, expanded=len(items) == 1):
            render_entry(entry, entry.id)
            st.markdown("---")
            if _entry_controls(items, index, f"{section_key}:{entry.id}"):
                st.rerun()

    if st.button(add_label, key=_wk(f"{section_key}:add"), type="primary"):
        items.append(factory())
        st.rerun()


# --------------------------------------------------------------------------
# Per-section renderers
# --------------------------------------------------------------------------


def render_basics(profile: Profile) -> None:
    theme.section_label("Contact details", "basics")
    b = profile.basics

    left, right = st.columns(2)
    with left:
        b.name = st.text_input("Full name", value=b.name, key=_wk("basics:name"))
        b.email = st.text_input("Email", value=b.email, key=_wk("basics:email"))
        b.location = st.text_input(
            "Location", value=b.location, key=_wk("basics:location"), placeholder="Manchester, UK"
        )
    with right:
        b.headline = st.text_input(
            "Headline",
            value=b.headline,
            key=_wk("basics:headline"),
            placeholder="Second-year CS & AI student",
            help="One line under your name. Not a summary -- a label.",
        )
        b.phone = st.text_input("Phone", value=b.phone, key=_wk("basics:phone"))

    st.markdown("**Links**")
    remove_id: str | None = None
    for link in b.links:
        label_col, url_col, del_col = st.columns([0.25, 0.69, 0.06])
        with label_col:
            link.label = st.text_input(
                "label", value=link.label, key=_wk(f"lnk:{link.id}:label"),
                label_visibility="collapsed", placeholder="GitHub",
            )
        with url_col:
            link.url = st.text_input(
                "url", value=link.url, key=_wk(f"lnk:{link.id}:url"),
                label_visibility="collapsed", placeholder="https://github.com/yourname",
            )
        with del_col:
            if st.button("x", key=_wk(f"lnk:{link.id}:del"), help="Remove link"):
                remove_id = link.id
    if remove_id is not None:
        b.links = [l for l in b.links if l.id != remove_id]
        st.rerun()
    if st.button("Add link", key=_wk("basics:addlink")):
        b.links.append(Link())
        st.rerun()


def render_summary(profile: Profile) -> None:
    theme.section_label("Summary", "summary")
    theme.muted(
        "Two or three lines. This is the block the AI tailoring step rewrites most heavily, "
        "so write the honest version here and let tailoring re-angle it per job."
    )
    profile.summary.text = st.text_area(
        "Summary",
        value=profile.summary.text,
        key=_wk("summary:text"),
        height=120,
        label_visibility="collapsed",
    )
    _render_findings(
        quality.check_text(
            profile.summary.text,
            profile.summary.id,
            is_summary=True,
            vocabulary=current_vocabulary(profile),
        )
    )


def render_experience(profile: Profile) -> None:
    vocabulary = current_vocabulary(profile)

    def render_entry(entry: Experience, eid: str) -> None:
        c1, c2 = st.columns(2)
        with c1:
            entry.role = st.text_input("Role", value=entry.role, key=_wk(f"exp:{eid}:role"))
            entry.organisation = st.text_input(
                "Organisation", value=entry.organisation, key=_wk(f"exp:{eid}:org")
            )
            entry.location = st.text_input("Location", value=entry.location, key=_wk(f"exp:{eid}:loc"))
        with c2:
            entry.employment_type = st.selectbox(
                "Type",
                EMPLOYMENT_TYPES,
                index=EMPLOYMENT_TYPES.index(entry.employment_type),
                key=_wk(f"exp:{eid}:type"),
            )
            d1, d2 = st.columns(2)
            with d1:
                entry.start = _month_input("Start", entry.start, f"exp:{eid}:start")
            with d2:
                entry.end = _month_input(
                    "End", entry.end, f"exp:{eid}:end", help="Leave blank if this is ongoing"
                )
        _bullet_editor(entry, key_prefix=f"exp:{eid}", vocabulary=vocabulary)

    _section(
        "Experience", "experience", profile.experience, render_entry, Experience,
        "Add experience",
        "Internships, part-time work, placements, paid or unpaid research.",
    )


def render_projects(profile: Profile) -> None:
    vocabulary = current_vocabulary(profile)

    def render_entry(entry: Project, eid: str) -> None:
        c1, c2 = st.columns(2)
        with c1:
            entry.name = st.text_input("Project name", value=entry.name, key=_wk(f"prj:{eid}:name"))
            entry.tagline = st.text_input(
                "Tagline", value=entry.tagline, key=_wk(f"prj:{eid}:tag"),
                placeholder="What it does, in one line",
            )
            entry.url = st.text_input("URL", value=entry.url, key=_wk(f"prj:{eid}:url"))
        with c2:
            d1, d2 = st.columns(2)
            with d1:
                entry.start = _month_input("Start", entry.start, f"prj:{eid}:start")
            with d2:
                entry.end = _month_input("End", entry.end, f"prj:{eid}:end")
            entry.tech = _csv_input(
                "Tech used", entry.tech, f"prj:{eid}:tech", "Python, Streamlit, Gemini API"
            )
        _bullet_editor(entry, key_prefix=f"prj:{eid}", vocabulary=vocabulary)

    _section(
        "Projects", "projects", profile.projects, render_entry, Project,
        "Add project",
        "For a second-year student this section usually does more work than experience. "
        "Say what the thing does and what it cost you to build.",
    )


def render_education(profile: Profile) -> None:
    vocabulary = current_vocabulary(profile)

    def render_entry(entry: Education, eid: str) -> None:
        c1, c2 = st.columns(2)
        with c1:
            entry.institution = st.text_input(
                "Institution", value=entry.institution, key=_wk(f"edu:{eid}:inst")
            )
            entry.credential = st.text_input(
                "Credential", value=entry.credential, key=_wk(f"edu:{eid}:cred"),
                placeholder="BSc Computer Science with Artificial Intelligence",
            )
            entry.location = st.text_input("Location", value=entry.location, key=_wk(f"edu:{eid}:loc"))
        with c2:
            d1, d2 = st.columns(2)
            with d1:
                entry.start = _month_input("Start", entry.start, f"edu:{eid}:start")
            with d2:
                entry.end = _month_input(
                    "End", entry.end, f"edu:{eid}:end", help="Expected end date is fine"
                )
            entry.grade = st.text_input(
                "Grade", value=entry.grade, key=_wk(f"edu:{eid}:grade"), placeholder="First class (78%)"
            )
        entry.coursework = _csv_input(
            "Relevant coursework", entry.coursework, f"edu:{eid}:course",
            "Data Structures, Machine Learning, Operating Systems",
        )
        _bullet_editor(
            entry, key_prefix=f"edu:{eid}", vocabulary=vocabulary, label="Notes (optional)"
        )

    _section(
        "Education", "education", profile.education, render_entry, Education,
        "Add education", "Your degree, and anything before it worth listing.",
    )


def render_skills(profile: Profile) -> None:
    def render_entry(entry: SkillGroup, eid: str) -> None:
        entry.label = st.text_input(
            "Group name", value=entry.label, key=_wk(f"skg:{eid}:label"),
            placeholder="Languages",
        )
        entry.items = _csv_input(
            "Skills in this group", entry.items, f"skg:{eid}:items", "Python, SQL, Java"
        )

    _section(
        "Skills", "skills", profile.skills, render_entry, SkillGroup,
        "Add skill group",
        "Grouped, not one long list -- templates render these as "
        "'Languages: Python, SQL' lines.",
    )


def render_certifications(profile: Profile) -> None:
    def render_entry(entry: Certification, eid: str) -> None:
        c1, c2 = st.columns(2)
        with c1:
            entry.name = st.text_input("Name", value=entry.name, key=_wk(f"crt:{eid}:name"))
            entry.issuer = st.text_input("Issuer", value=entry.issuer, key=_wk(f"crt:{eid}:iss"))
        with c2:
            entry.issued = _month_input("Issued", entry.issued, f"crt:{eid}:date")
            entry.url = st.text_input("Credential URL", value=entry.url, key=_wk(f"crt:{eid}:url"))

    _section(
        "Certifications", "certifications", profile.certifications, render_entry, Certification,
        "Add certification", "Named credentials and substantial courses.",
    )


def render_awards(profile: Profile) -> None:
    def render_entry(entry: Award, eid: str) -> None:
        c1, c2 = st.columns(2)
        with c1:
            entry.title = st.text_input("Title", value=entry.title, key=_wk(f"awd:{eid}:title"))
            entry.awarded_by = st.text_input(
                "Awarded by", value=entry.awarded_by, key=_wk(f"awd:{eid}:by")
            )
        with c2:
            entry.date = _month_input("Date", entry.date, f"awd:{eid}:date")
        entry.note = st.text_input(
            "Note", value=entry.note, key=_wk(f"awd:{eid}:note"),
            placeholder="2nd of 60 teams",
        )

    _section(
        "Awards", "awards", profile.awards, render_entry, Award,
        "Add award", "Hackathon placings, scholarships, prizes, dean's list.",
    )


SECTION_RENDERERS: dict[str, tuple[str, Callable[[Profile], None]]] = {
    "basics": ("Contact", render_basics),
    "summary": ("Summary", render_summary),
    "experience": ("Experience", render_experience),
    "projects": ("Projects", render_projects),
    "education": ("Education", render_education),
    "skills": ("Skills", render_skills),
    "certifications": ("Certifications", render_certifications),
    "awards": ("Awards", render_awards),
}
