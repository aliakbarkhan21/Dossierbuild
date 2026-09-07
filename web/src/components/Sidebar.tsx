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
  FilePlus2,
  FileText,
  Download,
  Mail,
  Target,
  Moon,
  PanelLeftClose,
  Stethoscope,
  Sun,
  Trash2,
  User,
} from "lucide-react";
import { useState } from "react";
import { NavLink, useLocation } from "react-router-dom";

import { MARKER_COLOUR_CLASS, markerStyle, useSlidingMarker } from "../lib/marker";
import { currentMode, toggleMode, type Mode } from "../lib/theme";
import { useShallow } from "zustand/react/shallow";
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
  // Whether the delete is armed. In place rather than in a modal: the row is
  // 200px of sidebar, and a dialog over the whole app for one line of
  // confirmation is a bigger interruption than the thing being confirmed.
  const [arming, setArming] = useState(false);

  async function run(work: () => Promise<void>) {
    setBusy(true);
    try {
      await work();
    } finally {
      setBusy(false);
    }
  }

  const active = cvs.find((cv) => cv.id === activeCv);

  // Deleting is the one action here that a switch cannot undo, so it asks --
  // and it asks about the CV you are looking at, which is why the prompt
  // takes the row rather than sitting beside a list you could still change.
  if (arming && active) {
    return (
      <div className="flex items-center gap-1 px-3 pb-1">
        <span className="min-w-0 flex-1 truncate text-2xs text-muted" title={active.name}>
          Delete “{active.name}”?
        </span>
        <button
          type="button"
          className="btn shrink-0 px-1.5 py-1 text-2xs text-poor"
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
        <button
          type="button"
          className="btn btn-quiet shrink-0 px-1.5 py-1 text-2xs"
          disabled={busy}
          onClick={() => setArming(false)}
        >
          Keep
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1.5 px-3 pb-1">
      {cvs.length > 1 ? (
        <select
          aria-label="Which CV"
          className="field h-8 min-w-0 flex-1 py-1 text-xs"
          value={activeCv}
          disabled={busy}
          onChange={(event) => void run(() => switchCv(event.target.value))}
        >
          {cvs.map((cv) => (
            <option key={cv.id} value={cv.id}>
              {cv.name}
              {cv.blank ? " · empty" : ""}
            </option>
          ))}
        </select>
      ) : (
        <span className="min-w-0 flex-1 truncate text-xs text-faint">
          {cvs[0]?.name ?? "Your CV"}
        </span>
      )}
      <button
        type="button"
        className="btn btn-quiet shrink-0 px-1.5 py-1"
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
          className="btn btn-quiet shrink-0 px-1.5 py-1"
          onClick={() => setArming(true)}
          disabled={busy}
          title="Delete the CV you are on. A copy is kept in data/backups."
          aria-label="Delete this CV"
        >
          <Trash2 size={15} />
        </button>
      )}
    </div>
  );
}
