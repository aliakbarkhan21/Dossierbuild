/**
 * Aiming the profile at one job.
 *
 * The screen is deliberately in that order: the posting, then what it asks
 * for, then what your profile already answers, and only then a model. By the
 * time anyone presses Rewrite they have read the gap themselves, which is
 * what stops the suggestions being taken on faith.
 *
 * The first two steps need no API key and no network -- everything on them is
 * computed by rules in `core/jobspec.py`. That is the point: the analysis is
 * useful on its own, and Gemini being down costs you the rewrites, not the
 * screen.
 */

import {
  AlertTriangle,
  ArrowRight,
  Briefcase,
  Check,
  Loader2,
  Sparkles,
  Target,
  X,
} from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useShallow } from "zustand/react/shallow";

import { useShell } from "../App";
import { TopBar } from "../components/TopBar";
import { ApiError, api } from "../lib/api";
import { useStore } from "../lib/store";
import { toast } from "../lib/toast";
import type { MatchReport, Profile, RewriteResult, Suggestion, Term } from "../lib/types";

/** Below this there is not enough posting to read tiers out of. */
const MIN_POSTING = 120;

export function TailorScreen() {
  const shell = useShell();
  const navigate = useNavigate();
  const { profile, health, reloadProfile } = useStore(
    useShallow((s) => ({
      profile: s.profile,
      health: s.health,
      reloadProfile: s.reloadProfile,
    })),
  );

  const [text, setText] = useState("");
  const [company, setCompany] = useState("");
  const [report, setReport] = useState<MatchReport | null>(null);
  const [result, setResult] = useState<RewriteResult | null>(null);
  const [busy, setBusy] = useState<"analyse" | "rewrite" | "apply" | null>(null);
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [accepted, setAccepted] = useState<Set<string>>(new Set());
  const [openTerm, setOpenTerm] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  // The id this posting was saved under, once it has been. Held so the
  // tailoring pass can be recorded against it, and cleared by a new analysis
  // -- a different posting is a different application.
  const [savedId, setSavedId] = useState("");
  // Counts analyses, and keys the save form. Without it the link and the note
  // typed for one posting were still sitting in the boxes when the next one
  // was analysed, and saving attached the wrong company's URL to it -- state
  // kept across something that should have been a fresh form.
  const [analysis, setAnalysis] = useState(0);

  if (!profile) return null;

  async function analyse() {
    setBusy("analyse");
    try {
      const next = await api.analysePosting({ text, company, profile: profile! });
      setReport(next);
      setResult(null);
      setOpenTerm(null);
      setCollapsed(true);
      setSavedId("");
      setAnalysis((n) => n + 1);
      // Everything that answers this posting at all starts ticked; entries
      // scoring zero do not, because sending them costs latency and returns
      // rewrites aimed at a job they have nothing to do with.
      setChosen(new Set(next.entries.filter((e) => e.score > 0).map((e) => e.entry_id)));
    } catch (error) {
      if (error instanceof ApiError) toast.error(error.message, error.fix);
    } finally {
      setBusy(null);
    }
  }

  async function rewrite() {
    setBusy("rewrite");
    try {
      const next = await api.rewriteFor({
        text,
        company,
        profile: profile!,
        entry_ids: [...chosen],
      });
      setResult(next);
      // A rewrite that introduced a number or a name the original did not
      // have starts unticked. The safe ones start ticked, because the common
      // case is "yes, all of these" and the risky case should cost a click.
      const safe = [next.summary, ...next.suggestions].filter(
        (s): s is Suggestion => Boolean(s) && s!.invented.length === 0,
      );
      setAccepted(new Set(safe.map((s) => s.block_id)));
      next.notes.forEach((note) => toast.info(note));
    } catch (error) {
      if (error instanceof ApiError) toast.error(error.message, error.fix);
      else toast.error("The rewrite did not come back.");
    } finally {
      setBusy(null);
    }
  }

  async function apply() {
    if (!result) return;
    const all = [result.summary, ...result.suggestions].filter(Boolean) as Suggestion[];
    const map = Object.fromEntries(
      all.filter((s) => accepted.has(s.block_id)).map((s) => [s.block_id, s.after]),
    );
    setBusy("apply");
    try {
      const { profile: updated, changed } = await api.applyRewrites(profile!, map);
      reloadProfile(updated, `Wrote in ${changed} rewrite${changed === 1 ? "" : "s"}`);
      // Recorded here rather than when the rewrites came back, because this
      // is the moment the verdicts are real: until Apply is pressed the ticks
      // are still being changed. A pass that is never applied is not
      // recorded, which is the honest reading of it.
      if (savedId) {
        void api
          .recordRun(savedId, {
            model: result.model,
            suggestions: all.map((s) => ({ ...s, accepted: accepted.has(s.block_id) })),
          })
          .catch(() => undefined);
      }
      toast.success(
        `${changed} rewrite${changed === 1 ? "" : "s"} written in`,
        "Not saved yet — press Save changes when it reads right.",
      );
      navigate("/profile?section=experience");
    } catch (error) {
      if (error instanceof ApiError) toast.error(error.message, error.fix);
    } finally {
      setBusy(null);
    }
  }

  const ready = text.trim().length >= MIN_POSTING;
  const suggestions = result ? [result.summary, ...result.suggestions].filter(Boolean) as Suggestion[] : [];

  return (
    <>
      <TopBar
        title="Tailor"
        subtitle={
          report
            ? `${report.title || "This posting"}${report.company ? ` · ${report.company}` : ""} · ${report.coverage}% of what it asks for`
            : "Paste a job posting. The gap analysis runs on your machine; only the rewrites use a model."
        }
        sidebarHidden={shell.sidebarHidden}
        onShowSidebar={shell.showSidebar}
        onOpenPalette={shell.openPalette}
        action={
          result ? (
            <button
              type="button"
              className="btn btn-primary"
              onClick={apply}
              disabled={busy !== null || accepted.size === 0}
            >
              {busy === "apply" ? <Loader2 size={15} className="animate-spin" /> : <Check size={15} />}
              Apply {accepted.size}
            </button>
          ) : report ? (
            // Once the gap is on screen the next thing to do is the rewrite,
            // not the analysis that just ran. A primary action that repeats
            // the step you have finished reads as a dead button.
            <button
              type="button"
              className="btn btn-primary"
              onClick={rewrite}
              disabled={busy !== null || !health?.ai_available || chosen.size === 0}
            >
              {busy === "rewrite" ? (
                <Loader2 size={15} className="animate-spin" />
              ) : (
                <Sparkles size={15} />
              )}
              Rewrite {chosen.size}
            </button>
          ) : (
            <button
              type="button"
              className="btn btn-primary"
              onClick={analyse}
              disabled={!ready || busy !== null}
            >
              {busy === "analyse" ? (
                <Loader2 size={15} className="animate-spin" />
              ) : (
                <Target size={15} />
              )}
              Analyse posting
            </button>
          )
        }
      />

      <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-5 p-6">
        <Posting
          text={text}
          company={company}
          collapsed={collapsed && report !== null}
          report={report}
          onText={setText}
          onCompany={setCompany}
          onExpand={() => setCollapsed(false)}
          onAnalyse={analyse}
          busy={busy === "analyse"}
          ready={ready}
        />

        {report && (
          <>
            <Coverage report={report} openTerm={openTerm} onOpenTerm={setOpenTerm} />
            <SaveApplication
              key={analysis}
              report={report}
              text={text}
              company={company}
              profile={profile}
              savedId={savedId}
              onSaved={setSavedId}
            />
            <Entries
              report={report}
              chosen={chosen}
              onToggle={(id) => {
                const next = new Set(chosen);
                next.has(id) ? next.delete(id) : next.add(id);
                setChosen(next);
              }}
            />

            {!result && (
              <section className="card flex flex-wrap items-center gap-4 p-4">
                <div className="min-w-0">
                  <h2 className="font-display text-lg">Rewrite for this job</h2>
                  <p className="mt-0.5 max-w-prose text-sm text-muted">
                    Your bullets get re-angled at what this posting asks for — reordered,
                    compressed, re-worded. Nothing is added: every number and name that comes
                    back is checked against the bullet it came from, and anything new is
                    flagged before you can accept it.
                  </p>
                </div>
                <button
                  type="button"
                  className="btn btn-primary ml-auto"
                  onClick={rewrite}
                  disabled={busy !== null || !health?.ai_available || chosen.size === 0}
                >
                  {busy === "rewrite" ? (
                    <Loader2 size={15} className="animate-spin" />
                  ) : (
                    <Sparkles size={15} />
                  )}
                  Rewrite {chosen.size} {chosen.size === 1 ? "entry" : "entries"}
                </button>
                {busy === "rewrite" && (
                  <p className="w-full text-xs text-muted">
                    Gemini is re-angling them. This takes 20–70 seconds — the model thinks
                    harder here than on an import, and every rewrite is checked afterwards.
                  </p>
                )}
                {!health?.ai_available && (
                  <p className="w-full text-xs text-fair">
                    No Gemini key, so rewriting is off. Everything above still works — it is
                    computed here, not by a model.
                  </p>
                )}
              </section>
            )}
          </>
        )}

        {result && (
          <Review
            result={result}
            suggestions={suggestions}
            accepted={accepted}
            onToggle={(id) => {
              const next = new Set(accepted);
              next.has(id) ? next.delete(id) : next.add(id);
              setAccepted(next);
            }}
            onDiscard={() => {
              setResult(null);
              setAccepted(new Set());
            }}
          />
        )}
      </div>
    </>
  );
}

