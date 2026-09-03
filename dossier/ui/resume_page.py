"""The Resume page: pick a template, dress it, watch it, print it.

The shape of this screen is the argument. A gallery of the *user's own*
material in eight layouts sits on top, the controls that change one thing each
sit on the left, and the page itself -- at the size it will print -- takes the
rest. Nothing here is a preview of a preview: the pane on the right renders
the same HTML that Chromium prints, so the two cannot disagree.
"""

from __future__ import annotations

import hashlib

import streamlit as st
import streamlit.components.v1 as components

from ..render import design as dz
from ..render import photo
from ..render.context import build_context, suggested_filename
from ..render.design import Design
from ..render.html import render_html, render_thumbnail
from ..render.pdf import PDFError, Report, pdf_report, render_pdf
from ..core.schema import Profile
from . import theme

DESIGN_KEY = "design"
BUILD_KEY = "pdf_build"
ZOOMS: dict[str, float] = {"Fit": 0.0, "100%": 1.0, "150%": 1.5}


# --------------------------------------------------------------------------
# State
# --------------------------------------------------------------------------


def boot_design() -> Design:
    if DESIGN_KEY not in st.session_state:
        st.session_state[DESIGN_KEY] = dz.load_design()
    return st.session_state[DESIGN_KEY]


def set_design(new: Design, *, rerun: bool = True) -> None:
    """Store and persist a design change.

    Written to disk on every change rather than behind a Save button: unlike
    the profile, nothing here is irreplaceable, and a design that forgets
    itself between sessions would be worse than useless.
    """
    st.session_state[DESIGN_KEY] = new
    dz.save_design(new)
    if rerun:
        st.rerun()


def _fingerprint(profile: Profile, design: Design) -> str:
    payload = profile.model_dump_json() + dz.design_key(design)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


@st.cache_data(show_spinner=False, max_entries=8)
def _pdf_bytes(html: str, margin_mm: float, page_numbers: bool) -> bytes:
    """Chromium, memoised on the exact document it is given.

    The cache key is the HTML itself, so pressing Build twice without editing
    costs nothing, while changing a single bullet produces a genuinely new
    document and a genuinely new render.
    """
    return render_pdf(html, margin_mm=margin_mm, page_numbers=page_numbers)


# --------------------------------------------------------------------------
# Gallery
# --------------------------------------------------------------------------


PER_ROW = 4

# What a person is actually choosing between when they scan eight layouts:
# will a parser read it in order, and is there a face on it.
FILTERS: dict[str, str] = {
    "All": "",
    "ATS-safe": "ats",
    "Two columns": "two",
    "With a portrait": "photo",
}


def _matches(spec: dz.Template, rule: str) -> bool:
    if rule == "ats":
        return spec.ats
    if rule == "two":
        return not spec.ats
    if rule == "photo":
        return spec.photo
    return True


def _card(profile: Profile, design: Design, key: str, spec: dz.Template) -> None:
    selected = key == design.template
    # The container key carries the selection, which is the only way the
    # stylesheet can tell the chosen card from the other seven.
    with st.container(key=f"db_tpl_{'sel_' if selected else ''}{key}"):
        components.html(
            render_thumbnail(profile, design, key, 0.0), height=224, scrolling=False
        )
        badges = (
            '<span class="db-badge ok">ATS-safe</span>'
            if spec.ats
            else '<span class="db-badge warn">Two-column</span>'
        )
        if spec.photo:
            badges += '<span class="db-badge">Portrait</span>'
        st.markdown(
            f'<div class="db-tpl-meta"><div class="db-tpl-name">{spec.name}</div>'
            f'<div class="db-tpl-badges">{badges}</div><p>{spec.blurb}</p></div>',
            unsafe_allow_html=True,
        )
        if st.button(
            "Selected" if selected else "Use this",
            key=f"db_pick_{key}",
            type="primary" if selected else "secondary",
            width="stretch",
            disabled=selected,
            help=spec.best_for,
        ):
            set_design(design.model_copy(update={"template": key}))


def _gallery(profile: Profile, design: Design) -> None:
    label_col, filter_col = st.columns([0.42, 0.58])
    with label_col:
        theme.section_label("Template", "projects")
    with filter_col:
        chosen = st.segmented_control(
            "Filter",
            options=list(FILTERS),
            default="All",
            label_visibility="collapsed",
            key="db_tpl_filter",
        ) or "All"

    rule = FILTERS[chosen]
    shown = [(k, s) for k, s in dz.TEMPLATES.items() if _matches(s, rule)]
    if not shown:
        theme.muted("No template matches that.")
        return

    # A fixed four across, padded out on the last row -- with a variable
    # column count the cards change width as the filter changes, which reads
    # as the page jumping rather than as a list being filtered.
    for start in range(0, len(shown), PER_ROW):
        row = shown[start : start + PER_ROW]
        columns = st.columns(PER_ROW, gap="small")
        for column, (key, spec) in zip(columns, row):
            with column:
                _card(profile, design, key, spec)


