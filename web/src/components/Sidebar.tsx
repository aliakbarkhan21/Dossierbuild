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
  Check,
  ChevronDown,
  FilePlus2,
  FileText,
  Download,
  Mail,
  Target,
  Crosshair,
  Moon,
  PanelLeftClose,
  Settings as SettingsIcon,
  ScanSearch,
  Sun,
  Trash2,
  User,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";

import { MARKER_COLOUR_CLASS, markerStyle, useSlidingMarker } from "../lib/marker";
import { currentMode, cycleMode, type Mode } from "../lib/theme";
import { useShallow } from "zustand/react/shallow";
import { useStore } from "../lib/store";

const NAV = [
  { to: "/profile", label: "Profile", icon: User, hint: "Everything you have done" },
  { to: "/resume", label: "Resume", icon: FileText, hint: "Choose a look and print it" },
  { to: "/tailor", label: "Tailor", icon: Target, hint: "Aim it at one job posting" },
  {
    to: "/focus",
    label: "Focus",
    icon: Crosshair,
    hint: "One profile, aimed at several kinds of job",
  },
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
  { to: "/health", label: "Review", icon: ScanSearch, hint: "What is wrong with the document" },
  { to: "/import", label: "Import", icon: Download, hint: "Bring in an existing CV" },
];

