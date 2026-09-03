"""Small persisted UI preferences.

Kept deliberately separate from ``storage.py``. That module guards your resume
data -- the thing that exists nowhere else and must never be lost. This one
holds which theme you like, and a corrupt or missing file here should cost
nothing but a fallback to defaults. Different stakes, different handling: no
backups, no validation errors surfaced, no exceptions escaping.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .storage import DATA_DIR

SETTINGS_PATH = DATA_DIR / "ui_settings.json"

# All values are strings, including the on/off ones. The loader below accepts
# only strings, which keeps a hand-edited or half-written file from producing
# a surprising type deeper in the app -- worth more here than the small
# awkwardness of "on"/"off" instead of a bool.
DEFAULTS: dict[str, Any] = {
    "theme": "sage",
    "mode": "light",
    "density": "comfortable",
    "autosave": "off",
}


def load_settings() -> dict[str, Any]:
    """Read preferences, falling back to defaults on any problem at all."""
    settings = dict(DEFAULTS)
    try:
        raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 -- missing, corrupt, unreadable: same answer
        return settings
    if isinstance(raw, dict):
        for key in DEFAULTS:
            if isinstance(raw.get(key), str):
                settings[key] = raw[key]
    return settings


def save_settings(settings: dict[str, Any]) -> None:
    """Write preferences. Failure here is never worth interrupting the user."""
    try:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({k: settings.get(k, v) for k, v in DEFAULTS.items()}, indent=2)
        tmp = SETTINGS_PATH.with_suffix(".json.tmp")
        tmp.write_text(payload + "\n", encoding="utf-8")
        os.replace(tmp, SETTINGS_PATH)
    except Exception:  # noqa: BLE001
        pass
