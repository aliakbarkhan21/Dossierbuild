/**
 * Toasts, in forty lines and no dependency.
 *
 * A library would bring its own look, and the brief is explicit that nothing
 * here should read as a component someone installed. This is a store and a
 * timer; the appearance lives in `Toaster.tsx` with everything else.
 */

import { create } from "zustand";

export type ToastKind = "success" | "error" | "info";

export interface Toast {
  id: number;
  kind: ToastKind;
  message: string;
  detail?: string;
}

interface ToastState {
  toasts: Toast[];
  push: (toast: Omit<Toast, "id">, ms?: number) => void;
  dismiss: (id: number) => void;
}

let nextId = 1;

export const useToasts = create<ToastState>((set) => ({
  toasts: [],
  push(toast, ms = 4000) {
    const id = nextId++;
    set((state) => ({ toasts: [...state.toasts, { ...toast, id }] }));
    // Errors stay until dismissed: the one message a person needs to read is
    // the one that vanishes while they are still reading it.
    if (toast.kind !== "error") {
      setTimeout(() => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })), ms);
    }
  },
  dismiss(id) {
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
  },
}));

export const toast = {
  success: (message: string, detail?: string) =>
    useToasts.getState().push({ kind: "success", message, detail }),
  error: (message: string, detail?: string) =>
    useToasts.getState().push({ kind: "error", message, detail }),
  info: (message: string, detail?: string) =>
    useToasts.getState().push({ kind: "info", message, detail }),
};
