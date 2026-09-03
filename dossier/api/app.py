"""The FastAPI application.

Run it with:

    uvicorn dossier.api:app --reload --port 8000

It serves the same ``data/`` directory the Streamlit app reads, on purpose:
during the migration both interfaces drive one engine and one set of files,
so nothing has to be kept in sync and there is no moment where the app has two
truths.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# The Streamlit entry point does this too. Both are entry points, and an API
# that reported "no AI key" while the app beside it had one would send someone
# hunting for a bug that is really a missing line here.
load_dotenv()

from . import errors, static  # noqa: E402
from .routes import design, ingest, profile, render  # noqa: E402

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
    title="Dossier",
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
    }


# Last, and it has to be: the frontend's catch-all route would otherwise
# swallow every endpoint registered after it.
static.install(app)
