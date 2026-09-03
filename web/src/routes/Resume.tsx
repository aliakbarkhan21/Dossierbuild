/**
 * Pick a look, watch the page, print it.
 *
 * The preview is the same HTML the printer gets, rendered by the same engine,
 * and it updates 250ms after you stop typing rather than on every keystroke.
 * Everything on the left changes one thing and shows the result immediately.
 */

import { Download, FileCode2, FileType2, Loader2, RotateCcw, Trash2, Upload } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { useShell } from "../App";
import { Frame } from "../components/Frame";
import { TopBar } from "../components/TopBar";
import { ApiError, api, download } from "../lib/api";
import { useShallow } from "zustand/react/shallow";

import { useStore } from "../lib/store";
import { toast } from "../lib/toast";
import type { Design, FitReport, Profile, TemplateOption } from "../lib/types";

const ZOOMS = [
  { label: "Fit", value: 0 },
  { label: "100%", value: 1 },
  { label: "150%", value: 1.5 },
];

const FILTERS = [
  { label: "All", test: () => true },
  { label: "ATS-safe", test: (t: TemplateOption) => t.ats },
  { label: "Two columns", test: (t: TemplateOption) => !t.ats },
  { label: "Portrait", test: (t: TemplateOption) => t.photo },
];

/** Re-render the document a beat after the last change, never during it. */
function useDebounced<T>(value: T, ms: number): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return settled;
}

