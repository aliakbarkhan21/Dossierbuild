/**
 * Pick a look, watch the page, print it.
 *
 * The preview is the same HTML the printer gets, rendered by the same engine,
 * and it updates 250ms after you stop typing rather than on every keystroke.
 * Everything on the left changes one thing and shows the result immediately.
 */

import {
  Briefcase,
  Check,
  Download,
  PanelLeftClose,
  PanelLeftOpen,
  FileCode2,
  FileType2,
  Loader2,
  Maximize2,
  RotateCcw,
  Trash2,
  Upload,
  X,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { useShell } from "../App";
import { Frame } from "../components/Frame";
import { PhotoCropper } from "../components/PhotoCropper";
import { TopBar } from "../components/TopBar";
import { ApiError, api, download } from "../lib/api";
import { useShallow } from "zustand/react/shallow";
import { tagsInUse } from "../components/Tags";
import { Wireframe } from "../components/Wireframe";

import { useStore } from "../lib/store";
import { toast } from "../lib/toast";
import type {
  Application,
  Design,
  FitReport,
  LookOption,
  Option,
  Profile,
  TemplateOption,
} from "../lib/types";

/** Zoom, as a percentage. 0 is the sentinel for "fit to the pane". */
const ZOOM_MIN = 60;
const ZOOM_MAX = 150;

/** The full-page view goes further both ways: it is where a page is read.
 *
 * Down to 40% puts a two-page resume on screen at once, which is the only
 * place the shape of the whole document is visible. Up to 250% is large
 * enough to check that a line of contact details set two points smaller than
 * the body is still legible on paper. */
const FULL_ZOOM_MIN = 40;
const FULL_ZOOM_MAX = 250;
const FULL_ZOOM_STEP = 10;

/**
 * What "Reset design" and an unpicked look both go back to.
 *
 * One constant rather than two copies: the reset button and the look toggle
 * have to agree on what "no look" means, and they did not while each held its
 * own object literal.
 */
const DEFAULT_DESIGN: Partial<Design> = {
  template: "classic",
  layout: "stacked",
  focus: "",
  accent: "ink",
  fonts: "serif_sans",
  page: "a4",
  margin: "normal",
  leading: "normal",
  date_format: "month",
  scale: 100,
  show_photo: true,
  hidden: [],
};

// "Portrait" was one of these until seven of the eight layouts grew a place
// for one. A filter that keeps almost everything is not a filter, it is a
// button that appears to do nothing.
const FILTERS = [
  { label: "All", test: () => true },
  { label: "ATS-safe", test: (t: TemplateOption) => t.ats },
  { label: "Two columns", test: (t: TemplateOption) => !t.ats },
];

/**
 * Whether the design panel is showing, and whether its column has closed yet.
 *
 * Two flags, because they must not change on the same frame. `collapsed` is
 * what the person asked for and drives the transform; `folded` is whether the
 * grid column has actually gone. Collapsing runs the slide first and closes
 * the column after; expanding opens the column first and slides in after. Do
 * both at once and the panel is clipped to nothing before it has moved, which
 * is a jump, not an animation.
 *
 * Remembered across sessions: someone who works on a laptop and wants the
 * width should not have to ask for it every time they open the app.
 */
const PANEL_KEY = "dossier:design-panel";
const SLIDE_MS = 200;

function useDesignPanel() {
  const [collapsed, setShown] = useState(() => {
    try {
      return localStorage.getItem(PANEL_KEY) === "hidden";
    } catch {
      return false;
    }
  });
  const [folded, setFolded] = useState(collapsed);

  useEffect(() => {
    try {
      if (collapsed) localStorage.setItem(PANEL_KEY, "hidden");
      else localStorage.removeItem(PANEL_KEY);
    } catch {
      /* a private window may refuse storage; the session still works */
    }

    if (collapsed) {
      const timer = setTimeout(() => setFolded(true), SLIDE_MS);
      return () => clearTimeout(timer);
    }
    setFolded(false);
    return undefined;
  }, [collapsed]);

  return { collapsed, folded, setCollapsed: setShown };
}

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
  const { profile, design, options, photoVersion, setDesign, edit } = useStore(useShallow((s) => ({
    profile: s.profile,
    design: s.design,
    options: s.options,
    photoVersion: s.photoVersion,
    setDesign: s.setDesign,
    edit: s.edit,
  })));

  // 0 means fit-to-pane; anything else is a literal scale. `percent` is what
  // the slider shows, and it survives a trip through Fit so going back to a
  // manual zoom returns you to the one you had.
  const [zoom, setZoom] = useState(0);
  const [percent, setPercent] = useState(100);
  const [fullscreen, setFullscreen] = useState(false);
  const [filter, setFilter] = useState("All");
  const [preview, setPreview] = useState("");
  const [thumbs, setThumbs] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<"pdf" | "html" | "text" | null>(null);
  const { collapsed, folded, setCollapsed } = useDesignPanel();
  const [report, setReport] = useState<FitReport | null>(null);
  // Set by a download, never by Check fit. Sending the file is the moment
  // worth recording, and the offer to record it should not appear before it.
  const [sent, setSent] = useState(false);

  // Two keys, because the two renders have different reasons to be redone:
  // the preview follows every edit, the thumbnails only follow the design.
  //
  // `photoVersion` is in both because the portrait is the one thing on the
  // page that can change without the profile changing: the file keeps its
  // name, so replacing it left these keys identical and the old face on the
  // page. See `store.photoVersion`.
  const previewKey = useDebounced(
    JSON.stringify({ profile, design, zoom, photoVersion }),
    250,
  );
  const galleryKey = useDebounced(
    JSON.stringify({ design, name: profile?.basics.name, photoVersion }),
    400,
  );

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
      setSent(true);
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

      <div
        className="grid flex-1 gap-6 p-6"
        style={{
          // Stepped, never transitioned. Animating this would re-lay-out
          // every document on the screen -- the preview and eight template
          // thumbnails -- on every frame, which is the mistake the sidebar
          // in App.tsx already made once. The visible motion is the panel's
          // transform; this just gets out of its way.
          gridTemplateColumns: folded
            ? "minmax(0,1fr)"
            : "minmax(0,340px) minmax(0,1fr)",
        }}
      >
        <div
          inert={collapsed}
          hidden={folded}
          className="flex min-w-0 flex-col gap-5 transition-[transform,opacity] duration-200 ease-out"
          style={{
            transform: collapsed ? "translateX(-24px)" : "none",
            opacity: collapsed ? 0 : 1,
          }}
        >
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold">Design</h2>
            <button
              type="button"
              className="btn btn-quiet px-1.5 py-1"
              onClick={() => setCollapsed(true)}
              title="Hide the design panel and give the page the width"
              aria-label="Hide the design panel"
            >
              <PanelLeftClose size={15} />
            </button>
          </div>

          <Looks
            design={design}
            profile={profile}
            options={options}
            refreshKey={galleryKey}
            onPick={setDesign}
          />

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

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
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
          {/* One control row, not two. With the panel away it gains the
              controls that lived in it -- the template and the print button --
              and sticks to the top of the pane; a floating bar *beside* the
              existing one would put two zoom sliders on the same screen. */}
          <div
            className={[
              "flex flex-wrap items-center gap-2 transition-[background-color,box-shadow,padding] duration-200 ease-out",
              collapsed
                ? "card sticky top-0 z-20 px-3 py-2 shadow-raised"
                : "",
            ].join(" ")}
          >
            {collapsed && (
              <button
                type="button"
                className="btn btn-quiet px-1.5 py-1"
                onClick={() => setCollapsed(false)}
                title="Show the design panel"
                aria-label="Show the design panel"
              >
                <PanelLeftOpen size={15} />
              </button>
            )}
            <h2 className="text-sm font-semibold">Preview</h2>

            {collapsed && (
              <select
                className="field h-8 w-auto min-w-0 max-w-44 py-1 text-xs"
                aria-label="Template"
                value={design.template}
                onChange={(event) => setDesign({ template: event.target.value })}
              >
                {options.templates.map((t) => (
                  <option key={t.key} value={t.key}>
                    {t.name}
                  </option>
                ))}
              </select>
            )}

            <div className="ml-auto flex items-center gap-2">
              <button
                type="button"
                onClick={() => setZoom(0)}
                className={[
                  "rounded px-2 py-1 text-2xs font-medium transition-colors duration-150",
                  zoom === 0 ? "bg-sunken text-ink shadow-subtle" : "text-muted hover:text-ink",
                ].join(" ")}
                title="Scale the page to fit this pane"
              >
                Fit
              </button>
              <input
                type="range"
                min={ZOOM_MIN}
                max={ZOOM_MAX}
                step={5}
                value={percent}
                aria-label="Zoom"
                onChange={(event) => {
                  const next = Number(event.target.value);
                  setPercent(next);
                  setZoom(next / 100);
                }}
                className="zoom w-28"
              />
              <span className="w-9 text-right font-mono text-2xs tabular-nums text-muted">
                {zoom === 0 ? "fit" : `${percent}%`}
              </span>
              <button
                type="button"
                className="btn btn-quiet px-1.5 py-1"
                onClick={() => setFullscreen(true)}
                title="See the whole page, as it prints"
                aria-label="Full screen preview"
              >
                <Maximize2 size={14} />
              </button>
            </div>

            <button type="button" className="btn" onClick={checkFit}>
              Check fit
            </button>
            {collapsed && (
              <button
                type="button"
                className="btn btn-primary"
                onClick={buildPdf}
                disabled={busy !== null}
              >
                {busy === "pdf" ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <Download size={14} />
                )}
                PDF
              </button>
            )}
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

          {sent && <KeepAsSent profile={profile} design={design} />}

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

      {fullscreen && (
        <FullPage profile={profile} design={design} onClose={() => setFullscreen(false)} />
      )}
    </>
  );
}

