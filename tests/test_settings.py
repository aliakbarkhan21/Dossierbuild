"""The settings screen's routes.

No network. ``verify_api_key`` is the only thing here that would reach Google,
and it is replaced -- what these check is the route's own behaviour: that a
key is verified *before* being stored, that the key never travels back to the
client, and that removing one really does take it out of the file.

``conftest`` points ``DOSSIER_ENV_FILE`` at a temporary directory, so nothing
here can touch the .env belonging to a real install.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from dossier.ai import client as ai_client
from dossier.api import app
from dossier.api.routes import settings as route

client = TestClient(app)

GOOD = "AIzaSyD-a-key-that-looks-plausible-0001"


@pytest.fixture(autouse=True)
def clean_env():
    """Every test starts with no key, and leaves none behind."""
    saved = {name: os.environ.get(name) for name in (*ai_client.API_KEY_VARS, "GEMINI_MODEL")}
    for name in saved:
        os.environ.pop(name, None)
    if route.ENV_PATH.exists():
        route.ENV_PATH.unlink()
    yield
    for name, value in saved.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


@pytest.fixture()
def accept(monkeypatch):
    monkeypatch.setattr(route, "verify_api_key", lambda key: None)


def test_it_says_what_this_copy_can_do() -> None:
    body = client.get("/api/settings").json()
    assert body["key_set"] is False
    assert body["key_hint"] == ""
    assert body["ai"]["ok"] is False
    # Whether Chromium is here depends on the machine; that it is answered is
    # what makes the screen worth having.
    assert "ok" in body["pdf"]
    assert body["storage"]["data_dir"]
    assert "gemini-3.8-flash" in body["models"]


def test_a_bad_key_fails_in_the_box_and_is_not_stored(monkeypatch) -> None:
    monkeypatch.setattr(route, "verify_api_key", lambda key: "That key was refused: no.")
    response = client.put("/api/settings/key", json={"key": "nope"})
    assert response.status_code == 422
    assert "refused" in response.json()["detail"]
    # Neither the process nor the file learned it.
    assert not any(os.environ.get(v) for v in ai_client.API_KEY_VARS)
    assert not route.ENV_PATH.exists()


def test_a_good_key_is_live_at_once_and_still_there_after_a_restart(accept) -> None:
    body = client.put("/api/settings/key", json={"key": GOOD}).json()
    assert body["key_set"] is True
    # Live in this process, so nothing needs restarting.
    assert os.environ["GEMINI_API_KEY"] == GOOD
    # And on disk, so a restart keeps it.
    assert GOOD in route.ENV_PATH.read_text(encoding="utf-8")


def test_the_key_never_travels_back_to_the_client(accept) -> None:
    response = client.put("/api/settings/key", json={"key": GOOD})
    assert GOOD not in response.text
    body = response.json()
    # A tail is enough to answer "is this the one I pasted".
    assert body["key_hint"].startswith("AIza")
    assert body["key_hint"].endswith(GOOD[-4:])
    assert len(body["key_hint"]) < len(GOOD)


def test_removing_a_key_takes_it_out_of_the_file(accept) -> None:
    client.put("/api/settings/key", json={"key": GOOD})
    body = client.delete("/api/settings/key").json()
    assert body["key_set"] is False
    assert not any(os.environ.get(v) for v in ai_client.API_KEY_VARS)
    assert GOOD not in route.ENV_PATH.read_text(encoding="utf-8")


def test_a_key_from_the_shell_is_reported_as_not_ours() -> None:
    """One exported outside the app outlives it, so Remove would do nothing."""
    os.environ["GEMINI_API_KEY"] = "from-the-shell-not-our-file"
    body = client.get("/api/settings").json()
    assert body["key_set"] is True
    assert body["key_from_environment"] is True


def test_a_model_can_be_pinned_and_unpinned() -> None:
    assert client.put("/api/settings/model", json={"model": "gemini-3.6-flash"}).json()["model"] == (
        "gemini-3.6-flash"
    )
    assert os.environ["GEMINI_MODEL"] == "gemini-3.6-flash"
    assert client.put("/api/settings/model", json={"model": ""}).json()["model"] == ""
    assert "GEMINI_MODEL" not in os.environ


def test_an_unknown_model_is_refused() -> None:
    response = client.put("/api/settings/model", json={"model": "gpt-9"})
    assert response.status_code == 422
    assert "gpt-9" in response.json()["detail"]


def test_changing_the_key_drops_the_cached_client(accept, monkeypatch) -> None:
    """The client is keyed on the key, but the last-good model is not."""
    monkeypatch.setattr(ai_client, "_last_good", "gemini-3.5-flash")
    client.put("/api/settings/key", json={"key": GOOD})
    assert ai_client._last_good is None
