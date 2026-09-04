/**
 * One score, and the sentences behind it.
 *
 * The old screen showed four percentages computed from three bullets --
 * "Quantified 33%" is not a measurement, it is one bullet. So: a single
 * number, an honest refusal to give one until there is enough written to
 * score fairly, and a breakdown that names the specific line to fix.
 */

import { AlertTriangle, ArrowRight, CircleAlert, Info } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { useShell } from "../App";
import { TopBar } from "../components/TopBar";
import { useShallow } from "zustand/react/shallow";

import { useStore } from "../lib/store";
import type { Finding, Severity } from "../lib/types";

/** Below this, a percentage says more about the sample than the writing. */
const ENOUGH = 5;

const SEVERITY_RANK: Record<Severity, number> = { error: 3, warning: 2, note: 1 };

/** A block is as bad as its worst finding. */
function rank(findings: Finding[]): number {
  return Math.max(...findings.map((f) => SEVERITY_RANK[f.severity]));
}

const SEVERITY: Record<Severity, { label: string; Icon: typeof Info; tone: string }> = {
  error: { label: "Filler", Icon: AlertTriangle, tone: "text-poor" },
  warning: { label: "Warning", Icon: CircleAlert, tone: "text-fair" },
  note: { label: "Note", Icon: Info, tone: "text-muted" },
};

