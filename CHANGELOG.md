# Changelog

Dates are when the work landed, not when a tag was cut. Every entry says what
changed and why it mattered; where a release fixed something that had been
wrong for a while, it says that too.

---

## Unreleased

### Added

- **Sections the app has no name for.** A heading matching none of the eight
  built-in sections used to be read by the importer and then dropped --
  silently, so the writer got a shorter resume and no reason for it.
  ``Profile.sections`` holds them now (schema v5), heading and words as
  written. They order, hide and rename beside the built-in eight and print in
  all thirty-two template-and-layout combinations. A real import of a senior
  CV placed "Executive Qualifications", "Governance, Security and Risk
  Leadership" and "Selected Speaking Engagements" correctly, each with the
  right shape.
- **Bold, italic and underline**, on every field that becomes words on the
  page. A stored line is still plain text: only ``<b>``, ``<i>``, ``<u>`` and
  their closers mean anything, which is what lets every profile written before
  this keep meaning exactly what it meant. Email, phone and links are left
  plain because an ``href`` built out of marked-up text is a link that goes
  nowhere; dates and the employment dropdown are structured values rather than
  writing. Everything that reads a line as *language* -- the writing standard,
  the posting matcher, the duplicate check, the plain-text export, every
  prompt, the CV's name in the sidebar, the download filename -- reads it
  stripped.
- **Editing on the page itself.** Type straight onto the resume, and move,
  remove or add a line from a rail in the margin. The printed document is
  unaffected by design: everything the feature adds lives behind
  ``{% if preview %}``, the outline is a ``box-shadow`` and the rail is
  ``position: fixed``, so neither takes space and the page breaks stay where
  the printer puts them. Proved across all thirty-two designs: three blank
  lines inserted into a profile change no printed document at all. An edit
  made here goes through the same ``store.edit`` the Profile screen uses, so
  it lands in the undo stack, in autosave and in the writing standard exactly
  like a typed one.
- **Times New Roman**, with Tinos behind it -- metrically identical, so a PDF
  built in CI breaks its lines in the same places as one built on a laptop.
- **Health check is now Review, and it reads the document.** Every finding it
  had was a general rule about writing -- lead with a verb, carry a number,
  do not say "responsible for" -- so it gave everybody the same advice and
  could not see that a resume had no email address on it. It checks the
  document too: no way to reply, no summary, a job that ends before it starts,
  the same bullet pasted twice, an entry with no dates, a heading with nothing
  under it, an entry so long the last bullets are read by nobody. Each names
  its place, and every one of them is silent on a resume that does not have
  the problem.
- **Every filler phrase got the same sentence, at the top severity.** Two
  different lines, two red "Problem" marks, and under each of them the same
  words with the phrase swapped in: ``"contributed to" is filler``,
  ``"successfully" is filler``. It was one fault when it is five, and it never
  looked at the sentence it was talking about. Filler is now typed -- a
  **hedge** is the wrong verb, an **adverb** is one word too many, a **vague**
  quantity is a missing number, a **cliche** is a claim with no opposite, an
  **inflated** word is a plain word in a costume -- and each is told its own
  repair, quoting the line: *"contributed to" is the verb of this line, so
  what it claims is that you were near "HPE's global strategy for cloud,
  telecommunications..." -- not what you did to it.* Severity is read off the
  rest of the sentence rather than fixed: a hedge that is the main verb, or
  anything at all on a line that counts nothing and names nothing, is a
  warning; one deletable word on a line already carrying a number is a note.
- **"Problem" now means the document is broken.** It used to hold a missing
  email address, a job ending before it starts, and the word "successfully" on
  an otherwise good line -- a tier holding all three means nothing. Nothing in
  the writing pass is a Problem any more. A word a PDF import split in half
  became one, because that is not an opinion: those two halves print exactly
  as they are stored.
- **A habit is now said once instead of five times.** "Supported" opened five
  bullets of one real CV and "managed" four, each collecting its own identical
  warning down the page -- which is the complaint itself. Counted across the
  document, it becomes a fact no single line could report: *5 bullets open
  with "supported" -- repeated, they make several jobs read as one.* The same
  for a filler phrase in three or more lines, and for a good verb opening four
  or more, because monotony costs a page whether or not the verb is strong.
  Weak verbs are reported before frequent ones: on that CV "Led" opened ten
  bullets, and ranking by count alone spent the card on the good verb.
- **The Review icon was a stethoscope**, which is a doctor listening to a
  body. It is a document being read closely, and now looks like one.