# --------------------------------------------------------------------------
# Controls
# --------------------------------------------------------------------------


def _looks_row(design: Design) -> None:
    """Six good combinations, one click each.

    The controls below this row are all independently sensible and still
    combine into a few hundred looks, most of which nobody wants. These are
    the ones worth starting from; everything stays adjustable afterwards.
    """
    st.markdown('<p class="db-menu-label">Start from a look</p>', unsafe_allow_html=True)
    for start in range(0, len(dz.LOOKS), 3):
        columns = st.columns(3, gap="small")
        for column, look in zip(columns, dz.LOOKS[start : start + 3]):
            active = design.is_look(look)
            with column, st.container(key=f"db_look_{'sel_' if active else ''}{look.key}"):
                if st.button(
                    look.name,
                    key=f"db_look_btn_{look.key}",
                    width="stretch",
                    help=look.blurb,
                    disabled=active,
                ):
                    set_design(design.with_look(look))


def _photo_controls(profile: Profile, design: Design) -> None:
    """Upload, shape and show/hide -- only for layouts with a place for one."""
    st.markdown('<p class="db-menu-label">Portrait</p>', unsafe_allow_html=True)
    current = photo.photo_path(profile.basics.photo)

    if current is not None:
        preview_col, action_col = st.columns([0.32, 0.68], vertical_alignment="center")
        with preview_col:
            st.image(str(current), width=76)
        with action_col:
            theme.muted(f"{current.name} · {current.stat().st_size // 1024} KB")
            if st.button("Remove", icon=":material/delete:", key="db_photo_remove"):
                photo.remove_photo(profile.basics.photo)
                profile.basics.photo = ""
                st.rerun()
    else:
        theme.muted(
            "No portrait yet. A photo is expected on a CV in much of Europe and "
            "Asia, and is discouraged in the US, UK and Canada -- several large "
            "employers there discard resumes carrying one."
        )

    uploaded = st.file_uploader(
        "Replace the portrait" if current else "Add a portrait",
        type=["png", "jpg", "jpeg", "webp"],
        key="db_photo_upload",
        label_visibility="collapsed",
    )
    if uploaded is not None:
        try:
            profile.basics.photo = photo.save_photo(uploaded.getvalue())
            st.toast("Portrait added", icon=":material/photo_camera:")
            st.rerun()
        except photo.PhotoError as exc:
            st.error(str(exc))

    shape = st.segmented_control(
        "Shape",
        options=["circle", "square"],
        default=design.photo_shape,
        format_func=lambda s: s.title(),
        label_visibility="collapsed",
    )
    if shape and shape != design.photo_shape:
        set_design(design.model_copy(update={"photo_shape": shape}))

    show = st.toggle("Show the portrait", value=design.show_photo)
    if show != design.show_photo:
        set_design(design.model_copy(update={"show_photo": show}))


def _accent_row(design: Design) -> None:
    st.markdown('<p class="db-menu-label">Accent</p>', unsafe_allow_html=True)
    columns = st.columns(len(dz.ACCENTS), gap="small")
    for column, (key, (name, _hex)) in zip(columns, dz.ACCENTS.items()):
        chosen = key == design.accent
        with column:
            if st.button(
                "​",  # zero-width space: the swatch is the colour, not a word
                key=f"db_accent_{'sel_' if chosen else ''}{key}",
                help=name,
                width="stretch",
            ):
                set_design(design.model_copy(update={"accent": key}))


def _segmented(label: str, options: dict[str, str], current: str, field: str, design: Design) -> None:
    st.markdown(f'<p class="db-menu-label">{label}</p>', unsafe_allow_html=True)
    choice = st.segmented_control(
        label,
        options=list(options),
        default=current,
        format_func=lambda k: options[k],
        label_visibility="collapsed",
    )
    if choice and choice != current:
        set_design(design.model_copy(update={field: choice}))


