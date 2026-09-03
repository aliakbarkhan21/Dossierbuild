"""Stable short identifiers.

Every entry and every block of prose in the profile carries an id that is
minted once and never regenerated. Later phases depend on this:

  * AI tailoring returns rewritten bullets keyed by id, so a rewrite can be
    matched back to its original even though the text has changed. Matching on
    text would fail precisely because rewriting is what changed the text.
  * The editor keys each row by id, so reordering an entry carries its state
    with it instead of leaving values behind on the row that took its place.

Six hex characters is 16.7 million possibilities -- ample for a document with a
few dozen entries, and short enough to read comfortably in the JSON file.
"""

from __future__ import annotations

import secrets

ID_LENGTH_BYTES = 3


def new_id(prefix: str) -> str:
    """Return a fresh id such as ``exp_2b8c04``."""
    return f"{prefix}_{secrets.token_hex(ID_LENGTH_BYTES)}"