export function ResumeScreen() {
  const shell = useShell();
  const { profile, design, options, setDesign, edit } = useStore(useShallow((s) => ({
    profile: s.profile,
    design: s.design,
    options: s.options,
    setDesign: s.setDesign,
    edit: s.edit,
  })));

  const [zoom, setZoom] = useState(0);
  const [filter, setFilter] = useState("All");
  const [preview, setPreview] = useState("");
  const [thumbs, setThumbs] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<"pdf" | "html" | "text" | null>(null);
  const [report, setReport] = useState<FitReport | null>(null);

  // Two keys, because the two renders have different reasons to be redone:
  // the preview follows every edit, the thumbnails only follow the design.
  const previewKey = useDebounced(
    JSON.stringify({ profile, design, zoom }),
    250,
  );
  const galleryKey = useDebounced(JSON.stringify({ design, name: profile?.basics.name }), 400);

  const inFlight = useRef(0);

  useEffect(() => {
    if (!profile || !design) return;
    const ticket = ++inFlight.current;
    api
      .preview({ profile, design, zoom })
      .then((html) => {
        // A slow render that finished after a newer one must not overwrite it.
        if (ticket === inFlight.current) setPreview(html);
      })
      .catch((error: unknown) => {
        if (error instanceof ApiError) toast.error(error.message, error.fix);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [previewKey]);

  useEffect(() => {
    if (!profile || !design || !options) return;
    let cancelled = false;
    Promise.all(
      options.templates.map(async (template) => {
        const html = await api.thumbnail({ profile, design, template: template.key, zoom: 0 });
        return [template.key, html] as const;
      }),
    )
      .then((pairs) => {
        if (!cancelled) setThumbs(Object.fromEntries(pairs));
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [galleryKey]);

  const shown = useMemo(() => {
    const rule = FILTERS.find((f) => f.label === filter) ?? FILTERS[0]!;
    return (options?.templates ?? []).filter((t) => rule.test(t));
  }, [options, filter]);

  if (!profile || !design || !options) return null;

  const template = options.templates.find((t) => t.key === design.template);

  async function buildPdf() {
    setBusy("pdf");
    try {
      const result = await api.pdf({ profile: profile!, design: design! });
      download(result.blob, result.filename);
      setReport({
        pages: result.pages,
        words: result.words,
        size_kb: Math.round(result.blob.size / 1024),
        machine_readable: result.machineReadable,
        found: {},
        missing: [],
        sections: [],
      });
      toast.success(
        `${result.filename} downloaded`,
        `${result.pages} page${result.pages === 1 ? "" : "s"} · ${Math.round(result.blob.size / 1024)} KB`,
      );
    } catch (error) {
      if (error instanceof ApiError) toast.error(error.message, error.fix);
      else toast.error("Could not print the PDF.");
    } finally {
      setBusy(null);
    }
  }

  async function checkFit() {
    try {
      const result = await api.report({ profile: profile!, design: design! });
      setReport(result);
      if (result.missing.length) {
        toast.error(
          `Not found in the PDF's text layer: ${result.missing.join(", ")}`,
          "A parser will not find them either.",
        );
      } else {
        toast.success(
          `${result.pages} page${result.pages === 1 ? "" : "s"}`,
          "Name, email and phone all readable by a machine.",
        );
      }
    } catch (error) {
      if (error instanceof ApiError) toast.error(error.message, error.fix);
    }
  }

  async function downloadHtml() {
    setBusy("html");
    try {
      const html = await api.printHtml({ profile: profile!, design: design! });
      download(new Blob([html], { type: "text/html" }), "Resume.html");
      toast.success("Resume.html downloaded", "One self-contained file.");
    } catch (error) {
      if (error instanceof ApiError) toast.error(error.message, error.fix);
    } finally {
      setBusy(null);
    }
  }

  async function downloadText() {
    setBusy("text");
    try {
      const text = await api.plainText({ profile: profile!, design: design! });
      download(new Blob([text], { type: "text/plain" }), "Profile.txt");
      toast.success("Profile.txt downloaded", "Everything you have, for pasting into a form.");
    } catch (error) {
      if (error instanceof ApiError) toast.error(error.message, error.fix);
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <TopBar
        title="Resume"
        subtitle={
          <>
            {template?.name} · {options.pages.find((p) => p.key === design.page)?.name}
            {report && ` · ${report.pages} page${report.pages === 1 ? "" : "s"}`}
          </>
        }
        sidebarHidden={shell.sidebarHidden}
        onShowSidebar={shell.showSidebar}
        onOpenPalette={shell.openPalette}
        action={
          <button type="button" className="btn btn-primary" onClick={buildPdf} disabled={busy !== null}>
            {busy === "pdf" ? <Loader2 size={15} className="animate-spin" /> : <Download size={15} />}
            Download PDF
          </button>
        }
      />

      <div className="grid flex-1 gap-6 p-6 xl:grid-cols-[minmax(0,340px)_minmax(0,1fr)]">
        <div className="flex min-w-0 flex-col gap-5">
          <Looks design={design} options={options} onPick={setDesign} />

          <section>
            <div className="mb-2 flex items-center justify-between gap-3">
              <h2 className="text-sm font-semibold">Template</h2>
              <div className="flex gap-0.5 rounded-md bg-sunken p-0.5">
                {FILTERS.map((f) => (
                  <button
                    key={f.label}
                    type="button"
                    onClick={() => setFilter(f.label)}
                    className={[
                      "rounded px-2 py-1 text-2xs font-medium transition-colors duration-150",
                      filter === f.label ? "bg-surface text-ink shadow-subtle" : "text-muted hover:text-ink",
                    ].join(" ")}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              {shown.map((t) => (
                <TemplateCard
                  key={t.key}
                  template={t}
                  html={thumbs[t.key] ?? ""}
                  selected={t.key === design.template}
                  onPick={() => setDesign({ template: t.key })}
                />
              ))}
            </div>
          </section>

          <DesignPanel
            design={design}
            options={options}
            profile={profile}
            onChange={setDesign}
            onProfile={edit}
          />
        </div>

        <div className="flex min-w-0 flex-col gap-3">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold">Preview</h2>
            <div className="ml-auto flex gap-0.5 rounded-md bg-sunken p-0.5">
              {ZOOMS.map((z) => (
                <button
                  key={z.label}
                  type="button"
                  onClick={() => setZoom(z.value)}
                  className={[
                    "rounded px-2 py-1 text-2xs font-medium transition-colors duration-150",
                    zoom === z.value ? "bg-surface text-ink shadow-subtle" : "text-muted hover:text-ink",
                  ].join(" ")}
                >
                  {z.label}
                </button>
              ))}
            </div>
            <button type="button" className="btn" onClick={checkFit}>
              Check fit
            </button>
            <button type="button" className="btn" onClick={downloadHtml} disabled={busy !== null}>
              <FileCode2 size={14} />
              HTML
            </button>
            <button
              type="button"
              className="btn"
              onClick={downloadText}
              disabled={busy !== null}
              title="Your whole profile as text, for forms that take no file"
            >
              <FileType2 size={14} />
              Text
            </button>
          </div>

          <Frame
            html={preview}
            title="Resume preview"
            className="card min-h-[70vh] flex-1 overflow-hidden"
            placeholder={
              <div className="absolute inset-0 animate-pulse rounded-lg bg-sunken" aria-hidden />
            }
          />

          {report && report.found && Object.keys(report.found).length > 0 && (
            <div className="card flex flex-wrap items-center gap-x-4 gap-y-1 border-l-2 border-l-accent p-3 text-xs">
              <span className="font-medium">
                {report.pages} page{report.pages === 1 ? "" : "s"}
              </span>
              <span className="text-muted">{report.words} words</span>
              <span className="text-muted">{report.size_kb} KB</span>
              {Object.entries(report.found).map(([label, ok]) => (
                <span key={label} className={ok ? "text-good" : "text-poor"}>
                  {ok ? "✓" : "✗"} {label}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function Looks({
  design,
  options,
  onPick,
}: {
  design: Design;
  options: { looks: { key: string; name: string; blurb: string; values: Partial<Design> }[] };
  onPick: (patch: Partial<Design>) => void;
}) {
  const matches = (values: Partial<Design>) =>
    Object.entries(values).every(
      ([key, value]) => JSON.stringify(design[key as keyof Design]) === JSON.stringify(value),
    );

  return (
    <section>
      <h2 className="mb-2 text-sm font-semibold">Start from a look</h2>
      <div className="grid grid-cols-3 gap-2">
        {options.looks.map((look) => {
          const active = matches(look.values);
          return (
            <button
              key={look.key}
              type="button"
              title={look.blurb}
              onClick={() => onPick(look.values)}
              className={[
                "btn justify-center",
                active ? "border-accent text-accent" : "",
              ].join(" ")}
            >
              {look.name}
            </button>
          );
        })}
      </div>
    </section>
  );
}

function TemplateCard({
  template,
  html,
  selected,
  onPick,
}: {
  template: TemplateOption;
  html: string;
  selected: boolean;
  onPick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onPick}
      aria-pressed={selected}
      title={template.best_for}
      className={[
        "card group overflow-hidden p-0 text-left transition-all duration-200 ease-out",
        selected
          ? "border-accent ring-2 ring-accent/25"
          : "hover:-translate-y-0.5 hover:border-line-strong hover:shadow-raised",
      ].join(" ")}
    >
      <Frame
        html={html}
        title={`${template.name} preview`}
        className="h-[168px] overflow-hidden border-b border-line bg-white"
        placeholder={<div className="h-full w-full animate-pulse bg-sunken" aria-hidden />}
      />
      <div className="p-2.5">
        <div className="flex items-center gap-1.5">
          <span className="font-display text-sm font-semibold">{template.name}</span>
          {selected && <span className="text-2xs font-semibold text-accent">Selected</span>}
        </div>
        <div className="mt-1 flex flex-wrap gap-1">
          <Badge tone={template.ats ? "good" : "fair"}>
            {template.ats ? "ATS-safe" : "Two-column"}
          </Badge>
          {template.photo && <Badge>Portrait</Badge>}
        </div>
      </div>
    </button>
  );
}

function Badge({ children, tone }: { children: React.ReactNode; tone?: "good" | "fair" }) {
  const cls =
    tone === "good"
      ? "border-good/40 text-good"
      : tone === "fair"
        ? "border-fair/40 text-fair"
        : "border-line text-muted";
  return (
    <span
      className={`rounded border px-1 py-px text-2xs font-semibold uppercase tracking-wide ${cls}`}
    >
      {children}
    </span>
  );
}

function DesignPanel({
  design,
  options,
  profile,
  onChange,
  onProfile,
}: {
  design: Design;
  options: {
    accents: { key: string; name: string; hex: string }[];
    fonts: { key: string; name: string; blurb: string }[];
    pages: { key: string; name: string }[];
    margins: { key: string; name: string; blurb: string }[];
    leading: { key: string; name: string }[];
    date_formats: { key: string; name: string; blurb: string }[];
    sections: { key: string; name: string }[];
    scale: { steps: number[] };
    templates: TemplateOption[];
  };
  profile: Profile;
  onChange: (patch: Partial<Design>) => void;
  onProfile: (mutate: (profile: Profile) => void) => void;
}) {
  const usesPhoto = options.templates.find((t) => t.key === design.template)?.photo ?? false;

  return (
    <section className="card flex flex-col gap-4 p-4">
      <div>
        <span className="label">Accent</span>
        <div className="flex gap-1.5">
          {options.accents.map((accent) => (
            <button
              key={accent.key}
              type="button"
              title={accent.name}
              aria-label={accent.name}
              onClick={() => onChange({ accent: accent.key })}
              style={{ background: accent.hex }}
              className={[
                "h-7 flex-1 rounded-md border transition-transform duration-150 ease-out hover:-translate-y-0.5",
                design.accent === accent.key
                  ? "border-transparent ring-2 ring-accent ring-offset-2 ring-offset-surface"
                  : "border-black/10",
              ].join(" ")}
            />
          ))}
        </div>
      </div>

      <Choice
        label="Typeface"
        value={design.fonts}
        options={options.fonts}
        onChange={(fonts) => onChange({ fonts })}
        note={options.fonts.find((f) => f.key === design.fonts)?.blurb}
      />

      <div className="grid grid-cols-2 gap-3">
        <Choice
          label="Paper"
          value={design.page}
          options={options.pages}
          onChange={(page) => onChange({ page })}
        />
        <Choice
          label="Margins"
          value={design.margin}
          options={options.margins}
          onChange={(margin) => onChange({ margin })}
        />
      </div>

      <Choice
        label="Dates"
        value={design.date_format}
        options={options.date_formats}
        onChange={(date_format) => onChange({ date_format })}
        note={options.date_formats.find((d) => d.key === design.date_format)?.blurb}
      />

      <div className="grid grid-cols-2 gap-3">
        <Choice
          label="Line spacing"
          value={design.leading}
          options={options.leading}
          onChange={(leading) => onChange({ leading })}
        />
        <div>
          <span className="label">Type size</span>
          <div className="flex gap-0.5 rounded-md bg-sunken p-0.5">
            {options.scale.steps.map((step) => (
              <button
                key={step}
                type="button"
                onClick={() => onChange({ scale: step })}
                className={[
                  "flex-1 rounded px-1 py-1 text-2xs font-medium transition-colors duration-150",
                  design.scale === step ? "bg-surface text-ink shadow-subtle" : "text-muted hover:text-ink",
                ].join(" ")}
              >
                {step}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <Toggle
          checked={design.show_links}
          onChange={(show_links) => onChange({ show_links })}
          label="Links in the header"
        />
        <Toggle
          checked={design.show_headline}
          onChange={(show_headline) => onChange({ show_headline })}
          label="Headline under the name"
        />
        <Toggle
          checked={design.show_page_numbers}
          onChange={(show_page_numbers) => onChange({ show_page_numbers })}
          label="Number the pages"
        />
      </div>

      {usesPhoto && (
        <PortraitControls design={design} profile={profile} onChange={onChange} onProfile={onProfile} />
      )}

      <SectionOrder design={design} options={options} profile={profile} onChange={onChange} />

      <button
        type="button"
        className="btn self-start"
        onClick={() =>
          onChange({
            template: "classic",
            accent: "ink",
            fonts: "serif_sans",
            page: "a4",
            margin: "normal",
            leading: "normal",
            date_format: "month",
            scale: 100,
            hidden: [],
            order: options.sections.map((s) => s.key),
          })
        }
      >
        <RotateCcw size={14} />
        Reset design
      </button>
    </section>
  );
}

function Choice({
  label,
  value,
  options,
  onChange,
  note,
}: {
  label: string;
  value: string;
  options: { key: string; name: string }[];
  onChange: (value: string) => void;
  note?: string;
}) {
  return (
    <div>
      <label className="label" htmlFor={`choice-${label}`}>
        {label}
      </label>
      <select
        id={`choice-${label}`}
        className="field"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((option) => (
          <option key={option.key} value={option.key}>
            {option.name}
          </option>
        ))}
      </select>
      {note && <p className="mt-1 text-xs text-muted">{note}</p>}
    </div>
  );
}

function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  label: string;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-2.5 text-sm">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={[
          "relative h-[18px] w-8 shrink-0 rounded-full transition-colors duration-200 ease-out",
          checked ? "bg-accent" : "bg-line-strong",
        ].join(" ")}
      >
        <span
          className="absolute top-[2px] h-[14px] w-[14px] rounded-full bg-white shadow-subtle transition-[left] duration-200 ease-out"
          style={{ left: checked ? 16 : 2 }}
        />
      </button>
      <span className="text-muted">{label}</span>
    </label>
  );
}

function PortraitControls({
  design,
  profile,
  onChange,
  onProfile,
}: {
  design: Design;
  profile: Profile;
  onChange: (patch: Partial<Design>) => void;
  onProfile: (mutate: (profile: Profile) => void) => void;
}) {
  const [busy, setBusy] = useState(false);
  const has = Boolean(profile.basics.photo);

  async function upload(file: File) {
    setBusy(true);
    try {
      const { photo } = await api.uploadPhoto(file);
      onProfile((draft) => {
        draft.basics.photo = photo;
      });
      toast.success("Portrait added");
    } catch (error) {
      if (error instanceof ApiError) toast.error(error.message, error.fix);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <span className="label">Portrait</span>
      <div className="flex items-center gap-2">
        <label className="btn cursor-pointer">
          {busy ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
          {has ? "Replace" : "Add a photo"}
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            className="sr-only"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void upload(file);
              event.target.value = "";
            }}
          />
        </label>
        {has && (
          <button
            type="button"
            className="btn"
            onClick={async () => {
              await api.deletePhoto();
              onProfile((draft) => {
                draft.basics.photo = "";
              });
              toast.info("Portrait removed");
            }}
          >
            <Trash2 size={14} />
          </button>
        )}
        <div className="ml-auto flex gap-0.5 rounded-md bg-sunken p-0.5">
          {(["circle", "square"] as const).map((shape) => (
            <button
              key={shape}
              type="button"
              onClick={() => onChange({ photo_shape: shape })}
              className={[
                "rounded px-2 py-1 text-2xs capitalize transition-colors duration-150",
                design.photo_shape === shape ? "bg-surface text-ink shadow-subtle" : "text-muted",
              ].join(" ")}
            >
              {shape}
            </button>
          ))}
        </div>
      </div>
      {!has && (
        <p className="mt-1.5 text-xs text-muted">
          Conventional on a CV in much of Europe and Asia; discouraged in the US, UK and Canada.
        </p>
      )}
    </div>
  );
}

function SectionOrder({
  design,
  options,
  profile,
  onChange,
}: {
  design: Design;
  options: { sections: { key: string; name: string }[] };
  profile: Profile;
  onChange: (patch: Partial<Design>) => void;
}) {
  const has = (key: string) => {
    if (key === "summary") return Boolean(profile.summary.text.trim());
    const value = (profile as unknown as Record<string, unknown[]>)[key];
    return Array.isArray(value) && value.length > 0;
  };

  const move = (key: string, delta: number) => {
    const order = [...design.order];
    const index = order.indexOf(key);
    const target = Math.max(0, Math.min(order.length - 1, index + delta));
    if (index < 0 || index === target) return;
    order.splice(target, 0, order.splice(index, 1)[0]!);
    onChange({ order });
  };

  const toggle = (key: string) => {
    const hidden = design.hidden.includes(key)
      ? design.hidden.filter((k) => k !== key)
      : [...design.hidden, key];
    onChange({ hidden });
  };

  return (
    <div>
      <span className="label">Sections</span>
      <ul className="flex flex-col divide-y divide-line overflow-hidden rounded-md border border-line">
        {design.order.map((key, index) => {
          const label = options.sections.find((s) => s.key === key)?.name ?? key;
          const shown = !design.hidden.includes(key);
          return (
            <li key={key} className="flex items-center gap-1 px-2 py-1.5 text-sm">
              <span className={shown ? "" : "text-faint line-through"}>{label}</span>
              {!has(key) && <span className="text-2xs text-faint">empty</span>}
              <span className="ml-auto flex items-center gap-0.5">
                <button
                  type="button"
                  className="btn btn-quiet px-1 py-0.5"
                  disabled={index === 0}
                  onClick={() => move(key, -1)}
                  aria-label={`Move ${label} up`}
                >
                  ↑
                </button>
                <button
                  type="button"
                  className="btn btn-quiet px-1 py-0.5"
                  disabled={index === design.order.length - 1}
                  onClick={() => move(key, 1)}
                  aria-label={`Move ${label} down`}
                >
                  ↓
                </button>
                <button
                  type="button"
                  className="btn btn-quiet px-1 py-0.5 text-2xs"
                  onClick={() => toggle(key)}
                >
                  {shown ? "Hide" : "Show"}
                </button>
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
