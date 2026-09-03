# Dossierbuild — architecture and conventions

An AI-assisted resume builder. One master profile of everything you have done;
each application gets a version tailored to that job, printed to a real PDF.

This file is the standing brief for anyone — human or model — working in this
repo. Update it when a decision is made, not afterwards.

---

## The shape of the thing

```
dossier/
  core/      the product, with no interface attached
    schema.py      the master profile contract (Pydantic v2). Facts only.
    storage.py     load / validate / atomic save / migrate. DATA_DIR is env-configurable.
    settings.py    small UI preferences, low stakes, never validated hard.
    quality.py     the bullet-writing standard, as code.
    db.py          SQLite: connection, pragmas, its own migration chain.
    applications.py  saved applications, and the queries across all of them.
    jobspec.py     a job posting, read by rules. Weighted terms, coverage, evidence. No AI.
    ids.py         stable short ids.
  ingest/    PDF·DOCX·LinkedIn -> profile, plus the merge review. No AI.
  ai/        every call that leaves this machine for a model.
    client.py      the key, the model fallback ladder, the retry budget. Shared.
    parse.py       resume text -> profile. Transcribes, never composes.
    tailor.py      profile + posting -> rewrites keyed by block id, each audited.
    suggest.py     one drafted bullet or summary, from facts the user supplies.
  render/    profile + design -> HTML -> PDF.
    design.py      every presentation choice, validated. Curated, not open-ended.
    context.py     the profile flattened into exactly what a template needs.
    html.py        Jinja2. One self-contained document, preview or print.
    pdf.py         Chromium in a subprocess; pypdf reads the result back.
    photo.py       the portrait: normalised on upload, embedded as a data URI.
    templates/     _base + _macros + eight layouts.
    text.py        the profile as plain text, for forms that take no file.
  api/       FastAPI over core, and the server that hosts the frontend.
    static.py      serves web/dist, so shipping is one process on one port.
web/         React + Vite + TypeScript + Tailwind. The interface.
  src/styles/tokens.css   the design system: every colour, in both themes.
scripts/     self-checks, runnable with nothing but the app's deps.
             launch.cmd / launch.vbs / stop.cmd back the desktop shortcut.
tests/       the same checks, one pytest case each.
```

### The dependency rule

`core`, `ingest`, `ai` and `render` **must not import FastAPI, or any other
web or UI library.** They are the product; the interface is one way to drive
it. This rule is what made replacing the entire frontend a matter of deleting
one directory — it earned its keep once, and it will again.

---

## Where this is going

Streamlit was replaced by **FastAPI + React (Vite) + Tailwind**, decided
2026-09-03 after an audit: Streamlit reruns the whole script on every
keystroke, which makes "no jank" unreachable, and `ui/theme.py` had grown to
1,738 lines of CSS targeting Streamlit's private DOM. The Python that mattered
was already UI-agnostic, so the migration replaced the shell, not the product.

Phases: **0** repo foundations ✓ · **1** `core/` + FastAPI ✓ · **2** React UI
to parity ✓ · **3** delete Streamlit ✓ · **4** AI tailoring ✓ · **5** variants,
history, cover letters.

Each phase ends with a working app, on its own branch, committed.

Phase 3 removed `app.py`, `dossier/ui/` and `.streamlit/`. If you need to see
what the old interface did, it is in git, not gone: `git show
phase-2-react:dossier/ui/insights.py` and so on.

---

## Invariants worth defending

**The schema holds facts, the design holds presentation.** No colours, fonts,
or section ordering in `schema.py`; no resume content in `design.py`. When a
template needs a field that does not exist, add it to the schema and write a
migration — do not special-case it in the template.

**Schema changes ship with a migration.** `storage.MIGRATIONS` upgrades a raw
dict one version at a time before validation. A field with a default would
load without one; write it anyway, or the version number stops meaning
anything. See `_v1_to_v2` and `_v2_to_v3`, and `tests/test_migrations.py`,
which walks a version-1 dict all the way forward and fails if any step is
missing.

**A heading is not a schema change.** "Awards" became "Honors" by editing two
label tuples; the stored key is still `awards`. Renaming a field to change a
word on screen is a migration that buys nothing and costs everyone's saved
files. Labels live in `schema.SECTION_ORDER` and `design.RESUME_SECTIONS`.

