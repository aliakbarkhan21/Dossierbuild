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

from ..core.schema import Profile, entry_label, format_range
from .design import Design, SECTION_LABELS
from .photo import STORED_PX, photo_data_uri


@dataclass(frozen=True)
class ContactItem:
    text: str
    href: str
    kind: str


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
    bullets: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Section:
    key: str
    label: str
    kind: str
    text: str = ""
    entries: list[Entry] = field(default_factory=list)
    groups: list[tuple[str, list[str]]] = field(default_factory=list)
    """``(label, items)`` with the items still a list.

    Joining them into "Python, SQL" here would be one character shorter in the
    common template and would stop the side-column layouts putting one skill
    per line. Templates that want a sentence ask for ``| join(', ')``."""
    lines: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ResumeContext:
    name: str
    headline: str
    contact: list[ContactItem]
    sections: list[Section]
    photo: str = ""
    photo_shape: str = "circle"
    initials: str = ""
    """``photo`` is a data URI or "", so a template can simply ask ``if r.photo``.

    ``initials`` is what a portrait-carrying layout falls back to when there is
    no photograph: an empty circle is a hole in the page, two letters are a
    monogram."""

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


def normalise_url(url: str) -> str:
    """A URL a browser will actually follow.

    People type "linkedin.com/in/x" and "www.github.com/x". Without a scheme
    those become relative links in the PDF and lead nowhere.
    """
    url = (url or "").strip()
    if not url:
        return ""
    if url.startswith("mailto:") or url.startswith("tel:"):
        return url
    if _SCHEME.match(url):
        return url
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
        if not text or text.lower() in seen:
            return
        seen.add(text.lower())
        items.append(ContactItem(text=text, href=href, kind=kind))

    basics = profile.basics
    add(basics.email, f"mailto:{basics.email}" if basics.email else "", "email")
    add(basics.phone, phone_href(basics.phone), "phone")
    add(basics.location, "", "location")
    if design.show_links:
        for link in basics.links:
            url = normalise_url(link.url)
            label = (link.label or "").strip() or display_url(url)
            if url or label:
                add(label, url, "link")
    return items


def _entry_bullets(entry: object) -> list[str]:
    return [b.text.strip() for b in getattr(entry, "bullets", []) if b.text.strip()]


def _experience_entry(item, design: Design) -> Entry:
    # The employment type only earns its place when it is not the assumed
    # thing: "Software Engineer, Acme (Full-time)" tells a reader nothing,
    # while "(Internship)" changes how the whole entry reads.
    note = item.employment_type if item.employment_type not in ("Full-time", "Other") else ""
    return Entry(
        title=item.role.strip(),
        subtitle=item.organisation.strip(),
        dates=format_range(item.start, item.end, style=design.date_format),
        place=item.location.strip(),
        note=note,
        bullets=_entry_bullets(item),
    )


def _project_entry(item, design: Design) -> Entry:
    url = normalise_url(item.url)
    return Entry(
        title=item.name.strip(),
        subtitle=item.tagline.strip(),
        dates=format_range(item.start, item.end, style=design.date_format),
        url=url,
        url_text=display_url(url),
        tag_label="Stack",
        tags=[t.strip() for t in item.tech if t.strip()],
        bullets=_entry_bullets(item),
    )


def _education_entry(item, design: Design) -> Entry:
    # Coursework is a tag row rather than prose: it is a list of nouns, and
    # printing it as a sentence wastes two lines saying "Modules included".
    #
    # The grade goes on the second line rather than in brackets after the
    # credential: people write grades that already contain brackets
    # ("Predicted First (79%)"), and nesting those reads as a typo.
    return Entry(
        title=item.credential.strip(),
        subtitle=item.institution.strip(),
        dates=format_range(item.start, item.end, style=design.date_format),
        place=item.location.strip(),
        detail=item.grade.strip(),
        tag_label="Modules",
        tags=[c.strip() for c in item.coursework if c.strip()],
        bullets=_entry_bullets(item),
    )


def _build_section(profile: Profile, design: Design, key: str) -> Section | None:
    """One section, or ``None`` when there is nothing in it worth a heading."""
    label = SECTION_LABELS.get(key, key.title())

    if key == "summary":
        text = profile.summary.text.strip()
        return Section(key, label, "text", text=text) if text else None

    if key in ("experience", "projects", "education"):
        builder = {
            "experience": _experience_entry,
            "projects": _project_entry,
            "education": _education_entry,
        }[key]
        entries = [builder(item, design) for item in getattr(profile, key)]
        # An entry with no title, no dates and no bullets is a half-typed row
        # in the editor, not something to print.
        entries = [e for e in entries if e.title or e.subtitle or e.bullets]
        return Section(key, label, "entries", entries=entries) if entries else None

    if key == "skills":
        groups = [
            (g.label.strip() or "Skills", [i.strip() for i in g.items if i.strip()])
            for g in profile.skills
            if any(i.strip() for i in g.items)
        ]
        return Section(key, label, "groups", groups=groups) if groups else None

    if key == "certifications":
        lines = []
        for c in profile.certifications:
            if not c.name.strip():
                continue
            parts = [c.name.strip()]
            if c.issuer.strip():
                parts.append(c.issuer.strip())
            if c.issued:
                from ..core.schema import format_date

                parts.append(format_date(c.issued, blank="", style=design.date_format))
            lines.append(" · ".join(p for p in parts if p))
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
            lines.append(line)
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
            lines.append(line)
        return Section(key, label, "lines", lines=lines) if lines else None

    return None


def initials(name: str) -> str:
    """"Muhammad Ali Akbar Khan" -> "MK". First and last, never three."""
    parts = [p for p in re.split(r"[\s\-]+", name.strip()) if p and p[0].isalpha()]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0][0].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def build_context(
    profile: Profile, design: Design, *, photo_size: int = STORED_PX
) -> ResumeContext:
    """Everything a template renders, in the order the design asks for."""
    sections: list[Section] = []
    for key in design.visible_sections():
        section = _build_section(profile, design, key)
        if section is not None:
            sections.append(section)

    headline = profile.basics.headline.strip() if design.show_headline else ""
    name = profile.basics.name.strip() or "Your name"
    portrait = (
        photo_data_uri(profile.basics.photo, photo_size) if design.wants_photo else ""
    )
    return ResumeContext(
        name=name,
        headline=headline,
        contact=build_contact(profile, design),
        sections=sections,
        photo=portrait,
        photo_shape=design.photo_shape,
        initials=initials(name) if design.wants_photo else "",
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
        photo_shape=context.photo_shape,
        initials=context.initials,
    )


def suggested_filename(profile: Profile, design: Design, suffix: str = "pdf") -> str:
    """``Muhammad-Ali-Akbar-Resume-Classic.pdf``.

    Named for the reader, not for us: this file lands in a stranger's
    downloads folder next to forty others called ``resume.pdf``.
    """
    name = re.sub(r"[^A-Za-z0-9]+", "-", profile.basics.name.strip()).strip("-")
    template = design.template_spec.name.replace(" ", "-")
    stem = "-".join(p for p in (name, "Resume", template) if p)
    return f"{stem or 'Resume'}.{suffix}"


def entry_titles(profile: Profile) -> list[str]:
    """Labels for everything printable, used by the fit report."""
    out: list[str] = []
    for key in ("experience", "projects", "education"):
        out += [entry_label(item) for item in getattr(profile, key)]
    return out
