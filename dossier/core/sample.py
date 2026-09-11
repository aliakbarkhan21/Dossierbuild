"""A worked example profile, for trying the app before typing anything.

**Why a curated one rather than lorem ipsum.** Every screen in this app is
only legible with real material in it: the templates need a long job title to
show how they wrap, the writing standard needs bullets that actually pass and
fail it, the posting reader needs skills to match against, and the page-fit
readout needs enough text to run to a second page. A profile of "Lorem Ipsum,
Foo Corp" makes all of that look broken.

**It is written to the standard the app teaches.** Every bullet opens on a
past-tense verb of result, names the tool and what it acted on, carries a
number only where a number would really be known, and ends without a full
stop. That is deliberate: the Health screen scores this profile in the
eighties, so a new person sees what "good" looks like on their first visit
rather than a wall of red. If a change here drops the score, the change is
wrong -- the sample is the worked example.

Two bullets are *deliberately* weak -- the ones about "various tasks" and
"assisted with" -- so the Review screen has something to catch and the feature
demonstrates itself. Removing them would make the sample look better and the
app look pointless.

Not a real person. The name, the employers and the numbers are invented, and
the profile is never written to disk unless someone loads it.
"""

from __future__ import annotations

from .schema import Profile

SAMPLE: dict = {
    "basics": {
        "name": "Priya Raman",
        "headline": "Backend engineer — data platforms and the services on top of them",
        "email": "priya.raman@example.com",
        "phone": "+44 7700 900318",
        "location": "Manchester, UK",
        "links": [
            {"label": "GitHub", "url": "github.com/priyaraman"},
            {"label": "LinkedIn", "url": "linkedin.com/in/priyaraman"},
        ],
    },
    "summary": {
        "text": (
            "Backend engineer, four years on Python data platforms. Happiest owning "
            "a thing end to end, from the Postgres schema to the dashboard the team "
            "actually reads."
        )
    },
    "experience": [
        {
            "role": "Senior Backend Engineer",
            "organisation": "Ridgeway Systems",
            "employment_type": "Full-time",
            "location": "Manchester, UK",
            "start": "2024-02",
            "end": None,
            "bullets": [
                {
                    "text": (
                        "Cut the nightly reconciliation run from 4 hours to 26 minutes by "
                        "batching Postgres writes and moving the join into the database"
                    ),
                    "tags": ["backend", "data"],
                },
                {
                    "text": (
                        "Rebuilt the ingest service in Python around a Redis queue, taking the "
                        "failure rate on malformed supplier files from 12% to under 1%"
                    ),
                    "tags": ["backend", "data"],
                },
                {
                    "text": (
                        "Wrote the Airflow alerting and the runbook for twelve scheduled jobs, "
                        "cutting out-of-hours pages from nine a month to two"
                    ),
                    "tags": ["backend"],
                },
                {
                    "text": (
                        "Mentored two graduate engineers through their first Postgres migration, "
                        "including the review that caught one with no rollback"
                    ),
                    "tags": ["leadership"],
                },
            ],
        },
        {
            "role": "Backend Engineer",
            "organisation": "Halden Analytics",
            "employment_type": "Full-time",
            "location": "Leeds, UK",
            "start": "2022-07",
            "end": "2024-01",
            "bullets": [
                {
                    "text": (
                        "Built the REST API behind the customer dashboard in FastAPI, serving 40 "
                        "endpoints and 1.2 million requests a day"
                    ),
                    "tags": ["backend"],
                },
                {
                    "text": (
                        "Migrated 380GB from MySQL to Postgres over four weekends with no "
                        "downtime, using logical replication and a read-only cutover window"
                    ),
                    "tags": ["backend", "data"],
                },
                {
                    # Deliberately weak, so the Health screen has something real
                    # to flag on a first visit.
                    "text": "Responsible for various tasks across the backend team.",
                    "tags": [],
                },
            ],
        },
        {
            "role": "Software Engineering Intern",
            "organisation": "Northgate Labs",
            "employment_type": "Internship",
            "location": "Manchester, UK",
            "start": "2021-06",
            "end": "2021-09",
            "bullets": [
                {
                    "text": (
                        "Wrote the Python CSV importer that replaced a manual spreadsheet step, "
                        "saving the operations team about six hours a week"
                    ),
                    "tags": ["backend"],
                },
                {
                    # The second deliberate weak line.
                    "text": "Assisted with testing and helped out with documentation.",
                    "tags": [],
                },
            ],
        },
    ],
    "projects": [
        {
            "name": "Ledgerline",
            "tagline": "Bank statement reconciliation, offline",
            "tech": ["Python", "SQLite", "Textual"],
            "url": "github.com/priyaraman/ledgerline",
            "start": "2023-03",
            "end": None,
            "bullets": [
                {
                    "text": (
                        "Reconciles 2,400 transactions across 6 bank export formats without "
                        "sending a statement anywhere, matching on amount and fuzzy date"
                    ),
                    "tags": ["backend", "data"],
                },
                {
                    "text": (
                        "Ships as a single binary; the SQLite schema migrates itself, so an old "
                        "install opens a new file rather than refusing it"
                    ),
                    "tags": ["backend"],
                },
            ],
        },
        {
            "name": "Signalbox",
            "tagline": "A dashboard for a hobby weather station",
            "tech": ["TypeScript", "React", "D3"],
            "url": "",
            "start": "2022-01",
            "end": "2022-08",
            "bullets": [
                {
                    "text": (
                        "Plots 18 months of readings from a Raspberry Pi with D3, downsampling in "
                        "a worker so the chart stays responsive on a phone"
                    ),
                    "tags": ["frontend"],
                }
            ],
        },
    ],
    "education": [
        {
            "institution": "University of Manchester",
            "credential": "BSc Computer Science",
            "location": "Manchester, UK",
            "start": "2018-09",
            "end": "2021-07",
            "grade": "First Class Honours",
            "coursework": [
                "Databases",
                "Distributed Systems",
                "Algorithms",
                "Compilers",
            ],
            "bullets": [],
        }
    ],
    # The levels are deliberately partial and deliberately not all fives. A
    # sample that rated every skill 5/5 would teach the opposite of what the
    # rest of this file teaches, and one that rated nothing would leave the
    # meters undiscovered. Frontend is left unrated on purpose, so the sample
    # also shows what a group with no ratings looks like -- a plain list.
    "skills": [
        {
            "label": "Languages",
            "items": ["Python", "SQL", "TypeScript", "Go"],
            "levels": {"Python": 5, "SQL": 4, "TypeScript": 3, "Go": 2},
            "tags": [],
        },
        {
            "label": "Data",
            "items": ["PostgreSQL", "Airflow", "dbt", "Redis"],
            "levels": {"PostgreSQL": 5, "Airflow": 4, "dbt": 3, "Redis": 3},
            "tags": ["backend", "data"],
        },
        {
            "label": "Infrastructure",
            "items": ["Docker", "GitHub Actions", "Terraform", "AWS"],
            "levels": {"Docker": 4, "GitHub Actions": 4, "Terraform": 2, "AWS": 3},
            "tags": ["backend"],
        },
        {"label": "Frontend", "items": ["React", "D3"], "tags": ["frontend"]},
    ],
    "certifications": [
        {
            "name": "AWS Certified Solutions Architect — Associate",
            "issuer": "Amazon Web Services",
            "issued": "2023-11",
            "url": "",
        }
    ],
    "awards": [
        {
            "title": "Dean's List",
            "awarded_by": "University of Manchester",
            "date": "2021",
            "note": "Top 5% of the cohort in the final year.",
        }
    ],
    "achievements": [
        {
            "title": "Cut platform running costs by 31%",
            "context": "Ridgeway Systems",
            "date": "2025-03",
            "note": "Rightsized the batch cluster and moved cold storage to S3 Glacier.",
        }
    ],
}


def sample_profile() -> Profile:
    """A fresh copy, validated. Never written to disk by this function."""
    return Profile.model_validate(SAMPLE)