def _sections_editor(profile: Profile, design: Design) -> None:
    theme.muted(
        "Order and visibility for this resume only -- nothing here changes your "
        "profile. A section with nothing in it never prints, shown or not."
    )
    last = len(design.order) - 1
    for index, key in enumerate(design.order):
        shown = key not in design.hidden
        has_content = _section_has_content(profile, key)
        label = dz.SECTION_LABELS[key]

        name_col, up_col, down_col, eye_col = st.columns([0.58, 0.14, 0.14, 0.14])
        with name_col:
            state = "" if has_content else '<span class="db-badge">empty</span>'
            css = "db-sec-row" + ("" if shown else " off")
            st.markdown(
                f'<div class="{css}">{label}{state}</div>', unsafe_allow_html=True
            )
        with up_col:
            if st.button(
                "", icon=":material/arrow_upward:", key=f"db_up_{key}",
                disabled=index == 0, width="stretch", help="Move up",
            ):
                set_design(design.with_moved(key, -1))
        with down_col:
            if st.button(
                "", icon=":material/arrow_downward:", key=f"db_down_{key}",
                disabled=index == last, width="stretch", help="Move down",
            ):
                set_design(design.with_moved(key, 1))
        with eye_col:
            if st.button(
                "",
                icon=":material/visibility:" if shown else ":material/visibility_off:",
                key=f"db_eye_{key}",
                width="stretch",
                help="Hide from this resume" if shown else "Show on this resume",
            ):
                set_design(design.with_toggled(key))


def _section_has_content(profile: Profile, key: str) -> bool:
    if key == "summary":
        return bool(profile.summary.text.strip())
    return bool(getattr(profile, key, []))


def _controls(profile: Profile, design: Design) -> None:
    _looks_row(design)
    st.markdown("")

    with st.expander("Type and colour", expanded=True):
        _accent_row(design)

        st.markdown('<p class="db-menu-label">Typeface</p>', unsafe_allow_html=True)
        keys = list(dz.PAIRINGS)
        chosen = st.selectbox(
            "Typeface",
            options=keys,
            index=keys.index(design.fonts),
            format_func=lambda k: dz.PAIRINGS[k].name,
            label_visibility="collapsed",
        )
        if chosen != design.fonts:
            set_design(design.model_copy(update={"fonts": chosen}))
        theme.muted(dz.PAIRINGS[design.fonts].blurb)

        _segmented(
            "Line spacing",
            {k: v[0] for k, v in dz.LEADING.items()},
            design.leading,
            "leading",
            design,
        )

        # Steps rather than a slider, for two reasons. Streamlit paints a
        # slider's filled track with a gradient baked from the startup theme,
        # so it stays green whatever palette is chosen -- and five sizes are
        # all a resume needs. 100% is 10.5pt body text.
        st.markdown('<p class="db-menu-label">Type size</p>', unsafe_allow_html=True)
        steps = [92, 96, 100, 104, 108]
        current = min(steps, key=lambda s: abs(s - design.scale))
        scale = st.segmented_control(
            "Type size",
            options=steps,
            default=current,
            format_func=lambda v: f"{v}%",
            label_visibility="collapsed",
        )
        if scale and scale != design.scale:
            set_design(design.model_copy(update={"scale": scale}))

    with st.expander("Page", expanded=False):
        _segmented(
            "Paper", {k: v.name for k, v in dz.PAGES.items()}, design.page, "page", design
        )
        _segmented(
            "Margins",
            {k: f"{v[0]} · {v[1]:.0f}mm" for k, v in dz.MARGINS.items()},
            design.margin,
            "margin",
            design,
        )
        st.markdown("")
        links = st.toggle("Show links in the header", value=design.show_links)
        headline = st.toggle("Show headline under the name", value=design.show_headline)
        numbers = st.toggle("Number the pages", value=design.show_page_numbers)
        if (links, headline, numbers) != (
            design.show_links,
            design.show_headline,
            design.show_page_numbers,
        ):
            set_design(
                design.model_copy(
                    update={
                        "show_links": links,
                        "show_headline": headline,
                        "show_page_numbers": numbers,
                    }
                )
            )

    if design.template_spec.photo:
        with st.expander("Portrait", expanded=False):
            _photo_controls(profile, design)

    with st.expander("Sections", expanded=False):
        _sections_editor(profile, design)

    if design != Design():
        if st.button("Reset design", icon=":material/restart_alt:", width="stretch"):
            set_design(Design())


# --------------------------------------------------------------------------
# Fit advice
# --------------------------------------------------------------------------


def fit_advice(design: Design, report: Report) -> list[str]:
    """Concrete moves, in order of how much room they buy.

    Not a lecture about being concise: every line here is a control the user
    can act on in one click, and each says roughly what it is worth.
    """
    if report.pages <= 1:
        return []
    tips: list[str] = []
    if design.template != "compact":
        tips.append("Switch to **Compact** -- about 13% shorter on the same material.")
    if design.margin != "tight":
        tips.append("**Tight margins** -- 4mm a side, worth roughly three lines.")
    if design.leading != "tight":
        tips.append("**Tight line spacing** -- the largest single saving on a busy page.")
    if design.scale > 96:
        tips.append("Drop **type size** to 96%.")
    hidden = [k for k in ("awards", "certifications") if k not in design.hidden]
    if hidden:
        names = " or ".join(dz.SECTION_LABELS[k] for k in hidden)
        tips.append(f"Hide **{names}** for this application.")
    return tips


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------