- **A summary was being judged as a bullet.** At 1,017 characters it was told
  that "over about 200 this will wrap badly and push the resume past one
  page" -- a bullet's rule read out over a paragraph, and wrong in both
  directions. And the note "trailing full stop; bullets read cleaner without"
  fired on that same summary, announcing its own mistake. Bullets, summaries
  and section prose now have their own lengths, and the rules that are about
  the bullet form -- the opening verb, the closing full stop, the missing
  number -- apply to bullets only.
- **Section headings were smaller than the text under them.** On Minimalist
  they measured 9.98pt against a 10.5pt body -- a heading that reads as a
  caption. The shared bump every template applies went from 2pt to 3pt, and
  Minimalist's own multiplier from .76 to the .102 the rest use: 13.3px to
  18.3px against a 14px body. Measured across all thirty-two designs
  afterwards, and none of them wraps a heading onto a second line.
- **The editing rail covered the text it was next to.** It preferred the left
  margin and, when there was not room, fell back to just inside the block --
  which is on top of the first thing you were trying to read. Three positions
  now, tried in order, none of them over the words: the left margin, the right
  margin, then above the block against its right edge. The width is measured
  rather than assumed, because the page is scaled by a transform and a
  hard-coded number is only right at one zoom.
- **The design belongs to the CV.** Typeface, template, layout, paper,
  margins, section order -- all of it was one file shared by every CV, on the
  reasoning that the look is a habit of the person rather than a fact about
  the document. That holds until somebody keeps two CVs for two different
  people, at which point setting Times New Roman on one silently reset the
  other. Section order was the sharper version: it can name a custom section,
  and a custom section belongs to exactly one profile, so a shared order
  carried ids the CV in front of you had never heard of and printed them as
  "Untitled section". One design file per CV now, and a CV that has never been
  styled reads the old shared one -- so nobody's look changes on the day this
  landed, and the two stop moving together the moment either is touched.
- **Removing a section from the CV.** A bin on every row of the section list,
  built-in or one you added, and it takes that section off this document and
  nothing else: remove Experience and every job is still in the Profile
  editor, still counted by the writing standard, still there when you put the
  section back or print a second CV that wants it. The row turns into "Back",
  which is why there is no confirmation -- a confirmation is for something you
  cannot undo, and this is one press from being undone by the same button.
  Deleting a section's *contents* is a different act and stays where the
  contents are.
- **Dates may be words.** "Summer 2024", "Expected 2026", "Ongoing",
  "2019 - Present". A field that refuses those makes people misstate their own
  history to satisfy a regex. Schema v6. Anything the app can still read is
  still normalised and still follows the design's date-format switch.

### Fixed

- **"Certifications" printed twice.** A CV that says "Education and
  Certifications" writes one heading over two sections the app keeps apart.
  The first fix let the first section claim the words and the second fall back
  to its default, which put "CERTIFICATIONS ... EDUCATION AND CERTIFICATIONS"
  on one page. An empty heading is now a real setting meaning "print no
  heading", the import applies it to the covered section and moves it directly
  beneath the one that named it.
- **"large- scale" and "Conc urrently" on the printed page.** A hyphen at the
  end of a PDF line is a compound the layout wrapped; the newline after it
  reached the model as ``large-
scale`` and came back as ``large- scale``.
  Extraction rejoins it before the model sees it, keeping the hyphen -- Word
  does not hyphenate by default, so on a resume that hyphen is nearly always
  one the writer typed. Line breaks that are not inside a word are untouched:
  they are the main signal separating one bullet from the next. For text
  already stored, the writing standard now flags it.
- **A field wrapped in a ``<label>`` could not be clicked into.** Clicking a
  label runs its activation behaviour, which hands focus to its labelable
  descendant; a ``contenteditable`` is not one, so the focus the click had
  just given it was dropped again. The box looked dead unless you held the
  mouse down and dragged.
- **A new entry was saved with no id.** The editor sends ``id: ""`` for a row
  somebody has just added and reads the profile back expecting a real one --
  the store said so in a comment and nothing did it. An empty id is not a
  duplicate of anything, so the repair pass walked straight past it. Invisible
  for years and immediately fatal for a custom section, whose id is the key
  its position and heading are filed under.
- **Skills under a heading the app did not recognise went missing.** A senior
  CV rarely says "Skills"; it says "Core Expertise". The section was read and
  dropped with nothing to say so. Named in the prompt, with the nine other
  spellings it also answers to.
