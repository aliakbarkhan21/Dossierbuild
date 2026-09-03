/**
 * Light and dark, remembered.
 *
 * The class is applied by a script in index.html before first paint, so this
 * only handles changes. Reading the stored value here as well keeps the
 * toggle honest on a page that was loaded following the system setting.
 */

const KEY = "dossier.mode";

export type Mode = "light" | "dark";

export function currentMode(): Mode {
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

export function setMode(mode: Mode): void {
  document.documentElement.classList.toggle("dark", mode === "dark");
  try {
    localStorage.setItem(KEY, mode);
  } catch {
    /* private browsing: the preference simply does not persist */
  }
}

export function toggleMode(): Mode {
  const next: Mode = currentMode() === "dark" ? "light" : "dark";
  setMode(next);
  return next;
}