export function HealthScreen() {
  const shell = useShell();
  const { quality, qualityError, refresh, profile } = useStore(useShallow((s) => ({
    quality: s.quality,
    qualityError: s.qualityError,
    refresh: s.refreshQuality,
    profile: s.profile,
  })));
  const [filter, setFilter] = useState<"all" | Severity>("all");

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const findings = (quality?.findings ?? []).filter(
    (f) => filter === "all" || f.severity === filter,
  );

  /**
   * Where each block of prose actually lives.
   *
   * The old version mapped an id to its text and nothing else, which is why a
   * finding could show you the offending sentence but not take you to it. The
   * section and the entry are what turn "Filler" into a link.
   */
  const lookup = new Map<string, { text: string; section: string; entry: string }>();
  if (profile) {
    lookup.set(profile.summary.id, {
      text: profile.summary.text,
      section: "summary",
      entry: "Summary",
    });
    for (const [section, entries] of [
      ["experience", profile.experience],
      ["projects", profile.projects],
      ["education", profile.education],
    ] as const) {
      for (const entry of entries) {
        const label =
          ("role" in entry && [entry.role, entry.organisation].filter(Boolean).join(" · ")) ||
          ("name" in entry && entry.name) ||
          ("credential" in entry && [entry.credential, entry.institution].filter(Boolean).join(" · ")) ||
          "Untitled";
        for (const bullet of entry.bullets) {
          lookup.set(bullet.id, { text: bullet.text, section, entry: label });
        }
      }
    }
  }

  /**
   * One card per block, not one per finding.
   *
   * Three bullets with two problems each was rendering as six cards, the same
   * sentence printed twice in a row -- which reads as six things wrong rather
   * than three. The count in the heading counts blocks for the same reason.
   */
  const grouped = new Map<string, Finding[]>();
  for (const finding of findings) {
    const list = grouped.get(finding.block_id);
    if (list) list.push(finding);
    else grouped.set(finding.block_id, [finding]);
  }
  const blocks = [...grouped.entries()].sort(
    // Worst first: a block carrying filler outranks one with a trailing stop.
    (a, b) => rank(b[1]) - rank(a[1]),
  );

  const enough = (quality?.bullets ?? 0) >= ENOUGH;
  const score = quality?.score ?? 0;
  // Written out rather than composed: Tailwind reads the source for class
  // names, so a template string like `text-${tone}` compiles to nothing.
  const verdict =
    score >= 80
      ? { text: "text-good", bar: "bg-good" }
      : score >= 55
        ? { text: "text-fair", bar: "bg-fair" }
        : { text: "text-poor", bar: "bg-poor" };

  return (
    <>
      <TopBar
        title="Health check"
        subtitle="Every bullet, measured against the writing standard. Nothing here blocks a save."
        sidebarHidden={shell.sidebarHidden}
        onShowSidebar={shell.showSidebar}
        onOpenPalette={shell.openPalette}
        action={
          <Link to="/profile" className="btn btn-primary">
            Edit the writing
          </Link>
        }
      />

      <div className="flex flex-col gap-5 p-6">
        {qualityError && (
          <section className="card flex flex-wrap items-center gap-3 border-l-2 border-l-poor p-4">
            <AlertTriangle size={16} className="shrink-0 text-poor" />
            <p className="min-w-0 flex-1 text-sm">{qualityError}</p>
            <button type="button" className="btn" onClick={() => void refresh()}>
              Try again
            </button>
          </section>
        )}

        {!quality && !qualityError ? (
          // The score is one request against a local file, but it is a
          // request: showing zeroes while it is in flight would read as a
          // profile with nothing wrong in it.
          <div className="card h-28 animate-pulse bg-sunken" aria-hidden />
        ) : (
        <section className="card flex flex-wrap items-center gap-6 p-5">
          <div>
            {/* An em-dash where the number goes left "— of bullets clean" on
                screen, which is not a sentence. With too small a sample the
                honest thing is a phrase, not a punctuation mark. */}
            <div className="flex items-baseline gap-1.5">
              {enough ? (
                <>
                  <span className={`font-display text-3xl ${verdict.text}`}>{score}%</span>
                  <span className="text-sm text-muted">of bullets clean</span>
                </>
              ) : (
                <span className="font-display text-2xl text-muted">Not scored yet</span>
              )}
            </div>
            <p className="mt-1 max-w-md text-xs text-muted">
              {enough
                ? `${quality?.clean_bullets} of ${quality?.bullets} bullets carry no filler and name something specific.`
                : `Write at least ${ENOUGH} bullets and this becomes a fair measurement. There ${
                    quality?.bullets === 1 ? "is" : "are"
                  } ${quality?.bullets ?? 0} so far.`}
            </p>
          </div>

          <div className="ml-auto flex gap-5 text-sm">
            <Count value={quality?.errors ?? 0} label="Filler" tone="text-poor" />
            <Count value={quality?.warnings ?? 0} label="Warnings" tone="text-fair" />
            <Count value={quality?.notes ?? 0} label="Notes" tone="text-muted" />
          </div>
        </section>
        )}

        {enough && (
          <div className="h-1.5 overflow-hidden rounded-full bg-sunken" aria-hidden>
            <div
              className={`h-full rounded-full ${verdict.bar} transition-[width] duration-500 ease-out`}
              style={{ width: `${score}%` }}
            />
          </div>
        )}

        <section>
          <div className="mb-2 flex items-center gap-2">
            <h2 className="text-sm font-semibold">
              {blocks.length} line{blocks.length === 1 ? "" : "s"} to look at
            </h2>
            <div className="ml-auto flex gap-0.5 rounded-md bg-sunken p-0.5">
              {(["all", "error", "warning", "note"] as const).map((key) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setFilter(key)}
                  className={[
                    "rounded px-2 py-1 text-2xs font-medium capitalize transition-colors duration-150",
                    filter === key ? "bg-surface text-ink shadow-subtle" : "text-muted hover:text-ink",
                  ].join(" ")}
                >
                  {key === "all" ? "All" : SEVERITY[key].label}
                </button>
              ))}
            </div>
          </div>

          {findings.length === 0 ? (
            <div className="card p-8 text-center">
              <p className="font-display text-lg">
                {quality?.bullets ? "Nothing flagged" : "Nothing written yet"}
              </p>
              <p className="mx-auto mt-1 max-w-sm text-sm text-muted">
                {quality?.bullets
                  ? "Every bullet names something specific and carries no filler."
                  : "Add a role with a bullet or two and this page will have something to say."}
              </p>
            </div>
          ) : (
            <ul className="flex flex-col gap-2">
              {blocks.map(([blockId, blockFindings]) => {
                const where = lookup.get(blockId);
                return (
                  <li key={blockId} className="card p-3">
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                      <span className="text-2xs font-semibold uppercase tracking-wide text-faint">
                        {where?.entry ?? "Somewhere in your profile"}
                      </span>
                      {where && (
                        // The whole reason the section and entry are looked up:
                        // reading that a line is wrong and then hunting for it
                        // through nine tabs is most of the work.
                        <Link
                          to={`/profile?section=${where.section}&focus=${blockId}`}
                          className="ml-auto flex items-center gap-1 text-xs text-accent hover:underline"
                        >
                          Fix this
                          <ArrowRight size={12} />
                        </Link>
                      )}
                    </div>

                    <p className="mt-1.5 text-sm">{where?.text ?? ""}</p>

                    <ul className="mt-1.5 flex flex-col gap-1">
                      {blockFindings.map((finding, index) => {
                        const { Icon, tone: colour, label } = SEVERITY[finding.severity];
                        return (
                          <li
                            key={`${finding.block_id}-${index}`}
                            className="flex items-start gap-1.5 text-xs"
                          >
                            <Icon size={12} className={`mt-0.5 shrink-0 ${colour}`} />
                            <span className={`shrink-0 font-semibold ${colour}`}>{label}</span>
                            <span className="text-muted">{finding.message}</span>
                          </li>
                        );
                      })}
                    </ul>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      </div>
    </>
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
