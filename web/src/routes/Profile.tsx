/**
 * The master profile editor.
 *
 * Eight sections, one declarative field table. Writing eight bespoke forms
 * would have meant eight places to fix a date input; instead each section
 * declares what it holds and this file renders it, which is also why adding a
 * field to the schema costs one line here.
 *
 * The section lives in the URL, so a refresh, a back button, and a link from
 * the command palette all land where you were.
 */

import { Download, GripVertical, PenLine, Plus, Sparkles, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { AiSuggest } from "../components/AiSuggest";
import { RichText } from "../components/RichText";
import { useShell } from "../App";
import { TopBar } from "../components/TopBar";
import { useShallow } from "zustand/react/shallow";

import { MARKER_COLOUR_CLASS, markerStyle, useSlidingMarker } from "../lib/marker";
import { isBlank, useStore } from "../lib/store";
import { moveWithin, useReorder } from "../lib/reorder";
import { Tags, tagsInUse } from "../components/Tags";
import type { ListSection, Profile } from "../lib/types";

type Kind = "text" | "month" | "csv" | "select" | "url" | "prose";

interface FieldSpec {
  key: string;
  label: string;
  kind?: Kind;
  placeholder?: string;
  options?: readonly string[];
  half?: boolean;
}

interface SectionSpec {
  label: string;
  singular: string;
  /** What an empty one looks like. Ids are minted by the server on save. */
  blank: () => Record<string, unknown>;
  fields: FieldSpec[];
  bullets: boolean;
  teaches: string;
}

const EMPLOYMENT = [
  "Internship",
  "Placement",
  "Part-time",
  "Full-time",
  "Freelance",
  "Volunteer",
  "Research",
  "Other",
] as const;

const SECTIONS: Record<ListSection, SectionSpec> = {
  experience: {
    label: "Experience",
    singular: "role",
    blank: () => ({
      id: "",
      role: "",
      organisation: "",
      location: "",
      employment_type: "Internship",
      start: null,
      end: null,
      bullets: [],
    }),
    fields: [
      { key: "role", label: "Role", placeholder: "Data Engineering Intern", half: true },
      { key: "organisation", label: "Organisation", placeholder: "Northgate Analytics", half: true },
      { key: "employment_type", label: "Type", kind: "select", options: EMPLOYMENT, half: true },
      { key: "location", label: "Location", placeholder: "Manchester, UK", half: true },
      { key: "start", label: "Start", kind: "month", half: true },
      { key: "end", label: "End", kind: "month", placeholder: "blank means present", half: true },
    ],
    bullets: true,
    teaches:
      "One line per thing you actually changed. Name the technology, the number, and what moved.",
  },
  projects: {
    label: "Projects",
    singular: "project",
    blank: () => ({ id: "", name: "", tagline: "", tech: [], url: "", start: null, end: null, bullets: [] }),
    fields: [
      { key: "name", label: "Name", placeholder: "Loot Ledger", half: true },
      { key: "tagline", label: "Tagline", placeholder: "Personal finance tracker", half: true },
      { key: "tech", label: "Stack", kind: "csv", placeholder: "Python, Streamlit, SQLite" },
      { key: "url", label: "Link", kind: "url", placeholder: "github.com/you/project", half: true },
      { key: "start", label: "Start", kind: "month", half: true },
      { key: "end", label: "End", kind: "month", half: true },
    ],
    bullets: true,
    teaches: "What it does, what you built, and one number that shows it worked.",
  },
  education: {
    label: "Education",
    singular: "qualification",
    blank: () => ({
      id: "",
      institution: "",
      credential: "",
      location: "",
      start: null,
      end: null,
      grade: "",
      coursework: [],
      bullets: [],
    }),
    fields: [
      { key: "credential", label: "Credential", placeholder: "BSc Computer Science", half: true },
      { key: "institution", label: "Institution", placeholder: "University of Manchester", half: true },
      { key: "grade", label: "Grade", placeholder: "Predicted First", half: true },
      { key: "location", label: "Location", half: true },
      { key: "start", label: "Start", kind: "month", half: true },
      { key: "end", label: "End", kind: "month", half: true },
      { key: "coursework", label: "Modules", kind: "csv", placeholder: "Algorithms, Databases" },
    ],
    bullets: true,
    teaches: "Only add bullets here if the work is worth a line of its own.",
  },
  skills: {
    label: "Skills",
    singular: "group",
    blank: () => ({ id: "", label: "", items: [], tags: [] }),
    fields: [
      { key: "label", label: "Group", placeholder: "Languages", half: true },
      { key: "items", label: "Items", kind: "csv", placeholder: "Python, SQL, TypeScript" },
    ],
    bullets: false,
    teaches: "Grouped, not a flat wall: a reader scans categories, and so does a parser.",
  },
  certifications: {
    label: "Certifications",
    singular: "certification",
    blank: () => ({ id: "", name: "", issuer: "", issued: null, url: "" }),
    fields: [
      { key: "name", label: "Name", placeholder: "AWS Certified Cloud Practitioner", half: true },
      { key: "issuer", label: "Issuer", placeholder: "Amazon Web Services", half: true },
      { key: "issued", label: "Issued", kind: "month", half: true },
      { key: "url", label: "Link", kind: "url", half: true },
    ],
    bullets: false,
    teaches: "",
  },
  awards: {
    label: "Honors",
    singular: "honor",
    blank: () => ({ id: "", title: "", awarded_by: "", date: null, note: "" }),
    fields: [
      { key: "title", label: "Title", placeholder: "Dean's List", half: true },
      { key: "awarded_by", label: "Awarded by", placeholder: "FAST NUCES", half: true },
      { key: "date", label: "Date", kind: "month", half: true },
      { key: "note", label: "Note", placeholder: "Top 5% of the cohort", half: true },
    ],
    bullets: false,
    teaches: "Things you were given: prizes, scholarships, a place on a list.",
  },
  achievements: {
    label: "Achievements",
    singular: "achievement",
    blank: () => ({ id: "", title: "", context: "", date: null, note: "" }),
    fields: [
      { key: "title", label: "What you did", placeholder: "Ranked 3rd of 400 teams", half: true },
      { key: "context", label: "Where", placeholder: "NUCES Hackathon", half: true },
      { key: "date", label: "Date", kind: "month", half: true },
      { key: "note", label: "Note", placeholder: "Built the routing engine", half: true },
    ],
    bullets: false,
    teaches: "Things you produced: a ranking, a placing, a record. Lead with the number.",
  },
  sections: {
    label: "Other sections",
    singular: "section",
    blank: () => ({ id: "", title: "", text: "", bullets: [] }),
    fields: [
      { key: "title", label: "Heading", placeholder: "Selected Publications" },
      {
        key: "text",
        label: "Paragraph",
        kind: "prose",
        placeholder: "Leave empty if this section is a list.",
      },
    ],
    bullets: true,
    teaches:
      "Anything the eight above have no name for, kept and printed exactly as you write it — heading and all.",
  },
};

const TABS = ["basics", "summary", ...Object.keys(SECTIONS)] as const;
type Tab = (typeof TABS)[number];

const TAB_LABELS: Record<Tab, string> = {
  basics: "Contact",
  summary: "Summary",
  experience: "Experience",
  projects: "Projects",
  education: "Education",
  skills: "Skills",
  certifications: "Certifications",
  awards: "Honors",
  achievements: "Achievements",
  sections: "Other",
};

export function ProfileScreen() {
  const shell = useShell();
  const [params, setParams] = useSearchParams();
  const { profile, edit, save, dirty, saving, quality } = useStore(useShallow((s) => ({
    profile: s.profile,
    edit: s.edit,
    save: s.save,
    dirty: s.dirty,
    saving: s.saving,
    quality: s.quality,
  })));

  const requested = params.get("section") as Tab | null;
  const tab: Tab = requested && TABS.includes(requested) ? requested : "basics";
  const marker = useSlidingMarker<HTMLElement>(tab, '[data-tab-active="yes"]', "x");
  const focus = params.get("focus");

  /**
   * Land on the exact line the Health screen sent you to.
   *
   * The tab comes from the same query string, so by the time this runs the
   * right section has already rendered and the node exists. The parameter is
   * dropped afterwards: it describes one arrival, and leaving it in the URL
   * would re-focus the field on every later render and fight the cursor.
   */
  useEffect(() => {
    if (!focus) return;
    const field = document.querySelector<HTMLTextAreaElement>(`[data-block-id="${focus}"]`);
    if (field) {
      field.scrollIntoView({ block: "center", behavior: "smooth" });
      field.focus({ preventScroll: true });
      // Focus alone is a thin outline that is easy to miss after a scroll.
      field.classList.add("ring-2", "ring-accent");
      setTimeout(() => field.classList.remove("ring-2", "ring-accent"), 1800);
    }
    const next = new URLSearchParams(params);
    next.delete("focus");
    setParams(next, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus]);

  if (!profile) return null;

  const counts: Record<string, number> = Object.fromEntries(
    Object.keys(SECTIONS).map((key) => [
      key,
      (profile as unknown as Record<string, unknown[]>)[key]?.length ?? 0,
    ]),
  );
  const filled = (key: Tab) =>
    key === "basics"
      ? Boolean(profile.basics.name && profile.basics.email)
      : key === "summary"
        ? Boolean(profile.summary.text.trim())
        : (counts[key] ?? 0) > 0;

  const done = TABS.filter(filled).length;

  return (
    <>
      <TopBar
        title={profile.basics.name || "Your profile"}
        subtitle={
          <>
            {profile.basics.headline || "Everything you have done, in one place"}
            {quality ? ` · ${quality.bullets} bullets · ${done}/${TABS.length} sections` : ""}
          </>
        }
        sidebarHidden={shell.sidebarHidden}
        onShowSidebar={shell.showSidebar}
        onOpenPalette={shell.openPalette}
        action={
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => void save()}
            disabled={!dirty || saving}
          >
            {saving ? "Saving" : dirty ? "Save changes" : "Saved"}
          </button>
        }
        below={
          <nav
            ref={marker.listRef}
            aria-label="Profile sections"
            className="relative flex gap-1 overflow-x-auto border-t border-line px-4 py-2 sm:px-6"
          >
        {/* One highlight for nine tabs, sliding between them -- the same
            handling as the sidebar, and the same reason: a background that
            switches off there and on here is a cut, and the eye cannot follow
            a cut. Absolutely positioned inside the scroller, so it scrolls
            with the tabs rather than floating over them. */}
        {marker.box && (
          <span
            aria-hidden
            className="pointer-events-none absolute top-2 rounded-md bg-accent-soft"
            style={{ ...markerStyle(marker.box, marker.animate, "x"), height: "calc(100% - 1rem)" }}
          />
        )}
        {TABS.map((key) => {
          const active = key === tab;
          return (
            <button
              key={key}
              type="button"
              data-tab-active={active ? "yes" : undefined}
              onClick={() => setParams(key === "basics" ? {} : { section: key })}
              className={[
                "relative z-10 flex shrink-0 items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm",
                MARKER_COLOUR_CLASS,
                active ? "font-semibold text-accent" : "text-muted hover:bg-sunken hover:text-ink",
              ].join(" ")}
            >
              {TAB_LABELS[key]}
              {counts[key] ? (
                <span className="text-2xs text-faint">{counts[key]}</span>
              ) : filled(key) ? null : (
                <span
                  aria-label="empty"
                  className="h-1.5 w-1.5 rounded-full border border-line-strong"
                />
              )}
            </button>
          );
        })}
          </nav>
        }
      />

      <div className="mx-auto w-full max-w-4xl flex-1 p-6">
        <SampleChip />
        {isBlank(profile) && tab === "basics" && <FirstRun />}
        {tab === "basics" && <ContactForm profile={profile} edit={edit} />}
        {tab === "summary" && <SummaryForm profile={profile} edit={edit} />}
        {tab !== "basics" && tab !== "summary" && (
          <EntryList section={tab as ListSection} profile={profile} edit={edit} />
        )}
      </div>
    </>
  );
}

/**
 * The first thing a stranger sees, and the three things they can do about it.
 *
 * The middle one matters most. Every screen in this app is only legible with
 * real material in it -- the templates need a long job title to show how they
 * wrap, the writing standard needs bullets that pass and fail it, the posting
 * reader needs skills to match against. Asking someone to type their whole
 * career before any of that is visible is asking them to take the app on
 * trust, so there is a worked example one press away.
 */
function FirstRun() {
  const loadSample = useStore((s) => s.loadSample);

  return (
    <div className="card mb-5 border-l-2 border-l-accent p-5">
      <h2 className="font-display text-lg">Start here</h2>
      <p className="mt-1 max-w-prose text-sm text-muted">
        This profile is the one place everything lives in full. Tailoring later cuts and re-angles
        this material — it never invents any, so whatever is missing here cannot reach a resume.
      </p>

      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <Start
          icon={<Download size={16} />}
          title="Import a resume"
          body="A LinkedIn export, a PDF, a DOCX, or pasted text. Usually faster than typing, and you correct it afterwards."
          action={
            <Link to="/import" className="btn btn-primary w-full justify-center">
              Import
            </Link>
          }
        />
        <Start
          icon={<Sparkles size={16} />}
          title="Try the sample"
          body="A worked profile to explore the templates, the tailoring and a real PDF with. Clear it whenever you like."
          action={
            <button
              type="button"
              className="btn w-full justify-center"
              onClick={() => void loadSample()}
            >
              Load the sample
            </button>
          }
        />
        <Start
          icon={<PenLine size={16} />}
          title="Start clean"
          body="Fill in your contact details, then add one role under Experience. The rest follows from there."
          action={
            <button
              type="button"
              className="btn w-full justify-center"
              onClick={() => {
                const name = document.getElementById("field-name");
                name?.scrollIntoView({ block: "center", behavior: "smooth" });
                (name as HTMLInputElement | null)?.focus();
              }}
            >
              Type it in
            </button>
          }
        />
      </div>
    </div>
  );
}

function Start({
  icon,
  title,
  body,
  action,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
  action: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5 rounded-md border border-line p-3">
      <span className="text-accent">{icon}</span>
      <h3 className="text-sm font-semibold">{title}</h3>
      <p className="min-h-0 flex-1 text-xs text-muted">{body}</p>
      <div className="mt-1">{action}</div>
    </div>
  );
}

/**
 * A quiet reminder that what is on screen is not yours.
 *
 * It survives a reload, because someone who loads the sample, closes the tab
 * and comes back would otherwise find a stranger's CV and no obvious way to
 * get rid of it. Two ways out on purpose: clear it, or dismiss the chip and
 * keep editing -- building on the sample is a reasonable thing to do, and a
 * chip that only offers deletion punishes it.
 */
function SampleChip() {
  const { sampleLoaded, clearProfile, dismissSample } = useStore(
    useShallow((s) => ({
      sampleLoaded: s.sampleLoaded,
      clearProfile: s.clearProfile,
      dismissSample: s.dismissSample,
    })),
  );
  if (!sampleLoaded) return null;

  return (
    <div className="mb-4 flex flex-wrap items-center gap-2 rounded-md border border-line bg-sunken px-3 py-2 text-xs">
      <Sparkles size={13} className="shrink-0 text-accent" />
      <span className="min-w-0 flex-1 text-muted">
        You are looking at the sample profile, not your own.
      </span>
      <button type="button" className="btn py-1 text-xs" onClick={() => void clearProfile()}>
        Clear it
      </button>
      <button
        type="button"
        className="btn btn-quiet py-1 text-xs"
        onClick={dismissSample}
        title="Keep this material and stop showing the reminder"
      >
        I am building on it
      </button>
    </div>
  );
}

/* -------------------------------------------------------------------------
   Fields
   ---------------------------------------------------------------------- */

function Field({
  label,
  children,
  half,
}: {
  label: string;
  children: React.ReactNode;
  half?: boolean;
}) {
  return (
    <label className={half ? "sm:col-span-1" : "sm:col-span-2"}>
      <span className="label">{label}</span>
      {children}
    </label>
  );
}

function TextInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className="field" />;
}

