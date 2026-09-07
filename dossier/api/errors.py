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

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ..ai.parse import MissingAPIKey
from ..core.cvs import CVError
from ..core.schema import DATE_PATTERN
from ..core.storage import ProfileError
from ..ingest.extract import ExtractError
from ..render.pdf import PDFError
from ..render.photo import PhotoError


logger = logging.getLogger("dossier.api")


def problem(status: int, message: str, *, fix: str = "") -> JSONResponse:
    """One error shape, so a client never has to guess where the text is."""
    return JSONResponse(status_code=status, content={"error": message, "fix": fix})


SECTION_NAMES = {
    "basics": "Contact",
    "summary": "Summary",
    "experience": "Experience",
    "projects": "Projects",
    "education": "Education",
    "skills": "Skills",
    "certifications": "Certifications",
    "awards": "Honors",
    "achievements": "Achievements",
}

FIELD_NAMES = {
    "start": "Start",
    "end": "End",
    "date": "Date",
    "url": "Link",
    "email": "Email",
}

# Pydantic states the rule; a person needs the shape. Keyed by the constraint
# that failed rather than by field name, so a new date field is covered the
# day it is added.
RULE_HELP = {
    DATE_PATTERN: "Use a month like 06/2025, or just the year: 2025.",
}


def describe(error: dict) -> str:
    """One validation failure as a sentence naming the place and the rule."""
    location = [part for part in error.get("loc", ()) if part != "body"]

    where: list[str] = []
    for part in location:
        if isinstance(part, int):
            # Positions are zero-based in the payload and one-based to a
            # person looking at "Qualification 2" on their screen.
            where.append(f"entry {part + 1}")
        else:
            where.append(SECTION_NAMES.get(part, FIELD_NAMES.get(part, part.replace("_", " "))))

    pattern = (error.get("ctx") or {}).get("pattern")
    reason = RULE_HELP.get(pattern) or error.get("msg", "is not valid")
    return f"{', '.join(where)}: {reason}" if where else reason


def install(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _invalid(_: Request, exc: RequestValidationError) -> JSONResponse:
        """Say which field and what shape, not which regex.

        FastAPI's default body is a nested array ending in
        "String should match pattern '^\\d{4}(-(0[1-9]|1[0-2]))?$'", which is
        precise, true, and no help at all to the person who typed a date.
        """
        problems = [describe(error) for error in exc.errors()]
        return problem(
            422,
            "; ".join(problems[:3]) + ("; and more" if len(problems) > 3 else ""),
            fix="Correct that field and try again. Nothing was saved.",
        )

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

    @app.exception_handler(CVError)
    async def _cv(_: Request, exc: CVError) -> JSONResponse:
        # ``cvs.json`` sits under every route that touches a profile, health
        # included, so a corrupt index would otherwise make the whole app
        # answer 500 with nothing to act on.
        return problem(422, str(exc), fix="Fix data/cvs.json, or move it aside to start a fresh list.")

    @app.exception_handler(PDFError)
    async def _pdf(_: Request, exc: PDFError) -> JSONResponse:
        # 503 rather than 500: every way this fails -- a missing browser, a
        # font fetch that timed out -- is fixed by acting and trying again,
        # not by the client changing its request.
        return problem(503, str(exc), fix="Try again. If it repeats, run: python -m playwright install chromium")

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        """The last handler, and the reason the ones above are worth writing.

        Without it, anything not named above -- a model that will not answer,
        an invalid key, a machine with no network -- arrives at the browser as
        Starlette's plain-text ``Internal Server Error``. The client cannot
        parse that as JSON, so it falls back to printing the status line, and
        the careful sentence raised at the point of failure is thrown away.

        The message is carried across as-is. Every ``RuntimeError`` this app
        raises is already written for the person reading it -- ``ai/client.py``
        explains that Gemini is congested and what to set to avoid it -- and a
        message written for a person is better than "something went wrong".

        The traceback still goes to the log: this changes what the user is
        told, not what the developer can find out.
        """
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        message = str(exc).strip() or f"{type(exc).__name__} while handling this request."
        return problem(
            500,
            message,
            fix="Try again. If it repeats, the server log has the full traceback.",
        )
