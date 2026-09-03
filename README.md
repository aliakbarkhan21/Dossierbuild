# Dossier

An AI-assisted resume builder. You maintain one complete "master profile" of
everything you have done; each application gets a version tailored to that job,
rendered to a real PDF.

**Status: phases 0-3 complete.** Profile schema, storage, editor and import;
eight print templates, a live preview that is the printed page, and real PDF
output. The interface is React over a FastAPI core; Streamlit is gone.

---

## Running it

```bash
pip install -r requirements.txt
python -m playwright install chromium      # the PDF pipeline needs a browser
cd web && npm install && npm run build     # the interface, built to web/dist
cd .. && python -m uvicorn dossier.api:app --port 8000
```

Then open <http://localhost:8000>. One process serves both the API and the
interface, so a machine running Dossier needs Python and Chromium but no Node.

On Windows, `scripts/launch.vbs` does all of that window-less and opens the
browser once the port answers -- it is what the desktop shortcut runs.
`scripts/stop.cmd` stops it.

While working on the frontend, run Vite instead for hot reload:

```bash
cd web && npm run dev      # 5173, proxying /api to 8000
```

Optional, and only needed for resume import (and later, AI tailoring):

```bash
cp .env.example .env      # then paste your key into it
```

Get a free Gemini key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).
The LinkedIn import route does not use AI and needs no key.

### Checks

```bash
pip install -r requirements-dev.txt
pytest                            # 59 checks, about 16 seconds
```

Or without pytest -- each script runs on the app's own dependencies:

```bash
python scripts/check_phase1.py    # schema, storage, id stability, migration
python scripts/check_import.py    # LinkedIn export, extraction, merge
python scripts/check_phase2.py    # design, templates, PDF and its text layer
```

The phase 2 checks print a real PDF, so they need Chromium:

```bash
python -m playwright install chromium
```

### In a container

```bash
docker build -t dossier .
docker run -p 8000:8000 -v "$PWD/data:/data" -e GEMINI_API_KEY=... dossier
```

---

## What exists

```
dossier/
  core/
    schema.py               the master profile contract (Pydantic v2)
    storage.py              load / validate / atomic save / migrate
    quality.py              the bullet-writing standard, as code
    settings.py             UI preferences
    ids.py                  stable short ids
  ingest/
    linkedin.py             LinkedIn data-export ZIP -> profile  (no AI)
    extract.py              PDF / DOCX / text -> plain text       (no AI)
    merge.py                folding an import into what exists
  ai/
    parse.py                resume text -> profile                (Gemini)
  render/
    design.py               the presentation choices, validated
    context.py              profile -> exactly what a template needs
    html.py                 Jinja2 -> one self-contained HTML document
    pdf.py                  Chromium prints it; pypdf reads it back
    photo.py                the portrait, normalised and embedded
    text.py                 the profile as plain text, for forms
    templates/              _base + Classic, Modern, Minimalist, Compact,
                            Executive, Gazette, Sidebar, Editorial
  api/                      FastAPI over core
    static.py               serves web/dist, so shipping is one process
web/                        React + Vite + TypeScript + Tailwind
  src/styles/tokens.css     the design system, in both themes
scripts/                    self-checks, and the desktop launcher
data/                       your data. gitignored. backed up on every save.
```

---

## The data model

One file, `data/profile.json`, holding facts only:

```jsonc
{
  "schema_version": 1,
  "basics":  { "name": "", "headline": "", "email": "", "phone": "",
               "location": "", "links": [{ "id": "lnk_…", "label": "", "url": "" }] },
  "summary": { "id": "sum_main", "text": "" },
  "experience": [{ "id": "exp_…", "role": "", "organisation": "", "location": "",
                   "employment_type": "Internship", "start": "2025-06", "end": null,   // "2025" is also valid: year-only precision
                   "bullets": [{ "id": "blt_…", "text": "" }] }],
  "projects":       [{ "id": "prj_…", "name": "", "tagline": "", "tech": [], "url": "",
                       "start": null, "end": null, "bullets": [] }],
  "education":      [{ "id": "edu_…", "institution": "", "credential": "", "location": "",
                       "start": null, "end": null, "grade": "", "coursework": [],
                       "bullets": [] }],
  "skills":         [{ "id": "skg_…", "label": "Languages", "items": ["Python", "SQL"] }],
  "certifications": [{ "id": "crt_…", "name": "", "issuer": "", "issued": null, "url": "" }],
  "awards":         [{ "id": "awd_…", "title": "", "awarded_by": "", "date": null, "note": "" }]
}
```

Four properties are load-bearing for later phases:

