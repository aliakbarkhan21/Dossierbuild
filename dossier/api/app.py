"""The FastAPI application.

Run it with:

    uvicorn dossier.api:app --reload --port 8000

It also serves the built React app from ``web/dist`` (see ``static.py``), so
running Dossierbuild is one process on one port rather than two servers that
disagree about which of them is current.
"""

from __future__ import annotations

import os

import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Before the routers import, because they read the key at import time. An API
# that reported "no AI key" while .env sat beside it would send someone hunting
# for a bug that is really a missing line here.
load_dotenv()

from . import errors, lifetime, static  # noqa: E402
from .routes import (  # noqa: E402
    applications,
    cvs,
    design,
    ingest,
    letter,
    profile,
    render,
    suggest,
    tailor,
)

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

@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Pay `import google.genai` before anyone is waiting on a suggestion.

    Seven tenths of a second of import that nothing on the startup path needs,
    and which the first person to ask for a drafted line would otherwise pay
    on top of a request that is already slow. In a thread so startup does not
    wait for it, and best-effort: no key, no network or no package, and the
    server starts exactly as it did.

    A lifespan rather than `@app.on_event("startup")`, which FastAPI has
    deprecated.
    """
    from ..ai.client import warm

    threading.Thread(target=warm, name="warm-genai", daemon=True).start()
    yield


app = FastAPI(
    title="Dossierbuild",
    version="1.1.0",
    summary="A master profile in, a print-ready resume out.",
    lifespan=lifespan,
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

app.include_router(cvs.router)
app.include_router(profile.router)
app.include_router(design.router)
app.include_router(render.router)
app.include_router(ingest.router)
app.include_router(tailor.router)
app.include_router(applications.router)
app.include_router(applications.versions)
app.include_router(letter.router)
app.include_router(letter.filed)
app.include_router(suggest.router)

lifetime.install(app)


@app.get("/api/health", tags=["meta"])
def health() -> dict[str, object]:
    """Enough to tell "up" from "up and able to do its job"."""
    from ..ai.parse import api_key_present
    from ..core.schema import SCHEMA_VERSION
    from ..core.storage import DATA_DIR, default_profile_path
    from ..render.pdf import chromium_ready

    browser_ok, browser_detail = chromium_ready()
    return {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "data_dir": str(DATA_DIR),
        # The CV in front of the user, not the legacy single file: on a
        # fresh install there never is one of those.
        "profile_exists": default_profile_path().exists(),
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
