/**
 * The page header, carrying the one thing to do next.
 *
 * It replaces a gradient banner that held a single word. Every screen states
 * where you are, what state the profile is in, and offers one primary action
 * -- which was the other thing missing: nothing on the old screen told anyone
 * what to do.
 */

import { Command, History, PanelLeftOpen, Redo2, Undo2, X } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { useShallow } from "zustand/react/shallow";

import { useStore } from "../lib/store";

/**
 * The history, as a list you can point at.
 *
 * Two buttons and a keyboard shortcut tell you that undo exists; they do not
 * tell you what it will undo, or how far back the thing you actually want is.
 * The panel names each step and lets you jump straight to one -- which is a
 * seek, not a one-way door: everything skipped over goes onto the redo stack
 * in order.
 */
function HistoryPanel() {
  const { past, future, revertTo, redo } = useStore(
    useShallow((s) => ({
      past: s.past,
      future: s.future,
      revertTo: s.revertTo,
      redo: s.redo,
    })),
  );
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  // A panel that only closes by pressing its own button is a panel people
  // leave open over the thing they were reading.
  useEffect(() => {
    if (!open) return;
    const onDown = (event: PointerEvent) => {
      if (!box.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("pointerdown", onDown);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("pointerdown", onDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const steps = [...past].reverse();

  return (
    <div ref={box} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-haspopup="dialog"
        className="btn btn-quiet px-1.5 py-1"
        title="Everything you have changed this session"
        aria-label="History"
      >
        <History size={15} />
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="History"
          className="card absolute right-0 top-full z-40 mt-1.5 w-72 p-0 shadow-overlay"
        >
          <div className="flex items-center justify-between border-b border-line px-3 py-2">
            <span className="text-xs font-semibold">History</span>
            <button
              type="button"
              className="btn btn-quiet px-1 py-0.5"
              onClick={() => setOpen(false)}
              aria-label="Close the history"
            >
              <X size={13} />
            </button>
          </div>

          <div className="max-h-72 overflow-y-auto p-1.5">
            {future.length > 0 && (
              <button
                type="button"
                onClick={redo}
                className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs text-muted transition-colors duration-150 hover:bg-sunken hover:text-ink"
              >
                <Redo2 size={12} className="shrink-0" />
                <span className="min-w-0 flex-1 truncate">
                  Redo: {future[0]!.label.toLowerCase()}
                </span>
                {future.length > 1 && (
                  <span className="shrink-0 text-2xs text-faint">+{future.length - 1}</span>
                )}
              </button>
            )}

            <div className="flex items-center gap-2 rounded bg-sunken px-2 py-1.5 text-xs font-medium">
              <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-accent" aria-hidden />
              Where you are now
            </div>

            {steps.length === 0 ? (
              <p className="px-2 py-3 text-xs text-muted">
                Nothing changed yet this session. Every edit lands here, and the last
                {" "}
                {HISTORY_SHOWN} stay.
              </p>
            ) : (
              steps.map((step, i) => (
                <button
                  key={`${step.at}-${i}`}
                  type="button"
                  // `steps` is reversed for reading, so the index into `past`
                  // counts back from the end.
                  onClick={() => {
                    revertTo(past.length - 1 - i);
                    setOpen(false);
                  }}
                  className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs transition-colors duration-150 hover:bg-sunken"
                  title="Go back to just before this"
                >
                  <Undo2 size={12} className="shrink-0 text-faint" />
                  <span className="min-w-0 flex-1 truncate text-muted">{step.label}</span>
                  <span className="shrink-0 text-2xs tabular-nums text-faint">
                    {step.at
                      ? new Date(step.at).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                        })
                      : ""}
                  </span>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/** Matches `HISTORY_LIMIT` in the store; said out loud so the panel can. */
const HISTORY_SHOWN = 50;

function SaveState() {
  const { dirty, saving, savedAt, autosave, setAutosave, undo, redo, canUndo, canRedo } =
    useStore(
      useShallow((s) => ({
        dirty: s.dirty,
        saving: s.saving,
        savedAt: s.savedAt,
        autosave: s.autosave,
        setAutosave: s.setAutosave,
        undo: s.undo,
        redo: s.redo,
        canUndo: s.past.length > 0,
        canRedo: s.future.length > 0,
      })),
    );

  const [tone, text] = saving
    ? ["bg-fair", "Saving"]
    : dirty
      ? ["bg-fair", autosave ? "Saving shortly" : "Unsaved changes"]
      : savedAt
        ? ["bg-good", `Saved ${savedAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`]
        : ["bg-line-strong", "Loaded from disk"];

  return (
    <div className="flex items-center gap-2">
      <span className="flex items-center gap-1.5 text-xs text-muted" aria-live="polite">
        <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${tone}`} />
        <span className="hidden sm:inline">{text}</span>
      </span>

      <button
        type="button"
        onClick={undo}
        disabled={!canUndo}
        className="btn btn-quiet px-1.5 py-1 disabled:opacity-40"
        title="Undo the last change (Ctrl+Z)"
        aria-label="Undo the last change"
      >
        <Undo2 size={15} />
      </button>

      <button
        type="button"
        onClick={redo}
        disabled={!canRedo}
        className="btn btn-quiet px-1.5 py-1 disabled:opacity-40"
        title="Redo (Ctrl+Shift+Z)"
        aria-label="Redo the last undone change"
      >
        <Redo2 size={15} />
      </button>

      <HistoryPanel />

      <button
        type="button"
        role="switch"
        aria-checked={autosave}
        onClick={() => setAutosave(!autosave)}
        className="btn btn-quiet gap-1.5 px-2 py-1 text-xs"
        title={
          autosave
            ? "Autosave is on: changes are written a moment after you stop typing."
            : "Autosave is off: use Ctrl+S or the Save button."
        }
      >
        {/* Full track height, flush at the end, and the track kept short --
            the same proportion as the switches in the design panel, which is
            the point: two switches in one app that are shaped differently
            read as two different controls. */}
        <span
          aria-hidden
          className={[
            "relative h-3.5 w-5 rounded-full transition-colors duration-150 ease-out",
            autosave ? "bg-accent" : "bg-line-strong",
          ].join(" ")}
        >
          <span
            className="absolute top-0 h-3.5 w-3.5 rounded-full bg-paper shadow-subtle ring-1 ring-black/10 transition-[left] duration-150 ease-out"
            style={{ left: autosave ? 20 - 14 : 0 }}
          />
        </span>
        <span className="hidden md:inline">Autosave</span>
      </button>
    </div>
  );
}

interface Props {
  title: string;
  subtitle?: ReactNode;
  action?: ReactNode;
  /**
   * A second row inside the sticky header -- the profile's section tabs.
   *
   * It lives here rather than sticking itself to a hand-measured offset below
   * the header. The offset was 57px, and adding one control to the row above
   * made the header taller than that, which slid the tabs underneath it. A
   * nested element cannot go out of step with a height it is part of.
   */
  below?: ReactNode;
  sidebarHidden: boolean;
  onShowSidebar: () => void;
  onOpenPalette: () => void;
}

export function TopBar({
  title,
  subtitle,
  action,
  below,
  sidebarHidden,
  onShowSidebar,
  onOpenPalette,
}: Props) {
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-bg/85 backdrop-blur">
      <div className="flex items-center gap-2 px-4 py-3 sm:gap-4 sm:px-6">
        {sidebarHidden && (
          <button
            type="button"
            className="btn btn-quiet shrink-0 px-1.5 py-1"
            onClick={onShowSidebar}
            aria-label="Show the sidebar"
          >
            <PanelLeftOpen size={16} />
          </button>
        )}

        <div className="min-w-0 flex-1">
          <h1 className="truncate font-display text-xl leading-tight">{title}</h1>
          {subtitle && <div className="mt-0.5 truncate text-xs text-muted">{subtitle}</div>}
        </div>

        <div className="flex shrink-0 items-center gap-2 sm:gap-3">
          <SaveState />
          {/* Hidden where it cannot be used. The chip advertises a keyboard
              shortcut, and a narrow screen is usually a screen with no
              keyboard -- so on one it is pure width, taken from the title and
              the primary action, which is what pushed both off the edge. */}
          <button
            type="button"
            onClick={onOpenPalette}
            className="btn btn-quiet hidden gap-1.5 text-xs md:inline-flex"
            title="Command palette"
          >
            <Command size={14} />
            <kbd className="font-mono text-2xs">K</kbd>
          </button>
          {action}
        </div>
      </div>
      {below}
    </header>
  );
}