**Every entry and bullet has a stable id.** Phase 3 sends bullets to Gemini and
gets rewrites back. Keyed by id, a rewrite maps to its original even though the
text has changed — which is what makes a per-bullet accept/revert diff possible.
Matching on text would fail precisely because rewriting is what changed the text.

**Dates are strings, at the precision actually known** — `"2025-06"` or `"2025"`.
JSON has no date type, resumes work in months, and the file stays hand-editable.
Year-only is allowed on purpose: if a source only says "2027", storing `"2027-01"`
would print a month on your resume that nobody ever stated. `format_date` renders
each at its own precision. `end: null` alone means ongoing.

**No styling, no per-application state.** Colours and fonts belong to the
template layer; "leave this off for that job" belongs to the version layer. This
file never goes stale for a particular application.

**`schema_version` with a migration hook.** Adding a field later upgrades
existing files instead of stranding them.

---

## Importing

Three routes, all landing on the same review screen — everything new is ticked,
anything resembling an existing entry is not, and nothing changes until you
press Add.

**LinkedIn export (best; no AI).** LinkedIn's API will not give you your own
positions, education or skills — those endpoints have been partner-only since
2015, and "Sign in with LinkedIn" returns just your name and email. Scraping a
logged-in page is prohibited by their User Agreement and risks the account. But
LinkedIn will hand you the whole thing as CSVs: **Settings → Data Privacy → Get
a copy of your data**. Upload that ZIP. Parsing is deterministic, so nothing is
guessed at.

**Resume file.** PDF, DOCX or text. Extraction is exact; structuring the result
uses Gemini, which is told to transcribe rather than rewrite. The extracted text
is shown for review before parsing, so extraction failures stay distinguishable
from parsing failures. Your LinkedIn profile's `More → Save to PDF` works here.

**Paste text.** For when a PDF will not extract cleanly.

---

## Writing bullets

`quality.py` checks every bullet and flags what will not survive a reader. It
never blocks a save.

A bullet should be something only you could have written. If the nouns could be
swapped out and it would still describe someone else, it is not doing any work.

| Instead of | Write |
| --- | --- |
| Responsible for maintaining the data pipeline | Cut nightly ETL runtime from 42 to 9 minutes by batching Postgres writes |
| Worked on a machine learning project | Trained a ResNet-18 on 12k labelled images; 91% top-1, up from 78% for the baseline |
| Assisted with testing | Added 61 pytest cases over the invoice parser, catching 3 rounding bugs before release |

What gets flagged: duty language and filler in any tense (`Responsible for`,
`Worked on` / `working on`, `Various`, `Successfully`), weak opening verbs,
bullets naming nothing specific, and bullets long enough to wreck a one-page
layout.

The specificity check reads **your own vocabulary** — the skills, project
technologies and coursework you have entered — rather than a fixed list of
frameworks, so it recognises the tools you actually use and gets sharper as you
fill the profile in. Behind that sit structural patterns (acronyms, internal
capitals, `C++`) and a common-technology fallback, with a stoplist so that a
capitalised month or a word like "Team" does not pass as meaningful.

---

## The resume itself

Four templates, all reading the same profile: **Classic** (centred header,
ruled headings), **Modern** (accent panel, side column), **Minimalist** (dates
in a left gutter) and **Compact** (for fitting a lot on one page). Each states
honestly whether its reading *order* is safe for an applicant tracking system
-- Modern's side column is the one that is not.

Presentation lives in `render/design.py`, never in `schema.py`: six accent
colours, four type pairings, two paper sizes, three margin widths, three line
spacings, a type scale, and per-resume section order and visibility. Curated on
purpose -- there is no colour picker, because the difference between a good
resume and a bad one was never the particular blue.

**The preview is the print.** Both come from one HTML document rendered by the
same engine; preview mode adds a grey desk, a white sheet at exact paper size,
and dashed lines where Chromium will cut. Measured, the two layouts agree to
within 0.1 pixels, so the page-break lines are where the breaks will be.

Printing happens in a subprocess, because Playwright's synchronous API refuses
to start inside a thread that already has an event loop -- which is exactly
what an async web server hands it. The PDF is then read *back* with pypdf: page
count, word count, and a check that the name, email and phone are really in the
text layer. A resume that looks perfect and parses as an empty document is the
failure nobody notices until the application has already been rejected.

---

## Roadmap

| Phase | | |
| --- | --- | --- |
| 1 | Master profile: schema, storage, editor, import | **done** |
| 2 | PDF generation: Jinja2 template → Playwright → PDF | **done** |
| 3 | AI tailoring against a job description | next |
| 4 | ATS keyword check | |
| 5 | Saved versions per application | |
