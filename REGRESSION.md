# Regression checklist

Run this before calling any phase done. The automated suites cover the parts
that can be asserted; this covers the parts that can only be seen, and the
paths that cross three subsystems at once.

Every step assumes a **scratch data directory**, never your real one:

```bash
DOSSIER_DATA_DIR=/tmp/dossier-check python -m uvicorn dossier.api:app --port 8000
```

Autosave writes to disk within seconds of any edit. Running this against
`data/` will overwrite the profile you care about.

---

## 1. The suites

```bash
pytest                                   # 171
cd web && npm test && npm run typecheck  # 18, then strict TypeScript
python scripts/check_phase1.py           # 20
python scripts/check_import.py           # 21
python scripts/check_phase2.py           # 20
python scripts/check_db.py               # 19
python scripts/check_tailor.py           # 29
```

All green, no skips you did not expect. `check_phase2` and `pytest` print real
PDFs; a skip there means Chromium is missing, not that the checks passed.

## 2. The primary flow, end to end

Start from an empty scratch directory so the first-run state is exercised.

- [ ] **Empty profile.** Every screen renders. Nothing says "undefined", no
      blank card with no explanation, and each screen says what to do first.
- [ ] **Create.** Add a role, two bullets, a project, a skill group. Reload the
      page: everything is still there.
- [ ] **Import.** Bring in a resume (PDF or pasted text). The review screen
      lists what is new and what looks like a duplicate. Press Add; the
      entries appear. Ctrl+Z reverses the whole import in one step.
- [ ] **Tailor.** Paste a real posting. Requirements are read out with tiers.
      Coverage is a number you believe. Save the application.
- [ ] **Rewrite** (needs a key). Suggestions come back; any that invented a
      number are flagged and start unticked. Apply; the bullets change.
- [ ] **Switch templates.** All eight render your content without overflowing
      or losing the name. Try each of the four body layouts over at least two
      templates.
- [ ] **Export PDF.** It downloads, **open it**, and check: the right number
      of pages, no clipped text, the portrait square and not stretched, and
      the name/email/phone selectable as text.
- [ ] **Keep the version.** File it against the application. Read it back from
      Applications and confirm it shows what was sent.
- [ ] **Write a letter.** Draft or type one, keep it against the application,
      download it, and **open the PDF**: the name and the sign-off must be
      selectable text, not a picture.
- [ ] **Interview brief.** Move an application to `interview`, open the brief,
      check a gap carries its bridge line, type a note, and print it — the
      app's chrome must not be on the printed page.
- [ ] **Focus tags.** Tag a bullet, set the focus on the Resume screen, and
      confirm the untagged lines stay while the other family's line goes.
- [ ] **A second CV.** Start one from the sidebar, confirm it is blank, put a
      name in it, switch back and confirm the first is untouched. The design
      should not change with the switch; the applications should still be
      there.
- [ ] **Restart the server.** Profile, design, applications, versions and
      letters all survive.

## 3. Undo

- [ ] Type into a bullet, then Ctrl+Z: the whole run goes, not one letter.
- [ ] Change the paper size from the dropdown, then Ctrl+Z **while the
      dropdown still has focus**: it goes back. (A `<select>` has no undo of
      its own; this regressed once.)
- [ ] Reorder a bullet, Ctrl+Z, Ctrl+Shift+Z: the order goes back and forward.
- [ ] Open the history panel, jump back three steps, then press redo three
      times: you walk back up through the same steps in order.

## 4. Degrading

- [ ] **No API key.** Import's parse button, Tailor's rewrite and the draft
      buttons are disabled with a sentence saying why. Everything else works.
- [ ] **Server stopped mid-session.** An action produces a message naming the
      command to restart it, and nothing on screen is lost.
- [ ] **A malformed import** (a text file of nonsense, a corrupt PDF) produces
      a sentence, not a traceback, and leaves the profile untouched.
- [ ] **A failed score.** The Health screen says so and offers a retry rather
      than showing a stale number.

## 5. Looking right

- [ ] Light and dark, on **every** screen — including the modals (photo
      cropper, command palette, history panel) and the toasts.
- [ ] 1500px and 420px wide. Nothing overlaps, nothing is clipped, and the
      document never scrolls horizontally.
- [ ] Tab through each screen: every interactive element takes focus in a
      sensible order and draws a visible ring.
- [ ] The browser console is clean. No warnings, no failed requests.

## 6. When the data model changed

- [ ] Write the migration, then **run it against a profile saved by the
      previous version** — not a fresh one.
- [ ] `tests/test_migrations.py` walks a version-1 dict all the way forward.
- [ ] Open a saved *version* from before the change. An archive that stops
      reading its own contents is not an archive.
