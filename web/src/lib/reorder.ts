/**
 * Reordering a list by pointer, with a keyboard equivalent beside it.
 *
 * **Pointer events, not HTML5 drag-and-drop.** The native API looks like the
 * obvious choice and is the wrong one here: it does not fire for touch at
 * all, so a drag handle stays decoration on a phone, and it cannot be driven
 * by synthetic events, so the behaviour cannot be tested. Pointer events
 * cover mouse, touch and pen in one path.
 *
 * A drag is unreachable from a keyboard whatever API draws it, so every list
 * that uses this also renders move-up / move-down buttons. That is not a
 * fallback, it is the accessible path.
 *
 * Extracted from `EntryList`, which had this inline, when bullets needed the
 * same behaviour. Two copies of a drag implementation is two sets of pointer
 * leaks to get wrong.
 */

import { useRef, useState } from "react";

export interface Reorder {
  /** The index currently in the air, or null. */
  dragging: number | null;
  /** The index it would land on, or null. */
  over: number | null;
  /**
   * How far the pointer has moved down the page since the drag began, in px.
   *
   * A list can ignore this and draw a drop indicator, or use it to carry the
   * row under the finger and shuffle its neighbours out of the way. The
   * second reads as picking a thing up; the first reads as filling in a form
   * about where you would like it to go.
   */
  offset: number;
  /** Put this on the scroll container holding the rows. */
  listRef: React.RefObject<HTMLDivElement | null>;
  /** Put this on the drag handle: `onPointerDown={(e) => startDrag(i, e)}`. */
  startDrag: (index: number, event: React.PointerEvent) => void;
}

/**
 * @param move      commits the reorder; called once, on release
 * @param rowSelector  finds the rows inside `listRef`, each carrying
 *                     `data-reorder-index`
 */
export function useReorder(
  move: (from: number, to: number) => void,
  rowSelector = "[data-reorder-index]",
): Reorder {
  const [dragging, setDragging] = useState<number | null>(null);
  const [over, setOver] = useState<number | null>(null);
  const [offset, setOffset] = useState(0);
  const startY = useRef(0);
  const listRef = useRef<HTMLDivElement>(null);
  // The live values the pointer handlers read. State drives the rendering;
  // these exist because the handler that commits the move runs outside
  // React's render and would otherwise close over the indices as they were
  // at pointerdown.
  const from = useRef<number | null>(null);
  const to = useRef<number | null>(null);
  /**
   * Where the rows were when the drag began.
   *
   * Hit-testing against where they are *now* cannot work once a list moves
   * its rows out of the way: the carried row follows the pointer, so it is
   * always the row under it and the target never changes; and the rows that
   * shifted leave a hole the pointer falls through. The layout at rest is the
   * one that answers "which place is the finger over", and it does not move,
   * so the answer is stable and the same going up as coming down.
   */
  const slots = useRef<{ index: number; top: number; bottom: number }[]>([]);

  function startDrag(index: number, event: React.PointerEvent) {
    // Left button only; a right-click on the handle should open a menu.
    if (event.button !== 0) return;
    event.preventDefault();
    from.current = index;
    to.current = index;
    startY.current = event.clientY;
    slots.current = [...(listRef.current?.querySelectorAll<HTMLElement>(rowSelector) ?? [])].map(
      (row) => {
        const box = row.getBoundingClientRect();
        return { index: Number(row.dataset.reorderIndex), top: box.top, bottom: box.bottom };
      },
    );
    setDragging(index);
    setOver(index);
    setOffset(0);

    const onMove = (moved: PointerEvent) => {
      setOffset(moved.clientY - startY.current);
      for (const slot of slots.current) {
        if (moved.clientY >= slot.top && moved.clientY <= slot.bottom) {
          to.current = slot.index;
          setOver(slot.index);
          return;
        }
      }
      // Past either end of the list, the nearest end is what was meant.
      const first = slots.current[0];
      const last = slots.current[slots.current.length - 1];
      if (first && moved.clientY < first.top) {
        to.current = first.index;
        setOver(first.index);
      } else if (last && moved.clientY > last.bottom) {
        to.current = last.index;
        setOver(last.index);
      }
    };

    const onUp = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onUp);
      if (from.current !== null && to.current !== null && from.current !== to.current) {
        move(from.current, to.current);
      }
      from.current = null;
      to.current = null;
      setDragging(null);
      setOver(null);
      setOffset(0);
    };

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onUp);
  }

  return { dragging, over, offset, listRef, startDrag };
}

/** Move one item within a list, in place. The one line both callers share. */
export function moveWithin<T>(list: T[], start: number, end: number): void {
  list.splice(end, 0, list.splice(start, 1)[0]!);
}
