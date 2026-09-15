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
  ChevronRight,
  Copy,
  FilePlus2,
  FileText,
  Download,
  Mail,
  PencilLine,
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
import type { LucideIcon } from "lucide-react";
import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import type { RefObject } from "react";
import { NavLink, useLocation } from "react-router-dom";

import { CV_NAME_MAX, groupByPerson, oneLine, type PersonGroup } from "../lib/cvName";
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
 * Which CV you are working on, and everything you can do to it.
 *
 * One profile was the right default and still is -- the design and the focus
 * tags exist so that one set of facts can be aimed at several postings -- but
 * two genuinely different accounts of a life do not belong in one document,
 * and this is where you say so.
 *
 * **The row is the name and a chevron, and nothing else.** It used to carry
 * two icon buttons as well, which is how a sidebar 232px wide came to show
 * "Muhamma…": those buttons took 66 of the 208 pixels the row has, and the
 * name got what was left. A name you cannot read is a worse problem than a
 * menu you have to open, so New, Duplicate, Rename and Delete moved into the
 * panel the name already opened -- where there is room to say in words what
 * each of them does, which three unlabelled icons never did.
 *
 * The trigger renders even when there is only one CV. It is the only way to
 * reach "New CV" now, so a chevron that appeared only once you already had two
 * documents would hide the door behind the room.
 *
 * **It asks nothing before switching, because there is nothing to ask.** The
 * CV being left is a file autosave has already written; switching does not
 * touch it, and coming back is one click.
 *
 * **Deleting does ask, once.** Not out of ceremony: it is the only action here
 * that a click cannot put back. It names the CV it is about, because "are you
 * sure?" over a document you cannot see while being asked is a question nobody
 * can answer.
 *
 * **Duplicating asks for a label first.** A copy that arrived called the same
 * thing as its original would leave two identical rows in the list, and naming
 * it afterwards is one more step at the moment you have least appetite for
 * one. The box opens pre-filled and selected, so typing over it is the whole
 * interaction.
 *
 * **The list is people, not CVs.** Five people with three CVs each is fifteen
 * rows, five of them reading the same name, which is not a list anybody can
 * choose from. So the panel lists whose CVs these are, and one person's CVs
 * open in a second panel beside them.
 *
 * The flyout opens on **click**, and once one is open, moving onto another
 * person swaps it. Not hover-to-open: a menu that opens under a pointer on its
 * way somewhere else needs safe-triangle tracking to be bearable, and it is
 * unreachable by touch and by keyboard either way. Click to commit, hover to
 * browse, which is the rule everywhere else that does this well.
 */
const PANEL =
  "absolute left-3 top-full z-30 w-[248px] max-w-[calc(100vw-2rem)] rounded-md " +
  "border border-line bg-surface p-2.5 shadow-raised";

/**
 * The flyout wears the same clothes, but is positioned against the viewport.
 *
 * It cannot be `absolute` inside the row it belongs to: that row lives in a
 * list with `overflow-y-auto`, and a scroll container clips its absolutely
 * positioned descendants on *both* axes. The panel rendered, was readable in
 * the DOM, and was invisible on screen. Fixed coordinates measured off the row
 * escape the clip, and nothing here creates a containing block that would
 * quietly reinterpret them.
 */
const FLYOUT_W = 204;
const FLYOUT =
  "fixed z-40 rounded-md border border-line bg-surface p-0 shadow-raised";

/**
 * What the panel is showing.
 *
 * One value rather than four flags: "the delete confirmation and the rename
 * box are both open" is a state this control does not have, and four booleans
 * would spell sixteen of which most are nonsense.
 */
type Panel =
  | { kind: "closed" }
  /** `openPerson` undefined means the people are listed and no flyout is up. */
  | { kind: "list"; openPerson?: string }
  | { kind: "arming" }
  | {
      kind: "naming";
      purpose: "duplicate" | "rename" | "person";
      value: string;
      /**
       * What is being named: a CV id for "duplicate" and "rename", the name
       * being replaced for "person". Carried rather than read off `activeCv`,
       * because the flyout can act on somebody whose CV is not the open one.
       */
      subject: string;
    };

/**
 * Whether a scroller has more below the fold.
 *
 * Every scrollbar in the app is hidden (see the base layer in tokens.css), so
 * a list of fifteen people in a box eight tall looks exactly like a list of
 * eight. This is what the fade at the bottom edge is driven by -- the one
 * affordance that says "there is more" without putting the chrome back.
 */
