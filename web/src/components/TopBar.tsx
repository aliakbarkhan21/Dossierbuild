/**
 * The page header, carrying the one thing to do next.
 *
 * It replaces a gradient banner that held a single word. Every screen states
 * where you are, what state the profile is in, and offers one primary action
 * -- which was the other thing missing: nothing on the old screen told anyone
 * what to do.
 */

import { Command, PanelLeftOpen } from "lucide-react";
import type { ReactNode } from "react";

import { useShallow } from "zustand/react/shallow";

import { useStore } from "../lib/store";

function SaveState() {
  const { dirty, saving, savedAt } = useStore(useShallow((s) => ({
    dirty: s.dirty,
    saving: s.saving,
    savedAt: s.savedAt,
  })));

  const [tone, text] = saving
    ? ["bg-fair", "Saving"]
    : dirty
      ? ["bg-fair", "Unsaved changes"]
      : savedAt
        ? ["bg-good", `Saved ${savedAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`]
        : ["bg-line-strong", "Loaded from disk"];

  return (
    <span className="flex items-center gap-1.5 text-xs text-muted" aria-live="polite">
      <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${tone}`} />
      {text}
    </span>
  );
}

interface Props {
  title: string;
  subtitle?: ReactNode;
  action?: ReactNode;
  sidebarHidden: boolean;
  onShowSidebar: () => void;
  onOpenPalette: () => void;
}

export function TopBar({
  title,
  subtitle,
  action,
  sidebarHidden,
  onShowSidebar,
  onOpenPalette,
}: Props) {
  return (
    <header className="sticky top-0 z-20 flex items-center gap-4 border-b border-line bg-bg/85 px-6 py-3 backdrop-blur">
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
    </header>
  );
}