def _report_card(report: Report, design: Design) -> None:
    checks = "".join(
        f'<span class="db-check {"ok" if ok else "bad"}">'
        f'{"✓" if ok else "✗"} {label}</span>'
        for label, ok in report.found.items()
    )
    pages = f"{report.pages} page" + ("s" if report.pages != 1 else "")
    st.markdown(
        f'<div class="db-pdfreport">'
        f'<div class="db-pdfrow"><b>{pages}</b> · {report.words} words · '
        f"{report.size_kb} KB · {design.page_spec.name}</div>"
        f'<div class="db-pdfrow db-checks">{checks}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )
    if not report.machine_readable:
        st.error(
            "The PDF carries almost no selectable text. An applicant tracking "
            "system would read it as an empty document."
        )
    elif report.missing:
        st.warning(
            "Not found in the PDF's text layer: "
            + ", ".join(report.missing)
            + ". A parser will not find them either."
        )


def _output(profile: Profile, design: Design, print_html: str, key: str) -> None:
    build = st.session_state.get(BUILD_KEY)
    fresh = bool(build and build.get("key") == key)

    build_col, get_col = st.columns([0.42, 0.58])
    with build_col:
        if st.button(
            "Rebuild PDF" if build else "Build PDF",
            type="primary",
            width="stretch",
            icon=":material/picture_as_pdf:",
            disabled=fresh,
        ):
            try:
                with st.spinner("Printing in headless Chromium..."):
                    pdf = _pdf_bytes(
                        print_html, design.margin_mm, design.show_page_numbers
                    )
                st.session_state[BUILD_KEY] = {
                    "key": key,
                    "bytes": pdf,
                    "report": pdf_report(pdf, profile),
                }
                st.toast("PDF ready", icon=":material/check_circle:")
                st.rerun()
            except PDFError as exc:
                st.error(str(exc))

    with get_col:
        if fresh:
            st.download_button(
                "Download PDF",
                data=build["bytes"],
                file_name=suggested_filename(profile, design),
                mime="application/pdf",
                width="stretch",
                icon=":material/download:",
                type="primary",
            )
        else:
            st.download_button(
                "Download HTML",
                data=print_html,
                file_name=suggested_filename(profile, design, "html"),
                mime="text/html",
                width="stretch",
                icon=":material/code:",
                help="The same document as a single self-contained file, for the web or an email.",
            )

    if build and not fresh:
        theme.muted("The profile or the design changed since that PDF -- build it again.")
    if fresh:
        _report_card(build["report"], design)
        tips = fit_advice(design, build["report"])
        if tips:
            with st.expander(f"Getting it onto one page ({len(tips)} ways)"):
                for tip in tips:
                    st.markdown(f"- {tip}")


# --------------------------------------------------------------------------
# Page
# --------------------------------------------------------------------------


def render_resume_page(profile: Profile) -> None:
    design = boot_design()
    theme.hero("Resume")

    if profile.is_blank():
        st.markdown(
            '<div class="db-empty"><h3>Nothing to print yet</h3>'
            "<p>A template needs material. Fill in Contact and one role on the "
            "Master profile, or bring an existing resume in through Import, and "
            "this page will show it on paper.</p></div>",
            unsafe_allow_html=True,
        )
        if st.button("Go to Master profile", type="primary"):
            # Parked rather than set: app.py applies it before the nav radio
            # is built, which is the only moment Streamlit allows.
            st.session_state.pending_page = "Master profile"
            st.rerun()
        return

    context = build_context(profile, design)
    if not context.sections:
        st.warning(
            "Every section is either empty or hidden, so the page would carry "
            "only your name. Turn something back on under **Sections**."
        )

    _gallery(profile, design)
    st.markdown("")

    controls, page = st.columns([0.34, 0.66], gap="large")

    with controls:
        theme.section_label("Design", "basics")
        _controls(profile, design)

    with page:
        head, zoom_col = st.columns([0.55, 0.45])
        with head:
            theme.section_label("Preview", "summary")
        with zoom_col:
            zoom_name = st.segmented_control(
                "Zoom",
                options=list(ZOOMS),
                default="Fit",
                label_visibility="collapsed",
                key="db_zoom",
            ) or "Fit"

        preview_html = render_html(
            profile, design, preview=True, zoom=ZOOMS[zoom_name], context=context
        )
        with st.container(key="db_preview"):
            components.html(preview_html, height=940, scrolling=True)

        print_html = render_html(profile, design, context=context)
        _output(profile, design, print_html, _fingerprint(profile, design))
