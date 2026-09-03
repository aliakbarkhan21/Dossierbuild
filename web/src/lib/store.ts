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

  boot: () => Promise<void>;
  edit: (mutate: (profile: Profile) => void) => void;
  save: () => Promise<void>;
  refreshQuality: () => Promise<void>;
  setDesign: (patch: Partial<Design>) => void;
  reloadProfile: (profile: Profile) => void;
}

/** Design writes are chatty -- a slider is a dozen changes a second. */
let designTimer: ReturnType<typeof setTimeout> | undefined;

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
      set((s) => {
        if (!s.profile) return;
        mutate(s.profile);
        s.dirty = true;
      });
    },

    async save() {
      const profile = get().profile;
      if (!profile || get().saving) return;
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
        toast.success("Saved");
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
      set((s) => {
        s.profile = profile;
        s.dirty = true;
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
