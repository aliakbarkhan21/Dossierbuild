/**
 * The only place in the frontend that knows a URL.
 *
 * Every call funnels through `request`, which turns a failure into an
 * `ApiError` carrying both halves of what the server said: what went wrong,
 * and what to do about it. Components show `.message` and `.fix`; none of
 * them have to know that FastAPI reports validation errors as a nested array.
 */

import type {
  Design,
  DesignOptions,
  Extracted,
  FitReport,
  Health,
  MatchReport,
  MergePlan,
  Parsed,
  PdfResult,
  Profile,
  QualityReport,
  RewriteResult,
} from "./types";

export class ApiError extends Error {
  status: number;
  fix: string;

  constructor(message: string, status: number, fix = "") {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fix = fix;
  }
}

/** Anything JSON-serialisable. The server validates it; TypeScript's job
 *  here is only to stop a `Profile` being rejected for lacking an index
 *  signature it has no reason to have. */
type Body = unknown;

async function failure(response: Response): Promise<ApiError> {
  let message = `${response.status} ${response.statusText}`;
  let fix = "";
  try {
    const body = await response.json();
    if (typeof body?.error === "string") {
      message = body.error;
      fix = typeof body.fix === "string" ? body.fix : "";
    } else if (Array.isArray(body?.detail)) {
      // FastAPI's own validation shape: field path plus reason, which is
      // useful to a person only once it is flattened.
      message = body.detail
        .map((d: { loc?: unknown[]; msg?: string }) => {
          const where = (d.loc ?? []).slice(1).join(" > ");
          return where ? `${where}: ${d.msg}` : d.msg;
        })
        .join("; ");
      fix = "Correct the highlighted field and try again.";
    } else if (typeof body?.detail === "string") {
      message = body.detail;
    }
  } catch {
    /* a non-JSON error body is rare and its status line says enough */
  }
  return new ApiError(message, response.status, fix);
}

async function request<T>(path: string, method = "GET", body?: Body): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      method,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    // The one failure the server cannot describe, because it never heard the
    // request. Naming the command to fix it saves a search.
    throw new ApiError(
      "Could not reach the Dossierbuild server.",
      0,
      "Start it with: uvicorn dossier.api:app --port 8000",
    );
  }
  if (!response.ok) throw await failure(response);
  return (await response.json()) as T;
}

async function requestText(path: string, body?: Body): Promise<string> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  if (!response.ok) throw await failure(response);
  return await response.text();
}

async function upload<T>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(path, { method: "POST", body: form });
  if (!response.ok) throw await failure(response);
  return (await response.json()) as T;
}

/** What the two render endpoints take: unsaved edits win over what is on disk. */
export interface RenderInput {
  profile?: Profile;
  design?: Design;
  zoom?: number;
}

export const api = {
  health: () => request<Health>("/api/health"),

  getProfile: () => request<Profile>("/api/profile"),
  saveProfile: (profile: Profile) =>
    request<{ saved: boolean; path: string }>("/api/profile", "PUT", profile),
  quality: () => request<QualityReport>("/api/profile/quality"),

  getDesign: () => request<Design>("/api/design"),
  saveDesign: (design: Design) => request<Design>("/api/design", "PUT", design),
  options: () => request<DesignOptions>("/api/design/options"),

  preview: (input: RenderInput) => requestText("/api/render/preview", input),
  thumbnail: (input: RenderInput & { template: string }) =>
    requestText("/api/render/thumbnail", input),
  printHtml: (input: RenderInput) => requestText("/api/render/html", input),
  plainText: (input: RenderInput) => requestText("/api/render/text", input),
  report: (input: RenderInput) => request<FitReport>("/api/render/report", "POST", input),

  async pdf(input: RenderInput): Promise<PdfResult> {
    const response = await fetch("/api/render/pdf", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
    if (!response.ok) throw await failure(response);
    const disposition = response.headers.get("content-disposition") ?? "";
    const match = /filename="([^"]+)"/.exec(disposition);
    return {
      blob: await response.blob(),
      filename: match?.[1] ?? "Resume.pdf",
      pages: Number(response.headers.get("X-Pages") ?? 0),
      words: Number(response.headers.get("X-Words") ?? 0),
      machineReadable: response.headers.get("X-Machine-Readable") === "1",
    };
  },

  uploadPhoto: (file: File) => upload<{ photo: string }>("/api/profile/photo", file),
  deletePhoto: () => request<{ photo: string }>("/api/profile/photo", "DELETE"),

  analysePosting: (body: { text: string; title?: string; company?: string; profile?: Profile }) =>
    request<MatchReport>("/api/tailor/analyse", "POST", body),
  rewriteFor: (body: {
    text: string;
    title?: string;
    company?: string;
    profile?: Profile;
    entry_ids?: string[];
  }) => request<RewriteResult>("/api/tailor/rewrite", "POST", body),
  applyRewrites: (profile: Profile, accepted: Record<string, string>) =>
    request<{ profile: Profile; changed: number }>("/api/tailor/apply", "POST", {
      profile,
      accepted,
    }),

  extract: (file: File) => upload<Extracted>("/api/ingest/extract", file),
  parse: (text: string) => request<Parsed>("/api/ingest/parse", "POST", { text }),
  linkedin: (file: File) => upload<Parsed>("/api/ingest/linkedin", file),
  plan: (candidate: Profile, source: string) =>
    request<MergePlan>("/api/ingest/plan", "POST", { candidate, source }),
  applyPlan: (
    candidate: Profile,
    source: string,
    accept_fields: string[],
    accept_candidates: string[],
  ) =>
    request<{ profile: Profile; changes: string[] }>("/api/ingest/apply", "POST", {
      candidate,
      source,
      accept_fields,
      accept_candidates,
    }),
};

/** Hand the browser a file without leaving the page. */
export function download(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  // Revoked on the next tick: doing it synchronously races the download in
  // Safari, and leaking the object URL keeps the whole blob in memory.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