/* -------------------------------------------------------------------------
   The posting
   ---------------------------------------------------------------------- */

function Posting({
  text,
  company,
  collapsed,
  report,
  onText,
  onCompany,
  onExpand,
  onAnalyse,
  busy,
  ready,
}: {
  text: string;
  company: string;
  collapsed: boolean;
  report: MatchReport | null;
  onText: (value: string) => void;
  onCompany: (value: string) => void;
  onExpand: () => void;
  onAnalyse: () => void;
  busy: boolean;
  ready: boolean;
}) {
  if (collapsed && report) {
    return (
      <button
        type="button"
        onClick={onExpand}
        className="card flex items-center gap-3 p-3 text-left transition-colors duration-150 hover:border-line-strong"
      >
        <Target size={15} className="shrink-0 text-accent" />
        <span className="min-w-0 flex-1 truncate text-sm">
          <b>{report.title || "Untitled posting"}</b>
          <span className="text-muted"> · {text.trim().split(/\s+/).length} words</span>
        </span>
        <span className="text-xs text-muted">Edit or paste another</span>
      </button>
    );
  }

  return (
    <section className="card p-5">
      <h2 className="font-display text-lg">The posting</h2>
      <p className="mt-1 max-w-prose text-sm text-muted">
        Paste the whole advert, headings and all. The headings are the useful part — a term
        under "Requirements" is read as a stronger ask than the same word in the friendly
        paragraph at the top, and a benefits list is skipped entirely.
      </p>

      <textarea
        className="field mt-4 min-h-64 resize-y text-sm leading-relaxed"
        // The main input of the screen, and it announced nothing: a
        // placeholder is not a label, and it disappears the moment anything
        // is typed into it.
        aria-label="Job posting"
        value={text}
        onChange={(event) => onText(event.target.value)}
        placeholder={"AI Engineering Intern\nNorthgate Analytics — Islamabad\n\nRequirements:\n- Strong Python…"}
      />

      <div className="mt-3 flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm">
          <span className="text-muted">Company</span>
          <input
            className="field w-48"
            value={company}
            placeholder="optional"
            onChange={(event) => onCompany(event.target.value)}
          />
        </label>
        <button
          type="button"
          className="btn btn-primary ml-auto"
          onClick={onAnalyse}
          disabled={!ready || busy}
        >
          {busy ? <Loader2 size={15} className="animate-spin" /> : <Target size={15} />}
          Analyse posting
        </button>
      </div>
      {!ready && text.trim().length > 0 && (
        <p className="mt-2 text-xs text-muted">
          {MIN_POSTING - text.trim().length} more characters — a posting this short has no
          structure to read.
        </p>
      )}
    </section>
  );
}

