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
  /**
   * Which job families this line is for. Empty means "always".
   *
   * A fact about the material rather than a styling choice, which is why it
   * lives on the profile: "I did this, and it is the kind of thing a backend
   * team cares about" is a property of the work. Which tag to *print* is
   * `Design.focus`.
   */
  tags: string[];
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
  /** Same rule as a bullet's: empty means the group always prints. */
  tags: string[];
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

/**
 * A section the eight built-in ones have no name for.
 *
 * `title` is the only name it has — there is no default behind it, which is
 * why the heading is profile data here and a design override everywhere else.
 * `text` and `bullets` are not alternatives: a resume that writes a paragraph
 * and then a list under one heading has written one section.
 */
export interface CustomSection {
  id: string;
  title: string;
  text: string;
  bullets: TextBlock[];
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
  sections: CustomSection[];
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
  "sections",
] as const;
export type ListSection = (typeof LIST_SECTIONS)[number];

export interface Design {
  template: string;
  /** How the body of the page is set, independent of which template drew the
   *  header. See dossier/render/templates/_layouts.html.j2. */
  layout: string;
  page: string;
  margin: string;
  margin_custom_mm: number | null;
  leading: string;
  date_format: string;
  accent: string;
  fonts: string;
  scale: number;
  order: string[];
  hidden: string[];
  /** What each section is called, where the default is not the writer's word. */
  labels: Record<string, string>;
  /** Which job family this printing is aimed at. "" prints everything. */
  focus: string;
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
  margin_range: { min: number; max: number; step: number };
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
  /** The resume's own section headings, adopted into the design on accept. */
  headings?: Record<string, string>;
  /**
   * `{section: the section whose heading already covers it}`.
   *
   * A CV that says "Education and Certifications" once has written one
   * heading over two of our sections. The covered one prints beneath the
   * other with no heading of its own, rather than falling back to its
   * default and putting the word on the page twice.
   */
  covered?: Record<string, string>;
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

/**
 * Saved applications: the shapes `/api/applications` returns.
 *
 * Mirrors `core/applications.py`. The counts on an application are joined on
 * in SQL rather than fetched per row, and `required_missing` is already the
 * list of stated requirements this posting asked for and the profile did not
 * evidence -- so a card can be drawn without a second call.
 */
export type ApplicationStatus = "draft" | "applied" | "interview" | "offer" | "rejected";

export interface Application {
  id: string;
  title: string;
  company: string;
  status: ApplicationStatus;
  coverage: number;
  created_at: string;
  updated_at: string;
  /** Stamped the first time it reaches "applied", and never overwritten. */
  applied_at: string | null;
  notes: string;
  source_url: string;
  required_missing: string[];
  runs: number;
  accepted: number;
  /** How many documents have been kept against it. */
  versions: number;
  /** How many cover letters have been filed against it. */
  letters: number;
}

/**
 * A cover letter as the screen holds it: editable text, not a model's output.
 *
 * `invented` is what the fabrication audit found when it was drafted -- the
 * numbers and named things the letter asserts that the profile does not. It
 * survives editing so the warning does not vanish the moment a word is
 * changed somewhere else.
 */
export interface LetterBody {
  paragraphs: string[];
  greeting: string;
  closing: string;
  signature: string;
  recipient: string;
  company: string;
  role: string;
  date: string;
  invented: string[];
  /** Which model wrote it, or "" for a letter written by hand. */
  model: string;
}

export interface LetterSummary {
  id: string;
  application_id: string;
  model: string;
  created_at: string;
  /** The opening words, so a list can say which letter this is. */
  preview: string;
}

export interface LetterDetail extends LetterSummary {
  letter: LetterBody;
  design: Design;
}

/**
 * One document, as it was actually sent.
 *
 * `pages` and `words` were read out of the PDF the server printed at the
 * moment it was kept, not counted from the markup -- the record says what
 * came out of the printer.
 */
export interface Version {
  id: string;
  application_id: string;
  label: string;
  pages: number;
  words: number;
  created_at: string;
}

/** A version with the document itself, ready to render. */
export interface VersionDetail extends Version {
  profile: Profile;
  design: Design;
}

/** One term, counted across every posting that named it. */
export interface Gap {
  term: string;
  tier: Tier;
  postings: number;
  missing_in: number;
  weight: number;
}

export interface Overview {
  applications: Application[];
  gaps: Gap[];
  pipeline: Record<ApplicationStatus, number>;
  /** `[created_at, coverage]`, oldest first. */
  trend: [string, number][];
  guard: {
    suggested: number;
    accepted: number;
    flagged: number;
    accepted_flagged: number;
  };
}


/**
 * One requirement on the interview brief, and what to say about it.
 *
 * `prompts` are questions worth having an answer ready for, assembled from
 * templates by `core/interview.py` — prompts, not predictions. `bridge` is
 * present only on a gap: the shape of an honest answer, because the failure
 * in the room is going quiet.
 */
export interface BriefTerm {
  term: string;
  tier: Tier;
  weight: number;
  evidence: { entry_label: string; text: string }[];
  prompts: string[];
  bridge: string;
}

export interface InterviewBrief {
  title: string;
  company: string;
  coverage: number;
  notes: string;
  strengths: BriefTerm[];
  gaps: BriefTerm[];
  /** Named in your skills and described in no bullet — the weakest claim. */
  declared_only: string[];
}

/** One CV in the data directory. The facts are per-CV; the design is not. */
export interface CVSummary {
  id: string;
  name: string;
  created: string;
  updated: string;
  blank: boolean;
  /** True while the name is still generated, and so still follows the profile. */
  auto_named: boolean;
}

export interface CVList {
  cvs: CVSummary[];
  active: string;
}

/** Everything about the installation rather than about the document. */
export interface Capability {
  ok: boolean;
  detail: string;
}

export interface SettingsStorage {
  data_dir: string;
  env_file: string;
  backups: number;
  bytes: number;
}

export interface Settings {
  key_set: boolean;
  /** `AIza…9f2b`. Never the key itself. */
  key_hint: string;
  /** Exported in the shell rather than written by us, so we cannot remove it. */
  key_from_environment: boolean;
  /** Empty means no pin: walk the ladder from the top. */
  model: string;
  models: string[];
  storage: SettingsStorage;
  ai: Capability;
  pdf: Capability;
}

/** A copy the app kept before a write, or a whole CV that was deleted. */
export interface BackupSummary {
  id: string;
  cv_id: string;
  /** Blank when that CV is gone -- which is when the backup matters most. */
  cv_name: string;
  deleted_cv: boolean;
  taken: string;
  name: string;
  headline: string;
  entries: number;
  bullets: number;
  bytes: number;
  /** Set when the file will not parse. Listed anyway, so it is not a mystery. */
  unreadable: string;
}

export interface BackupList {
  backups: BackupSummary[];
  /** How many are kept per CV, so the screen can say why old ones go. */
  keep: number;
}

/** One focus tag, and how much of the profile it actually selects. */
export interface FocusCount {
  tag: string;
  bullets: number;
  skills: number;
  /** Names of the CVs that open with this focus. */
  cvs: string[];
}

export interface Coverage {
  focuses: FocusCount[];
  /** These print under every focus, and are usually most of the CV. */
  untagged_bullets: number;
  untagged_skills: number;
  active_cv: string;
  active_focus: string;
}
