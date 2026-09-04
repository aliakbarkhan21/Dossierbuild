/**
 * Bringing an existing career in.
 *
 * Three routes in, one way out: everything lands on a review screen where
 * each proposed entry is ticked or not. Nothing an import produces reaches
 * the profile without someone accepting it, which is the whole reason the
 * merge plan exists as a separate step.
 */

import { FileUp, Loader2, Sparkles } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useShell } from "../App";
import { TopBar } from "../components/TopBar";
import { ApiError, api } from "../lib/api";
import { useShallow } from "zustand/react/shallow";

import { useStore } from "../lib/store";
import { toast } from "../lib/toast";
import type { MergePlan, Profile } from "../lib/types";

type Tab = "linkedin" | "file" | "paste";

export function ImportScreen() {
  const shell = useShell();
  const navigate = useNavigate();
  const { reloadProfile, health } = useStore(useShallow((s) => ({
    reloadProfile: s.reloadProfile,
    health: s.health,
  })));

  const [tab, setTab] = useState<Tab>("linkedin");
  const [busy, setBusy] = useState("");
  const [text, setText] = useState("");
  const [candidate, setCandidate] = useState<Profile | null>(null);
  const [plan, setPlan] = useState<MergePlan | null>(null);
  const [source, setSource] = useState("Import");
  const [accepted, setAccepted] = useState<Set<string>>(new Set());
  const [acceptedFields, setAcceptedFields] = useState<Set<string>>(new Set());

  async function propose(profile: Profile, label: string, notes: string[] = []) {
    setCandidate(profile);
    setSource(label);
    const result = await api.plan(profile, label);
    result.notes = [...notes, ...result.notes];
    setPlan(result);
    // Everything new starts ticked, anything that looks like a duplicate does
    // not: the common case is "yes, all of this", and the risky case is the
    // one that needs a deliberate click.
    setAccepted(new Set(result.candidates.filter((c) => !c.is_duplicate).map((c) => c.key)));
    setAcceptedFields(new Set(result.fields.filter((f) => !f.conflicts).map((f) => f.path)));
  }

  async function run<T>(name: string, work: () => Promise<T>): Promise<T | undefined> {
    setBusy(name);
    try {
      return await work();
    } catch (error) {
      if (error instanceof ApiError) toast.error(error.message, error.fix);
      else toast.error("That did not work.");
      return undefined;
    } finally {
      setBusy("");
    }
  }

  async function applyPlan() {
    if (!candidate) return;
    const result = await run("apply", () =>
      api.applyPlan(candidate, source, [...acceptedFields], [...accepted]),
    );
    if (!result) return;
    reloadProfile(result.profile, "Imported into the profile");
    toast.success(
      result.changes.length ? result.changes.join(". ") : "Nothing was selected.",
      "Not saved yet — press Save changes when it looks right.",
    );
    navigate("/profile");
  }

  if (plan) {
    return (
      <>
        <TopBar
          title="Review the import"
          subtitle={`${plan.source} · ${plan.candidates.length} entries found`}
          sidebarHidden={shell.sidebarHidden}
          onShowSidebar={shell.showSidebar}
          onOpenPalette={shell.openPalette}
          action={
            <button type="button" className="btn btn-primary" onClick={applyPlan} disabled={busy !== ""}>
              {busy === "apply" ? <Loader2 size={15} className="animate-spin" /> : null}
              Add {accepted.size + acceptedFields.size} to profile
            </button>
          }
        />
        <div className="mx-auto w-full max-w-4xl flex-1 p-6">
          {plan.notes.map((note, index) => (
            <p key={index} className="mb-2 text-sm text-muted">
              {note}
            </p>
          ))}

          {plan.fields.length > 0 && (
            <section className="card mb-4 p-4">
              <h2 className="mb-3 font-display text-lg">Contact details and summary</h2>
              <ul className="flex flex-col gap-2">
                {plan.fields.map((field) => (
                  <li key={field.path} className="flex items-start gap-2.5">
                    <input
                      type="checkbox"
                      className="mt-1 accent-[var(--c-accent)]"
                      checked={acceptedFields.has(field.path)}
                      onChange={(event) => {
                        const next = new Set(acceptedFields);
                        event.target.checked ? next.add(field.path) : next.delete(field.path);
                        setAcceptedFields(next);
                      }}
                    />
                    <div className="min-w-0">
                      <p className="text-sm font-medium">
                        {field.label}
                        {field.conflicts && (
                          <span className="ml-2 text-2xs uppercase tracking-wide text-fair">
                            replaces what you have
                          </span>
                        )}
                      </p>
                      <p className="truncate text-xs text-muted">{field.proposed}</p>
                      {field.conflicts && (
                        <p className="truncate text-xs text-faint">now: {field.current}</p>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section className="flex flex-col gap-2">
            {plan.candidates.map((entry) => (
              <label
                key={entry.key}
                className="card flex cursor-pointer items-start gap-2.5 p-3 transition-colors duration-150 hover:border-line-strong"
              >
                <input
                  type="checkbox"
                  className="mt-1 accent-[var(--c-accent)]"
                  checked={accepted.has(entry.key)}
                  onChange={(event) => {
                    const next = new Set(accepted);
                    event.target.checked ? next.add(entry.key) : next.delete(entry.key);
                    setAccepted(next);
                  }}
                />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium">{entry.label}</span>
                    <span className="text-2xs uppercase tracking-wide text-faint">
                      {entry.section}
                    </span>
                    {entry.is_duplicate && (
                      <span className="text-2xs uppercase tracking-wide text-fair">
                        already in your profile
                      </span>
                    )}
                  </div>
                  {entry.detail && <p className="text-xs text-muted">{entry.detail}</p>}
                  {entry.bullets.length > 0 && (
                    <ul className="mt-1.5 flex flex-col gap-1">
                      {entry.bullets.map((bullet, index) => (
                        <li key={index} className="text-xs text-muted">
                          · {bullet}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </label>
            ))}
          </section>

          <button
            type="button"
            className="btn mt-4"
            onClick={() => {
              setPlan(null);
              setCandidate(null);
            }}
          >
            Discard this import
          </button>
        </div>
      </>
    );
  }

  return (
    <>
      <TopBar
        title="Import"
        subtitle="Imports only ever add. Nothing already in your profile is replaced without you ticking it."
        sidebarHidden={shell.sidebarHidden}
        onShowSidebar={shell.showSidebar}
        onOpenPalette={shell.openPalette}
      />

      <div className="mx-auto w-full max-w-3xl flex-1 p-6">
        <div className="mb-5 flex gap-1 border-b border-line">
          {(
            [
              ["linkedin", "LinkedIn export"],
              ["file", "Resume file"],
              ["paste", "Paste text"],
            ] as const
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => setTab(key)}
              className={[
                "-mb-px border-b-2 px-3 py-2 text-sm transition-colors duration-150",
                tab === key
                  ? "border-accent font-semibold text-accent"
                  : "border-transparent text-muted hover:text-ink",
              ].join(" ")}
            >
              {label}
            </button>
          ))}
        </div>

        {tab === "linkedin" && (
          <section className="card p-5">
            <p className="max-w-prose text-sm text-muted">
              LinkedIn has no API that returns your positions or education — those endpoints are
              restricted to partner companies. It does let you export your own data, which is
              better anyway: it arrives already structured, so nothing has to be guessed at.
            </p>
            <ol className="mt-3 flex flex-col gap-1 text-sm text-muted">
              <li>1. LinkedIn → Settings &amp; Privacy → Data Privacy</li>
              <li>2. Get a copy of your data → Download larger data archive</li>
              <li>3. Upload the ZIP here without unzipping it</li>
            </ol>
            <FilePicker
              accept=".zip"
              busy={busy === "linkedin"}
              label="Choose the export ZIP"
              onPick={(file) =>
                void run("linkedin", async () => {
                  const parsed = await api.linkedin(file);
                  await propose(parsed.profile, `LinkedIn export (${file.name})`, parsed.notes);
                })
              }
            />
          </section>
        )}

        {tab === "file" && (
          <section className="card p-5">
            <p className="max-w-prose text-sm text-muted">
              Reading the text out of a PDF or DOCX is exact. Working out which line is a job title
              is not, so that part uses Gemini and everything it returns is shown for review.
            </p>
            {!health?.ai_available && (
              <p className="mt-3 rounded-md border border-fair/40 bg-fair-soft p-3 text-sm text-fair">
                No Gemini key found, so a file can be read but not parsed into fields. Put
                GEMINI_API_KEY in .env and restart the server.
              </p>
            )}
            <FilePicker
              accept=".pdf,.docx,.txt,.md"
              busy={busy === "extract"}
              label="Choose a resume file"
              onPick={(file) =>
                void run("extract", async () => {
                  const extracted = await api.extract(file);
                  setText(extracted.text);
                  setTab("paste");
                  extracted.warnings.forEach((warning) => toast.info(warning));
                  toast.success(
                    `Read ${extracted.text.length} characters`,
                    "Check it looks right, then parse it.",
                  );
                })
              }
            />
          </section>
        )}

        {tab === "paste" && (
          <section className="card p-5">
            <p className="max-w-prose text-sm text-muted">
              Paste resume text, or edit what was extracted. If a two-column layout came out
              interleaved, fix it here first — the parse is only as good as this.
            </p>
            <textarea
              className="field mt-3 min-h-72 resize-y font-mono text-xs"
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder="Paste the whole resume here…"
            />
            <div className="mt-3 flex items-center gap-3">
              <button
                type="button"
                className="btn btn-primary"
                disabled={!text.trim() || busy !== "" || !health?.ai_available}
                onClick={() =>
                  void run("parse", async () => {
                    const parsed = await api.parse(text);
                    await propose(parsed.profile, "Pasted text", parsed.notes);
                  })
                }
              >
                {busy === "parse" ? (
                  <Loader2 size={15} className="animate-spin" />
                ) : (
                  <Sparkles size={15} />
                )}
                Parse into profile
              </button>
              <span className="text-xs text-muted">
                {busy === "parse"
                  ? "Gemini is reading it. This takes 10–35 seconds when the flash tier is busy."
                  : `${text.length} characters`}
              </span>
            </div>
          </section>
        )}
      </div>
    </>
  );
}

function FilePicker({
  accept,
  label,
  busy,
  onPick,
}: {
  accept: string;
  label: string;
  busy: boolean;
  onPick: (file: File) => void;
}) {
  const [over, setOver] = useState(false);
  return (
    <label
      onDragOver={(event) => {
        event.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(event) => {
        event.preventDefault();
        setOver(false);
        const file = event.dataTransfer.files?.[0];
        if (file) onPick(file);
      }}
      className={[
        "mt-4 flex cursor-pointer flex-col items-center gap-2 rounded-lg border border-dashed p-6 text-center transition-colors duration-150",
        over ? "border-accent bg-accent-soft" : "border-line-strong hover:border-accent",
      ].join(" ")}
    >
      {busy ? (
        <Loader2 size={20} className="animate-spin text-accent" />
      ) : (
        <FileUp size={20} className="text-faint" />
      )}
      <span className="text-sm font-medium">{label}</span>
      <span className="text-xs text-muted">or drop it here</span>
      <input
        type="file"
        accept={accept}
        className="sr-only"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) onPick(file);
          event.target.value = "";
        }}
      />
    </label>
  );
}

