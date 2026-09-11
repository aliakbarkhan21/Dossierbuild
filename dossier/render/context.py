"""The profile, flattened into exactly what a template needs.

Templates should contain layout and nothing else. Every decision that is
really about *data* -- how a half-known date prints, which link text to show,
whether a section has enough in it to be worth a heading -- is made here, once,
so that four templates cannot drift into four different answers.

The shapes below are deliberately dumb: strings and lists of strings, already
formatted. A template asking ``{{ entry.dates }}`` cannot get the month wrong.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..core.markup import plain, rich
from ..core.schema import Profile, entry_label, format_range
from .design import Design, is_custom, normalise_tag, section_label
from .naming import safe_stem
from .photo import STORED_PX, photo_data_uri


@dataclass(frozen=True)
class ContactItem:
    text: str
    href: str
    kind: str


@dataclass(frozen=True)
class Bullet:
    """One line of an entry, and the address the editor writes back to.

    A plain string did until the page itself became editable. The renderer is
    the only place that knows which paragraph on the sheet is which block in
    the profile, so it is the only place that can say so -- and it says so in
    an attribute rather than by position, because position changes the moment
    anybody reorders anything.

    ``__str__`` returns the text, so a template that has not been taught about
    this still prints the right thing.
    """

    id: str
    text: str
    path: str = ""

    def __str__(self) -> str:
        return str(self.text)

    def __html__(self) -> str:
        """The text is already safe markup, and saying so is not optional.

        Without this, Jinja sees an object with no ``__html__``, falls back to
        ``__str__``, gets a plain ``str`` -- the Markup marker lost on the way
        out -- and escapes it a second time. A bullet reading "a &lt; b"
        printed "a &amp;lt; b", and one carrying a mark printed the tag.
        """
        return str(self.text)


@dataclass(frozen=True)
class Entry:
    """One dated thing: a job, a project, a degree.

    ``title``/``subtitle`` rather than ``role``/``organisation`` because the
    templates lay out a two-line heading and genuinely do not care which is
    which -- education fills the same slots with a credential and a school.
    """

    title: str = ""
    subtitle: str = ""
    dates: str = ""
    place: str = ""
    note: str = ""
    detail: str = ""
    url: str = ""
    url_text: str = ""
    tag_label: str = ""
    tags: list[str] = field(default_factory=list)
    bullets: list["Bullet"] = field(default_factory=list)
    path: str = ""
    """``experience/exp_3f`` -- what to move or delete when the rail is used."""

    edit: dict[str, str] = field(default_factory=dict)
    """``{slot: address}`` for the text on this entry.

    A dict rather than a field per slot because the slots are the template's
    vocabulary (title, subtitle, place) and the addresses are the profile's
    (role, organisation, location), and the mapping between them is different
    for every section. Keeping it here means the macro writes
    ``data-edit="{{ e.edit.title }}"`` once and every section is covered.
    """


@dataclass(frozen=True)
class Skill:
    """One skill, and how well it is claimed.

    ``__str__`` and ``__html__`` return the name alone, so every template that
    already writes ``{{ items | join(', ') }}`` keeps printing exactly what it
    printed before this existed. A template that wants the rating asks for
    ``item.level``; one that does not never learns there is one.

    ``level`` is 1-5, or 0 for "not rated" -- which is the common case and
    must stay silent. A default of 0 rather than 3 matters: an unrated skill
    drawn at the midpoint would be the app inventing a claim on somebody's
    behalf, on the one document where that is least forgivable.
    """

    name: str
    level: int = 0

    def __str__(self) -> str:
        return str(self.name)

    def __html__(self) -> str:
        return str(self.name)


@dataclass(frozen=True)
class Line:
    """One entry in a "lines" section: certifications, honors, achievements.

    A plain string would do for the text, and did until a certification needed
    its name to be clickable. The link is kept apart from the text rather than
    baked in as HTML because ``render/text.py`` prints the same sections into a
    plain-text resume, where an anchor tag is noise.
    """

    text: str
    """Everything after the name -- issuer, date -- already joined."""
    name: str = ""
    url: str = ""
    path: str = ""
    """Where this line came from, for the rail. Empty means it is assembled
    from several fields and cannot be edited as one string on the page."""

    edit: str = ""
    """The address of the one field this line is, when it is one field."""

    def __str__(self) -> str:
        """So a template that has not been updated still prints something."""
        return f"{self.name} · {self.text}" if self.name and self.text else (self.name or self.text)


@dataclass(frozen=True)
class Section:
    key: str
    label: str
    kind: str
    text: str = ""
    edit: str = ""
    """The address of ``text``, when the section is one editable block."""
    entries: list[Entry] = field(default_factory=list)
    groups: list[tuple[str, list["Skill"]]] = field(default_factory=list)
    """``(label, items)`` with the items still a list.

    Joining them into "Python, SQL" here would be one character shorter in the
    common template and would stop the side-column layouts putting one skill
    per line. Templates that want a sentence ask for ``| join(', ')``."""
    lines: list["Line"] = field(default_factory=list)


@dataclass(frozen=True)
class ResumeContext:
    name: str
    headline: str
    contact: list[ContactItem]
    sections: list[Section]
    photo: str = ""
    """A data URI, or "" when there is no photograph to print.

    Empty covers both cases a template cares about — none uploaded, or one
    uploaded and switched off — so a template asks ``if r.photo`` and needs to
    know nothing about the design. There is no monogram behind this any more:
    no photograph means no portrait, on every template. See the ``portrait``
    macro."""

    def has(self, key: str) -> bool:
        return any(s.key == key for s in self.sections)

    def get(self, key: str) -> Section | None:
        for section in self.sections:
            if section.key == key:
                return section
        return None

    def only(self, keys: tuple[str, ...]) -> list[Section]:
        """Sections whose key is in ``keys``, in the design's order.

        The two-column template needs to split the same ordered list between a
        side column and a main column without either forgetting the order the
        user chose.
        """
        return [s for s in self.sections if s.key in keys]

    def excluding(self, keys: tuple[str, ...]) -> list[Section]:
        return [s for s in self.sections if s.key not in keys]


# --------------------------------------------------------------------------
# Small formatting decisions, made once
# --------------------------------------------------------------------------

_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*://", re.I)


#: What may appear in an ``href``. Everything else is dropped.
SAFE_SCHEMES = frozenset({"http", "https", "mailto", "tel"})

#: A scheme as the URL grammar defines one, so that "example.com:8080/x" --
#: which also has a colon in it -- is not mistaken for one.
_ANY_SCHEME = re.compile(r"^([A-Za-z][A-Za-z0-9+.\-]*):")


def normalise_url(url: str) -> str:
    """A URL a browser will actually follow, or nothing.

    People type "linkedin.com/in/x" and "www.github.com/x". Without a scheme
    those become relative links in the PDF and lead nowhere, so one is added.

    A scheme that is already there has to be one a CV can legitimately carry.
    ``javascript:`` is the one that matters: it used to reach an ``href``
    verbatim, and the preview now opens links in a real tab, so an address
    nobody can follow should not look like one. The label still prints -- it
    simply is not a link.
    """
    url = (url or "").strip()
    if not url:
        return ""

    match = _ANY_SCHEME.match(url)
    if match:
        scheme = match.group(1).lower()
        if scheme in SAFE_SCHEMES:
            return url
        # "example.com:8080/path" matches the scheme grammar and is not one.
        rest = url[match.end() :]
        if rest[:1].isdigit():
            return "https://" + url.lstrip("/")
        return ""

    return "https://" + url.lstrip("/")


def display_url(url: str) -> str:
    """What to print for a link: the part a reader needs, nothing else."""
    text = (url or "").strip()
    text = _SCHEME.sub("", text)
    text = re.sub(r"^www\.", "", text, flags=re.I)
    return text.rstrip("/")


def phone_href(phone: str) -> str:
    digits = re.sub(r"[^\d+]", "", phone or "")
    return f"tel:{digits}" if digits else ""


def build_contact(profile: Profile, design: Design) -> list[ContactItem]:
    """The header line: everything a reader might need to reach you, once.

    Ordered by how likely it is to be used, and de-duplicated -- a person who
    put their email in both the email field and a link should not print it
    twice.
    """
    items: list[ContactItem] = []
    seen: set[str] = set()

    def add(text: str, href: str, kind: str) -> None:
        text = (text or "").strip()
        # Deduplicated on the words. Somebody who emboldened their email in
        # one box and not in the other still put it there once.
        key = plain(text).lower()
        if not text or key in seen:
            return
        seen.add(key)
        items.append(ContactItem(text=rich(text), href=href, kind=kind))

    basics = profile.basics
    # The two that are addresses rather than words. An href built out of
    # marked-up text is a link that goes nowhere, which is why the editor
    # offers no formatting on these two either.
    email = plain(basics.email).strip()
    add(email, f"mailto:{email}" if email else "", "email")
    add(plain(basics.phone), phone_href(basics.phone), "phone")
    add(basics.location, "", "location")
    if design.show_links:
        for link in basics.links:
            url = normalise_url(plain(link.url))
            label = (link.label or "").strip() or display_url(url)
            if url or label:
                add(label, url, "link")
    return items


def wanted(tags: list[str], focus: str) -> bool:
    """Whether a tagged thing prints under this focus.

    Untagged material always prints. That is the whole ergonomics of the
    feature: a profile where every line must be labelled before any of it
    appears is a profile nobody finishes labelling, so an empty tag list means
    "core material" rather than "belongs to no job".
    """
    if not focus or not tags:
        return True
    return focus in {normalise_tag(t) for t in tags}


def _entry_bullets(
    entry: object, section: str = "", focus: str = "", *, blanks: bool = False
) -> list[Bullet]:
    # ``rich`` rather than the raw string: a bullet is one of the four places
    # the editor offers bold, italic and underline, so it is one of the four
    # places the renderer has to honour them. Everywhere else stays plain and
    # escaped exactly as before -- formatting exists where it is offered, and
    # a tag typed into a field with no toolbar prints as the characters it is.
    owner = getattr(entry, "id", "")
    return [
        Bullet(
            id=b.id,
            text=rich(b.text.strip()),
            path=f"{section}/{owner}/bullets/{b.id}" if section and owner else "",
        )
        for b in getattr(entry, "bullets", [])
        if (b.text.strip() or blanks) and wanted(getattr(b, "tags", []), focus)
    ]


#: How many steps a proficiency meter has. Five, because the words people
#: actually use for this -- aware, working, competent, strong, expert -- run
#: to about five, and because an odd count gives "competent" a middle to sit
#: in rather than forcing it up or down.
SKILL_LEVELS = 5


def _level(value: object) -> int:
    """A stored rating, clamped to the meter -- or 0 for "not rated".

    The file is user-editable and survives schema changes, so a level of 9, of
    -1, or of "expert" all have to land somewhere sane rather than drawing a
    row of dots off the edge of the column.
    """
    if not isinstance(value, int) or isinstance(value, bool):
        return 0
    if value <= 0:
        return 0
    return min(value, SKILL_LEVELS)


def _experience_entry(item, design: Design, *, blanks: bool = False) -> Entry:
    # The employment type only earns its place when it is not the assumed
    # thing: "Software Engineer, Acme (Full-time)" tells a reader nothing,
    # while "(Internship)" changes how the whole entry reads.
    note = item.employment_type if item.employment_type not in ("Full-time", "Other") else ""
    return Entry(
        title=rich(item.role.strip()),
        subtitle=rich(item.organisation.strip()),
        dates=format_range(item.start, item.end, style=design.date_format),
        place=rich(item.location.strip()),
        note=note,
        bullets=_entry_bullets(item, "experience", design.focus, blanks=blanks),
        path=f"experience/{item.id}",
        edit={
            "title": f"experience/{item.id}/role",
            "subtitle": f"experience/{item.id}/organisation",
            "place": f"experience/{item.id}/location",
        },
    )


def _project_entry(item, design: Design, *, blanks: bool = False) -> Entry:
    url = normalise_url(plain(item.url))
    return Entry(
        title=rich(item.name.strip()),
        subtitle=rich(item.tagline.strip()),
        dates=format_range(item.start, item.end, style=design.date_format),
        url=url,
        url_text=display_url(url),
        tag_label="Stack",
        tags=[rich(t.strip()) for t in item.tech if t.strip()],
        bullets=_entry_bullets(item, "projects", design.focus, blanks=blanks),
        path=f"projects/{item.id}",
        edit={
            "title": f"projects/{item.id}/name",
            "subtitle": f"projects/{item.id}/tagline",
        },
    )


def _education_entry(item, design: Design, *, blanks: bool = False) -> Entry:
    # Coursework is a tag row rather than prose: it is a list of nouns, and
    # printing it as a sentence wastes two lines saying "Modules included".
    #
    # The grade goes on the second line rather than in brackets after the
    # credential: people write grades that already contain brackets
    # ("Predicted First (79%)"), and nesting those reads as a typo.
    return Entry(
        title=rich(item.credential.strip()),
        subtitle=rich(item.institution.strip()),
        dates=format_range(item.start, item.end, style=design.date_format),
        place=rich(item.location.strip()),
        detail=rich(item.grade.strip()),
        tag_label="Modules",
        tags=[rich(c.strip()) for c in item.coursework if c.strip()],
        bullets=_entry_bullets(item, "education", design.focus, blanks=blanks),
        path=f"education/{item.id}",
        edit={
            "title": f"education/{item.id}/credential",
            "subtitle": f"education/{item.id}/institution",
            "place": f"education/{item.id}/location",
            "detail": f"education/{item.id}/grade",
        },
    )


def _custom_section(
    profile: Profile, design: Design, key: str, *, blanks: bool = False
) -> Section | None:
    """A section the schema has no name for, printed as it was written.

    The heading comes off the profile rather than out of ``SECTION_LABELS``,
    because this is the one section whose name is a fact about the document
    instead of a default somebody might override. The design may still
    override it -- that is what ``labels`` is for everywhere else, and the
    Sections list on Resume would be a strange place for one row to behave
    differently.

    ``kind`` is "free" rather than "text" or "lines": a resume that writes a
    paragraph and then a list under one heading has written one section, and
    splitting it in two here to fit an existing kind would print a heading the
    writer never used.
    """
    custom = next((c for c in profile.sections if c.id == key), None)
    if custom is None:
        return None
    text = custom.text.strip()
    lines = [
        Line(
            text=rich(b.text.strip()),
            path=f"sections/{custom.id}/bullets/{b.id}",
            edit=f"sections/{custom.id}/bullets/{b.id}",
        )
        for b in custom.bullets
        if (b.text.strip() or blanks) and wanted(getattr(b, "tags", []), design.focus)
    ]
    if not text and not lines:
        return None
    labels = design.labels or {}
    label = labels[key] if key in labels else custom.title.strip()
    return Section(
        key, label, "free", text=rich(text), lines=lines, edit=f"sections/{custom.id}/text"
    )


def _build_section(
    profile: Profile, design: Design, key: str, *, blanks: bool = False
) -> Section | None:
    """One section, or ``None`` when there is nothing in it worth a heading."""
    if is_custom(key):
        return _custom_section(profile, design, key, blanks=blanks)

    label = section_label(key, design.labels)

    if key == "summary":
        text = profile.summary.text.strip()
        return Section(key, label, "text", text=rich(text), edit="summary") if text else None

    if key in ("experience", "projects", "education"):
        builder = {
            "experience": _experience_entry,
            "projects": _project_entry,
            "education": _education_entry,
        }[key]
        entries = [builder(item, design, blanks=blanks) for item in getattr(profile, key)]
        # An entry with no title, no dates and no bullets is a half-typed row
        # in the editor, not something to print.
        entries = [e for e in entries if e.title or e.subtitle or e.bullets]
        return Section(key, label, "entries", entries=entries) if entries else None

    if key == "skills":
        # The level is looked up by the item's raw text, before `rich` turns
        # it into markup -- the profile keys the ratings by what was typed,
        # and matching against the rendered version would miss every skill
        # carrying a mark.
        groups = [
            (
                rich(g.label.strip() or "Skills"),
                [
                    Skill(rich(i.strip()), _level(g.levels.get(i.strip())))
                    for i in g.items
                    if i.strip()
                ],
            )
            for g in profile.skills
            if any(i.strip() for i in g.items) and wanted(g.tags, design.focus)
        ]
        return Section(key, label, "groups", groups=groups) if groups else None

    if key == "certifications":
        from ..core.schema import format_date

        lines = []
        for c in profile.certifications:
            if not c.name.strip():
                continue
            # The name is the link, not a trailing URL. A certification's
            # credential page is what its name refers to, and printing the URL
            # beside it spends a line of a resume on an address nobody types.
            rest = [c.issuer.strip()]
            if c.issued:
                rest.append(format_date(c.issued, blank="", style=design.date_format))
            lines.append(
                Line(
                    name=rich(c.name.strip()),
                    text=rich(" · ".join(p for p in rest if p)),
                    url=normalise_url(plain(c.url)),
                    path=f"certifications/{c.id}",
                    edit=f"certifications/{c.id}/name",
                )
            )
        return Section(key, label, "lines", lines=lines) if lines else None

    if key == "awards":
        lines = []
        for a in profile.awards:
            if not a.title.strip():
                continue
            parts = [a.title.strip()]
            if a.awarded_by.strip():
                parts.append(a.awarded_by.strip())
            if a.date:
                from ..core.schema import format_date

                parts.append(format_date(a.date, blank="", style=design.date_format))
            line = " · ".join(p for p in parts if p)
            if a.note.strip():
                line += f". {a.note.strip()}"
            lines.append(Line(text=rich(line), path=f"{key}/{a.id}"))
        return Section(key, label, "lines", lines=lines) if lines else None

    if key == "achievements":
        lines = []
        for a in profile.achievements:
            if not a.title.strip():
                continue
            parts = [a.title.strip()]
            if a.context.strip():
                parts.append(a.context.strip())
            if a.date:
                from ..core.schema import format_date

                parts.append(format_date(a.date, blank="", style=design.date_format))
            line = " · ".join(p for p in parts if p)
            if a.note.strip():
                line += f". {a.note.strip()}"
            lines.append(Line(text=rich(line), path=f"{key}/{a.id}"))
        return Section(key, label, "lines", lines=lines) if lines else None

    return None


def build_context(
    profile: Profile,
    design: Design,
    *,
    photo_size: int = STORED_PX,
    blanks: bool = False,
) -> ResumeContext:
    """Everything a template renders, in the order the design asks for.

    ``blanks`` keeps lines that have no text yet. It is on for the preview and
    off for the print, and the difference is deliberate: pressing "+" on the
    page has to leave something to type into, and a line with nothing in it is
    not something to print. The preview draws those at zero height, so the
    page breaks stay where the printer puts them -- see ``.ghost`` in
    ``_base.html.j2``. Nothing else differs between the two.
    """
    sections: list[Section] = []
    for key in design.visible_sections([c.id for c in profile.sections]):
        section = _build_section(profile, design, key, blanks=blanks)
        if section is not None:
            sections.append(section)

    headline = profile.basics.headline.strip() if design.show_headline else ""
    name = profile.basics.name.strip() or "Your name"
    portrait = (
        photo_data_uri(profile.basics.photo, photo_size) if design.wants_photo else ""
    )
    return ResumeContext(
        name=rich(name),
        headline=rich(headline),
        contact=build_contact(profile, design),
        sections=sections,
        photo=portrait,
    )


def trim(context: ResumeContext, entries: int = 2, bullets: int = 2, groups: int = 4) -> ResumeContext:
    """A shortened context for the gallery thumbnails.

    Eight thumbnails on one screen means eight full renders per interaction.
    At 1/4 scale a card shows roughly the top of page one, so everything below
    that is bytes nobody sees. Sections are all kept -- dropping one would
    change the *shape* of a layout, which is the only thing a thumbnail is
    for -- and only their contents are capped.
    """
    kept: list[Section] = []
    for section in context.sections:
        kept.append(
            Section(
                key=section.key,
                label=section.label,
                kind=section.kind,
                text=section.text,
                entries=[
                    Entry(**{**e.__dict__, "bullets": e.bullets[:bullets]})
                    for e in section.entries[:entries]
                ],
                groups=section.groups[:groups],
                lines=section.lines[:entries],
            )
        )
    return ResumeContext(
        name=context.name,
        headline=context.headline,
        contact=context.contact,
        sections=kept,
        photo=context.photo,
    )


def suggested_filename(profile: Profile, design: Design, suffix: str = "pdf") -> str:
    """``Muhammad-Ali-Akbar-Resume-Classic.pdf``.

    Named for the reader, not for us: this file lands in a stranger's
    downloads folder next to forty others called ``resume.pdf``.

    The name is kept in the alphabet it was written in. This used to be
    ``[^A-Za-z0-9]`` replaced with dashes, which meant "Ünsal Öztürk"
    downloaded as ``nsal-zt-rk`` and a name in Han characters was deleted
    outright, leaving a file named after a template. Carrying it safely across
    an HTTP header is ``api.downloads.attachment``'s job, not this one's.
    """
    name = safe_stem(plain(profile.basics.name))
    template = safe_stem(design.template_spec.name)
    stem = "-".join(p for p in (name, "Resume", template) if p)
    return f"{stem or 'Resume'}.{suffix}"


def entry_titles(profile: Profile) -> list[str]:
    """Labels for everything printable, used by the fit report."""
    out: list[str] = []
    for key in ("experience", "projects", "education"):
        out += [entry_label(item) for item in getattr(profile, key)]
    return out
