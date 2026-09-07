/**
 * One store for the two documents the app edits: the profile and the design.
 *
 * They are kept apart on purpose, because they behave differently. The
 * profile is irreplaceable, so it is edited locally, marked dirty, and only
 * written when the user (or autosave) says so. The design is a preference:
 * every change is persisted immediately, and nothing is lost if the tab
 * closes mid-thought.
 */

import { create } from "zustand";
import { immer } from "zustand/middleware/immer";

import { ApiError, api } from "./api";
import {
  describeDesign,
  redoStep,
  remember,
  revertStep,
  undoStep,
  type History,
  type Snapshot,
} from "./history";
import type { Design, DesignOptions, Health, Profile, QualityReport,
  CVSummary,
  CVList,
} from "./types";
import { toast } from "./toast";

interface State {
  profile: Profile | null;
  design: Design | null;
  options: DesignOptions | null;
  health: Health | null;
  quality: QualityReport | null;
  /**
   * Why the score is missing, when it is.
   *
   * It used to be swallowed on the grounds that "the score is a nicety". That
   * is true of the number and false of the silence: a Health screen showing
   * nothing, with no explanation, reads as a profile with no findings rather
   * than as a request that did not come back.
   */
  qualityError: string | null;

  ready: boolean;
  bootError: string | null;
  dirty: boolean;
  saving: boolean;
  savedAt: Date | null;

  autosave: boolean;
  /** Oldest first. The state to go back to, and what changed to get here. */
  past: Snapshot[];
  /** What `undo` took away, newest first, so `redo` can put it back. */
  future: Snapshot[];

  /**
   * Bumped whenever the stored portrait changes.
   *
   * The file is always called `photo.jpg`, so replacing one leaves
   * `basics.photo` exactly as it was -- and the preview, which re-renders
   * when the profile changes, had nothing to notice. "Replace" uploaded the
   * new picture and went on showing the old one. This is the part of the
   * portrait the profile cannot hold: which version of that file it is.
   */
  photoVersion: number;

  /**
   * Whether the profile on screen is the worked example.
   *
   * A hint about what the person did, not a fact about the profile, so it
   * stays out of `schema.py` and lives in localStorage instead -- which also
   * means it survives a reload. Without that, someone who loads the sample,
   * closes the tab and comes back finds a stranger's CV and no obvious way
   * to clear it.
   */
  sampleLoaded: boolean;

  boot: () => Promise<void>;
  edit: (mutate: (profile: Profile) => void, label?: string) => void;
  save: (options?: { silent?: boolean }) => Promise<void>;
  undo: () => void;
  redo: () => void;
  /** Jump to a point in the history panel. Index into `past`. */
  revertTo: (index: number) => void;
  setAutosave: (on: boolean) => void;
  refreshQuality: () => Promise<void>;
  setDesign: (patch: Partial<Design>, label?: string) => void;
  reloadProfile: (profile: Profile, label?: string) => void;
  bumpPhoto: () => void;
  /** Every CV in the data directory, and which one is open. */
  cvs: CVSummary[];
  activeCv: string;
  newCv: () => Promise<void>;
  switchCv: (id: string) => Promise<void>;
  deleteCv: (id: string) => Promise<void>;
  syncCvs: () => Promise<void>;
  adoptCv: (list: CVList) => Promise<void>;
  /** Take the server's profile after something changed it behind us. */
  refreshProfile: () => Promise<void>;
  loadSample: () => Promise<void>;
  clearProfile: () => Promise<void>;
  /** Hide the chip without touching the data, for "I am building on this". */
  dismissSample: () => void;
}

/** Design writes are chatty -- a slider is a dozen changes a second. */
let designTimer: ReturnType<typeof setTimeout> | undefined;

/** Autosave waits for a pause in typing, not for a keystroke. */
let saveTimer: ReturnType<typeof setTimeout> | undefined;
const AUTOSAVE_IDLE_MS = 1500;

const SAMPLE_KEY = "dossier:sample";

function samplePreference(): boolean {
  try {
    return localStorage.getItem(SAMPLE_KEY) === "on";
  } catch {
    return false;
  }
}

function rememberSample(on: boolean): void {
  try {
    if (on) localStorage.setItem(SAMPLE_KEY, "on");
    else localStorage.removeItem(SAMPLE_KEY);
  } catch {
    /* a private window may refuse storage; the chip is a nicety */
  }
}