**The preview is the print.** Both come from one HTML document rendered by the
same engine. They are measured equal to 0.1px (`scripts/measure` in the
scratchpad, and by eye in `check_phase2`). Anything that could make them
disagree — a shrinkable sheet, a font that only loads in one of them — is a
bug, not a detail.

**A PDF is not done until its text layer is checked.** `pdf_report` reads the
generated PDF back with pypdf and confirms the name, email and phone are
really in it. A resume that looks perfect and parses as an empty document is
the failure nobody notices until the application is rejected.

**Tailoring re-angles facts; it never adds them.** A bullet that gained a
number the model invented is not an improved bullet, it is a claim the user
will be asked to defend in an interview and cannot. `ai/tailor.audit` diffs
every rewrite against its source and reports numbers and names that appear in
neither the original nor anywhere else in the profile; the UI starts those
unticked. The prompt asks for the same thing, but the prompt is not the
guarantee — the diff is. `scripts/check_tailor.py` pins both the catches and
the non-catches, because a warning that cries wolf is a warning people learn
to click past.

**The model is never asked what a job requires.** `core/jobspec.py` reads the
posting by rules and hands the model its conclusions. A hallucinated
requirement would silently re-angle an entire resume at something the employer
never asked for — and keeping the analysis deterministic is also why the gap
report works with no API key, with Gemini down, and inside a test.

**Two stores, and the split is deliberate.** `profile.json` holds the one
hand-typed document — read whole, written whole, atomic, backed up.
`data/dossier.db` holds what is actually relational: many applications, the
terms each posting asked for, the tailoring runs and their rewrites. The test
of which is which is whether you would ever ask a question *across* the rows.
`recurring_gaps` is that question, and it is why the terms are rows rather
than a JSON blob. SQLite is stdlib, so this added no dependency, and there is
no ORM because the queries are the point.

**`PRAGMA foreign_keys` is off by default in SQLite.** Every `ON DELETE
CASCADE` in the schema is decorative without it, so `db.connect` sets it and
`check_db` proves it by deleting an application and asserting its rows go and
its siblings stay.

**Never lose the profile.** Atomic writes, a timestamped backup on every save,
and `data/` deny-listed in `.gitignore` by default.

---

## Writing standard

This applies to resume content the app produces *and* to the app's own copy.

Banned: "Responsible for", "Worked on", "Assisted with", "spearheaded",
"leveraged", "seamlessly", "robust", "cutting-edge", "passionate about", and
anything else that could appear on any resume in the world. Every bullet names
real technologies, real numbers, real outcomes — something only this person
could have written. `quality.py` enforces it; keep the linter aligned rather
than working around it.

UI copy follows the same rule: say the specific thing. "Page 2 holds about 4
lines" beats "Content overflows".

---

## Comments

Explain *why*, never *what*. A comment earns its place when it records a
decision, a trap, or a measurement — "``flex: none`` is the difference between
a preview and a lie" — and does not when it narrates the line below it. No
comment noise on obvious lines.

---

## Running it

```bash
pip install -r requirements.txt
python -m playwright install chromium      # the PDF pipeline needs a browser
cd web && npm install && npm run build     # the interface, built to web/dist
python -m uvicorn dossier.api:app --port 8000        # then localhost:8000

pip install -r requirements-dev.txt
pytest                                     # 140 checks, ~26s (real PDF renders)
python scripts/check_phase2.py             # the render checks, no pytest needed
python scripts/check_tailor.py             # the posting reader and the audit
python scripts/check_db.py                 # the schema, its constraints, its queries
```

One process serves both the API and the interface: `api/static.py` mounts
`web/dist` at the root, so a machine running Dossier needs Python and Chromium
but no Node. The desktop shortcut runs exactly this, window-less, via
`scripts/launch.vbs`.

While working on the frontend, run Vite instead — `cd web && npm run dev` on
5173, proxying `/api` to 8000 — for hot reload. The static mount stays out of
the way when `web/dist` does not exist.

Environment: `GEMINI_API_KEY`, optional `GEMINI_MODEL`, optional
`DOSSIER_DATA_DIR`. Nothing else. No secrets in the repo.

---

## Traps worth remembering

Each of these cost a debugging round.

- **A subprocess must be given `stdin=subprocess.DEVNULL` on Windows.** The
  inherited handle is invalid under pytest capture and under the window-less
  launcher, and `Popen` fails before Chromium starts.
