/**
 * The tags on one bullet or one skill group.
 *
 * Tags are how a single master profile serves more than one job family
 * without being duplicated: a line tagged `backend` prints when the resume is
 * focused on backend work, and an **untagged** line prints always. That
 * default is the whole ergonomics of the feature — a profile where every line
 * must be labelled before any of it appears is a profile nobody finishes
 * labelling — so this control stays out of the way until it is used.
 *
 * Deliberately not a free-text box per tag. The suggestions are the tags
 * already in the profile, because the failure mode here is a person typing
 * `backend`, `back-end` and `Backend` over three sittings and quietly getting
 * three job families. Normalising on the way in is the other half of that,
 * and it matches `design.normalise_tag` on the server.
 */

import { Plus, X } from "lucide-react";
import { useState } from "react";

/** One spelling for a tag, wherever it was typed. Mirrors the server. */
export function normaliseTag(value: string): string {
  return value.trim().replace(/^#+/, "").trim().toLowerCase();
}

export function Tags({
  tags,
  known,
  onChange,
  label,
}: {
  tags: string[];
  /** Every tag already used anywhere in the profile, for the datalist. */
  known: string[];
  onChange: (next: string[]) => void;
  /** What this row of tags belongs to, for the screen reader. */
  label: string;
}) {
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState("");

  function add(value: string) {
    const tag = normaliseTag(value);
    if (tag && !tags.includes(tag)) onChange([...tags, tag]);
    setDraft("");
    setAdding(false);
  }

  return (
    <div className="flex flex-wrap items-center gap-1">
      {tags.map((tag) => (
        <span
          key={tag}
          className="inline-flex items-center gap-1 rounded bg-accent-soft px-1.5 py-0.5 text-2xs text-accent"
        >
          #{tag}
          <button
            type="button"
            onClick={() => onChange(tags.filter((t) => t !== tag))}
            aria-label={`Remove the tag ${tag} from ${label}`}
            className="transition-opacity duration-150 hover:opacity-70"
          >
            <X size={10} />
          </button>
        </span>
      ))}

      {adding ? (
        <>
          <input
            autoFocus
            list="dossier-tags"
            className="field h-6 w-28 px-1.5 py-0 text-2xs"
            placeholder="backend"
            aria-label={`New tag for ${label}`}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                add(draft);
              } else if (event.key === "Escape") {
                setDraft("");
                setAdding(false);
              }
            }}
            // Committing on blur as well as on Enter: half the people who type
            // a tag then click away expect it to have stuck.
            onBlur={() => add(draft)}
          />
          {/* One list for the whole page, so every tag box suggests the same
              vocabulary. Rendered here rather than once at the top because a
              datalist is inert markup and the duplicate ids resolve to the
              same list. */}
          <datalist id="dossier-tags">
            {known.map((tag) => (
              <option key={tag} value={tag} />
            ))}
          </datalist>
        </>
      ) : (
        <button
          type="button"
          onClick={() => setAdding(true)}
          className="inline-flex items-center gap-0.5 rounded px-1 py-0.5 text-2xs text-faint transition-colors duration-150 hover:bg-sunken hover:text-muted"
          aria-label={`Add a tag to ${label}`}
          title="Tag this for a job family, so a focused resume can leave it out"
        >
          <Plus size={10} />
          {tags.length === 0 && "tag"}
        </button>
      )}
    </div>
  );
}

/** Every tag used anywhere, normalised and sorted. Drives the datalist and
 *  the focus selector on the Resume screen. */
export function tagsInUse(profile: {
  experience: { bullets: { tags: string[] }[] }[];
  projects: { bullets: { tags: string[] }[] }[];
  education: { bullets: { tags: string[] }[] }[];
  skills: { tags: string[] }[];
  summary: { tags: string[] };
}): string[] {
  const found = new Set<string>();
  const take = (tags: string[] | undefined) =>
    (tags ?? []).forEach((tag) => {
      const clean = normaliseTag(tag);
      if (clean) found.add(clean);
    });

  take(profile.summary?.tags);
  for (const section of [profile.experience, profile.projects, profile.education]) {
    for (const entry of section ?? []) {
      for (const bullet of entry.bullets ?? []) take(bullet.tags);
    }
  }
  for (const group of profile.skills ?? []) take(group.tags);
  return [...found].sort();
}
