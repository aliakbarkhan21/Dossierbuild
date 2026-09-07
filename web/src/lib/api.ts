/**
 * The only place in the frontend that knows a URL.
 *
 * Every call funnels through `request`, which turns a failure into an
 * `ApiError` carrying both halves of what the server said: what went wrong,
 * and what to do about it. Components show `.message` and `.fix`; none of
 * them have to know that FastAPI reports validation errors as a nested array.
 */

import type {
  ApplicationStatus,
  Design,
  DesignOptions,
  Draft,
  Extracted,
  FitReport,
  Health,
  MatchReport,
  MergePlan,
  Overview,
  Parsed,
  PdfResult,
  Profile,
  QualityReport,
  InterviewBrief,
  LetterBody,
  LetterDetail,
  LetterSummary,
  RewriteResult,
  Suggestion,
  Version,
  VersionDetail,
  CVList,
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
  /** What a zoom of 0 means: fill the pane's width, or fit a whole page. */
  fit?: "width" | "page";
}

export const api = {
  health: () => request<Health>("/api/health"),

  getProfile: () => request<Profile>("/api/profile"),
  saveProfile: (profile: Profile) =>
    request<{ saved: boolean; path: string }>("/api/profile", "PUT", profile),
  quality: () => request<QualityReport>("/api/profile/quality"),
  /** A worked example. Returned, not saved -- loading it is an ordinary edit. */
  sampleProfile: () => request<Profile>("/api/profile/sample"),

  cvs: () => request<CVList>("/api/cvs"),
  newCv: () => request<CVList>("/api/cvs", "POST", {}),
  switchCv: (id: string) => request<CVList>(`/api/cvs/${id}/active`, "PUT"),
  renameCv: (id: string, name: string) => request<CVList>(`/api/cvs/${id}`, "PUT", { name }),
  deleteCv: (id: string) => request<CVList>(`/api/cvs/${id}`, "DELETE"),
  /** An empty profile of the current shape, from the schema that defines it. */
  blankProfile: () => request<Profile>("/api/profile/blank"),

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
    return {
      blob: await response.blob(),
      filename: filenameFrom(disposition, "Resume.pdf"),
      pages: Number(response.headers.get("X-Pages") ?? 0),
      words: Number(response.headers.get("X-Words") ?? 0),
      machineReadable: response.headers.get("X-Machine-Readable") === "1",
    };
  },

  uploadPhoto: (file: File) => upload<{ photo: string }>("/api/profile/photo", file),
  deletePhoto: () => request<{ photo: string }>("/api/profile/photo", "DELETE"),

  suggest: (body: {
    kind: "summary" | "bullet";
    note?: string;
    entry_label?: string;
    section?: string;
    entry_id?: string;
    profile?: Profile;
  }) => request<Draft>("/api/suggest", "POST", body),

  /** Everything the Applications screen shows, in one round trip. */
  applications: () => request<Overview>("/api/applications"),
  /** Analysed by rules on the way in -- saving a posting calls no model. */
  saveApplication: (body: {
    text: string;
    title?: string;
    company?: string;
    source_url?: string;
    notes?: string;
    profile?: Profile;
  }) =>
    request<{ id: string; title: string; coverage: number }>(
      "/api/applications",
      "POST",
      body,
    ),
  recordRun: (
    id: string,
    // Every rewrite the run produced, with the verdict on it -- the rejected
    // ones included, because a rejection is the judgement worth having a
    // record of and the only evidence the fabrication guard catches anything.
    body: { model: string; suggestions: (Suggestion & { accepted: boolean })[] },
  ) =>
    request<{ id: string }>(`/api/applications/${id}/runs`, "POST", body),
  setApplicationStatus: (id: string, status: ApplicationStatus) =>
    request<{ status: string }>(`/api/applications/${id}/status`, "PUT", { status }),
  deleteApplication: (id: string) =>
    request<{ deleted: boolean }>(`/api/applications/${id}`, "DELETE"),

  /** One sheet to read before an interview. Rules only, no model. */
  brief: (id: string) => request<InterviewBrief>(`/api/applications/${id}/brief`),
  setNotes: (id: string, notes: string) =>
    request<{ notes: string }>(`/api/applications/${id}/notes`, "PUT", { notes }),

  /** Keep the document as it stands against one application. */
  keepVersion: (id: string, body: { label?: string; profile?: Profile; design?: Design }) =>
    request<Version>(`/api/applications/${id}/versions`, "POST", body),
  versions: (id: string) => request<Version[]>(`/api/applications/${id}/versions`),
  readVersion: (id: string) => request<VersionDetail>(`/api/versions/${id}`),
  deleteVersion: (id: string) =>
    request<{ deleted: boolean }>(`/api/versions/${id}`, "DELETE"),

  /** The same PDF again, printed from the stored document. */
  async versionPdf(id: string): Promise<PdfResult> {
    const response = await fetch(`/api/versions/${id}/pdf`, { method: "POST" });
    if (!response.ok) throw await failure(response);
    const disposition = response.headers.get("content-disposition") ?? "";
    return {
      blob: await response.blob(),
      filename: filenameFrom(disposition, "Resume.pdf"),
      pages: Number(response.headers.get("X-Pages") ?? 0),
      words: Number(response.headers.get("X-Words") ?? 0),
      machineReadable: response.headers.get("X-Machine-Readable") === "1",
    };
  },

  /** Draft a cover letter. The one call here that needs a key.
   *
   *  Named by application rather than carrying the posting: the advert is
   *  already in the database, and sending it back up the wire would be
   *  shipping the same text twice. */
  draftLetter: (body: {
    application_id?: string;
    text?: string;
    company?: string;
    role?: string;
    recipient?: string;
    note?: string;
    profile?: Profile;
  }) => request<LetterBody>("/api/letter/draft", "POST", body),
  letterPreview: (body: { letter: LetterBody; profile?: Profile; design?: Design; zoom?: number }) =>
    requestText("/api/letter/preview", body),
  letters: (applicationId: string) =>
    request<LetterSummary[]>(`/api/applications/${applicationId}/letters`),
  keepLetter: (
    applicationId: string,
    body: { letter: LetterBody; profile?: Profile; design?: Design; model?: string },
  ) => request<LetterSummary>(`/api/applications/${applicationId}/letters`, "POST", body),
  readLetter: (id: string) => request<LetterDetail>(`/api/letter/${id}`),
  updateLetter: (id: string, body: { letter: LetterBody; profile?: Profile }) =>
    request<LetterSummary>(`/api/letter/${id}`, "PUT", body),
  deleteLetter: (id: string) => request<{ deleted: boolean }>(`/api/letter/${id}`, "DELETE"),

  async letterPdf(body: {
    letter: LetterBody;
    profile?: Profile;
    design?: Design;
  }): Promise<{ blob: Blob; filename: string }> {
    const response = await fetch("/api/letter/pdf", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) throw await failure(response);
    const disposition = response.headers.get("content-disposition") ?? "";
    return { blob: await response.blob(), filename: filenameFrom(disposition, "Cover-Letter.pdf") };
  },

  /** The same letter again, in the design it was written in. */
  async filedLetterPdf(id: string): Promise<{ blob: Blob; filename: string }> {
    const response = await fetch(`/api/letter/${id}/pdf`, { method: "POST" });
    if (!response.ok) throw await failure(response);
    const disposition = response.headers.get("content-disposition") ?? "";
    return { blob: await response.blob(), filename: filenameFrom(disposition, "Cover-Letter.pdf") };
  },

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

/**
 * The filename the server chose, out of a `Content-Disposition` header.
 *
 * The download is a blob and an `<a download>`, so the browser never reads
 * this header itself -- whatever is returned here is the name the file lands
 * under. That matters more than it sounds: a resume for an applicant called
 * 李明 was arriving as `Resume-Classic.pdf` with the name deleted, because
 * this only ever looked at `filename="..."`, which is the ASCII half.
 *
 * RFC 6266 sends both. `filename*` carries the real characters as
 * percent-encoded UTF-8 and is preferred; `filename` is the transliterated
 * fallback for anything that cannot read the first.
 */
export function filenameFrom(disposition: string, fallback: string): string {
  const extended = /filename\*=(?:UTF-8|utf-8)''([^;]+)/.exec(disposition)?.[1];
  if (extended) {
    try {
      const decoded = decodeURIComponent(extended.trim());
      if (decoded) return decoded;
    } catch {
      // A malformed percent sequence is not worth failing a download over;
      // the plain half below is still a perfectly good name.
    }
  }
  return /filename="([^"]+)"/.exec(disposition)?.[1] ?? fallback;
}

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