function useMoreBelow(ref: RefObject<HTMLElement | null>, deps: unknown): boolean {
  const [more, setMore] = useState(false);
  useLayoutEffect(() => {
    const node = ref.current;
    if (!node) {
      setMore(false);
      return;
    }
    // 1px of slack: fractional scroll positions on a zoomed or hi-dpi display
    // otherwise leave the fade painted over the last row for ever.
    const check = () => setMore(node.scrollTop + node.clientHeight < node.scrollHeight - 1);
    check();
    node.addEventListener("scroll", check, { passive: true });
    const sizes = new ResizeObserver(check);
    sizes.observe(node);
    return () => {
      node.removeEventListener("scroll", check);
      sizes.disconnect();
    };
  }, [ref, deps]);
  return more;
}

/**
 * Where to put the flyout, in viewport coordinates.
 *
 * To the right of its row, almost always -- the sidebar is on the left and the
 * whole window is over there. Below 1024px the sidebar is a drawer over the
 * content and there may be nothing to the right to open into, so it folds back
 * over the panel instead.
 *
 * Recomputed while the list scrolls, because fixed coordinates do not travel
 * with a row that moves under them. Closing the flyout on scroll would be the
 * cheaper answer and the wrong one: the scroll is how you reach the person
 * whose CVs you are comparing.
 */
function useFlyoutPosition(anchor: HTMLElement | null, open: boolean) {
  const [box, setBox] = useState<{ top: number; left: number } | null>(null);
  useLayoutEffect(() => {
    if (!anchor || !open) {
      setBox(null);
      return;
    }
    const place = () => {
      const rect = anchor.getBoundingClientRect();
      const room = window.innerWidth - rect.right;
      setBox({
        top: rect.top,
        left: room < FLYOUT_W + 12 ? rect.left - FLYOUT_W - 4 : rect.right + 4,
      });
    };
    place();
    const scroller = anchor.closest("ul");
    scroller?.addEventListener("scroll", place, { passive: true });
    window.addEventListener("resize", place);
    return () => {
      scroller?.removeEventListener("scroll", place);
      window.removeEventListener("resize", place);
    };
  }, [anchor, open]);
  return box;
}

/**
 * One person in the switcher, and their CVs in a panel beside them.
 *
 * A person with a single CV has nothing to show in a flyout, so clicking them
 * switches straight to it. Opening a panel to say "here is the one CV you
 * already knew about" would be a click spent on nothing.
 */
