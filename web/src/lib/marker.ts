/**
 * One highlight that travels, for a row or a column of links.
 *
 * The alternative is what both of these did before: give every item its own
 * background and switch on the one that is active. That is a cut, and the eye
 * cannot follow a cut -- you are told which item is selected but not that
 * anything moved, so a seven-item nav gives no sense of where you were.
 *
 * Extracted when the profile's section tabs wanted what the sidebar had. Two
 * copies of a measuring hook is two sets of observers to get wrong, and the
 * only real difference between them is which axis the thing slides along.
 *
 * **Measured, not computed from an index.** Both callers have items of equal
 * size today -- nav rows, tab pills -- so arithmetic would work and would go
 * quietly wrong the first time a label wrapped or a count widened one pill.
 * Reading a box costs nothing at nine items.
 */

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

export interface MarkerBox {
  /** Offset along the axis, in px, from the container's padding box. */
  pos: number;
  /** Length along the axis, in px. */
  size: number;
  /** False when nothing is active: fade rather than fly to the origin. */
  shown: boolean;
}

export function useSlidingMarker<T extends HTMLElement>(
  /** Changes when the active item changes -- a route, a tab key. */
  key: string,
  /** Finds the active child inside the container. */
  activeSelector: string,
  axis: "x" | "y" = "y",
) {
  const listRef = useRef<T>(null);
  const [box, setBox] = useState<MarkerBox | null>(null);
  // The first placement must not animate. These containers remount -- the
  // sidebar every time the drawer opens on a narrow window -- and a highlight
  // flying in from the origin reads as the app choosing the page for you.
  const animate = useRef(false);

  const measure = useCallback(() => {
    const list = listRef.current;
    if (!list) return;
    const active = list.querySelector<HTMLElement>(activeSelector);
    setBox((was) => {
      // Nothing active: a route outside the set, or the instant before a
      // redirect. Hold the position and fade.
      if (!active) return was ? { ...was, shown: false } : null;
      const next =
        axis === "y"
          ? { pos: active.offsetTop, size: active.offsetHeight, shown: true }
          : { pos: active.offsetLeft, size: active.offsetWidth, shown: true };
      const same = was && was.pos === next.pos && was.size === next.size && was.shown;
      return same ? was : next;
    });
  }, [activeSelector, axis]);

  useLayoutEffect(() => {
    measure();
  }, [measure, key]);

  useEffect(() => {
    const list = listRef.current;
    if (!list) return;
    // An item is as big as its text, and the text is a web font that arrives
    // several hundred milliseconds after the first paint.
    const observer = new ResizeObserver(measure);
    observer.observe(list);
    for (const child of list.children) observer.observe(child);
    document.fonts?.ready.then(measure).catch(() => {});
    return () => observer.disconnect();
  }, [measure]);

  useEffect(() => {
    if (box && !animate.current) {
      const id = requestAnimationFrame(() => {
        animate.current = true;
      });
      return () => cancelAnimationFrame(id);
    }
    return undefined;
  }, [box]);

  return { listRef, box, animate: animate.current };
}

/**
 * The inline style for the highlight itself.
 *
 * `transform` and `opacity` only. The size is set outright rather than
 * transitioned, because width and height are not compositor properties and a
 * single entry that cannot be composited drags the whole transition onto the
 * main thread -- where it stutters through whatever the page being navigated
 * to is doing. An item of a different size therefore resizes in one step
 * while it slides, which is the right thing to trade.
 */
export function markerStyle(box: MarkerBox, animate: boolean, axis: "x" | "y" = "y"): React.CSSProperties {
  return {
    [axis === "y" ? "top" : "left"]: 0,
    [axis === "y" ? "height" : "width"]: box.size,
    transform: axis === "y" ? `translateY(${box.pos}px)` : `translateX(${box.pos}px)`,
    opacity: box.shown ? 1 : 0,
    // The layer goes up before the first move rather than on it, so the first
    // navigation is as smooth as every one after it.
    willChange: "transform",
    transition: animate
      ? "transform 260ms cubic-bezier(.22,.61,.36,1), opacity 160ms ease-out"
      : "none",
  };
}

/** What an item's colour transition has to match, or the two read as two events. */
export const MARKER_COLOUR_CLASS =
  "transition-colors duration-[260ms] ease-[cubic-bezier(.22,.61,.36,1)]";