/**
 * Record what was just sent, at the moment it is sent.
 *
 * The alternative is remembering to do it later, from a screen you are not
 * on, about a file you have already emailed -- which is the same as not
 * recording it. It appears only after a download, and only when there is an
 * application to attach it to: an offer to file something against nothing is
 * noise on the one screen that should stay about the page.
 */
function KeepAsSent({ profile, design }: { profile: Profile; design: Design }) {
  const [options, setOptions] = useState<Application[] | null>(null);
  const [chosen, setChosen] = useState("");
  const [busy, setBusy] = useState(false);
  const [kept, setKept] = useState("");

  useEffect(() => {
    api
      .applications()
      // Rejected ones are dropped: nobody files a new document against an
      // application that is closed.
      .then(({ applications }) => setOptions(applications.filter((a) => a.status !== "rejected")))
      .catch(() => setOptions([]));
  }, []);

  if (!options || options.length === 0) return null;
  const target = chosen || options[0]!.id;

  async function keep() {
    setBusy(true);
    try {
      const version = await api.keepVersion(target, { profile, design });
      const application = options!.find((a) => a.id === target);
      setKept(application?.company || application?.title || "that application");
      toast.success(
        "Kept as sent",
        `${version.pages} page${version.pages === 1 ? "" : "s"}. Readable again from Applications, whatever the profile does next.`,
      );
    } catch (error) {
      if (error instanceof ApiError) toast.error(error.message, error.fix);
    } finally {
      setBusy(false);
    }
  }

  if (kept) {
    return (
      <div className="card flex flex-wrap items-center gap-2 border-l-2 border-l-accent p-3 text-sm">
        <Check size={15} className="text-accent" />
        <span className="min-w-0 flex-1">
          Filed against {kept}. This exact document can be read and printed again from
          Applications, however far the profile moves on.
        </span>
        <Link to="/applications" className="btn">
          <Briefcase size={14} />
          Applications
        </Link>
      </div>
    );
  }

  return (
    <div className="card flex flex-wrap items-center gap-2 p-3 text-sm">
      <span className="min-w-0 shrink-0 text-muted">Keep this as what you sent to</span>
      <select
        className="field h-8 w-auto min-w-0 flex-1 py-1 text-xs"
        aria-label="Which application this was sent to"
        value={target}
        onChange={(event) => setChosen(event.target.value)}
      >
        {options.map((application) => (
          <option key={application.id} value={application.id}>
            {[application.company, application.title].filter(Boolean).join(" · ") ||
              "Untitled posting"}
          </option>
        ))}
      </select>
      <button type="button" className="btn shrink-0" onClick={() => void keep()} disabled={busy}>
        {busy ? <Loader2 size={14} className="animate-spin" /> : <Briefcase size={14} />}
        Keep it
      </button>
    </div>
  );
}