/* -------------------------------------------------------------------------
   The gap
   ---------------------------------------------------------------------- */

const TIER_LABEL: Record<string, string> = {
  required: "Required",
  preferred: "Preferred",
  general: "Mentioned",
};

/**
 * Keep this posting, or read it and move on.
 *
 * Deliberately not automatic. Analysing a posting is browsing -- half of them
 * are read to see whether they are worth the afternoon -- and a pipeline that
 * fills itself with every advert anyone glanced at is a pipeline nobody
 * trusts. Pressing this is the statement that this one is real.
 *
 * What gets stored is the rules-based analysis that is already on screen, not
 * a model's opinion of it, so the record stays reproducible: the same posting
 * saved twice gives the same terms.
 */
function SaveApplication({
  report,
  text,
  company,
  profile,
  savedId,
  onSaved,
}: {
  report: MatchReport;
  text: string;
  company: string;
  profile: Profile;
  savedId: string;
  onSaved: (id: string) => void;
}) {
  const [url, setUrl] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    try {
      const { id } = await api.saveApplication({
        text,
        title: report.title,
        company,
        source_url: url.trim(),
        notes: notes.trim(),
        profile,
      });
      onSaved(id);
      toast.success(
        "Saved to Applications",
        "Rewrites you apply from here are recorded against it.",
      );
    } catch (error) {
      if (error instanceof ApiError) toast.error(error.message, error.fix);
    } finally {
      setBusy(false);
    }
  }

  if (savedId) {
    return (
      <section className="card flex flex-wrap items-center gap-3 border-l-2 border-l-accent p-4">
        <Check size={16} className="text-accent" />
        <p className="min-w-0 flex-1 text-sm">
          Saved. Its requirements now count towards what you keep missing, and any rewrite
          you apply is recorded against it.
        </p>
        <Link to="/applications" className="btn">
          <Briefcase size={14} />
          Applications
        </Link>
      </section>
    );
  }

  return (
    <section className="card flex flex-col gap-3 p-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-semibold">Keep this one?</h2>
          <p className="mt-0.5 max-w-prose text-xs text-muted">
            Stores the posting and the {report.terms.length} requirements read out of it. Once
            two are saved, the Applications screen can tell you which ones keep coming up that
            your profile does not evidence — the question a single posting cannot answer.
          </p>
        </div>
        <button type="button" className="btn ml-auto" onClick={save} disabled={busy}>
          {busy ? <Loader2 size={14} className="animate-spin" /> : <Briefcase size={14} />}
          Save this application
        </button>
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        <input
          className="field"
          type="url"
          placeholder="Link to the posting (optional)"
          aria-label="Link to the posting"
          value={url}
          onChange={(event) => setUrl(event.target.value)}
        />
        <input
          className="field"
          placeholder="A note to your future self (optional)"
          aria-label="Note"
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
        />
      </div>
    </section>
  );
}

