/**
 * The shapes the API speaks, mirrored by hand.
 *
 * Generating these from the OpenAPI schema was the alternative; it was not
 * worth a build step and a code generator for one backend that ships in the
 * same commit as this file. The schema is validated on the server, so a
 * mismatch here surfaces immediately as a 422 rather than as corrupt data.
 */

export interface TextBlock {
  id: string;
  text: string;
}

export interface Link {
  id: string;
  label: string;
  url: string;
}

export interface Basics {
  name: string;
  headline: string;
  email: string;
  phone: string;
  location: string;
  links: Link[];
  photo: string;
}

export type EmploymentType =
  | "Internship"
  | "Placement"
  | "Part-time"
  | "Full-time"
  | "Freelance"
  | "Volunteer"
  | "Research"
  | "Other";

export interface Experience {
  id: string;
  role: string;
  organisation: string;
  location: string;
  employment_type: EmploymentType;
  start: string | null;
  end: string | null;
  bullets: TextBlock[];
}

export interface Project {
  id: string;
  name: string;
  tagline: string;
  tech: string[];
  url: string;
  start: string | null;
  end: string | null;
  bullets: TextBlock[];
}

export interface Education {
  id: string;
  institution: string;
  credential: string;
  location: string;
  start: string | null;
  end: string | null;
  grade: string;
  coursework: string[];
  bullets: TextBlock[];
}

export interface SkillGroup {
  id: string;
  label: string;
  items: string[];
}

export interface Certification {
  id: string;
  name: string;
  issuer: string;
  issued: string | null;
  url: string;
}

export interface Award {
  id: string;
  title: string;
  awarded_by: string;
  date: string | null;
  note: string;
}

export interface Achievement {
  id: string;
  title: string;
  context: string;
  date: string | null;
  note: string;
}

export interface Profile {
  schema_version: number;
  basics: Basics;
  summary: TextBlock;
  experience: Experience[];
  projects: Project[];
  education: Education[];
  skills: SkillGroup[];
  certifications: Certification[];
  awards: Award[];
  achievements: Achievement[];
}

/** The list sections, in editor order. Keys match the profile's own fields. */
export const LIST_SECTIONS = [
  "experience",
  "projects",
  "education",
  "skills",
  "certifications",
  "awards",
  "achievements",
] as const;
export type ListSection = (typeof LIST_SECTIONS)[number];

export interface Design {
  template: string;
  /** How the body of the page is set, independent of which template drew the
   *  header. See dossier/render/templates/_layouts.html.j2. */
  layout: string;
  page: string;
  margin: string;
  leading: string;
  date_format: string;
  accent: string;
  fonts: string;
  scale: number;
  order: string[];
  hidden: string[];
  show_links: boolean;
  show_headline: boolean;
  show_page_numbers: boolean;
  show_photo: boolean;
}

export interface Option {
  key: string;
  name: string;
  blurb: string;
}

export interface TemplateOption extends Option {
  ats: boolean;
  columns: string;
  best_for: string;
  photo: boolean;
}

export interface AccentOption extends Option {
  hex: string;
}

export interface PageOption extends Option {
  width_mm: number;
  height_mm: number;
}

export interface VariantOption extends Option {
  values: Partial<Design>;
}

export interface LookOption extends Option {
  /** The first variant, for a caller that only wants "apply this look". */
  values: Partial<Design>;
  variants: VariantOption[];
}

export interface DesignOptions {
  templates: TemplateOption[];
  layouts: Option[];
  accents: AccentOption[];
  fonts: Option[];
  pages: PageOption[];
  margins: Option[];
  leading: Option[];
  date_formats: Option[];
  looks: LookOption[];
  sections: Option[];
  scale: { steps: number[]; base_pt: number };
}

export type Severity = "error" | "warning" | "note";

export interface Finding {
  block_id: string;
  severity: Severity;
  message: string;
  icon: string;
}

export interface QualityReport {
  findings: Finding[];
  entries: number;
  bullets: number;
  words: number;
  clean_bullets: number;
  score: number;
  errors: number;
  warnings: number;
  notes: number;
  sections_filled: Record<string, boolean>;
}

export interface Health {
  ok: boolean;
  schema_version: number;
  data_dir: string;
  profile_exists: boolean;
  pdf_available: boolean;
  pdf_detail: string;
  ai_available: boolean;
}

export interface FitReport {
  pages: number;
  words: number;
  size_kb: number;
  machine_readable: boolean;
  found: Record<string, boolean>;
  missing: string[];
  sections: string[];
}

export interface PdfResult {
  blob: Blob;
  filename: string;
  pages: number;
  words: number;
  machineReadable: boolean;
}

export interface Extracted {
  text: string;
  kind: string;
  pages: number;
  warnings: string[];
}

export interface Parsed {
  profile: Profile;
  model: string;
  notes: string[];
}

export interface MergeProposal {
  path: string;
  label: string;
  current: string;
  proposed: string;
  conflicts: boolean;
}

export interface MergeCandidate {
  key: string;
  section: string;
  label: string;
  detail: string;
  is_duplicate: boolean;
  bullets: string[];
}

export interface MergePlan {
  source: string;
  notes: string[];
  fields: MergeProposal[];
  candidates: MergeCandidate[];
}

/* -------------------------------------------------------------------------
   Tailoring
   ---------------------------------------------------------------------- */

export type Tier = "required" | "preferred" | "general";

export interface Term {
  text: string;
  key: string;
  weight: number;
  count: number;
  tier: Tier;
}

export interface Evidence {
  section: string;
  entry_id: string;
  entry_label: string;
  block_id: string;
  text: string;
}

export interface EntryScore {
  section: string;
  entry_id: string;
  label: string;
  score: number;
  matched: string[];
}

export interface MatchReport {
  title: string;
  company: string;
  coverage: number;
  terms: Term[];
  /** Keyed by term key. An empty list means the term is declared in your
   *  skills but never described in a bullet -- covered, but weakly. */
  covered: Record<string, Evidence[]>;
  missing: Term[];
  entries: EntryScore[];
  declared_only: string[];
}

export interface Suggestion {
  block_id: string;
  section: string;
  entry_label: string;
  before: string;
  after: string;
  reason: string;
  /** Numbers and names the rewrite asserts that its source did not. */
  invented: string[];
  findings_before: number;
  findings_after: number;
  terms_added: string[];
}

export interface RewriteResult {
  model: string;
  summary: Suggestion | null;
  suggestions: Suggestion[];
  notes: string[];
}

/** One drafted line, already audited against its source and linted. */
export interface Draft {
  text: string;
  model: string;
  /** Asserted by the draft and not present in what it was given. */
  invented: string[];
  findings: string[];
}
