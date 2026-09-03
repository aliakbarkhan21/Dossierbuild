"""Dossierbuild -- entry point.

Run with:  streamlit run app.py

The profile lives in ``st.session_state`` for the life of the browser session
and is written to disk only when Save is pressed. Streamlit reruns this whole
script on every interaction, so anything expensive or destructive has to be
guarded -- loading from disk happens once, and writing happens on an explicit
click rather than on every keystroke.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

# Reads .env into the environment, so GEMINI_API_KEY can live in a file
# next to the project rather than in your shell profile.
load_dotenv()

from dossierbuild.quality import check_text, summarise
from dossierbuild.schema import LIST_SECTIONS, Profile, iter_bullets
from dossierbuild.settings import load_settings, save_settings
from dossierbuild.storage import PROFILE_PATH, ProfileError, load_profile, save_profile
from dossierbuild.ui import insights, theme
from dossierbuild.ui.assets import favicon
from dossierbuild.ui.profile_editor import SECTION_RENDERERS, current_vocabulary

# The tab icon is drawn in the saved theme's accent. It has to be settled
# before set_page_config, which must be the first Streamlit call -- so it reads
# the saved preference straight off disk rather than through session state. A
# ?theme= override in the URL therefore restyles the page but not the tab.
_saved = load_settings()
_accent = theme.get_palette(_saved["theme"], _saved["mode"])["primary"]

st.set_page_config(
    page_title="Dossierbuild",
    page_icon=favicon(_accent),
    layout="wide",
    initial_sidebar_state="expanded",
)


# --------------------------------------------------------------------------
# Appearance
# --------------------------------------------------------------------------


def boot_appearance() -> None:
    """Resolve theme and mode: query params win, then saved prefs, then defaults.

    Query-param support exists so a link or a screenshot run can pin an exact
    look (``?theme=sage&mode=dark``) without disturbing the saved preference.

    An explicit query parameter is re-applied on *every* run, not only the
    first. Streamlit reuses a session across page loads in the same browser,
    so a first-run-only check would silently ignore the parameter on every
    subsequent navigation.
    """
    params = st.query_params
    requested_theme = params.get("theme")
    requested_mode = params.get("mode")

    if "theme_key" not in st.session_state:
        saved = load_settings()
        st.session_state.theme_key = saved["theme"]
        st.session_state.mode = saved["mode"]
        st.session_state.density = saved["density"]
        st.session_state.autosave = saved["autosave"] == "on"

    if requested_theme:
        st.session_state.theme_key = requested_theme
    if requested_mode:
        st.session_state.mode = requested_mode

    if st.session_state.theme_key not in theme.THEMES:
        st.session_state.theme_key = theme.DEFAULT_THEME
    if st.session_state.mode not in ("light", "dark"):
        st.session_state.mode = theme.DEFAULT_MODE
    if st.session_state.get("density") not in ("comfortable", "compact"):
        st.session_state.density = "comfortable"


boot_appearance()
theme.apply_theme(
    st.session_state.theme_key, st.session_state.mode, st.session_state.density
)


def set_appearance(
    *,
    theme_key: str | None = None,
    mode: str | None = None,
    density: str | None = None,
    autosave: bool | None = None,
) -> None:
    if theme_key is not None:
        st.session_state.theme_key = theme_key
    if mode is not None:
        st.session_state.mode = mode
    if density is not None:
        st.session_state.density = density
    if autosave is not None:
        st.session_state.autosave = autosave
    save_settings(
        {
            "theme": st.session_state.theme_key,
            "mode": st.session_state.mode,
            "density": st.session_state.density,
            "autosave": "on" if st.session_state.autosave else "off",
        }
    )


# Appearance lives in a keyed container that CSS pins to the top-right, beside
# Streamlit's own three-dot menu -- a closed component that cannot take custom
# items, so this sits next to it rather than inside it. Palette and light/dark
# are one decision, so they share one popover instead of being split between
# the sidebar and a floating button.
with st.container(key="db_appearance"):
    with st.popover("Appearance", icon=":material/palette:"):
        st.markdown('<p class="db-menu-label">Palette</p>', unsafe_allow_html=True)
        keys = list(theme.THEMES)
        chosen = st.selectbox(
            "Palette",
            options=keys,
            index=keys.index(st.session_state.theme_key),
            format_func=lambda k: theme.THEMES[k]["name"],
            label_visibility="collapsed",
        )
        if chosen != st.session_state.theme_key:
            set_appearance(theme_key=chosen)
            st.rerun()
        theme.muted(theme.THEMES[st.session_state.theme_key]["blurb"])

        st.markdown('<p class="db-menu-label">Mode</p>', unsafe_allow_html=True)
        # Material icons rather than a typographic moon: they come from the
        # font Streamlit already loads, so they stay sharp at any zoom and
        # match weight with the rest of the interface.
        mode_choice = st.segmented_control(
            "Mode",
            options=["light", "dark"],
            default=st.session_state.mode,
            format_func=lambda m: (
                ":material/light_mode: Light" if m == "light" else ":material/dark_mode: Dark"
            ),
            label_visibility="collapsed",
        )
        if mode_choice and mode_choice != st.session_state.mode:
            set_appearance(mode=mode_choice)
            st.rerun()

        # Density is an appearance decision in the same breath as palette and
        # mode: it changes nothing about the data, only how much room the
        # workspace takes to show it.
        st.markdown('<p class="db-menu-label">Density</p>', unsafe_allow_html=True)
        density_choice = st.segmented_control(
            "Density",
            options=["comfortable", "compact"],
            default=st.session_state.density,
            format_func=lambda d: (
                ":material/density_medium: Comfortable"
                if d == "comfortable"
                else ":material/density_small: Compact"
            ),
            label_visibility="collapsed",
        )
        if density_choice and density_choice != st.session_state.density:
            set_appearance(density=density_choice)
            st.rerun()


# --------------------------------------------------------------------------
# Profile state
# --------------------------------------------------------------------------


def fingerprint(p: Profile) -> str:
    """A stable hash of the profile, used to detect unsaved changes."""
    payload = json.dumps(p.model_dump(mode="json"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def boot_profile() -> None:
    """Load the profile from disk exactly once per session."""
    if "profile" in st.session_state:
        return
    try:
        st.session_state.profile = load_profile()
        st.session_state.load_error = None
    except ProfileError as exc:
        st.session_state.profile = Profile.empty()
        st.session_state.load_error = str(exc)
    st.session_state.last_saved = None
    st.session_state.saved_fingerprint = fingerprint(st.session_state.profile)


boot_profile()
profile: Profile = st.session_state.profile

HISTORY_LIMIT = 30


def track_history() -> None:
    """Keep the last few states of the profile so an edit can be taken back.

    Streamlit gives no per-edit hook, so this watches the fingerprint instead:
    whenever it differs from the last run, the *previous* snapshot is pushed
    onto the stack. That makes one undo step equal one interaction, which is
    what a person means by "undo" here.
    """
    current = fingerprint(profile)
    if st.session_state.get("last_fingerprint") == current:
        return
    previous = st.session_state.get("last_snapshot")
    if previous is not None:
        history = st.session_state.setdefault("history", [])
        history.append(previous)
        del history[:-HISTORY_LIMIT]
    st.session_state.last_snapshot = profile.model_dump(mode="json")
    st.session_state.last_fingerprint = current


def undo() -> None:
    """Restore the previous snapshot, widgets included.

    Restoring the model is the easy half. The hard half is that the editor's
    widgets hold the old text in the *browser*, and the next rerun request
    carries those values back up -- so a widget with a key silently overwrites
    the model it was supposed to be re-reading. Deleting the server-side keys
    does not stop that; the values are re-sent regardless.

    What does work is renaming the widgets: see ``_wk`` in profile_editor.
    A new key is a new widget, with nothing remembered to send back.
    """
    history = st.session_state.get("history") or []
    if not history:
        return
    snapshot = history.pop()
    st.session_state.profile = Profile.model_validate(snapshot)
    st.session_state.last_snapshot = snapshot
    st.session_state.last_fingerprint = fingerprint(st.session_state.profile)
    # Bumping the revision renames every editor widget, so the rebuilt set has
    # no remembered values to re-send and reads the restored model instead.
    st.session_state.editor_rev = st.session_state.get("editor_rev", 0) + 1
    for key in [k for k in st.session_state if isinstance(k, str) and ":" in k]:
        del st.session_state[key]


track_history()

# The boot snapshot is what "changes this session" is measured against.
if "boot_snapshot" not in st.session_state:
    st.session_state.boot_snapshot = profile.model_dump(mode="json")


def do_save(announce: bool = False) -> None:
    """Write the profile. ``announce`` is for saves the user asked for.

    Autosave calls this on every keystroke, so a success message has to be
    opt-in: a toast per character would be worse than no feedback at all.
    """
    try:
        path = save_profile(profile)
        st.session_state.last_saved = datetime.now()
        st.session_state.saved_fingerprint = fingerprint(profile)
        if announce:
            st.toast(f"Saved to {path.name}", icon=":material/check_circle:")
    except Exception as exc:  # noqa: BLE001 -- surfaced, not swallowed
        st.session_state.save_error = f"Could not save: {exc}"


# --------------------------------------------------------------------------
# Derived figures
# --------------------------------------------------------------------------


def completeness(p: Profile) -> tuple[int, list[str]]:
    checks = [
        ("contact details", bool(p.basics.name and p.basics.email)),
        ("a summary", bool(p.summary.text.strip())),
        ("experience", bool(p.experience)),
        ("projects", bool(p.projects)),
        ("education", bool(p.education)),
        ("skills", bool(p.skills)),
    ]
    done = sum(1 for _, ok in checks if ok)
    return round(100 * done / len(checks)), [name for name, ok in checks if not ok]


def run_quality(p: Profile) -> dict[str, list]:
    """Lint every block using the same live vocabulary the editor uses."""
    vocabulary = current_vocabulary(p)
    results: dict[str, list] = {}
    for section, _owner, block in iter_bullets(p):
        found = check_text(
            block.text,
            block.id,
            is_summary=(section == "summary"),
            vocabulary=vocabulary,
        )
        if found:
            results[block.id] = found
    return results


def section_fill(p: Profile) -> list[tuple[str, bool]]:
    """One (label, has content) pair per editor tab, in tab order.

    Basics and summary are single objects rather than lists, so "filled" means
    something different for each: a contactable header, and a summary with
    words in it.
    """
    out: list[tuple[str, bool]] = []
    for key, (label, _renderer) in SECTION_RENDERERS.items():
        if key == "basics":
            ok = bool(p.basics.name and p.basics.email)
        elif key == "summary":
            ok = bool(p.summary.text.strip())
        else:
            ok = bool(getattr(p, key))
        out.append((label, ok))
    return out


def profile_stats(p: Profile, results: dict[str, list]) -> dict[str, int]:
    blocks = [b for _s, _o, b in iter_bullets(p) if b.text.strip()]
    entries = sum(len(getattr(p, section)) for section in LIST_SECTIONS)
    words = sum(len(b.text.split()) for b in blocks)

    # A block counts as clean if nothing above note level was flagged against
    # it. Notes are stylistic nudges; errors and warnings are the ones that
    # mean a line is not pulling its weight.
    flagged = {
        bid
        for bid, findings in results.items()
        if any(f.severity in ("error", "warning") for f in findings)
    }
    clean = len([b for b in blocks if b.id not in flagged])
    score = round(100 * clean / len(blocks)) if blocks else 0
    return {"entries": entries, "bullets": len(blocks), "words": words, "score": score}


# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------

# A page change asked for from the main area cannot write to the nav radio's
# key directly: by the time a button in the body runs, the widget has already
# been instantiated this run and Streamlit refuses the assignment. So the
# request is parked and applied here, before the radio is built.
if pending := st.session_state.pop("pending_page", None):
    st.session_state.db_page = pending

with st.sidebar:
    theme.brand("Dossierbuild", "Resume workspace")
    theme.rule()

    with st.container(key="db_nav"):
        page = st.radio(
            "Section",
            ["Master profile", "Resume", "Import", "Health check"],
            label_visibility="collapsed",
            key="db_page",
        )

    theme.rule()

    # Everything below this line reports on the profile, and the profile does
    # not hold this run's typing until the editors further down have run. So
    # the position is reserved now and filled at the very end of the script --
    # without that, "Save changes" stayed disabled for one whole interaction
    # after an edit, which also made Ctrl+S do nothing.
    sidebar_tail = st.container()

    with st.container(key="db_sidebar_footer"):
        theme.sidebar_footer(
            "Muhammad Ali Akbar",
            "https://www.linkedin.com/in/muhammad-ali-akbar-khan-7b37b8197",
        )


# --------------------------------------------------------------------------
# Main area
# --------------------------------------------------------------------------

if st.session_state.get("load_error"):
    st.error(
        "**data/profile.json could not be loaded, so this session started blank.**\n\n"
        "Saving now would overwrite that file. Fix it first, or rename it.\n\n"
        f"```\n{st.session_state.load_error}\n```"
    )

if page == "Master profile":
    theme.hero("Master profile")

    # Both readouts are drawn into slots reserved here and filled at the
    # bottom of this branch. Streamlit runs the script top to bottom, and the
    # editors below are what copy this run's keystrokes into the profile --
    # so anything measured *above* them reports the state before the edit and
    # trails the screen by one interaction. Reserving the position and writing
    # into it afterwards keeps the numbers honest while leaving them on top.
    empty_slot = st.container()
    stats_slot = st.container()
    search_slot = st.container()
    progress_slot = st.container(key="db_tab_progress")

    # A pill row rather than st.tabs, for two reasons that both bite daily.
    # Streamlit forgets which tab was open across a rerun, so adding an entry
    # -- which reruns -- threw you back to Contact every time. And st.tabs
    # renders *every* panel on every run, so eight sections of widgets were
    # being built to show one. This keeps the choice in session state and
    # draws only the section being looked at.
    counts = {section: len(getattr(profile, section)) for section in LIST_SECTIONS}
    section_keys = list(SECTION_RENDERERS)
    captions = {
        key: (f"{label} · {counts[key]}" if counts.get(key) else label)
        for key, (label, _r) in SECTION_RENDERERS.items()
    }

    if st.session_state.get("db_section") not in section_keys:
        st.session_state.db_section = section_keys[0]

    # Keyed container so the stylesheet can tell these apart from the mode and
    # density toggles -- Streamlit gives pills and segmented controls the same
    # stButtonGroup testid, and they want opposite treatments.
    with st.container(key="db_sections"):
        chosen_section = st.pills(
            "Section",
            options=section_keys,
            default=st.session_state.db_section,
            format_func=lambda k: captions[k],
            label_visibility="collapsed",
            key="db_section_pills",
        )
    if chosen_section and chosen_section != st.session_state.db_section:
        st.session_state.db_section = chosen_section
        st.rerun()

    active = st.session_state.db_section
    # Keyed by section, so switching sections builds a genuinely new element
    # and the fade in the stylesheet replays. Typing does not change the key,
    # so the panel does not flicker on every keystroke.
    with st.container(key=f"db_section_panel_{active}"):
        SECTION_RENDERERS[active][1](profile)

    # The one lint pass for this page. It runs *after* the editors, which is
    # the only point at which the profile holds this run's typing -- and it
    # used to run twice, once stale above and once here.
    results = run_quality(profile)
    stats = profile_stats(profile, results)
    has_material = bool(stats["bullets"] or stats["entries"])

    with empty_slot:
        if not has_material:
            st.markdown(
                '<div class="db-empty"><h3>Nothing in here yet</h3>'
                "<p>The master profile is the one place everything lives in full. "
                "Tailoring later cuts and re-angles this material -- it never "
                "invents any, so whatever is missing here cannot reach a resume.</p>"
                "<ol><li><b>Import</b> an existing resume or LinkedIn export, then "
                "correct it -- usually faster than typing.</li>"
                "<li>Or start with <b>Contact</b> and <b>Experience</b> below.</li>"
                "<li>Watch <b>Health check</b> for bullets that are not saying "
                "anything specific.</li></ol></div>",
                unsafe_allow_html=True,
            )
            st.markdown("")

    with stats_slot:
        if has_material:
            insights.render_strength(insights.strength(profile))
            st.markdown("")
            if insights.spans(profile):
                with st.expander("Career timeline", expanded=True):
                    insights.render_timeline(profile)

    with search_slot:
        if stats["bullets"]:
            query = st.text_input(
                "Search your material",
                placeholder="Search every bullet you have written...",
                label_visibility="collapsed",
                key="db_search",
            )
            if query.strip():
                hits = insights.search(profile, query)
                if not hits:
                    theme.muted(f"Nothing matches “{query.strip()}”.")
                else:
                    theme.muted(
                        f"{len(hits)} match{'es' if len(hits) != 1 else ''} "
                        f"for “{query.strip()}”."
                    )
                    for hit in hits:
                        where = " / ".join(x for x in (hit.section, hit.owner) if x)
                        st.markdown(
                            f'<div class="db-hit"><div class="db-hit-where">{where}</div>'
                            f'<div class="db-hit-text">'
                            f"{insights.highlight(hit.text, query)}</div></div>",
                            unsafe_allow_html=True,
                        )
                st.markdown("")

    # Sits in the free space to the right of the last tab; the stylesheet
    # lifts this zero-height block onto the tab row.
    fill = section_fill(profile)
    with progress_slot:
        theme.tab_progress(
            done=sum(1 for _label, ok in fill if ok),
            total=len(fill),
            filled=[ok for _label, ok in fill],
            missing=[label for label, ok in fill if not ok],
            active=section_keys.index(active) if active in section_keys else None,
        )

elif page == "Resume":
    from dossierbuild.ui.resume_page import render_resume_page

    render_resume_page(profile)

elif page == "Import":
    from dossierbuild.ui.import_page import render_import_page

    render_import_page(profile)

elif page == "Health check":
    theme.hero(
        "Health check",
        "Every bullet in the profile, measured against the writing standard. "
        "Nothing here blocks a save -- these are judgements, not rules.",
    )

    results = run_quality(profile)
    errors, warnings, notes = summarise(results)
    stats = profile_stats(profile, results)

    cols = st.columns(4)
    with cols[0]:
        theme.stat(f"{stats['score']}%", "Bullets clean")
    with cols[1]:
        theme.stat(errors, "Filler")
    with cols[2]:
        theme.stat(warnings, "Warnings")
    with cols[3]:
        theme.stat(notes, "Notes")
    st.markdown("")

    if not results:
        if stats["bullets"]:
            st.success("Nothing flagged. Every bullet names something specific.")
        else:
            theme.muted("No bullets written yet -- nothing to check.")
    else:
        # With a full profile this list runs long, and the three severities are
        # different jobs: filler is a rewrite, a note is a judgement call. The
        # filter lets one be worked through without the others in the way.
        severity = st.segmented_control(
            "Show",
            options=["all", "error", "warning", "note"],
            default="all",
            format_func=lambda s: {
                "all": f"All {len(results)}",
                "error": f"Filler {errors}",
                "warning": f"Warnings {warnings}",
                "note": f"Notes {notes}",
            }[s],
            label_visibility="collapsed",
        ) or "all"

        lookup = {block.id: (section, block) for section, _o, block in iter_bullets(profile)}
        shown = 0
        for block_id, findings in results.items():
            if severity != "all":
                findings = [f for f in findings if f.severity == severity]
                if not findings:
                    continue
            shown += 1
            section, block = lookup[block_id]
            body = "".join(
                f'<div class="db-finding {f.severity}">{f.icon} {f.message}</div>'
                for f in findings
            )
            st.markdown(
                f'<div class="db-card">{theme.tag(section, section)}'
                f'<div style="margin:.55rem 0 .5rem 0;font-size:.93rem">{block.text}</div>'
                f"{body}</div>",
                unsafe_allow_html=True,
            )

        if not shown:
            theme.muted("Nothing at that level.")


# --------------------------------------------------------------------------
# Autosave, last
# --------------------------------------------------------------------------
#
# The editors above are what copy this run's typing into the profile, so this
# is the earliest point at which "everything the user has done" is actually in
# the model. Saving here means closing the tab straight after a keystroke does
# not lose it -- which is the whole promise of autosave, and would be quietly
# broken by saving from the sidebar alone.

# --------------------------------------------------------------------------
# The sidebar's lower half, drawn last
# --------------------------------------------------------------------------


def render_sidebar_tail() -> None:
    """Save, undo, autosave, backup and the session log -- with fresh figures.

    Every widget here is a function of the profile *after* this run's edits,
    so it is rendered into the slot reserved in the sidebar rather than in
    place. Buttons still behave normally: a click reruns the script, and by
    the time this function is reached again the edit is in the model.
    """
    now_dirty = fingerprint(profile) != st.session_state.saved_fingerprint

    save_col, undo_col = st.columns([3, 1], gap="small")
    with save_col:
        if st.button(
            "Save changes" if now_dirty else "Saved",
            type="primary" if now_dirty else "secondary",
            disabled=not now_dirty,
            width="stretch",
        ):
            do_save(announce=True)
            st.rerun()
    with undo_col:
        if st.button(
            "",
            icon=":material/undo:",
            help="Undo the last edit",
            disabled=not st.session_state.get("history"),
            width="stretch",
            key="db_undo",
        ):
            undo()
            st.toast("Took back the last edit", icon=":material/undo:")
            st.rerun()

    # One strip where there used to be four stacked elements saying the same
    # thing: a state, and the single switch that changes how it is reached.
    autosave_on = st.toggle(
        "Autosave",
        value=st.session_state.autosave,
        help="Write every edit to data/profile.json as you go.",
    )
    if now_dirty:
        theme.status("unsaved", "Unsaved changes")
    elif st.session_state.get("last_saved"):
        theme.status("ok", "Saved " + st.session_state.last_saved.strftime("%H:%M"))
    elif PROFILE_PATH.exists():
        theme.status("ok", "Loaded from disk")
    else:
        theme.status("idle", "Nothing saved yet")
    if autosave_on != st.session_state.autosave:
        set_appearance(autosave=autosave_on)
        st.rerun()

    if failure := st.session_state.pop("save_error", None):
        st.error(failure)
    theme.keys_hint()

    theme.rule()

    with st.expander("Backup"):
        theme.muted(
            "Your profile is plain JSON. Keep a copy anywhere you like, and restore it here."
        )
        st.download_button(
            "Download profile.json",
            data=json.dumps(profile.model_dump(mode="json"), indent=2, ensure_ascii=False),
            file_name=f"dossierbuild-profile-{datetime.now():%Y%m%d}.json",
            mime="application/json",
            width="stretch",
        )
        st.markdown(
            '<p class="db-menu-label" style="margin-top:.6rem">Readable copy</p>',
            unsafe_allow_html=True,
        )
        theme.muted(
            "Everything in the profile as plain text -- for an email, an "
            "application form, or someone reviewing your material."
        )
        st.download_button(
            "Download profile.txt",
            data=insights.plain_text(profile),
            file_name=f"dossierbuild-profile-{datetime.now():%Y%m%d}.txt",
            mime="text/plain",
            width="stretch",
        )

        restore = st.file_uploader("Restore from a file", type=["json"], key="restore_file")
        if restore is not None:
            confirmed = st.checkbox("Replace everything currently in this session")
            if st.button("Restore", disabled=not confirmed):
                try:
                    raw = json.loads(restore.getvalue().decode("utf-8"))
                    st.session_state.profile = Profile.model_validate(raw)
                    st.session_state.saved_fingerprint = ""  # leaves it dirty on purpose
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Could not restore that file: {exc}")

    session_changes = insights.changes(
        st.session_state.boot_snapshot, profile.model_dump(mode="json")
    )
    if session_changes:
        with st.expander(f"This session ({len(session_changes)})"):
            for line in session_changes:
                theme.muted(line)


# Autosave first, so the strip below reports the state the disk is actually
# in rather than a saved-a-moment-ago "Unsaved changes".
if st.session_state.autosave and fingerprint(profile) != st.session_state.saved_fingerprint:
    do_save()

with sidebar_tail:
    render_sidebar_tail()

theme.shortcuts()
