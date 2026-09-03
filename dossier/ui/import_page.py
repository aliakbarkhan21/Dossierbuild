"""Import: bring existing career data in without overwriting what is here.

Every route lands in the same place -- a review screen listing what was found,
with everything that looks new ticked and anything resembling an existing entry
left unticked. Nothing touches the profile until Apply is pressed.
"""

from __future__ import annotations

import streamlit as st

from ..ai import parse as ai_parse
from ..ingest import extract, linkedin
from ..ingest.merge import MergePlan, apply_merge_plan, build_merge_plan
from ..core.schema import Profile
from . import theme

PLAN_KEY = "merge_plan"
PREVIEW_KEY = "import_preview_text"


# --------------------------------------------------------------------------
# Review screen
# --------------------------------------------------------------------------


def _render_plan(profile: Profile, plan: MergePlan) -> None:
    st.markdown("---")
    theme.section_label(f"Review: {plan.source}", "import")

    if plan.notes:
        for note in plan.notes:
            theme.muted(note)

    total = len(plan.candidates)
    new = len(plan.new_candidates)
    dupes = len(plan.duplicate_candidates)
    st.markdown(
        f"Found **{total}** entries: **{new}** new, **{dupes}** that look like "
        "something already in your profile."
    )

    accepted_fields: set[str] = set()
    accepted_candidates: set[str] = set()

    # --- scalar fields ----------------------------------------------------
    if plan.fields:
        st.markdown("**Contact details and summary**")
        for proposal in plan.fields:
            label = proposal.label
            if proposal.conflicts:
                label += "  (would replace what you have)"
            checked = st.checkbox(
                label,
                value=not proposal.conflicts,
                key=f"field:{proposal.path}",
            )
            if proposal.conflicts:
                col1, col2 = st.columns(2)
                with col1:
                    theme.muted(f"Now: {proposal.current[:180]}")
                with col2:
                    theme.muted(f"Import: {proposal.proposed[:180]}")
            else:
                theme.muted(proposal.proposed[:220])
            if checked:
                accepted_fields.add(proposal.path)
        st.markdown("")

    # --- entries ----------------------------------------------------------
    for section in ("experience", "projects", "education", "skills", "certifications", "awards"):
        entries = [c for c in plan.candidates if c.section == section]
        if not entries:
            continue
        st.markdown(f"**{section.title()}**")
        for candidate in entries:
            suffix = "  - already in your profile" if candidate.is_duplicate else ""
            checked = st.checkbox(
                f"{candidate.label}{suffix}",
                value=not candidate.is_duplicate,
                key=f"cand:{candidate.key}",
            )
            theme.muted(candidate.detail)
            bullets = getattr(candidate.entry, "bullets", [])
            if bullets:
                with st.expander(f"{len(bullets)} bullet points", expanded=False):
                    for block in bullets:
                        st.markdown(f"- {block.text}")
            if checked:
                accepted_candidates.add(candidate.key)
        st.markdown("")

    st.markdown("---")
    apply_col, cancel_col = st.columns([0.3, 0.7])
    with apply_col:
        if st.button("Add to profile", type="primary", width="stretch"):
            changes = apply_merge_plan(profile, plan, accepted_fields, accepted_candidates)
            st.session_state.pop(PLAN_KEY, None)
            if changes:
                st.session_state["import_result"] = changes
            else:
                st.session_state["import_result"] = ["Nothing was selected, so nothing changed."]
            st.rerun()
    with cancel_col:
        if st.button("Discard this import"):
            st.session_state.pop(PLAN_KEY, None)
            st.rerun()

    st.info(
        "Adding here only changes this session. Press **Save profile** in the sidebar "
        "to write it to data/profile.json."
    )


# --------------------------------------------------------------------------
# Sources
# --------------------------------------------------------------------------


def _linkedin_tab(profile: Profile) -> None:
    st.markdown(
        "LinkedIn does not offer an API that returns your positions, education or "
        "skills -- those endpoints are restricted to partner companies, and signing "
        "in with LinkedIn would only return your name and email. It does let you "
        "**export your own data**, which is better anyway: it arrives already "
        "structured, so nothing has to be guessed at."
    )

    with st.expander("How to get the export (about 10 minutes)", expanded=False):
        st.markdown(
            "1. LinkedIn -> **Settings & Privacy**\n"
            "2. **Data Privacy** -> **Get a copy of your data**\n"
            "3. Choose **Download larger data archive**, or tick just Profile, "
            "Positions, Education, Skills, Certifications, Projects and Honors\n"
            "4. Request it. LinkedIn emails a download link, usually within 10 minutes "
            "for the smaller archive\n"
            "5. Upload the ZIP here, without unzipping it"
        )

    uploaded = st.file_uploader("LinkedIn export ZIP", type=["zip"], key="li_zip")
    if uploaded is None:
        return

    if st.button("Read this archive", type="primary", key="li_go"):
        try:
            result = linkedin.parse_export(uploaded.getvalue())
        except ValueError as exc:
            st.error(str(exc))
            return

        plan = build_merge_plan(profile, result.profile, f"LinkedIn export ({uploaded.name})")
        plan.notes = list(result.notes)
        plan.notes.append(
            "Read: " + ", ".join(result.files_found)
            if result.files_found
            else "No recognised files."
        )
        plan.notes.append(
            "LinkedIn stores some dates as a year only. Those are kept as a year "
            "(\"2027\"), not turned into a month -- your resume will print the year."
        )
        st.session_state[PLAN_KEY] = plan
        st.rerun()