/** Remembered across sessions: an autosave preference is a preference. */
const AUTOSAVE_KEY = "dossier:autosave";

function autosavePreference(): boolean {
  try {
    return localStorage.getItem(AUTOSAVE_KEY) !== "off";
  } catch {
    // A private window can refuse storage outright, and defaulting to "on" is
    // the safe side of that: the cost is a save nobody asked for.
    return true;
  }
}

/**
 * The state as a snapshot -- read from `get()`, **never** from an immer draft.
 *
 * This is the whole trick and it is easy to get wrong. Inside `set((s) => …)`
 * the `s.profile` you can see is a *draft*: immer finalises it at the end of
 * the producer, so a snapshot taken from it ends up holding the state after
 * the edit, not before it. Undo then restored what was already on screen and
 * looked, precisely, like nothing happening.
 *
 * Taken from `get()` before the producer runs, the reference is to the
 * previous, frozen state -- a complete snapshot at no copying cost.
 */
function snapshotOf(s: State): Snapshot {
  return { profile: s.profile!, design: s.design, label: "", at: 0 };
}

/** Put a snapshot back over both documents, if there was one. */
function apply(s: State, step: Snapshot | null): void {
  if (!step) return;
  s.profile = step.profile;
  if (step.design) s.design = step.design;
  s.dirty = true;
}

/**
 * Save once typing stops, rather than on a fixed clock.
 *
 * Each save writes the profile and mints a timestamped backup, so firing
 * every few seconds during a long paragraph would fill the backup folder with
 * half-written sentences. Resetting the timer on every keystroke means one
 * write per thought.
 */
function scheduleAutosave(get: () => State): void {
  clearTimeout(saveTimer);
  if (!get().autosave) return;
  saveTimer = setTimeout(() => {
    const state = get();
    if (state.dirty && !state.saving) void state.save({ silent: true });
  }, AUTOSAVE_IDLE_MS);
}

