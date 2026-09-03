"""The migration chain, walked from the oldest shape forward.

A schema bump without a migration is the failure this file exists to catch:
the profile still loads, because the new field has a default, and the version
number quietly stops meaning anything. These read a version-1 dict -- the
shape that was on disk before any of this -- and check it arrives whole.
"""

from __future__ import annotations

import pytest

from dossier.core.schema import SCHEMA_VERSION, Profile
from dossier.core.storage import MIGRATIONS, ProfileError, migrate


def v1() -> dict:
    """A profile as written by the first version: no photo, no achievements."""
    return {
        "schema_version": 1,
        "basics": {
            "name": "A. Student",
            "email": "a@example.com",
            "phone": "",
            "location": "",
            "links": [],
        },
        "summary": {"id": "sum_main", "text": "Ships small tools end to end."},
        "experience": [
            {
                "id": "exp_1",
                "role": "Intern",
                "organisation": "Northgate Labs",
                "start": "2025-06",
                "end": "2025-09",
                "bullets": [{"id": "blt_1", "text": "Cut ETL runtime from 42 to 9 minutes."}],
            }
        ],
        "awards": [{"id": "awd_1", "title": "Dean's List", "awarded_by": "FAST NUCES"}],
    }


def test_every_version_has_a_step_to_the_next() -> None:
    """No gaps: version N must know how to become N+1, for every N."""
    for version in range(1, SCHEMA_VERSION):
        assert version in MIGRATIONS, f"nothing upgrades schema {version}"


def test_a_version_one_profile_arrives_intact() -> None:
    profile = Profile.model_validate(migrate(v1()))

    assert profile.schema_version == SCHEMA_VERSION
    # The content survives the walk, which is the entire point.
    assert profile.basics.name == "A. Student"
    assert profile.experience[0].bullets[0].text.startswith("Cut ETL runtime")
    assert profile.awards[0].title == "Dean's List"


def test_the_fields_each_version_added_are_present() -> None:
    profile = Profile.model_validate(migrate(v1()))

    assert profile.basics.photo == ""  # v2
    assert profile.achievements == []  # v3


def test_honors_are_not_reclassified_as_achievements() -> None:
    """v3 split the two; nothing moves on its own.

    A machine cannot tell "Dean's List" from "Ranked 3rd of 400 teams"
    reliably, and a wrong guess rewrites someone's record silently.
    """
    profile = Profile.model_validate(migrate(v1()))
    assert len(profile.awards) == 1
    assert profile.achievements == []


def test_a_profile_from_the_future_is_refused_rather_than_guessed_at() -> None:
    raw = v1()
    raw["schema_version"] = SCHEMA_VERSION + 1
    with pytest.raises(ProfileError, match="newer version"):
        migrate(raw)


def test_migrating_a_current_profile_is_a_no_op() -> None:
    current = Profile.empty().model_dump()
    assert migrate(dict(current))["schema_version"] == SCHEMA_VERSION
