"""Filler, told apart and told about.

The reported bug, verbatim: *"what are these 'Problems' again, same thing for
all of them"*. Two screenshots, two different sentences, one red mark on each,
and underneath both the same sentence with the offending phrase substituted
in -- ``"contributed to" is filler`` and ``"successfully" is filler``.

Three things were wrong with that, and this file pins all three.

1. **It was the same thing for all of them.** The message never looked at the
   sentence, so it could not be about the sentence.
2. **It was one fault when it is five.** A hedge is the wrong verb; an adverb
   is one word too many; a vague quantity is a missing number; a cliche is an
   unfalsifiable claim; an inflated word is a plain word in a costume. They
   have five different repairs.
3. **It was a Problem.** The top tier held a missing email address, a job that
   ends before it starts, and the word "successfully" on an otherwise good
   line. A tier that holds all three is a tier that means nothing.
"""

from __future__ import annotations

from dossier.core.quality import HABIT, check_document, check_text
from dossier.core.schema import Basics, Experience, Profile, TextBlock


def messages(findings) -> str:
    return " | ".join(f.message for f in findings)


def only(findings, needle: str):
    """The one finding that talks about ``needle``."""
    hits = [f for f in findings if needle in f.message]
    assert len(hits) == 1, messages(findings)
    return hits[0]


# --------------------------------------------------------------------------
# It reads the sentence
# --------------------------------------------------------------------------


def test_a_hedge_quotes_back_the_work_you_were_standing_next_to() -> None:
    """The first screenshot. The advice names what this line was near."""
    line = "Contributed to HPE's global strategy for cloud and telecommunications"
    said = only(check_text(line, "b"), "contributed to").message
    assert "HPE's global strategy" in said, said


def test_two_different_lines_do_not_get_the_same_sentence() -> None:
    """The complaint itself, as an assertion."""
    first = only(check_text("Contributed to the Cabinet Division's data platform", "b"), "contributed to")
    second = only(check_text("Contributed to a Kubernetes migration for 40 services", "b"), "contributed to")
    assert first.message != second.message


def test_the_five_kinds_do_not_share_a_repair() -> None:
    said = {
        "hedge": only(check_text("Involved in the Postgres migration", "b"), "involved in").message,
        "adverb": only(check_text("Cut latency 40% and did it seamlessly", "b"), "seamlessly").message,
        "vague": only(check_text("Advised numerous Fortune 500 boards", "b"), "numerous").message,
        "cliche": only(check_text("A team player on the Azure rollout", "b"), "team player").message,
        "inflated": only(check_text("Utilised Docker to halve deploy time", "b"), "utilised").message,
    }
    assert len(set(said.values())) == 5, said
    # Each says the thing that is specific to its own kind of nothing.
    assert "which part" in said["hedge"] or "not what you did" in said["hedge"]
    assert "delete the word" in said["adverb"]
    assert "how many" in said["vague"]
    assert "no opposite" in said["cliche"]
    assert '"used"' in said["inflated"]


def test_an_inflated_word_is_told_which_plain_word_it_means() -> None:
    """Advice, versus an edit. "Use the plain word" is the former."""
    assert '"led"' in only(check_text("Spearheaded the Kafka rollout", "b"), "spearheaded").message


# --------------------------------------------------------------------------
# It weighs the sentence
# --------------------------------------------------------------------------


def test_nothing_in_the_writing_pass_is_a_problem_any_more() -> None:
    """A Problem is a fault in the document, not an opinion about a word."""
    lines = [
        "Responsible for various tasks across the backend team",
        "Successfully delivered a 40% cut in Postgres query latency",
        "A passionate, results-driven team player",
        "Utilised Docker in order to speed up the build",
    ]
    for line in lines:
        assert not [f for f in check_text(line, "b") if f.severity == "error"], line


def test_a_word_a_pdf_split_in_half_is_still_a_problem() -> None:
    """Because that one is not an opinion: it prints exactly as stored."""
    found = check_text("Drove large- scale change at 4 regulators", "b")
    assert only(found, "large-scale").severity == "error"


def test_one_deletable_word_on_a_working_line_is_a_note() -> None:
    """The second screenshot, correctly weighed.

    The line carries a number and names a thing. "successfully" is one word to
    delete, and a red mark beside it was telling the writer their good line was
    as broken as a resume with no email address on it.
    """
    line = "Successfully cut nightly ETL runtime from 42 to 9 minutes in Postgres"
    assert only(check_text(line, "b"), "successfully").severity == "note"


def test_a_hedge_that_is_the_verb_of_the_line_is_a_warning() -> None:
    """Here the phrase *is* the claim, so deleting it leaves no sentence."""
    line = "Contributed to the Kubernetes migration across 40 services"
    assert only(check_text(line, "b"), "contributed to").severity == "warning"


