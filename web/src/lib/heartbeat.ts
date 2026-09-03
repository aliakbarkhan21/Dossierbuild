/**
 * Tell the server someone is still here, and tell it when they leave.
 *
 * Dossierbuild is a desktop app built out of a web server, and a desktop app
 * quits when its window closes. This is what lets the server do that, and so
 * what removes the need for a second desktop icon whose only job was to stop
 * the first.
 *
 * Two signals, because neither is sufficient alone:
 *
 * * `pagehide` fires the moment the tab goes away, which is what makes
 *   closing it feel immediate. But it also fires on a refresh and on a
 *   navigation, so on its own it would shut the app down every time you
 *   pressed F5. The server therefore treats it as "probably leaving" and
 *   waits a few seconds for a heartbeat to contradict it.
 * * The heartbeat is the backstop, for the cases that send no event at all:
 *   a crashed tab, a killed browser, a laptop that lost power. Its timeout is
 *   deliberately long -- browsers throttle timers in hidden tabs to roughly
 *   once a minute, and a short timeout would kill the app while someone was
 *   reading a job description in another tab.
 */

const INTERVAL_MS = 3000;

async function beat(): Promise<void> {
  try {
    await fetch("/api/alive", { method: "POST", keepalive: true });
  } catch {
    /* the server going away is the normal end of a session, not an error */
  }
}

export function startHeartbeat(): () => void {
  void beat();
  const timer = setInterval(() => void beat(), INTERVAL_MS);

  const onShow = () => {
    // Coming back from a hidden tab or the back/forward cache. Beat at once
    // rather than waiting for the next interval, so a "leaving" flag raised
    // by pagehide is withdrawn immediately.
    if (document.visibilityState === "visible") void beat();
  };

  const onHide = () => {
    // sendBeacon rather than fetch: the page is being torn down, and it is
    // the one request the browser guarantees to deliver anyway.
    try {
      navigator.sendBeacon("/api/leaving", "");
    } catch {
      /* nothing useful to do while the page is disappearing */
    }
  };

  document.addEventListener("visibilitychange", onShow);
  window.addEventListener("pageshow", onShow);
  window.addEventListener("pagehide", onHide);

  return () => {
    clearInterval(timer);
    document.removeEventListener("visibilitychange", onShow);
    window.removeEventListener("pageshow", onShow);
    window.removeEventListener("pagehide", onHide);
  };
}