function Coverage({
  report,
  openTerm,
  onOpenTerm,
}: {
  report: MatchReport;
  openTerm: string | null;
  onOpenTerm: (key: string | null) => void;
}) {
  const tone =
    report.coverage >= 70
      ? { text: "text-good", bar: "bg-good" }
      : report.coverage >= 40
        ? { text: "text-fair", bar: "bg-fair" }
        : { text: "text-poor", bar: "bg-poor" };

  const evidence = openTerm ? (report.covered[openTerm] ?? []) : null;
  const weak = new Set(report.declared_only.map((t) => t.toLowerCase()));

  return (
    <section className="card p-5">
      <div className="flex flex-wrap items-start gap-6">
        <div>
          <div className="flex items-baseline gap-1.5">
            <span className={`font-display text-3xl ${tone.text}`}>{report.coverage}%</span>
            <span className="text-sm text-muted">of what it asks for</span>
          </div>
          <p className="mt-1 max-w-md text-xs text-muted">
            Weighted by where each term sits in the advert, so a stated requirement counts
            for more than a passing mention. It measures words, not whether you would be
            good at the job — a posting you half-match is still worth applying to.
          </p>
        </div>
        <div className="ml-auto flex gap-6 text-sm">
          <Count value={Object.keys(report.covered).length} label="Evidenced" tone="text-good" />
          <Count value={report.declared_only.length} label="Listed only" tone="text-fair" />
          <Count value={report.missing.length} label="Missing" tone="text-poor" />
        </div>
      </div>

      <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-sunken" aria-hidden>
        <div
          className={`h-full rounded-full ${tone.bar} transition-[width] duration-500 ease-out`}
          style={{ width: `${report.coverage}%` }}
        />
      </div>

      <div className="mt-4 flex flex-wrap gap-1.5">
        {report.terms.map((term) => (
          <Chip
            key={term.key}
            term={term}
            state={
              term.key in report.covered
                ? weak.has(term.text.toLowerCase())
                  ? "weak"
                  : "covered"
                : "missing"
            }
            open={openTerm === term.key}
            onClick={() => onOpenTerm(openTerm === term.key ? null : term.key)}
          />
        ))}
      </div>

      {openTerm && (
        <div className="mt-3 rounded-md border border-line bg-sunken p-3">
          <p className="text-2xs font-semibold uppercase tracking-wide text-faint">
            {evidence && evidence.length > 0
              ? `Where your profile backs up "${openTerm}"`
              : `"${openTerm}"`}
          </p>
          {evidence && evidence.length > 0 ? (
            <ul className="mt-1.5 flex flex-col gap-1.5">
              {evidence.slice(0, 6).map((hit) => (
                <li key={hit.block_id} className="text-xs">
                  <span className="text-faint">{hit.entry_label} · </span>
                  {/* A match found in the entry's own title, stack or
                      coursework rather than in a bullet. Printing that
                      synthesised text back reads as a run-on of fragments, so
                      it is described instead of quoted. */}
                  <span className="text-muted">
                    {hit.block_id.endsWith(":heading")
                      ? "named in the title or the stack, not in a bullet"
                      : hit.text.slice(0, 180)}
                  </span>
                </li>
              ))}
            </ul>
          ) : report.covered[openTerm] ? (
            <p className="mt-1 max-w-prose text-xs text-muted">
              In your skills list, but no bullet describes you using it. A reader treats a
              listed skill as a claim and a described one as evidence — this is the cheapest
              gap on this screen to close.
            </p>
          ) : (
            <p className="mt-1 max-w-prose text-xs text-muted">
              Nothing in your profile mentions this. If you have actually done it, add it to
              the relevant role or project — tailoring re-angles what is there and will never
              invent it for you.
            </p>
          )}
        </div>
      )}
    </section>
  );
}

