/**
 * Choose which part of a photograph becomes the portrait, before it is saved.
 *
 * Without this the server decided: it cropped to a square centred
 * horizontally and weighted a little above the middle, which is right for a
 * head-and-shoulders shot taken straight on and wrong for everything else.
 * A photo taken at arm's length, or one where the person stands to the left,
 * came out cropped through the ear with no way to say otherwise except
 * cropping it somewhere else first and uploading again.
 *
 * The preview and the file are the same crop, not two implementations of the
 * same idea. `place` below returns the one transform, in units of the crop
 * square's own side, and both the CSS on screen and the canvas that writes
 * the JPEG are built from it -- so what the frame shows is what gets saved,
 * the way the resume preview is the print.
 */

import { RotateCcw, RotateCw, X } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";

/** What the server stores. Exporting at the same size avoids a second resample. */
const OUT_PX = 512;
/** The window on screen, at most. On a narrow phone it is whatever fits.
 *
 * The window is bigger than the crop on purpose: the part of the photograph
 * that will be cut off is dimmed rather than hidden, so it is clear what is
 * being left out and which way to drag. */
const VIEW_MAX_PX = 360;
/** The crop as a share of the window, so the square stays square at any size.
 *
 * Both of these are ratios rather than pixel constants because the window is
 * allowed to shrink: a fixed 36px inset inside a window that had narrowed to
 * 356px and stayed 360px tall drew a *rectangle* and called it the crop, which
 * is the one thing this dialog may not do. The rendered width is measured, and
 * every number below comes off it. */
const CROP_RATIO = 0.8;
const MARGIN_PERCENT = `${((1 - CROP_RATIO) / 2) * 100}%`;
const ZOOM_MIN = 1;
const ZOOM_MAX = 4;

interface Placement {
  /** Frame centre to image centre, in pixels of whatever square it is drawn at. */
  x: number;
  y: number;
  radians: number;
  /** Image pixels to square pixels. */
  k: number;
}

/**
 * The crop, for a square of `side` pixels.
 *
 * `zoom` of 1 means the image's shorter side exactly fills the square, so
 * zoom is a real minimum: there is no way to drag a gap in at the edge.
 */
function place(
  image: { width: number; height: number },
  view: { zoom: number; degrees: number; x: number; y: number },
  side: number,
): Placement {
  const cover = side / Math.min(image.width, image.height);
  return {
    x: view.x * side,
    y: view.y * side,
    radians: (view.degrees * Math.PI) / 180,
    k: cover * view.zoom,
  };
}

