/**
 * The shell: navigation on the left, one screen on the right, and the two
 * things that belong to the whole app -- toasts and the command palette.
 *
 * Routing is real routing. Each screen has a URL, the back button works, and
 * the section you were editing survives a refresh.
 */

import { createContext, useContext, useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { CommandPalette, useCommandPalette } from "./components/CommandPalette";
import { Sidebar } from "./components/Sidebar";
import { Toaster } from "./components/Toaster";
import { startHeartbeat } from "./lib/heartbeat";
import { useStore } from "./lib/store";
import { HealthScreen } from "./routes/Health";
import { ImportScreen } from "./routes/Import";
import { ProfileScreen } from "./routes/Profile";
import { ResumeScreen } from "./routes/Resume";
import { TailorScreen } from "./routes/Tailor";

interface Shell {
  sidebarHidden: boolean;
  showSidebar: () => void;
  openPalette: () => void;
}

const ShellContext = createContext<Shell>({
  sidebarHidden: false,
  showSidebar: () => undefined,
  openPalette: () => undefined,
});

export const useShell = () => useContext(ShellContext);

/** Whether a keystroke is being typed into something that owns its own undo. */
function isTyping(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  if (!el) return false;
  return (
    el.tagName === "INPUT" ||
    el.tagName === "TEXTAREA" ||
    el.tagName === "SELECT" ||
    el.isContentEditable
  );
}

export default function App() {
  const boot = useStore((s) => s.boot);
  const save = useStore((s) => s.save);
  const undo = useStore((s) => s.undo);
  const ready = useStore((s) => s.ready);
  const bootError = useStore((s) => s.bootError);
  const [sidebarHidden, setSidebarHidden] = useState(false);
  const { open, setOpen } = useCommandPalette();

  useEffect(() => {
    void boot();
  }, [boot]);

  // What lets closing the tab close the app. See lib/heartbeat.ts.
  useEffect(() => startHeartbeat(), []);

  // Ctrl/Cmd+S saves from anywhere, including from inside a text field, which
  // is exactly where someone's hands are when they think to save.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (!(event.metaKey || event.ctrlKey)) return;
      const key = event.key.toLowerCase();

      if (key === "s") {
        event.preventDefault();
        void save();
        return;
      }

      // Ctrl+Z inside a field belongs to the field. Taking it would mean a
      // mistyped word could only be fixed by reverting the whole edit, which
      // is worse than the browser behaviour it replaced.
      if (key === "z" && !event.shiftKey && !isTyping(event.target)) {
        event.preventDefault();
        undo();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [save, undo]);

  // Autosave waits for a pause in typing, so closing the tab mid-sentence can
  // still outrun it.
  useEffect(() => {
    function onLeave(event: BeforeUnloadEvent) {
      if (useStore.getState().dirty) event.preventDefault();
    }
    window.addEventListener("beforeunload", onLeave);
    return () => window.removeEventListener("beforeunload", onLeave);
  }, []);

  const shell: Shell = {
    sidebarHidden,
    showSidebar: () => setSidebarHidden(false),
    openPalette: () => setOpen(true),
  };

  if (bootError) {
    return (
      <main className="grid min-h-screen place-items-center p-8">
        <div className="card max-w-md p-6 text-center">
          <h1 className="font-display text-xl">Dossierbuild cannot reach its server</h1>
          <p className="mt-2 text-sm text-muted">{bootError}</p>
          <button type="button" className="btn btn-primary mt-4" onClick={() => void boot()}>
            Try again
          </button>
        </div>
      </main>
    );
  }

  return (
    <ShellContext.Provider value={shell}>
      <div className="flex h-screen overflow-hidden">
        {!sidebarHidden && <Sidebar onCollapse={() => setSidebarHidden(true)} />}
        <main className="flex min-w-0 flex-1 flex-col overflow-y-auto">
          {ready ? (
            <Routes>
              <Route path="/" element={<Navigate to="/profile" replace />} />
              <Route path="/profile" element={<ProfileScreen />} />
              <Route path="/resume" element={<ResumeScreen />} />
              <Route path="/tailor" element={<TailorScreen />} />
              <Route path="/import" element={<ImportScreen />} />
              <Route path="/health" element={<HealthScreen />} />
              <Route path="*" element={<Navigate to="/profile" replace />} />
            </Routes>
          ) : (
            <BootSkeleton />
          )}
        </main>
      </div>
      <CommandPalette open={open} onClose={() => setOpen(false)} />
      <Toaster />
    </ShellContext.Provider>
  );
}

/**
 * A skeleton rather than a spinner: it holds the shape the content will take,
 * so the page does not jump when the data lands.
 */
function BootSkeleton() {
  return (
    <div className="animate-pulse p-6">
      <div className="h-7 w-56 rounded-md bg-sunken" />
      <div className="mt-6 grid gap-4 md:grid-cols-2">
        <div className="h-40 rounded-lg bg-sunken" />
        <div className="h-40 rounded-lg bg-sunken" />
      </div>
    </div>
  );
}
