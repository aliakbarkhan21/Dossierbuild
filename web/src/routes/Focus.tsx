/**
 * The tags that aim one profile at several kinds of job.
 *
 * The mechanism has worked since 1.1 and had no home. You tag a bullet in the
 * Profile editor; you pick a focus from a dropdown on Resume; and nothing
 * anywhere shows you which tags exist, how much each one selects, or which CV
 * uses which. So this screen is not a new feature so much as the first place
 * the existing one is visible.
 *
 * **The number beside each focus is the point.** A focus tagged on two bullets
 * out of forty prints a document two lines different from any other -- it
 * looks tailored, it reads tailored, and it is not. That is the failure mode
 * of the whole idea, the output gives no sign of it, and a count does.
 *
 * **A default, not a lock.** Setting a CV's focus here changes what it opens
 * with. The Resume dropdown still overrides it for one printing, because
 * binding a focus rigidly to a CV would undo the reason focus tags exist: one
 * profile printed several ways *without* a second CV to keep in step.
 */

import { Pencil, Target } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, api } from "../lib/api";
import { useStore } from "../lib/store";
import { toast } from "../lib/toast";
import type { Coverage, FocusCount } from "../lib/types";

/** Below this, a focus barely changes the document it selects. */
const THIN = 3;

export function FocusScreen() {
  const [data, setData] = useState<Coverage | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState("");

  const load = useCallback(async () => {
    try {
      setData(await api.focus());
      setError("");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not read the focus tags.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function run(work: () => Promise<Coverage>) {
    setBusy(true);
    try {
      setData(await work());
      return true;
    } catch (caught) {
      if (caught instanceof ApiError) toast.error(caught.message, caught.fix);
      return false;
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <header className="border-b border-line px-6 py-4">
        <div className="mx-auto w-full max-w-3xl">
          <h1 className="font-display text-2xl font-semibold tracking-tight">Focus</h1>
          <p className="mt-0.5 text-sm text-muted">
            One profile, aimed at several kinds of job. Tag a bullet{" "}
            <code className="rounded bg-sunken px-1 py-0.5 font-mono text-2xs">#backend</code> and
            it prints only under that focus; untagged lines always print.
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
        ) : data.focuses.length === 0 ? (
          <Empty />
        ) : (
          <>
            <DefaultCard data={data} busy={busy} run={run} />

            <section className="card p-5">
              <h2 className="font-display text-lg font-semibold">What each one selects</h2>
              <p className="mt-1 text-sm text-muted">
                Plus {data.untagged_bullets} untagged{" "}
                {data.untagged_bullets === 1 ? "bullet" : "bullets"} and {data.untagged_skills}{" "}
                untagged skill {data.untagged_skills === 1 ? "group" : "groups"}, which print under
                every focus.
              </p>
              {data.focuses.some((f) => f.bullets + f.skills < THIN) && (
                <p className="mt-2 rounded bg-fair-soft px-2.5 py-2 text-2xs text-fair">
                  A focus marked <strong>thin</strong> selects fewer than {THIN} lines, so the
                  document it prints is barely different from any other. That is the one way this
                  feature fails quietly — the CV looks tailored and is not.
                </p>
              )}
              <ul className="mt-3 flex flex-col divide-y divide-line border-y border-line">
                {data.focuses.map((focus) => (
                  <Row
                    key={focus.tag}
                    focus={focus}
                    editing={editing === focus.tag}
                    busy={busy}
                    onEdit={() => setEditing(focus.tag)}
                    onCancel={() => setEditing("")}
                    onRename={async (next) => {
                      const ok = await run(() => api.renameFocus(focus.tag, next));
                      if (ok) {
                        setEditing("");
                        // The profile in the store is now a rename behind.
                        await useStore.getState().refreshProfile();
                        toast.success(
                          next ? `Renamed to #${next}` : `#${focus.tag} removed`,
                          "Every line carrying it was changed in one pass.",
                        );
                      }
                    }}
                  />
                ))}
              </ul>
            </section>
          </>
        )}
      </div>
    </div>
  );
}

function DefaultCard({
  data,
  busy,
  run,
}: {
  data: Coverage;
  busy: boolean;
  run: (work: () => Promise<Coverage>) => Promise<boolean>;
}) {
  return (
    <section className="card p-5">
      <div className="flex items-start gap-3">
        <Target size={17} className="mt-0.5 shrink-0 text-muted" />
        <div className="min-w-0 flex-1">
          <h2 className="font-display text-lg font-semibold">This CV opens with</h2>
          <p className="mt-1 text-sm text-muted">
            A default, not a lock — the picker on{" "}
            <Link to="/resume" className="underline decoration-line underline-offset-2 hover:text-accent">
              Resume
            </Link>{" "}
            still overrides it for a single printing.
          </p>
          <select
            className="field mt-3 w-full max-w-sm text-sm"
            value={data.active_focus}
            disabled={busy}
            aria-label="Default focus for this CV"
            onChange={(event) => void run(() => api.setDefaultFocus(event.target.value))}
          >
            <option value="">Everything (no focus)</option>
            {data.focuses.map((focus) => (
              <option key={focus.tag} value={focus.tag}>
                #{focus.tag}
              </option>
            ))}
          </select>
        </div>
      </div>
    </section>
  );
}

function Row({
  focus,
  editing,
  busy,
  onEdit,
  onCancel,
  onRename,
}: {
  focus: FocusCount;
  editing: boolean;
  busy: boolean;
  onEdit: () => void;
  onCancel: () => void;
  onRename: (next: string) => void;
}) {
  const [draft, setDraft] = useState(focus.tag);
  const total = focus.bullets + focus.skills;

  if (editing) {
    return (
      <li className="py-2">
        <form
          className="flex flex-wrap items-center gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            onRename(draft.trim());
          }}
        >
          <input
            className="field min-w-0 flex-1 text-sm"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            aria-label={`Rename #${focus.tag}`}
            // eslint-disable-next-line jsx-a11y/no-autofocus -- the row became
            // a form because the user asked to edit this one field.
            autoFocus
          />
          <button type="submit" className="btn btn-primary px-2 py-1 text-xs" disabled={busy}>
            Rename everywhere
          </button>
          <button
            type="button"
            className="btn btn-quiet px-2 py-1 text-xs"
            onClick={onCancel}
            disabled={busy}
          >
            Cancel
          </button>
          <p className="w-full text-2xs text-faint">
            Empty removes <code className="font-mono">#{focus.tag}</code> from every line carrying
            it. Nothing else about those lines changes.
          </p>
        </form>
      </li>
    );
  }

  return (
    <li className="flex items-center gap-3 py-2">
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-center gap-1.5 text-sm">
          <code className="rounded bg-sunken px-1.5 py-0.5 font-mono text-xs">#{focus.tag}</code>
          {focus.cvs.map((name) => (
            <span
              key={name}
              className="rounded bg-accent-soft px-1.5 py-0.5 text-2xs font-medium text-accent"
            >
              {name}
            </span>
          ))}
          {total < THIN && (
            /* The failure mode of the whole feature, stated where it is
               actionable rather than discovered on a printed page. */
            <span className="rounded bg-fair-soft px-1.5 py-0.5 text-2xs font-medium text-fair">
              thin
            </span>
          )}
        </p>
        <p className="text-2xs text-faint">
          {focus.bullets} {focus.bullets === 1 ? "bullet" : "bullets"} · {focus.skills} skill{" "}
          {focus.skills === 1 ? "group" : "groups"}
        </p>
      </div>
      <button
        type="button"
        className="btn btn-quiet shrink-0 px-1.5 py-1"
        onClick={onEdit}
        disabled={busy}
        title={`Rename #${focus.tag} on every line at once`}
        aria-label={`Rename #${focus.tag}`}
      >
        <Pencil size={14} />
      </button>
    </li>
  );
}

function Empty() {
  return (
    <section className="card p-8 text-center">
      <Target size={22} className="mx-auto text-faint" />
      <h2 className="mt-3 font-display text-lg font-semibold">Nothing is tagged yet</h2>
      <p className="mx-auto mt-1 max-w-md text-sm text-muted">
        Tag a bullet or a skill group{" "}
        <code className="rounded bg-sunken px-1 py-0.5 font-mono text-2xs">#backend</code> in the
        Profile editor. Set a focus here or on Resume, and only the lines carrying that tag print —
        alongside everything untagged.
      </p>
      <p className="mt-3 text-sm text-muted">
        It is what lets one profile serve two kinds of job without a second CV to keep in step.
      </p>
      <Link to="/profile" className="btn mt-4 inline-flex">
        Go and tag something
      </Link>
    </section>
  );
}
