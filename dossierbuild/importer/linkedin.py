"""Read a LinkedIn data-export archive into the profile schema.

Why this route rather than an API or a scraper
----------------------------------------------
LinkedIn's public OAuth product ("Sign In with LinkedIn using OpenID Connect")
returns name, email, picture and locale -- and nothing else. Positions,
education, skills and certifications sit behind the Profile API, which has been
restricted to contracted partners since the 2015 scope deprecation. So there is
no supported way to ask LinkedIn's API for the data this module needs.

Scraping a logged-in profile page would work technically and is prohibited by
the LinkedIn User Agreement, risks the account, and would mean handling the
user's password. Not built.

What LinkedIn *does* offer is a full export of your own data, on request:
Settings -> Data Privacy -> Get a copy of your data. It arrives as a ZIP of
CSVs. That is this module's input. It is better input than scraping would be:
already structured, so nothing has to be inferred.

Robustness notes
----------------
Column names in the export have drifted over the years and vary by locale, so
every lookup goes through ``_pick``, which matches case-insensitively against
several candidate names and returns "" rather than raising. A missing CSV is
skipped, not fatal -- a partial import is still worth having.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from dataclasses import dataclass, field
from typing import Iterable

from ..schema import (
    Award,
    Certification,
    Education,
    Experience,
    Profile,
    Project,
    SkillGroup,
    TextBlock,
)

# Files we know how to read, mapped to the section they feed.
KNOWN_FILES = {
    "profile.csv": "basics",
    "positions.csv": "experience",
    "education.csv": "education",
    "skills.csv": "skills",
    "certifications.csv": "certifications",
    "projects.csv": "projects",
    "honors.csv": "awards",
    "email addresses.csv": "basics",
}

MONTHS = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
    "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}


@dataclass
class LinkedInImport:
    """What came out of the archive, plus what could not be read."""

    profile: Profile
    files_found: list[str] = field(default_factory=list)
    files_skipped: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Field helpers
# --------------------------------------------------------------------------


def _pick(row: dict[str, str], *names: str) -> str:
    """First non-empty value among several candidate column names."""
    lowered = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value:
            return value
    return ""


def parse_date(value: str) -> str | None:
    """Turn a LinkedIn date into "YYYY-MM" or "YYYY", or None if unreadable.

    The export writes dates several ways depending on what the member entered:
    "Jun 2025", "2025", "06/2025", "2025-06-01".

    A year with no month is returned as a year. An earlier version forced these
    to January, which meant a graduation date of "2027" would be printed on the
    resume as "Jan 2027" -- a month nobody had stated. The schema accepts both
    precisions precisely so that this stays honest.
    """
    value = (value or "").strip()
    if not value:
        return None

    match = re.match(r"^(\d{4})-(\d{2})", value)  # 2025-06-01
    if match and "01" <= match.group(2) <= "12":
        return f"{match.group(1)}-{match.group(2)}"

    match = re.match(r"^(\d{1,2})/(\d{4})$", value)  # 06/2025
    if match:
        return f"{match.group(2)}-{int(match.group(1)):02d}"

    match = re.match(r"^([A-Za-z]{3})[a-z]*\s+(\d{4})$", value)  # Jun 2025
    if match:
        month = MONTHS.get(match.group(1).lower())
        if month:
            return f"{match.group(2)}-{month}"

    match = re.match(r"^(\d{4})$", value)  # 2025 -- year only, kept as a year
    if match:
        return match.group(1)

    return None


def split_description(text: str) -> list[TextBlock]:
    """Split a LinkedIn description field into bullet points.

    Members write these as newline-separated lines, as one paragraph, or with
    literal bullet characters pasted in. Leading bullet glyphs and numbering are
    stripped; a single long paragraph is split on sentence boundaries only if it
    is long enough that leaving it whole would be worse.
    """
    text = (text or "").strip()
    if not text:
        return []

    lines = [line.strip() for line in re.split(r"[\r\n]+", text) if line.strip()]
    cleaned = [re.sub(r"^[\-•·\*●▪‣⁃]+\s*|^\d+[.)]\s*", "", line) for line in lines]
    cleaned = [line for line in cleaned if line]

    if len(cleaned) == 1 and len(cleaned[0]) > 300:
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", cleaned[0])
        cleaned = [s.strip() for s in sentences if len(s.strip()) > 20]

    return [TextBlock(text=line) for line in cleaned]


def _rows(data: bytes) -> list[dict[str, str]]:
    """Read one CSV. LinkedIn exports UTF-8, sometimes with a BOM.

    Some files open with a "Notes:" preamble before the real header row. Only
    that specific marker is skipped: an earlier version of this dropped every
    leading line without a comma, which silently emptied ``Skills.csv`` --
    a single-column file where no line has a comma at all.
    """
    text = data.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    while lines and (not lines[0].strip() or lines[0].strip().lower().startswith(("notes:", "note:"))):
        lines.pop(0)
    if not lines:
        return []
    return list(csv.DictReader(io.StringIO("\n".join(lines))))


# --------------------------------------------------------------------------
# Per-file readers
# --------------------------------------------------------------------------


def _read_profile(rows: Iterable[dict[str, str]], profile: Profile) -> None:
    for row in rows:
        first = _pick(row, "First Name")
        last = _pick(row, "Last Name")
        name = " ".join(p for p in (first, last) if p)
        if name:
            profile.basics.name = name
        profile.basics.headline = _pick(row, "Headline") or profile.basics.headline
        profile.basics.location = (
            _pick(row, "Geo Location", "Location", "Address") or profile.basics.location
        )
        summary = _pick(row, "Summary")
        if summary:
            profile.summary.text = summary
        break  # Profile.csv holds exactly one member


def _read_emails(rows: Iterable[dict[str, str]], profile: Profile) -> None:
    best = ""
    for row in rows:
        address = _pick(row, "Email Address")
        if not address:
            continue
        if _pick(row, "Primary").lower() in {"yes", "true"}:
            best = address
            break
        best = best or address
    if best and not profile.basics.email:
        profile.basics.email = best


def _read_positions(rows: Iterable[dict[str, str]], profile: Profile) -> None:
    for row in rows:
        title = _pick(row, "Title")
        company = _pick(row, "Company Name", "Company")
        if not (title or company):
            continue
        profile.experience.append(
            Experience(
                role=title,
                organisation=company,
                location=_pick(row, "Location"),
                start=parse_date(_pick(row, "Started On", "Start Date")),
                end=parse_date(_pick(row, "Finished On", "End Date")),
                bullets=split_description(_pick(row, "Description")),
            )
        )


def _read_education(rows: Iterable[dict[str, str]], profile: Profile) -> None:
    for row in rows:
        school = _pick(row, "School Name", "School")
        degree = _pick(row, "Degree Name", "Degree")
        if not (school or degree):
            continue
        field_of_study = _pick(row, "Field Of Study", "Field of Study")
        credential = " ".join(p for p in (degree, field_of_study) if p)
        profile.education.append(
            Education(
                institution=school,
                credential=credential,
                start=parse_date(_pick(row, "Start Date", "Started On")),
                end=parse_date(_pick(row, "End Date", "Finished On")),
                bullets=split_description(_pick(row, "Notes", "Activities", "Description")),
            )
        )


def _read_skills(rows: Iterable[dict[str, str]], profile: Profile) -> None:
    names = [_pick(row, "Name", "Skill") for row in rows]
    names = [n for n in names if n]
    if names:
        # LinkedIn exports skills flat and uncategorised. Dropping them into one
        # group named "Imported from LinkedIn" makes it obvious they still need
        # sorting into real groups, rather than pretending the grouping is real.
        profile.skills.append(SkillGroup(label="Imported from LinkedIn", items=names))


def _read_certifications(rows: Iterable[dict[str, str]], profile: Profile) -> None:
    for row in rows:
        name = _pick(row, "Name")
        if not name:
            continue
        profile.certifications.append(
            Certification(
                name=name,
                issuer=_pick(row, "Authority", "Issuer"),
                issued=parse_date(_pick(row, "Started On", "Issued On", "Start Date")),
                url=_pick(row, "Url", "URL"),
            )
        )


def _read_projects(rows: Iterable[dict[str, str]], profile: Profile) -> None:
    for row in rows:
        title = _pick(row, "Title", "Name")
        if not title:
            continue
        profile.projects.append(
            Project(
                name=title,
                url=_pick(row, "Url", "URL"),
                start=parse_date(_pick(row, "Started On", "Start Date")),
                end=parse_date(_pick(row, "Finished On", "End Date")),
                bullets=split_description(_pick(row, "Description")),
            )
        )


def _read_honors(rows: Iterable[dict[str, str]], profile: Profile) -> None:
    for row in rows:
        title = _pick(row, "Title", "Name")
        if not title:
            continue
        profile.awards.append(
            Award(
                title=title,
                awarded_by=_pick(row, "Issuer", "Authority"),
                date=parse_date(_pick(row, "Issued On", "Date")),
                note=_pick(row, "Description"),
            )
        )


READERS = {
    "profile.csv": _read_profile,
    "email addresses.csv": _read_emails,
    "positions.csv": _read_positions,
    "education.csv": _read_education,
    "skills.csv": _read_skills,
    "certifications.csv": _read_certifications,
    "projects.csv": _read_projects,
    "honors.csv": _read_honors,
}


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def parse_export(data: bytes) -> LinkedInImport:
    """Parse a LinkedIn export ZIP into a candidate profile."""
    result = LinkedInImport(profile=Profile.empty())

    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValueError(
            "That file is not a readable ZIP archive. Upload the archive LinkedIn "
            "emailed you, without unzipping it first."
        ) from exc

    members = {name.split("/")[-1].lower(): name for name in archive.namelist() if name.lower().endswith(".csv")}

    if not members:
        raise ValueError(
            "No CSV files inside that ZIP. Make sure this is the LinkedIn data "
            "export and not, for example, a folder of documents."
        )

    for filename, reader in READERS.items():
        member = members.get(filename)
        if member is None:
            result.files_skipped.append(filename)
            continue
        try:
            rows = _rows(archive.read(member))
        except Exception as exc:  # noqa: BLE001 -- one bad file must not sink the import
            result.notes.append(f"{filename} could not be read ({exc}); skipped.")
            result.files_skipped.append(filename)
            continue
        reader(rows, result.profile)
        result.files_found.append(filename)

    unknown = sorted(set(members) - set(READERS))
    if unknown:
        result.notes.append(
            f"{len(unknown)} other CSVs in the archive were ignored "
            f"(connections, messages, ad data and so on)."
        )

    if not result.files_found:
        raise ValueError(
            "The ZIP contained CSVs, but none of the ones this reads "
            "(Profile, Positions, Education, Skills, Certifications, Projects, Honors). "
            "If you requested a partial export, request the full archive instead."
        )

    return result
