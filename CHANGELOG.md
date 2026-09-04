# Changelog

Dates are when the work landed, not when a tag was cut. Every entry says what
changed and why it mattered; where a release fixed something that had been
wrong for a while, it says that too.

---

## 1.1.0 — 2026-09-04

The improved version. 1.0.0 made everything in the app work; this one adds the
three things that were missing from a job search rather than from a resume
builder, and fixes an accessibility failure that had been there all along.

### Added

- **Cover letters.** One per application, drafted from the requirements your
  profile can actually evidence and told not to claim the ones it cannot. Set
  in the resume's own typeface, on the same paper — a letter in a different
  face from the CV attached to it looks like two people applied. The greeting,
  the sign-off and the date are computed rather than asked of a model: a named
  reader gets "Yours sincerely", an unnamed one "Yours faithfully". Writing one
  by hand and printing it needs no API key.
- **Role focus tags.** Tag a bullet or a skill group `#backend`, `#frontend`,
  then set a focus on the resume. Tagged lines print only under their own
  focus; untagged lines always print. One master profile serving several job
  families without a second profile to keep in step. Schema 3 → 4.
- **Interview brief.** On any application at interview stage: what you can
  evidence and where, what you cannot and what to say about it, the questions
  each invites, and a scratchpad that saves itself. Rules only — no model, no
  network — so it reads the same every time and works on a train with no
  signal. It prints.
- **A first run with something to look at.** An empty profile offers three
  ways out: import one, load a worked sample, or start clean. The sample is
  written to the standard the app teaches and scores 85% on the Health screen,
  with two deliberately weak bullets so the check catches something real.
- **A collapsible design panel.** On a 1366px laptop the preview goes from
  720px to 1084px. The column width is stepped and never transitioned; the
  visible motion is a compositor transform. The hidden panel is `inert`, and
  the choice is remembered.
- **Section headings are two points larger**, on every template. Each
  template sizes its headings as a multiple of the body size — .76 in
  minimal's gutter, 1.05 in executive — and those proportions are the
  template's character, so the two points are added rather than substituted:
  every heading keeps its own weight in the page and every one gains the same
  amount. The one exception is the gutter body layout, where .78 was not a
  taste but a measurement — the largest size at which CERTIFICATIONS fits a
  26mm column, with two pixels to spare. All 32 template-and-layout pairings
  were rendered and measured for collisions before and after.
- **Sections can be dragged into order**, not only nudged with the arrows.
  Same pointer-event handling as entries and bullets, so it works on a
  touchscreen, and both paths make the same edit — one entry in the undo
  stack either way.
- **An exact page margin.** A slider from 2mm to 20mm, between line spacing
  and type size, replacing a three-option dropdown — the difference between
  spilling onto a second sheet and not is often two millimetres, and the
  dropdown's steps were four and five. The named presets stay: they are what
  the curated looks set, and applying a look clears the exact value so the
  look's own choice shows. The sheet reflows under the finger — the margin is
  pushed into the frame and re-paginated there, the way zoom already was —
  rather than waiting on a round trip per step of the handle.
- **The sidebar highlight travels.** One highlight for seven links instead
  of one each, so the green pill and its accent bar slide between rows rather
  than switching off here and on there. The label's colour takes the same
  260ms on the same curve — at 150ms it went green while the highlight was
  still two rows away, which reads as two things happening rather than one.
- **Structured wireframe skeletons.** Each template card draws its own
  silhouette while Chromium renders the real thing, so the grid stops being
  eight identical grey boxes and answers the question the reader actually has.

### Fixed

- **"Number the pages" changed the PDF and nothing on screen.** The flag
  reached `render_pdf` and stopped there, so the switch looked dead: the
  export was numbered, the preview never was. The preview now draws the
  number Chromium will print, in the same corner, size and grey.
- **The zoom slider ignored Fit.** Only the document knows what the
  automatic fit came out as — it computes the scale inside the frame from the
  pane's width against the sheet's — so the handle sat wherever it was last
  dragged, reporting a number that was not the scale on screen. The frame
  posts its scale out and the handle follows it.