function Chip({
  term,
  state,
  open,
  onClick,
}: {
  term: Term;
  state: "covered" | "weak" | "missing";
  open: boolean;
  onClick: () => void;
}) {
  // Written out rather than composed: Tailwind extracts class names as literal
  // strings, so an interpolated `border-${tone}` compiles to nothing.
  const style =
    state === "covered"
      ? "border-good/45 bg-good-soft text-good"
      : state === "weak"
        ? "border-fair/45 bg-fair-soft text-fair"
        : "border-line-strong text-muted hover:border-poor/50 hover:text-poor";

  return (
    <button
      type="button"
      onClick={onClick}
      title={`${TIER_LABEL[term.tier]} · weight ${term.weight}`}
      className={[
        "rounded-full border px-2 py-0.5 text-xs transition-colors duration-150",
        style,
        open ? "ring-2 ring-accent/30" : "",
        term.tier === "required" ? "font-semibold" : "",
      ].join(" ")}
    >
      {term.text}
    </button>
  );
}

function Count({ value, label, tone }: { value: number; label: string; tone: string }) {
  return (
    <div className="text-center">
      <div className={`font-display text-xl ${tone}`}>{value}</div>
      <div className="text-2xs uppercase tracking-wide text-faint">{label}</div>
    </div>
  );
}

