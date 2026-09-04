/**
 * The one switch in the app, in two sizes.
 *
 * **The geometry, and why it changed twice.** The first version put a 14px
 * knob inset 2px in a 32px track: geometrically near the end, but the two
 * pixels of colour past the knob read as a gap, and it was reported as one.
 * The second answer was to make the knob the full height of the track and
 * flush at both ends -- 22px in 32px, no inset at all. That removed the gap
 * and introduced a worse problem: the travel was 10px, the knob covered
 * two-thirds of the track, and what the eye saw was not a knob sliding along
 * a track but a circle with a coloured crescent behind it. Because the
 * crescent is only conspicuous in the "on" state -- accent green against
 * white, where the "off" crescent is pale grey on a pale surface -- the two
 * ends did not even look symmetrical. The switch read as *stuck halfway when
 * on, and properly parked when off*, which is exactly how it was described.
 *
 * So: a knob a little under half the track's width, inset by a small even
 * margin, travelling most of the track's length. The conventional proportion,
 * for the conventional reason -- the distance the knob covers is the only
 * thing that says a switch has been thrown, and it has to be a distance you
 * can see. At `md` the knob now moves 18px rather than 10, and the field it
 * crosses is longer than the knob rather than half its size.
 *
 * `left` is animated rather than `transform` on purpose: the knob is one
 * small element with no children, the distance is under 20px, and `left`
 * keeps the shadow and the ring rendering identically at both ends, which a
 * composited layer promotion does not always do at fractional device pixels.
 */

const SIZES = {
  /** In the design panel, beside a full row of label. */
  md: { track: 40, height: 22, knob: 18 },
  /** In the top bar, beside 12px text. */
  sm: { track: 26, height: 15, knob: 11 },
} as const;

export function Switch({
  checked,
  size = "md",
  className = "",
}: {
  checked: boolean;
  size?: keyof typeof SIZES;
  className?: string;
}) {
  const { track, height, knob } = SIZES[size];
  // Centred vertically, so the same number is the margin at every edge and
  // the knob sits in the track rather than on it.
  const inset = (height - knob) / 2;

  return (
    <span
      aria-hidden
      className={[
        "relative inline-block shrink-0 rounded-full transition-colors duration-200 ease-out",
        checked ? "bg-accent" : "bg-line-strong",
        className,
      ].join(" ")}
      style={{ width: track, height }}
    >
      <span
        className="absolute rounded-full bg-white shadow-subtle ring-1 ring-black/10 transition-[left] duration-[280ms] ease-[cubic-bezier(.22,.61,.36,1)]"
        style={{
          width: knob,
          height: knob,
          top: inset,
          left: checked ? track - knob - inset : inset,
        }}
      />
    </span>
  );
}