- **An import could not tell you what it had done to a heading.** The
  extraction reports the resume's own section names, and the design adopts
  them on accept -- so a CV that says "Executive Profile" gets that back
  rather than being told it is "Summary". A heading you have set yourself is
  never overwritten.

### Added (1.1.0 cycle)

- **More than one CV.** A switcher and a "new CV" button in the sidebar, and a
  way to delete one. Each CV is a profile file of exactly the format
  ``storage`` already reads, so every migration and the atomic write apply
  unchanged. The design, the applications, the saved versions and the letters
  stay shared: those are a record of a job search, not of a document. Starting
  one asks nothing, because the one you were on is already on disk. Deleting
  asks once and moves the file to ``data/backups`` rather than unlinking it.
- **A licence.** MIT. Without one a public repository is legally
  all-rights-reserved, which is not what a portfolio piece is for.
- **Screenshots in the README**, taken on the app's own worked sample.
- **A Settings screen.** The API key, which model to try first, what this copy
  can do, and where the files are. The key is checked with Google before being
  stored, so a typo fails in the box rather than on the screen where you next
  needed it; it never travels back to the client; and a key exported in your
  shell is reported as one this screen cannot remove, rather than being given
  a button that would not work.
- **Continuous integration.** Both suites and a real Chromium on every push,
  deliberately with no API key set -- everything but three features is meant
  to work without one, and a run with no key is the only thing that proves it.
  All 213 pass that way.

### Fixed

- **Long unbroken text no longer runs off the printed page.** ``.entry-line``
  is a flex row and its children had no ``min-width: 0``, so a flex item would
  not shrink below its content's minimum — and for an unbroken token that
  minimum is the whole token, which meant the ``overflow-wrap`` rule on
  ``body`` never got a chance. Measured before the fix: a 300-character role
  title printed with **104 characters** in the PDF's text layer and the rest
  silently gone; a long portfolio URL vanished entirely. All 300 now survive.
  Triggered in practice by a pasted link, a compound word, or an import that
  ran two fields together.
- **Errors reach the person instead of the log.** There was no catch-all
  exception handler, so anything not on the list of six typed handlers arrived
  as Starlette's plain-text ``Internal Server Error`` — which the client
  cannot parse as JSON, so it fell back to printing the status line. Every
  carefully-worded ``RuntimeError`` in ``ai/client.py``, including the one
  explaining that Gemini is congested and what to set to avoid it, was being
  thrown away. Also adds a handler for ``CVError``: a corrupt ``cvs.json``
  sits under every route that touches a profile, health included, and used to
  make the whole app answer 500 with nothing to act on.
- **A rejected API key says so.** A key that is present but invalid produced
  ``500 Internal Server Error``; it now names the problem and where to get a
  new one, and stops rather than spending the retry budget proving the same
  key wrong five more times.
- **The request timeout can now trigger the fallback ladder it was written
  for.** Retryability was decided by substring-matching ``str(exc)``, which is
  wrong in both directions: a request id containing "429" read as rate
  limiting, and an ``httpx.ReadTimeout`` — whose ``str()`` is the single
  phrase "timed out" — matched nothing. So ``REQUEST_TIMEOUT_MS``, which
  exists to turn a slow model into "try the next one", was aborting the ladder
  instead. Being offline failed the same way. Now read off the exception's
  status code, with the transport exceptions handled by type.
- **Two reachable 500s are now 422s.** "There is nothing to tailor yet" and
  "There is no text to parse." are advice, and arrived as server errors.
- **An applicant whose name is not written in the Latin alphabet can
  download their documents.** The name went into a ``Content-Disposition``
  header, Starlette encodes headers as latin-1, and nothing caught the
  ``UnicodeEncodeError`` -- so a cover letter for someone called 李明 or محمد
  returned **HTTP 500**. The resume path dodged the crash by deleting the
  characters instead, which is not better: "Ünsal Öztürk" downloaded as
  ``nsal-zt-rk-Resume-Classic.pdf`` and a name in Han characters vanished
  entirely, leaving a file named after a template.

  Fixed on both sides, because it took both. The server now sends RFC 6266's
  two forms in one header: a transliterated ``filename=`` that folds accents
  rather than deleting letters, and ``filename*=`` carrying the real
  characters as percent-encoded UTF-8. The client was the other half -- it
  fetches the file as a blob and hands it over with ``<a download>``, so the
  browser never reads the header itself, and the regex there only ever
  matched the ASCII form. It reads the encoded one first now.

  Verified in a browser: 李明-Resume-Classic.pdf, محمد-الأحمد-Resume-Classic.pdf,
  Ünsal-Öztürk-Resume-Classic.pdf. Twenty-six tests, and the first non-ASCII
  fixtures in the suite -- which is why this survived to 1.1: every profile in
  every test was called "A. Student".
