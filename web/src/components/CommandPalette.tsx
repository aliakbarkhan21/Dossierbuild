/**
 * Ctrl/Cmd+K.
 *
 * It is the app's keyboard surface, not a search box: navigation, the actions
 * that matter (save, build a PDF, switch theme), and -- once there is enough
 * written to be worth searching -- the bullets themselves. That last part is
 * why the orphaned search field on the old profile screen could be removed
 * rather than relocated.
 */

import { ArrowRight, Command as CommandIcon, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useStore } from "../lib/store";
import { cycleMode } from "../lib/theme";

export interface Action {
  id: string;
  label: string;
  hint?: string;
  group: string;
  run: () => void | Promise<void>;
}

export function useCommandPalette() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((value) => !value);
      }
      if (event.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return { open, setOpen };
}

export function CommandPalette({
  open,
  onClose,
  extra = [],
}: {
  open: boolean;
  onClose: () => void;
  extra?: Action[];
}) {
  const navigate = useNavigate();
  const save = useStore((s) => s.save);
  const profile = useStore((s) => s.profile);
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setQuery("");
      setCursor(0);
      // The frame delay lets the dialog mount before focus moves, which is
      // what stops the first keystroke going to the page behind it.
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  const actions = useMemo<Action[]>(() => {
    const base: Action[] = [
      { id: "go-profile", group: "Go to", label: "Profile", run: () => navigate("/profile") },
      { id: "go-resume", group: "Go to", label: "Resume", run: () => navigate("/resume") },
      { id: "go-tailor", group: "Go to", label: "Tailor for a job", run: () => navigate("/tailor") },
      {
        id: "go-applications",
        group: "Go to",
        label: "Applications",
        run: () => navigate("/applications"),
      },
      {
        id: "go-letter",
        group: "Go to",
        label: "Cover letter",
        run: () => navigate("/letter"),
      },
      { id: "go-import", group: "Go to", label: "Import", run: () => navigate("/import") },
      { id: "go-health", group: "Go to", label: "Review", run: () => navigate("/health") },
      { id: "save", group: "Do", label: "Save profile", hint: "Ctrl+S", run: () => void save() },
      {
        id: "theme",
        group: "Do",
        label: "Switch light / dark",
        run: () => {
          cycleMode();
        },
      },
      ...extra,
    ];

    // Bullets become searchable only once there are enough of them to be
    // worth searching -- below that the list is the profile itself.
    const bullets: Action[] = [];
    if (profile) {
      const collect = (owner: string, section: "experience" | "projects" | "education") => {
        for (const entry of profile[section]) {
          for (const bullet of entry.bullets) {
            if (!bullet.text.trim()) continue;
            bullets.push({
              id: `b-${bullet.id}`,
              group: owner,
              label: bullet.text,
              run: () => navigate(`/profile?section=${section}`),
            });
          }
        }
      };
      collect("Experience", "experience");
      collect("Projects", "projects");
      collect("Education", "education");
    }
    return bullets.length >= 6 ? [...base, ...bullets] : base;
  }, [navigate, save, profile, extra]);

  const matches = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return actions.filter((a) => !a.id.startsWith("b-"));
    return actions.filter((a) => a.label.toLowerCase().includes(needle)).slice(0, 12);
  }, [actions, query]);

  if (!open) return null;

  function choose(index: number) {
    const action = matches[index];
    if (!action) return;
    onClose();
    void action.run();
  }

  return (
    <div
      className="fixed inset-0 z-40 flex items-start justify-center bg-black/40 pt-[12vh] backdrop-blur-[2px]"
      onMouseDown={onClose}
      role="presentation"
      style={{ animation: "fade-in 150ms cubic-bezier(0.22,0.61,0.36,1)" }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        className="card w-[min(34rem,calc(100vw-2rem))] overflow-hidden p-0 shadow-overlay"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="flex items-center gap-2 border-b border-line px-3">
          <Search size={15} className="text-faint" />
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setCursor(0);
            }}
            onKeyDown={(event) => {
              if (event.key === "ArrowDown") {
                event.preventDefault();
                setCursor((c) => Math.min(c + 1, matches.length - 1));
              } else if (event.key === "ArrowUp") {
                event.preventDefault();
                setCursor((c) => Math.max(c - 1, 0));
              } else if (event.key === "Enter") {
                event.preventDefault();
                choose(cursor);
              }
            }}
            placeholder="Search actions, pages, and your own bullets"
            className="w-full bg-transparent py-3 text-sm outline-none placeholder:text-faint"
          />
          <kbd className="rounded border border-line px-1 font-mono text-2xs text-faint">esc</kbd>
        </div>

        <ul className="max-h-[52vh] overflow-y-auto p-1.5">
          {matches.length === 0 && (
            <li className="px-3 py-6 text-center text-sm text-muted">Nothing matches that.</li>
          )}
          {matches.map((action, index) => (
            <li key={action.id}>
              <button
                type="button"
                onMouseEnter={() => setCursor(index)}
                onClick={() => choose(index)}
                className={[
                  "flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-sm transition-colors duration-150",
                  index === cursor ? "bg-accent-soft text-accent" : "text-ink hover:bg-sunken",
                ].join(" ")}
              >
                <span className="w-20 shrink-0 text-2xs uppercase tracking-wide text-faint">
                  {action.group}
                </span>
                <span className="min-w-0 flex-1 truncate">{action.label}</span>
                {action.hint && <kbd className="font-mono text-2xs text-faint">{action.hint}</kbd>}
                {index === cursor && <ArrowRight size={13} className="shrink-0" />}
              </button>
            </li>
          ))}
        </ul>

        <div className="flex items-center gap-2 border-t border-line px-3 py-1.5 text-2xs text-faint">
          <CommandIcon size={11} />
          <span>Enter to run, arrows to move</span>
        </div>
      </div>
      <style>{`@keyframes fade-in { from { opacity: 0 } to { opacity: 1 } }`}</style>
    </div>
  );
}