/** The schema's own date rule, mirrored so the field can check before saving. */
const MONTH_RE = /^\d{4}(-(0[1-9]|1[0-2]))?$/;

const MONTH_NAMES = [
  "jan", "feb", "mar", "apr", "may", "jun",
  "jul", "aug", "sep", "oct", "nov", "dec",
];

/**
 * Read a typed or pasted date, or return null if it is not one yet.
 *
 * Day-first ("06/2025", "15/06/2025") because that is the convention here,
 * but year-first and month names are accepted too: this field is most often
 * filled by pasting out of an existing CV, and refusing "June 2025" would be
 * pedantry. Strict about what it returns -- only the two shapes the schema
 * accepts ever leave here.
 *
 * A day is read and discarded. The schema stores months, because that is what
 * a resume states; keeping "15" would be storing a fact the CV will never
 * print. The field redisplays "06/2025" straight after, so the loss is
 * visible rather than silent.
 */
function normaliseMonth(text: string): string | null {
  let s = text
    .toLowerCase()
    .replace(/[‐-―−]/g, "-") // dashes pasted out of Word
    .replace(/[.,]/g, "-")
    .trim();

  for (const [index, name] of MONTH_NAMES.entries()) {
    // "june 2025" and "jun-2025" both reduce to "2025-06".
    const named = new RegExp(`^${name}[a-z]*[\\s\\-/]+(\\d{4})$|^(\\d{4})[\\s\\-/]+${name}[a-z]*$`);
    const hit = named.exec(s);
    if (hit) return `${hit[1] ?? hit[2]}-${String(index + 1).padStart(2, "0")}`;
  }

  s = s.replace(/\s+/g, "/").replace(/-/g, "/").replace(/\/+/g, "/").replace(/^\/|\/$/g, "");
  if (!s) return null;

  const month = (value: string) => {
    const n = Number(value);
    return n >= 1 && n <= 12 ? String(n).padStart(2, "0") : null;
  };

  // A bare year is a valid date at the precision actually known.
  if (/^\d{4}$/.test(s)) return s;

  // dd/mm/yyyy -- the day is read so the input is accepted, then dropped.
  const withDay = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(s);
  if (withDay) {
    const m = month(withDay[2]!);
    return m && Number(withDay[1]) >= 1 && Number(withDay[1]) <= 31 ? `${withDay[3]}-${m}` : null;
  }

  // Two numbers: whichever is four digits is the year, so "06/2025" and
  // "2025/06" both work and neither can be misread as the other.
  const pair = /^(\d{1,4})\/(\d{1,4})$/.exec(s);
  if (pair) {
    const [, a, b] = pair;
    if (a!.length === 4) {
      const m = month(b!);
      return m ? `${a}-${m}` : null;
    }
    if (b!.length === 4) {
      const m = month(a!);
      return m ? `${b}-${m}` : null;
    }
  }
  return null;
}

