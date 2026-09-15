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
    const existing = groups.get(cv.person);
    if (existing) existing.cvs.push(cv);
    else groups.set(cv.person, { person: cv.person, cvs: [cv] });
  }
  return [...groups.values()];
}

/** How a CV reads on one line, matching `CV.name` on the server. */
export function oneLine(cv: Pick<CVSummary, "person" | "label">): string {
  return cv.label ? `${cv.person} — ${cv.label}` : cv.person;
}
