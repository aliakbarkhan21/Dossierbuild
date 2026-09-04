/**
 * A cover letter for one application.
 *
 * The same shape as the Resume screen — edit on the left, the printed page on
 * the right — because it is the same job: this is a document that gets
 * printed, and the only honest preview of a printed document is the printed
 * document.
 *
 * A letter always belongs to an application. That is not a limitation, it is
 * the point: a letter with no addressee is a paragraph, and the posting is
 * what the draft is written against. With nothing saved yet the screen says
 * so and sends you to Tailor rather than offering an empty form.
 *
 * Drafting is the only thing here that needs a key. Writing one by hand and
 * printing it works with no model at all, because a person who does not want
 * a model writing their letter should still get the paper and the typeface.
 */

import { Briefcase, Download, FileText, Loader2, Save, Sparkles, Target, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useShallow } from "zustand/react/shallow";

import { useShell } from "../App";
import { Frame } from "../components/Frame";
import { TopBar } from "../components/TopBar";
import { ApiError, api, download } from "../lib/api";
import { useStore } from "../lib/store";
import { toast } from "../lib/toast";
import type { Application, LetterBody, LetterSummary } from "../lib/types";

/** Re-render the page a beat after the last keystroke, never during it. */
function useDebounced<T>(value: T, ms: number): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return settled;
}

/**
 * The role, without the company and the city stuck to it.
 *
 * `jobspec` takes an application's title from the first line of the advert,
 * which is usually "Backend Engineer — Northgate Labs, Manchester". That is
 * the right title for a card in a list and the wrong one for the addressee
 * block on a letter, where the company is already on the line above: the
 * letter came out naming Northgate Labs twice.
 */
function roleOnly(title: string, company: string): string {
  // Cut at the first dash of any kind, which is where the employer usually
  // starts, then take the company off whatever is left in case it was joined
  // with "at" or a comma instead.
  let role = title.split(/\s+[—–-]\s+/)[0]!.trim();
  if (company) {
    const escaped = company.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    role = role.replace(new RegExp(`\\s*(at|,)?\\s*${escaped}\\s*$`, "i"), "").trim();
  }
  // Never return nothing: a title that is only the company is still better
  // than a blank field the user has to work out how to fill.
  return role || title.trim();
}

const BLANK: LetterBody = {
  paragraphs: [],
  greeting: "",
  closing: "",
  signature: "",
  recipient: "",
  company: "",
  role: "",
  date: "",
  invented: [],
  model: "",
};