def _resume_tab(profile: Profile) -> None:
    st.markdown(
        "Upload an existing resume. Reading the text out of the file is exact; "
        "working out which line is a job title and which is a date is not, so that "
        "part uses Gemini and everything it returns is shown for review."
    )
    st.markdown(
        "Tip: your LinkedIn profile page has **More -> Save to PDF**. That PDF works here."
    )

    uploaded = st.file_uploader(
        "Resume file", type=["pdf", "docx", "txt", "md"], key="cv_file"
    )
    if uploaded is None:
        return

    if st.button("Read this file", key="cv_extract"):
        try:
            result = extract.extract(uploaded.getvalue(), uploaded.name)
        except (ValueError, RuntimeError) as exc:
            st.error(str(exc))
            return
        st.session_state[PREVIEW_KEY] = result.text
        for warning in result.warnings:
            st.warning(warning)
        st.rerun()

    text = st.session_state.get(PREVIEW_KEY)
    if not text:
        return

    st.markdown("**Extracted text**")
    theme.muted(
        f"{len(text)} characters. Check this looks right before parsing -- if a "
        "two-column layout came out interleaved, fix it here first."
    )
    edited = st.text_area("Extracted text", value=text, height=280, label_visibility="collapsed")
    st.session_state[PREVIEW_KEY] = edited

    _parse_button(profile, edited, source=f"Resume file ({uploaded.name})", key="cv_parse")


def _paste_tab(profile: Profile) -> None:
    st.markdown(
        "Paste resume text directly. Useful when a PDF will not extract cleanly, or "
        "when the resume only exists somewhere you can copy from."
    )
    text = st.text_area("Resume text", height=320, key="paste_text", label_visibility="collapsed")
    _parse_button(profile, text, source="Pasted text", key="paste_parse")


def _api_key_form(key: str) -> None:
    """Take the key here rather than sending the user off to edit a file.

    The old message was a dead end mid-task: stop, find a terminal, set a
    variable, restart, come back, re-upload the resume. The key only has to
    reach this process's environment, so it can just as well be typed in --
    and checked against the API before it is written anywhere, so a typo is
    caught now rather than on every later parse.
    """
    st.warning(
        "Parsing needs a Gemini API key -- it is what reads the resume text into "
        "structured fields. Get one free at aistudio.google.com/apikey, then paste "
        "it below.\n\nThe LinkedIn export tab needs no key: it does not use AI."
    )
    with st.form(f"{key}_apikey", border=False):
        entered = st.text_input(
            "Gemini API key",
            type="password",
            placeholder="AIza...",
            help="Kept on this machine. It is never sent anywhere except Google's API.",
        )
        remember = st.checkbox(
            "Remember it on this computer", value=True, key=f"{key}_remember"
        )
        if st.form_submit_button("Use this key", type="primary"):
            if not entered.strip():
                st.error("Paste the key first.")
                return
            with st.spinner("Checking the key..."):
                problem = ai_parse.verify_api_key(entered)
            if problem:
                st.error(problem)
                return
            ai_parse.use_api_key(entered)
            if remember:
                path = ai_parse.remember_api_key(entered)
                st.session_state["api_key_saved"] = path.name
            st.rerun()


def _parse_button(profile: Profile, text: str, *, source: str, key: str) -> None:
    saved = st.session_state.pop("api_key_saved", None)
    if saved:
        st.success(f"Key accepted and saved to {saved}. It will be picked up on every launch.")

    if not ai_parse.api_key_present():
        _api_key_form(key)
        return

    if st.button("Parse into profile", type="primary", key=key, disabled=not text.strip()):
        # A plain spinner was indistinguishable from a hang: when Google's
        # flash tier is busy this retries across several models for up to a
        # minute, and saying so beats a silent wheel.
        with st.status("Reading the resume...", expanded=True) as status:

            def report(model: str, state: str) -> None:
                if not model:
                    status.write(state)
                elif state == "trying":
                    status.update(label=f"Reading the resume with {model}...")
                else:
                    status.write(f"{model}: {state}")

            try:
                result = ai_parse.parse_resume_text(text, on_attempt=report)
            except ai_parse.MissingAPIKey as exc:
                status.update(label="No API key", state="error")
                st.error(str(exc))
                return
            except Exception as exc:  # noqa: BLE001
                status.update(label="Parsing failed", state="error")
                st.error(f"Parsing failed: {exc}")
                return
            status.update(label=f"Read by {result.model}", state="complete", expanded=False)

        plan = build_merge_plan(profile, result.profile, source)
        plan.notes.append(
            f"Parsed by {result.model}. It was told to transcribe, not rewrite -- "
            "but check the bullets below say what your resume actually said."
        )
        st.session_state[PLAN_KEY] = plan
        st.rerun()


# --------------------------------------------------------------------------
# Page
# --------------------------------------------------------------------------


def render_import_page(profile: Profile) -> None:
    theme.hero(
        "Import",
        "Pull in what you have already written. Imports only ever add -- "
        "nothing already in your profile is replaced without you ticking it.",
    )

    if result := st.session_state.pop("import_result", None):
        st.success("  ".join(result) + ".  Remember to press Save profile.")

    plan = st.session_state.get(PLAN_KEY)
    if plan is not None:
        _render_plan(profile, plan)
        return

    linkedin_tab, resume_tab, paste_tab = st.tabs(
        ["LinkedIn export", "Resume file", "Paste text"]
    )
    with linkedin_tab:
        _linkedin_tab(profile)
    with resume_tab:
        _resume_tab(profile)
    with paste_tab:
        _paste_tab(profile)
