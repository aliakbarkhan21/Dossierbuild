/**
 * Turning a flat list of CVs into the people who own them.
 *
 * The registry stores a flat list because that is what it is on disk. The
 * switcher shows people, because fifteen rows of which five read "Muhammad Ali
 * Akbar Khan" is not a list anybody can choose from. This is the one step
 * between the two, and it lives here rather than inside the component so the
 * ordering rule can be stated once and tested without a browser.
 */

import type { CVSummary } from "./types";

/** `NameIn` on the route refuses anything longer, so nothing longer is offered. */
export const CV_NAME_MAX = 80;

export interface PersonGroup {
  person: string;
  cvs: CVSummary[];
}

/**
 * Whose CV this is, surviving a server that has not been restarted.
 *
 * A build from before the name was split sends `name` and no `person`, and the
 * bundle in the browser is replaced by a rebuild while the Python process is
 * not. For the minute or two that lasts, every CV would group under
 * `undefined` -- one row, no name on it, everybody's CVs inside. Falling back
 * to `name` is the same thing `_entries` does on the server for an unmigrated
 * row, and it degrades to exactly the old behaviour instead of to a blank.
 */
export function personOf(cv: Pick<CVSummary, "person"> & { name?: string }): string {
  return cv.person || cv.name || "Untitled";
}

/**
 * Group by person, keeping the registry's order on both levels.
 *
 * First-seen order rather than alphabetical: the registry appends, so the
 * person you added most recently stays at the bottom where you last saw them,
 * and nobody's row moves because somebody else was renamed. Sorting would make
 * the list rearrange itself under a rename, which is the one moment you are
 * looking straight at it.
 */
export function groupByPerson(cvs: CVSummary[]): PersonGroup[] {
  const groups = new Map<string, PersonGroup>();
  for (const cv of cvs) {
    const person = personOf(cv);
    const existing = groups.get(person);
    if (existing) existing.cvs.push(cv);
    else groups.set(person, { person, cvs: [cv] });
  }
  return [...groups.values()];
}

/** How a CV reads on one line, matching `CV.name` on the server. */
export function oneLine(cv: Pick<CVSummary, "person" | "label"> & { name?: string }): string {
  const person = personOf(cv);
  return cv.label ? `${person} — ${cv.label}` : person;
}
