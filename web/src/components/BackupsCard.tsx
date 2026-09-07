/**
 * The copies the app has always kept, made reachable.
 *
 * `storage.save_profile` has written a timestamped copy before every write
 * since the beginning, and `cvs.delete` moves a whole deleted CV here rather
 * than unlinking it. Neither was reachable from the interface: the sidebar
 * said "a copy is kept in data/backups", which is an application telling you
 * to go and open a file manager. This is the door, not new machinery.
 *
 * **Restoring makes a new CV rather than overwriting one.** The recovery path
 * is where somebody is already having a bad day, and it must not become a
 * second way to lose work. An extra CV you can delete beats a good CV you
 * cannot get back.
 *
 * Its own file rather than another section of `Settings.tsx`, which is the
 * habit that produced a 1,748-line `Resume.tsx`.
 */

import { Archive, Loader2, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { ApiError, api } from "../lib/api";
import { useStore } from "../lib/store";
import { toast } from "../lib/toast";
import type { BackupSummary } from "../lib/types";

/** How many to show before the list needs opening. */
const PREVIEW = 4;

export function BackupsCard() {
  const [list, setList] = useState<BackupSummary[]>([]);
  const [keep, setKeep] = useState(15);
  const [state, setState] = useState<"loading" | "ready" | "failed">("loading");
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    setState("loading");
    try {
      const body = await api.backups();
      setList(body.backups);
      setKeep(body.keep);
      setState("ready");
    } catch {
      // A named failure with a way back. A backup panel that silently shows
      // nothing reads as "there are no backups", which is the one wrong
      // thing it could say.
      setState("failed");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function restore(backup: BackupSummary) {
    setBusy(backup.id);
    try {
      await api.restoreBackup(backup.id);
      // The restore switched CV server-side, so the client has to catch up:
      // the sidebar list, and the profile now in front of the user.
      await useStore.getState().adoptCv(await api.cvs());
      await load();
      toast.success(
        "Restored into a new CV",
        "You are now on it. The one you were on is untouched and still in the sidebar.",
      );
    } catch (caught) {
      if (caught instanceof ApiError) toast.error(caught.message, caught.fix);
    } finally {
      setBusy("");
    }
  }

  const shown = open ? list : list.slice(0, PREVIEW);

  return (
    <section className="card p-5">
      <div className="flex items-start gap-3">
        <Archive size={17} className="mt-0.5 shrink-0 text-muted" />
        <div className="min-w-0 flex-1">
          <h2 className="font-display text-lg font-semibold">Backups</h2>
          <p className="mt-1 text-sm text-muted">
            A copy is written before every save, and a deleted CV is moved here whole rather than
            removed. The last {keep} per CV are kept. Restoring makes a new CV — it never writes
            over the one you are on.
          </p>

          {state === "loading" && (
            <div className="mt-3 h-20 animate-pulse rounded bg-sunken" aria-hidden />
          )}

          {state === "failed" && (
            <div className="mt-3">
              <p className="text-sm text-poor">Could not read the backup folder.</p>
              <button type="button" className="btn mt-2 px-2 py-1 text-xs" onClick={() => void load()}>
                Try again
              </button>
            </div>
          )}

          {state === "ready" && list.length === 0 && (
            <p className="mt-3 text-sm text-faint">
              None yet. The first is written the next time a CV is saved.
            </p>
          )}

          {state === "ready" && list.length > 0 && (
            <>
              <ul className="mt-3 flex flex-col divide-y divide-line border-y border-line">
                {shown.map((backup) => (
                  <li key={backup.id} className="flex items-center gap-3 py-2">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm">
                        {backup.name || <span className="text-faint">an empty CV</span>}
                        {backup.deleted_cv && (
                          /* The case this panel exists for. */
                          <span className="ml-1.5 rounded bg-poor-soft px-1.5 py-0.5 text-2xs font-medium text-poor">
                            deleted CV
                          </span>
                        )}
                      </p>
                      <p className="truncate text-2xs text-faint">
                        {when(backup.taken)} · {backup.entries}{" "}
                        {backup.entries === 1 ? "entry" : "entries"} · {backup.bullets}{" "}
                        {backup.bullets === 1 ? "bullet" : "bullets"}
                        {backup.cv_name ? ` · from ${backup.cv_name}` : ""}
                        {backup.unreadable ? (
                          <span className="text-poor"> · {backup.unreadable}</span>
                        ) : null}
                      </p>
                    </div>
                    <button
                      type="button"
                      className="btn btn-quiet shrink-0 px-2 py-1 text-xs"
                      disabled={busy !== "" || backup.unreadable !== ""}
                      title={
                        backup.unreadable
                          ? "This file will not parse, so there is nothing to restore."
                          : "Copy this into a new CV"
                      }
                      onClick={() => void restore(backup)}
                    >
                      {busy === backup.id ? (
                        <Loader2 size={13} className="animate-spin" />
                      ) : (
                        <RotateCcw size={13} />
                      )}
                      Restore
                    </button>
                  </li>
                ))}
              </ul>
              {list.length > PREVIEW && (
                <button
                  type="button"
                  className="btn btn-quiet mt-2 px-2 py-1 text-xs"
                  onClick={() => setOpen((was) => !was)}
                >
                  {open ? "Show fewer" : `Show all ${list.length}`}
                </button>
              )}
            </>
          )}
        </div>
      </div>
    </section>
  );
}

/** "Today at 14:32", "Yesterday at 09:04", or the date. */
function when(iso: string): string {
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return iso;
  const time = at.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  const days = Math.round(
    (new Date().setHours(0, 0, 0, 0) - new Date(at.getTime()).setHours(0, 0, 0, 0)) / 86_400_000,
  );
  if (days === 0) return `Today at ${time}`;
  if (days === 1) return `Yesterday at ${time}`;
  return `${at.toLocaleDateString(undefined, { day: "numeric", month: "short" })} at ${time}`;
}
