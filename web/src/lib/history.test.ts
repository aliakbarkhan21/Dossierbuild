/**
 * The undo stack's arithmetic.
 *
 * This is the only part of the store with numbers worth getting wrong, and
 * every one of them fails silently: a coalescing window that never closes
 * makes Ctrl+Z do nothing, one that never opens makes it delete a letter at a
 * time, and an off-by-one in the seek sends you to the wrong step with no
 * error anywhere.
 */

import { describe, expect, it } from "vitest";

import {
  COALESCE_MS,
  HISTORY_LIMIT,
  describeDesign,
  redoStep,
  remember,
  revertStep,
  undoStep,
  type History,
  type Snapshot,
} from "./history";
import type { Design, Profile } from "./types";

/** A profile is opaque to this module; only its identity is under test. */
const profileNamed = (name: string) => ({ basics: { name } }) as unknown as Profile;
const design = (template: string) => ({ template }) as unknown as Design;

function snapshot(name: string, template = "classic"): Snapshot {
  return { profile: profileNamed(name), design: design(template), label: "", at: 0 };
}

const fresh = (): History => ({ past: [], future: [] });
const names = (steps: Snapshot[]) => steps.map((s) => (s.profile as never as { basics: { name: string } }).basics.name);

describe("remember", () => {
  it("stores the state as it was before the change", () => {
    const h = fresh();
    remember(h, snapshot("first"), "Edited the profile", 1000);
    expect(names(h.past)).toEqual(["first"]);
  });

  it("folds a run of the same change into one step", () => {
    const h = fresh();
    remember(h, snapshot("before"), "Edited experience 1", 1000);
    remember(h, snapshot("mid"), "Edited experience 1", 1000 + COALESCE_MS - 1);
    remember(h, snapshot("later"), "Edited experience 1", 1000 + COALESCE_MS - 1 + 300);
    // One step, and it is the state the run *started* from -- which is what
    // makes one Ctrl+Z undo the whole sentence rather than one keystroke.
    expect(names(h.past)).toEqual(["before"]);
  });

  it("starts a new step after a pause", () => {
    const h = fresh();
    remember(h, snapshot("a"), "Edited experience 1", 1000);
    remember(h, snapshot("b"), "Edited experience 1", 1000 + COALESCE_MS + 1);
    expect(names(h.past)).toEqual(["a", "b"]);
  });

  it("starts a new step when the change is a different kind", () => {
    const h = fresh();
    remember(h, snapshot("a"), "Edited experience 1", 1000);
    remember(h, snapshot("b"), "Edited experience 2", 1010);
    expect(names(h.past)).toEqual(["a", "b"]);
  });

  it("drops the oldest step past the limit, and never grows beyond it", () => {
    const h = fresh();
    for (let i = 0; i < HISTORY_LIMIT + 10; i++) {
      remember(h, snapshot(`s${i}`), `Step ${i}`, i * 10_000);
    }
    expect(h.past).toHaveLength(HISTORY_LIMIT);
    expect(names(h.past)[0]).toBe("s10");
  });

  it("throws away the redo branch, because a new edit orphans it", () => {
    const h: History = { past: [], future: [snapshot("undone")] };
    remember(h, snapshot("now"), "Edited the profile", 1000);
    expect(h.future).toEqual([]);
  });
});

