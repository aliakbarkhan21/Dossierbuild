"""Serving the built React app from the same process as the API.

Two servers is a development convenience, not a way to ship. A desktop
shortcut that had to start Node as well as Python would have twice the
failure surface and would need Node installed on the machine at all; once
``npm run build`` has run, the frontend is a folder of static files and
uvicorn can serve it alone.

Mounted last, after every router, so ``/api/...`` is always matched by the
API and never by the catch-all below.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ..core.storage import PROJECT_ROOT

WEB_DIR = Path(os.environ.get("DOSSIER_WEB_DIR") or PROJECT_ROOT / "web" / "dist")


def build_present() -> bool:
    return (WEB_DIR / "index.html").is_file()


def install(app: FastAPI) -> None:
    """Serve ``web/dist`` at the root, if it has been built.

    Absent a build this does nothing, which is what a developer running Vite
    on 5173 wants: the API stays a bare API and nothing shadows it.
    """
    if not build_present():
        return

    # Vite fingerprints everything under assets/, so those files are immutable
    # for as long as their names exist and can be cached hard. index.html is
    # the opposite -- it names the current fingerprints, and a cached copy
    # after a rebuild points at files that are gone.
    app.mount(
        "/assets",
        StaticFiles(directory=WEB_DIR / "assets"),
        name="assets",
    )

    # response_model=None because the return type is a union of two Response
    # classes, and FastAPI would otherwise try to derive a Pydantic model from
    # it and refuse at import time.
    @app.get("/{path:path}", include_in_schema=False, response_model=None)
    def spa(path: str) -> FileResponse | JSONResponse:
        """Any real file, else index.html so the router can handle the URL.

        The client routes (/profile, /resume) exist only in the browser. A
        reload on one of them arrives here as a GET for a path with no file
        behind it, and answering 404 would break the back button and every
        bookmark.
        """
        # An unmatched /api/ path is a missing endpoint, and answering it with
        # the HTML shell would turn a typo into "unexpected token '<'" inside
        # a JSON parser somewhere in the frontend.
        if path.startswith("api/"):
            return JSONResponse({"detail": "No such endpoint."}, status_code=404)

        candidate = (WEB_DIR / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(WEB_DIR.resolve()):
            return FileResponse(candidate)

        return FileResponse(
            WEB_DIR / "index.html",
            headers={"Cache-Control": "no-cache"},
        )
