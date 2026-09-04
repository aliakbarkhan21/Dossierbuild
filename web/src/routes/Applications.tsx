/**
 * Every job you have gone for, and what they add up to.
 *
 * The database has been here since phase 3 and had no screen: every tailoring
 * pass computed a posting's requirements, scored the profile against them,
 * and threw the lot away when the tab closed. This is the front door.
 *
 * The order on the page is the order the answers are worth having. Where
 * things stand first, because that is what anyone opens this for. Then the
 * one question no other screen in the app can answer -- which requirement you
 * keep failing to evidence, counted across every posting rather than read off
 * the one in front of you. The list is last: it is the record, not the point.
 */

import {
  Briefcase,
  ChevronDown,
  ClipboardList,
  Download,
  ExternalLink,
  Eye,
  Loader2,
  Target,
  Trash2,
  TrendingUp,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { useShell } from "../App";
import { TopBar } from "../components/TopBar";
import { ApiError, api, download } from "../lib/api";
import { useStore } from "../lib/store";
import { useShallow } from "zustand/react/shallow";
import { toast } from "../lib/toast";
import type {
  Application,
  ApplicationStatus,
  Gap,
  Overview,
  Version,
  VersionDetail,
} from "../lib/types";
import { FullPage } from "./Resume";
import { InterviewBriefSheet } from "../components/InterviewBriefSheet";

/**
 * The pipeline, in the order an application moves through it.
 *
 * "rejected" is on the end rather than hidden. A search with nothing in that
 * column is a search that has not started; the number is information, and
 * leaving it out to be kind would make the other four read as the whole story.
 */
const STATUSES: { key: ApplicationStatus; label: string; tone: string }[] = [
  { key: "draft", label: "Draft", tone: "text-muted" },
  { key: "applied", label: "Applied", tone: "text-ink" },
  { key: "interview", label: "Interview", tone: "text-accent" },
  { key: "offer", label: "Offer", tone: "text-good" },
  { key: "rejected", label: "Rejected", tone: "text-faint" },
];

/**
 * Below this, "what you keep missing" is one posting's gap with a plural on
 * it. The whole claim of that panel is that a term recurring across postings
 * means something a single posting cannot say, so it does not open its mouth
 * until it has two to compare.
 */
const ENOUGH_FOR_GAPS = 2;

/** A trend needs a direction, and two points is a line, not a trend. */
const ENOUGH_FOR_TREND = 3;

/** Stored UTC to the second; read here as a date a person recognises. */
function when(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export function ApplicationsScreen() {
  const shell = useShell();
  const [data, setData] = useState<Overview | null>(null);
  const [filter, setFilter] = useState<ApplicationStatus | "all">("all");
  // Which delete is armed. A saved application takes its runs and its
  // rewrites down with it (ON DELETE CASCADE), so it asks first -- in place,
  // because a modal for a row is a bigger interruption than the action.
  const [arming, setArming] = useState("");
  // A saved version being read. It is the same full-page view the Resume
  // screen uses, fed the stored document instead of the current one.
  const [reading, setReading] = useState<VersionDetail | null>(null);
  // Which application's interview brief is open, if any.
  const [briefing, setBriefing] = useState("");

  const load = useCallback(async () => {
    try {
      setData(await api.applications());
    } catch (error) {
      if (error instanceof ApiError) toast.error(error.message, error.fix);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function move(id: string, status: ApplicationStatus) {
    // Moved on screen first: the round trip is to a file on this machine, and
    // a select that waits for it feels broken rather than careful. A failure
    // reloads, which puts the truth back.
    setData((current) =>
      current
        ? {
            ...current,
            applications: current.applications.map((a) =>
              a.id === id ? { ...a, status } : a,
            ),
          }
        : current,
    );
    try {
      await api.setApplicationStatus(id, status);
      await load();
    } catch (error) {
      if (error instanceof ApiError) toast.error(error.message, error.fix);
      void load();
    }
  }

  async function remove(id: string) {
    try {
      await api.deleteApplication(id);
      setArming("");
      await load();
      toast.info("Application deleted", "Its postings, runs and rewrites went with it.");
    } catch (error) {
      if (error instanceof ApiError) toast.error(error.message, error.fix);
    }
  }

  const applications = data?.applications ?? [];
  const shown =
    filter === "all" ? applications : applications.filter((a) => a.status === filter);
  const average = applications.length
    ? Math.round(applications.reduce((sum, a) => sum + a.coverage, 0) / applications.length)
    : 0;

  return (
    <>
      <TopBar
        title="Applications"
        subtitle={
          applications.length
            ? `${applications.length} saved · ${average}% average coverage`
            : "Every posting you save, and the requirements they have in common."
        }
        sidebarHidden={shell.sidebarHidden}
        onShowSidebar={shell.showSidebar}
        onOpenPalette={shell.openPalette}
        action={
          <Link to="/tailor" className="btn btn-primary">
            <Target size={15} />
            Tailor for a job
          </Link>
        }
      />

      <div className="flex flex-col gap-5 p-6">
        {!data ? (
          <div className="card h-32 animate-pulse bg-sunken" aria-hidden />
        ) : applications.length === 0 ? (
          <Empty />
        ) : (
          <>
            <Pipeline
              counts={data.pipeline}
              filter={filter}
              onFilter={(next) => setFilter(next === filter ? "all" : next)}
            />

            <Gaps gaps={data.gaps} total={applications.length} />

            <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,300px)]">
              <section className="flex flex-col gap-3">
                <h2 className="text-sm font-semibold">
                  {filter === "all" ? "Every application" : `${filter} · ${shown.length}`}
                </h2>
                {shown.map((application) => (
                  <Card
                    key={application.id}
                    application={application}
                    armed={arming === application.id}
                    onArm={() => setArming(application.id)}
                    onDisarm={() => setArming("")}
                    onMove={(status) => void move(application.id, status)}
                    onDelete={() => void remove(application.id)}
                    onRead={setReading}
                    onBrief={() => setBriefing(application.id)}
                    onChanged={() => void load()}
                  />
                ))}
                {shown.length === 0 && (
                  <p className="text-sm text-muted">
                    Nothing at that status yet. Press it again to see them all.
                  </p>
                )}
              </section>

              <div className="flex flex-col gap-5">
                <Trend trend={data.trend} />
                <Guard guard={data.guard} />
              </div>
            </div>
          </>
        )}
      </div>

      {reading && (
        <FullPage
          profile={reading.profile}
          design={reading.design}
          onClose={() => setReading(null)}
        />
      )}

      {briefing && (
        <InterviewBriefSheet applicationId={briefing} onClose={() => setBriefing("")} />
      )}
    </>
  );
}

/**
 * What to do, rather than a shrug.
 *
 * An empty dashboard that says "no data" teaches nothing. This one names the
 * two presses that fill it and what the screen will be able to tell you once
 * they have happened twice.
 */
function Empty() {
  return (
    <section className="card flex max-w-xl flex-col items-start gap-3 p-6">
      <span className="rounded-md bg-accent-soft p-2 text-accent">
        <Briefcase size={18} />
      </span>
      <h2 className="font-display text-lg font-semibold">Nothing saved yet</h2>
      <p className="text-sm text-muted">
        Paste a posting on Tailor and press <b>Analyse</b>, then <b>Save this application</b>.
        The posting, the requirements it names and what your profile answers are all stored
        here — no model involved, so the record stays reproducible.
      </p>
      <p className="text-sm text-muted">
        From the second one on, this screen can tell you which requirements keep coming up
        that your profile does not evidence. That is the question a single posting cannot
        answer, and it is the one worth knowing.
      </p>
      <Link to="/tailor" className="btn btn-primary mt-1">
        <Target size={15} />
        Tailor for a job
      </Link>
    </section>
  );
}

function Pipeline({
  counts,
  filter,
  onFilter,
}: {
  counts: Record<ApplicationStatus, number>;
  filter: ApplicationStatus | "all";
  onFilter: (status: ApplicationStatus) => void;
}) {
  return (
    <section className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
      {STATUSES.map(({ key, label, tone }) => {
        const active = filter === key;
        return (
          <button
            key={key}
            type="button"
            onClick={() => onFilter(key)}
            aria-pressed={active}
            title={active ? "Showing only these — press again for all" : `Show only ${label}`}
            className={[
              "card flex flex-col items-start px-3 py-2.5 text-left transition-colors duration-150",
              active ? "border-accent bg-accent-soft" : "hover:border-line-strong",
            ].join(" ")}
          >
            <span className={`font-display text-2xl font-semibold tabular-nums ${tone}`}>
              {counts[key] ?? 0}
            </span>
            <span className="text-2xs font-medium uppercase tracking-wide text-faint">
              {label}
            </span>
          </button>
        );
      })}
    </section>
  );
}

/**
 * The question the database exists for.
 *
 * "Docker was named by six postings and evidenced in none of them" is not
 * something the Tailor screen can say -- it has one posting in front of it.
 * This is a GROUP BY across every application, and it is the most useful
 * sentence this app produces, so it gets the width.
 */
function Gaps({ gaps, total }: { gaps: Gap[]; total: number }) {
  if (total < ENOUGH_FOR_GAPS) {
    return (
      <section className="card p-4">
        <h2 className="text-sm font-semibold">What you keep missing</h2>
        <p className="mt-1 text-sm text-muted">
          Save a second posting and this counts the requirements they have in common that
          your profile does not evidence. One posting only ever tells you about that job.
        </p>
      </section>
    );
  }

  const worst = gaps.filter((g) => g.missing_in > 1);
  // The bar is how often, against the worst offender -- not the share of the
  // postings that named it. As a share it read 100% for every row on a
  // profile that evidences none of them, which is four identical bars beside
  // four different numbers: decoration, and misleading decoration at that.
  const loudest = Math.max(...worst.map((g) => g.missing_in), 1);
  if (worst.length === 0) {
    return (
      <section className="card p-4">
        <h2 className="text-sm font-semibold">What you keep missing</h2>
        <p className="mt-1 text-sm text-muted">
          Nothing is missing from more than one posting. Every gap so far has been specific
          to the job rather than a hole in the profile.
        </p>
      </section>
    );
  }

  return (
    <section className="card p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold">What you keep missing</h2>
        <p className="text-xs text-muted">
          Across {total} saved posting{total === 1 ? "" : "s"}. Learn the top one and every
          future match moves.
        </p>
      </div>

      <ul className="mt-3 flex flex-col gap-1.5">
        {worst.slice(0, 8).map((gap) => (
          <li key={gap.term} className="flex items-center gap-3">
            <span className="w-32 shrink-0 truncate font-medium" title={gap.term}>
              {gap.term}
            </span>
            <span
              className={[
                "shrink-0 rounded px-1.5 py-0.5 text-2xs font-medium uppercase tracking-wide",
                gap.tier === "required"
                  ? "bg-poor-soft text-poor"
                  : gap.tier === "preferred"
                    ? "bg-sunken text-fair"
                    : "bg-sunken text-faint",
              ].join(" ")}
            >
              {gap.tier}
            </span>
            <span className="h-1.5 min-w-0 flex-1 rounded-full bg-sunken">
              <span
                className="block h-full rounded-full bg-poor"
                style={{ width: `${Math.round((gap.missing_in / loudest) * 100)}%` }}
              />
            </span>
            <span className="w-28 shrink-0 text-right text-xs tabular-nums text-muted">
              missing in {gap.missing_in} of {gap.postings}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Card({
  application,
  armed,
  onArm,
  onDisarm,
  onMove,
  onDelete,
  onRead,
  onBrief,
  onChanged,
}: {
  application: Application;
  armed: boolean;
  onArm: () => void;
  onDisarm: () => void;
  onMove: (status: ApplicationStatus) => void;
  onDelete: () => void;
  onRead: (version: VersionDetail) => void;
  onBrief: () => void;
  onChanged: () => void;
}) {
  const { title, company, coverage, required_missing, runs, accepted } = application;
  const band =
    coverage >= 70 ? "text-good" : coverage >= 45 ? "text-fair" : "text-poor";

  return (
    <article className="card flex flex-col gap-2.5 p-4">
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="truncate font-medium">{title || "Untitled posting"}</h3>
          <p className="truncate text-xs text-muted">
            {company || "No company named"}
            {" · saved "}
            {when(application.created_at)}
            {application.applied_at && ` · applied ${when(application.applied_at)}`}
          </p>
        </div>

        <div className="text-right">
          <div className={`font-display text-xl font-semibold tabular-nums ${band}`}>
            {coverage}%
          </div>
          <div className="text-2xs uppercase tracking-wide text-faint">covered</div>
        </div>

        {/* Only on a card that has actually reached an interview: it is the
            only card the sheet means anything on. */}
        {application.status === "interview" && (
          <button type="button" className="btn" onClick={onBrief}>
            <ClipboardList size={14} />
            Interview brief
          </button>
        )}

        <select
          className="field w-auto py-1 text-xs"
          value={application.status}
          aria-label={`Status of ${title || "this application"}`}
          onChange={(event) => onMove(event.target.value as ApplicationStatus)}
        >
          {STATUSES.map((s) => (
            <option key={s.key} value={s.key}>
              {s.label}
            </option>
          ))}
        </select>

        {armed ? (
          <span className="flex items-center gap-1">
            <button type="button" className="btn text-poor" onClick={onDelete}>
              Delete for good
            </button>
            <button type="button" className="btn btn-quiet" onClick={onDisarm}>
              Keep
            </button>
          </span>
        ) : (
          <button
            type="button"
            className="btn btn-quiet px-1.5 py-1"
            onClick={onArm}
            title="Delete this application"
            aria-label={`Delete ${title || "this application"}`}
          >
            <Trash2 size={14} />
          </button>
        )}
      </div>

      {required_missing.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-2xs uppercase tracking-wide text-faint">Required, unevidenced</span>
          {required_missing.map((term) => (
            <span key={term} className="rounded bg-poor-soft px-1.5 py-0.5 text-2xs text-poor">
              {term}
            </span>
          ))}
        </div>
      )}

      <Versions application={application} onRead={onRead} onChanged={onChanged} />

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
        <span>
          {runs} tailoring run{runs === 1 ? "" : "s"}
          {runs > 0 && ` · ${accepted} rewrite${accepted === 1 ? "" : "s"} kept`}
        </span>
        {application.source_url && (
          <a
            className="inline-flex items-center gap-1 text-muted underline decoration-line underline-offset-2 hover:text-accent"
            href={application.source_url}
            target="_blank"
            rel="noopener noreferrer"
          >
            <ExternalLink size={12} />
            The posting
          </a>
        )}
        {application.notes && <span className="min-w-0 truncate">{application.notes}</span>}
      </div>
    </article>
  );
}

/**
 * What was actually sent, and when.
 *
 * Six weeks after an application the recruiter calls and the profile has moved
 * on -- bullets rewritten for three jobs since, a section reordered, the type
 * a size smaller to save a page. This is the only place that can still answer
 * "what did they read".
 *
 * There is deliberately no "restore this". The master profile is everything
 * you have done and a version is a subset of it re-angled at one employer;
 * writing the second over the first would lose whatever was written in
 * between, and autosave would commit that to disk before anyone noticed. A
 * version can be read and it can be printed again. Copying a line back out of
 * it is a decision a person makes, one line at a time.
 */
function Versions({
  application,
  onRead,
  onChanged,
}: {
  application: Application;
  onRead: (version: VersionDetail) => void;
  onChanged: () => void;
}) {
  const { profile, design } = useStore(
    useShallow((s) => ({ profile: s.profile, design: s.design })),
  );
  const [open, setOpen] = useState(false);
  const [list, setList] = useState<Version[] | null>(null);
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState("");

  // Fetched when the section is opened, not with the overview: a screen
  // showing nine applications would otherwise fetch nine lists nobody asked
  // to see.
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    api
      .versions(application.id)
      .then((next) => !cancelled && setList(next))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [open, application.id, application.versions]);

  async function keep() {
    if (!profile || !design) return;
    setBusy("keep");
    try {
      // The server prints the PDF to fill in the page and word counts, so
      // this takes as long as a download does. Said out loud rather than
      // left as a button that looks stuck.
      const kept = await api.keepVersion(application.id, { label: label.trim(), profile, design });
      setLabel("");
      setList((current) => (current ? [kept, ...current] : [kept]));
      onChanged();
      toast.success(
        "Kept",
        `${kept.pages} page${kept.pages === 1 ? "" : "s"}, exactly as it stands now.`,
      );
    } catch (error) {
      if (error instanceof ApiError) toast.error(error.message, error.fix);
    } finally {
      setBusy("");
    }
  }

  async function read(id: string) {
    setBusy(id);
    try {
      onRead(await api.readVersion(id));
    } catch (error) {
      if (error instanceof ApiError) toast.error(error.message, error.fix);
    } finally {
      setBusy("");
    }
  }

  async function print(id: string) {
    setBusy(id);
    try {
      const result = await api.versionPdf(id);
      download(result.blob, result.filename);
      toast.success(`${result.filename} downloaded`, "Printed from the stored document.");
    } catch (error) {
      if (error instanceof ApiError) toast.error(error.message, error.fix);
    } finally {
      setBusy("");
    }
  }

  async function forget(id: string) {
    try {
      await api.deleteVersion(id);
      setList((current) => (current ?? []).filter((v) => v.id !== id));
      onChanged();
    } catch (error) {
      if (error instanceof ApiError) toast.error(error.message, error.fix);
    }
  }

  return (
    <div className="border-t border-line pt-2.5">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="flex items-center gap-1.5 text-xs font-medium text-muted transition-colors duration-150 hover:text-ink"
      >
        <ChevronDown
          size={13}
          className={`transition-transform duration-200 ease-out ${open ? "" : "-rotate-90"}`}
        />
        {application.versions === 0
          ? "No version kept"
          : `${application.versions} version${application.versions === 1 ? "" : "s"} kept`}
      </button>

      {open && (
        <div className="mt-2 flex flex-col gap-2">
          {list === null ? (
            <div className="h-6 animate-pulse rounded bg-sunken" aria-hidden />
          ) : (
            list.map((version) => (
              <div key={version.id} className="flex flex-wrap items-center gap-2 text-xs">
                <span className="tabular-nums text-muted">{when(version.created_at)}</span>
                <span className="text-faint">
                  {version.pages} page{version.pages === 1 ? "" : "s"} · {version.words} words
                </span>
                {version.label && <span className="min-w-0 truncate font-medium">{version.label}</span>}
                <span className="ml-auto flex items-center gap-1">
                  <button
                    type="button"
                    className="btn btn-quiet px-1.5 py-1"
                    onClick={() => void read(version.id)}
                    disabled={busy === version.id}
                    title="Read it as it was"
                    aria-label={`Read the version of ${when(version.created_at)}`}
                  >
                    {busy === version.id ? <Loader2 size={13} className="animate-spin" /> : <Eye size={13} />}
                  </button>
                  <button
                    type="button"
                    className="btn btn-quiet px-1.5 py-1"
                    onClick={() => void print(version.id)}
                    disabled={busy === version.id}
                    title="Print this PDF again"
                    aria-label={`Print the version of ${when(version.created_at)} again`}
                  >
                    <Download size={13} />
                  </button>
                  <button
                    type="button"
                    className="btn btn-quiet px-1.5 py-1"
                    onClick={() => void forget(version.id)}
                    title="Forget this version"
                    aria-label={`Forget the version of ${when(version.created_at)}`}
                  >
                    <Trash2 size={13} />
                  </button>
                </span>
              </div>
            ))
          )}

          <div className="flex flex-wrap items-center gap-2">
            <input
              className="field h-8 min-w-0 flex-1 py-1 text-xs"
              placeholder="What is this one? (optional)"
              aria-label={`Label for a new version of ${application.title || "this application"}`}
              value={label}
              onChange={(event) => setLabel(event.target.value)}
            />
            <button
              type="button"
              className="btn shrink-0 py-1 text-xs"
              onClick={() => void keep()}
              disabled={busy === "keep" || !profile}
            >
              {busy === "keep" ? <Loader2 size={13} className="animate-spin" /> : <Briefcase size={13} />}
              Keep the resume as it stands
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Is the profile catching up with what you are applying for?
 *
 * Drawn rather than charted: a polyline over a viewBox needs no library, and
 * a library for one sparkline is 40KB to answer a question with six numbers
 * in it.
 */
function Trend({ trend }: { trend: [string, number][] }) {
  if (trend.length < ENOUGH_FOR_TREND) {
    return (
      <section className="card p-4">
        <h2 className="text-sm font-semibold">Coverage over time</h2>
        <p className="mt-1 text-sm text-muted">
          Three saved postings and this shows whether the profile is catching up with what
          you are applying for.
        </p>
      </section>
    );
  }

  const values = trend.map(([, coverage]) => coverage);
  const first = values[0]!;
  const last = values[values.length - 1]!;
  const change = last - first;
  const points = values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * 100;
      // The y axis is the full 0-100 the number is on. Scaling to the range
      // present would turn three points a percent apart into a cliff.
      return `${x.toFixed(2)},${(100 - value).toFixed(2)}`;
    })
    .join(" ");

  return (
    <section className="card p-4">
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold">Coverage over time</h2>
        <span
          className={[
            "inline-flex items-center gap-1 text-xs tabular-nums",
            change > 0 ? "text-good" : change < 0 ? "text-poor" : "text-muted",
          ].join(" ")}
        >
          <TrendingUp size={13} />
          {change > 0 ? "+" : ""}
          {change} pts
        </span>
      </div>

      <svg
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        className="mt-3 h-20 w-full"
        role="img"
        aria-label={`Coverage went from ${first}% to ${last}% across ${values.length} postings`}
      >
        <polyline
          points={points}
          fill="none"
          stroke="var(--c-accent)"
          strokeWidth="2"
          vectorEffect="non-scaling-stroke"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      </svg>

      <p className="mt-1 text-xs text-muted tabular-nums">
        {first}% on the first, {last}% on the latest, across {values.length}.
      </p>
    </section>
  );
}

/**
 * What the fabrication guard has actually caught.
 *
 * Kept on screen for the reason the query exists: a check nobody measures is
 * a check nobody can defend. If `flagged` sits at zero over dozens of
 * rewrites, the audit is either working perfectly or not running, and this is
 * the number that starts that conversation.
 */
function Guard({ guard }: { guard: Overview["guard"] }) {
  if (guard.suggested === 0) {
    return (
      <section className="card p-4">
        <h2 className="text-sm font-semibold">The fabrication guard</h2>
        <p className="mt-1 text-sm text-muted">
          Nothing to report: no rewrite has been recorded yet. Every one that is gets diffed
          against its source, and what it invented is kept here.
        </p>
      </section>
    );
  }

  return (
    <section className="card p-4">
      <h2 className="text-sm font-semibold">The fabrication guard</h2>
      <dl className="mt-3 flex flex-col gap-2 text-sm">
        <Stat label="Rewrites proposed" value={guard.suggested} />
        <Stat label="Kept" value={guard.accepted} />
        <Stat
          label="Flagged as inventing something"
          value={guard.flagged}
          tone={guard.flagged > 0 ? "text-fair" : "text-muted"}
        />
        <Stat
          label="Flagged and kept anyway"
          value={guard.accepted_flagged}
          tone={guard.accepted_flagged > 0 ? "text-poor" : "text-good"}
        />
      </dl>
      {guard.accepted_flagged > 0 && (
        <p className="mt-2 text-xs text-muted">
          Those are claims an interviewer can ask you to defend. Worth a second read.
        </p>
      )}
    </section>
  );
}

function Stat({ label, value, tone = "text-ink" }: { label: string; value: number; tone?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="min-w-0 text-muted">{label}</dt>
      <dd className={`shrink-0 font-medium tabular-nums ${tone}`}>{value}</dd>
    </div>
  );
}