def test_the_same_phrase_is_weighed_differently_by_where_it_sits() -> None:
    leading = only(check_text("Worked on the Kafka pipeline for 9 teams", "b"), "worked on")
    inside = only(check_text("Rebuilt the Kafka pipeline, worked on by 9 teams", "b"), "worked on")
    assert (leading.severity, inside.severity) == ("warning", "note")


def test_a_line_carrying_nothing_else_is_a_warning_whatever_the_kind() -> None:
    """No number, no named thing: the filler is the entire sentence."""
    for line in ("A hard worker with various skills", "Utilised many tools"):
        assert any(f.severity == "warning" for f in check_text(line, "b")), line


# --------------------------------------------------------------------------
# It reads the document, not just the line
# --------------------------------------------------------------------------


def test_a_phrase_you_reach_for_everywhere_is_reported_once_at_the_top() -> None:
    """An observation a line-by-line reader structurally cannot make."""
    profile = Profile.empty()
    profile.basics = Basics(name="A. Khan", email="a@example.com", phone="123")
    profile.summary.text = "Executive with two decades in national digital government."
    profile.experience.append(
        Experience(
            id="e1",
            role="Consultant",
            organisation="HPE",
            bullets=[
                TextBlock(id=f"b{n}", text=f"Contributed to the {name} programme for 12 agencies")
                for n, name in enumerate(("Azure", "Kafka", "Postgres", "Docker"), start=1)
            ],
        )
    )
    said = messages(check_document(profile))
    assert "in 4 of your lines" in said, said
    assert "habit rather than a slip" in said, said


def test_one_or_two_uses_are_not_a_habit() -> None:
    profile = Profile.empty()
    profile.basics = Basics(name="A. Khan", email="a@example.com", phone="123")
    profile.summary.text = "Executive with two decades in national digital government."
    profile.experience.append(
        Experience(
            id="e1",
            role="Consultant",
            organisation="HPE",
            bullets=[
                TextBlock(id=f"b{n}", text="Contributed to the Azure programme for 12 agencies")
                for n in range(HABIT - 1)
            ],
        )
    )
    assert "habit rather than a slip" not in messages(check_document(profile))


def _with_bullets(*texts: str) -> Profile:
    profile = Profile.empty()
    profile.basics = Basics(name="A. Khan", email="a@example.com", phone="123")
    profile.summary.text = "Executive with two decades in national digital government."
    profile.experience.append(
        Experience(
            id="e1",
            role="Consultant",
            organisation="HPE",
            bullets=[TextBlock(id=f"b{n}", text=t) for n, t in enumerate(texts, start=1)],
        )
    )
    return profile


def test_the_same_weak_verb_opening_five_bullets_is_said_once() -> None:
    """From the real CV: "supported" led five bullets and "managed" four.

    Five identical warnings down the page *is* the complaint. Counted, it
    becomes a fact about the document -- these jobs all read as one -- which
    is a thing no single line could have told you.
    """
    said = messages(
        check_document(
            _with_bullets(
                "Supported the Azure rollout for 12 agencies",
                "Supported the Kafka migration across 40 services",
                "Supported the Postgres upgrade at 3 regulators",
                "Built the ingest service in Python",
            )
        )
    )
    assert 'open with "supported"' in said, said
    assert "3 bullets" in said, said


def test_even_a_strong_verb_is_flagged_when_it_is_the_only_one() -> None:
    said = messages(
        check_document(
            _with_bullets(
                "Built the Azure ingest service for 12 agencies",
                "Built the Kafka bridge across 40 services",
                "Built the Postgres replica at 3 regulators",
                "Built the Docker pipeline in 2 weeks",
            )
        )
    )
    assert 'open with "built"' in said, said
    assert "flattens the page" in said, said


def test_variety_is_left_alone() -> None:
    said = messages(
        check_document(
            _with_bullets(
                "Built the Azure ingest service for 12 agencies",
                "Cut Kafka lag from 40 seconds to 2",
                "Rewrote the Postgres replica at 3 regulators",
                "Shipped the Docker pipeline in 2 weeks",
            )
        )
    )
    assert "open with" not in said, said


def test_a_weak_verb_is_reported_even_when_a_good_one_recurs_more() -> None:
    """From the real CV: "Led" opened ten bullets, "Supported" five.

    Ranking by frequency spent the card on the good verb and never mentioned
    the weak one. What earns a line here is not what recurs most; it is what
    recurs and is also wrong.
    """
    said = messages(
        check_document(
            _with_bullets(
                *[f"Led the Azure programme in region {n}" for n in range(6)],
                *[f"Supported the Kafka migration for team {n}" for n in range(3)],
            )
        )
    )
    assert 'open with "supported"' in said, said
    assert 'open with "led"' in said, said