export function PhotoCropper({
  file,
  busy,
  onCancel,
  onSave,
}: {
  file: File;
  busy: boolean;
  onCancel: () => void;
  onSave: (cropped: Blob) => void;
}) {
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  const [error, setError] = useState("");
  const [zoom, setZoom] = useState(1);
  const [degrees, setDegrees] = useState(0);
  // Held as a fraction of the crop square, so one pair of numbers describes
  // the same crop at whatever size it is drawn and at 512px in the file.
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const drag = useRef<{ x: number; y: number; ox: number; oy: number } | null>(null);

  // The crop square's side as actually rendered. Offsets are fractions of it,
  // so a window that resizes mid-crop moves nothing.
  const view = useRef<HTMLDivElement>(null);
  const [cropPx, setCropPx] = useState(VIEW_MAX_PX * CROP_RATIO);
  useLayoutEffect(() => {
    const el = view.current;
    if (!el) return;
    const measure = () => setCropPx(el.clientWidth * CROP_RATIO);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, [image]);

  useEffect(() => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    // The same element is measured for the preview and drawn to the export
    // canvas, so whatever the browser does with the EXIF orientation it does
    // to both. Reading the orientation ourselves would be a second opinion.
    img.onload = () => setImage(img);
    img.onerror = () => setError("That file could not be read as an image.");
    img.src = url;
    return () => URL.revokeObjectURL(url);
  }, [file]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel]);

  function startDrag(event: React.PointerEvent) {
    (event.target as Element).setPointerCapture(event.pointerId);
    drag.current = { x: event.clientX, y: event.clientY, ox: offset.x, oy: offset.y };
  }

  function moveDrag(event: React.PointerEvent) {
    const from = drag.current;
    if (!from) return;
    setOffset({
      x: from.ox + (event.clientX - from.x) / cropPx,
      y: from.oy + (event.clientY - from.y) / cropPx,
    });
  }

  function save() {
    if (!image) return;
    const canvas = document.createElement("canvas");
    canvas.width = OUT_PX;
    canvas.height = OUT_PX;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    // A photograph rotated off-square leaves the corners empty. White rather
    // than transparent, because the file is a JPEG and every layout that
    // carries a portrait sits it on paper.
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, OUT_PX, OUT_PX);
    ctx.imageSmoothingQuality = "high";

    const at = place(image, { zoom, degrees, ...offset }, OUT_PX);
    ctx.translate(OUT_PX / 2 + at.x, OUT_PX / 2 + at.y);
    ctx.rotate(at.radians);
    ctx.scale(at.k, at.k);
    ctx.drawImage(image, -image.width / 2, -image.height / 2);

    canvas.toBlob(
      (blob) => {
        if (blob) onSave(blob);
        else setError("The crop could not be saved. Try a different image.");
      },
      "image/jpeg",
      0.92,
    );
  }

  const at = image ? place(image, { zoom, degrees, ...offset }, cropPx) : null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Adjust your photo"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 p-4 backdrop-blur-[1px]"
      onPointerDown={(event) => {
        if (event.target === event.currentTarget) onCancel();
      }}
    >
      <div className="card w-full max-w-md overflow-hidden p-0">
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <h2 className="font-display text-base font-semibold">Adjust your photo</h2>
          <button
            type="button"
            className="btn btn-quiet px-1.5 py-1"
            onClick={onCancel}
            aria-label="Cancel"
          >
            <X size={15} />
          </button>
        </div>

        <div className="p-4">
          {error ? (
            <p className="py-8 text-center text-sm text-poor">{error}</p>
          ) : (
            <>
              <div
                ref={view}
                className="relative mx-auto touch-none select-none overflow-hidden rounded-lg bg-sunken"
                style={{ width: `min(${VIEW_MAX_PX}px, 100%)`, aspectRatio: "1" }}
                onPointerDown={startDrag}
                onPointerMove={moveDrag}
                onPointerUp={() => (drag.current = null)}
                onPointerCancel={() => (drag.current = null)}
              >
                {image && at && (
                  <img
                    src={image.src}
                    alt=""
                    draggable={false}
                    className="absolute left-1/2 top-1/2 max-w-none cursor-grab active:cursor-grabbing"
                    style={{
                      width: image.width,
                      height: image.height,
                      // Read outward-in, this is the canvas sequence above:
                      // move to the frame centre plus the drag, turn, scale,
                      // then draw the image about its own middle.
                      transformOrigin: "0 0",
                      transform:
                        `translate(${at.x}px, ${at.y}px) ` +
                        `rotate(${degrees}deg) scale(${at.k}) ` +
                        `translate(${-image.width / 2}px, ${-image.height / 2}px)`,
                    }}
                  />
                )}
                {/* The square is the crop. Everything the resume will not keep
                    is dimmed rather than hidden, so it is clear what is being
                    left out and which way to drag. */}
                <div
                  aria-hidden
                  className="pointer-events-none absolute rounded-sm border-2 border-white/90"
                  style={{ inset: MARGIN_PERCENT, boxShadow: "0 0 0 9999px rgba(0,0,0,.45)" }}
                />
              </div>

              <p className="mt-2 text-center text-xs text-muted">
                Drag the photo to move it. The square is what prints.
              </p>

              <label className="label mt-3 block" htmlFor="crop-zoom">
                Zoom
              </label>
              <input
                id="crop-zoom"
                type="range"
                className="zoom w-full"
                min={ZOOM_MIN}
                max={ZOOM_MAX}
                step={0.01}
                value={zoom}
                onChange={(event) => setZoom(Number(event.target.value))}
              />

              <div className="mt-3 flex items-center gap-3">
                <label className="label mb-0 shrink-0" htmlFor="crop-rotate">
                  Rotate
                </label>
                <input
                  id="crop-rotate"
                  type="range"
                  className="zoom min-w-0 flex-1"
                  min={-180}
                  max={180}
                  step={1}
                  value={degrees}
                  onChange={(event) => setDegrees(Number(event.target.value))}
                />
                {/* A phone that saved a photo on its side needs one press, not
                    a slider dragged to exactly ninety. */}
                <button
                  type="button"
                  className="btn btn-quiet px-1.5 py-1"
                  onClick={() => setDegrees((d) => ((d - 90 + 540) % 360) - 180)}
                  aria-label="Turn a quarter left"
                  title="Turn a quarter left"
                >
                  <RotateCcw size={14} />
                </button>
                <button
                  type="button"
                  className="btn btn-quiet px-1.5 py-1"
                  onClick={() => setDegrees((d) => ((d + 90 + 540) % 360) - 180)}
                  aria-label="Turn a quarter right"
                  title="Turn a quarter right"
                >
                  <RotateCw size={14} />
                </button>
              </div>
            </>
          )}
        </div>

        <div className="flex items-center gap-2 border-t border-line px-4 py-3">
          <button
            type="button"
            className="btn btn-primary"
            onClick={save}
            disabled={!image || busy || Boolean(error)}
          >
            Use this photo
          </button>
          <button
            type="button"
            className="btn"
            onClick={() => {
              setZoom(1);
              setDegrees(0);
              setOffset({ x: 0, y: 0 });
            }}
            disabled={!image}
          >
            Reset
          </button>
          <button type="button" className="btn ml-auto" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
