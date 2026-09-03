/**
 * One score, and the sentences behind it.
 *
 * The old screen showed four percentages computed from three bullets --
 * "Quantified 33%" is not a measurement, it is one bullet. So: a single
 * number, an honest refusal to give one until there is enough written to
 * score fairly, and a breakdown that names the specific line to fix.
 */

import { AlertTriangle, CircleAlert, Info } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { useShell } from "../App";
import { TopBar } from "../components/TopBar";
import { useShallow } from "zustand/react/shallow";

import { useStore } from "../lib/store";
import type { Severity } from "../lib/types";

/** Below this, a percentage says more about the sample than the writing. */
const ENOUGH = 5;

const SEVERITY: Record<Severity, { label: string; Icon: typeof Info; tone: string }> = {
  error: { label: "Filler", Icon: AlertTriangle, tone: "text-poor" },
  warning: { label: "Warning", Icon: CircleAlert, tone: "text-fair" },
  note: { label: "Note", Icon: Info, tone: "text-muted" },
};

export function HealthScreen() {
  const shell = useShell();
  const { quality, refresh, profile } = useStore(useShallow((s) => ({
    quality: s.quality,
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

  const lookup = new Map<string, string>();
  if (profile) {
    lookup.set(profile.summary.id, profile.summary.text);
    for (const section of [profile.experience, profile.projects, profile.education]) {
      for (const entry of section) {
        for (const bullet of entry.bullets) lookup.set(bullet.id, bullet.text);
      }
    }
  }

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
        <section className="card flex flex-wrap items-center gap-6 p-5">
          <div>
            <div className="flex items-baseline gap-1.5">
              <span className={`font-display text-3xl ${verdict.text}`}>
                {enough ? `${score}%` : "—"}
              </span>
              <span className="text-sm text-muted">of bullets clean</span>
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
              {quality?.findings.length ?? 0} thing{quality?.findings.length === 1 ? "" : "s"} to look at
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
              {findings.map((finding, index) => {
                const { Icon, tone: colour, label } = SEVERITY[finding.severity];
                return (
                  <li key={`${finding.block_id}-${index}`} className="card p-3">
                    <div className="flex items-center gap-1.5">
                      <Icon size={13} className={colour} />
                      <span className={`text-2xs font-semibold uppercase tracking-wide ${colour}`}>
                        {label}
                      </span>
                    </div>
                    <p className="mt-1.5 text-sm">{lookup.get(finding.block_id) ?? ""}</p>
                    <p className="mt-1 text-xs text-muted">{finding.message}</p>
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
