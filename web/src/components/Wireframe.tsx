/**
 * The shape of a template, while Chromium is drawing the real thing.
 *
 * A pulsing grey rectangle tells you a thing is loading and nothing else. On
 * this screen there are eight of them at once, all identical, and the one
 * question the reader has — *which of these is the two-column one* — is
 * exactly what the placeholder could answer and did not.
 *
 * So each card draws its own silhouette: the header block where that template
 * puts it, and rules where its body columns are. It is not a preview and does
 * not pretend to be one, but it is the right shape, so the grid stops being
 * eight identical grey boxes and the card does not jump when the render
 * lands.
 *
 * Inline SVG rather than an image: a few hundred bytes, no request that could
 * fail, and it takes its colour from the card it is sitting in.
 */

/** How the eight templates arrange the top of the page and the body. */
type Shape = "centred" | "band" | "gutter" | "side" | "masthead" | "dense";

const SHAPES: Record<string, Shape> = {
  classic: "centred",
  modern: "band",
  minimal: "gutter",
  compact: "dense",
  executive: "centred",
  gazette: "masthead",
  sidebar: "side",
  editorial: "side",
};

export function Wireframe({ template }: { template: string }) {
  const shape = SHAPES[template] ?? "centred";

  return (
    <div className="flex h-full w-full items-start justify-center bg-white p-3">
      <svg
        viewBox="0 0 120 160"
        className="h-full w-auto animate-pulse"
        role="img"
        aria-label="Drawing the preview"
        // The paper stays white -- it is a sheet of paper either way -- and
        // only the marks are grey, so the card does not change colour when
        // the real render arrives.
        style={{ color: "var(--c-line-strong)" }}
      >
        <rect x="0" y="0" width="120" height="160" fill="#fff" />
        {header(shape)}
        {body(shape)}
      </svg>
    </div>
  );
}

const bar = (x: number, y: number, w: number, h = 3, opacity = 1) => (
  <rect key={`${x}-${y}-${w}`} x={x} y={y} width={w} height={h} rx={1} fill="currentColor" opacity={opacity} />
);

function header(shape: Shape) {
  if (shape === "band") {
    return (
      <g>
        <rect x="0" y="0" width="120" height="26" fill="currentColor" opacity={0.5} />
        {bar(8, 8, 46, 6, 0.25)}
        {bar(8, 18, 66, 2.5, 0.25)}
      </g>
    );
  }
  if (shape === "masthead") {
    return (
      <g>
        {bar(10, 8, 100, 8, 0.55)}
        <rect x="10" y="21" width="100" height="1.4" fill="currentColor" opacity={0.5} />
        {bar(28, 26, 64, 2.5, 0.3)}
      </g>
    );
  }
  if (shape === "side") {
    return (
      <g>
        <rect x="0" y="0" width="42" height="160" fill="currentColor" opacity={0.13} />
        <circle cx="21" cy="20" r="10" fill="currentColor" opacity={0.35} />
        {bar(8, 36, 26, 4, 0.45)}
      </g>
    );
  }
  if (shape === "dense") {
    return (
      <g>
        {bar(10, 7, 54, 5, 0.55)}
        {bar(10, 15, 92, 2, 0.3)}
      </g>
    );
  }
  // centred and gutter share a plain top; the gutter shows in the body.
  return (
    <g>
      {bar(shape === "gutter" ? 10 : 32, 8, shape === "gutter" ? 56 : 56, 7, 0.55)}
      {bar(shape === "gutter" ? 10 : 26, 19, 68, 2.5, 0.3)}
      {shape === "centred" && (
        <rect x="10" y="27" width="100" height="1.2" fill="currentColor" opacity={0.45} />
      )}
    </g>
  );
}

function body(shape: Shape) {
  const rows: React.ReactNode[] = [];
  const left = shape === "side" ? 48 : 10;
  const width = shape === "side" ? 62 : 100;
  const step = shape === "dense" ? 9 : 12;
  let y = shape === "band" ? 34 : shape === "masthead" ? 36 : 36;

  for (let section = 0; section < 4 && y < 150; section++) {
    if (shape === "gutter") {
      // The heading sits in a left gutter, which is the whole idea of it.
      rows.push(bar(10, y, 22, 3, 0.5));
      rows.push(bar(38, y, 72, 3, 0.28));
      rows.push(bar(38, y + 5, 62, 2.2, 0.2));
    } else {
      rows.push(bar(left, y, shape === "dense" ? 30 : 34, 3, 0.5));
      rows.push(bar(left, y + 5, width, 2.2, 0.22));
      rows.push(bar(left, y + 9, width - 16, 2.2, 0.22));
    }
    if (shape === "side") {
      // The side column carries its own short lines.
      rows.push(bar(8, y + 8, 26, 2, 0.3));
    }
    y += step + 4;
  }
  return <g>{rows}</g>;
}
