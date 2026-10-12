"""The one place that talks to Claude.

The second provider, behind the same ``generate`` contract as ``client.py``:
a prompt, a system instruction and a Pydantic schema in, the parsed object and
the model's name out. Nothing a caller does with the answer changes -- the
fabrication audit in ``tailor``, ``suggest`` and ``letter`` runs on whatever
comes back, from either provider, exactly as before.

**Why there is no fallback ladder here.** Gemini's ladder exists because
Google retires models for new keys and saturates the flash tier; both have
happened. Anthropic's SDK already retries rate limits, overloads and dropped
connections with backoff, so a second ladder on top would only multiply the
wait. One model, chosen by ``CLAUDE_MODEL``, and a clear sentence when it
fails.

**Why ``temperature`` is accepted and not sent.** The current Claude models
reject sampling parameters outright, so passing one through would turn every
request into a 400. Depth is controlled by effort instead, mapped from the
``thinking`` level the callers already choose.
"""

from __future__ import annotations

import os
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from .client import MissingAPIKey, Progress

#: The model used when ``CLAUDE_MODEL`` is not set. Named once, here.
DEFAULT_MODEL = "claude-opus-5-5"

MODEL_VAR = "CLAUDE_MODEL"

API_KEY_VARS = ("ANTHROPIC_API_KEY",)

#: Room for the longest thing asked of it -- a whole resume transcribed into
#: the import schema -- while staying a plain, non-streaming request.
MAX_TOKENS = 16_000

#: Longer than Gemini's 25 seconds: there is no ladder to move on to, so one
#: attempt has to be allowed to finish. The SDK retries on top of this.
REQUEST_TIMEOUT_SECONDS = 120

#: The callers' thinking levels, as Claude effort levels.
EFFORT = {"LOW": "low", "MEDIUM": "medium", "HIGH": "high"}

T = TypeVar("T", bound=BaseModel)

#: Built once per key, for the same reason as Gemini's: the connection pool
#: behind it is worth reusing, and a key changed in Settings must not keep
#: using the old one.
_client: tuple[str, Any] | None = None


def key() -> str:
    return next((os.environ[v] for v in API_KEY_VARS if os.environ.get(v)), "")


def key_present() -> bool:
    return bool(key())


def model_name() -> str:
    return os.environ.get(MODEL_VAR, "").strip() or DEFAULT_MODEL


def client():
    global _client
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("The anthropic package is not installed. Run: pip install anthropic") from exc

    current = key()
    if not current:
        raise MissingAPIKey(
            "No Claude API key found. Add one on the Settings screen "
            "(create one at platform.claude.com), or set ANTHROPIC_API_KEY in .env."
        )
    if _client is not None and _client[0] == current:
        return _client[1]
    # The key is passed explicitly so the SDK never falls back to some other
    # credential on this machine that the person did not choose for this app.
    built = anthropic.Anthropic(api_key=current, timeout=REQUEST_TIMEOUT_SECONDS, max_retries=2)
    _client = (current, built)
    return built


def forget() -> None:
    global _client
    _client = None


def verify_key(candidate: str) -> str | None:
    """Return None if the key works, otherwise a message saying why not.

    Listing one model is enough to prove the key is real and costs no tokens.
    """
    try:
        import anthropic
    except ImportError:  # pragma: no cover
        return "The anthropic package is not installed. Run: pip install anthropic"
    try:
        anthropic.Anthropic(api_key=candidate.strip(), timeout=20, max_retries=0).models.list(limit=1)
    except anthropic.AuthenticationError:
        return "That key was refused: Anthropic does not recognise it."
    except anthropic.PermissionDeniedError:
        return "That key was refused: it does not have permission to use the API."
    except anthropic.APIConnectionError:
        return "Could not reach Anthropic to check the key. Check your connection and try again."
    except anthropic.APIStatusError as exc:
        return f"That key could not be checked: {str(exc.message)[:200]}"
    return None


