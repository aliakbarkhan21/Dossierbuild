"""The one place that talks to Gemini.

Extracted when tailoring became the second thing to call a model, because the
part worth getting right is not the prompt -- it is everything around it. The
key lookup, the model fallback ladder, the retry budget and the timeout are
identical whether the request is transcribing a resume or rewriting a bullet,
and a second hand-rolled copy would have drifted from this one the first time
Google retired a model.

Callers supply what actually differs: a system instruction, a response schema,
and a temperature. They get back the parsed object and the name of the model
that answered.

**Why the fallback ladder exists.** Both of these have already happened here:
Google retired a model for new keys (``gemini-2.5-flash`` returning 404
NOT_FOUND, "no longer available to new users"), and a current model was
temporarily saturated (``gemini-3.6-flash`` returning 503, "experiencing high
demand"). Neither is worth failing a user's request over when a sibling model
does the same job.

**Why one pass is not an attempt.** When the flash tier is busy, every model
returns 503 within a second or two. Giving up there reports failure after
three seconds of not really trying. Circling back with a growing pause is what
actually gets a request through a congested minute.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")

FALLBACK_MODELS = (
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    # The lite tier is last but genuinely useful: it carries far less traffic,
    # so it answers when the flash models are saturated, and both of the jobs
    # asked of it here are well within what it can do.
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
)

# Error text that means "try again" rather than "stop". 503 and 429 are
# congestion and 504 is a slow response -- all temporary, all worth another
# pass. 404 means the model is gone for this key, so only the *other* models
# are worth trying.
RETRYABLE = (
    "404", "NOT_FOUND",
    "503", "UNAVAILABLE",
    "429", "RESOURCE_EXHAUSTED",
    "504", "DEADLINE_EXCEEDED",
)

RETRY_BUDGET_SECONDS = 75

# How long one attempt may take before the next model is tried.
#
# Measured over a dozen calls on one key: a healthy bullet comes back in 3 to
# 15 seconds, and the spread is congestion on Google's side rather than the
# model -- the same model answered in 3.4s and then in 75.9s on consecutive
# requests. 45 seconds meant one unlucky attempt held the whole request for
# most of a minute before the ladder moved on. 25 clears every healthy call
# measured with room over, and turns the bad case into "try the next one".
REQUEST_TIMEOUT_MS = 25_000

API_KEY_VARS = ("GEMINI_API_KEY", "GOOGLE_API_KEY")

T = TypeVar("T", bound=BaseModel)

Progress = Callable[[str, str], None]
"""``on_attempt(model, state)``, called as each request starts and finishes, so
a caller can show which model is being tried instead of an opaque spinner."""


class MissingAPIKey(RuntimeError):
    pass


def api_key_present() -> bool:
    return any(os.environ.get(v) for v in API_KEY_VARS)


#: The client, and the key it was built for. Kept so that the connection pool
#: behind it is reused: a fresh client per request meant a fresh TLS handshake
#: to Google on every suggestion. Keyed on the key itself because one can be
#: pasted in through the Import page while the server is running, and a cached
#: client holding the old one would keep using it.
_client: tuple[str, Any] | None = None

#: The model that last answered, tried first next time.
#:
#: The ladder exists because models are retired and tiers get saturated, but
#: it was walked from scratch on every request -- so a key whose default model
#: is busy paid the whole walk every time, which measured at 61 seconds
#: against 14 for the same work once a working model was found. One
#: successful answer is enough to know where to start.
_last_good: str | None = None


def client():
    global _client
    try:
        from google import genai
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("google-genai is not installed. Run: pip install google-genai") from exc

    key = next((os.environ[v] for v in API_KEY_VARS if os.environ.get(v)), None)
    if not key:
        raise MissingAPIKey(
            "No Gemini API key found. Paste one into the Import page "
            "(get one free at aistudio.google.com/apikey), or set "
            "GEMINI_API_KEY in .env."
        )
    if _client is not None and _client[0] == key:
        return _client[1]

    from google.genai import types

    built = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS))
    _client = (key, built)
    return built


def warm() -> None:
    """Pay the import cost before anyone is waiting on it.

    ``import google.genai`` is 0.7 seconds, and without this the first person
    to ask for a suggestion pays it on top of a request that is already slow.
    Called off the startup path in a thread, and deliberately silent: a
    machine with no key or no network should start exactly as it does now.
    """
    try:
        client()
    except Exception:  # noqa: BLE001 -- warming is best-effort by definition
        pass


def candidates(model: str | None) -> list[str]:
    """The model to try, then the fallbacks, without repeats.

    An explicitly requested model still gets the fallbacks behind it: the
    caller is expressing a preference, not a requirement that the request fail
    because that one model happens to be down.
    """
    # The last model that actually answered goes first when nobody has asked
    # for a particular one. The configured default stays in the list behind
    # it, so a tier that was busy an hour ago is still tried again later.
    head = [model] if model else [_last_good, DEFAULT_MODEL]
    ordered = [*head, *FALLBACK_MODELS]
    unique: list[str] = []
    for name in ordered:
        # `_last_good` is None until something has answered, and a None in the
        # ladder would be handed to the API as a model name.
        if name and name not in unique:
            unique.append(name)
    return unique


def short(message: str) -> str:
    """The first meaningful line of an API error, for a status line."""
    first = message.strip().splitlines()[0]
    for token in ("UNAVAILABLE", "RESOURCE_EXHAUSTED", "DEADLINE_EXCEEDED", "NOT_FOUND"):
        if token in first:
            return token.replace("_", " ").lower()
    return first[:60]


def generate(
    prompt: str,
    *,
    system: str,
    schema: type[T],
    temperature: float = 0.1,
    thinking: str = "LOW",
    model: str | None = None,
    on_attempt: Progress | None = None,
    task: str = "request",
) -> tuple[T, str]:
    """Ask a model for one structured answer. Returns ``(parsed, model_name)``.

    The answer is constrained to ``schema`` by the API, so a caller never has
    to parse JSON hopefully or handle a shape the app cannot load.
    """
    from google.genai import types

    genai_client = client()
    config = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        response_schema=schema,
        temperature=temperature,
        # The default thinking budget doubles the wait: measured at 19s against
        # 8.8s on the same input, with the long version sometimes exceeding the
        # request deadline outright.
        thinking_config=types.ThinkingConfig(thinking_level=thinking),
    )

    tries = candidates(model)
    failures: dict[str, str] = {}
    last_error: Exception | None = None
    deadline = time.monotonic() + RETRY_BUDGET_SECONDS
    round_number = 0

    while True:
        round_number += 1
        for name in tries:
            if on_attempt:
                on_attempt(name, "trying")
            try:
                response = genai_client.models.generate_content(
                    model=name, contents=prompt, config=config
                )
            except Exception as exc:  # noqa: BLE001 -- inspected, then re-raised
                message = str(exc)
                if not any(token in message for token in RETRYABLE):
                    raise
                failures[name] = short(message)
                last_error = exc
                if on_attempt:
                    on_attempt(name, failures[name])
                continue

            parsed: Any = response.parsed
            if parsed is None:
                raise RuntimeError(
                    "The model returned nothing usable. This usually means the input was "
                    "too short or was blocked."
                )
            global _last_good
            _last_good = name
            return parsed, name

        # A model that is gone for this key will not come back this minute.
        tries = [n for n in tries if failures.get(n) != "not found"]
        remaining = deadline - time.monotonic()
        if not tries or remaining <= 0:
            break
        pause = min(round_number * 3, int(remaining) or 1, 10)
        if on_attempt:
            on_attempt("", f"all busy -- waiting {pause}s before another pass")
        time.sleep(pause)

    tried = "; ".join(f"{name} ({reason})" for name, reason in failures.items())
    raise RuntimeError(
        f"Gemini is not answering right now. Tried {tried} over "
        f"{RETRY_BUDGET_SECONDS} seconds on this {task}. This is congestion on "
        "Google's side, not your key or your input -- wait a minute and try "
        "again, or set GEMINI_MODEL in .env to pin a quieter model."
    ) from last_error
