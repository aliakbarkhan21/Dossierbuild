"""Everything about the app rather than about the document.

The line this screen has to hold is that "seven screens, each doing one
thing" is a rule, and a settings page is where things go when nobody decided
where they belong. So the test for admission here is narrow: does it describe
*the installation* rather than *the CV*? A typeface does not qualify -- that
is a property of the document and lives on the Resume screen, per printing. An
API key does.

The immediate reason this exists is that the key had nowhere to go at all.
``ai.parse`` has had ``use_api_key``, ``verify_api_key`` and
``remember_api_key`` since the import work -- three careful functions, checked
before storing so a typo fails at the point you can still see what you typed
-- and **nothing has ever called them**. Meanwhile ``ai/client.py`` told
people to "paste one into the Import page", which has never had a box to paste
it into. Somebody with no key was told the app could not do a thing and given
no way to change that without editing ``.env`` and restarting.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...ai import client as ai_client
from ...ai.parse import ENV_PATH, api_key_present, remember_api_key, use_api_key, verify_api_key
from ...core.storage import BACKUP_DIR, DATA_DIR
from ...render.pdf import chromium_ready

router = APIRouter(prefix="/api/settings", tags=["settings"])

#: Offered in the model picker. The ladder tries these in order anyway; this
#: is for pinning one when the default is congested.
MODELS = ("gemini-3.8-flash", *ai_client.FALLBACK_MODELS)


class Capability(BaseModel):
    ok: bool
    detail: str = ""


class Storage(BaseModel):
    data_dir: str
    env_file: str
    backups: int
    bytes: int


class SettingsOut(BaseModel):
    #: Never the key itself. There is no reason to send a secret back to a
    #: page that already has it, and a masked tail is enough to answer "is the
    #: one I am looking at the one I pasted".
    key_set: bool
    key_hint: str
    #: True when the key came from the real environment rather than our .env,
    #: because then clearing it here would not stick and we should say so.
    key_from_environment: bool
    model: str
    models: list[str]
    storage: Storage
    ai: Capability
    pdf: Capability


class KeyIn(BaseModel):
    key: str = Field(min_length=1, max_length=200)


class ModelIn(BaseModel):
    #: Empty means "no pin": walk the ladder from the top, which is the
    #: default and the right answer for almost everyone.
    model: str = Field(default="", max_length=80)


def _hint(key: str) -> str:
    """``AIza…9f2b``. Enough to recognise, not enough to use."""
    key = key.strip()
    if len(key) < 12:
        return "set"
    return f"{key[:4]}…{key[-4:]}"


def _folder_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def _current() -> SettingsOut:
    key = next((os.environ[v] for v in ai_client.API_KEY_VARS if os.environ.get(v)), "")
    # A key in .env is one we wrote and can remove; one exported in the shell
    # outlives this process, so "Remove" would appear to do nothing.
    from_env_file = bool(key) and ENV_PATH.exists() and key in ENV_PATH.read_text(
        encoding="utf-8", errors="ignore"
    )
    browser_ok, browser_detail = chromium_ready()
    return SettingsOut(
        key_set=api_key_present(),
        key_hint=_hint(key) if key else "",
        key_from_environment=bool(key) and not from_env_file,
        model=os.environ.get("GEMINI_MODEL", ""),
        models=list(MODELS),
        storage=Storage(
            data_dir=str(DATA_DIR),
            env_file=str(ENV_PATH),
            backups=len(list(BACKUP_DIR.glob("*"))) if BACKUP_DIR.exists() else 0,
            bytes=_folder_bytes(DATA_DIR),
        ),
        ai=Capability(
            ok=api_key_present(),
            detail="" if api_key_present() else "No key, so parsing an import and rewriting are off.",
        ),
        pdf=Capability(ok=browser_ok, detail="" if browser_ok else browser_detail),
    )


@router.get("", response_model=SettingsOut)
def index() -> SettingsOut:
    return _current()


@router.put("/key", response_model=SettingsOut)
def set_key(body: KeyIn) -> SettingsOut:
    """Check the key, then keep it. In that order, deliberately.

    A key stored without checking comes back as a failure on some later
    action, by which time the cause is two screens away. This fails in the box
    you typed it into.
    """
    problem = verify_api_key(body.key)
    if problem:
        raise HTTPException(status_code=422, detail=problem)
    use_api_key(body.key)          # live immediately, no restart
    remember_api_key(body.key)     # and still here after one
    ai_client.forget()             # the cached client holds the old key
    return _current()


@router.delete("/key", response_model=SettingsOut)
def clear_key() -> SettingsOut:
    for name in ai_client.API_KEY_VARS:
        os.environ.pop(name, None)
    if ENV_PATH.exists():
        kept = [
            line
            for line in ENV_PATH.read_text(encoding="utf-8").splitlines()
            if not line.strip().startswith(("GEMINI_API_KEY=", "GOOGLE_API_KEY="))
        ]
        ENV_PATH.write_text("\n".join(kept).rstrip("\n") + "\n", encoding="utf-8")
    ai_client.forget()
    return _current()


@router.put("/model", response_model=SettingsOut)
def set_model(body: ModelIn) -> SettingsOut:
    name = body.model.strip()
    if name and name not in MODELS:
        raise HTTPException(status_code=422, detail=f"Unknown model {name!r}.")
    if name:
        os.environ["GEMINI_MODEL"] = name
    else:
        os.environ.pop("GEMINI_MODEL", None)
    ai_client.forget()
    return _current()