export function LetterScreen() {
  const shell = useShell();
  const [params, setParams] = useSearchParams();
  const { profile, design, health } = useStore(
    useShallow((s) => ({ profile: s.profile, design: s.design, health: s.health })),
  );

  const [applications, setApplications] = useState<Application[] | null>(null);
  const [letter, setLetter] = useState<LetterBody>(BLANK);
  // The paragraphs as one editable block. A letter is prose; making each
  // paragraph its own box would turn writing one into managing a list.
  const [text, setText] = useState("");
  const [filed, setFiled] = useState<LetterSummary[]>([]);
  const [editing, setEditing] = useState("");
  const [busy, setBusy] = useState<"draft" | "pdf" | "keep" | null>(null);
  const [preview, setPreview] = useState("");

  const chosen = params.get("application") ?? "";
  const application = applications?.find((a) => a.id === chosen) ?? applications?.[0];

  useEffect(() => {
    api
      .applications()
      .then(({ applications: list }) => setApplications(list))
      .catch((error: unknown) => {
        if (error instanceof ApiError) toast.error(error.message, error.fix);
        setApplications([]);
      });
  }, []);

  // When the application changes, so does everything the letter is about.
  useEffect(() => {
    if (!application) return;
    setLetter((current) => ({
      ...current,
      company: application.company,
      role: roleOnly(application.title, application.company),
    }));
    api
      .letters(application.id)
      .then(setFiled)
      .catch(() => setFiled([]));
  }, [application?.id, application?.company, application?.title]);

  const body = useMemo<LetterBody>(
    () => ({
      ...letter,
      paragraphs: text
        .split(/\n\s*\n/)
        .map((p) => p.trim())
        .filter(Boolean),
    }),
    [letter, text],
  );

  const previewKey = useDebounced(JSON.stringify({ body, design }), 350);

  useEffect(() => {
    if (!profile || !design || body.paragraphs.length === 0) {
      setPreview("");
      return;
    }
    api
      .letterPreview({ letter: body, profile, design })
      .then(setPreview)
      .catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [previewKey]);

  const setField = useCallback(
    (patch: Partial<LetterBody>) => setLetter((current) => ({ ...current, ...patch })),
    [],
  );

  async function draft() {
    if (!application) return;
    setBusy("draft");
    try {
      const written = await api.draftLetter({
        // The posting is stored with the application, so the server reads it
        // back and re-analyses it by rules. The screen never holds the advert.
        application_id: application.id,
        recipient: letter.recipient,
        role: letter.role,
        profile: profile!,
      });
      setLetter(written);
      setText(written.paragraphs.join("\n\n"));
      setEditing("");
      if (written.invented.length) {
        toast.error(
          `Check ${written.invented.length} claim${written.invented.length === 1 ? "" : "s"} before you send this`,
          `Not evidenced in your profile: ${written.invented.join(", ")}`,
        );
      } else {
        toast.success("Drafted", "Every claim in it is one your profile already makes.");
      }
    } catch (error) {
      if (error instanceof ApiError) toast.error(error.message, error.fix);
    } finally {
      setBusy(null);
    }
  }

  async function toPdf() {
    setBusy("pdf");
    try {
      const result = await api.letterPdf({ letter: body, profile: profile!, design: design! });
      download(result.blob, result.filename);
      toast.success(`${result.filename} downloaded`);
    } catch (error) {
      if (error instanceof ApiError) toast.error(error.message, error.fix);
    } finally {
      setBusy(null);
    }
  }

  async function keep() {
    if (!application) return;
    setBusy("keep");
    try {
      if (editing) {
        await api.updateLetter(editing, { letter: body, profile: profile! });
        toast.success("Saved", "The edit replaced the draft, not a copy of it.");
      } else {
        // Which model wrote it travels on the letter itself, so one written
        // by hand is recorded as hand-written without a second flag to keep
        // in step.
        const kept = await api.keepLetter(application.id, {
          letter: body,
          profile: profile!,
          design: design!,
        });
        setEditing(kept.id);
        toast.success("Filed", `Kept against ${application.company || "this application"}.`);
      }
      setFiled(await api.letters(application.id));
    } catch (error) {
      if (error instanceof ApiError) toast.error(error.message, error.fix);
    } finally {
      setBusy(null);
    }
  }

  async function open(id: string) {
    try {
      const detail = await api.readLetter(id);
      setLetter(detail.letter);
      setText(detail.letter.paragraphs.join("\n\n"));
      setEditing(id);
    } catch (error) {
      if (error instanceof ApiError) toast.error(error.message, error.fix);
    }
  }

  async function forget(id: string) {
    try {
      await api.deleteLetter(id);
      if (editing === id) setEditing("");
      setFiled(await api.letters(application!.id));
      toast.info("Letter deleted");
    } catch (error) {
      if (error instanceof ApiError) toast.error(error.message, error.fix);
    }
  }

  if (!profile || !design) return null;

  return (
    <>
      <TopBar
        title="Cover letter"
        subtitle={
          application
            ? `${application.company || "Untitled"}${application.title ? ` · ${application.title}` : ""}`
            : "One letter per application, on the same paper as the resume."
        }
        sidebarHidden={shell.sidebarHidden}
        onShowSidebar={shell.showSidebar}
        onOpenPalette={shell.openPalette}
        action={
          <button
            type="button"
            className="btn btn-primary"
            onClick={toPdf}
            disabled={busy !== null || body.paragraphs.length === 0}
          >
            {busy === "pdf" ? <Loader2 size={15} className="animate-spin" /> : <Download size={15} />}
            Download PDF
          </button>
        }
      />

      {applications === null ? (
        <div className="p-6">
          <div className="card h-40 animate-pulse bg-sunken" aria-hidden />
        </div>
      ) : applications.length === 0 ? (
        <Empty />
      ) : (
        <div className="grid flex-1 gap-6 p-6 xl:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
          <div className="flex min-w-0 flex-col gap-4">
            <section className="card p-4">
              <label className="label" htmlFor="letter-application">
                Which application
              </label>
              <select
                id="letter-application"
                className="field"
                value={application?.id ?? ""}
                onChange={(event) => {
                  setParams({ application: event.target.value });
                  setEditing("");
                }}
              >
                {applications.map((a) => (
                  <option key={a.id} value={a.id}>
                    {[a.company, a.title].filter(Boolean).join(" · ") || "Untitled posting"}
                  </option>
                ))}
              </select>

              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                <div>
                  <label className="label" htmlFor="letter-recipient">
                    Who it is to
                  </label>
                  <input
                    id="letter-recipient"
                    className="field"
                    placeholder="Ms Okafor — or leave blank"
                    value={letter.recipient}
                    onChange={(event) => setField({ recipient: event.target.value })}
                  />
                </div>
                <div>
                  <label className="label" htmlFor="letter-role">
                    The role
                  </label>
                  <input
                    id="letter-role"
                    className="field"
                    value={letter.role}
                    onChange={(event) => setField({ role: event.target.value })}
                  />
                </div>
              </div>
              {/* Convention, and the sort of thing a letter-reader notices. */}
              <p className="mt-1.5 text-xs text-muted">
                A named reader gets “Yours sincerely”; an unnamed one gets “Yours faithfully”.
                Filled in for you either way.
              </p>
            </section>

            <section className="card flex flex-wrap items-center gap-3 p-4">
              <div className="min-w-0 flex-1">
                <h2 className="text-sm font-semibold">Draft it from the posting</h2>
                <p className="mt-0.5 text-xs text-muted">
                  Built on the requirements your profile can already evidence, and told not to
                  claim the ones it cannot. Every claim is diffed against your profile
                  afterwards.
                </p>
              </div>
              <button
                type="button"
                className="btn"
                onClick={draft}
                disabled={busy !== null || !health?.ai_available}
              >
                {busy === "draft" ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <Sparkles size={14} />
                )}
                Draft
              </button>
              {!health?.ai_available && (
                <p className="w-full text-xs text-fair">
                  No Gemini key, so drafting is off. You can still write the letter below and
                  print it.
                </p>
              )}
            </section>

            {letter.invented.length > 0 && (
              <section className="card border-l-2 border-l-poor p-4">
                <h2 className="text-sm font-semibold text-poor">Check these before you send it</h2>
                <p className="mt-1 text-xs text-muted">
                  Asserted by the letter and not evidenced anywhere in your profile. An
                  interviewer can ask you about any of them.
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {letter.invented.map((claim) => (
                    <span key={claim} className="rounded bg-poor-soft px-1.5 py-0.5 text-2xs text-poor">
                      {claim}
                    </span>
                  ))}
                </div>
              </section>
            )}

            <section className="card flex min-h-0 flex-col p-4">
              <div className="mb-2 flex items-center justify-between gap-3">
                <label className="label mb-0" htmlFor="letter-body">
                  The letter
                </label>
                <span className="text-2xs text-faint">
                  {body.paragraphs.length} paragraph{body.paragraphs.length === 1 ? "" : "s"} ·{" "}
                  {text.trim() ? text.trim().split(/\s+/).length : 0} words
                </span>
              </div>
              <textarea
                id="letter-body"
                className="field min-h-72 flex-1 resize-y text-sm leading-relaxed"
                placeholder={
                  "Write, or press Draft.\n\nA blank line starts a new paragraph. The " +
                  "greeting and the sign-off are added for you, so start with the first " +
                  "sentence of the letter itself."
                }
                value={text}
                onChange={(event) => setText(event.target.value)}
              />

              <div className="mt-3 flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  className="btn"
                  onClick={keep}
                  disabled={busy !== null || body.paragraphs.length === 0}
                >
                  {busy === "keep" ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : (
                    <Save size={14} />
                  )}
                  {editing ? "Save the edit" : "Keep it against this application"}
                </button>
                {editing && (
                  <button
                    type="button"
                    className="btn btn-quiet"
                    onClick={() => {
                      setEditing("");
                      setLetter({ ...BLANK, company: letter.company, role: letter.role });
                      setText("");
                    }}
                  >
                    Start another
                  </button>
                )}
              </div>
            </section>

            {filed.length > 0 && (
              <section className="card p-4">
                <h2 className="text-sm font-semibold">Filed against this application</h2>
                <ul className="mt-2 flex flex-col gap-1.5">
                  {filed.map((one) => (
                    <li key={one.id} className="flex items-center gap-2 text-xs">
                      <FileText size={13} className="shrink-0 text-faint" />
                      <button
                        type="button"
                        onClick={() => void open(one.id)}
                        className={[
                          "min-w-0 flex-1 truncate text-left transition-colors duration-150 hover:text-accent",
                          editing === one.id ? "font-medium text-accent" : "text-muted",
                        ].join(" ")}
                        title="Open this one for editing"
                      >
                        {one.preview || "Untitled letter"}
                      </button>
                      <button
                        type="button"
                        className="btn btn-quiet px-1.5 py-1"
                        onClick={() => void api.filedLetterPdf(one.id).then((r) => download(r.blob, r.filename))}
                        aria-label="Print this letter again"
                        title="Print this letter again"
                      >
                        <Download size={13} />
                      </button>
                      <button
                        type="button"
                        className="btn btn-quiet px-1.5 py-1 text-poor"
                        onClick={() => void forget(one.id)}
                        aria-label="Delete this letter"
                      >
                        <Trash2 size={13} />
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>

          <div className="flex min-w-0 flex-col gap-3">
            <h2 className="text-sm font-semibold">Preview</h2>
            {body.paragraphs.length === 0 ? (
              <div className="card flex min-h-[60vh] flex-1 flex-col items-center justify-center gap-2 p-8 text-center">
                <FileText size={20} className="text-faint" />
                <p className="text-sm text-muted">
                  The page appears here as you write, in the same typeface and on the same paper
                  as your resume.
                </p>
              </div>
            ) : (
              <Frame
                html={preview}
                title="Cover letter preview"
                className="card min-h-[70vh] flex-1 overflow-hidden"
                placeholder={
                  <div className="absolute inset-0 animate-pulse rounded-lg bg-sunken" aria-hidden />
                }
              />
            )}
          </div>
        </div>
      )}
    </>
  );
}

function Empty() {
  return (
    <div className="p-6">
      <section className="card flex max-w-xl flex-col items-start gap-3 p-6">
        <span className="rounded-md bg-accent-soft p-2 text-accent">
          <Briefcase size={18} />
        </span>
        <h2 className="font-display text-lg font-semibold">Save a posting first</h2>
        <p className="text-sm text-muted">
          A letter is written for one job. Paste the posting on Tailor and press{" "}
          <b>Save this application</b>; the letter is then drafted from the requirements it
          names and the ones your profile can actually evidence.
        </p>
        <Link to="/tailor" className="btn btn-primary mt-1">
          <Target size={15} />
          Tailor for a job
        </Link>
      </section>
    </div>
  );
}
