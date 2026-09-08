"""Tailoring self-check. Run with:  python scripts/check_tailor.py

Two halves, and the split is the point.

``core/jobspec.py`` is fully covered here, because it is deterministic: the
same posting always yields the same terms, weights and coverage, so every
claim the Tailor screen makes about a job can be pinned to a test.

The Gemini call itself is not exercised -- it needs a key and a network -- but
``ai/tailor.audit`` is, exhaustively. That function is the only thing standing
between a model's confident sentence and a number on someone's resume that
they cannot defend in an interview, so it is checked against the cases that
actually matter: an invented metric, an invented technology, a technology the
user really does have, and a rewrite that changes nothing but the wording.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dossier.ai import suggest
from dossier.ai.tailor import apply_suggestions, audit, _known_vocabulary
from dossier.core import jobspec
from dossier.core.schema import (
    Education,
    Experience,
    Profile,
    Project,
    SkillGroup,
    TextBlock,
)

from _harness import check, run


POSTING = """AI Engineering Intern
Northgate Analytics

About the role:
You will help the data team ship features.

Requirements:
- Strong Python, including pandas
- SQL and PostgreSQL
- Version control with Git

Nice to have:
- Docker and CI/CD
- Exposure to PyTorch

Benefits:
- A MacBook and free lunches
"""


def sample_profile() -> Profile:
    profile = Profile.empty()
    profile.summary = TextBlock(id="sum_main", text="Student who builds data tools.")
    profile.experience = [
        Experience(
            id="exp_1",
            role="Data Intern",
            organisation="TeleTaleem",
            bullets=[
                TextBlock(id="blt_1", text="Cleaned 8,400 rows of survey data with pandas"),
                TextBlock(id="blt_2", text="Wrote onboarding documentation for new starters"),
            ],
        )
    ]
    profile.projects = [
        Project(
            id="prj_1",
            name="Loot Ledger",
            tech=["Python", "SQLite"],
            bullets=[TextBlock(id="blt_3", text="Built a budget tracker in Python")],
        )
    ]
    profile.education = [
        Education(id="edu_1", institution="SZABIST", credential="BS Artificial Intelligence")
    ]
    profile.skills = [SkillGroup(id="skg_1", label="Languages", items=["Python", "SQL"])]
    return profile


# --------------------------------------------------------------------------
# Reading the posting
# --------------------------------------------------------------------------


@check("a posting's terms are found, and the title is read off the first line")
def test_reads_posting() -> None:
    spec = jobspec.read_posting(POSTING)
    keys = {t.key for t in spec.terms}
    assert spec.title == "AI Engineering Intern", spec.title
    for expected in ("python", "pandas", "sql", "postgresql", "git", "docker", "pytorch"):
        assert expected in keys, f"{expected} not found in {sorted(keys)}"


@check("a heading raises the weight of everything under it")
def test_tiers() -> None:
    spec = jobspec.read_posting(POSTING)
    tier = {t.key: t.tier for t in spec.terms}
    assert tier["python"] == "required", tier
    assert tier["pandas"] == "required", tier
    assert tier["docker"] == "preferred", tier
    assert tier["pytorch"] == "preferred", tier

    weight = {t.key: t.weight for t in spec.terms}
    assert weight["python"] > weight["docker"], weight


@check("a benefits section is not read as a list of requirements")
def test_benefits_skipped() -> None:
    keys = {t.key for t in jobspec.read_posting(POSTING).terms}
    assert "macbook" not in keys, "a perk became a requirement"
    assert not any("lunch" in k for k in keys), keys


@check("a phrase absorbs its own parts, so one requirement is counted once")
def test_phrase_absorbs_parts() -> None:
    spec = jobspec.read_posting(
        "Requirements:\n- REST APIs and CI/CD pipelines\n- Familiar with version control\n"
    )
    keys = {t.key for t in spec.terms}
    assert "ci/cd" in keys, keys
    assert "ci" not in keys and "cd" not in keys, f"CI/CD counted three times: {keys}"
    assert "rest api" in keys, keys
    assert "rest" not in keys, keys


@check("a single-word bullet is a requirement, not a heading")
def test_single_word_list_items() -> None:
    """The bug this pins cost four requirements across three postings.

    "- Docker", "- SQL" and "- Python" are short and Title Case or all-caps,
    which is exactly what the heading test looked for, so the reader treated
    each as a section heading and skipped the line -- silently dropping the
    requirement. Postings list single-word requirements constantly.
    """
    spec = jobspec.read_posting(
        "Requirements:\n- Python\n- SQL\n- Docker\n• Tableau\n1. Excel\n"
    )
    keys = {t.key for t in spec.terms}
    for expected in ("python", "sql", "docker", "tableau", "excel"):
        assert expected in keys, f"{expected} was swallowed as a heading: {sorted(keys)}"
    assert all(t.tier == "required" for t in spec.terms), [(t.key, t.tier) for t in spec.terms]


@check("headings are recognised by name, not by capitalisation")
def test_heading_detection() -> None:
    for line in ("Requirements:", "REQUIREMENTS", "Nice to have", "Benefits", "About the role"):
        assert jobspec._is_heading(line), f"{line!r} should be a heading"
    for line in ("- Docker", "• Python", "1. Tableau", "SQL", "Docker",
                 "You will help the team ship features."):
        assert not jobspec._is_heading(line), f"{line!r} should not be a heading"

    # "Nice to have" is not Title Case, so a casing rule misses it and every
    # preferred term underneath is scored as though it were merely mentioned.
    spec = jobspec.read_posting("Requirements:\n- Python\n\nNice to have\n- Docker\n")
    tier = {t.key: t.tier for t in spec.terms}
    assert tier == {"python": "required", "docker": "preferred"}, tier


@check("a term is matched as a word, never as a substring")
def test_word_boundaries() -> None:
    profile = Profile.empty()
    profile.experience = [
        Experience(id="e", role="Analyst", bullets=[TextBlock(id="b", text="Wrote algorithms")])
    ]
    spec = jobspec.read_posting("Requirements:\n- Go and Rust\n")
    report = jobspec.match(profile, spec)
    assert "go" not in report.covered, '"Go" matched inside "algorithms"'


# --------------------------------------------------------------------------
# Matching it
# --------------------------------------------------------------------------


@check("coverage counts what the profile evidences, and names where")
def test_coverage_and_evidence() -> None:
    report = jobspec.analyse(sample_profile(), POSTING)
    assert "pandas" in report.covered, sorted(report.covered)
    assert "python" in report.covered, sorted(report.covered)
    assert "postgresql" in {t.key for t in report.missing}, [t.key for t in report.missing]

    evidence = report.covered["pandas"]
    assert any("8,400" in hit.text for hit in evidence), evidence
    assert evidence[0].entry_label == "Data Intern - TeleTaleem", evidence[0]
    assert 0 < report.coverage < 100, report.coverage


@check("a skill listed but never described is reported as a weak claim, not a match")
def test_declared_only() -> None:
    report = jobspec.analyse(sample_profile(), POSTING)
    # SQL is in the skills group and in no bullet.
    assert "SQL" in report.declared_only, report.declared_only
    assert report.covered["sql"] == [], report.covered["sql"]
    assert "pandas" not in [t.lower() for t in report.declared_only], report.declared_only


@check("entries are ranked by how much of the posting they answer")
def test_entry_ranking() -> None:
    report = jobspec.analyse(sample_profile(), POSTING)
    by_id = {e.entry_id: e for e in report.entries}
    assert by_id["exp_1"].score > by_id["edu_1"].score, report.entries
    assert by_id["edu_1"].score == 0, by_id["edu_1"]
    assert report.entries == sorted(report.entries, key=lambda e: -e.score), "not sorted"


@check("an entry's title and stack count as evidence, not just its bullets")
def test_heading_is_evidence() -> None:
    profile = Profile.empty()
    profile.projects = [Project(id="p", name="Tracker", tech=["PyTorch"], bullets=[])]
    report = jobspec.analyse(profile, "Requirements:\n- PyTorch\n")
    assert "pytorch" in report.covered, report.covered
    assert report.covered["pytorch"][0].block_id.endswith(":heading"), report.covered["pytorch"]


@check("an empty profile scores zero rather than dividing by it")
def test_empty_profile() -> None:
    report = jobspec.analyse(Profile.empty(), POSTING)
    assert report.coverage == 0, report.coverage
    assert report.missing, "an empty profile should be missing everything"


@check("a posting with nothing in it does not crash the reader")
def test_empty_posting() -> None:
    report = jobspec.analyse(sample_profile(), "")
    assert report.coverage == 0, report.coverage
    assert report.spec.terms == [], report.spec.terms


# --------------------------------------------------------------------------
# The fabrication guard
# --------------------------------------------------------------------------


@check("a number the original did not have is caught")
def test_audit_invented_number() -> None:
    found = audit(
        "Fixed printer and network issues for staff",
        "Cut ticket resolution time by 40% across 200 staff",
        known=frozenset({"python"}),
    )
    assert set(found) == {"40", "200"}, found


@check("the same number written differently is not called invented")
def test_audit_number_formatting() -> None:
    found = audit(
        "Handled 1,200 support tickets",
        "Resolved 1200 support tickets",
        known=frozenset(),
    )
    assert found == [], found


@check("a technology the user has never mentioned anywhere is caught")
def test_audit_invented_tech() -> None:
    known = _known_vocabulary(sample_profile())
    assert audit(
        "Built a budget tracker in Python",
        "Built a budget tracker in Python and Kubernetes",
        known=known,
    ) == ["Kubernetes"]
    # Ordinary capitalisation is not an invention, or the warning is worthless.
    assert audit("built a tracker", "Built a tracker", known=known) == []


@check("a technology the user really does have is left alone")
def test_audit_known_tech() -> None:
    known = _known_vocabulary(sample_profile())
    assert audit(
        "Built a budget tracker",
        "Built a budget tracker on SQLite",
        known=known,
    ) == [], "flagged a tool the profile declares"
    # Their own employer, from a different entry.
    assert audit("Fixed network issues", "Fixed network issues at TeleTaleem", known=known) == []


@check("a product named slightly differently is not a false alarm")
def test_audit_prefix_tolerance() -> None:
    known = frozenset({"postgres", "javascript"})
    assert audit("Stored it in a database", "Stored it in PostgreSQL", known=known) == []
    # But the floor still holds: a short word is not a licence for anything.
    assert audit("Wrote it", "Wrote it in Golang", known=frozenset({"go"})) == ["Golang"]


@check("a pure re-angle flags nothing")
def test_audit_clean_rewrite() -> None:
    known = _known_vocabulary(sample_profile())
    assert (
        audit(
            "Used pandas to clean 8,400 rows of survey data",
            "Cleaned 8,400 rows of survey data with pandas, cutting manual review",
            known=known,
        )
        == []
    )


# --------------------------------------------------------------------------
# Writing the accepted ones back
# --------------------------------------------------------------------------


@check("accepted rewrites land on the right bullets and nothing else moves")
def test_apply() -> None:
    profile = sample_profile()
    updated, changed = apply_suggestions(profile, {"blt_1": "Cleaned 8,400 survey rows in pandas"})

    assert changed == 1, changed
    assert updated.experience[0].bullets[0].text == "Cleaned 8,400 survey rows in pandas"
    assert updated.experience[0].bullets[0].id == "blt_1", "the id must survive a rewrite"
    assert updated.experience[0].bullets[1].text == profile.experience[0].bullets[1].text
    assert updated.projects[0].bullets[0].text == "Built a budget tracker in Python"


@check("apply returns a copy, so the editor keeps an undo target")
def test_apply_does_not_mutate() -> None:
    profile = sample_profile()
    original = profile.experience[0].bullets[0].text
    apply_suggestions(profile, {"blt_1": "something else entirely"})
    assert profile.experience[0].bullets[0].text == original, "the input was mutated"


@check("the summary is rewritable through the same path as a bullet")
def test_apply_summary() -> None:
    profile = sample_profile()
    updated, changed = apply_suggestions(profile, {"sum_main": "Builds data tools in Python."})
    assert changed == 1, changed
    assert updated.summary.text == "Builds data tools in Python."


@check("an id that is not in the profile changes nothing")
def test_apply_unknown_id() -> None:
    updated, changed = apply_suggestions(sample_profile(), {"blt_nope": "ignored"})
    assert changed == 0, changed
    assert updated.experience[0].bullets[0].text == "Cleaned 8,400 rows of survey data with pandas"


# --------------------------------------------------------------------------
# Drafting a single line
# --------------------------------------------------------------------------


@check("a note too short to work from is refused rather than filled in")
def test_suggest_needs_a_note() -> None:
    """The failure this prevents is the whole reason the guard exists: given
    two words, a model writes the other twenty itself."""
    try:
        suggest.suggest_bullet(sample_profile(), "did stuff")
    except ValueError as exc:
        assert "a sentence" in str(exc), exc
        return
    raise AssertionError("a two-word note was accepted")


@check("a summary is refused when there is nothing to summarise")
def test_suggest_needs_a_profile() -> None:
    try:
        suggest.suggest_summary(Profile.empty())
    except ValueError as exc:
        assert "nothing to summarise" in str(exc), exc
        return
    raise AssertionError("an empty profile was summarised")


@check("a drafted line is audited against the note it came from")
def test_draft_is_audited() -> None:
    profile = sample_profile()

    honest = suggest._finish(
        "Configured new starter laptops and wrote the VPN guide",
        profile,
        "set up the new starter laptops and wrote the guide for connecting to the VPN",
        "test-model",
        is_summary=False,
    )
    assert honest.invented == [], honest.invented
    assert honest.is_safe

    # The failure mode in full: a plausible metric nobody stated.
    invented = suggest._finish(
        "Configured 40 new starter laptops, cutting setup time 60%",
        profile,
        "set up the new starter laptops and wrote the guide for connecting to the VPN",
        "test-model",
        is_summary=False,
    )
    assert set(invented.invented) == {"40", "60"}, invented.invented
    assert not invented.is_safe


@check("a drafted line is linted by the same rules as a typed one")
def test_draft_is_linted() -> None:
    draft = suggest._finish(
        "Responsible for various tasks.",
        sample_profile(),
        "responsible for various tasks",
        "test-model",
        is_summary=False,
    )
    joined = " ".join(draft.findings)
    # Named, not categorised. The linter used to answer every filler phrase
    # with the word "filler"; it now quotes the phrase and says what to do
    # with it, and that is what a drafted line should come back carrying.
    assert '"responsible for"' in joined, draft.findings
    assert "trailing full stop" in joined, draft.findings


@check("a bullet character the model added is stripped, not inserted")
def test_draft_strips_bullet_glyph() -> None:
    for raw in ("- Built a tracker", "• Built a tracker", "  Built a tracker  "):
        draft = suggest._finish(raw, sample_profile(), "built a tracker", "m", is_summary=False)
        assert draft.text == "Built a tracker", (raw, draft.text)


@check("the facts offered to a summary are the ones already in the profile")
def test_profile_facts() -> None:
    facts = suggest._profile_facts(sample_profile())
    assert "8,400" in facts, facts
    assert "Loot Ledger" in facts, facts
    assert "TeleTaleem" in facts, facts
    assert suggest._profile_facts(Profile.empty()).strip() == ""


def main() -> int:
    return run(
        __name__,
        skipped="the Gemini rewrite and suggestion calls (need a key and a network)",
    )


if __name__ == "__main__":
    raise SystemExit(main())
