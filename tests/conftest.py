"""Test setup: importable project, and a data directory that is never yours.

The API tests write profiles, portraits and designs. Pointing ``DATA_DIR`` at
a throwaway directory *before* anything imports ``dossier.core.storage`` is
what makes ``pytest`` safe to run on a machine with a real profile on it. It
is set rather than defaulted: an environment variable left over in a shell is
exactly the case this is guarding against.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

for path in (ROOT, ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

_SANDBOX = tempfile.mkdtemp(prefix="dossier-tests-")
os.environ["DOSSIER_DATA_DIR"] = _SANDBOX

# The same guard for the key file. ``remember_api_key`` writes a real .env,
# and the Settings routes call it -- so without this a test run would
# overwrite the key belonging to the copy of the app the developer actually
# uses. Set here, before any import reads it, for the same reason as above.
os.environ["DOSSIER_ENV_FILE"] = str(Path(_SANDBOX) / ".env")