def generate(
    prompt: str,
    *,
    system: str,
    schema: type[T],
    temperature: float = 0.1,  # noqa: ARG001 -- see the module docstring
    thinking: str = "LOW",
    model: str | None = None,
    on_attempt: Progress | None = None,
    task: str = "request",
) -> tuple[T, str]:
    """Ask Claude for one structured answer. Returns ``(parsed, model_name)``.

    The answer is constrained to ``schema`` by the API and validated against it
    again by the SDK. Anything that does not parse is refused here, so a caller
    never receives a shape it cannot load.
    """
    import anthropic

    claude = client()
    # A model named on the request is a Gemini name unless it says otherwise:
    # the screens that pass one were written when there was only Gemini.
    name = model if model and model.startswith("claude-") else model_name()
    if on_attempt:
        on_attempt(name, "trying")

    def failed(reason: str) -> None:
        if on_attempt:
            on_attempt(name, reason)

    try:
        response = claude.messages.parse(
            model=name,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_format=schema,
            output_config={"effort": EFFORT.get(thinking.upper(), "low")},
        )
    except anthropic.AuthenticationError as exc:
        failed("key rejected")
        raise MissingAPIKey(
            "Claude rejected that API key. Check it on the Settings screen -- "
            "pasting it there tests it before saving."
        ) from exc
    except anthropic.PermissionDeniedError as exc:
        failed("no permission")
        raise MissingAPIKey(
            f"That Claude key is not allowed to use {name}. Check the key's "
            "workspace on platform.claude.com, or set CLAUDE_MODEL in .env."
        ) from exc
    except anthropic.NotFoundError as exc:
        failed("unknown model")
        raise RuntimeError(
            f"Claude does not know a model called {name!r}. Fix CLAUDE_MODEL in "
            f".env, or remove it to use {DEFAULT_MODEL}."
        ) from exc
    except anthropic.RateLimitError as exc:
        failed("rate limited")
        raise RuntimeError(
            f"Claude is rate-limiting this key, so the {task} did not run. Wait a "
            "minute and try again."
        ) from exc
    except anthropic.APITimeoutError as exc:
        failed("timed out")
        raise RuntimeError(
            f"Claude took longer than {REQUEST_TIMEOUT_SECONDS} seconds on this "
            f"{task}. Try again in a moment."
        ) from exc
    except anthropic.APIConnectionError as exc:
        failed("no connection")
        raise RuntimeError(
            f"Could not reach Claude for this {task}. Check your internet "
            "connection and try again."
        ) from exc
    except anthropic.APIStatusError as exc:
        failed(f"error {exc.status_code}")
        if exc.status_code >= 500:
            raise RuntimeError(
                f"Anthropic's servers are struggling right now, so the {task} did "
                "not run. This is on their side, not your key or your input -- "
                "try again in a minute."
            ) from exc
        raise RuntimeError(f"Claude refused this {task}: {str(exc.message)[:200]}") from exc
    except (ValidationError, ValueError) as exc:
        # The SDK validates the JSON against the schema; an answer that does
        # not fit is not something to load and hope about.
        failed("unusable answer")
        raise RuntimeError(
            f"Claude's answer to this {task} did not match the expected shape, so "
            "none of it was used. Try again."
        ) from exc

    if response.stop_reason == "refusal":
        failed("declined")
        raise RuntimeError(
            f"Claude declined this {task}. Nothing was changed. If the text is "
            "ordinary resume material, try again or switch to Gemini in Settings."
        )
    if response.stop_reason == "max_tokens":
        failed("cut off")
        raise RuntimeError(
            f"Claude's answer to this {task} was cut off before it finished, so "
            "none of it was used. Try a shorter input."
        )
    parsed = response.parsed_output
    if parsed is None:
        failed("nothing usable")
        raise RuntimeError(
            "The model returned nothing usable. This usually means the input was "
            "too short or was blocked."
        )
    return parsed, name
