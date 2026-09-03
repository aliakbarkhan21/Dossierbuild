# Dossier — architecture and conventions

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
    ids.py         stable short ids.
  ingest/    PDF·DOCX·LinkedIn -> profile, plus the merge review. No AI.
  ai/        every call that leaves this machine for a model. Currently: resume parsing.
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
to parity ✓ · **3** delete Streamlit ✓ · **4** AI tailoring · **5** variants,
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
pytest                                     # 78 checks, ~24s (real PDF renders)
python scripts/check_phase2.py             # the render checks, no pytest needed
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
- **FastAPI derives a response model from the return annotation.** A route
  returning `FileResponse | JSONResponse` fails at import until it is given
  `response_model=None`.
