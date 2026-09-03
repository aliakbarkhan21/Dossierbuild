/**
 * A drafted line, offered over the field it would go into.
 *
 * The panel deliberately covers the input rather than sitting beside it: the
 * choice is between what is written and what is suggested, and putting them
 * side by side asks the reader to hold both at once. Nothing is written until
 * Insert, and Cancel leaves the field exactly as it was.
 *
 * Every draft arrives already checked -- `invented` is what the model asserted
 * that its source did not, and `findings` is the same linter the Health screen
 * runs. Both are shown before Insert is reachable, because a suggestion the
 * app would immediately mark down is not a suggestion worth taking silently.
 */

import { AlertTriangle, Loader2, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { ApiError, api } from "../lib/api";
import { useStore } from "../lib/store";
import { toast } from "../lib/toast";
import type { Draft } from "../lib/types";

interface Props {
  kind: "summary" | "bullet";
  /** Shown on the role a bullet belongs to, so the model knows the context. */
  entryLabel?: string;
  onInsert: (text: string) => void;
}

export function AiSuggest({ kind, entryLabel = "", onInsert }: Props) {
  const [open, setOpen] = useState(false);
  const health = useStore((s) => s.health);

  if (!health?.ai_available) return null;

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="btn btn-quiet gap-1.5 text-xs"
        title="Draft this line from what you tell it — nothing is inserted until you say so"
      >
        <Sparkles size={13} />
        AI suggestion
      </button>
      {open && (
        <Panel
          kind={kind}
          entryLabel={entryLabel}
          onClose={() => setOpen(false)}
          onInsert={(text) => {
            onInsert(text);
            setOpen(false);
          }}
        />
      )}
    </div>
  );
}

function Panel({
  kind,
  entryLabel,
  onClose,
  onInsert,
}: {
  kind: "summary" | "bullet";
  entryLabel: string;
  onClose: () => void;
  onInsert: (text: string) => void;
}) {
  const profile = useStore((s) => s.profile);
  const [note, setNote] = useState("");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [busy, setBusy] = useState(false);
  const noteRef = useRef<HTMLTextAreaElement>(null);

  async function run() {
    setBusy(true);
    try {
      const result = await api.suggest({
        kind,
        note,
        entry_label: entryLabel,
        profile: profile ?? undefined,
      });
      setDraft(result);
    } catch (error) {
      if (error instanceof ApiError) toast.error(error.message, error.fix);
      else toast.error("The suggestion did not come back.");
    } finally {
      setBusy(false);
    }
  }

  // A summary has the whole profile to work from, so it can be drafted the
  // moment the panel opens. A bullet has nothing until the user says what they
  // did, so it waits and puts the cursor in the box.
  useEffect(() => {
    if (kind === "summary") void run();
    else noteRef.current?.focus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      role="dialog"
      aria-label="AI suggestion"
      className="absolute right-0 top-full z-30 mt-1.5 w-[min(30rem,calc(100vw-3rem))] rounded-lg border border-line bg-raised p-3.5 shadow-raised"
    >
      <div className="flex items-center gap-1.5">
        <Sparkles size={13} className="text-accent" />
        <span className="text-2xs font-semibold uppercase tracking-wide text-faint">
          {kind === "summary" ? "Suggested summary" : "Suggested bullet"}
        </span>
      </div>

      {kind === "bullet" && (
        <>
          <p className="mt-1.5 text-xs text-muted">
            In one line, what did you actually do? Plain words are fine — it will
            phrase it, and it will not add a number you did not give it.
          </p>
          <textarea
            ref={noteRef}
            className="field mt-2 min-h-16 resize-y text-sm"
            value={note}
            placeholder="fixed printers and set up new staff accounts for the office"
            onChange={(event) => setNote(event.target.value)}
            onKeyDown={(event) => {
              if ((event.metaKey || event.ctrlKey) && event.key === "Enter") void run();
            }}
          />
        </>
      )}

      {kind === "summary" && !draft && (
        <p className="mt-1.5 text-xs text-muted">
          Written from what your profile already says. Nothing new is invented.
        </p>
      )}

      {busy && (
        <p className="mt-3 flex items-center gap-2 text-sm text-muted">
          <Loader2 size={14} className="animate-spin" />
          Writing it — 10–30 seconds.
        </p>
      )}

      {draft && !busy && (
        <>
          <p className="mt-2.5 rounded-md border border-line bg-surface p-2.5 text-sm leading-relaxed">
            {draft.text}
          </p>

          {draft.invented.length > 0 && (
            <div className="mt-2 flex items-start gap-2 rounded-md border border-poor/40 bg-poor-soft p-2.5">
              <AlertTriangle size={13} className="mt-0.5 shrink-0 text-poor" />
              <p className="text-xs text-poor">
                <b>{draft.invented.join(", ")}</b>{" "}
                {draft.invented.length === 1 ? "is" : "are"} not in what you wrote. If it is
                not true, do not insert it.
              </p>
            </div>
          )}

          {draft.findings.length > 0 && (
            <ul className="mt-2 flex flex-col gap-0.5">
              {draft.findings.map((finding, index) => (
                <li key={index} className="text-2xs text-muted">
                  · {finding}
                </li>
              ))}
            </ul>
          )}
        </>
      )}

      <div className="mt-3 flex items-center gap-2">
        {draft && !busy ? (
          <>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => onInsert(draft.text)}
            >
              Insert
            </button>
            <button type="button" className="btn" onClick={() => void run()} disabled={busy}>
              Try again
            </button>
          </>
        ) : (
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => void run()}
            disabled={busy || (kind === "bullet" && note.trim().length < 12)}
          >
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
            Write it
          </button>
        )}
        <button type="button" className="btn ml-auto" onClick={onClose}>
          Cancel
        </button>
      </div>
    </div>
  );
}
