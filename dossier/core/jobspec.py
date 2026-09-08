"""A job description, read without a model, and matched against the profile.

This is the half of tailoring that does not need an API key, and keeping it
that way was the point. Everything here -- which terms the posting actually
asks for, which of them your profile already evidences, and which of your
entries speak to this role -- is computed from the text by rules you can read.
The model in ``ai/tailor.py`` is handed the *result* of this analysis; it is
never asked to decide what the job requires, because a hallucinated
requirement would silently re-angle a whole resume.

It also means the gap analysis still works when Gemini is down, when there is
no key, and inside a test.

**How a term is found.** Three sources, and a posting names things in all
three:

1. **The technology lexicon** -- ``quality.COMMON_TECH``, plus multi-word
   competencies a single-word scan cannot see ("machine learning" is not
   "machine" and "learning").
2. **Structural shapes** -- acronyms, internal capitals, dotted module names,
   ``C++``. ``PyTorch`` and ``ETL`` are specific whether or not anyone
   enumerated them.
3. **What you have already declared.** A term in your own skills or project
   stacks is, by definition, one that matters on your resume; when the posting
   mentions it too, that is the strongest possible match.

**How a term is weighted.** Postings are structured documents, and the
structure carries meaning that a bag of words throws away. A term under
"Requirements" is not the same claim as one under "Nice to have", so headings
are detected and set a tier which multiplies the term's weight. Repetition
counts too, but with a low ceiling -- a word said four times is emphatic, not
four times as important.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from .quality import COMMON_TECH, SPECIFIC_SHAPE_RE, expand_terms
from .markup import plain
from .schema import Profile, entry_label

Tier = Literal["required", "preferred", "general"]

# What each tier multiplies a term's weight by. "Required" is worth roughly
# twice a bare mention because that is how a reader treats it; "preferred" sits
# between the two rather than below general text, since a posting bothered to
# name it at all.
TIER_WEIGHT: dict[Tier, float] = {"required": 2.0, "preferred": 1.4, "general": 1.0}

# Headings that switch the tier for everything under them, matched against a
# line that reads as a heading (short, and often ending in a colon).
TIER_HEADINGS: tuple[tuple[Tier, tuple[str, ...]], ...] = (
    (
        "required",
        (
            "requirement", "required", "qualification", "must have", "must-have",
            "essential", "you will need", "what you need", "minimum", "we require",
            "who you are", "about you", "skills and experience",
        ),
    ),
    (
        "preferred",
        (
            "nice to have", "nice-to-have", "preferred", "desirable", "bonus",
            "plus", "advantageous", "would be great", "beneficial",
        ),
    ),
    (
        "general",
        (
            "responsibilit", "what you will do", "what you'll do", "the role",
            "about the role", "about us", "day to day", "benefits", "we offer",
            "perks", "how to apply", "equal opportunit", "salary",
        ),
    ),
)

# Sections that are not about the candidate at all. Their contents are skipped
# outright rather than demoted: a benefits list offering a MacBook and Slack
# swag was, in testing, read as two things the resume needed to answer.
IGNORED_SECTIONS = (
    "benefit", "we offer", "perk", "how to apply", "equal opportunit",
    "salary", "compensation", "about us", "our values", "diversity",
)

# Competencies that are phrases. A word-by-word scan finds neither half of
# "machine learning", and "learning" alone would be noise.
PHRASE_LEXICON: tuple[str, ...] = (
    "machine learning", "deep learning", "reinforcement learning",
    "natural language processing", "computer vision", "large language model",
    "neural network", "data science", "data engineering", "data pipeline",
    "data analysis", "data visualisation", "data visualization", "feature engineering",
    "model deployment", "model training", "prompt engineering", "vector database",
    "time series", "predictive model", "statistical analysis", "a/b testing",
    "software engineering", "web development", "mobile development",
    "back end", "backend", "front end", "frontend", "full stack", "full-stack",
    "rest api", "restful api", "graphql", "microservices", "distributed systems",
    "object oriented", "object-oriented", "functional programming",
    "unit testing", "integration testing", "test driven", "test-driven",
    "version control", "code review", "continuous integration", "ci/cd",
    "cloud computing", "cloud infrastructure", "infrastructure as code",
    "technical writing", "technical documentation", "requirements gathering",
    "stakeholder management", "cross functional", "cross-functional",
    "agile", "scrum", "kanban", "problem solving", "problem-solving",
    "customer support", "technical support", "incident response",
    "database design", "query optimisation", "query optimization",
    "operating systems", "computer networks", "information security",
    "linear algebra", "probability", "statistics", "calculus", "discrete mathematics",
)

# Extra single words the technology lexicon does not carry, because they are
# disciplines and tools rather than libraries.
EXTRA_LEXICON: frozenset[str] = frozenset(
    {
        "algorithms", "api", "apis", "automation", "aws", "azure", "bash",
        "ci", "cd", "cli", "css", "dashboards", "debugging", "devops",
        "documentation", "etl", "excel", "gcp", "git", "html", "http",
        "json", "jupyter", "latex", "llm", "llms", "logging", "matlab",
        "ml", "networking", "nlp", "notebooks", "numpy", "oop", "orm",
        "pipelines", "powerbi", "prototyping", "python", "pytorch", "regex",
        "rest", "scraping", "scripting", "sdk", "seo", "sql", "tableau",
        "testing", "ui", "ux", "vba", "wireframes", "xml", "yaml",
    }
)

# Capitalised or technical-looking words that carry no requirement. Without
# this, every posting "requires" Monday, English and the company's own name in
# the same breath as Python.
STOPLIST: frozenset[str] = frozenset(
    {
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
        "sunday", "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december",
        "we", "you", "our", "your", "the", "and", "or", "for", "with", "this",
        "that", "will", "must", "should", "can", "able", "ability", "strong",
        "excellent", "good", "great", "solid", "proven", "demonstrable",
        "experience", "experienced", "knowledge", "understanding", "familiarity",
        "skills", "skill", "years", "year", "role", "job", "team", "teams",
        "company", "candidate", "candidates", "applicant", "position", "work",
        "working", "working", "opportunity", "environment", "culture", "office",
        "remote", "hybrid", "onsite", "salary", "benefits", "pension", "holiday",
        "degree", "bachelor", "bachelors", "master", "masters", "phd", "university",
        "graduate", "undergraduate", "student", "internship", "intern",
        "full", "part", "time", "permanent", "contract", "monday-friday",
        "please", "apply", "cv", "resume", "email", "contact", "linkedin",
        "uk", "us", "usa", "eu", "english", "visa", "sponsorship",
        "day", "week", "month", "including", "etc", "eg", "ie",
        "a", "an", "of", "to", "in", "on", "at", "as", "is", "are", "be",
    }
)

WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#./\-]*")

# A line that opens with a bullet marker is an item in a list, whatever else
# it looks like. This is load-bearing: postings list single-word requirements
# constantly ("- Docker", "- SQL", "- Python"), and every one of those is short
# and Title Case or all-caps, so the heading test below matched them and the
# reader skipped the requirement entirely. It cost `sql`, `docker`, `python`
# and `tableau` across three test postings before it was caught.
LIST_MARKER_RE = re.compile(r"^\s*(?:[-*•‣◦–—+]|\(?\d{1,2}[.)])\s+")


# Every heading phrase the reader acts on. Recognising these by name beats
# guessing from capitalisation: "Nice to have" is not Title Case and would be
# missed, while "Docker" is and would be invented. A heading this does not
# know changes no tier anyway, so treating it as ordinary text is the correct
# fallback rather than a gap.
KNOWN_HEADINGS: frozenset[str] = frozenset(
    needle for _tier, needles in TIER_HEADINGS for needle in needles
) | frozenset(IGNORED_SECTIONS)


# A heading is short, is not a list item, and announces itself -- with a colon,
# by being one of the phrases above, or by being shouted in capitals. Postings
# are written in Word, not Markdown, so the "##" that would make this trivial
# is never there.
def _is_heading(line: str) -> bool:
    if LIST_MARKER_RE.match(line):
        return False
    stripped = line.strip().strip("*#• \t")
    if not stripped or len(stripped) > 60:
        return False
    if stripped.endswith(":"):
        return True
    lowered = stripped.lower()
    if any(needle in lowered for needle in KNOWN_HEADINGS):
        return True
    # All-caps needs a second word: a posting listing a bare "SQL" on its own
    # line is shouting a requirement, not opening a section.
    return stripped.isupper() and len(stripped.split()) >= 2


def _tier_of(line: str) -> Tier | None:
    """The tier a heading line switches to, or None if it is not a heading."""
    if not _is_heading(line):
        return None
    lowered = line.strip().lower()
    for tier, needles in TIER_HEADINGS:
        if any(needle in lowered for needle in needles):
            return tier
    return None


def _singular(key: str, lexicon: frozenset[str]) -> str:
    """"APIs" and "API" are one requirement, not two."""
    if key.endswith("s") and key[:-1] in lexicon:
        return key[:-1]
    return key


def _absorb_into_phrases(counts: dict[str, int]) -> set[str]:
    """Keys made redundant by a longer phrase that was also found.

    A posting saying "REST APIs" yields ``rest``, ``api`` and ``rest api``, and
    scoring all three counts one requirement three times -- which is enough to
    outrank an actual second requirement. The phrase is the specific reading,
    so its parts are dropped. ``sql`` survives alongside ``postgresql`` because
    that is a substring, not a word.
    """
    phrases = [key for key in counts if " " in key or "/" in key]
    redundant: set[str] = set()
    for phrase in phrases:
        for part in re.split(r"[\s/]+", phrase):
            if part and part != phrase and part in counts:
                redundant.add(part)
    return redundant


@dataclass(frozen=True)
class Term:
    """One thing the posting asks for."""

    text: str
    """The surface form the posting used -- its casing, not ours. A canonical
    spelling table would be one more thing to maintain and to get wrong, and
    the employer's own spelling is the one worth mirroring anyway."""

    key: str
    weight: float
    count: int
    tier: Tier


