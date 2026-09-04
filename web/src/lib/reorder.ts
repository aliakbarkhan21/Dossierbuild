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
  const listRef = useRef<HTMLDivElement>(null);
  // The live values the pointer handlers read. State drives the rendering;
  // these exist because the handler that commits the move runs outside
  // React's render and would otherwise close over the indices as they were
  // at pointerdown.
  const from = useRef<number | null>(null);
  const to = useRef<number | null>(null);

  function startDrag(index: number, event: React.PointerEvent) {
    // Left button only; a right-click on the handle should open a menu.
    if (event.button !== 0) return;
    event.preventDefault();
    from.current = index;
    to.current = index;
    setDragging(index);
    setOver(index);

    const onMove = (moved: PointerEvent) => {
      const rows = listRef.current?.querySelectorAll<HTMLElement>(rowSelector);
      if (!rows) return;
      for (const row of rows) {
        const box = row.getBoundingClientRect();
        if (moved.clientY >= box.top && moved.clientY <= box.bottom) {
          const hit = Number(row.dataset.reorderIndex);
          to.current = hit;
          setOver(hit);
          return;
        }
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
    };

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onUp);
  }

  return { dragging, over, listRef, startDrag };
}

/** Move one item within a list, in place. The one line both callers share. */
export function moveWithin<T>(list: T[], start: number, end: number): void {
  list.splice(end, 0, list.splice(start, 1)[0]!);
}
