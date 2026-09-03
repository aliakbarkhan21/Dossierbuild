"""Turning the failures this app can actually have into HTTP answers.

The brief asks that every external call carry a user-facing message saying
what to do next. That message already exists at the point of failure --
``PDFError`` explains that Chromium is missing and names the command,
``ProfileError`` describes which field is wrong -- so the job here is to carry
it across the wire intact rather than to replace it with "500 Internal Server
Error".

Status codes are chosen for what the client should *do*: 422 when the request
was wrong, 502 when a service we depend on failed, 503 when it is busy and
retrying makes sense.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..ai.parse import MissingAPIKey
from ..core.storage import ProfileError
from ..ingest.extract import ExtractError
from ..render.pdf import PDFError
from ..render.photo import PhotoError


def problem(status: int, message: str, *, fix: str = "") -> JSONResponse:
    """One error shape, so a client never has to guess where the text is."""
    return JSONResponse(status_code=status, content={"error": message, "fix": fix})


def install(app: FastAPI) -> None:
    @app.exception_handler(ProfileError)
    async def _profile(_: Request, exc: ProfileError) -> JSONResponse:
        return problem(422, str(exc), fix="Correct the profile file, or restore a backup from data/backups.")

    @app.exception_handler(PhotoError)
    async def _photo(_: Request, exc: PhotoError) -> JSONResponse:
        return problem(400, str(exc), fix="Try a JPEG or PNG under 12MB.")

    @app.exception_handler(ExtractError)
    async def _extract(_: Request, exc: ExtractError) -> JSONResponse:
        return problem(422, str(exc), fix="Try a different file, or paste the text instead.")

    @app.exception_handler(MissingAPIKey)
    async def _key(_: Request, exc: MissingAPIKey) -> JSONResponse:
        return problem(
            401,
            str(exc),
            fix="Set GEMINI_API_KEY in .env. Get one free at aistudio.google.com/apikey.",
        )

    @app.exception_handler(PDFError)
    async def _pdf(_: Request, exc: PDFError) -> JSONResponse:
        # 503 rather than 500: every way this fails -- a missing browser, a
        # font fetch that timed out -- is fixed by acting and trying again,
        # not by the client changing its request.
        return problem(503, str(exc), fix="Try again. If it repeats, run: python -m playwright install chromium")