@dataclass(frozen=True)
class Evidence:
    """Where in the profile a required term is already backed up."""

    section: str
    entry_id: str
    entry_label: str
    block_id: str
    text: str


@dataclass
class JobSpec:
    """A posting, read."""

    title: str = ""
    company: str = ""
    text: str = ""
    terms: list[Term] = field(default_factory=list)

    @property
    def required(self) -> list[Term]:
        return [t for t in self.terms if t.tier == "required"]


@dataclass
class EntryScore:
    """How much one profile entry speaks to this posting."""

    section: str
    entry_id: str
    label: str
    score: float
    matched: list[str]


@dataclass
class MatchReport:
    spec: JobSpec
    covered: dict[str, list[Evidence]]
    missing: list[Term]
    entries: list[EntryScore]
    coverage: int
    """Percentage of the posting's weight your profile already evidences."""

    declared_only: list[str]
    """Terms found only in your skills list, with no bullet backing them up.
    Listing a language you never describe using is the weakest kind of claim,
    and a posting asking for it is exactly when that shows."""


# --------------------------------------------------------------------------
# Reading the posting
# --------------------------------------------------------------------------


def _lexicon() -> frozenset[str]:
    return COMMON_TECH | EXTRA_LEXICON


def guess_title(text: str) -> str:
    """The role title, taken from the first line that reads like one.

    Deliberately shallow. This fills in a heading on screen and the PDF's file
    name; getting it wrong costs a user one edit, and asking a model for it
    would cost an API call and a fabrication risk for the same result.
    """
    for line in text.splitlines():
        stripped = line.strip().strip("*#-• \t")
        if 3 <= len(stripped) <= 80 and not stripped.endswith("."):
            return stripped
    return ""


