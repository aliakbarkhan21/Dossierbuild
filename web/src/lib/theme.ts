/**
 * Light or dark, and nothing else.
 *
 * The class is applied by a script in index.html before first paint, so this
 * only handles changes. Reading the stored value here as well keeps the
 * control honest on a page that was loaded before React ran.
 *
 * **There was a third mode, "system", and it is gone.** It cost the toggle its
 * whole point: a control you press to change the theme should change the
 * theme, and one press in three did something you could not see -- picking the
 * setting the app was already showing. The operating system still decides
 * where a *first* visit starts, which is the part that actually mattered
 * (nobody who runs their machine dark should meet a white app). It stops being
 * a state you can be in the moment you express a preference.
 */

const KEY = "dossier.mode";

export type Mode = "light" | "dark";

const MODES: Mode[] = ["light", "dark"];

function systemPrefersDark(): boolean {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
}

/**
 * The stored choice, or what this computer is set to if there is not one yet.
 *
 * Anything unrecognised falls through to the system as well, which is what
 * quietly retires the "system" value left in the storage of anyone who was
 * using it: they keep the appearance they had, and their next press writes a
 * real one.
 */
export function currentMode(): Mode {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved && (MODES as string[]).includes(saved)) return saved as Mode;
  } catch {
    /* private browsing: nothing was ever stored */
  }
  return systemPrefersDark() ? "dark" : "light";
}

export function setMode(mode: Mode): Mode {
  document.documentElement.classList.toggle("dark", mode === "dark");
  try {
    localStorage.setItem(KEY, mode);
  } catch {
    /* private browsing: the preference simply does not persist */
  }
  return mode;
}

/** The other one. */
export function cycleMode(): Mode {
  return setMode(currentMode() === "dark" ? "light" : "dark");
}
