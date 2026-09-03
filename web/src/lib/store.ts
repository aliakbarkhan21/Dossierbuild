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
import type { Design, DesignOptions, Health, Profile, QualityReport } from "./types";
import { toast } from "./toast";

interface State {
  profile: Profile | null;
  design: Design | null;
  options: DesignOptions | null;
  health: Health | null;
  quality: QualityReport | null;

  ready: boolean;
  bootError: string | null;
  dirty: boolean;
  saving: boolean;
  savedAt: Date | null;

  autosave: boolean;
  past: Profile[];

  boot: () => Promise<void>;
  edit: (mutate: (profile: Profile) => void) => void;
  save: (options?: { silent?: boolean }) => Promise<void>;
  undo: () => void;
  setAutosave: (on: boolean) => void;
  refreshQuality: () => Promise<void>;
  setDesign: (patch: Partial<Design>) => void;
  reloadProfile: (profile: Profile) => void;
}

/** Design writes are chatty -- a slider is a dozen changes a second. */
let designTimer: ReturnType<typeof setTimeout> | undefined;

/** Autosave waits for a pause in typing, not for a keystroke. */
let saveTimer: ReturnType<typeof setTimeout> | undefined;
const AUTOSAVE_IDLE_MS = 1500;

/**
 * How far back undo reaches.
 *
 * Every edit pushes the whole previous profile, which is cheap -- a large
 * profile is a few tens of kilobytes of plain objects -- and total: there is
 * no per-field undo logic to get wrong when the schema grows a field.
 */
const HISTORY_LIMIT = 50;

const AUTOSAVE_KEY = "dossier:autosave";

function autosavePreference(): boolean {
  try {
    return localStorage.getItem(AUTOSAVE_KEY) !== "off";
  } catch {
    return true;
  }
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

    ready: false,
    bootError: null,
    dirty: false,
    saving: false,
    savedAt: null,

    autosave: autosavePreference(),
    past: [],

    async boot() {
      try {
        const [profile, design, options, health] = await Promise.all([
          api.getProfile(),
          api.getDesign(),
          api.options(),
          api.health(),
        ]);
        set((s) => {
          s.profile = profile;
          s.design = design;
          s.options = options;
          s.health = health;
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

    edit(mutate) {
      // Captured before the draft is applied: immer leaves the previous state
      // untouched and frozen, so keeping the reference is a complete snapshot
      // at no copying cost.
      const previous = get().profile;
      set((s) => {
        if (!s.profile) return;
        mutate(s.profile);
        s.dirty = true;
        if (previous) {
          s.past.push(previous);
          if (s.past.length > HISTORY_LIMIT) s.past.shift();
        }
      });
      scheduleAutosave(get);
    },

    undo() {
      const previous = get().past.at(-1);
      if (!previous) {
        toast.info("Nothing to undo.");
        return;
      }
      set((s) => {
        s.past.pop();
        s.profile = previous;
        s.dirty = true;
      });
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
      try {
        set((s) => {
          s.quality = null;
        });
        const report = await api.quality();
        set((s) => {
          s.quality = report;
        });
      } catch {
        /* the score is a nicety; its absence is not worth interrupting anyone */
      }
    },

    setDesign(patch) {
      set((s) => {
        if (!s.design) return;
        Object.assign(s.design, patch);
      });
      clearTimeout(designTimer);
      designTimer = setTimeout(() => {
        const design = get().design;
        if (design) void api.saveDesign(design).catch(() => undefined);
      }, 400);
    },

    reloadProfile(profile) {
      // An import is the single largest change anyone makes here, so it is
      // the one that most needs to be reversible.
      const previous = get().profile;
      set((s) => {
        if (previous) {
          s.past.push(previous);
          if (s.past.length > HISTORY_LIMIT) s.past.shift();
        }
        s.profile = profile;
        s.dirty = true;
      });
      scheduleAutosave(get);
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