- **`chromium_ready()` no longer spawns a Playwright driver on every call.**
  It is called by `/api/health`, which the open page heartbeats against, so
  the cost was being paid continuously. 0.50s to 0.00s. Only a success is
  cached; a failure can change while the app runs, because the fix for it is
  to install the browser.
- **`ENV_PATH` was fixed at the project's own `.env`**, so a second copy of
  the app -- or the test suite -- would write over the key belonging to the
  real one. Overridable by `DOSSIER_ENV_FILE`, which `conftest` now sets.
- **A rejected key is one sentence, not a wall of JSON.** The SDK's `str()` is
  the entire error body; `.message` is what Google wrote for a person.
- **An unknown template key no longer 500s.** ``/api/render/thumbnail`` took
  the template as a bare string and reached the template map through
  ``model_copy``, which does not re-validate.

### Documentation

- The README listed "one profile, not many" under **Known limitations** three
  days after multi-CV shipped, advertised a ``scripts/stop.cmd`` that was
  deliberately deleted, claimed 171 tests against 178, said "seven screens"
  above an eight-row table, and carried a roadmap "towards v1.0" under a v1.1
  heading. All corrected, and the roadmap is now the honest "what I would
  build next" it always said it would become.
- ``render/design.py``'s module docstring stated as a design principle that
  there is "no margin slider". The margin slider shipped in 1.1.

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
- **Arriving at the Resume screen no longer stutters.** Nine documents mount
  there at once, and each ran a full A4 pagination — a forced layout to read
  `scrollHeight` — on the arrival frame. Eight of them are 168px thumbnails
  with no fit bar, no break markers and nothing to paginate for, so they now
  take the scale and skip the rest. The preview mounts a slide later, behind
  the placeholder that was already there. Measured: the 260ms the sidebar
  highlight is sliding for is now clean, against gaps of 83ms and 217ms.
- **More than one CV.** A switcher in the sidebar and a button to start a
  fresh one. Each CV is a profile file of exactly the format storage already
  reads, so every migration and the atomic write apply unchanged; the only new
  thing is which file `load_profile()` reaches for. The design, the
  applications, the saved versions and the letters stay shared — a house style
  and a record of a job search belong to the person, not to a document.
  Starting a new one asks nothing, because the one being left is a file
  autosave has already written and switching does not touch it. An existing
  profile is adopted as CV one on first run, copied rather than moved.
- **The profile's section tabs slide too**, sharing the sidebar's handling
  rather than a second copy of it.
- **Structured wireframe skeletons.** Each template card draws its own
  silhouette while Chromium renders the real thing, so the grid stops being
  eight identical grey boxes and answers the question the reader actually has.

### Fixed

- **A link in the preview blanked the preview.** The frame is sandboxed into
  an opaque origin, so clicking the GitHub link in a header took the frame
  itself to github.com — a navigation the sandbox then refused, leaving an
  empty pane with the document gone. Links open in a tab now. The printed
  document is untouched: it carries no script at all.
- **`normalise_url` passed any scheme through to an `href`**, `javascript:`
  included. Only http, https, mailto and tel reach the page; a label with an
  address nobody can follow still prints, it simply is not a link.
- **AI suggestions were slower than they had to be.** The Gemini client was
  rebuilt per request, so every suggestion paid a fresh TLS handshake; it is
  kept now, and two consecutive drafts measured 4.2s then 1.35s. The fallback
  ladder was walked from scratch every time, which measured at 61 seconds
  against 14 for the same work — the model that last answered is tried first.
  A single attempt could hold the whole request for 45 seconds before the
  ladder moved on; capped at 25, which clears every healthy call measured. The
  import is warmed at startup rather than paid by the first person to ask. And
  the panel counts the seconds, because the spread is 3s to 25s and a bare
  spinner over that range is indistinguishable from a hang.
- A portrait deleted from the profile came back on reload: the save was
  guarded on the old single-profile path, which is not where a profile lives
  any more.
- `test_lifetime` compared a fabricated timestamp against `time.monotonic()`,
  so whether it passed depended on how long the machine had been switched on
  — it failed on one booted twelve minutes earlier. The heartbeat now takes a
  clock the way `should_stop` already did.
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