/* -------------------------------------------------------------------------
   Which of your entries answer it
   ---------------------------------------------------------------------- */

function Entries({
  report,
  chosen,
  onToggle,
}: {
  report: MatchReport;
  chosen: Set<string>;
  onToggle: (id: string) => void;
}) {
  const top = report.entries[0]?.score ?? 0;

  return (
    <section>
      <div className="mb-2 flex items-baseline gap-3">
        <h2 className="text-sm font-semibold">What of yours speaks to this job</h2>
        <p className="text-xs text-muted">
          Ranked by how much of the posting each entry answers. Ticked entries go to the
          rewrite; the rest are left exactly as they are.
        </p>
      </div>

      <ul className="flex flex-col divide-y divide-line overflow-hidden rounded-lg border border-line">
        {report.entries.map((entry) => (
          <li key={entry.entry_id}>
            <label className="flex cursor-pointer items-center gap-3 bg-surface px-3 py-2.5 transition-colors duration-150 hover:bg-sunken">
              <input
                type="checkbox"
                className="accent-[var(--c-accent)]"
                checked={chosen.has(entry.entry_id)}
                onChange={() => onToggle(entry.entry_id)}
              />
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline gap-2">
                  <span className="truncate text-sm font-medium">{entry.label}</span>
                  <span className="text-2xs uppercase tracking-wide text-faint">
                    {entry.section}
                  </span>
                </div>
                {entry.matched.length > 0 ? (
                  <p className="truncate text-xs text-muted">{entry.matched.join(" · ")}</p>
                ) : (
                  <p className="text-xs text-faint">
                    nothing in this entry matches the posting
                  </p>
                )}
              </div>
              <div className="h-1.5 w-24 shrink-0 overflow-hidden rounded-full bg-sunken">
                <div
                  className="h-full rounded-full bg-accent"
                  style={{ width: top ? `${Math.round((entry.score / top) * 100)}%` : "0%" }}
                />
              </div>
            </label>
          </li>
        ))}
      </ul>
    </section>
  );
}

/* -------------------------------------------------------------------------
   The suggestions
   ---------------------------------------------------------------------- */

function Review({
  result,
  suggestions,
  accepted,
  onToggle,
  onDiscard,
}: {
  result: RewriteResult;
  suggestions: Suggestion[];
  accepted: Set<string>;
  onToggle: (id: string) => void;
  onDiscard: () => void;
}) {
  const flagged = suggestions.filter((s) => s.invented.length > 0).length;

  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline gap-3">
        <h2 className="font-display text-lg">
          {suggestions.length} rewrite{suggestions.length === 1 ? "" : "s"}
        </h2>
        <p className="text-sm text-muted">
          Rewritten by {result.model}, then checked against the originals.
          {flagged > 0 && (
            <span className="text-poor">
              {" "}
              {flagged} introduced something the source did not say — those start unticked.
            </span>
          )}
        </p>
        <button type="button" className="btn ml-auto" onClick={onDiscard}>
          Discard these
        </button>
      </div>

      {suggestions.length === 0 && (
        <div className="card p-8 text-center">
          <p className="font-display text-lg">Nothing worth rewriting</p>
          <p className="mx-auto mt-1 max-w-md text-sm text-muted">
            The model was told to leave alone any bullet already right for this job, and it
            left all of them. Closing the gaps above will do more than a rewrite would.
          </p>
        </div>
      )}

      {suggestions.map((suggestion) => (
        <SuggestionCard
          key={suggestion.block_id}
          suggestion={suggestion}
          accepted={accepted.has(suggestion.block_id)}
          onToggle={() => onToggle(suggestion.block_id)}
        />
      ))}
    </section>
  );
}

