"""Turning a model's answer into something the schema will actually accept.

No network: these test the conversion, which is the part that had the bug.
``to_profile`` is pure, and was untested despite being the seam every AI
import passes through.
"""

from __future__ import annotations

from typing import get_args

import pytest

from dossier.ai.parse import _employment
from dossier.core.schema import EmploymentType, Experience

ALLOWED = get_args(EmploymentType)


@pytest.mark.parametrize(
    "written",
    [
        "Full-time", "Full-Time", "full-time", "FULL-TIME",
        "Full time", "full  time", "Full_Time", "  Full-Time  ",
    ],
)
def test_every_way_a_resume_writes_full_time(written: str) -> None:
    """The bug that started this: ``.title()`` produced "Full-Time".

    Python capitalises after every non-letter, so "full-time" became
    "Full-Time" while the schema spells it "Full-time" -- and the import died
    on a raw Pydantic error. Only the two hyphenated values were affected,
    which is exactly why nobody noticed: they are also the two commonest.
    """
    assert _employment(written) == "Full-time"


@pytest.mark.parametrize("written", ["Part-time", "Part Time", "PART-TIME", "part_time"])
def test_the_other_hyphenated_one(written: str) -> None:
    assert _employment(written) == "Part-time"


@pytest.mark.parametrize("value", ALLOWED)
def test_every_value_the_schema_allows_survives_a_round_trip(value: str) -> None:
    """Guards the whole class, not the one instance that was reported."""
    assert _employment(value) == value
    assert _employment(value.lower()) == value
    assert _employment(value.upper()) == value


def test_anything_unrecognised_becomes_other_rather_than_failing() -> None:
    for written in ("chief wizard", "", "   ", "n/a"):
        assert _employment(written) == "Other"


@pytest.mark.parametrize("written", ["Full-Time", "Part Time", "internship", "nonsense"])
def test_the_result_always_validates(written: str) -> None:
    """The real contract: whatever comes out, the schema takes it."""
    entry = Experience(
        role="Engineer", organisation="Org", employment_type=_employment(written)
    )
    assert entry.employment_type in ALLOWED
