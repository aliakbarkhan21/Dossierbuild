/**
 * Everything about the installation rather than about the document.
 *
 * That distinction is the whole reason this screen is allowed to exist. "Seven
 * screens, each doing one thing" is a rule worth keeping, and a settings page
 * is the classic way to break it -- it becomes where things go when nobody
 * decided where they belong. So the test for admission is narrow: a typeface
 * is a property of the CV and belongs on Resume, per printing. An API key is a
 * property of this copy of the app, and belonged nowhere at all.
 *
 * It really did belong nowhere. `ai/parse.py` has had `use_api_key`,
 * `verify_api_key` and `remember_api_key` since the import work -- three
 * careful functions, one of which checks a key before storing it so a typo
 * fails in the box you typed it into rather than on some later screen -- and
 * nothing ever called them. The error text pointed people at the Import page,
 * which has never had a box to paste a key into. Somebody with no key was told
 * what the app could not do and given no way to change it short of editing a
 * dotfile and restarting.
 */

import { Check, Copy, KeyRound, Loader2, Trash2, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { BackupsCard } from "../components/BackupsCard";
import { ApiError, api } from "../lib/api";
import { toast } from "../lib/toast";
import type { Capability, Settings } from "../lib/types";

export function SettingsScreen() {
  const [data, setData] = useState<Settings | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    try {
      setData(await api.settings());
      setError("");
    } catch (caught) {
      // Named, with a way back. A screen that reports what the app can do is
      // the worst possible place to fail silently.
      setError(caught instanceof ApiError ? caught.message : "Could not read the settings.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function run(what: string, work: () => Promise<Settings>) {
    setBusy(what);
    try {
      setData(await work());
      return true;
    } catch (caught) {
      if (caught instanceof ApiError) toast.error(caught.message, caught.fix);
      return false;
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      {/* The heading sits in the same column as the cards. Left-aligned
          against a centred stack reads as two unrelated things on one page. */}
      <header className="border-b border-line px-6 py-4">
        <div className="mx-auto w-full max-w-3xl">
          <h1 className="font-display text-2xl font-semibold tracking-tight">Settings</h1>
          <p className="mt-0.5 text-sm text-muted">
            This copy of the app, not the CV in it. Anything about how a document looks lives on
            Resume.
          </p>
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-3xl flex-col gap-5 p-6">
        {error ? (
          <div className="card p-5">
            <p className="text-sm text-poor">{error}</p>
            <button type="button" className="btn mt-3" onClick={() => void load()}>
              Try again
            </button>
          </div>
        ) : !data ? (
          <div className="card h-40 animate-pulse bg-sunken" aria-hidden />
        ) : (
          <>
            <KeyCard data={data} busy={busy} run={run} />
            <ModelCard data={data} busy={busy} run={run} />
            <CapabilityCard data={data} />
            <BackupsCard />
            <DataCard data={data} />
          </>
        )}
      </div>
    </div>
  );
}

type Run = (what: string, work: () => Promise<Settings>) => Promise<boolean>;

/**
 * The key, checked before it is kept.
 *
 * Verifying first is the whole point of the flow: a key stored without a check
 * comes back as a failure on some later action, by which time the cause is two
 * screens away and looks like the app being broken.
 */
function KeyCard({ data, busy, run }: { data: Settings; busy: string; run: Run }) {
  const [key, setKey] = useState("");

  return (
    <section className="card p-5">
      <div className="flex items-start gap-3">
        <KeyRound size={17} className="mt-0.5 shrink-0 text-muted" />
        <div className="min-w-0 flex-1">
          <h2 className="font-display text-lg font-semibold">Gemini API key</h2>
          <p className="mt-1 text-sm text-muted">
            Optional, and it buys exactly three things: parsing a resume you import, rewriting
            bullets for a posting, and drafting a single line on request. Reading a posting,
            scoring your writing, every template and every PDF work without one.
          </p>

          {data.key_set ? (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded bg-good-soft px-2 py-1 text-xs font-medium text-good">
                <Check size={13} /> A key is set
              </span>
              <code className="rounded bg-sunken px-1.5 py-1 font-mono text-xs text-muted">
                {data.key_hint}
              </code>
              {data.key_from_environment ? (
                // Exported in the shell rather than written by us. Offering a
                // Remove button that cannot work is worse than saying so.
                <span className="text-xs text-faint">
                  set in your environment, so it cannot be removed from here
                </span>
              ) : (
                <button
                  type="button"
                  className="btn btn-quiet px-2 py-1 text-xs text-poor"
                  disabled={busy !== ""}
                  onClick={() =>
                    void run("clear", api.clearKey).then((ok) => {
                      if (ok) toast.info("Key removed", "The AI features are off until you add one.");
                    })
                  }
                >
                  <Trash2 size={13} /> Remove
                </button>
              )}
            </div>
          ) : (
            <p className="mt-3 inline-flex items-center gap-1.5 rounded bg-sunken px-2 py-1 text-xs text-muted">
              <X size={13} /> No key, so the three things above are switched off.
            </p>
          )}

          <form
            className="mt-3 flex flex-wrap items-center gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              if (!key.trim()) return;
              void run("key", () => api.saveKey(key)).then((ok) => {
                if (ok) {
                  setKey("");
                  toast.success("Key saved", "Checked with Google before storing, and it works.");
                }
              });
            }}
          >
            <input
              type="password"
              className="field min-w-0 flex-1 font-mono text-sm"
              placeholder={data.key_set ? "Paste a different key" : "Paste your key"}
              value={key}
              onChange={(event) => setKey(event.target.value)}
              autoComplete="off"
              spellCheck={false}
              aria-label="Gemini API key"
            />
            <button type="submit" className="btn btn-primary" disabled={!key.trim() || busy !== ""}>
              {busy === "key" ? <Loader2 size={14} className="animate-spin" /> : null}
              {busy === "key" ? "Checking…" : "Check and save"}
            </button>
          </form>

          <p className="mt-2 text-2xs text-faint">
            Tested against Google before it is stored, so a typo fails here rather than on the
            screen where you next needed it. Written to <code>.env</code>, which is gitignored.
            Get one free at{" "}
            <a
              className="underline decoration-line underline-offset-2 hover:text-accent"
              href="https://aistudio.google.com/apikey"
              target="_blank"
              rel="noopener noreferrer"
            >
              aistudio.google.com/apikey
            </a>
            .
          </p>
        </div>
      </div>
    </section>
  );
}

/**
 * Which model to try first.
 *
 * Automatic is right for almost everyone: the ladder starts at the newest and
 * falls through on congestion, which is what the spread in response times is
 * actually caused by. Pinning matters when one tier is saturated for an hour
 * and you would rather go straight to a quieter one than pay the fallback each
 * time.
 */
function ModelCard({ data, busy, run }: { data: Settings; busy: string; run: Run }) {
  return (
    <section className="card p-5">
      <h2 className="font-display text-lg font-semibold">Model</h2>
      <p className="mt-1 text-sm text-muted">
        Automatic tries the newest first and falls through to a quieter one when Google is busy —
        which is what a slow answer nearly always is. Pin one only if you have a reason to.
      </p>
      <select
        className="field mt-3 w-full max-w-sm text-sm"
        value={data.model}
        disabled={busy !== "" || !data.key_set}
        aria-label="Which model"
        onChange={(event) => void run("model", () => api.pinModel(event.target.value))}
      >
        <option value="">Automatic (recommended)</option>
        {data.models.map((name) => (
          <option key={name} value={name}>
            {name}
          </option>
        ))}
      </select>
      {!data.key_set && <p className="mt-2 text-2xs text-faint">Add a key to change this.</p>}
    </section>
  );
}

/** What the app can do right now, said plainly rather than discovered later. */
function CapabilityCard({ data }: { data: Settings }) {
  return (
    <section className="card p-5">
      <h2 className="font-display text-lg font-semibold">What this copy can do</h2>
      <ul className="mt-3 flex flex-col gap-2">
        <Row
          label="Print a PDF"
          note="Chromium, run locally. Nothing is uploaded to print."
          state={data.pdf}
        />
        <Row
          label="Parse an import, rewrite, and draft"
          note="The only three things that call a model."
          state={data.ai}
        />
      </ul>
    </section>
  );
}

function Row({ label, note, state }: { label: string; note: string; state: Capability }) {
  return (
    <li className="flex items-start gap-2.5">
      <span
        className={`mt-0.5 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full ${
          state.ok ? "bg-good-soft text-good" : "bg-sunken text-faint"
        }`}
      >
        {state.ok ? <Check size={11} /> : <X size={11} />}
      </span>
      <span className="min-w-0">
        <span className="text-sm">{label}</span>
        <span className="block text-2xs text-faint">{state.detail || note}</span>
      </span>
    </li>
  );
}

/**
 * Where the data is.
 *
 * "Your history stays on your machine" is the app's whole argument, and an
 * argument you cannot verify is a slogan. This is the path, so you can go and
 * look.
 */
function DataCard({ data }: { data: Settings }) {
  const [copied, setCopied] = useState("");

  function copy(text: string, which: string) {
    void navigator.clipboard
      ?.writeText(text)
      .then(() => {
        setCopied(which);
        setTimeout(() => setCopied(""), 1600);
      })
      .catch(() => toast.error("Could not copy that.", "Select the path and copy it by hand."));
  }

  return (
    <section className="card p-5">
      <h2 className="font-display text-lg font-semibold">Your data</h2>
      <p className="mt-1 text-sm text-muted">
        All of it, on this machine. Nothing is uploaded except the text you explicitly send to a
        model, and there is no account to delete.
      </p>
      <dl className="mt-3 flex flex-col gap-2.5">
        <Path
          term="Profiles, portrait, applications"
          value={data.storage.data_dir}
          extra={`${data.storage.backups} backup${data.storage.backups === 1 ? "" : "s"} · ${formatBytes(data.storage.bytes)}`}
          copied={copied === "data"}
          onCopy={() => copy(data.storage.data_dir, "data")}
        />
        <Path
          term="API key"
          value={data.storage.env_file}
          extra="gitignored"
          copied={copied === "env"}
          onCopy={() => copy(data.storage.env_file, "env")}
        />
      </dl>
    </section>
  );
}

function Path({
  term,
  value,
  extra,
  copied,
  onCopy,
}: {
  term: string;
  value: string;
  extra: string;
  copied: boolean;
  onCopy: () => void;
}) {
  return (
    <div className="min-w-0">
      <dt className="text-2xs uppercase tracking-wide text-faint">
        {term} · {extra}
      </dt>
      <dd className="mt-1 flex items-center gap-1.5">
        <code className="min-w-0 flex-1 truncate rounded bg-sunken px-2 py-1 font-mono text-xs text-muted">
          {value}
        </code>
        <button
          type="button"
          className="btn btn-quiet shrink-0 px-1.5 py-1"
          onClick={onCopy}
          title={`Copy the path to ${term.toLowerCase()}`}
          aria-label={`Copy the path to ${term.toLowerCase()}`}
        >
          {copied ? <Check size={14} className="text-good" /> : <Copy size={14} />}
        </button>
      </dd>
    </div>
  );
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