function SuggestionCard({
  suggestion,
  accepted,
  onToggle,
}: {
  suggestion: Suggestion;
  accepted: boolean;
  onToggle: () => void;
}) {
  const risky = suggestion.invented.length > 0;

  return (
    <article
      className={[
        "card p-4 transition-colors duration-150",
        risky ? "border-l-2 border-l-poor" : accepted ? "border-l-2 border-l-accent" : "",
      ].join(" ")}
    >
      <div className="flex items-start gap-3">
        <button
          type="button"
          role="switch"
          aria-checked={accepted}
          onClick={onToggle}
          aria-label={accepted ? "Reject this rewrite" : "Accept this rewrite"}
          className={[
            "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md border transition-colors duration-150",
            accepted
              ? "border-accent bg-accent text-[var(--c-on-accent)]"
              : "border-line-strong text-faint hover:border-accent hover:text-accent",
          ].join(" ")}
        >
          {accepted ? <Check size={14} /> : <X size={14} />}
        </button>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-2xs font-semibold uppercase tracking-wide text-faint">
              {suggestion.entry_label}
            </span>
            {/* Not shown on a flagged rewrite. A term "gained" by inventing it
                is not a gain, and a green badge beside a red warning argues
                with it. */}
            {!risky && suggestion.terms_added.length > 0 && (
              <Tag tone="good">+{suggestion.terms_added.join(", +")}</Tag>
            )}
            {suggestion.findings_after < suggestion.findings_before && (
              <Tag tone="good">
                {suggestion.findings_before} → {suggestion.findings_after} flags
              </Tag>
            )}
            {suggestion.findings_after > suggestion.findings_before && (
              <Tag tone="fair">
                {suggestion.findings_before} → {suggestion.findings_after} flags
              </Tag>
            )}
          </div>

          <p className="mt-2 text-sm text-faint line-through decoration-line">
            {suggestion.before}
          </p>
          <div className="mt-1.5 flex items-start gap-1.5">
            <ArrowRight size={13} className="mt-1 shrink-0 text-accent" aria-hidden />
            <p className="text-sm">{suggestion.after}</p>
          </div>

          {suggestion.reason && (
            <p className="mt-1.5 text-xs text-muted">{suggestion.reason}</p>
          )}

          {risky && (
            <div className="mt-2.5 flex items-start gap-2 rounded-md border border-poor/40 bg-poor-soft p-2.5">
              <AlertTriangle size={14} className="mt-0.5 shrink-0 text-poor" />
              <p className="text-xs text-poor">
                <b>{suggestion.invented.join(", ")}</b>{" "}
                {suggestion.invented.length === 1 ? "is" : "are"} not in the original and not
                anywhere in your profile. If it is not true, reject this — you will be asked
                about it.
              </p>
            </div>
          )}
        </div>
      </div>
    </article>
  );
}

function Tag({ children, tone }: { children: React.ReactNode; tone: "good" | "fair" }) {
  const style =
    tone === "good" ? "border-good/40 text-good" : "border-fair/40 text-fair";
  return (
    <span className={`rounded border px-1 py-px text-2xs font-semibold ${style}`}>
      {children}
    </span>
  );
}
