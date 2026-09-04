"""Stop the server when the last tab closes.

Dossierbuild is a desktop app that happens to be built out of a web server. A
desktop app quits when you close its window; leaving a Python process holding
port 8000 until the next reboot is server behaviour, and the price of it was a
second desktop icon whose entire job was to undo the first.

Two signals from the page, because neither is sufficient alone:

* ``/api/leaving`` is sent by ``pagehide`` the instant a tab goes away, which
  is what makes closing the window feel immediate. It cannot be trusted on its
  own, because it fires on a refresh and on a navigation too -- so it only
  starts a short countdown, and any heartbeat arriving during that countdown
  cancels it. A reload comes back well inside the window.
* ``/api/alive`` every few seconds is the backstop, for the endings that send
  no event at all: a crashed tab, a killed browser, a lost battery. Its
  timeout is deliberately long, because browsers throttle timers in hidden
  tabs to roughly once a minute and a short one would kill the app while
  someone was reading a job description in another tab.

Before the browser has ever connected, silence is normal -- uvicorn binds the
port a second or two before Chrome renders anything -- so the clock does not
start until the first heartbeat, with an outer limit in case no browser ever
arrives.
"""

from __future__ import annotations

import asyncio
import os
import signal
import time

from fastapi import FastAPI

# How long to wait after a tab says it is going, in case it was a refresh.
LEAVING_GRACE = 6.0

# The no-events-at-all backstop. Must comfortably exceed the once-a-minute
# floor that browsers throttle hidden tabs to.
IDLE_TIMEOUT = 150.0

# If the browser never arrives -- someone ran uvicorn by hand, or the launcher
# failed to open a window -- do not sit forever, but do not lose the race on a
# slow machine either.
STARTUP_GRACE = 180.0

CHECK_EVERY = 1.0


class Lifetime:
    """Tracks whether anyone is still watching."""

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled
        self.started = time.monotonic()
        self.last_seen: float | None = None
        self.leaving_since: float | None = None

    def beat(self, now: float | None = None) -> None:
        # `now` is here for the same reason `should_stop` has it: these three
        # are one clock, and a test that fabricates a time for one of them and
        # lets the others read `time.monotonic()` is comparing a made-up
        # instant against however long this machine has been switched on. That
        # is exactly what the refresh test was doing -- it passed on a machine
        # up for a quarter of an hour and failed on one just booted.
        self.last_seen = time.monotonic() if now is None else now
        # A heartbeat is proof the page is still there, so it withdraws a
        # pagehide that turned out to be a refresh.
        self.leaving_since = None

    def leaving(self, now: float | None = None) -> None:
        self.leaving_since = time.monotonic() if now is None else now

    def seconds_since_beat(self) -> float | None:
        """For /api/health, so "why has it not exited" is answerable."""
        return None if self.last_seen is None else round(time.monotonic() - self.last_seen, 1)

    def should_stop(self, now: float | None = None) -> bool:
        if not self.enabled:
            return False
        now = time.monotonic() if now is None else now

        if self.last_seen is None:
            # Nobody has ever connected.
            return now - self.started > STARTUP_GRACE

        if self.leaving_since is not None and now - self.leaving_since > LEAVING_GRACE:
            return True

        return now - self.last_seen > IDLE_TIMEOUT


def install(app: FastAPI) -> None:
    """Add the heartbeat endpoints, and the watchdog behind them.

    Off unless ``DOSSIER_EXIT_WHEN_IDLE=1``. The launcher sets it; a developer
    running ``uvicorn --reload`` does not, and their server stays up whether or
    not a browser is pointed at it.
    """
    state = Lifetime(enabled=os.environ.get("DOSSIER_EXIT_WHEN_IDLE") == "1")
    app.state.lifetime = state

    @app.post("/api/alive", include_in_schema=False)
    async def alive() -> dict[str, bool]:
        state.beat()
        return {"ok": True}

    @app.post("/api/leaving", include_in_schema=False)
    async def leaving() -> dict[str, bool]:
        state.leaving()
        return {"ok": True}

    if not state.enabled:
        return

    async def watchdog() -> None:
        while True:
            await asyncio.sleep(CHECK_EVERY)
            if state.should_stop():
                # SIGINT rather than sys.exit: uvicorn owns the event loop and
                # this coroutine runs inside it. Its own handler is what shuts
                # down properly -- closing connections, firing lifespan events
                # -- instead of tearing the loop down from within itself.
                signal.raise_signal(signal.SIGINT)
                return

    @app.on_event("startup")
    async def _start() -> None:
        app.state.watchdog = asyncio.create_task(watchdog())

    @app.on_event("shutdown")
    async def _stop() -> None:
        task = getattr(app.state, "watchdog", None)
        if task:
            task.cancel()
