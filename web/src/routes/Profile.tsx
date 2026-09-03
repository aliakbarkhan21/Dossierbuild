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

import { GripVertical, Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useShell } from "../App";
import { TopBar } from "../components/TopBar";
import { useShallow } from "zustand/react/shallow";

import { isBlank, useStore } from "../lib/store";
import type { ListSection, Profile } from "../lib/types";

type Kind = "text" | "month" | "csv" | "select" | "url";

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
    blank: () => ({ id: "", label: "", items: [] }),
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
            aria-label="Profile sections"
            className="flex gap-1 overflow-x-auto border-t border-line px-6 py-2"
          >
        {TABS.map((key) => {
          const active = key === tab;
          return (
            <button
              key={key}
              type="button"
              onClick={() => setParams(key === "basics" ? {} : { section: key })}
              className={[
                "flex shrink-0 items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm transition-colors duration-150 ease-out",
                active ? "bg-accent-soft font-semibold text-accent" : "text-muted hover:bg-sunken hover:text-ink",
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

function FirstRun() {
  return (
    <div className="card mb-5 border-l-2 border-l-accent p-5">
      <h2 className="font-display text-lg">Start here</h2>
      <p className="mt-1 max-w-prose text-sm text-muted">
        This profile is the one place everything lives in full. Tailoring later cuts and re-angles
        this material — it never invents any, so whatever is missing here cannot reach a resume.
      </p>
      <ol className="mt-3 flex flex-col gap-1 text-sm text-muted">
        <li>
          1. <b className="text-ink">Import</b> an existing resume and correct it — usually faster
          than typing.
        </li>
        <li>
          2. Or fill in <b className="text-ink">Contact</b>, then add one role under Experience.
        </li>
      </ol>
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
 * Generous about separators and month names because the common way this field
 * gets filled is a paste out of a CV, and "June 2025" is a date by any
 * reasonable reading. Strict about what it returns: only the two shapes the
 * schema accepts ever leave here.
 */
function normaliseMonth(text: string): string | null {
  let s = text
    .toLowerCase()
    .replace(/[‐-―−]/g, "-") // dashes pasted out of Word
    .replace(/[/.,]/g, "-")
    .trim();

  for (const [index, name] of MONTH_NAMES.entries()) {
    // "june 2025" and "jun-2025" both reduce to "2025-06".
    const named = new RegExp(`^${name}[a-z]*[\\s-]+(\\d{4})$|^(\\d{4})[\\s-]+${name}[a-z]*$`);
    const hit = named.exec(s);
    if (hit) return `${hit[1] ?? hit[2]}-${String(index + 1).padStart(2, "0")}`;
  }

  s = s.replace(/\s+/g, "-").replace(/-+/g, "-").replace(/^-|-$/g, "");
  if (!s) return null;
  if (MONTH_RE.test(s)) return s;

  // "2025-6" is unambiguous; the schema just wants the zero.
  const loose = /^(\d{4})-(\d{1,2})$/.exec(s);
  if (loose) {
    const month = Number(loose[2]);
    if (month >= 1 && month <= 12) return `${loose[1]}-${String(month).padStart(2, "0")}`;
  }
  return null;
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
  const [draft, setDraft] = useState(value ?? "");

  // Follow the value when it changes underneath: an undo, an import, or the
  // read-back after a save.
  useEffect(() => {
    setDraft(value ?? "");
  }, [value]);

  const invalid = draft.trim() !== "" && normaliseMonth(draft) === null;

  return (
    <div>
      <input
        className="field font-mono"
        value={draft}
        placeholder={placeholder ?? "2025-06 or 2025"}
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
          // Tidy up on the way out: "2025-6" and "June 2025" become the
          // stored shape, and anything unreadable stays on screen, marked,
          // rather than being silently discarded.
          const parsed = normaliseMonth(draft);
          if (parsed) setDraft(parsed);
        }}
        inputMode="numeric"
      />
      {invalid && (
        <p className="mt-1 text-2xs text-poor">Not saved yet. Use 2025-06, or 2025 for a year.</p>
      )}
    </div>
  );
}

function CsvInput({
  value,
  onChange,
  placeholder,
}: {
  value: string[];
  onChange: (value: string[]) => void;
  placeholder?: string;
}) {
  return (
    <input
      className="field"
      value={value.join(", ")}
      placeholder={placeholder}
      onChange={(event) =>
        onChange(
          event.target.value
            .split(",")
            .map((part) => part.trim())
            .filter(Boolean),
        )
      }
    />
  );
}

/* -------------------------------------------------------------------------
   Contact and summary
   ---------------------------------------------------------------------- */

type Edit = (mutate: (profile: Profile) => void) => void;

function ContactForm({ profile, edit }: { profile: Profile; edit: Edit }) {
  const basics = profile.basics;
  return (
    <section className="card p-5">
      <h2 className="mb-4 font-display text-lg">Contact details</h2>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Full name" half>
          <TextInput
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

function SummaryForm({ profile, edit }: { profile: Profile; edit: Edit }) {
  const text = profile.summary.text;
  return (
    <section className="card p-5">
      <h2 className="font-display text-lg">Summary</h2>
      <p className="mt-1 max-w-prose text-sm text-muted">
        Three or four lines. What you work on, what you have built, and what you are looking for —
        named specifically enough that nobody else could have written it.
      </p>
      <textarea
        className="field mt-4 min-h-32 resize-y leading-relaxed"
        value={text}
        onChange={(event) => edit((d) => void (d.summary.text = event.target.value))}
        placeholder="Computer Science and AI undergraduate who ships working tools…"
      />
      <p className="mt-1 text-xs text-faint">{text.trim().split(/\s+/).filter(Boolean).length} words</p>
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

  const mutate = (index: number, key: string, value: unknown) =>
    edit((draft) => {
      const list = (draft as unknown as Record<string, Record<string, unknown>[]>)[section]!;
      list[index]![key] = value;
    });

  return (
    <section className="flex flex-col gap-4">
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
              })
            }
          >
            <Plus size={15} />
            Add {spec.singular}
          </button>
        </div>
      )}

      {entries.map((entry, index) => (
        <article key={(entry.id as string) || index} className="card p-4">
          <div className="mb-3 flex items-center gap-2">
            <GripVertical size={14} className="text-faint" aria-hidden />
            <span className="text-2xs font-semibold uppercase tracking-wide text-faint">
              {spec.singular} {index + 1}
            </span>
            <div className="ml-auto flex items-center gap-1">
              <button
                type="button"
                className="btn btn-quiet px-1.5 py-1"
                disabled={index === 0}
                aria-label="Move up"
                onClick={() =>
                  edit((draft) => {
                    const list = (draft as unknown as Record<string, unknown[]>)[section]!;
                    list.splice(index - 1, 0, list.splice(index, 1)[0]);
                  })
                }
              >
                ↑
              </button>
              <button
                type="button"
                className="btn btn-quiet px-1.5 py-1"
                disabled={index === entries.length - 1}
                aria-label="Move down"
                onClick={() =>
                  edit((draft) => {
                    const list = (draft as unknown as Record<string, unknown[]>)[section]!;
                    list.splice(index + 1, 0, list.splice(index, 1)[0]);
                  })
                }
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
                  })
                }
              >
                <Trash2 size={14} />
              </button>
            </div>
          </div>

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
              bullets={(entry.bullets as { id: string; text: string }[]) ?? []}
              onChange={(next) => mutate(index, "bullets", next)}
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

function Bullets({
  bullets,
  onChange,
}: {
  bullets: { id: string; text: string }[];
  onChange: (next: { id: string; text: string }[]) => void;
}) {
  return (
    <div className="mt-4">
      <span className="label">Bullets</span>
      <div className="flex flex-col gap-2">
        {bullets.map((bullet, index) => (
          <div key={bullet.id || index} className="flex items-start gap-2">
            <span aria-hidden className="mt-3 h-1.5 w-1.5 shrink-0 rounded-full bg-accent/70" />
            <textarea
              className="field min-h-16 flex-1 resize-y"
              value={bullet.text}
              placeholder="Cut nightly ETL runtime from 42 minutes to 9 by batching Postgres writes"
              onChange={(event) => {
                const next = bullets.map((b, i) =>
                  i === index ? { ...b, text: event.target.value } : b,
                );
                onChange(next);
              }}
            />
            <button
              type="button"
              className="btn btn-quiet mt-1 px-1.5 py-1"
              aria-label="Remove bullet"
              onClick={() => onChange(bullets.filter((_, i) => i !== index))}
            >
              <Trash2 size={14} />
            </button>
          </div>
        ))}
        <button
          type="button"
          className="btn self-start"
          onClick={() => onChange([...bullets, { id: "", text: "" }])}
        >
          <Plus size={14} />
          Add bullet
        </button>
      </div>
    </div>
  );
}
