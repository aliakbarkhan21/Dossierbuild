/**
 * Every save, export and failure says so.
 *
 * Successes fade; errors stay until dismissed, and carry the "what to do
 * next" line the API sends with them.
 */

import { AlertTriangle, CheckCircle2, Info, X } from "lucide-react";

import { useToasts } from "../lib/toast";

const LOOK = {
  success: { Icon: CheckCircle2, tone: "text-good", edge: "border-l-good" },
  error: { Icon: AlertTriangle, tone: "text-poor", edge: "border-l-poor" },
  info: { Icon: Info, tone: "text-accent", edge: "border-l-accent" },
} as const;

export function Toaster() {
  const { toasts, dismiss } = useToasts();

  return (
    <div
      className="pointer-events-none fixed bottom-5 right-5 z-50 flex w-[min(24rem,calc(100vw-2.5rem))] flex-col gap-2"
      role="status"
      aria-live="polite"
    >
      {toasts.map((t) => {
        const { Icon, tone, edge } = LOOK[t.kind];
        return (
          <div
            key={t.id}
            className={`card pointer-events-auto flex items-start gap-2.5 border-l-2 p-3 shadow-overlay ${edge}`}
            style={{ animation: "toast-in 200ms cubic-bezier(0.22,0.61,0.36,1)" }}
          >
            <Icon size={16} className={`mt-0.5 shrink-0 ${tone}`} />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">{t.message}</p>
              {t.detail && <p className="mt-0.5 text-xs text-muted">{t.detail}</p>}
            </div>
            <button
              type="button"
              onClick={() => dismiss(t.id)}
              className="btn btn-quiet -m-1 p-1"
              aria-label="Dismiss"
            >
              <X size={14} />
            </button>
          </div>
        );
      })}
      <style>{`
        @keyframes toast-in {
          from { opacity: 0; transform: translateY(6px); }
          to { opacity: 1; transform: none; }
        }
      `}</style>
    </div>
  );
}
