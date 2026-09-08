/**
 * A row of choices with the highlight sliding between them.
 *
 * This started as one control -- the type-size stepper -- where the point was
 * that five numbers four percent apart give no reading of which way you moved
 * if the highlight simply appears under the one you pressed. Sliding it says
 * *which direction* and *how far*, which is the whole information the control
 * carries.
 *
 * That argument is not specific to numbers, so the behaviour is here rather
 * than in one screen, and the template filter and the health-check severity
 * filter use it too.
 *
 * **Why the highlight is measured rather than computed.** The first version
 * translated by `index * 100%`, which is exact only when every slot is the
 * same width. "All / ATS-safe / Two columns" are not, so the highlight is
 * given the active button's real `offsetLeft` and `offsetWidth`. That also
 * fixes the thing equal slots were quietly doing wrong: forcing five slots to
 * share a 147px bar left each one 28.6px to hold a label that needs 29, so
 * the digits sat a hair outside their own pill. Measured slots take the width
 * the text asks for.
 *
 * One element moves and resizes; the buttons only change colour. So there is
 * one thing for the browser to animate however many choices there are.
 */

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

export interface Choice {
  key: string;
  /** What the button says. */
  label: React.ReactNode;
  /** Optional `title`, for a choice whose label is too short to explain itself. */
  hint?: string;
}

/** The container's padding, in px: `p-0.5`. The highlight insets by the same. */
const PAD = 2;

export function Segmented({
  choices,
  value,
  onChange,
  ariaLabel,
  className = "",
  fill = false,
}: {
  choices: Choice[];
  value: string;
  onChange: (key: string) => void;
  ariaLabel?: string;
  className?: string;
  /**
   * Share the bar out equally instead of letting each slot take the width
   * its text asks for. Right for a stepper, where the slots are a scale and
   * uneven ones would misreport the distance between two settings; wrong for
   * a filter, where "All" and "Two columns" are not equal amounts of word.
   */
  fill?: boolean;
}) {
  const listRef = useRef<HTMLDivElement>(null);
  const [box, setBox] = useState<{ x: number; w: number } | null>(null);
  // The first measurement must not animate: a highlight that slides in from
  // the left edge on every mount reads as the control resetting itself.
  const settled = useRef(false);

  const measure = useCallback(() => {
    const list = listRef.current;
    const active = list?.querySelector<HTMLElement>('[data-seg="on"]');
    if (!list || !active) {
      setBox((was) => (was === null ? was : null));
      return;
    }
    const next = { x: active.offsetLeft, w: active.offsetWidth };
    // Only when it actually moved. The observer below watches the buttons,
    // and one of the things that resizes them is this component rendering --
    // so a new object every time would be a render on every observed frame,
    // and, since the highlight is a sibling of what is observed, a loop.
    setBox((was) => (was && was.x === next.x && was.w === next.w ? was : next));
  }, []);

  useLayoutEffect(() => {
    measure();
  }, [measure, value, choices]);

  useEffect(() => {
    const list = listRef.current;
    if (!list) return;
    // The bar is inside a panel that collapses and a page that resizes, and
    // the slot widths follow the text -- so they change when the web font
    // arrives, several hundred milliseconds after the first paint.
    const observer = new ResizeObserver(measure);
    observer.observe(list);
    for (const child of list.children) {
      // Not the highlight itself, which is the one thing here whose size this
      // component sets rather than reads.
      if (child instanceof HTMLElement && child.dataset.seg) observer.observe(child);
    }
    document.fonts?.ready.then(measure).catch(() => {});
    return () => observer.disconnect();
  }, [measure, choices]);

  useEffect(() => {
    // One frame after the first real measurement, motion is allowed.
    if (box && !settled.current) {
      const id = requestAnimationFrame(() => {
        settled.current = true;
      });
      return () => cancelAnimationFrame(id);
    }
    return undefined;
  }, [box]);

  return (
    <div
      ref={listRef}
      role="group"
      aria-label={ariaLabel}
      // `w-fit` unless the slots are sharing the bar out. A block-level flex
      // container takes the whole line, and with slots sized to their own
      // text that left "All / ATS-safe / Two columns" sitting in a tray of
      // empty grey running to the edge of the panel -- the bar looked like a
      // control with three more choices that had failed to load.
      className={`relative flex rounded-md bg-sunken p-0.5 ${fill ? "" : "w-fit max-w-full"} ${className}`}
    >
      {box && (
        <span
          aria-hidden
          className="absolute left-0 rounded bg-surface shadow-subtle"
          style={{
            top: PAD,
            bottom: PAD,
            width: box.w,
            transform: `translateX(${box.x}px)`,
            transition: settled.current
              ? "transform 260ms cubic-bezier(.22,.61,.36,1), width 260ms cubic-bezier(.22,.61,.36,1)"
              : "none",
          }}
        />
      )}
      {choices.map((choice) => {
        const on = choice.key === value;
        return (
          <button
            key={choice.key}
            type="button"
            data-seg={on ? "on" : "off"}
            title={choice.hint}
            onClick={() => onChange(choice.key)}
            aria-pressed={on}
            className={[
              // `min-w-0` so a narrow panel shrinks the slots instead of
              // letting them push their text out through the ends of the bar.
              "relative z-10 min-w-0 rounded px-2 py-1 text-2xs font-medium",
              "transition-colors duration-150",
              fill ? "flex-1" : "",
              on ? "text-ink" : "text-muted hover:text-ink",
            ].join(" ")}
          >
            {choice.label}
          </button>
        );
      })}
    </div>
  );
}