def read_posting(text: str, *, title: str = "", company: str = "") -> JobSpec:
    """Turn posting text into a weighted list of what it asks for."""
    lexicon = _lexicon()
    counts: dict[str, int] = {}
    surface: dict[str, str] = {}
    best_tier: dict[str, Tier] = {}

    def record(key: str, shown: str, tier: Tier) -> None:
        key = _singular(key, lexicon)
        if key in STOPLIST or len(key) < 2:
            return
        counts[key] = counts.get(key, 0) + 1
        surface.setdefault(key, shown)
        # A term named as required anywhere is required, even if it also
        # appears in the friendly paragraph at the top.
        current = best_tier.get(key, "general")
        if TIER_WEIGHT[tier] > TIER_WEIGHT[current]:
            best_tier[key] = tier
        else:
            best_tier.setdefault(key, tier)

    tier: Tier = "general"
    ignoring = False
    for line in text.splitlines():
        lowered = line.lower()

        if _is_heading(line):
            ignoring = any(needle in lowered for needle in IGNORED_SECTIONS)
            switched = _tier_of(line)
            if switched is not None:
                tier = switched
            # The heading itself is prose, not a requirement.
            continue

        if ignoring:
            continue

        for phrase in PHRASE_LEXICON:
            if phrase in lowered:
                record(phrase, phrase, tier)

        for match in WORD_RE.finditer(line):
            word = match.group(0)
            key = word.lower().strip(".-/")
            if key in lexicon:
                record(key, word, tier)

        for match in SPECIFIC_SHAPE_RE.finditer(line):
            shown = match.group(0)
            record(shown.lower().strip(".-/"), shown, tier)

    for key in _absorb_into_phrases(counts):
        counts.pop(key, None)

    terms = [
        Term(
            text=surface[key],
            key=key,
            # Repetition is emphasis, not multiplication: capped at three so a
            # word repeated through a long posting cannot outweigh a stated
            # requirement mentioned once.
            weight=round(TIER_WEIGHT[best_tier[key]] * (1 + 0.25 * min(count, 3)), 3),
            count=count,
            tier=best_tier[key],
        )
        for key, count in counts.items()
    ]
    terms.sort(key=lambda t: (-t.weight, t.key))

    return JobSpec(
        title=title or guess_title(text),
        company=company,
        text=text,
        # A posting names a few dozen things at most; past that it is
        # boilerplate, and a wall of 200 chips helps nobody choose.
        terms=terms[:40],
    )