describe("undo and redo", () => {
  it("returns nothing when there is nothing to undo", () => {
    expect(undoStep(fresh(), snapshot("now"))).toBeNull();
    expect(redoStep(fresh(), snapshot("now"))).toBeNull();
  });

  it("hands back the previous state and files the current one for redo", () => {
    const h = fresh();
    remember(h, snapshot("first"), "Changed the template", 1000);
    const back = undoStep(h, snapshot("second"), 2000);

    expect(names([back!])).toEqual(["first"]);
    expect(h.past).toEqual([]);
    expect(names(h.future)).toEqual(["second"]);
    // The redo entry is named for the step it would replay, so the panel can
    // say "Redo: changed the template".
    expect(h.future[0]!.label).toBe("Changed the template");
  });

  it("round-trips: undo then redo lands where it started", () => {
    const h = fresh();
    remember(h, snapshot("first"), "Changed the template", 1000);
    const back = undoStep(h, snapshot("second"), 2000)!;
    const forward = redoStep(h, back, 3000)!;

    expect(names([forward])).toEqual(["second"]);
    expect(h.future).toEqual([]);
    expect(names(h.past)).toEqual(["first"]);
  });

  it("carries the design back with the profile", () => {
    const h = fresh();
    remember(h, snapshot("first", "classic"), "Changed the template", 1000);
    const back = undoStep(h, snapshot("first", "editorial"), 2000)!;
    // The whole reason a snapshot holds both: undoing a template change has
    // to restore the template.
    expect((back.design as never as { template: string }).template).toBe("classic");
  });
});

describe("revertStep", () => {
  /** Four states: a -> b -> c -> now, with three steps recorded. */
  function walked(): History {
    const h = fresh();
    remember(h, snapshot("a"), "Step one", 1000);
    remember(h, snapshot("b"), "Step two", 20_000);
    remember(h, snapshot("c"), "Step three", 40_000);
    return h;
  }

  it("returns nothing for an index that is not there", () => {
    expect(revertStep(walked(), snapshot("now"), 9)).toBeNull();
    expect(revertStep(walked(), snapshot("now"), -1)).toBeNull();
  });

  it("jumps to the chosen step and keeps everything before it", () => {
    const h = walked();
    const back = revertStep(h, snapshot("now"), 0, 60_000)!;
    expect(names([back])).toEqual(["a"]);
    expect(h.past).toEqual([]);
  });

  it("puts every skipped step on the redo stack, in walking order", () => {
    const h = walked();
    revertStep(h, snapshot("now"), 0, 60_000);
    // Redoing from "a" should walk a -> b -> c -> now, so the stack reads
    // b, c, now from the front. This is the off-by-one that a panel makes
    // easy to write and impossible to notice.
    expect(names(h.future)).toEqual(["b", "c", "now"]);
  });

  it("is equivalent to pressing undo that many times", () => {
    const stepwise = walked();
    let state = snapshot("now");
    for (let i = 0; i < 3; i++) state = undoStep(stepwise, state, 60_000)!;

    const seek = walked();
    const jumped = revertStep(seek, snapshot("now"), 0, 60_000)!;

    expect(names([state])).toEqual(names([jumped]));
    expect(names(seek.future)).toEqual(names(stepwise.future));
    expect(seek.past).toEqual(stepwise.past);
  });

  it("redo after a seek walks back up one step at a time", () => {
    const h = walked();
    let state = revertStep(h, snapshot("now"), 0, 60_000)!;
    state = redoStep(h, state, 70_000)!;
    expect(names([state])).toEqual(["b"]);
    state = redoStep(h, state, 80_000)!;
    expect(names([state])).toEqual(["c"]);
    state = redoStep(h, state, 90_000)!;
    expect(names([state])).toEqual(["now"]);
    expect(h.future).toEqual([]);
  });
});

describe("describeDesign", () => {
  it("names a single change in the user's language", () => {
    expect(describeDesign({ template: "gazette" })).toBe("Changed the template");
    expect(describeDesign({ scale: 104 })).toBe("Changed the type size");
  });

  it("calls a whole bundle what it is", () => {
    // A look sets template, layout, accent, fonts, scale and more at once;
    // listing them is noise.
    expect(
      describeDesign({ template: "gazette", layout: "rail", accent: "navy", fonts: "slab", scale: 96 }),
    ).toBe("Applied a look");
  });

  it("falls back to the field name rather than to nothing", () => {
    expect(describeDesign({ nonsense: 1 } as never)).toBe("Changed nonsense");
    expect(describeDesign({})).toBe("Changed the design");
  });
});
