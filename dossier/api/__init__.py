"""HTTP over the core, and the server that hosts the interface.

This package holds no product logic. Every route validates its input, calls
into ``dossier.core`` / ``ingest`` / ``ai`` / ``render``, and turns whatever
comes back -- including the failures -- into an HTTP answer. If a rule about
resumes ever appears in here, it is in the wrong file.
"""

from .app import app

__all__ = ["app"]
