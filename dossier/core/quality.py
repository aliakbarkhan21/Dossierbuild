"""The bullet-writing standard, enforced as code.

The rule this encodes: a bullet should be something only you could have
written. If the nouns could be swapped out and the sentence would still
describe someone else's job, it is not carrying its weight.

This module is advisory. It never blocks a save -- a half-written bullet is
still worth storing. It exists so the standard is applied consistently, and so
that phase 3 can run AI-generated text through the same checks rather than
trusting the model to have followed instructions.

**On the specificity check.** The interesting problem here is deciding whether a
bullet names anything concrete. A fixed list of technology names is always
incomplete, and it is the wrong shape anyway -- a dataset name, a client, a
course or a competition is just as specific as a framework. So the check works
from three sources, best first:

1. **Your own vocabulary.** ``build_vocabulary`` collects the skills and project
   technologies you have already entered. Those are, by definition, the terms
   that matter on *your* resume, and the check gets sharper the more of your
   profile you fill in.
2. **Structural shapes.** Acronyms, internal capitals, dotted module names,
   ``C++``. These are almost never ordinary words.
3. **A common-technology fallback**, for names that are ordinary capitalised
   words and so invisible to (2) when they open a sentence.

Against those sits a stoplist, because a capitalised word is not automatically
meaningful: months, weekdays and a handful of generic business nouns get
capitalised constantly without making a sentence any more specific.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Literal

from .markup import plain
from .schema import Profile, format_date, is_month, iter_bullets

Severity = Literal["error", "warning", "note"]

# Phrases that describe duties rather than accomplishments, or that pad without
# adding information. Matched case-insensitively, as whole words.
FILLER_PHRASES: tuple[str, ...] = (
    "responsible for",
    "involved in",
    "participated in",
    "tasked with",
    "duties included",
    "contributed to",
    "utilised",
    "utilized",
    "leveraged",
    "spearheaded",
    "passionate about",
    "team player",
    "hard worker",
    "detail-oriented",
    "results-driven",
    "self-starter",
    "think outside the box",
    "wide range of",
    "various",
    "a variety of",
    "several different",
    "successfully",
    "effectively",
    "efficiently",
    "seamlessly",
    "state-of-the-art",
    "cutting-edge",
    "best practices",
    "synergy",
)

# Filler built on a verb, so every tense has to be caught. "Worked on",
# "working on" and "work on" are the same evasion.
FILLER_VERB_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bwork(?:ed|ing)?\s+on\b", "worked on"),
    (r"\bassist(?:ed|ing)?\s+(?:with|in)\b", "assisted with"),
    (r"\bhelp(?:ed|ing)?\s+(?:with|to|in)\b", "helped with"),
    (r"\bworked\s+as\s+part\s+of\b", "worked as part of"),
)

# Verbs that are technically past tense but say nothing about what changed.
WEAK_OPENERS: tuple[str, ...] = (
    "used",
    "made",
    "did",
    "got",
    "learned",
    "studied",
    "attended",
    "supported",
    "handled",
    "managed",
    "maintained",
)

NUMBER_RE = re.compile(r"\d")

# Structural shapes that are almost always a specific name.
SPECIFIC_SHAPE_RE = re.compile(
    r"\b("
    r"[A-Z][a-z]+[A-Z][A-Za-z]*"  # internal capital: PostgreSQL, TypeScript
    r"|[A-Z]{2,}"  # acronyms: API, ETL, SQL, CI
    r"|[a-z]+\.(?:js|py|ts|io|ai|sh)"  # node.js, next.js
    r"|[A-Za-z]+\+\+|[A-Za-z]+#"  # C++, C#
    r")\b"
)

# A capitalised word anywhere except the first position.
PROPER_NOUN_RE = re.compile(r"(?<!^)(?<![.!?]\s)\b[A-Z][a-z]{2,}\b")

# Capitalised words that carry no specificity. Without these, "Delivered the
# report in January" would count as naming something concrete.
NOT_SPECIFIC: frozenset[str] = frozenset(
    {
        "january", "february", "march", "april", "may", "june", "july",
        "august", "september", "october", "november", "december",
        "monday", "tuesday", "wednesday", "thursday", "friday",
        "saturday", "sunday", "spring", "summer", "autumn", "winter",
        "present", "current", "university", "college", "school", "company",
        "team", "project", "system", "software", "database", "application",
        "website", "platform", "solution", "process", "client", "customer",
        "manager", "student", "intern", "developer", "engineer",
    }
)

# Names that are ordinary capitalised words, so the rules above miss them when
# they open a bullet. Not exhaustive and not meant to be -- your own profile is
# the primary source, and this is the fallback for an empty profile.
COMMON_TECH: frozenset[str] = frozenset(
    {
        # languages
        "python", "java", "javascript", "typescript", "rust", "golang", "go",
        "kotlin", "swift", "ruby", "scala", "haskell", "matlab", "julia", "perl",
        "php", "dart", "elixir", "clojure", "lua", "assembly", "verilog",
        # data / ml
        "pandas", "numpy", "scipy", "pytorch", "tensorflow", "keras", "sklearn",
        "scikit-learn", "xgboost", "lightgbm", "huggingface", "transformers",
        "opencv", "spacy", "nltk", "langchain", "matplotlib", "seaborn", "plotly",
        # web / frameworks
        "django", "flask", "fastapi", "streamlit", "gradio", "react", "angular",
        "vue", "svelte", "next", "nuxt", "express", "spring", "rails", "laravel",
        "tailwind", "bootstrap", "jinja", "htmx",
        # infra / tools
        "docker", "kubernetes", "terraform", "ansible", "jenkins", "nginx",
        "apache", "linux", "ubuntu", "debian", "bash", "git", "github", "gitlab",
        "bitbucket", "jira", "figma", "vercel", "netlify", "heroku", "cloudflare",
        # data stores
        "postgres", "postgresql", "mysql", "sqlite", "mongodb", "redis", "kafka",
        "spark", "hadoop", "airflow", "snowflake", "elasticsearch", "dynamodb",
        "firebase", "supabase", "prisma", "sqlalchemy",
        # testing / misc
        "playwright", "selenium", "cypress", "pytest", "junit", "jest", "vitest",
        "gemini", "openai", "anthropic", "claude", "llama", "ollama",
        "unity", "unreal", "godot", "blender", "arduino", "raspberry",
    }
)

#: How long a line of each kind may run before it is worth saying something.
#:
#: One number for all of them was the bug: a summary is a paragraph and was
#: being told, at 1,017 characters, that "over about 200 this will wrap badly
#: and push the resume past one page" -- advice written for a bullet, applied
#: to prose, and wrong in both directions. A summary that short would be two
#: lines; a bullet that long is a paragraph pretending to be a bullet.
#:
#: ``(minimum, maximum)``. A minimum of 0 means the kind has no floor worth
#: enforcing -- a one-line section of prose is a legitimate thing to write.
LENGTH: dict[str, tuple[int, int]] = {
    "bullet": (25, 200),
    "summary": (120, 700),
    "prose": (0, 1200),
}

#: Kept for the callers and tests that named them before there were kinds.
MAX_CHARS = LENGTH["bullet"][1]
MIN_CHARS = LENGTH["bullet"][0]


def expand_terms(items: Iterable[str]) -> set[str]:
    """Lowercase a list of declared terms, plus their individual words.

    Multi-word entries such as "scikit-learn" or "Google Cloud" contribute their
    parts as well as the whole, so a bullet mentioning only half the phrase
    still matches.
    """
    terms = {item.strip().lower() for item in items if item and item.strip()}
    parts: set[str] = set()
    for term in terms:
        for part in re.split(r"[\s/,()+&-]+", term):
            if len(part) > 2:
                parts.add(part)
    return terms | parts


def build_vocabulary(profile: Profile) -> frozenset[str]:
    """Collect the specific terms this person has already declared.

    Everything in their skill groups, every technology listed against a project,
    and their coursework. These are the words that, appearing in a bullet, mean
    the bullet is talking about something real rather than gesturing at it.
    """
    items: list[str] = []
    for group in profile.skills:
        items.extend(group.items)
    for project in profile.projects:
        items.extend(project.tech)
    for entry in profile.education:
        items.extend(entry.coursework)
    return frozenset(expand_terms(items))


def mentions_specific(text: str, vocabulary: Iterable[str] = ()) -> bool:
    """Whether the text names anything concrete enough to be checkable."""
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z+#.\-]*", text.lower())]
    stripped = [w.strip(".-") for w in words]

    vocab = {v for v in vocabulary}
    if vocab and any(word in vocab for word in stripped):
        return True

    if SPECIFIC_SHAPE_RE.search(text):
        return True

    for match in PROPER_NOUN_RE.finditer(text):
        if match.group(0).lower() not in NOT_SPECIFIC:
            return True

    return any(word in COMMON_TECH for word in stripped)


@dataclass(frozen=True)
class Finding:
    """One thing worth changing about one block of text."""

    block_id: str
    severity: Severity
    message: str
    where: str = ""
    """Which part of the document, for a finding that is not about one line.

    "Experience, entry 2" rather than a block id, because the thing being
    reported -- an end date before its start, a heading with nothing under it
    -- belongs to an entry rather than to a sentence inside one.
    """

    @property
    def icon(self) -> str:
        return {"error": "!", "warning": "*", "note": "-"}[self.severity]


def check_text(
    text: str,
    block_id: str = "",
    *,
    is_summary: bool = False,
    kind: str = "",
    vocabulary: Iterable[str] = (),
) -> list[Finding]:
    """Run every check against one piece of writing, judged as its own kind.

    ``kind`` is "bullet", "summary" or "prose". It decides how long the line
    may run, whether a full stop at the end is worth a note, and whether the
    opening word is expected to be a verb -- because those rules disagree
    between a bullet and a paragraph, and applying a bullet's to a paragraph
    produced advice that was not merely unhelpful but wrong.

    ``is_summary`` is the old spelling of ``kind="summary"`` and still works:
    every caller that passed it meant exactly that.
    """
    kind = kind or ("summary" if is_summary else "bullet")
    is_summary = kind == "summary"
    #: Bullets are a form with rules -- lead with a verb, carry a number, no
    #: closing full stop. Prose is prose.
    is_bullet = kind == "bullet"
    # Formatting is not language. A bullet reading "cut runtime <b>68%</b>"
    # is nine words with a number in it, and counting the tags would fail it
    # for length and read "b" as a word nobody wrote.
    text = plain(text)
    findings: list[Finding] = []
    stripped = text.strip()

    if not stripped:
        return findings

    lowered = stripped.lower()
    seen_filler: set[str] = set()

    for phrase in FILLER_PHRASES:
        if re.search(rf"\b{re.escape(phrase)}\b", lowered):
            seen_filler.add(phrase)
    for pattern, label in FILLER_VERB_PATTERNS:
        if re.search(pattern, lowered):
            seen_filler.add(label)

    for phrase in sorted(seen_filler):
        findings.append(
            Finding(
                block_id,
                "error",
                f'"{phrase}" is filler -- say what changed instead of that you were near it',
            )
        )

    # A word the PDF extractor broke in half. Precise on purpose: a hyphen
    # followed by a space and a lowercase letter is not something anybody
    # types, and it is what "large-\nscale" turns into on its way through an
    # import. The general case -- a space dropped anywhere inside a word --
    # needs a dictionary to spot and is left to the writer's own eyes.
    for match in re.finditer(r"\b([A-Za-z]{2,})- ([a-z]{2,})\b", stripped):
        findings.append(
            Finding(
                block_id,
                "warning",
                f'"{match.group(0)}" looks like one word split by a PDF import '
                f'-- probably "{match.group(1)}-{match.group(2)}"',
            )
        )

    if is_bullet:
        first_word = re.split(r"\W+", lowered, maxsplit=1)[0]
        if first_word in WEAK_OPENERS:
            findings.append(
                Finding(
                    block_id,
                    "warning",
                    f'"{first_word}" is a weak opening verb -- it names an activity, not a result',
                )
            )
        elif first_word.endswith("ing"):
            findings.append(
                Finding(
                    block_id,
                    "note",
                    "starts with an -ing verb; past tense ('Built', 'Cut', 'Shipped') reads stronger",
                )
            )

    has_number = bool(NUMBER_RE.search(stripped))
    has_specific = mentions_specific(stripped, vocabulary)

    if not has_number and not has_specific:
        findings.append(
            Finding(
                block_id,
                "warning",
                "nothing specific here -- no number, no named tool, no proper noun. "
                "This could describe almost anyone",
            )
        )
    elif not has_number and is_bullet:
        findings.append(
            Finding(
                block_id,
                "note",
                "names something specific but has no measurable outcome; "
                "a number here would land harder",
            )
        )

    floor, ceiling = LENGTH.get(kind, LENGTH["bullet"])
    if len(stripped) > ceiling:
        over = len(stripped) - ceiling
        findings.append(
            Finding(
                block_id,
                "warning",
                f"{len(stripped)} characters"
                + (
                    f" -- about {over} more than a bullet carries before it wraps to "
                    "three lines and starts costing the page"
                    if is_bullet
                    else f" -- long for a {kind}; the last {over} are the ones nobody reaches"
                ),
            )
        )
    elif floor and len(stripped) < floor:
        findings.append(
            Finding(
                block_id,
                "note",
                "very short -- likely missing the outcome or the method"
                if is_bullet
                else "shorter than most readers expect here",
            )
        )

    # Only bullets. A paragraph ending in a full stop is a paragraph; the note
    # used to fire on the summary and say "bullets read cleaner without",
    # which announced its own mistake.
    if is_bullet and stripped.endswith("."):
        findings.append(Finding(block_id, "note", "trailing full stop; bullets read cleaner without"))

    return findings


def check_bullets(blocks: Iterable, vocabulary: Iterable[str] = ()) -> list[Finding]:
    """Check a collection of TextBlocks (one entry's bullets, typically)."""
    vocab = frozenset(vocabulary)
    findings: list[Finding] = []
    for block in blocks:
        findings.extend(check_text(block.text, block.id, vocabulary=vocab))
    return findings


def check_profile(profile: Profile) -> dict[str, list[Finding]]:
    """Check everything, returned as ``{block_id: [findings]}``."""
    vocabulary = build_vocabulary(profile)
    results: dict[str, list[Finding]] = {}
    for section, _owner_id, block in iter_bullets(profile):
        found = check_text(
            block.text,
            block.id,
            is_summary=(section == "summary"),
            vocabulary=vocabulary,
        )
        if found:
            results[block.id] = found
    return results


def summarise(results: dict[str, list[Finding]]) -> tuple[int, int, int]:
    """Return ``(errors, warnings, notes)`` across a whole check run."""
    errors = warnings = notes = 0
    for findings in results.values():
        for finding in findings:
            if finding.severity == "error":
                errors += 1
            elif finding.severity == "warning":
                warnings += 1
            else:
                notes += 1
    return errors, warnings, notes


# --------------------------------------------------------------------------
# The document, as against the writing in it
# --------------------------------------------------------------------------
#
# Everything above reads one line at a time and asks whether it is well
# written. Useful, and the same advice for everybody: lead with a verb, carry
# a number, do not say "responsible for". None of it can see that a resume has
# no email address on it, or that a job ends before it starts, or that the
# same bullet was pasted twice -- which are the faults that actually cost
# somebody an interview, and which are specific to their document.
#
# So these read the profile as a whole. Every one of them is a fact about this
# CV that a person can act on, and none of them fires on a resume that does not
# have the problem.

#: Past this many, a reader has stopped. Not a style rule -- a claim about
#: attention, and the reason the last bullets of a long entry are wasted.
CROWDED_ENTRY = 8


def check_document(profile: Profile) -> list[Finding]:
    """Faults in the document rather than in a sentence of it."""
    out: list[Finding] = []
    basics = profile.basics

    def add(severity: Severity, where: str, message: str) -> None:
        out.append(Finding("", severity, message, where))

    # ---- can anybody reply? ----------------------------------------
    if not plain(basics.name).strip():
        add("error", "Contact", "no name on the resume")
    if not plain(basics.email).strip():
        add("error", "Contact", "no email address -- there is no way to answer this")
    elif "@" not in plain(basics.email):
        add("error", "Contact", f'"{plain(basics.email)}" is not an email address')
    if not plain(basics.phone).strip():
        add("note", "Contact", "no phone number; some employers ring before they write")

    if not plain(profile.summary.text).strip():
        add(
            "warning",
            "Summary",
            "no summary -- the first thing read is a job title with no claim attached to it",
        )

    # ---- dates that cannot be true ---------------------------------
    for section in ("experience", "projects", "education"):
        for index, entry in enumerate(getattr(profile, section, []) or [], start=1):
            where = f"{section.title()}, entry {index}"
            start, end = getattr(entry, "start", None), getattr(entry, "end", None)
            if is_month(start) and is_month(end) and end < start:
                add(
                    "error",
                    where,
                    f"ends {format_date(end)} but starts {format_date(start)}",
                )
            if not start and not end:
                add("note", where, "no dates -- a reader cannot place it in your history")

            bullets = [b for b in getattr(entry, "bullets", []) or [] if b.text.strip()]
            if len(bullets) > CROWDED_ENTRY:
                add(
                    "note",
                    where,
                    f"{len(bullets)} bullets; past about {CROWDED_ENTRY} the last ones are "
                    "read by nobody -- cut or promote them",
                )

    # ---- the same line twice ---------------------------------------
    seen: dict[str, str] = {}
    for section, owner, block in iter_bullets(profile):
        key = re.sub(r"[^a-z0-9]+", " ", plain(block.text).lower()).strip()
        if len(key) < 20:
            continue
        if key in seen:
            add("warning", section.title(), f'the same line appears twice: "{block.text.strip()[:60]}…"')
        else:
            seen[key] = owner

    # ---- a heading with nothing under it ---------------------------
    for custom in profile.sections:
        title = plain(custom.title).strip()
        if not title:
            add("note", "Other sections", "a section with no heading will print without one")
        elif not custom.text.strip() and not any(b.text.strip() for b in custom.bullets):
            add("warning", title, "a heading with nothing under it -- it will not print at all")

    return out