/**
 * The resume with nothing else on screen.
 *
 * Exported because the Applications screen reads saved versions with it: a
 * version is a profile and a design, which is exactly what this takes, and a
 * second implementation of "show me this document" would be a second thing to
 * keep in step with the renderer.
 *
 * Rendered at its own zoom rather than reusing the pane's: the point of this
 * view is to read the page as a page, so it fits the *height* of the window
 * instead of the width of a column. It asks the server for its own document
 * because the fit script runs per-frame -- sharing the pane's HTML would mean
 * both frames fighting over one scale.
 */
export function FullPage({
  profile,
  design,
  onClose,
}: {
  profile: Profile;
  design: Design;
  onClose: () => void;
}) {
  const [html, setHtml] = useState("");
  // 0 is the automatic fit the view opens at; `percent` is the last literal
  // zoom, so Fit and back returns you to the size you were reading at.
  const [zoom, setZoom] = useState(0);
  const [percent, setPercent] = useState(100);
  const frame = useRef<HTMLIFrameElement>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setReady(false);
    api
      // "page" rather than a zoom: the whole sheet has to be inside the
      // window and centred, which depends on the window, so the fit is
      // computed there rather than guessed here.
      .preview({ profile, design, zoom: 0, fit: "page" })
      .then(setHtml)
      .catch((error: unknown) => {
        if (error instanceof ApiError) toast.error(error.message, error.fix);
      });
  }, [profile, design]);

  // The scale is handed to the document rather than fetched with it. A slider
  // that re-rendered server-side would put a round trip behind every step,
  // and the fit script already knows how to scale itself -- so it is told,
  // and the page redraws in the same frame as the handle.
  useEffect(() => {
    if (!ready) return;
    frame.current?.contentWindow?.postMessage({ dossierZoom: zoom }, "*");
  }, [zoom, ready]);

  const setLiteral = useCallback((next: number) => {
    const clamped = Math.min(FULL_ZOOM_MAX, Math.max(FULL_ZOOM_MIN, next));
    setPercent(clamped);
    setZoom(clamped / 100);
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      // The keys a reader already has in every viewer they use. Bare rather
      // than Ctrl+, because Ctrl+= is the browser's own zoom -- that scales
      // the app around the page instead of scaling the page.
      else if (event.key === "+" || event.key === "=") setLiteral(percent + FULL_ZOOM_STEP);
      else if (event.key === "-" || event.key === "_") setLiteral(percent - FULL_ZOOM_STEP);
      else if (event.key === "0") setZoom(0);
    };
    window.addEventListener("keydown", onKey);
    // The page behind must not scroll while a full-screen layer is over it.
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [onClose, percent, setLiteral]);

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-[#1b1c1f]">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-2 text-sm text-white/80">
        <span className="font-display">{profile.basics.name || "Resume"}</span>
        <span className="hidden text-white/45 lg:inline">
          Escape closes · + and − zoom · 0 fits
        </span>

        <div className="ml-auto flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => setZoom(0)}
            className={[
              "rounded px-2 py-1 text-2xs font-medium transition-colors duration-150",
              zoom === 0
                ? "bg-white/15 text-white"
                : "text-white/70 hover:bg-white/10 hover:text-white",
            ].join(" ")}
            title="Fit the whole page in the window"
          >
            Fit page
          </button>
          <button
            type="button"
            onClick={() => setLiteral(percent - FULL_ZOOM_STEP)}
            className="rounded px-1.5 py-1 text-white/70 transition-colors duration-150 hover:bg-white/10 hover:text-white"
            aria-label="Zoom out"
          >
            <ZoomOut size={15} />
          </button>
          <input
            type="range"
            min={FULL_ZOOM_MIN}
            max={FULL_ZOOM_MAX}
            step={FULL_ZOOM_STEP}
            value={percent}
            aria-label="Zoom"
            onChange={(event) => setLiteral(Number(event.target.value))}
            className="zoom zoom-dark w-28 sm:w-36"
          />
          <button
            type="button"
            onClick={() => setLiteral(percent + FULL_ZOOM_STEP)}
            className="rounded px-1.5 py-1 text-white/70 transition-colors duration-150 hover:bg-white/10 hover:text-white"
            aria-label="Zoom in"
          >
            <ZoomIn size={15} />
          </button>
          <span className="w-9 text-right font-mono text-2xs tabular-nums text-white/60">
            {zoom === 0 ? "fit" : `${percent}%`}
          </span>
        </div>

        <button
          type="button"
          onClick={onClose}
          className="rounded-md px-2 py-1 text-white/80 transition-colors duration-150 hover:bg-white/10 hover:text-white"
          aria-label="Close the full screen preview"
        >
          <X size={18} />
        </button>
      </div>
      <Frame
        html={html}
        title="Full page preview"
        className="min-h-0 flex-1"
        frameRef={frame}
        onLoad={() => setReady(true)}
        placeholder={<div className="absolute inset-0 animate-pulse bg-white/5" aria-hidden />}
      />
    </div>
  );
}

