/**
 * Light, dark, or whichever the computer is using.
 *
 * The class is applied by a script in index.html before first paint, so this
 * only handles changes. Reading the stored value here as well keeps the
 * control honest on a page that was loaded following the system setting.
 *
 * **Why "system" is a stored value rather than the absence of one.** It was
 * the absence of one, which made following the system a state you could leave
 * and never return to: the first click on the toggle wrote "light" or "dark",
 * and nothing could ever unset it again. A person who dims their machine in
 * the evening wants the app to come with them, and that was a one-way door.
 */

const KEY = "dossier.mode";

/** What the user chose. Not what is on screen -- see `resolved`. */
export type Mode = "light" | "dark" | "system";

const MODES: Mode[] = ["light", "dark", "system"];

function systemPrefersDark(): boolean {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
}

/** The stored choice, defaulting to following the system. */
export function currentMode(): Mode {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved && (MODES as string[]).includes(saved)) return saved as Mode;
  } catch {
    /* private browsing: nothing was ever stored */
  }
  return "system";
}

/** What is actually painted right now: "system" resolved against the OS. */
export function resolved(mode: Mode = currentMode()): "light" | "dark" {
  if (mode === "system") return systemPrefersDark() ? "dark" : "light";
  return mode;
}

export function setMode(mode: Mode): Mode {
  document.documentElement.classList.toggle("dark", resolved(mode) === "dark");
  try {
    localStorage.setItem(KEY, mode);
  } catch {
    /* private browsing: the preference simply does not persist */
  }
  return mode;
}

/** Light, then dark, then back to following the system. */
export function cycleMode(): Mode {
  const order: Mode[] = ["light", "dark", "system"];
  const next = order[(order.indexOf(currentMode()) + 1) % order.length] ?? "system";
  return setMode(next);
}

/**
 * Repaint when the OS changes, but only while following it.
 *
 * Without this, "system" would mean "whatever the system was when this tab
 * opened" -- which is wrong precisely at the moment it matters, when the
 * machine turns dark at sunset and the tab has been open all day.
 */
export function watchSystem(onChange: (mode: Mode) => void): () => void {
  const query = window.matchMedia?.("(prefers-color-scheme: dark)");
  if (!query) return () => {};
  const react = () => {
    if (currentMode() === "system") {
      document.documentElement.classList.toggle("dark", query.matches);
      onChange("system");
    }
  };
  query.addEventListener("change", react);
  return () => query.removeEventListener("change", react);
}