function PersonRow({
  group,
  activeCv,
  open,
  anyOpen,
  disabled,
  onOpen,
  onPick,
  onAdd,
  onRenamePerson,
}: {
  group: PersonGroup;
  activeCv: string;
  open: boolean;
  anyOpen: boolean;
  disabled?: boolean;
  onOpen: (person: string) => void;
  onPick: (cvId: string) => void;
  onAdd: (cvId: string) => void;
  onRenamePerson: (person: string) => void;
}) {
  const [anchor, setAnchor] = useState<HTMLLIElement | null>(null);
  const at = useFlyoutPosition(anchor, open);
  const only = group.cvs.length === 1 ? group.cvs[0] : undefined;
  const mine = group.cvs.some((cv) => cv.id === activeCv);

  return (
    <li ref={setAnchor} className="relative">
      <button
        type="button"
        role="option"
        aria-selected={mine}
        aria-expanded={only ? undefined : open}
        disabled={disabled}
        className={
          "flex w-full items-center gap-1.5 px-2 py-1.5 text-left text-xs " +
          `hover:bg-sunken disabled:opacity-45 ${open ? "bg-sunken" : ""}`
        }
        onClick={() => (only ? onPick(only.id) : onOpen(group.person))}
        // Hover swaps between people only once a flyout is already up. From
        // closed it does nothing, so a pointer crossing the list on its way
        // somewhere else never opens anything.
        onPointerEnter={() => {
          if (anyOpen && !open && !only && !disabled) onOpen(group.person);
        }}
      >
        <Check size={13} className={mine ? "shrink-0 text-accent" : "shrink-0 opacity-0"} />
        <span
          className={`min-w-0 flex-1 truncate ${mine ? "font-medium text-ink" : "text-muted"}`}
        >
          {group.person}
        </span>
        {group.cvs.length > 1 ? (
          <>
            <span className="shrink-0 text-2xs text-faint">{group.cvs.length}</span>
            <ChevronRight size={12} className="shrink-0 text-faint" />
          </>
        ) : (
          only?.blank && <span className="shrink-0 text-2xs text-faint">empty</span>
        )}
      </button>

      {open && !only && at && (
        <div
          className={FLYOUT}
          style={{ top: at.top, left: at.left, width: FLYOUT_W }}
          // The row above owns the hover that opened this; without stopping it
          // here, sliding the pointer into the flyout crosses rows underneath
          // and swaps the panel out from under itself.
          onPointerEnter={(event) => event.stopPropagation()}
        >
          <ul role="listbox" aria-label={`${group.person}'s CVs`} className="py-1">
            {group.cvs.map((cv) => {
              const on = cv.id === activeCv;
              return (
                <li key={cv.id}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={on}
                    disabled={disabled}
                    className="flex w-full items-center gap-1.5 px-2 py-1.5 text-left text-xs hover:bg-sunken disabled:opacity-45"
                    onClick={() => onPick(cv.id)}
                  >
                    <Check
                      size={13}
                      className={on ? "shrink-0 text-accent" : "shrink-0 opacity-0"}
                    />
                    <span
                      className={`min-w-0 flex-1 truncate ${on ? "font-medium text-ink" : "text-muted"}`}
                    >
                      {/* An unlabelled CV is the one they started with. Saying
                          so beats an empty row you cannot click with confidence. */}
                      {cv.label || "Main CV"}
                    </span>
                    {cv.blank && <span className="shrink-0 text-2xs text-faint">empty</span>}
                  </button>
                </li>
              );
            })}
          </ul>
          <div role="group" aria-label={group.person} className="border-t border-line py-1">
            <MenuRow
              icon={Copy}
              label="Another CV for them"
              hint="Copies this person's content, design and focus under a new name."
              disabled={disabled}
              // Copy the one of theirs you are actually on where that is one
              // of theirs, so "another CV for them" starts from what you were
              // just looking at rather than from whichever is listed first.
              onClick={() => {
                const from = group.cvs.find((cv) => cv.id === activeCv) ?? group.cvs[0];
                if (from) onAdd(from.id);
              }}
            />
            <MenuRow
              icon={PencilLine}
              label="Rename them"
              hint="Moves every one of their CVs together."
              disabled={disabled}
              onClick={() => onRenamePerson(group.person)}
            />
          </div>
        </div>
      )}
    </li>
  );
}

/** One action in the panel's footer, said in a word rather than drawn as one. */
function MenuRow({
  icon: Icon,
  label,
  hint,
  tone = "text-ink",
  onClick,
  disabled,
}: {
  icon: LucideIcon;
  label: string;
  hint?: string;
  tone?: string;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={hint}
      className={
        "flex w-full items-center gap-2 px-2 py-1.5 text-left text-xs " +
        `hover:bg-sunken disabled:opacity-45 ${tone}`
      }
    >
      <Icon size={13} className="shrink-0 text-muted" />
      {label}
    </button>
  );
}