export const useStore = create<State>()(
  immer((set, get) => ({
    profile: null,
    design: null,
    options: null,
    health: null,
    quality: null,
    qualityError: null,

    ready: false,
    bootError: null,
    dirty: false,
    saving: false,
    savedAt: null,

    autosave: autosavePreference(),
    cvs: [],
    activeCv: "",
    past: [],
    future: [],
    photoVersion: 0,
    sampleLoaded: samplePreference(),

    async boot() {
      try {
        const [profile, design, options, health, cvs] = await Promise.all([
          api.getProfile(),
          api.getDesign(),
          api.options(),
          api.health(),
          api.cvs(),
        ]);
        set((s) => {
          s.profile = profile;
          s.design = design;
          s.options = options;
          s.health = health;
          s.cvs = cvs.cvs;
          s.activeCv = cvs.active;
          s.ready = true;
          s.bootError = null;
        });
        void get().refreshQuality();
      } catch (error) {
        const message =
          error instanceof ApiError
            ? `${error.message}${error.fix ? ` ${error.fix}` : ""}`
            : String(error);
        set((s) => {
          s.bootError = message;
          s.ready = true;
        });
      }
    },

    edit(mutate, label = "Edited the profile") {
      if (!get().profile) return;
      const before = snapshotOf(get());
      set((s) => {
        if (!s.profile) return;
        remember(s as History, before, label);
        mutate(s.profile);
        s.dirty = true;
      });
      scheduleAutosave(get);
    },

    undo() {
      const step = get().past.at(-1);
      if (!step) {
        toast.info("Nothing to undo.");
        return;
      }
      const before = snapshotOf(get());
      set((s) => {
        apply(s, undoStep(s as History, before));
      });
      toast.info(`Undid: ${step.label.toLowerCase()}`, "Ctrl+Shift+Z puts it back.");
      scheduleAutosave(get);
      void get().refreshQuality();
    },

    redo() {
      if (get().future.length === 0) {
        toast.info("Nothing to redo.");
        return;
      }
      const before = snapshotOf(get());
      set((s) => {
        apply(s, redoStep(s as History, before));
      });
      scheduleAutosave(get);
      void get().refreshQuality();
    },

    revertTo(index) {
      const step = get().past[index];
      if (!step) return;
      const before = snapshotOf(get());
      set((s) => {
        apply(s, revertStep(s as History, before, index));
      });
      toast.info(`Went back to before: ${step.label.toLowerCase()}`);
      scheduleAutosave(get);
      void get().refreshQuality();
    },

    setAutosave(on) {
      set((s) => {
        s.autosave = on;
      });
      try {
        localStorage.setItem(AUTOSAVE_KEY, on ? "on" : "off");
      } catch {
        /* a private window may refuse storage; the session still works */
      }
      if (on) scheduleAutosave(get);
      else clearTimeout(saveTimer);
    },

    async save(options) {
      const profile = get().profile;
      if (!profile || get().saving) return;
      // A manual save while a scheduled one is pending would otherwise write
      // twice and mint two backups for one edit.
      clearTimeout(saveTimer);
      set((s) => {
        s.saving = true;
      });
      try {
        await api.saveProfile(profile);
        // Read back rather than trusting the local copy: the server mints ids
        // for anything new, and the editor needs the same ones it will send
        // next time.
        const stored = await api.getProfile();
        set((s) => {
          s.profile = stored;
          s.dirty = false;
          s.saving = false;
          s.savedAt = new Date();
        });
        void get().refreshQuality();
        void get().syncCvs();
        // Autosave stays quiet. The header already reports "Saving" and then
        // "Saved 14:32"; a toast every time typing pauses would be noise
        // announcing that nothing went wrong.
        if (!options?.silent) toast.success("Saved");
      } catch (error) {
        set((s) => {
          s.saving = false;
        });
        if (error instanceof ApiError) toast.error(error.message, error.fix);
        else toast.error("Could not save.");
      }
    },

    async refreshQuality() {
      set((s) => {
        s.quality = null;
        s.qualityError = null;
      });
      try {
        const report = await api.quality();
        set((s) => {
          s.quality = report;
        });
      } catch (error) {
        // Recorded, not raised: the Health screen says so in place, and no
        // other screen is interrupted by a score that did not arrive.
        set((s) => {
          s.qualityError =
            error instanceof ApiError
              ? `${error.message}${error.fix ? ` ${error.fix}` : ""}`
              : "The writing score could not be fetched.";
        });
      }
    },

    setDesign(patch, label) {
      const named = label ?? describeDesign(patch);
      if (!get().design || !get().profile) return;
      const before = snapshotOf(get());
      set((s) => {
        if (!s.design) return;
        // The design is in the same history as the profile, so Ctrl+Z after
        // picking a template undoes the template rather than the last word
        // you typed.
        remember(s as History, before, named);
        Object.assign(s.design, patch);
      });
      clearTimeout(designTimer);
      designTimer = setTimeout(() => {
        const design = get().design;
        if (design) void api.saveDesign(design).catch(() => undefined);
      }, 400);
    },

    reloadProfile(profile, label = "Replaced the profile") {
      // An import is the single largest change anyone makes here, so it is
      // the one that most needs to be reversible -- and it never coalesces
      // with whatever was typed a moment before.
      if (!get().profile) return;
      const before = snapshotOf(get());
      set((s) => {
        remember(s as History, before, label);
        s.past.at(-1)!.at = 0;
        s.profile = profile;
        s.dirty = true;
      });
      scheduleAutosave(get);
    },

    /**
     * Start a fresh CV and open it. The one being left is already on disk.
     *
     * Not an undoable edit, and deliberately not routed through
     * `reloadProfile`: switching document is not a change to a document, and
     * a history that could Ctrl+Z you into a different CV's contents would be
     * a history nobody could reason about. The past is dropped and the new
     * document starts its own.
     */
    async newCv() {
      try {
        const list = await api.newCv();
        await get().adoptCv(list);
        toast.success("New CV started", "The one you were on is saved. Switch back from the sidebar.");
      } catch (error) {
        if (error instanceof ApiError) toast.error(error.message, error.fix);
      }
    },

    async switchCv(id) {
      if (id === get().activeCv) return;
      try {
        await get().adoptCv(await api.switchCv(id));
      } catch (error) {
        if (error instanceof ApiError) toast.error(error.message, error.fix);
      }
    },

    /**
     * Remove a CV. The file is not unlinked -- the registry moves it into
     * ``data/backups`` -- so this is recoverable by hand, which is why it
     * asks once in the sidebar rather than twice.
     *
     * The profile is reloaded only when the CV being deleted is the open one.
     * Deleting a different CV changes nothing about the document in front of
     * you, and reloading it there would throw away any edit autosave has not
     * written yet.
     */
    async deleteCv(id) {
      try {
        const wasActive = id === get().activeCv;
        const list = await api.deleteCv(id);
        if (wasActive) {
          await get().adoptCv(list);
        } else {
          set((s) => {
            s.cvs = list.cvs;
            s.activeCv = list.active;
          });
        }
        toast.info("CV deleted", "A copy is in data/backups if you need it back.");
      } catch (error) {
        if (error instanceof ApiError) toast.error(error.message, error.fix);
      }
    },

    /**
     * Keep the sidebar's label honest after a save, and no more often.
     *
     * A CV we named ("CV 2") takes the profile's name the first time one is
     * saved into it, and stops being empty. Neither is something the client
     * can work out, so it asks -- but only when what it is showing could
     * actually have gone stale. A CV the user has named themselves never
     * changes name under them, so saving into one asks nothing.
     *
     * It matters more than a label usually would: the delete confirmation
     * names the CV it is about, and a stale name there is the one way this
     * control could take the wrong document.
     */
    async syncCvs() {
      const { cvs, activeCv, profile } = get();
      const mine = cvs.find((cv) => cv.id === activeCv);
      const named = profile?.basics.name.trim() ?? "";
      const couldRename = mine?.auto_named && named && mine.name !== named;
      if (!mine || (!mine.blank && !couldRename)) return;
      try {
        const list = await api.cvs();
        set((s) => {
          s.cvs = list.cvs;
          s.activeCv = list.active;
        });
      } catch {
        // A label one save out of date is not worth interrupting anyone over.
      }
    },

    /**
     * Re-read the profile after the server changed it under us.
     *
     * One caller today: renaming a focus retags every line in a single pass
     * on the server, so the copy in this store is a rename behind. Any
     * pending edit is written first -- discarding what someone typed to pick
     * up a change they asked for would be a poor trade, and autosave means
     * the window is small but not zero.
     */
    async refreshProfile() {
      if (get().dirty) await get().save({ silent: true });
      try {
        const profile = await api.getProfile();
        set((s) => {
          s.profile = profile;
          s.dirty = false;
        });
        void get().refreshQuality();
      } catch (error) {
        if (error instanceof ApiError) toast.error(error.message, error.fix);
      }
    },

    /** The half both of the above share: take the server's word for it. */
    async adoptCv(list: CVList) {
      const profile = await api.getProfile();
      set((s) => {
        s.cvs = list.cvs;
        s.activeCv = list.active;
        s.profile = profile;
        s.past = [];
        s.future = [];
        s.dirty = false;
      });
      void get().refreshQuality();
    },

    async loadSample() {
      try {
        const profile = await api.sampleProfile();
        // Through the normal edit path, so it lands in the undo stack: one
        // Ctrl+Z puts back whatever was there before.
        get().reloadProfile(profile, "Loaded the sample profile");
        rememberSample(true);
        set((s) => {
          s.sampleLoaded = true;
        });
        toast.success(
          "Sample profile loaded",
          "Try the templates, the tailoring and a PDF. Clear it whenever you like.",
        );
      } catch (error) {
        if (error instanceof ApiError) toast.error(error.message, error.fix);
      }
    },

    async clearProfile() {
      try {
        get().reloadProfile(await api.blankProfile(), "Cleared the profile");
        rememberSample(false);
        set((s) => {
          s.sampleLoaded = false;
        });
        toast.info("Back to a blank profile", "Ctrl+Z brings it back.");
      } catch (error) {
        if (error instanceof ApiError) toast.error(error.message, error.fix);
      }
    },

    dismissSample() {
      rememberSample(false);
      set((s) => {
        s.sampleLoaded = false;
      });
    },

    bumpPhoto() {
      set((s) => {
        s.photoVersion += 1;
      });
    },
  })),
);

/** Convenience for components that only care whether there is anything yet. */
export function isBlank(profile: Profile | null): boolean {
  if (!profile) return true;
  return (
    !profile.basics.name &&
    !profile.summary.text &&
    profile.experience.length === 0 &&
    profile.projects.length === 0 &&
    profile.education.length === 0 &&
    profile.skills.length === 0
  );
}
