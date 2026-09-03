/**
 * The page header, carrying the one thing to do next.
 *
 * It replaces a gradient banner that held a single word. Every screen states
 * where you are, what state the profile is in, and offers one primary action
 * -- which was the other thing missing: nothing on the old screen told anyone
 * what to do.
 */

import { Command, PanelLeftOpen, Undo2 } from "lucide-react";
import type { ReactNode } from "react";

import { useShallow } from "zustand/react/shallow";

import { useStore } from "../lib/store";

function SaveState() {
  const { dirty, saving, savedAt, autosave, setAutosave, undo, canUndo } = useStore(
    useShallow((s) => ({
      dirty: s.dirty,
      saving: s.saving,
      savedAt: s.savedAt,
      autosave: s.autosave,
      setAutosave: s.setAutosave,
      undo: s.undo,
      canUndo: s.past.length > 0,
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
        {/* The knob is the full height of the track and finishes flush with
            its end, the same geometry as the switches in the design panel.
            A 10px knob inset 2px in a 24px track stopped 2px short, and two
            pixels of accent past the knob read as a gap -- the switch looked
            half thrown while it was fully on. */}
        <span
          aria-hidden
          className={[
            "relative h-3.5 w-6 rounded-full transition-colors duration-150 ease-out",
            autosave ? "bg-accent" : "bg-line-strong",
          ].join(" ")}
        >
          <span
            className="absolute top-0 h-3.5 w-3.5 rounded-full bg-paper shadow-subtle ring-1 ring-black/10 transition-[left] duration-150 ease-out"
            style={{ left: autosave ? 24 - 14 : 0 }}
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