function CVSwitcher() {
  const { cvs, activeCv, newCv, duplicateCv, renameCv, renamePerson, switchCv, deleteCv } =
    useStore(
      useShallow((s) => ({
        cvs: s.cvs,
        activeCv: s.activeCv,
        newCv: s.newCv,
        duplicateCv: s.duplicateCv,
        renameCv: s.renameCv,
        renamePerson: s.renamePerson,
        switchCv: s.switchCv,
        deleteCv: s.deleteCv,
      })),
    );
  const [busy, setBusy] = useState(false);
  // Everything the panel can be showing, in one value. The confirmation and
  // the name box live below the row rather than over the app: a modal for one
  // line of confirmation is a bigger interruption than the thing being
  // confirmed, and it takes you away from what you are confirming.
  const [panel, setPanel] = useState<Panel>({ kind: "closed" });
  const rowRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const nameId = useId();
  const shown = panel.kind !== "closed";
  const people = groupByPerson(cvs);
  // The list is unmounted while the panel is shut, so the measurement has to
  // be redone when it opens -- not just when the people change. Keying on both
  // is what stops the fade being decided against a ref that was still null.
  const moreBelow = useMoreBelow(listRef, `${panel.kind}:${people.length}`);

  useEffect(() => {
    if (!shown) return;
    const away = (event: PointerEvent) => {
      if (!rowRef.current?.contains(event.target as Node)) setPanel({ kind: "closed" });
    };
    // Escape steps back rather than slamming: out of the name box to the list,
    // out of the list to nothing. Handled here rather than on the input so
    // there is one rule in one place -- a text input does nothing else with
    // Escape, so letting it bubble this far costs nothing.
    const key = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setPanel((was) => {
        // One rung at a time: the name box gives way to the list, an open
        // flyout closes before the panel it hangs off, and only a bare list
        // shuts the whole thing.
        if (was.kind !== "list") return { kind: "list" };
        return was.openPerson ? { kind: "list" } : { kind: "closed" };
      });
    };
    document.addEventListener("pointerdown", away);
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("pointerdown", away);
      document.removeEventListener("keydown", key);
    };
    // `shown`, not `panel`: the name box rewrites `panel.value` on every
    // keystroke, and depending on the object would tear down and re-attach two
    // document listeners per character typed. The functional `setPanel` above
    // is what makes the narrower dependency safe -- neither handler closes
    // over a `panel` that could go stale.
  }, [shown]);

  async function run(work: () => Promise<void>) {
    setBusy(true);
    try {
      await work();
    } finally {
      setBusy(false);
    }
  }

  const active = cvs.find((cv) => cv.id === activeCv);
  const person = active?.person ?? "Your CV";
  const label = active?.label ?? "";
  const full = active ? oneLine(active) : person;

  return (
    <div ref={rowRef} className="relative flex items-center px-3 pb-1">
      <button
        type="button"
        className={[
          // No border and no reserved arrow gutter: the chevron follows the
          // text instead of being pinned to the right of a box, so a short
          // name takes a short row and a long one gets every pixel between the
          // logo above it and the edge of the sidebar.
          "-mx-1 flex min-w-0 max-w-full items-center gap-1 rounded px-1 py-1",
          "text-ink transition-colors hover:bg-sunken disabled:opacity-45",
        ].join(" ")}
        onClick={() =>
          setPanel((was) => (was.kind === "closed" ? { kind: "list" } : { kind: "closed" }))
        }
        disabled={busy}
        // "true" rather than "listbox": the panel is a list of people *and* a
        // group of actions, and telling a screen reader it is only the former
        // would be describing something that is not there.
        aria-haspopup="true"
        aria-expanded={shown}
        aria-label="Which CV"
        title={full}
      >
        {/* Two lines, because the two halves are two different facts and 208px
            is not enough for both on one. Stacking them is what keeps the name
            whole -- putting them side by side with a separator would bring back
            the truncation the row was rearranged to get rid of. */}
        <span className="flex min-w-0 flex-col items-start">
          <span className="max-w-full truncate text-sm font-medium leading-tight">{person}</span>
          {label && (
            <span className="max-w-full truncate text-2xs leading-tight text-muted">{label}</span>
          )}
        </span>
        <ChevronDown
          size={14}
          strokeWidth={2}
          className={`shrink-0 self-center text-muted transition-transform duration-150 ${shown ? "rotate-180" : ""}`}
        />
      </button>

      {/* Deleting is the one action here that a switch cannot undo, so it
          asks -- and it asks in the panel rather than in the row, because the
          row is 208px of sidebar and the question is *which CV*. A
          confirmation that has to truncate the name it is asking about is not
          a confirmation. */}
      {panel.kind === "arming" && active && (
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
              onClick={() => setPanel({ kind: "list" })}
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
                  setPanel({ kind: "closed" });
                })
              }
            >
              Delete
            </button>
          </div>
        </div>
      )}

      {/* The panel is where there is room to be complete: full names, "empty"
          said in words rather than squeezed into the trigger, and the actions
          labelled instead of drawn. The listbox and the actions are siblings
          rather than nested, because a button that is not an `option` has no
          business inside a `role="listbox"`. */}
      {(panel.kind === "list" || panel.kind === "naming") && (
        <div className={`${PANEL} p-0`}>
          {/* `relative` so the fade below can sit on the list's bottom edge. */}
          <div className="relative">
            <ul
              ref={listRef}
              role="listbox"
              aria-label="Whose CV"
              className="max-h-56 overflow-y-auto py-1"
            >
              {people.map((group) => (
                <PersonRow
                  key={group.person}
                  group={group}
                  activeCv={activeCv}
                  open={panel.kind === "list" && panel.openPerson === group.person}
                  // Only once one is already up. Opening on hover from closed
                  // would fire on a pointer merely crossing the list.
                  anyOpen={panel.kind === "list" && panel.openPerson !== undefined}
                  // Frozen while a name is being typed: switching document out
                  // from under a half-finished rename would either apply it to
                  // the wrong CV or throw it away.
                  disabled={busy || panel.kind === "naming"}
                  onOpen={(person) => setPanel({ kind: "list", openPerson: person })}
                  onPick={(id) => {
                    setPanel({ kind: "closed" });
                    if (id !== activeCv) void run(() => switchCv(id));
                  }}
                  onAdd={(cvId) =>
                    setPanel({ kind: "naming", purpose: "duplicate", value: "", subject: cvId })
                  }
                  onRenamePerson={(name) =>
                    setPanel({ kind: "naming", purpose: "person", value: name, subject: name })
                  }
                />
              ))}
            </ul>
            {/* The one thing that says "there is more" now that every
                scrollbar in the app is hidden. Painted over the last few
                pixels of the list and gone the moment you reach the end. */}
            {moreBelow && (
              <div
                aria-hidden
                className="pointer-events-none absolute inset-x-0 bottom-0 h-6 rounded-b-md bg-gradient-to-t from-surface to-transparent"
              />
            )}
          </div>

          {panel.kind === "list" ? (
            // Scoped to the CV you are on, and to starting a new one. Anything
            // about a *person* -- another of their CVs, their name -- lives in
            // their flyout, next to the person it is about.
            <div role="group" aria-label="This CV" className="border-t border-line py-1">
              <MenuRow
                icon={FilePlus2}
                label="New CV"
                hint="Somebody new, from blank. The one you are on is saved and stays in the list."
                disabled={busy}
                onClick={() => {
                  setPanel({ kind: "closed" });
                  void run(newCv);
                }}
              />
              <MenuRow
                icon={PencilLine}
                label={label ? `Rename “${label}”` : "Name this CV"}
                hint="What to call this one of their CVs. Their name is renamed from their own row."
                disabled={busy || !active}
                onClick={() =>
                  active &&
                  setPanel({
                    kind: "naming",
                    purpose: "rename",
                    value: label,
                    subject: active.id,
                  })
                }
              />
              {/* Only once there is somewhere to land. The last CV cannot go --
                  the registry refuses it -- and a row that only ever errors is
                  worse than no row, so it is not shown until deleting means
                  something. */}
              {cvs.length > 1 && (
                <MenuRow
                  icon={Trash2}
                  label="Delete"
                  tone="text-poor"
                  hint="Delete the CV you are on. A copy is kept in data/backups."
                  disabled={busy}
                  onClick={() => setPanel({ kind: "arming" })}
                />
              )}
            </div>
          ) : (
            <div className="border-t border-line p-2">
              <label className="block text-2xs text-faint" htmlFor={nameId}>
                {panel.purpose === "duplicate"
                  ? "Call the new one"
                  : panel.purpose === "person"
                    ? "Rename them everywhere"
                    : "Call this one"}
              </label>
              <input
                id={nameId}
                // Two attributes rather than an effect: the input mounts only
                // when naming begins, so `autoFocus` fires exactly once and
                // the selection is not redone on every keystroke. Selecting is
                // what makes a pre-filled name something you type over.
                autoFocus
                onFocus={(event) => event.currentTarget.select()}
                value={panel.value}
                maxLength={CV_NAME_MAX}
                disabled={busy}
                placeholder={panel.purpose === "duplicate" ? "Education" : undefined}
                className="mt-1 w-full rounded border border-line bg-sunken px-1.5 py-1 text-xs text-ink"
                onChange={(event) => setPanel({ ...panel, value: event.target.value })}
                onKeyDown={(event) => {
                  // Escape is left to bubble to the document handler above, so
                  // stepping back out of here obeys the same rule as anywhere
                  // else in this control. No <form>, so no submit to cancel.
                  if (event.key !== "Enter") return;
                  event.preventDefault();
                  const wanted = panel.value.trim();
                  // A label may be cleared, so "rename" accepts an empty box.
                  // The other two name something that must end up called
                  // *something*, and would only be refused by the server.
                  if (!wanted && panel.purpose !== "rename") return;
                  const { purpose, subject } = panel;
                  setPanel({ kind: "closed" });
                  void run(async () => {
                    if (purpose === "duplicate") await duplicateCv(wanted, subject);
                    else if (purpose === "person") await renamePerson(subject, wanted);
                    else await renameCv(subject, wanted);
                  });
                }}
              />
              <p className="mt-1 text-2xs text-faint">
                {panel.purpose === "person"
                  ? "Every CV of theirs moves together."
                  : "Enter to confirm, Escape to cancel."}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