- **Font stacks must be `| safe` inside `<style>`.** Jinja's autoescape turns
  the quotes in `"Source Serif 4", Georgia, serif` into entities, every
  template silently falls back to Times, and nothing errors.
- **`flex: none` on the preview sheet.** As a flex item it shrinks below A4,
  and the preview stops being the print. This is the difference between a
  preview and a lie.
- **No hand-measured sticky offsets.** The section tabs stuck at `top-[57px]`,
  a measurement of the header above them; adding one control to that header
  made it taller and the tabs slid underneath. Nest the thing instead — see
  `TopBar`'s `below` slot.
- **HTML5 drag-and-drop is the wrong API here.** It does not fire for touch at
  all, so a drag handle stays decoration on a phone, and synthetic events
  cannot drive it, so the behaviour cannot be tested. `EntryList` reorders with
  pointer events, which cover mouse, touch and pen in one path — and the ↑/↓
  buttons stay, because no drag is reachable from a keyboard.
- **A control that only works with a keyboard is width taken from one that
  works without.** The ⌘K chip sat beside the title on every screen; on a
  phone it helped nobody and pushed the page title and the primary action off
  the right edge. It is `hidden md:inline-flex`.
- **Merge candidate keys must not embed entry ids.** Ids are minted at
  validation, so a key built from one is different in the response than it was
  in the request, and `/plan` never matches `/apply`.
- **zustand v5 selectors returning object literals need `useShallow`.** A new
  object every render is a new value every render, which is an infinite loop.
- **Tailwind cannot see `text-${tone}`.** Class names are extracted from the
  source as literal strings; interpolated ones compile to nothing. Use a map
  of literal classes.
- **A field that writes every keystroke into the model will save a
  half-typed value.** `2025-06` passes through `2025-`, which the schema
  rejects, and autosave posted it. Inputs with a format hold their own draft
  and commit only what parses — see `MonthInput`.
- **A Jinja comment cannot sit inside an expression.** `{# #}` between the
  entries of a `{% set x = {...} %}` dict is `unexpected char '#'`, not a
  comment. Put it above the tag.
- **A word-boundary match is not a substring match.** "Go" as a required
  skill matched inside "algorithms", and every profile mentioning an algorithm
  scored a language nobody had written. Term matching uses
  `(?<![A-Za-z0-9])term(?![A-Za-z0-9])` throughout `jobspec` and `tailor`.
- **A posting names one requirement several ways.** "REST APIs and CI/CD"
  yields `rest`, `api`, `rest api`, `ci`, `cd` and `ci/cd` — six terms for two
  requirements, enough to outweigh a real third. A phrase absorbs its own
  parts (`_absorb_into_phrases`), and a benefits section is skipped outright
  rather than demoted, after a MacBook was read as a required skill.
- **The fabrication guard cannot rely on capitalisation alone.** Acronyms and
  internal capitals catch `PyTorch` and `ETL`, but `Kubernetes`, `Docker` and
  `React` are ordinary capitalised words — exactly the fabrications a posting
  invites. They are caught by name against the technology lexicon instead.
  Going the other way and flagging every capitalised word makes "Built" an
  invented entity and the warning worthless.
- **A short Title Case line is not a heading.** Postings list single-word
  requirements constantly — "- Docker", "- SQL" — and each is short and either
  Title Case or all-caps, which was exactly the heading test. Four
  requirements were silently dropped across three test postings. Headings are
  matched against the vocabulary that already exists (`KNOWN_HEADINGS`), and a
  line opening with a bullet marker is never one. Casing was always a bad
  proxy: "Nice to have" is not Title Case, and "Docker" is.
- **`executescript` commits before it runs**, which ends the migration's own
  transaction and makes the following COMMIT fail. Splitting a script on ";"
  instead is worse — a semicolon inside a SQL comment cut a statement in half
  and produced a syntax error pointing at an English word. Migrations are
  tuples of whole statements.
- **A `transform` does not affect layout.** The preview desk stayed pane-width
  while the scaled sheet overflowed it, so zooming past fit clipped the page
  and offered no scrollbar — which read as "150% does nothing". The desk needs
  an explicit width for the scaled sheet to be reachable.
- **FastAPI derives a response model from the return annotation.** A route
  returning `FileResponse | JSONResponse` fails at import until it is given
  `response_model=None`.
