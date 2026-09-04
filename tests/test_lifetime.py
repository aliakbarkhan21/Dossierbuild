"""When the server decides nobody is watching any more.

This logic decides when the app closes itself, so both mistakes are bad in
different ways: quitting too eagerly loses someone's session mid-sentence,
and never quitting is the background process the stop icon existed to kill.

``should_stop`` takes the clock as an argument so these can test a laptop lid
closed for an hour without waiting an hour.
"""

from __future__ import annotations

from dossier.api.lifetime import (
    IDLE_TIMEOUT,
    LEAVING_GRACE,
    STARTUP_GRACE,
    Lifetime,
)


def live() -> Lifetime:
    state = Lifetime(enabled=True)
    state.started = 0.0
    return state


def test_disabled_never_stops() -> None:
    """A developer's uvicorn --reload has no browser and must survive that."""
    state = Lifetime(enabled=False)
    state.started = 0.0
    assert not state.should_stop(now=STARTUP_GRACE + IDLE_TIMEOUT + 10_000)


def test_it_waits_for_the_browser_to_arrive() -> None:
    """uvicorn binds the port a second or two before Chrome renders anything."""
    state = live()
    assert not state.should_stop(now=STARTUP_GRACE - 1)


def test_it_gives_up_if_no_browser_ever_arrives() -> None:
    state = live()
    assert state.should_stop(now=STARTUP_GRACE + 1)


def test_a_beating_page_keeps_it_alive() -> None:
    state = live()
    state.beat()
    state.last_seen = 1000.0
    assert not state.should_stop(now=1000.0 + IDLE_TIMEOUT - 1)


def test_a_hidden_tab_beating_once_a_minute_keeps_it_alive() -> None:
    """Browsers throttle timers in background tabs to about once a minute.

    Someone reading a job description in another tab has not closed the app,
    and the backstop has to clear that floor with room to spare.
    """
    assert IDLE_TIMEOUT > 60.0 * 2


def test_it_stops_when_the_beats_stop() -> None:
    """A crashed tab or a killed browser sends no event at all."""
    state = live()
    state.beat()
    state.last_seen = 1000.0
    assert state.should_stop(now=1000.0 + IDLE_TIMEOUT + 1)


def test_closing_a_tab_stops_it_promptly() -> None:
    state = live()
    state.beat()
    state.last_seen = 1000.0
    state.leaving_since = 1000.0
    assert not state.should_stop(now=1000.0 + LEAVING_GRACE - 1)
    assert state.should_stop(now=1000.0 + LEAVING_GRACE + 1)


def test_a_refresh_does_not_stop_it() -> None:
    """pagehide fires on F5 too; the beat that follows must withdraw it.

    This is the failure that would make the app unusable: reload the page,
    and the server it was talking to is gone.
    """
    state = live()
    state.beat(now=999.0)
    state.leaving_since = 1000.0

    state.beat(now=1001.0)  # the reloaded page, about a second later

    assert state.leaving_since is None
    assert not state.should_stop(now=1000.0 + LEAVING_GRACE + 1)


def test_the_leaving_grace_outlasts_a_reload() -> None:
    """A reload re-registers in well under a second; the grace is seconds."""
    assert LEAVING_GRACE >= 3.0