/** The stored "2025-06" as the "06/2025" this dashboard shows. */
function displayMonth(stored: string | null): string {
  if (!stored) return "";
  if (MONTH_RE.test(stored) && stored.length === 7) {
    const [year, month] = stored.split("-");
    return `${month}/${year}`;
  }
  return stored;
}

/**
 * A month, stored as "YYYY-MM" or "YYYY".
 *
 * `<input type="month">` looks tidy and cannot express a year-only date,
 * which the schema deliberately allows: LinkedIn stores plenty of them, and
 * turning "2024" into January 2024 is inventing a fact.
 *
 * The text being typed is held here rather than in the profile. Typing
 * "2025-06" passes through "2025-", which is not a date, and writing that to
 * the profile meant autosave posted it and the server rejected the whole save
 * with a regex for a message. The draft is committed only once it parses, so
 * a half-typed date is now simply a half-typed date.
 */
function MonthInput({
  value,
  onChange,
  placeholder,
}: {
  value: string | null;
  onChange: (value: string | null) => void;
  placeholder?: string;
}) {
  const [draft, setDraft] = useState(displayMonth(value));

  // Follow the value when it changes underneath: an undo, an import, or the
  // read-back after a save. Compared on the parsed value so that what is being
  // typed is not rewritten mid-keystroke.
  useEffect(() => {
    if (normaliseMonth(draft) !== value) setDraft(displayMonth(value));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  const invalid = draft.trim() !== "" && normaliseMonth(draft) === null;

  return (
    <div>
      <input
        className="field font-mono"
        value={draft}
        placeholder={placeholder ?? "06/2025 or 2025"}
        aria-invalid={invalid}
        onChange={(event) => {
          const text = event.target.value;
          setDraft(text);
          if (text.trim() === "") onChange(null);
          else {
            const parsed = normaliseMonth(text);
            if (parsed) onChange(parsed);
          }
        }}
        onBlur={() => {
          // Tidy up on the way out: "6/2025", "2025-06" and "June 2025" all
          // settle to "06/2025", and a typed day disappears here rather than
          // quietly at save time. Anything unreadable stays on screen, marked,
          // rather than being discarded.
          const parsed = normaliseMonth(draft);
          if (parsed) setDraft(displayMonth(parsed));
        }}
        inputMode="numeric"
      />
      {invalid && (
        <p className="mt-1 text-2xs text-poor">Not saved yet. Use 06/2025, or 2025 for a year.</p>
      )}
    </div>
  );
}

/**
 * A comma-separated list, held as text while it is being typed.
 *
 * The obvious version -- render `value.join(", ")`, split on every keystroke --
 * cannot accept a comma. Typing one makes a trailing empty item, `filter`
 * drops it, the list re-renders without it, and the character disappears the
 * instant it is pressed. Same for the space after it, and for any item you try
 * to edit in the middle.
 *
 * So the draft is the input's own state. The parsed list still goes to the
 * profile on every change, because the preview and the save both want it; the
 * text on screen is simply left alone until focus leaves.
 */
function CsvInput({
  value,
  onChange,
  placeholder,
}: {
  value: string[];
  onChange: (value: string[]) => void;
  placeholder?: string;
}) {
  const [draft, setDraft] = useState(value.join(", "));

  // Follow the value when it changes from somewhere else: an undo, an import,
  // or the read-back after a save. Comparing the parsed lists rather than the
  // strings means the user's own spacing is not overwritten while they type.
  useEffect(() => {
    const shown = draft.split(",").map((p) => p.trim()).filter(Boolean);
    if (shown.join("\u0000") !== value.join("\u0000")) setDraft(value.join(", "));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  return (
    <input
      className="field"
      value={draft}
      placeholder={placeholder}
      onChange={(event) => {
        setDraft(event.target.value);
        onChange(
          event.target.value
            .split(",")
            .map((part) => part.trim())
            .filter(Boolean),
        );
      }}
      onBlur={() => setDraft(value.join(", "))}
    />
  );
}

/* -------------------------------------------------------------------------
   Contact and summary
   ---------------------------------------------------------------------- */

/** The store's `edit`. The label names the step in the history panel. */
type Edit = (mutate: (profile: Profile) => void, label?: string) => void;

function ContactForm({ profile, edit }: { profile: Profile; edit: Edit }) {
  const basics = profile.basics;
  return (
    <section className="card p-5">
      <h2 className="mb-4 font-display text-lg">Contact details</h2>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Full name" half>
          {/* Named so "Start clean" can put the cursor here: a button that
              says it will start you typing has to actually do that. */}
          <TextInput
            id="field-name"
            value={basics.name}
            onChange={(e) => edit((d) => void (d.basics.name = e.target.value))}
          />
        </Field>
        <Field label="Headline" half>
          <TextInput
            value={basics.headline}
            placeholder="Second-year CS & AI student"
            onChange={(e) => edit((d) => void (d.basics.headline = e.target.value))}
          />
        </Field>
        <Field label="Email" half>
          <TextInput
            type="email"
            value={basics.email}
            onChange={(e) => edit((d) => void (d.basics.email = e.target.value))}
          />
        </Field>
        <Field label="Phone" half>
          <TextInput
            value={basics.phone}
            onChange={(e) => edit((d) => void (d.basics.phone = e.target.value))}
          />
        </Field>
        <Field label="Location" half>
          <TextInput
            value={basics.location}
            placeholder="Manchester, UK"
            onChange={(e) => edit((d) => void (d.basics.location = e.target.value))}
          />
        </Field>
      </div>

      <div className="mt-5">
        <span className="label">Links</span>
        <div className="flex flex-col gap-2">
          {basics.links.map((link, index) => (
            <div key={link.id || index} className="flex gap-2">
              <input
                className="field sm:w-48"
                placeholder="GitHub"
                value={link.label}
                onChange={(e) => edit((d) => void (d.basics.links[index]!.label = e.target.value))}
              />
              <input
                className="field flex-1"
                placeholder="github.com/you"
                value={link.url}
                onChange={(e) => edit((d) => void (d.basics.links[index]!.url = e.target.value))}
              />
              <button
                type="button"
                className="btn btn-quiet px-2"
                aria-label="Remove link"
                onClick={() => edit((d) => void d.basics.links.splice(index, 1))}
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
          <button
            type="button"
            className="btn self-start"
            onClick={() =>
              edit((d) => void d.basics.links.push({ id: "", label: "", url: "" }))
            }
          >
            <Plus size={14} />
            Add link
          </button>
        </div>
      </div>
    </section>
  );
}

/** Words as a reader counts them: the three marks are not language. */
function words(text: string): number {
  return text.replace(/<\/?[biu]>/gi, "").trim().split(/\s+/).filter(Boolean).length;
}

function SummaryForm({ profile, edit }: { profile: Profile; edit: Edit }) {
  const text = profile.summary.text;
  return (
    <section className="card p-5">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <h2 className="font-display text-lg">Summary</h2>
          <p className="mt-1 max-w-prose text-sm text-muted">
            Three or four lines. What you work on, what you have built, and what you are looking
            for — named specifically enough that nobody else could have written it.
          </p>
        </div>
        <AiSuggest
          kind="summary"
          onInsert={(text) => edit((d) => void (d.summary.text = text))}
        />
      </div>
      <RichText
        blockId={profile.summary.id}
        ariaLabel="Summary"
        className="mt-4 min-h-32 leading-relaxed transition-shadow duration-300"
        value={text}
        onChange={(next) => edit((d) => void (d.summary.text = next))}
        placeholder="Computer Science and AI undergraduate who ships working tools…"
      />
      {/* Counted on the words, not the characters stored. A bolded number is
          one word however many tags are wrapped around it. */}
      <p className="mt-1 text-xs text-faint">{words(text)} words</p>
    </section>
  );
}

/* -------------------------------------------------------------------------
   List sections
   ---------------------------------------------------------------------- */

function EntryList({
  section,
  profile,
  edit,
}: {
  section: ListSection;
  profile: Profile;
  edit: Edit;
}) {
  const spec = SECTIONS[section];
  const entries = (profile as unknown as Record<string, Record<string, unknown>[]>)[section] ?? [];
  // Every tag already in the profile, so the suggestions are the person's own
  // vocabulary rather than a fixed list -- and so `backend`, `back-end` and
  // `Backend` do not quietly become three job families.
  const known = tagsInUse(profile as never);

  const mutate = (index: number, key: string, value: unknown, label?: string) =>
    edit(
      (draft) => {
        const list = (draft as unknown as Record<string, Record<string, unknown>[]>)[section]!;
        list[index]![key] = value;
      },
      // Per field by default, so typing in one box coalesces into one step and
      // moving to the next box starts a new one. A caller with a better name
      // for what it did says so -- a bullet reorder sharing a label with the
      // typing that preceded it meant one Ctrl+Z undid both.
      label ?? `Edited ${spec.singular} ${index + 1}`,
    );

  const move = (start: number, end: number) =>
    edit((draft) => {
      moveWithin((draft as unknown as Record<string, unknown[]>)[section]!, start, end);
    }, `Moved a ${spec.singular}`);

  const { dragging, over, listRef, startDrag } = useReorder(move);

  return (
    <section ref={listRef} className="flex flex-col gap-4">
      <header className="flex items-baseline gap-3">
        <h2 className="font-display text-lg">{spec.label}</h2>
        {spec.teaches && <p className="text-sm text-muted">{spec.teaches}</p>}
      </header>

      {entries.length === 0 && (
        <div className="card p-8 text-center">
          <p className="font-display text-lg">No {spec.label.toLowerCase()} yet</p>
          <p className="mx-auto mt-1 max-w-sm text-sm text-muted">
            {spec.teaches || `Add your first ${spec.singular}.`}
          </p>
          <button
            type="button"
            className="btn btn-primary mt-4"
            onClick={() =>
              edit((draft) => {
                const list = (draft as unknown as Record<string, unknown[]>)[section]!;
                list.push(spec.blank());
              }, `Added a ${spec.singular}`)
            }
          >
            <Plus size={15} />
            Add {spec.singular}
          </button>
        </div>
      )}

      {entries.map((entry, index) => (
        <article
          key={(entry.id as string) || index}
          data-reorder-index={index}
          className={[
            "card p-4 transition-all duration-150",
            dragging === index ? "opacity-50" : "",
            over === index && dragging !== null && dragging !== index
              ? "ring-2 ring-accent"
              : "",
          ].join(" ")}
        >
          <div className="mb-3 flex items-center gap-2">
            {/* This used to be decoration: a handle that looks draggable and
                is not is worse than no handle at all. The arrows stay beside
                it, because a drag is unreachable from a keyboard. */}
            <span
              onPointerDown={(event) => startDrag(index, event)}
              title="Drag to reorder, or use the arrows"
              // Without this a touch drag scrolls the page instead.
              style={{ touchAction: "none" }}
              className="cursor-grab text-faint transition-colors duration-150 hover:text-muted active:cursor-grabbing"
            >
              <GripVertical size={14} aria-hidden />
            </span>
            <span className="text-2xs font-semibold uppercase tracking-wide text-faint">
              {spec.singular} {index + 1}
            </span>
            <div className="ml-auto flex items-center gap-1">
              <button
                type="button"
                className="btn btn-quiet px-1.5 py-1"
                disabled={index === 0}
                aria-label={`Move ${spec.singular} ${index + 1} up`}
                onClick={() => move(index, index - 1)}
              >
                ↑
              </button>
              <button
                type="button"
                className="btn btn-quiet px-1.5 py-1"
                disabled={index === entries.length - 1}
                aria-label={`Move ${spec.singular} ${index + 1} down`}
                onClick={() => move(index, index + 1)}
              >
                ↓
              </button>
              <button
                type="button"
                className="btn btn-quiet px-1.5 py-1 text-poor"
                aria-label={`Remove ${spec.singular}`}
                onClick={() =>
                  edit((draft) => {
                    const list = (draft as unknown as Record<string, unknown[]>)[section]!;
                    list.splice(index, 1);
                  }, `Removed a ${spec.singular}`)
                }
              >
                <Trash2 size={14} />
              </button>
            </div>
          </div>

          {section === "skills" && (
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <span className="text-2xs uppercase tracking-wide text-faint">Print this for</span>
              <Tags
                tags={(entry.tags as string[]) ?? []}
                known={known}
                label={`skill group ${index + 1}`}
                onChange={(next) => mutate(index, "tags", next, "Tagged a skill group")}
              />
            </div>
          )}

          <div className="grid gap-3 sm:grid-cols-2">
            {spec.fields.map((field) => {
              const value = entry[field.key];
              if (field.kind === "month") {
                return (
                  <Field key={field.key} label={field.label} half={field.half}>
                    <MonthInput
                      value={(value as string | null) ?? null}
                      placeholder={field.placeholder}
                      onChange={(next) => mutate(index, field.key, next)}
                    />
                  </Field>
                );
              }
              if (field.kind === "csv") {
                return (
                  <Field key={field.key} label={field.label} half={field.half}>
                    <CsvInput
                      value={(value as string[]) ?? []}
                      placeholder={field.placeholder}
                      onChange={(next) => mutate(index, field.key, next)}
                    />
                  </Field>
                );
              }
              if (field.kind === "select") {
                return (
                  <Field key={field.key} label={field.label} half={field.half}>
                    <select
                      className="field"
                      value={String(value ?? "")}
                      onChange={(event) => mutate(index, field.key, event.target.value)}
                    >
                      {(field.options ?? []).map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </select>
                  </Field>
                );
              }
              if (field.kind === "prose") {
                return (
                  <Field key={field.key} label={field.label} half={field.half}>
                    <RichText
                      value={String(value ?? "")}
                      placeholder={field.placeholder}
                      className="min-h-20"
                      onChange={(next) => mutate(index, field.key, next)}
                    />
                  </Field>
                );
              }
              return (
                <Field key={field.key} label={field.label} half={field.half}>
                  <TextInput
                    value={String(value ?? "")}
                    placeholder={field.placeholder}
                    onChange={(event) => mutate(index, field.key, event.target.value)}
                  />
                </Field>
              );
            })}
          </div>

          {spec.bullets && (
            <Bullets
              bullets={(entry.bullets as { id: string; text: string; tags: string[] }[]) ?? []}
              known={known}
              onChange={(next, why) => mutate(index, "bullets", next, why)}
              entryLabel={entryTitle(section, entry)}
              section={section}
              entryId={(entry.id as string) ?? ""}
            />
          )}
        </article>
      ))}

      {entries.length > 0 && (
        <button
          type="button"
          className="btn self-start"
          onClick={() =>
            edit((draft) => {
              const list = (draft as unknown as Record<string, unknown[]>)[section]!;
              list.push(spec.blank());
            })
          }
        >
          <Plus size={15} />
          Add {spec.singular}
        </button>
      )}
    </section>
  );
}

/** What to call this entry when asking for a bullet for it. */
function entryTitle(section: ListSection, entry: Record<string, unknown>): string {
  const parts =
    section === "projects"
      ? [entry.name, entry.tagline]
      : section === "education"
        ? [entry.credential, entry.institution]
        : section === "sections"
          ? [entry.title]
          : [entry.role, entry.organisation];
  return parts.filter(Boolean).join(" — ");
}

/**
 * The bullets of one entry, in the order they will print.
 *
 * Order is editorial, not incidental: the first bullet of a role is the one
 * that gets read, and on a two-page resume the last is the one that falls off
 * the bottom. Entries and sections have reordered since phase 2 and bullets
 * did not, which meant the only way to promote a line was to retype two.
 *
 * Same pair of affordances as everywhere else -- a pointer drag and a pair of
 * arrows -- because a drag is unreachable from a keyboard.
 */
function Bullets({
  bullets,
  known,
  onChange,
  entryLabel,
  section,
  entryId,
}: {
  bullets: { id: string; text: string; tags: string[] }[];
  known: string[];
  onChange: (next: { id: string; text: string; tags: string[] }[], label?: string) => void;
  entryLabel: string;
  section: string;
  entryId: string;
}) {
  const move = (start: number, end: number) => {
    const next = [...bullets];
    moveWithin(next, start, end);
    onChange(next, "Moved a bullet");
  };
  const { dragging, over, listRef, startDrag } = useReorder(move);

  return (
    <div className="mt-4">
      <div className="flex items-center justify-between gap-3">
        <span className="label">Bullets</span>
        {/* Appends rather than replacing: a drafted line is a new bullet, and
            overwriting whichever one happened to be focused would lose work. */}
        <AiSuggest
          kind="bullet"
          entryLabel={entryLabel}
          section={section}
          entryId={entryId}
          onInsert={(text) => onChange([...bullets, { id: "", text, tags: [] }], "Added a drafted bullet")}
        />
      </div>
      <div ref={listRef} className="flex flex-col gap-2">
        {bullets.map((bullet, index) => (
          <div
            key={bullet.id || index}
            data-reorder-index={index}
            className={[
              "flex items-start gap-2 rounded-md transition-all duration-150",
              dragging === index ? "opacity-50" : "",
              over === index && dragging !== null && dragging !== index
                ? "ring-2 ring-accent"
                : "",
            ].join(" ")}
          >
            {/* The dot was decoration. It is the handle now -- the row needs
                somewhere to grab that is not the writing area, and a bullet
                already has a mark at its head. */}
            <span
              onPointerDown={(event) => startDrag(index, event)}
              title="Drag to reorder, or use the arrows"
              // Without this a touch drag scrolls the page instead.
              style={{ touchAction: "none" }}
              className="mt-2.5 cursor-grab p-1 text-faint transition-colors duration-150 hover:text-muted active:cursor-grabbing"
            >
              <GripVertical size={13} aria-hidden />
            </span>
            <div className="flex min-w-0 flex-1 flex-col gap-1">
              <RichText
                blockId={bullet.id}
                ariaLabel={`Bullet ${index + 1}`}
                className="min-h-16 transition-shadow duration-300"
                value={bullet.text}
                placeholder="Cut nightly ETL runtime from 42 minutes to 9 by batching Postgres writes"
                onChange={(next) =>
                  onChange(bullets.map((b, i) => (i === index ? { ...b, text: next } : b)))
                }
              />
              <Tags
                tags={bullet.tags ?? []}
                known={known}
                label={`bullet ${index + 1}`}
                onChange={(tags) =>
                  onChange(
                    bullets.map((b, i) => (i === index ? { ...b, tags } : b)),
                    "Tagged a bullet",
                  )
                }
              />
            </div>
            <div className="mt-1 flex shrink-0 items-center gap-0.5">
              <button
                type="button"
                className="btn btn-quiet px-1.5 py-1"
                disabled={index === 0}
                aria-label={`Move bullet ${index + 1} up`}
                onClick={() => move(index, index - 1)}
              >
                ↑
              </button>
              <button
                type="button"
                className="btn btn-quiet px-1.5 py-1"
                disabled={index === bullets.length - 1}
                aria-label={`Move bullet ${index + 1} down`}
                onClick={() => move(index, index + 1)}
              >
                ↓
              </button>
              <button
                type="button"
                className="btn btn-quiet px-1.5 py-1 text-poor"
                aria-label={`Remove bullet ${index + 1}`}
                onClick={() => onChange(bullets.filter((_, i) => i !== index), "Removed a bullet")}
              >
                <Trash2 size={14} />
              </button>
            </div>
          </div>
        ))}
        <button
          type="button"
          className="btn self-start"
          onClick={() => onChange([...bullets, { id: "", text: "", tags: [] }], "Added a bullet")}
        >
          <Plus size={14} />
          Add bullet
        </button>
      </div>
    </div>
  );
}
