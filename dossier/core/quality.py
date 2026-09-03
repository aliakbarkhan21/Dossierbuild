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

from .schema import Profile, iter_bullets

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

MAX_CHARS = 200
MIN_CHARS = 25


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

    @property
    def icon(self) -> str:
        return {"error": "!", "warning": "*", "note": "-"}[self.severity]


def check_text(
    text: str,
    block_id: str = "",
    *,
    is_summary: bool = False,
    vocabulary: Iterable[str] = (),
) -> list[Finding]:
    """Run every check against a single bullet or summary."""
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

    if not is_summary:
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
    elif not has_number and not is_summary:
        findings.append(
            Finding(
                block_id,
                "note",
                "names something specific but has no measurable outcome; "
                "a number here would land harder",
            )
        )

    if len(stripped) > MAX_CHARS:
        findings.append(
            Finding(
                block_id,
                "warning",
                f"{len(stripped)} characters -- over about {MAX_CHARS} this will wrap badly "
                "and push the resume past one page",
            )
        )
    elif len(stripped) < MIN_CHARS and not is_summary:
        findings.append(
            Finding(block_id, "note", "very short -- likely missing the outcome or the method")
        )

    if stripped.endswith("."):
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
