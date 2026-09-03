"""Every self-check, as its own pytest case.

The checks live in ``scripts/check_*.py`` because they are also meant to be
run by a person with nothing installed but the app's own dependencies. This
file does not duplicate them: importing those modules registers their checks,
and each one becomes a test with its own name, so a CI run says *which*
property broke rather than which script exited non-zero.

Covers exactly what the brief asks tests to cover -- PDF generation, import
parsing, schema migration and template rendering -- plus the tailoring
analysis and its fabrication guard, which are deterministic for the same
reason and so belong here rather than behind an API key.
"""

from __future__ import annotations

import pytest

# Imported for their side effect: each module registers its checks on import.
import check_import  # noqa: F401
import check_phase1  # noqa: F401
import check_phase2  # noqa: F401
import check_db  # noqa: F401
import check_tailor  # noqa: F401
from _harness import CHECKS


@pytest.mark.parametrize("case", CHECKS, ids=lambda c: c.label)
def test_check(case) -> None:
    case.fn()


def test_the_registry_is_not_empty() -> None:
    """A guard against the imports above being tidied away as unused."""
    assert len(CHECKS) > 40, f"only {len(CHECKS)} checks registered"
