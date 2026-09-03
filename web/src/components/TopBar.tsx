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
        <span
          aria-hidden
          className={[
            "relative h-3.5 w-6 rounded-full transition-colors duration-150 ease-out",
            autosave ? "bg-accent" : "bg-line-strong",
          ].join(" ")}
        >
          <span
            className={[
              "absolute top-0.5 h-2.5 w-2.5 rounded-full bg-paper transition-all duration-150 ease-out",
              autosave ? "left-3" : "left-0.5",
            ].join(" ")}
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
      <div className="flex items-center gap-4 px-6 py-3">
        {sidebarHidden && (
          <button type="button" className="btn btn-quiet px-1.5 py-1" onClick={onShowSidebar}>
            <PanelLeftOpen size={16} />
          </button>
        )}

        <div className="min-w-0">
          <h1 className="truncate font-display text-xl leading-tight">{title}</h1>
          {subtitle && <div className="mt-0.5 truncate text-xs text-muted">{subtitle}</div>}
        </div>

        <div className="ml-auto flex items-center gap-3">
          <SaveState />
          <button
            type="button"
            onClick={onOpenPalette}
            className="btn btn-quiet gap-1.5 text-xs"
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
