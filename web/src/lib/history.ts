/**
 * Undo, redo, and the seek between them — as pure functions over two stacks.
 *
 * Kept out of the store because this is the only part of it with arithmetic
 * worth getting wrong: which snapshot a panel index refers to, what happens
 * to the steps a seek jumps over, and when two changes are one step. Pure
 * functions can be tested without a browser, a fetch or a zustand instance,
 * and `history.test.ts` pins each of those.
 *
 * Every function takes the history and the state *as it is now*, mutates the
 * history in place (immer gives us a draft, so this is the cheap way), and
 * returns the snapshot the caller should restore — or null when there is
 * nothing to do.
 */

import type { Design, Profile } from "./types";

/**
 * One step back, holding **both** documents.
 *
 * The design used to sit outside the history entirely, so changing a template
 * and pressing Ctrl+Z undid the last thing you typed instead — which is the
 * opposite of "the obvious thing". A snapshot carries the pair because the
 * user is editing one resume, not two files.
 */
export interface Snapshot {
  profile: Profile;
  design: Design | null;
  /** What the change *away from* this state was called. */
  label: string;
  at: number;
}

export interface History {
  /** Oldest first. */
  past: Snapshot[];
  /** Newest first, so `future[0]` is the next redo. */
  future: Snapshot[];
}

/** How far back undo reaches. */
export const HISTORY_LIMIT = 50;

/**
 * Consecutive changes of the same kind inside this window become one step.
 *
 * Without it, typing a fifty-character bullet pushed fifty entries and a
 * fifty-deep history held one sentence — so Ctrl+Z deleted a letter and three
 * presses got you nowhere. This is what a text editor does: a step is a
 * pause, not a keystroke. A slider is the same problem at a dozen changes a
 * second.
 */
export const COALESCE_MS = 700;

/**
 * Record the state about to be changed, folding it into the last step when it
 * is more of the same.
 *
 * The snapshot stored is the state *before* a run of edits began, which is
 * what makes one Ctrl+Z undo the whole run rather than one keystroke of it.
 */
export function remember(
  history: History,
  current: Snapshot,
  label: string,
  now = Date.now(),
): void {
  const last = history.past.at(-1);
  if (last && last.label === label && now - last.at < COALESCE_MS) {
    // Extend the run rather than starting a new step. The snapshot itself is
    // untouched: it is still the state the run started from.
    last.at = now;
    return;
  }
  history.past.push({ ...current, label, at: now });
  if (history.past.length > HISTORY_LIMIT) history.past.shift();
  // Anything redone is unreachable the moment a new branch starts.
  history.future = [];
}

/** One step back. Returns what to restore, or null if there is nothing. */
export function undoStep(
  history: History,
  current: Snapshot,
  now = Date.now(),
): Snapshot | null {
  const step = history.past.at(-1);
  if (!step) return null;
  history.past.pop();
  // The redo entry carries the label of the step being undone, so the panel
  // can say "Redo: changed the template" rather than naming the state.
  history.future.unshift({ ...current, label: step.label, at: now });
  return step;
}

/** One step forward. */
export function redoStep(
  history: History,
  current: Snapshot,
  now = Date.now(),
): Snapshot | null {
  const step = history.future[0];
  if (!step) return null;
  history.future.shift();
  history.past.push({ ...current, label: step.label, at: now });
  return step;
}

/**
 * Jump to a point in the panel. `index` indexes `past`, oldest-first.
 *
 * A seek, not a one-way door: every step skipped over goes onto the redo
 * stack in order, so pressing redo walks back up through exactly the steps
 * this passed. Getting that order wrong is the bug this function exists to
 * make testable.
 */
export function revertStep(
  history: History,
  current: Snapshot,
  index: number,
  now = Date.now(),
): Snapshot | null {
  const target = history.past[index];
  if (!target) return null;
  const skipped = history.past.splice(index);
  // `skipped[0]` is the target itself. Walking forward again means restoring
  // each *later* state, so the redo entries are the states after each skipped
  // step: the ones still in `skipped`, plus `current` at the end.
  const forward: Snapshot[] = [];
  for (let i = 1; i < skipped.length; i++) {
    forward.push({ ...skipped[i]!, label: skipped[i - 1]!.label });
  }
  forward.push({ ...current, label: skipped.at(-1)!.label, at: now });
  // In walking order already, and `future` is newest-*last* to walk forward
  // through: `future[0]` is the next redo. Reversing here is the mistake this
  // function's tests exist to catch -- it made redo after a seek jump
  // straight back to where the seek started.
  history.future.unshift(...forward);
  return target;
}

/**
 * What a design change is called in the history.
 *
 * Derived from the patch rather than passed in by each control: there are
 * fifteen of them and one `setDesign`, and a map in one place stays correct
 * when the sixteenth is added.
 */
const DESIGN_LABELS: Record<string, string> = {
  template: "Changed the template",
  layout: "Changed the body layout",
  accent: "Changed the accent colour",
  fonts: "Changed the typeface",
  page: "Changed the paper size",
  margin: "Changed the margins",
  leading: "Changed the line spacing",
  scale: "Changed the type size",
  date_format: "Changed the date format",
  order: "Reordered the sections",
  hidden: "Showed or hid a section",
  show_links: "Toggled the header links",
  show_headline: "Toggled the headline",
  show_page_numbers: "Toggled page numbers",
  show_photo: "Toggled the portrait",
};

export function describeDesign(patch: Partial<Design>): string {
  const keys = Object.keys(patch);
  if (keys.length === 0) return "Changed the design";
  // A look applies a dozen keys at once, and listing them is noise.
  if (keys.length > 3) return "Applied a look";
  return keys.map((key) => DESIGN_LABELS[key] ?? `Changed ${key}`).join(", ");
}
