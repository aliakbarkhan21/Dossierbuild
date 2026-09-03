"""The check registry shared by the self-check scripts.

The scripts predate pytest here and are worth keeping in their own right:
each check states the property it proves, and any of them runs with nothing
installed but the app's own dependencies. What was missing was a way for CI --
or a person typing ``pytest`` -- to see them as individual tests rather than
as three shell scripts that either print "0 failed" or do not.

So registration and execution are now separate. Importing a check module
registers its checks; ``run`` executes the ones a given module registered and
prints the report, while ``tests/test_checks.py`` parametrises over the same
registry so each check becomes its own pytest case with its own name.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

Fn = Callable[[], None]


@dataclass(frozen=True)
class Check:
    name: str
    fn: Fn
    module: str

    @property
    def label(self) -> str:
        return f"{self.module.replace('check_', '')}: {self.name}"


CHECKS: list[Check] = []


def check(name: str) -> Callable[[Fn], Fn]:
    """Register a check. It is *not* run at import time."""

    def decorator(fn: Fn) -> Fn:
        CHECKS.append(Check(name=name, fn=fn, module=fn.__module__))
        return fn

    return decorator


def for_module(module: str) -> list[Check]:
    return [c for c in CHECKS if c.module == module]


def run(module: str, skipped: str = "") -> int:
    """Run one module's checks, print the report, return an exit code."""
    passed: list[str] = []
    failed: list[str] = []

    for case in for_module(module):
        try:
            case.fn()
        except AssertionError as exc:
            failed.append(f"{case.name}\n      {exc}")
        except Exception as exc:  # noqa: BLE001 -- an unexpected error is a failure
            failed.append(f"{case.name}\n      unexpected {type(exc).__name__}: {exc}")
        else:
            passed.append(case.name)

    for name in passed:
        print(f"  ok    {name}")
    for name in failed:
        print(f"  FAIL  {name}")
    if skipped:
        print(f"  skip  {skipped}")
    print()
    print(f"{len(passed)} passed, {len(failed)} failed")
    return 1 if failed else 0