# --------------------------------------------------------------------------
# Matching it against the profile
# --------------------------------------------------------------------------


def _entry_texts(profile: Profile) -> list[tuple[str, str, str, str, str]]:
    """``(section, entry_id, label, block_id, text)`` for everything searchable.

    Entry headings are included as their own searchable block -- a role called
    "Data Engineering Intern" evidences "data engineering" even when no bullet
    repeats the phrase.
    """
    rows: list[tuple[str, str, str, str, str]] = []
    rows.append(("summary", "summary", "Summary", profile.summary.id, plain(profile.summary.text)))

    for section in ("experience", "projects", "education"):
        for entry in getattr(profile, section):
            label = entry_label(entry)
            heading = " ".join(
                str(getattr(entry, name, "") or "")
                for name in ("role", "organisation", "name", "tagline", "credential", "institution")
            )
            extras = " ".join(getattr(entry, "tech", []) or getattr(entry, "coursework", []) or [])
            rows.append((section, entry.id, label, f"{entry.id}:heading", f"{heading} {extras}"))
            for block in entry.bullets:
                rows.append((section, entry.id, label, block.id, plain(block.text)))

    return rows


def _mentions(haystack: str, key: str) -> bool:
    """Whether a term appears in a piece of text, as a word rather than a
    substring. Without the boundary, "go" matches "algorithm" and "R" matches
    everything."""
    if not haystack:
        return False
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(key)}(?![A-Za-z0-9])", haystack.lower()) is not None


def match(profile: Profile, spec: JobSpec) -> MatchReport:
    """Which of the posting's terms your profile already backs up, and where."""
    rows = _entry_texts(profile)

    declared: set[str] = set()
    for group in profile.skills:
        declared |= expand_terms(group.items)
    for project in profile.projects:
        declared |= expand_terms(project.tech)
    for education in profile.education:
        declared |= expand_terms(education.coursework)

    covered: dict[str, list[Evidence]] = {}
    declared_only: list[str] = []

    for term in spec.terms:
        hits = [
            Evidence(section, entry_id, label, block_id, text)
            for section, entry_id, label, block_id, text in rows
            if _mentions(text, term.key)
        ]
        if hits:
            covered[term.key] = hits
        elif term.key in declared:
            # Declared but never described. It counts as covered for the ATS,
            # and as a weak spot for a human reader, so it is reported as both.
            covered[term.key] = []
            declared_only.append(term.text)

    missing = [t for t in spec.terms if t.key not in covered]

    total = sum(t.weight for t in spec.terms)
    met = sum(t.weight for t in spec.terms if t.key in covered)
    coverage = round(100 * met / total) if total else 0

    # Per-entry relevance: the weight of the posting this entry alone answers.
    # Scored on the entry's whole text, so a project's stack counts as much as
    # its bullets -- which is how a reader skims it.
    per_entry: dict[str, EntryScore] = {}
    for section, entry_id, label, _block_id, text in rows:
        if section == "summary":
            continue
        score = per_entry.get(entry_id) or EntryScore(section, entry_id, label, 0.0, [])
        for term in spec.terms:
            if term.key not in score.matched and _mentions(text, term.key):
                score.matched.append(term.key)
                score.score += term.weight
        per_entry[entry_id] = score

    entries = sorted(per_entry.values(), key=lambda e: -e.score)

    return MatchReport(
        spec=spec,
        covered=covered,
        missing=missing,
        entries=entries,
        coverage=coverage,
        declared_only=declared_only,
    )


def analyse(profile: Profile, text: str, *, title: str = "", company: str = "") -> MatchReport:
    """Read a posting and match it, in one call."""
    return match(profile, read_posting(text, title=title, company=company))
