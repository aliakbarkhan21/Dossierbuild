"""The Claude provider, against a fake client.

No network and no key. What these check is everything around the call: that
the request asks for structured output and never sends a sampling parameter
the current models reject, that each way it can fail becomes a sentence a
person can act on, that the provider setting really routes requests, and --
the one that matters most -- that a Claude rewrite goes through the same
fabrication audit as a Gemini one.
"""

from __future__ import annotations

import os
from dataclasses import replace
from types import SimpleNamespace

import anthropic
import httpx2
import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError

from dossier.ai import claude
from dossier.ai import client as ai_client
from dossier.ai import provider
from dossier.ai.client import MissingAPIKey
from dossier.api import app
from dossier.api.routes import settings as route
from dossier.core.schema import Profile

api = TestClient(app)

KEY = "sk-ant-api03-a-key-that-looks-plausible-0001"
REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


class Answer(BaseModel):
    text: str


class FakeClaude:
    """Records what was asked, and answers -- or fails -- as told."""

    def __init__(self, *, parsed=None, stop_reason="end_turn", error: Exception | None = None):
        self.calls: list[dict] = []
        self._parsed = parsed
        self._stop = stop_reason
        self._error = error
        self.messages = SimpleNamespace(parse=self._parse)

    def _parse(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return SimpleNamespace(parsed_output=self._parsed, stop_reason=self._stop)


def status_error(cls, code: int):
    return cls("no", response=httpx2.Response(code, request=REQUEST), body=None)


@pytest.fixture(autouse=True)
def clean_env():
    """No key and no provider choice going in, and none left behind."""
    names = (*claude.API_KEY_VARS, *ai_client.API_KEY_VARS, claude.MODEL_VAR, provider.PROVIDER_VAR)
    saved = {name: os.environ.get(name) for name in names}
    for name in names:
        os.environ.pop(name, None)
    if route.ENV_PATH.exists():
        route.ENV_PATH.unlink()
    claude.forget()
    yield
    for name, value in saved.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
    claude.forget()


def use(monkeypatch, fake: FakeClaude) -> FakeClaude:
    monkeypatch.setattr(claude, "client", lambda: fake)
    return fake


# -- the request -------------------------------------------------------------


def test_it_asks_for_the_schema_and_returns_the_parsed_answer(monkeypatch) -> None:
    fake = use(monkeypatch, FakeClaude(parsed=Answer(text="Led the migration.")))
    parsed, model = claude.generate("prompt", system="be careful", schema=Answer, thinking="MEDIUM")
    assert parsed.text == "Led the migration."
    assert model == claude.DEFAULT_MODEL
    call = fake.calls[0]
    assert call["output_format"] is Answer
    assert call["system"] == "be careful"
    assert call["output_config"] == {"effort": "medium"}
    assert call["messages"] == [{"role": "user", "content": "prompt"}]


def test_no_sampling_parameter_is_sent(monkeypatch) -> None:
    """The current models answer a temperature with a 400."""
    fake = use(monkeypatch, FakeClaude(parsed=Answer(text="x")))
    claude.generate("p", system="s", schema=Answer, temperature=0.4)
    assert "temperature" not in fake.calls[0]


def test_the_model_comes_from_the_setting(monkeypatch) -> None:
    fake = use(monkeypatch, FakeClaude(parsed=Answer(text="x")))
    os.environ[claude.MODEL_VAR] = "claude-sonnet-5-5"
    _, model = claude.generate("p", system="s", schema=Answer)
    assert model == fake.calls[0]["model"] == "claude-sonnet-5-5"


def test_a_gemini_model_name_on_the_request_is_ignored(monkeypatch) -> None:
    """Screens written for Gemini can still pass one of its model names."""
    fake = use(monkeypatch, FakeClaude(parsed=Answer(text="x")))
    claude.generate("p", system="s", schema=Answer, model="gemini-3.8-flash")
    assert fake.calls[0]["model"] == claude.DEFAULT_MODEL


# -- failures ------------------------------------------------------------------


def test_no_key_is_said_plainly_and_nothing_is_sent() -> None:
    with pytest.raises(MissingAPIKey, match="No Claude API key"):
        claude.generate("p", system="s", schema=Answer)


@pytest.mark.parametrize(
    ("error", "kind", "words"),
    [
        (status_error(anthropic.AuthenticationError, 401), MissingAPIKey, "rejected that API key"),
        (status_error(anthropic.PermissionDeniedError, 403), MissingAPIKey, "not allowed"),
        (status_error(anthropic.NotFoundError, 404), RuntimeError, "CLAUDE_MODEL"),
        (status_error(anthropic.RateLimitError, 429), RuntimeError, "rate-limiting"),
        (status_error(anthropic.InternalServerError, 500), RuntimeError, "their side"),
        (anthropic.APITimeoutError(request=REQUEST), RuntimeError, "took longer"),
        (anthropic.APIConnectionError(request=REQUEST), RuntimeError, "Could not reach Claude"),
    ],
)
def test_each_failure_becomes_a_sentence(monkeypatch, error, kind, words) -> None:
    seen: list[tuple[str, str]] = []
    use(monkeypatch, FakeClaude(error=error))
    with pytest.raises(kind, match=words):
        claude.generate("p", system="s", schema=Answer, on_attempt=lambda m, s: seen.append((m, s)))
    # The progress line saw it fail too, not just "trying" forever.
    assert len(seen) == 2 and seen[1][1] != "trying"


def test_an_answer_that_does_not_parse_is_rejected(monkeypatch) -> None:
    try:
        Answer.model_validate({"wrong": 1})
    except ValidationError as exc:
        broken = exc
    use(monkeypatch, FakeClaude(error=broken))
    with pytest.raises(RuntimeError, match="did not match the expected shape"):
        claude.generate("p", system="s", schema=Answer)


def test_an_empty_answer_is_rejected(monkeypatch) -> None:
    use(monkeypatch, FakeClaude(parsed=None))
    with pytest.raises(RuntimeError, match="nothing usable"):
        claude.generate("p", system="s", schema=Answer)


@pytest.mark.parametrize(("stop", "words"), [("refusal", "declined"), ("max_tokens", "cut off")])
def test_a_refused_or_truncated_answer_is_not_used(monkeypatch, stop, words) -> None:
    use(monkeypatch, FakeClaude(parsed=Answer(text="half a"), stop_reason=stop))
    with pytest.raises(RuntimeError, match=words):
        claude.generate("p", system="s", schema=Answer)


# -- routing and the audit -------------------------------------------------------


def test_gemini_answers_unless_claude_is_chosen(monkeypatch) -> None:
    asked: list[str] = []

    def gemini(*_args, **_kwargs):
        asked.append("gemini")
        return Answer(text="g"), "gemini-3.8-flash"

    monkeypatch.setitem(provider.PROVIDERS, "gemini", replace(provider.PROVIDERS["gemini"], generate=gemini))
    fake = use(monkeypatch, FakeClaude(parsed=Answer(text="x")))
    ai_client.generate("p", system="s", schema=Answer)
    assert asked == ["gemini"] and not fake.calls

    os.environ[provider.PROVIDER_VAR] = "claude"
    ai_client.generate("p", system="s", schema=Answer)
    assert asked == ["gemini"] and len(fake.calls) == 1


def test_an_unknown_provider_falls_back_to_gemini() -> None:
    os.environ[provider.PROVIDER_VAR] = "someone-else"
    assert provider.active_name() == "gemini"


def test_a_claude_rewrite_goes_through_the_same_audit(monkeypatch) -> None:
    """A tool and a number the profile never mentioned are flagged, as with Gemini."""
    from dossier.ai.suggest import suggest_bullet

    profile = Profile.model_validate(api.get("/api/profile/sample").json())
    assert "kubernetes" not in profile.model_dump_json().lower()
    os.environ[provider.PROVIDER_VAR] = "claude"
    use(
        monkeypatch,
        FakeClaude(parsed=claude_answer("Migrated the reporting database to Postgres on Kubernetes, cutting costs by 40%")),
    )
    draft = suggest_bullet(profile, "I moved the reporting database from MySQL to Postgres.")
    assert draft.model == claude.DEFAULT_MODEL
    assert not draft.is_safe
    flagged = " ".join(draft.invented).lower()
    assert "kubernetes" in flagged


def claude_answer(text: str):
    from dossier.ai.suggest import Drafted

    return Drafted(text=text)


# -- the settings routes -------------------------------------------------------


def test_the_provider_choice_is_live_and_kept() -> None:
    body = api.put("/api/settings/provider", json={"provider": "claude"}).json()
    assert body["provider"] == "claude"
    assert os.environ[provider.PROVIDER_VAR] == "claude"
    assert f"{provider.PROVIDER_VAR}=claude" in route.ENV_PATH.read_text(encoding="utf-8")
    # Chosen with no key: allowed, and the screen says the AI is off.
    assert body["ai"]["ok"] is False
    assert "Claude" in body["ai"]["detail"]


def test_an_unknown_provider_is_refused() -> None:
    response = api.put("/api/settings/provider", json={"provider": "gpt"})
    assert response.status_code == 422
    assert provider.PROVIDER_VAR not in os.environ


def test_a_bad_claude_key_fails_in_the_box_and_is_not_stored(monkeypatch) -> None:
    monkeypatch.setattr(claude, "verify_key", lambda key: "That key was refused: no.")
    response = api.put("/api/settings/claude-key", json={"key": "nope"})
    assert response.status_code == 422
    assert not claude.key_present()
    assert not route.ENV_PATH.exists()


def test_a_good_claude_key_is_kept_and_never_sent_back(monkeypatch) -> None:
    monkeypatch.setattr(claude, "verify_key", lambda key: None)
    response = api.put("/api/settings/claude-key", json={"key": KEY})
    assert KEY not in response.text
    body = response.json()
    assert body["claude"]["key_set"] is True
    assert body["claude"]["key_hint"].endswith(KEY[-4:])
    assert os.environ["ANTHROPIC_API_KEY"] == KEY
    assert KEY in route.ENV_PATH.read_text(encoding="utf-8")
    # The Gemini key is a separate thing and was not touched.
    assert body["key_set"] is False

    body = api.delete("/api/settings/claude-key").json()
    assert body["claude"]["key_set"] is False
    assert KEY not in route.ENV_PATH.read_text(encoding="utf-8")


def test_with_claude_chosen_and_keyed_the_ai_is_on() -> None:
    os.environ[provider.PROVIDER_VAR] = "claude"
    os.environ["ANTHROPIC_API_KEY"] = KEY
    body = api.get("/api/settings").json()
    assert body["ai"]["ok"] is True
    assert body["claude_model"] == claude.DEFAULT_MODEL
    assert api.get("/api/health").json()["ai_available"] is True