- **"Page 2 holds about 1 line" is gone.** It was a real measurement rather
  than debug output, fired when a document ran just past a page boundary, but
  it read as an error on a document that was not wrong. The page count beside
  it already says the document is two pages.

- **The switches did not look like switches.** The knob was the full height
  of a 32px track, so it travelled 10px and covered two-thirds of the ground:
  what the eye saw was a circle with a coloured crescent behind it, and
  because the crescent is only conspicuous in the "on" state, the two ends did
  not even look symmetrical. It read as stuck halfway when on and properly
  parked when off. The knob is now a little under half the track and travels
  most of its length — 18px rather than 10 in the design panel. One component
  in two sizes now, rather than two implementations with different geometry.
- **The type sizes printed outside their own bar.** Five slots sharing half a
  340px panel came to 28.6px each against labels needing 29, so "92" and "108"
  sat a hair over the ends. The stepper has the full width of the panel now,
  and the segmented control measures its slots rather than assuming they are
  equal.
- Side panels slid too fast to follow: 200ms, and in the design panel's case
  over 24px, which is a blink rather than a movement. Both now take 340ms on a
  decelerating curve, and the design panel travels its own full width.

- **`--c-faint` failed WCAG AA, and always had.** Measured 3.54:1 on the
  surface and 3.13:1 on the sunken against a 4.5 requirement — on the token
  that colours almost nothing but small text. Now 5.31 and 4.70, with dark
  mode taken from 4.79 to 5.97 so both themes sit at the same distance.
- **Cover letter PDFs are read back with pypdf**, the same guarantee the
  resume has had since 2.0. A document that looks perfect and parses as empty
  fails silently.
- Status badge borders went from 40% of their colour to 70%; at 40% the ring
  distinguishing ATS-safe from two-column was gone on a dim screen.
- The role pulled from a saved application carried the company and the city,
  so a letter's addressee block named the employer twice.

### Changed

- The sliding highlight built for the type-size stepper is now a component,
  and the template filter and the health-check severity filter use it. The
  highlight is measured from the active button rather than computed from its
  index, which is what lets it work on choices of unequal width.

- Drafting a letter names the application rather than sending the posting up
  the wire; the advert is already in the database.

---

## 1.0.0 — 2026-09-04

An audit of everything built, then every defect it found. The goal was not
feature count: it was that each thing in the app is completely wired, and that
the repository does not claim anything untrue.

### Fixed

- **The README described an app two phases out of date** — "AI tailoring —
  next" for a feature that had shipped, 85 checks against 153, four templates
  against eight. Rewritten from the code, with every count read out of
  `design.py`, and given an honest known-limitations section.
- **Undo did not cover the design**, pushed a snapshot per keystroke, and had
  no redo. It now holds both documents in one history, a run of typing is one
  step, and there is a history panel you can seek in. Two bugs found by the
  tests written for it: the redo stack came back reversed after a seek, and
  snapshots were taken from the immer draft, so every one equalled the state
  it was meant to undo.
- **A `<select>` counted as "typing"**, so the guard protecting a text field's
  own undo swallowed Ctrl+Z. Changing the paper size and pressing Ctrl+Z did
  nothing.
- **Bullets could not be reordered** — entries and sections had drag and arrow
  keys; bullets had neither.
- **Two raw NUL bytes in `Profile.tsx`** made `grep` classify the largest file
  in the interface as binary.
- The Health screen swallowed every error, so a failed fetch showed a stale
  score with no explanation.
- Switch knobs finished flush with their track, and the tracks were shortened
  so the colour behind the knob no longer reads as slack.

### Removed

- `core/settings.py`, which had zero importers since the Streamlit build went.

### Added

- The first frontend tests (vitest, over the undo stack's arithmetic) and
  `REGRESSION.md`, the manual walk-through run before any phase is called done.

---

## Before 1.0.0

Phases 0–5, in order: the profile schema and storage; the PDF pipeline
(Jinja2 → Chromium → pypdf); the React interface; deleting Streamlit; AI
tailoring with a fabrication audit; and the applications database with saved
versions of what was actually sent. `CLAUDE_GUIDE.md` carries the reasoning
behind the architecture those phases produced.
