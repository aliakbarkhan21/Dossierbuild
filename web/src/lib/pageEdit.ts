/**
 * Turning a place on the printed page back into a place in the profile.
 *
 * The resume in the preview is a rendering, not a document — there is no text
 * file behind it to edit. So editing it means answering one question: which
 * field produced this paragraph? The renderer is the only thing that knows,
 * and it says so in a `data-edit` attribute (see `render/context.py`), which
 * is an address like:
 *
 *     summary
 *     experience/exp_3f/role
 *     experience/exp_3f/bullets/blt_9a
 *     sections/cus_1c/text
 *
 * By id rather than by position, because position is the thing most likely to
 * change between the render and the edit — reordering a bullet would
 * otherwise rewrite the wrong one.
 *
 * Nothing here talks to the server. Both functions mutate an Immer draft
 * inside `store.edit`, which is the same call the Profile screen makes — so
 * an edit made on the page lands in the undo stack, in autosave and in the
 * writing standard exactly like one typed into a form. One data model, one
 * way in; a second path is how two screens start disagreeing about what the
 * profile says.
 */

import type { Profile } from "./types";

type Bag = Record<string, unknown>;
type Block = { id: string; text: string; tags: string[] };

/** What a `data-edit` or `data-move` address resolves to. */
interface Spot {
  /** The list the entry lives in — "experience", "sections", … */
  section: string;
  /** The entry itself, as a loose bag so one resolver covers every section. */
  entry: Bag;
  /** Its index in that list, for a move or a delete. */
  index: number;
  list: Bag[];
  /** Set when the address named a bullet rather than the entry. */
  bullet?: { block: Block; index: number; list: Block[] };
  /** Set when the address named a scalar field on the entry. */
  field?: string;
}

function locate(profile: Profile, path: string): Spot | null {
  const parts = path.split("/").filter(Boolean);
  if (parts.length < 2) return null;

  const [section, entryId, ...rest] = parts;
  const list = (profile as unknown as Record<string, Bag[]>)[section!];
  if (!Array.isArray(list)) return null;

  const index = list.findIndex((item) => item.id === entryId);
  if (index < 0) return null;
  const entry = list[index]!;
  const spot: Spot = { section: section!, entry, index, list };

  if (rest[0] === "bullets" && rest[1]) {
    const bullets = (entry.bullets as Block[] | undefined) ?? [];
    const at = bullets.findIndex((b) => b.id === rest[1]);
    if (at < 0) return null;
    spot.bullet = { block: bullets[at]!, index: at, list: bullets };
  } else if (rest[0]) {
    spot.field = rest[0];
  }
  return spot;
}

/**
 * Write a new value into whatever the address names.
 *
 * Returns a label for the history panel, or "" when the address named nothing
 * — which happens legitimately: a message can arrive from a frame rendered
 * against a profile that has since had that entry deleted.
 */
export function applyPageChange(profile: Profile, path: string, value: string): string {
  const text = value.replace(/\s+/g, " ").trim();

  if (path === "summary") {
    profile.summary.text = text;
    return "Edited the summary";
  }

  const spot = locate(profile, path);
  if (!spot) return "";

  if (spot.bullet) {
    spot.bullet.block.text = text;
    return "Edited a line";
  }
  if (spot.field && spot.field in spot.entry) {
    spot.entry[spot.field] = text;
    return "Edited on the page";
  }
  return "";
}

/** Move, remove, or add a line beside the one the rail is on. */
export function applyPageCommand(profile: Profile, op: string, path: string): string {
  const spot = locate(profile, path);
  if (!spot) return "";

  // A bullet moves and is removed within its own entry; an entry within its
  // section. Same four operations, two different lists.
  const list: unknown[] = spot.bullet ? spot.bullet.list : spot.list;
  const at = spot.bullet ? spot.bullet.index : spot.index;
  const what = spot.bullet ? "line" : "entry";

  if (op === "up" || op === "down") {
    const to = op === "up" ? at - 1 : at + 1;
    if (to < 0 || to >= list.length) return "";
    const [moved] = list.splice(at, 1);
    list.splice(to, 0, moved);
    return `Moved a ${what} ${op}`;
  }

  if (op === "delete") {
    list.splice(at, 1);
    return `Removed a ${what}`;
  }

  if (op === "add" && spot.bullet) {
    // An empty id, because ids are the server's to mint — the same contract
    // the Profile editor's "Add bullet" follows.
    spot.bullet.list.splice(at + 1, 0, { id: "", text: "", tags: [] });
    return "Added a line";
  }

  return "";
}