function Looks({
  design,
  profile,
  options,
  refreshKey,
  onPick,
}: {
  design: Design;
  profile: Profile;
  options: { looks: LookOption[] };
  /** Changes when the thumbnails would come back different. */
  refreshKey: string;
  onPick: (patch: Partial<Design>) => void;
}) {
  const matches = (values: Partial<Design>) =>
    Object.entries(values).every(
      ([key, value]) => JSON.stringify(design[key as keyof Design]) === JSON.stringify(value),
    );

  const look = options.looks.find((l) => l.variants.some((v) => matches(v.values)));
  const variant = look?.variants.find((v) => matches(v.values));
  const [thumbs, setThumbs] = useState<Record<string, string>>({});

  // Rendered on demand rather than up front. Twenty-four thumbnails is
  // twenty-four documents; the four belonging to the look in hand are the
  // only ones anybody is choosing between.
  useEffect(() => {
    if (!look) {
      setThumbs({});
      return;
    }
    let cancelled = false;
    Promise.all(
      look.variants.map(async (v) => {
        const html = await api.thumbnail({
          profile,
          design: { ...design, ...v.values },
          template: String(v.values.template ?? design.template),
          zoom: 0,
        });
        return [v.key, html] as const;
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
  }, [look?.key, refreshKey]);

  return (
    <section>
      <h2 className="mb-2 text-sm font-semibold">Start from a look</h2>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {options.looks.map((option) => {
          const active = option.key === look?.key;
          return (
            <button
              key={option.key}
              type="button"
              title={active ? `${option.blurb} — click again to clear it` : option.blurb}
              aria-pressed={active}
              // A look was a one-way door: once applied there was no way back
              // to an unstyled starting point except by hunting through the
              // controls it had changed. Clicking the active one clears it.
              onClick={() => onPick(active ? DEFAULT_DESIGN : option.values)}
              className={["btn justify-center", active ? "border-accent text-accent" : ""].join(" ")}
            >
              {option.name}
            </button>
          );
        })}
      </div>

      {/* The four are the point. A look is a colour, a typeface and a set of
          spacings; on their own those change how a page is dressed and not
          how it is built, which is why six buttons could feel like one
          design. Each of these takes a different template *and* a different
          way of setting the body underneath it. */}
      {look && (
        <div className="mt-3">
          <p className="label">Four ways to set {look.name.toLowerCase()}</p>
          <div className="grid grid-cols-4 gap-1.5">
            {look.variants.map((v) => {
              const chosen = v.key === variant?.key;
              return (
                <button
                  key={v.key}
                  type="button"
                  onClick={() => onPick(v.values)}
                  aria-pressed={chosen}
                  title={v.name}
                  className={[
                    "card overflow-hidden p-0 text-left transition-all duration-200 ease-out",
                    chosen
                      ? "border-accent ring-2 ring-accent/45"
                      : "hover:-translate-y-0.5 hover:border-line-strong hover:shadow-raised",
                  ].join(" ")}
                >
                  <Frame
                    html={thumbs[v.key] ?? ""}
                    title={`${look.name}, ${v.name}`}
                    decorative
                    className="h-[92px] overflow-hidden border-b border-line bg-white"
                    // The variant knows which template it applies, so the
                    // silhouette is the right one before the render lands --
                    // which is the whole difference between four variants
                    // and four grey boxes.
                    placeholder={
                      <Wireframe template={String(v.values.template ?? design.template)} />
                    }
                  />
                  <span
                    className={[
                      "block truncate px-1.5 py-1 text-2xs font-medium",
                      chosen ? "text-accent" : "text-muted",
                    ].join(" ")}
                  >
                    {v.name}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}
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
          ? "border-accent ring-2 ring-accent/45"
          : "hover:-translate-y-0.5 hover:border-line-strong hover:shadow-raised",
      ].join(" ")}
    >
      <Frame
        html={html}
        title={`${template.name} preview`}
        decorative
        className="h-[168px] overflow-hidden border-b border-line bg-white"
        placeholder={<Wireframe template={template.key} />}
      />
      <div className="p-2.5">
        <div className="flex items-center gap-1.5">
          <span className="font-display text-sm font-semibold">{template.name}</span>
          {selected && (
            <span className="rounded bg-accent-soft px-1.5 py-0.5 text-2xs font-semibold text-accent">
              Selected
            </span>
          )}
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

/**
 * A small status word with a ring around it.
 *
 * The borders were at 40% of their colour, which is legible on a bright
 * screen and gone on a dim one -- and these labels are the whole reason
 * anyone can tell an ATS-safe template from a two-column one at a glance.
 * At 70% the ring survives a laptop at half brightness, and the tinted
 * ground does the rest without shouting.
 */
function Badge({ children, tone }: { children: React.ReactNode; tone?: "good" | "fair" }) {
  const cls =
    tone === "good"
      ? "border-good/70 bg-good-soft text-good"
      : tone === "fair"
        ? "border-fair/70 bg-fair-soft text-fair"
        : "border-line-strong text-muted";
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
    layouts: Option[];
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

      <FocusPicker design={design} profile={profile} onChange={onChange} />

      {/* The template draws the top of the page; this sets everything under
          it. They are separate controls because they are separate decisions:
          the same header over a gutter and over a panel are two designs. */}
      <Choice
        label="Body layout"
        value={design.layout}
        options={options.layouts}
        onChange={(layout) => onChange({ layout })}
        note={options.layouts.find((l) => l.key === design.layout)?.blurb}
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
        label="Date format"
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
        <ScaleSlider
          steps={options.scale.steps}
          value={design.scale}
          onChange={(scale) => onChange({ scale })}
        />
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
            ...DEFAULT_DESIGN,
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

/**
 * Which job family this printing is aimed at.
 *
 * The tags live on the profile, because "this line is the kind of thing a
 * backend team cares about" is a fact about the work. Which one to print is a
 * presentation decision, so it lives in the design beside `hidden` — and it
 * means one master profile serves several job families without being copied.
 *
 * The control hides itself until something is tagged. A dropdown whose only
 * option is "everything" is a dropdown that teaches nothing, so instead the
 * feature announces itself once, where the tags are added.
 */
function FocusPicker({
  design,
  profile,
  onChange,
}: {
  design: Design;
  profile: Profile;
  onChange: (patch: Partial<Design>) => void;
}) {
  const tags = tagsInUse(profile as never);
  if (tags.length === 0) return null;

  const kept = design.focus
    ? `Printing the lines tagged #${design.focus}, plus every untagged one.`
    : "Printing everything. Tagged lines are only left out when a focus is set.";

  return (
    <div>
      <label className="label" htmlFor="choice-focus">
        Focus
      </label>
      <select
        id="choice-focus"
        className="field"
        value={design.focus}
        onChange={(event) => onChange({ focus: event.target.value })}
      >
        <option value="">Everything</option>
        {tags.map((tag) => (
          <option key={tag} value={tag}>
            #{tag}
          </option>
        ))}
      </select>
      <p className="mt-1 text-xs text-muted">{kept}</p>
    </div>
  );
}

/**
 * The five type sizes, with the highlight sliding between them.
 *
 * It used to appear under whichever number you pressed. On a row of five
 * numbers that differ by four percent each, an instant jump gives no reading
 * of which way you moved -- and moving is the whole point of the control.
 * The highlight is one element that translates, so the browser animates it on
 * the compositor rather than restyling five buttons.
 */
function ScaleSlider({
  steps,
  value,
  onChange,
}: {
  steps: number[];
  value: number;
  onChange: (value: number) => void;
}) {
  // A saved design could name a size this build no longer offers; the
  // highlight parks on the first step rather than sliding off the end.
  const index = Math.max(0, steps.indexOf(value));

  return (
    <div>
      <span className="label">Type size</span>
      <div className="relative flex rounded-md bg-sunken p-0.5">
        <span
          aria-hidden
          className="absolute inset-y-0.5 left-0.5 rounded bg-surface shadow-subtle transition-transform duration-200 ease-out"
          // The slots are contiguous and equal, so one slot width is the
          // whole of the travel per step -- which is what a 100% translate of
          // this element means.
          style={{
            width: `calc((100% - 4px) / ${steps.length})`,
            transform: `translateX(${index * 100}%)`,
          }}
        />
        {steps.map((step) => (
          <button
            key={step}
            type="button"
            onClick={() => onChange(step)}
            aria-pressed={step === value}
            className={[
              "relative flex-1 rounded px-1 py-1 text-2xs font-medium transition-colors duration-150",
              step === value ? "text-ink" : "text-muted hover:text-ink",
            ].join(" ")}
          >
            {step}
          </button>
        ))}
      </div>
    </div>
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

/**
 * A settings row: what it does at one end, the switch at the other.
 *
 * The switch used to sit immediately left of its label, which left the rest
 * of the row empty and gave three unrelated controls three different hit
 * targets. Full width means the whole row is clickable and the switches line
 * up in a column the eye can run down.
 */
/** The track and the knob, in one place: `left` has to agree with `w-8`. */
const TRACK_W = 32;
const KNOB = 22;

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
    <label className="flex w-full cursor-pointer items-center gap-3 py-0.5 text-sm">
      <span className="min-w-0 flex-1 text-muted">{label}</span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={() => onChange(!checked)}
        className={[
          "relative h-[22px] w-8 shrink-0 rounded-full transition-colors duration-200 ease-out",
          checked ? "bg-accent" : "bg-line-strong",
        ].join(" ")}
      >
        {/* The knob is the full height of the track and flush against
            whichever end it is at. Two things were wrong before, in order: a
            14px knob inset 2px in a 32px track was geometrically at the end
            and did not look it, because two pixels of colour past the knob
            read as a gap. Fixing that left a 40px track carrying a 22px knob,
            and the 18px of accent behind it read as slack -- a switch looks
            thrown when the knob dominates the track, not when it has crossed
            a field. 32 is the shortest track that still shows the travel. */}
        <span
          className="absolute top-0 h-[22px] w-[22px] rounded-full bg-white shadow-subtle ring-1 ring-black/10 transition-[left] duration-200 ease-out"
          style={{ left: checked ? TRACK_W - KNOB : 0 }}
        />
      </button>
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
  // The file waits here while the crop is chosen. Uploading first and cropping
  // afterwards would mean the server had already thrown away the pixels the
  // person is about to ask for.
  const [pending, setPending] = useState<File | null>(null);
  const bumpPhoto = useStore((s) => s.bumpPhoto);
  const has = Boolean(profile.basics.photo);

  async function upload(file: File) {
    setBusy(true);
    try {
      const { photo } = await api.uploadPhoto(file);
      onProfile((draft) => {
        draft.basics.photo = photo;
      });
      // The name is `photo.jpg` both times, so on a replace the line above
      // writes the value that was already there and nothing downstream can
      // tell the picture changed. This is what re-renders the page.
      bumpPhoto();
      setPending(null);
      toast.success(has ? "Portrait replaced" : "Portrait added");
    } catch (error) {
      if (error instanceof ApiError) toast.error(error.message, error.fix);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      {pending && (
        <PhotoCropper
          file={pending}
          busy={busy}
          onCancel={() => setPending(null)}
          onSave={(cropped) =>
            void upload(new File([cropped], "portrait.jpg", { type: "image/jpeg" }))
          }
        />
      )}
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
              if (file) setPending(file);
              // Cleared so that choosing the same file twice -- after a
              // cancel -- still fires a change event.
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
              bumpPhoto();
              toast.info("Portrait removed");
            }}
          >
            <Trash2 size={14} />
          </button>
        )}
      </div>
      {/* A look can turn the portrait off -- Formal does, because a photo on a
          resume is a liability in the countries Formal is aimed at. Without a
          switch here that decision would be one-way: the upload button would
          still work, and nothing would appear on the page. */}
      {has && (
        <Toggle
          checked={design.show_photo}
          onChange={(show_photo) => onChange({ show_photo })}
          label="Show it on the page"
        />
      )}
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
