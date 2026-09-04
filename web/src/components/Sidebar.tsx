/**
 * Navigation that reads as navigation.
 *
 * The Streamlit build used a radio group here: circular dots beside four
 * words, which is a form control asking the user to choose an option, not a
 * way to move around an application. These are links with an icon, a hover
 * state, and a filled background plus a left accent bar when active.
 */

import {
  Briefcase,
  FileText,
  Download,
  Mail,
  Target,
  Moon,
  PanelLeftClose,
  Stethoscope,
  Sun,
  User,
} from "lucide-react";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";

import { currentMode, toggleMode, type Mode } from "../lib/theme";
import { useStore } from "../lib/store";

const NAV = [
  { to: "/profile", label: "Profile", icon: User, hint: "Everything you have done" },
  { to: "/resume", label: "Resume", icon: FileText, hint: "Choose a look and print it" },
  { to: "/tailor", label: "Tailor", icon: Target, hint: "Aim it at one job posting" },
  {
    to: "/applications",
    label: "Applications",
    icon: Briefcase,
    hint: "Every job you have gone for, and what they have in common",
  },
  {
    to: "/letter",
    label: "Cover letter",
    icon: Mail,
    hint: "One letter per application, on the same paper as the resume",
  },
  { to: "/import", label: "Import", icon: Download, hint: "Bring in an existing CV" },
  { to: "/health", label: "Health check", icon: Stethoscope, hint: "How the writing reads" },
];

/**
 * Where the active-link highlight should be, and whether it may animate there.
 *
 * Measured rather than computed from the index: the rows are the same height
 * today, but one long enough to wrap would break an arithmetic version
 * silently, and reading the box costs nothing at seven links.
 *
 * `animate` is false for the first placement. A highlight that slides in from
 * the top of the list on every mount reads as the app choosing the page for
 * you -- and this component remounts whenever the drawer opens on a narrow
 * window.
 */
function useActiveMarker() {
  const listRef = useRef<HTMLUListElement>(null);
  const location = useLocation();
  const [box, setBox] = useState<{ y: number; h: number; shown: boolean } | null>(null);
  const animate = useRef(false);

  const measure = useCallback(() => {
    const list = listRef.current;
    if (!list) return;
    const active = list.querySelector<HTMLElement>('a[aria-current="page"]');
    setBox((was) => {
      // No active link -- a route outside the nav, or the instant before "/"
      // redirects. The highlight stays where it is and fades, rather than
      // flying to the top of the list and back.
      if (!active) return was ? { ...was, shown: false } : null;
      const next = { y: active.offsetTop, h: active.offsetHeight, shown: true };
      return was && was.y === next.y && was.h === next.h && was.shown ? was : next;
    });
  }, []);

  useLayoutEffect(() => {
    measure();
  }, [measure, location.pathname]);

  useEffect(() => {
    const list = listRef.current;
    if (!list) return;
    // The rows are as tall as their text, and the text is a web font that
    // arrives after the first paint.
    const observer = new ResizeObserver(measure);
    observer.observe(list);
    for (const item of list.querySelectorAll("li")) observer.observe(item);
    document.fonts?.ready.then(measure).catch(() => {});
    return () => observer.disconnect();
  }, [measure]);

  useEffect(() => {
    if (box && !animate.current) {
      const id = requestAnimationFrame(() => {
        animate.current = true;
      });
      return () => cancelAnimationFrame(id);
    }
    return undefined;
  }, [box]);

  return { listRef, box, animate: animate.current };
}

export function Sidebar({ onCollapse }: { onCollapse: () => void }) {
  const [mode, setModeState] = useState<Mode>(currentMode);
  const health = useStore((s) => s.health);
  const marker = useActiveMarker();

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

      <ul ref={marker.listRef} className="relative flex flex-col gap-0.5 px-2 py-1">
        {/* One highlight for seven links, rather than one each.
            It is a sibling of the links and sits behind them, so the pill and
            its accent bar travel together between two settled positions --
            which is the whole point: a background that switches off here and
            on there is a cut, and the eye cannot follow a cut. */}
        {marker.box && (
          <span
            aria-hidden
            className="pointer-events-none absolute left-2 right-2 rounded-md bg-accent-soft"
            style={{
              top: 0,
              height: marker.box.h,
              transform: `translateY(${marker.box.y}px)`,
              opacity: marker.box.shown ? 1 : 0,
              // `transform` and `opacity` only. Height was in this list, and
              // height is not a compositor property -- one entry that cannot
              // be composited drags the whole transition onto the main
              // thread, where it is at the mercy of whatever the page being
              // navigated to is doing. The Resume screen parses a full A4
              // document into an iframe on arrival, and the slide was
              // stopping dead for 200ms in the middle of it. Every row here
              // is the same height, so nothing is lost by setting it
              // outright; a row long enough to wrap would resize in one step
              // rather than easing, which is the right thing to trade.
              //
              // `will-change` gets the layer up before the first move rather
              // than on it, so the first navigation is as smooth as the rest.
              willChange: "transform",
              transition: marker.animate
                ? "transform 260ms cubic-bezier(.22,.61,.36,1), opacity 160ms ease-out"
                : "none",
            }}
          >
            <span className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-full bg-accent" />
          </span>
        )}

        {NAV.map(({ to, label, icon: Icon, hint }) => (
          <li key={to}>
            <NavLink
              to={to}
              title={hint}
              // The marker finds the active link by `aria-current="page"`,
              // which NavLink sets itself. Using its own idea of active is
              // what keeps the highlight and the bold text from disagreeing,
              // and it needs no extra attribute to carry it.
              className={({ isActive }) =>
                [
                  // `relative` so the label and icon paint above the pill.
                  //
                  // The colour takes as long as the pill does, and on the
                  // same curve. At 150ms against a 260ms slide the label went
                  // green while the highlight was still two rows away, which
                  // reads as two things happening rather than one.
                  "group relative z-10 flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm",
                  "transition-colors duration-[260ms] ease-[cubic-bezier(.22,.61,.36,1)]",
                  isActive
                    ? "font-semibold text-accent"
                    : "text-muted hover:bg-sunken hover:text-ink",
                ].join(" ")
              }
            >
              <Icon size={16} strokeWidth={1.9} />
              {label}
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
