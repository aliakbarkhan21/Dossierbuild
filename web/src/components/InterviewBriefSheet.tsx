/**
 * One sheet to read before an interview.
 *
 * Everything on it comes from `core/interview.py`, which is rules over the
 * posting already stored in SQLite. No model call, so it says the same thing
 * every time it is opened and works on a train with no signal — which is
 * exactly when someone reads it.
 *
 * It prints. Not through the resume's Chromium pipeline, deliberately: this
 * is a working document for one reader, not a document anyone sends, so it
 * does not need the sheet-at-exact-paper-size machinery and should not pay
 * for it. A print stylesheet on the dialog is the proportionate answer, and
 * `window.print()` is a button the browser already draws.
 *
 * The framing matters as much as the content. The questions are labelled as
 * prompts rather than predictions, and a gap carries the shape of an honest
 * answer rather than an apology — the failure in the room is going quiet.
 */

import { Printer, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { ApiError, api } from "../lib/api";
import { toast } from "../lib/toast";
import type { BriefTerm, InterviewBrief } from "../lib/types";

export function InterviewBriefSheet({
  applicationId,
  onClose,
}: {
  applicationId: string;
  onClose: () => void;
}) {
  const [brief, setBrief] = useState<InterviewBrief | null>(null);
  const [error, setError] = useState("");
  const [notes, setNotes] = useState("");
  const [saved, setSaved] = useState(true);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    api
      .brief(applicationId)
      .then((next) => {
        setBrief(next);
        setNotes(next.notes);
      })
      .catch((caught: unknown) =>
        setError(
          caught instanceof ApiError ? caught.message : "The brief could not be built.",
        ),
      );
  }, [applicationId]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // The scratchpad saves itself a beat after typing stops, the way the profile
  // does. Notes taken the night before an interview are exactly the thing
  // nobody remembers to press save on.
  function edit(value: string) {
    setNotes(value);
    setSaved(false);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      api
        .setNotes(applicationId, value)
        .then(() => setSaved(true))
        .catch((caught: unknown) => {
          if (caught instanceof ApiError) toast.error(caught.message, caught.fix);
        });
    }, 800);
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Interview brief"
      className="brief-layer fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/55 p-4 backdrop-blur-[1px]"
      onPointerDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      {/* Only the sheet reaches the printer. The app's chrome, the scrim and
          the dialog's own buttons are screen furniture. */}
      <style>{`
        @media print {
          body > *:not(.brief-layer) { display: none !important; }
          .brief-layer {
            position: static !important;
            overflow: visible !important;
            background: none !important;
            backdrop-filter: none !important;
            padding: 0 !important;
          }
          .brief-sheet {
            max-width: none !important;
            box-shadow: none !important;
            border: none !important;
          }
          .brief-noprint { display: none !important; }
          .brief-block { break-inside: avoid; }
        }
      `}</style>

      <div className="brief-sheet card my-4 w-full max-w-3xl p-0">
        <div className="brief-noprint flex items-center justify-between gap-3 border-b border-line px-5 py-3">
          <h2 className="font-display text-base font-semibold">Interview brief</h2>
          <div className="flex items-center gap-2">
            <span className="text-2xs text-faint" aria-live="polite">
              {saved ? "Notes saved" : "Saving notes…"}
            </span>
            <button type="button" className="btn" onClick={() => window.print()}>
              <Printer size={14} />
              Print
            </button>
            <button
              type="button"
              className="btn btn-quiet px-1.5 py-1"
              onClick={onClose}
              aria-label="Close the brief"
            >
              <X size={15} />
            </button>
          </div>
        </div>

        {error ? (
          <p className="px-5 py-10 text-center text-sm text-poor">{error}</p>
        ) : !brief ? (
          <div className="space-y-3 p-5" aria-hidden>
            <div className="h-6 w-1/3 animate-pulse rounded bg-sunken" />
            <div className="h-24 animate-pulse rounded bg-sunken" />
            <div className="h-24 animate-pulse rounded bg-sunken" />
          </div>
        ) : (
          <div className="flex flex-col gap-5 p-5">
            <header className="brief-block">
              <h1 className="font-display text-xl font-semibold">
                {brief.title || "This posting"}
              </h1>
              <p className="mt-0.5 text-sm text-muted">
                {brief.company || "No company named"} · your profile evidences{" "}
                {brief.coverage}% of what it asks for
              </p>
            </header>

            <Section
              title="What you can evidence"
              blurb="Say the specific thing. The line under each requirement is already in your profile, so it is a claim you can defend."
              terms={brief.strengths}
              empty="Nothing in this posting is backed by a bullet yet. Everything it asks for is under gaps."
            />

            <Section
              title="Gaps, and what to say about them"
              blurb="A gap is not a reason not to apply. What loses the room is going quiet, so each one carries the shape of an honest answer."
              terms={brief.gaps}
              empty="Nothing this posting requires is missing from your profile."
            />

            {brief.declared_only.length > 0 && (
              <section className="brief-block">
                <h3 className="text-sm font-semibold">Listed but never described</h3>
                <p className="mt-0.5 text-xs text-muted">
                  These are in your skills and in none of your bullets. It is the weakest
                  kind of claim, and a posting asking for one is exactly when that shows —
                  have an example ready.
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {brief.declared_only.map((term) => (
                    <span key={term} className="rounded bg-fair-soft px-1.5 py-0.5 text-2xs text-fair">
                      {term}
                    </span>
                  ))}
                </div>
              </section>
            )}

            <section className="brief-block">
              <label className="label" htmlFor="brief-notes">
                Your notes
              </label>
              <p className="mb-1.5 text-xs text-muted">
                Interviewer names, questions to ask them, salary and logistics. Saved
                against this application and printed with the sheet.
              </p>
              <textarea
                id="brief-notes"
                className="field min-h-32 resize-y text-sm leading-relaxed"
                placeholder={
                  "Who I am meeting:\n\nQuestions to ask them:\n\nSalary and logistics:"
                }
                value={notes}
                onChange={(event) => edit(event.target.value)}
              />
            </section>

            <p className="brief-block text-xs text-faint">
              Built on this machine from the posting you saved. The questions are prompts
              assembled from what the advert asked for — not predictions of what anyone
              will actually ask.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function Section({
  title,
  blurb,
  terms,
  empty,
}: {
  title: string;
  blurb: string;
  terms: BriefTerm[];
  empty: string;
}) {
  return (
    <section className="brief-block">
      <h3 className="text-sm font-semibold">{title}</h3>
      <p className="mt-0.5 text-xs text-muted">{blurb}</p>

      {terms.length === 0 ? (
        <p className="mt-2 text-sm text-muted">{empty}</p>
      ) : (
        <ul className="mt-2 flex flex-col gap-3">
          {terms.map((term) => (
            <li key={term.term} className="brief-block border-l-2 border-l-line pl-3">
              <div className="flex flex-wrap items-baseline gap-2">
                <span className="font-medium">{term.term}</span>
                <span
                  className={[
                    "rounded px-1.5 py-0.5 text-2xs font-medium uppercase tracking-wide",
                    term.tier === "required"
                      ? "bg-poor-soft text-poor"
                      : term.tier === "preferred"
                        ? "bg-fair-soft text-fair"
                        : "bg-sunken text-muted",
                  ].join(" ")}
                >
                  {term.tier}
                </span>
              </div>

              {term.evidence.map((line) => (
                <p key={line.text} className="mt-1 text-sm">
                  <span className="text-faint">{line.entry_label} — </span>
                  {line.text}
                </p>
              ))}

              {term.bridge && <p className="mt-1 text-sm text-muted">{term.bridge}</p>}

              <ul className="mt-1.5 flex flex-col gap-0.5">
                {term.prompts.map((prompt) => (
                  <li key={prompt} className="text-xs text-muted">
                    — {prompt}
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