export function Sidebar({ onCollapse }: { onCollapse: () => void }) {
  const [mode, setModeState] = useState<Mode>(currentMode);
  const health = useStore((s) => s.health);
  // The active link is found by `aria-current="page"`, which NavLink sets
  // itself -- using its own idea of active is what stops the highlight and
  // the bold text ever disagreeing, and it needs no extra attribute.
  const location = useLocation();
  const marker = useSlidingMarker<HTMLUListElement>(
    location.pathname,
    'a[aria-current="page"]',
    "y",
  );

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

      <CVSwitcher />

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
            style={markerStyle(marker.box, marker.animate, "y")}
          >
            <span className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-full bg-accent" />
          </span>
        )}

        {NAV.map(({ to, label, icon: Icon, hint }) => (
          <li key={to}>
            <NavLink
              to={to}
              title={hint}
              className={({ isActive }) =>
                [
                  // `relative` so the label and icon paint above the pill.
                  "group relative z-10 flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm",
                  MARKER_COLOUR_CLASS,
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
        {/* Both of these are about the app rather than about the document, which
            is why they sit down here with each other rather than in the nav
            above: that list is places to work, and neither of these is one.
            The palette hint stays in the top bar -- it is the only thing that
            tells anyone the palette exists. */}
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            className="btn btn-quiet min-w-0 flex-1 justify-start"
            onClick={() => setModeState(cycleMode())}
            // The label names what you are looking at, not what pressing it
            // does. It is the one readable place the current theme is stated,
            // and a button that reads "Dark" while the app is light would be
            // lying to make room for an instruction nobody needs.
            title={mode === "dark" ? "Switch to light" : "Switch to dark"}
          >
            {mode === "dark" ? <Moon size={15} /> : <Sun size={15} />}
            {mode === "dark" ? "Dark" : "Light"}
          </button>
          <NavLink
            to="/settings"
            title="Your API key, the model, and where your data lives"
            aria-label="Settings"
            className={({ isActive }) =>
              [
                "btn btn-quiet shrink-0 px-1.5 py-1",
                isActive ? "border-accent text-accent" : "",
              ].join(" ")
            }
          >
            <SettingsIcon size={15} />
          </NavLink>
        </div>

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

/**
 * Which CV you are working on, and a way to start another.
 *
 * One profile was the right default and still is -- the design and the focus
 * tags exist so that one set of facts can be aimed at several postings -- but
 * two genuinely different accounts of a life do not belong in one document,
 * and this is where you say so.
 *
 * **It asks nothing before switching, because there is nothing to ask.** The
 * CV being left is a file autosave has already written; switching does not
 * touch it, and coming back is one click. A confirmation dialog here would be
 * asking permission to do something with no consequences.
 *
 * Hidden entirely while there is only one CV and it is untouched -- a
 * switcher with one entry teaches nothing. The "New CV" button stays.
 *
 * **Deleting does ask, once.** Not out of ceremony: it is the only action in
 * this row that a click cannot put back. It arms in place and names the CV it
 * is about, because "are you sure?" over a document you cannot see while
 * being asked is a question nobody can answer.
 */
const PANEL =
  "absolute left-3 top-full z-30 w-[248px] max-w-[calc(100vw-2rem)] rounded-md " +
  "border border-line bg-surface p-2.5 shadow-raised";

function CVSwitcher() {
  const { cvs, activeCv, newCv, switchCv, deleteCv } = useStore(
    useShallow((s) => ({
      cvs: s.cvs,
      activeCv: s.activeCv,
      newCv: s.newCv,
      switchCv: s.switchCv,
      deleteCv: s.deleteCv,
    })),
  );
  const [busy, setBusy] = useState(false);
  // Whether the delete is armed. Below the row rather than over the app: a
  // modal for one line of confirmation is a bigger interruption than the
  // thing being confirmed, and it takes you away from what you are deleting.
  const [arming, setArming] = useState(false);
  const [open, setOpen] = useState(false);
  const rowRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open && !arming) return;
    const shut = () => {
      setOpen(false);
      setArming(false);
    };
    const away = (event: PointerEvent) => {
      if (!rowRef.current?.contains(event.target as Node)) shut();
    };
    const key = (event: KeyboardEvent) => {
      if (event.key === "Escape") shut();
    };
    document.addEventListener("pointerdown", away);
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("pointerdown", away);
      document.removeEventListener("keydown", key);
    };
  }, [open, arming]);

  async function run(work: () => Promise<void>) {
    setBusy(true);
    try {
      await work();
    } finally {
      setBusy(false);
    }
  }

  const active = cvs.find((cv) => cv.id === activeCv);
  const label = active?.name ?? "Your CV";

  return (
    <div ref={rowRef} className="relative flex items-center gap-1.5 px-3 pb-1">
      {cvs.length > 1 ? (
        <button
          type="button"
          className={[
            // No border and no reserved arrow gutter: the chevron follows the
            // last letter instead of being pinned to the right of a box, so a
            // short name takes a short row and a long one gets every pixel
            // between the logo above it and the buttons beside it.
            "-mx-1 flex min-w-0 items-center gap-1 rounded px-1 py-1 text-sm font-medium",
            "text-ink transition-colors hover:bg-sunken disabled:opacity-45",
          ].join(" ")}
          onClick={() => {
            setArming(false);
            setOpen((was) => !was);
          }}
          disabled={busy}
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-label="Which CV"
          title={label}
        >
          <span className="truncate">{label}</span>
          <ChevronDown
            size={14}
            strokeWidth={2}
            className={`shrink-0 text-muted transition-transform duration-150 ${open ? "rotate-180" : ""}`}
          />
        </button>
      ) : (
        <span className="min-w-0 truncate text-sm font-medium text-muted" title={label}>
          {label}
        </span>
      )}

      <span className="ml-auto flex shrink-0 items-center gap-1.5">
        <button
          type="button"
          className="btn btn-quiet px-1.5 py-1"
          onClick={() => void run(newCv)}
          disabled={busy}
          title="Start a new CV. This one is saved and stays in the list."
          aria-label="New CV"
        >
          <FilePlus2 size={15} />
        </button>
        {/* Only once there is somewhere to land. The last CV cannot go -- the
            registry refuses it -- and a button that only ever errors is worse
            than no button, so it is not shown until deleting means something. */}
        {cvs.length > 1 && (
          <button
            type="button"
            className="btn btn-quiet px-1.5 py-1"
            onClick={() => {
              setOpen(false);
              setArming(true);
            }}
            disabled={busy}
            title="Delete the CV you are on. A copy is kept in data/backups."
            aria-label="Delete this CV"
          >
            <Trash2 size={15} />
          </button>
        )}
      </span>

      {/* Deleting is the one action in this row that a switch cannot undo,
          so it asks -- and it asks in the panel rather than in the row,
          because the row is 200px of sidebar and the question is *which CV*.
          A confirmation that has to truncate the name it is asking about is
          not a confirmation. */}
      {arming && active && (
        <div className={PANEL}>
          <p className="text-xs text-ink">
            Delete “<span className="font-medium">{active.name}</span>”?
          </p>
          <p className="mt-1 text-2xs text-faint">
            A copy is kept in data/backups, and the CVs you are not on are untouched.
          </p>
          <div className="mt-2.5 flex justify-end gap-1.5">
            <button
              type="button"
              className="btn btn-quiet px-2 py-1 text-2xs"
              disabled={busy}
              onClick={() => setArming(false)}
            >
              Keep
            </button>
            <button
              type="button"
              className="btn px-2 py-1 text-2xs text-poor"
              disabled={busy}
              onClick={() =>
                void run(async () => {
                  await deleteCv(active.id);
                  setArming(false);
                })
              }
            >
              Delete
            </button>
          </div>
        </div>
      )}

      {/* The list is where there is room to be complete: full names, and
          "empty" said in words rather than squeezed into the trigger. */}
      {open && (
        <ul
          role="listbox"
          aria-label="Your CVs"
          className={`${PANEL} max-h-72 overflow-y-auto p-0 py-1`}
        >
          {cvs.map((cv) => {
            const on = cv.id === activeCv;
            return (
              <li key={cv.id}>
                <button
                  type="button"
                  role="option"
                  aria-selected={on}
                  className="flex w-full items-center gap-1.5 px-2 py-1.5 text-left text-xs hover:bg-sunken"
                  onClick={() => {
                    setOpen(false);
                    if (!on) void run(() => switchCv(cv.id));
                  }}
                >
                  <Check
                    size={13}
                    className={on ? "shrink-0 text-accent" : "shrink-0 opacity-0"}
                  />
                  <span className={`min-w-0 flex-1 truncate ${on ? "font-medium text-ink" : "text-muted"}`}>
                    {cv.name}
                  </span>
                  {cv.blank && <span className="shrink-0 text-2xs text-faint">empty</span>}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
