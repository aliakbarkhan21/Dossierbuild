"""The FastAPI application.

Run it with:

    uvicorn dossier.api:app --reload --port 8000

It also serves the built React app from ``web/dist`` (see ``static.py``), so
running Dossierbuild is one process on one port rather than two servers that
disagree about which of them is current.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Before the routers import, because they read the key at import time. An API
# that reported "no AI key" while .env sat beside it would send someone hunting
# for a bug that is really a missing line here.
load_dotenv()

from . import errors, lifetime, static  # noqa: E402
from .routes import design, ingest, profile, render, tailor  # noqa: E402

# The Vite dev server runs on a different port, which makes every call
# cross-origin. Origins are read from the environment so a deployment can
# name its own; the defaults are the two ports a developer actually uses.
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "DOSSIER_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]

app = FastAPI(
    title="Dossierbuild",
    version="0.3.0",
    summary="A master profile in, a print-ready resume out.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    # The PDF response carries its page count and text-layer verdict in
    # headers; without this the browser hides them from the frontend.
    expose_headers=["X-Pages", "X-Words", "X-Machine-Readable", "Content-Disposition"],
)

errors.install(app)

app.include_router(profile.router)
app.include_router(design.router)
app.include_router(render.router)
app.include_router(ingest.router)
app.include_router(tailor.router)

lifetime.install(app)


@app.get("/api/health", tags=["meta"])
def health() -> dict[str, object]:
    """Enough to tell "up" from "up and able to do its job"."""
    from ..ai.parse import api_key_present
    from ..core.schema import SCHEMA_VERSION
    from ..core.storage import DATA_DIR, PROFILE_PATH
    from ..render.pdf import chromium_ready

    browser_ok, browser_detail = chromium_ready()
    return {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "data_dir": str(DATA_DIR),
        "profile_exists": PROFILE_PATH.exists(),
        "pdf_available": browser_ok,
        "pdf_detail": "" if browser_ok else browser_detail,
        "ai_available": api_key_present(),
        "web_build": static.build_present(),
        "exits_when_idle": app.state.lifetime.enabled,
        "seconds_since_beat": app.state.lifetime.seconds_since_beat(),
        "leaving": app.state.lifetime.leaving_since is not None,
    }


# Last, and it has to be: the frontend's catch-all route would otherwise
# swallow every endpoint registered after it.
static.install(app)
