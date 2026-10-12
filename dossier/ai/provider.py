"""Which model provider answers, behind one small interface.

Every AI feature in the app calls ``client.generate`` and nothing else, and
everything it does with the answer -- the fabrication audit above all -- runs
on the parsed object that comes back. So adding a provider is a matter of
supplying that one call, plus the key handling Settings needs; no caller has
to know which company answered.

Gemini stays the default. A copy of the app that has never heard of this
setting behaves exactly as it did.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from . import claude
from . import client as gemini

#: Where the choice lives, in the process environment and in ``.env``, beside
#: the keys themselves.
PROVIDER_VAR = "DOSSIER_AI_PROVIDER"

DEFAULT = "gemini"


@dataclass(frozen=True)
class Provider:
    """What the app needs from a provider: answer, and manage a key."""

    name: str
    label: str
    key_vars: tuple[str, ...]
    key_present: Callable[[], bool]
    verify_key: Callable[[str], str | None]
    generate: Callable[..., tuple[Any, str]]
    forget: Callable[[], None]


def _verify_gemini(key: str) -> str | None:
    # Imported here: parse imports client, which imports this lazily, and a
    # module-level import would close that loop.
    from .parse import verify_api_key

    return verify_api_key(key)


PROVIDERS: dict[str, Provider] = {
    "gemini": Provider(
        name="gemini",
        label="Gemini",
        key_vars=gemini.API_KEY_VARS,
        key_present=gemini.gemini_key_present,
        verify_key=_verify_gemini,
        generate=gemini.generate_gemini,
        forget=gemini.forget,
    ),
    "claude": Provider(
        name="claude",
        label="Claude",
        key_vars=claude.API_KEY_VARS,
        key_present=claude.key_present,
        verify_key=claude.verify_key,
        generate=claude.generate,
        forget=claude.forget,
    ),
}


def active_name() -> str:
    """The chosen provider, or the default when the setting is missing or unknown."""
    name = os.environ.get(PROVIDER_VAR, "").strip().lower()
    return name if name in PROVIDERS else DEFAULT


def active() -> Provider:
    return PROVIDERS[active_name()]
