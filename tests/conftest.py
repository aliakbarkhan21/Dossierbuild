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

os.environ["DOSSIER_DATA_DIR"] = tempfile.mkdtemp(prefix="dossier-tests-")
