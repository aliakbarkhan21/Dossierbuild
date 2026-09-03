/**
 * The shell: navigation on the left, one screen on the right, and the two
 * things that belong to the whole app -- toasts and the command palette.
 *
 * Routing is real routing. Each screen has a URL, the back button works, and
 * the section you were editing survives a refresh.
 */

import { createContext, useContext, useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";

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

/**
 * Where the sidebar stops being a column and becomes a drawer.
 *
 * Below this it was taking 232px of a 420px screen, which pushed the page
 * title and the primary action off the right-hand edge -- the sidebar was
 * still there, but nothing else was. There is no hand-measured offset here:
 * the number is the width at which the two-column layout stops fitting, not a
 * measurement of anything inside it.
 */
const DRAWER_BELOW = 1024;

/** The sidebar's width, in one place: the spacer and the slide must agree. */
const SIDEBAR_W = 232;

function useNarrow(): boolean {
  const [narrow, setNarrow] = useState(
    () => typeof window !== "undefined" && window.innerWidth < DRAWER_BELOW,
  );
  useEffect(() => {
    const query = window.matchMedia(`(max-width: ${DRAWER_BELOW - 1}px)`);
    const update = () => setNarrow(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return narrow;
}

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
  const narrow = useNarrow();
  const [collapsed, setCollapsed] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const { open, setOpen } = useCommandPalette();

  // Two different states behind one idea. On a wide screen the sidebar is a
  // column the user may collapse; on a narrow one it is a drawer that is shut
  // until asked for. Keeping them separate is what lets a phone-sized window
  // stop being a drawer, and go back to the column the user had, on rotate.
  const sidebarHidden = narrow ? !drawerOpen : collapsed;

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

  // A drawer that stayed open over the page you just navigated to would have
  // to be dismissed by hand every single time.
  const location = useLocation();
  useEffect(() => setDrawerOpen(false), [location.pathname]);

  useEffect(() => {
    if (!narrow || !drawerOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setDrawerOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [narrow, drawerOpen]);

  const shell: Shell = {
    sidebarHidden,
    showSidebar: () => (narrow ? setDrawerOpen(true) : setCollapsed(false)),
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
      <div className="relative flex h-screen overflow-hidden">
        {/* Both forms stay mounted whether they are showing or not. An
            element removed from the tree on close has nothing left to
            animate -- it is simply gone on the next frame -- so the panel
            would slide open and then vanish. `inert` is what keeps a hidden
            panel out of the tab order and away from a screen reader; it is
            not decoration, it is the price of leaving it mounted. */}
        {narrow ? (
          // Over the page rather than beside it. A 232px column on a phone
          // leaves no room for the thing the column is for navigating to.
          <>
            <div
              className={[
                "fixed inset-0 z-30 bg-black/40 backdrop-blur-[1px] transition-opacity duration-200 ease-out",
                drawerOpen ? "opacity-100" : "pointer-events-none opacity-0",
              ].join(" ")}
              onClick={() => setDrawerOpen(false)}
              aria-hidden
            />
            <div
              inert={!drawerOpen}
              className={[
                "fixed inset-y-0 left-0 z-40 shadow-raised transition-transform duration-200 ease-out",
                drawerOpen ? "translate-x-0" : "-translate-x-full",
              ].join(" ")}
            >
              <Sidebar onCollapse={() => setDrawerOpen(false)} />
            </div>
          </>
        ) : (
          // Two elements, and only one of them animates.
          //
          // The spacer is what the page layout follows, and its width changes
          // in a single step -- no transition. Transitioning it instead cost a
          // layout of every document on the page on every frame, and the
          // Resume screen holds ten of them: the app, the preview, and eight
          // template thumbnails. That is what made a 200ms slide stutter.
          //
          // The panel is taken out of the flow and moved with a transform,
          // which the compositor does without laying anything out at all. The
          // single width step is invisible: on the way out the panel is still
          // covering the ground the content grows into, and on the way in the
          // gap opens first and the panel arrives to fill it.
          <>
            <div className="shrink-0" style={{ width: collapsed ? 0 : SIDEBAR_W }} aria-hidden />
            <div
              inert={collapsed}
              className="absolute inset-y-0 left-0 z-30 transition-transform duration-200 ease-out"
              style={{ transform: collapsed ? `translateX(-${SIDEBAR_W}px)` : "none" }}
            >
              <Sidebar onCollapse={() => setCollapsed(true)} />
            </div>
          </>
        )}
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
