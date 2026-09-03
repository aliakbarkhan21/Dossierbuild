/**
 * Navigation that reads as navigation.
 *
 * The Streamlit build used a radio group here: circular dots beside four
 * words, which is a form control asking the user to choose an option, not a
 * way to move around an application. These are links with an icon, a hover
 * state, and a filled background plus a left accent bar when active.
 */

import {
  FileText,
  Download,
  Moon,
  PanelLeftClose,
  Stethoscope,
  Sun,
  User,
} from "lucide-react";
import { useState } from "react";
import { NavLink } from "react-router-dom";

import { currentMode, toggleMode, type Mode } from "../lib/theme";
import { useStore } from "../lib/store";

const NAV = [
  { to: "/profile", label: "Profile", icon: User, hint: "Everything you have done" },
  { to: "/resume", label: "Resume", icon: FileText, hint: "Choose a look and print it" },
  { to: "/import", label: "Import", icon: Download, hint: "Bring in an existing CV" },
  { to: "/health", label: "Health check", icon: Stethoscope, hint: "How the writing reads" },
];

export function Sidebar({ onCollapse }: { onCollapse: () => void }) {
  const [mode, setModeState] = useState<Mode>(currentMode);
  const health = useStore((s) => s.health);

  return (
    <nav
      aria-label="Sections"
      className="flex h-full w-[232px] shrink-0 flex-col border-r border-line bg-surface"
    >
      <div className="flex items-center justify-between px-4 pt-4 pb-3">
        <div className="flex items-center gap-2">
          <span
            aria-hidden
            className="h-[26px] w-[28px] bg-ink"
            style={{
              maskImage: "url(/mark.png)",
              WebkitMaskImage: "url(/mark.png)",
              maskSize: "contain",
              WebkitMaskSize: "contain",
              maskRepeat: "no-repeat",
              WebkitMaskRepeat: "no-repeat",
              maskPosition: "center",
              WebkitMaskPosition: "center",
            }}
          />
          <span className="whitespace-nowrap font-display text-lg font-semibold tracking-tight">
            Dossierbuild<span className="text-accent">.</span>
          </span>
        </div>
        <button
          type="button"
          onClick={onCollapse}
          className="btn btn-quiet px-1.5 py-1"
          title="Hide the sidebar"
          aria-label="Hide the sidebar"
        >
          <PanelLeftClose size={15} />
        </button>
      </div>

      <ul className="flex flex-col gap-0.5 px-2 py-1">
        {NAV.map(({ to, label, icon: Icon, hint }) => (
          <li key={to}>
            <NavLink
              to={to}
              title={hint}
              className={({ isActive }) =>
                [
                  "group relative flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors duration-150 ease-out",
                  isActive
                    ? "bg-accent-soft font-semibold text-accent"
                    : "text-muted hover:bg-sunken hover:text-ink",
                ].join(" ")
              }
            >
              {({ isActive }) => (
                <>
                  <span
                    aria-hidden
                    className={[
                      "absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-full transition-opacity duration-150 ease-out",
                      isActive ? "bg-accent opacity-100" : "opacity-0",
                    ].join(" ")}
                  />
                  <Icon size={16} strokeWidth={1.9} />
                  {label}
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>

      <div className="mt-auto border-t border-line p-3">
        <button
          type="button"
          className="btn btn-quiet w-full justify-start"
          onClick={() => setModeState(toggleMode())}
        >
          {mode === "dark" ? <Moon size={15} /> : <Sun size={15} />}
          {mode === "dark" ? "Dark" : "Light"}
        </button>

        {/* What the app can actually do right now, stated rather than
            discovered when a button fails. */}
        {health && (!health.pdf_available || !health.ai_available) && (
          <p className="mt-2 px-1 text-2xs text-faint">
            {!health.pdf_available && "PDF unavailable. "}
            {!health.ai_available && "No Gemini key: import cannot parse."}
          </p>
        )}

        <p className="mt-2 px-1 text-2xs text-faint">
          Built by{" "}
          <a
            className="text-muted underline decoration-line underline-offset-2 hover:text-accent"
            href="https://www.linkedin.com/in/muhammad-ali-akbar-khan-7b37b8197"
            target="_blank"
            rel="noopener noreferrer"
          >
            Muhammad Ali Akbar
          </a>
        </p>
      </div>
    </nav>
  );
}
