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
  api/       FastAPI over core. What the React frontend will talk to.
  ui/        Streamlit. Being replaced — see "Where this is going".
scripts/     self-checks, runnable with nothing but the app's deps.
tests/       the same checks, one pytest case each.
```

### The dependency rule

`core`, `ingest`, `ai` and `render` **must not import Streamlit, FastAPI, or
any UI library.** They are the product; the UI is one
way to drive it. This rule is what makes the frontend replaceable, and it is
already honoured — do not break it for convenience.

---

## Where this is going

The Streamlit UI is being replaced by **FastAPI + React (Vite) + Tailwind**.
Decided 2026-09-03 after an audit: Streamlit reruns the whole script on every
keystroke, which makes "no jank" unreachable, and `ui/theme.py` had grown to
1,700 lines of CSS targeting Streamlit's private DOM. The Python that matters
is already UI-agnostic, so the migration replaces the shell, not the product.

Phases: **0** repo foundations · **1** `core/` + FastAPI, Streamlit still
running · **2** React UI to parity · **3** delete Streamlit · **4** AI
tailoring · **5** variants, history, cover letters.

Each phase ends with a working app, on its own branch, committed.

---

## Invariants worth defending

**The schema holds facts, the design holds presentation.** No colours, fonts,
or section ordering in `schema.py`; no resume content in `design.py`. When a
template needs a field that does not exist, add it to the schema and write a
migration — do not special-case it in the template.

**Schema changes ship with a migration.** `storage.MIGRATIONS` upgrades a raw
dict one version at a time before validation. A field with a default would
load without one; write it anyway, or the version number stops meaning
anything. See `_v1_to_v2`.

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
streamlit run app.py

pip install -r requirements-dev.txt
pytest                                     # 59 checks, ~16s (4 real PDF renders)
python scripts/check_phase2.py             # the same checks, no pytest needed
```

Environment: `GEMINI_API_KEY`, optional `GEMINI_MODEL`, optional
`DOSSIER_DATA_DIR`. Nothing else. No secrets in the repo.

---

## Streamlit traps (while the Streamlit UI still exists)

Recorded because each one cost a debugging round, and the UI will not be gone
for a few phases yet.

- The theme is frozen at startup from `.streamlit/config.toml`. Runtime
  theming is CSS custom properties only. A slider's filled track is baked at
  startup and **cannot** be re-themed; toggles and checkboxes can.
- `st.pills` and `st.segmented_control` share the `stButtonGroup` testid.
  Scope by a keyed container or rules will silently style the wrong widget.
- The script runs top to bottom, so anything rendered *above* the editors
  reports the state before the current edit. Reserve a container early and
  fill it at the end of the run.
- A keyed widget's value lives in the browser and is re-sent on every rerun,
  so it beats a model that was just replaced. Undo needs the widget *keys* to
  change (a revision stamp), not the session-state entries deleted.
- Assigning to a widget's key from a button in the page body raises — the
  widget already exists this run. Park the request and apply it at the top of
  the next run.
- A subprocess must be given `stdin=subprocess.DEVNULL` on Windows; the
  inherited handle is invalid under pytest capture and under the window-less
  launcher, and `Popen` fails before the browser starts.
