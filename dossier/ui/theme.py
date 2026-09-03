"""The look of the Dossierbuild app itself.

Scope note, because it is easy to blur: this styles the *workspace* -- the
screen used while building a resume. It has nothing to do with how the
generated resume looks. The PDFs get their own typography in phase 2, and they
stay restrained. A recruiter should never see this palette.

How theming works here
----------------------
Streamlit's own theme is fixed at startup by ``.streamlit/config.toml``, so it
cannot be switched while the app is running. Everything below therefore drives
colour through **CSS custom properties**: one ``:root`` block is emitted per
render carrying the active palette, and every rule downstream reads
``var(--db-bg)`` and friends. Switching theme or mode re-emits that one block
and the entire interface follows, Streamlit's own widgets included.

That is also why the widget overrides are as thorough as they are. Streamlit
paints its inputs, tabs, expanders and alerts from its startup theme; without
explicit overrides they would stay light while everything around them went
dark.
"""

from __future__ import annotations

from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from dossier.render.design import ACCENTS as ACCENT_SWATCHES
from dossier.ui.assets import logo_data_uri

# --------------------------------------------------------------------------
# Typography
# --------------------------------------------------------------------------
#
# A serif for headings, a sans for everything else. This is the standard
# formal pairing: the serif carries authority in the places you read slowly
# (titles, section headings), while the sans stays legible at the small sizes
# and tight line-heights a dense form needs. An all-serif interface looks
# formal in a screenshot and becomes tiring to actually work in.
#
# Source Serif 4 and Source Sans 3 are a designed superfamily -- same origin,
# matched proportions and vertical metrics -- so they sit together without the
# mismatch you get from pairing two unrelated faces.

FONT_HEADING = (
    '"Source Serif 4", "Source Serif Pro", Georgia, "Times New Roman", serif'
)
FONT_BODY = (
    '"Source Sans 3", "Source Sans Pro", "Segoe UI", -apple-system, '
    "BlinkMacSystemFont, system-ui, sans-serif"
)
FONT_MONO = '"JetBrains Mono", "Cascadia Code", Consolas, monospace'

GOOGLE_FONTS = (
    "https://fonts.googleapis.com/css2"
    "?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700"
    "&family=Source+Sans+3:wght@400;500;600;700"
    "&display=swap"
)

SECTION_KEYS = (
    "basics",
    "summary",
    "experience",
    "projects",
    "education",
    "skills",
    "certifications",
    "awards",
    "import",
)


def _tints(*colours: str) -> dict[str, str]:
    """Map the nine section keys onto nine tint colours, in order."""
    return dict(zip(SECTION_KEYS, colours))


# --------------------------------------------------------------------------
# The palettes
# --------------------------------------------------------------------------
#
# Each theme defines a light and a dark variant that are designed together
# rather than one being derived from the other. Dark is never simply inverted:
# the accent lightens (a mid-tone violet that reads well on white is muddy on
# near-black), and the "paper" keeps a hint of the theme's warmth so the
# interface does not fall back to a flat grey.

THEMES: dict[str, dict[str, Any]] = {
    "slate": {
        "name": "Slate & Violet",
        "blurb": "Soft neutral greys, muted violet accent. The most understated of the four.",
        "light": {
            "bg": "#FAFAFC",
            "surface": "#FFFFFF",
            "surface_alt": "#F4F3F8",
            "primary": "#6A57C2",
            "primary_hover": "#5A48AD",
            "primary_soft": "#EBE7F9",
            "on_primary": "#FFFFFF",
            "text": "#1A1822",
            "text_muted": "#6A6778",
            "text_faint": "#9691A5",
            "border": "#E4E2EC",
            "border_strong": "#CFCCDC",
            "success": "#3F7D5C",
            "warning": "#9A6D25",
            "danger": "#B0475A",
            "tints": _tints(
                "#EFEBFA", "#E7EEF8", "#E7F2EA", "#FAEDE2",
                "#F2EAF8", "#E8F0F3", "#F8F1DC", "#FBE9EC", "#ECEDF8",
            ),
        },
        "dark": {
            "bg": "#131219",
            "surface": "#1B1A23",
            "surface_alt": "#22202C",
            "primary": "#A18DEC",
            "primary_hover": "#B4A4F2",
            "primary_soft": "#2C2740",
            "on_primary": "#15121F",
            "text": "#ECEAF4",
            "text_muted": "#9C98AC",
            "text_faint": "#6F6B80",
            "border": "#2C2A38",
            "border_strong": "#3D3A4C",
            "success": "#6FBF93",
            "warning": "#D8A75A",
            "danger": "#E28495",
            "tints": _tints(
                "#282243", "#1E2A38", "#1D3028", "#37281B",
                "#2D2340", "#1E2C31", "#332B18", "#3A2229", "#242639",
            ),
        },
    },
    "ivory": {
        "name": "Ivory & Bronze",
        "blurb": "Warm paper and bronze. The most editorial and formal -- reads like print.",
        "light": {
            "bg": "#FAF7F1",
            "surface": "#FFFDF9",
            "surface_alt": "#F3EEE4",
            "primary": "#8A5A24",
            "primary_hover": "#734A1C",
            "primary_soft": "#F3E7D5",
            "on_primary": "#FFFFFF",
            "text": "#1E1912",
            "text_muted": "#6B6154",
            "text_faint": "#9A8F7E",
            "border": "#E6DECF",
            "border_strong": "#D2C6B0",
            "success": "#4A7550",
            "warning": "#96631F",
            "danger": "#A94A42",
            "tints": _tints(
                "#F4EADA", "#EDEDE0", "#E6EDDF", "#F8E8D8",
                "#F1E8DE", "#E9EDEC", "#F9EFD3", "#F7E4DC", "#EFEAE0",
            ),
        },
        "dark": {
            "bg": "#151209",
            "surface": "#1E1A11",
            "surface_alt": "#262117",
            "primary": "#D9A85C",
            "primary_hover": "#E8BC79",
            "primary_soft": "#33291A",
            "on_primary": "#191307",
            "text": "#F1EADD",
            "text_muted": "#A99C86",
            "text_faint": "#7A6F5C",
            "border": "#2F2818",
            "border_strong": "#443A24",
            "success": "#7FB784",
            "warning": "#DFAB55",
            "danger": "#DE8478",
            "tints": _tints(
                "#332A18", "#2B2D1F", "#26301E", "#382A17",
                "#302819", "#222A28", "#3A3015", "#3A2A20", "#2D2A1E",
            ),
        },
    },
    "sage": {
        "name": "Sage & Stone",
        "blurb": "Cool off-white, deep green accent. Calm and clinical without feeling cold.",
        "light": {
            "bg": "#F7FAF8",
            "surface": "#FFFFFF",
            "surface_alt": "#EDF3EF",
            "primary": "#2C6A54",
            "primary_hover": "#225744",
            "primary_soft": "#DCEBE3",
            "on_primary": "#FFFFFF",
            "text": "#141E19",
            "text_muted": "#5B6C64",
            "text_faint": "#8B9C93",
            "border": "#DDE7E1",
            "border_strong": "#C3D2CA",
            "success": "#2F7355",
            "warning": "#8E6520",
            "danger": "#A94D4D",
            "tints": _tints(
                "#E4EFE8", "#E3EDF2", "#DFEDE3", "#F6EBDE",
                "#E9EAF3", "#E2EFEF", "#F6F0D9", "#F7E6E4", "#E8EFEB",
            ),
        },
        "dark": {
            "bg": "#0E1512",
            "surface": "#151E19",
            "surface_alt": "#1C2721",
            "primary": "#71C3A0",
            "primary_hover": "#8AD3B4",
            "primary_soft": "#1E3229",
            "on_primary": "#0C1712",
            "text": "#E7F0EA",
            "text_muted": "#94A79C",
            "text_faint": "#68796F",
            "border": "#243029",
            "border_strong": "#35453B",
            "success": "#74C79B",
            "warning": "#D3A65B",
            "danger": "#DD8582",
            "tints": _tints(
                "#1D3029", "#1B2C33", "#1B3227", "#33291C",
                "#252938", "#1C2F30", "#332C19", "#37262A", "#212C27",
            ),
        },
    },
    "harbour": {
        "name": "Harbour & Copper",
        "blurb": "Deep navy with a copper accent. The most corporate and highest contrast.",
        "light": {
            "bg": "#F7F9FB",
            "surface": "#FFFFFF",
            "surface_alt": "#EDF1F6",
            "primary": "#1F4470",
            "primary_hover": "#16355A",
            "primary_soft": "#DEE8F3",
            "on_primary": "#FFFFFF",
            "text": "#111823",
            "text_muted": "#57657A",
            "text_faint": "#8695A8",
            "border": "#DEE4EC",
            "border_strong": "#C2CCDA",
            "success": "#2F6E55",
            "warning": "#9A5F27",
            "danger": "#A8474F",
            "tints": _tints(
                "#E3EAF4", "#E2EDF3", "#E2EFE9", "#F8E9DC",
                "#EAE9F4", "#E4EEF2", "#F7EFD8", "#F8E6E6", "#E9EDF4",
            ),
        },
        "dark": {
            "bg": "#0D131B",
            "surface": "#141C26",
            "surface_alt": "#1B2530",
            "primary": "#78A6DC",
            "primary_hover": "#93BAE8",
            "primary_soft": "#1D2E42",
            "on_primary": "#0B1420",
            "text": "#E5EDF6",
            "text_muted": "#90A0B3",
            "text_faint": "#65758A",
            "border": "#223040",
            "border_strong": "#334458",
            "success": "#6EC099",
            "warning": "#D9A45F",
            "danger": "#E0868D",
            "tints": _tints(
                "#1C2E42", "#1B2C38", "#1C3129", "#36291C",
                "#26283D", "#1D2E35", "#342C1A", "#382429", "#212B3A",
            ),
        },
    },
}

DEFAULT_THEME = "sage"
DEFAULT_MODE = "light"


def theme_options() -> list[tuple[str, str, str]]:
    """``(key, name, blurb)`` for every theme, for a picker."""
    return [(key, spec["name"], spec["blurb"]) for key, spec in THEMES.items()]


def get_palette(theme_key: str = DEFAULT_THEME, mode: str = DEFAULT_MODE) -> dict[str, Any]:
    spec = THEMES.get(theme_key, THEMES[DEFAULT_THEME])
    return spec.get(mode, spec[DEFAULT_MODE])


# --------------------------------------------------------------------------
# CSS
# --------------------------------------------------------------------------


def _variables(palette: dict[str, Any]) -> str:
    # Palette keys are snake_case; the stylesheet spells every custom property
    # in kebab-case (--db-surface-alt, --db-text-muted, ...). Without this
    # swap those var() lookups resolve to nothing and the rule is dropped.
    lines = [
        f"--db-{name.replace('_', '-')}: {value};"
        for name, value in palette.items()
        if name != "tints"
    ]
    lines += [f"--db-tint-{key}: {value};" for key, value in palette["tints"].items()]
    lines.append(f"--db-font-heading: {FONT_HEADING};")
    lines.append(f"--db-font-body: {FONT_BODY};")
    lines.append(f"--db-font-mono: {FONT_MONO};")
    return "\n        ".join(lines)


def _density_css(density: str) -> str:
    """Extra rules for compact mode.

    Streamlit's own vertical rhythm is generous -- a gap between every element
    container, plus padding inside each widget. On a form this long that reads
    as a page with air in it rather than a tool. Compact pulls the gaps in and
    trims widget padding; nothing changes size, so nothing reflows oddly.
    """
    if density != "compact":
        return ""
    return """
    .block-container { padding-top: 1.35rem !important; }
    [data-testid="stMain"] [data-testid="stVerticalBlock"] { gap: .5rem !important; }
    [data-testid="stMain"] [data-testid="stElementContainer"] { margin-bottom: 0 !important; }
    .db-hero { padding: .6rem 1.15rem; margin-bottom: .8rem; }
    .db-hero h1 { font-size: 1.5rem; }
    .db-card { padding: .6rem .8rem !important; }
    .db-stat { padding: .5rem .7rem !important; }
    [data-testid="stTextInputRootElement"] input,
    [data-testid="stNumberInput"] input { padding-top: .2rem; padding-bottom: .2rem; }
    [data-testid="stTextArea"] textarea { padding-top: .3rem; padding-bottom: .3rem; }
    [data-testid="stWidgetLabel"] { margin-bottom: .05rem !important; }
    [role="tablist"] { margin-bottom: .35rem; }
    """


def _resume_css() -> str:
    """Everything the Resume page needs.

    A plain string, not an f-string: this is CSS with hundreds of braces in it
    and doubling every one of them to survive ``_css``'s formatting is how a
    stylesheet acquires silent typos. The only generated part is the accent
    swatch row, built with %-formatting for the same reason.
    """
    swatches = "\n".join(
        (
            ".st-key-db_accent_%s button, .st-key-db_accent_sel_%s button {"
            " background: %s !important; border-color: %s !important; }"
        )
        % (key, key, value, value)
        for key, (_name, value) in ACCENT_SWATCHES.items()
    )
    return (
        swatches
        + """
    /* ---- Template gallery --------------------------------------------- */

    [class*="st-key-db_tpl_"] {
        border: 1px solid var(--db-border);
        border-radius: 14px;
        padding: .5rem .5rem .65rem;
        background: var(--db-surface);
        transition: border-color .16s ease, box-shadow .16s ease, transform .16s ease;
    }
    [class*="st-key-db_tpl_"]:hover {
        border-color: var(--db-border-strong);
        transform: translateY(-2px);
        box-shadow: 0 10px 24px rgba(0, 0, 0, .09);
    }
    /* The selected card is keyed differently rather than marked by a class,
       because CSS cannot see which of four Streamlit containers is chosen. */
    [class*="st-key-db_tpl_sel_"] {
        border-color: var(--db-primary);
        box-shadow: 0 0 0 2px var(--db-primary-soft);
    }
    [class*="st-key-db_tpl_"] iframe {
        background: #FFFFFF;
        border: 1px solid var(--db-border);
        border-radius: 9px;
    }
    .db-tpl-meta { margin-top: .5rem; }
    .db-tpl-name {
        font-family: var(--db-font-heading);
        font-weight: 600;
        font-size: .98rem;
        color: var(--db-text);
        display: flex;
        align-items: center;
        gap: .4rem;
        flex-wrap: wrap;
    }
    .db-tpl-meta p {
        margin: .15rem 0 .5rem;
        font-size: .78rem;
        line-height: 1.35;
        color: var(--db-text-muted);
    }
    .db-badge {
        font-size: .64rem;
        font-weight: 700;
        letter-spacing: .05em;
        text-transform: uppercase;
        padding: .12rem .38rem;
        border-radius: 5px;
        background: var(--db-surface-alt);
        color: var(--db-text-muted);
        border: 1px solid var(--db-border);
        white-space: nowrap;
    }
    .db-badge.ok { color: var(--db-success); border-color: var(--db-success); }
    .db-badge.warn { color: var(--db-warning); border-color: var(--db-warning); }

    /* ---- Accent swatches ----------------------------------------------- */

    [class*="st-key-db_accent_"] button {
        height: 30px;
        min-height: 30px;
        padding: 0 !important;
        border-radius: 8px;
        border-width: 1px !important;
        transition: transform .14s ease, box-shadow .14s ease;
    }
    [class*="st-key-db_accent_"] button:hover { transform: translateY(-1px); }
    [class*="st-key-db_accent_sel_"] button {
        box-shadow: 0 0 0 2px var(--db-surface), 0 0 0 4px var(--db-primary);
    }

    /* ---- Section order list -------------------------------------------- */

    .db-sec-row {
        display: flex;
        align-items: center;
        gap: .4rem;
        font-size: .88rem;
        font-weight: 600;
        color: var(--db-text);
        padding-top: .45rem;
    }
    .db-sec-row.off { color: var(--db-text-faint); font-weight: 500; }
    [class*="st-key-db_up_"] button,
    [class*="st-key-db_down_"] button,
    [class*="st-key-db_eye_"] button {
        padding: .15rem !important;
        min-height: 32px;
    }

    /* ---- Preview pane --------------------------------------------------- */

    [class*="st-key-db_preview"] iframe {
        border: 1px solid var(--db-border);
        border-radius: 12px;
        background: var(--db-surface-alt);
    }

    /* ---- PDF report ----------------------------------------------------- */

    .db-pdfreport {
        border: 1px solid var(--db-border);
        border-left: 3px solid var(--db-primary);
        border-radius: 10px;
        background: var(--db-surface);
        padding: .55rem .8rem;
        margin-top: .6rem;
    }
    .db-pdfrow { font-size: .85rem; color: var(--db-text-muted); }
    .db-pdfrow b { color: var(--db-text); }
    .db-checks { margin-top: .3rem; display: flex; gap: .7rem; flex-wrap: wrap; }
    .db-check { font-size: .78rem; font-weight: 600; }
    .db-check.ok { color: var(--db-success); }
    .db-check.bad { color: var(--db-danger); }

    /* ---- Sidebar status strip ------------------------------------------- */

    .db-status {
        display: flex;
        align-items: center;
        gap: .4rem;
        font-size: .78rem;
        color: var(--db-text-muted);
        padding-top: .5rem;
    }
    .db-status .dot {
        width: 7px; height: 7px;
        border-radius: 50%;
        background: var(--db-text-faint);
        flex: none;
    }
    .db-status.unsaved .dot { background: var(--db-warning); }
    .db-status.ok .dot { background: var(--db-success); }
    .db-keys {
        font-size: .7rem;
        color: var(--db-text-faint);
        letter-spacing: .01em;
        margin-top: .15rem;
    }
    .db-keys kbd {
        font-family: var(--db-font-mono);
        font-size: .68rem;
        border: 1px solid var(--db-border);
        border-bottom-width: 2px;
        border-radius: 4px;
        padding: 0 .25rem;
        color: var(--db-text-muted);
    }

    /* ---- Clickable timeline --------------------------------------------- */

    [class*="st-key-db_tl_"] button {
        padding: 0 !important;
        min-height: 0 !important;
        text-align: left;
        justify-content: flex-start;
        font-size: .8rem !important;
        font-weight: 500 !important;
        color: var(--db-text) !important;
    }
    [class*="st-key-db_tl_"] button:hover { color: var(--db-primary) !important; }

    /* ---- Motion ---------------------------------------------------------- */
    /*
       Transitions only, plus one keyframe on the section panel. Streamlit
       rebuilds the DOM on every keystroke, so animating anything that reruns
       often would flicker constantly; a transition costs nothing when the
       value has not changed.
    */
    .db-card, .db-stat, .db-hit {
        transition: border-color .16s ease, box-shadow .16s ease, transform .16s ease;
    }
    .db-card:hover, .db-hit:hover {
        border-color: var(--db-border-strong);
        transform: translateY(-1px);
    }
    .db-meter-fill, .db-tl-bar { transition: width .25s ease; }
    @keyframes db-rise {
        from { opacity: 0; transform: translateY(4px); }
        to { opacity: 1; transform: none; }
    }
    [class*="st-key-db_section_panel"] { animation: db-rise .16s ease-out; }
    """
    )


def _css(palette: dict[str, Any], mode: str, density: str = "comfortable") -> str:
    scheme = "dark" if mode == "dark" else "light"
    logo_uri = logo_data_uri()
    density_rules = _density_css(density)
    resume_rules = _resume_css()
    return f"""
    <style>
    @import url('{GOOGLE_FONTS}');

    :root {{
        {_variables(palette)}
        color-scheme: {scheme};
    }}

    /* ---- Base ---------------------------------------------------------- */
    html, body, [class*="css"], .stApp, button, input, textarea, select {{
        font-family: var(--db-font-body);
    }}
    /* ``body`` and the main block both paint their own background from
       Streamlit's startup theme. Without them here, a dark palette leaves a
       light band behind everything else. */
    html, body,
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stMainBlockContainer"],
    [data-testid="stBottomBlockContainer"] {{
        background: var(--db-bg);
        color: var(--db-text);
    }}
    [data-testid="stHeader"] {{
        background: transparent;
        height: 0;
    }}
    .block-container {{
        padding-top: 2.2rem;
        padding-bottom: 5rem;
        max-width: 1120px;
    }}
    [data-testid="stMarkdownContainer"],
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li {{
        color: var(--db-text);
    }}

    h1, h2, h3, h4, h5 {{
        font-family: var(--db-font-heading);
        color: var(--db-text);
        letter-spacing: -0.012em;
        font-weight: 600;
    }}
    code, pre, [data-testid="stCode"] {{ font-family: var(--db-font-mono); }}
    pre, [data-testid="stCode"] > div {{
        background: var(--db-surface-alt) !important;
        border: 1px solid var(--db-border);
        border-radius: 10px;
    }}
    hr {{ border-color: var(--db-border); }}
    a {{ color: var(--db-primary); }}

    /* The Deploy button is meaningless for a local personal tool and is the
       loudest thing on the screen. Removed so the toolbar holds only what
       this app actually uses. */
    [data-testid="stAppDeployButton"] {{ display: none !important; }}
    [data-testid="stToolbar"] {{
        background: transparent;
        right: .6rem;
        top: .35rem;
    }}
    [data-testid="stToolbar"] svg,
    [data-testid="stMainMenu"] svg {{ color: var(--db-text-muted); fill: var(--db-text-muted); }}

    /* ---- Sidebar ------------------------------------------------------- */
    [data-testid="stSidebar"] {{
        background: var(--db-surface);
        border-right: 1px solid var(--db-border);
    }}
    /* Streamlit reserves a block of empty space at the top of the sidebar for
       its collapse control. Reclaiming it is what lets the wordmark sit at the
       very top of the panel instead of floating below a gap. */
    [data-testid="stSidebar"] > div:first-child {{ padding-top: 0; }}
    /* The header band holds nothing but the collapse control and a 32px
       spacer Streamlit reserves for an app logo we do not set. Dropping the
       spacer and shrinking the band is what closes the gap above the
       wordmark; the collapse button still has room. */
    [data-testid="stSidebarHeader"] {{
        position: relative;
        height: 0;
        min-height: 0;
        padding-top: 0;
        padding-bottom: 0;
        overflow: visible;
    }}
    [data-testid="stLogoSpacer"] {{ display: none !important; }}
    /* With the band collapsed the control has to be lifted out of the flow,
       or it would push the wordmark straight back down. */
    [data-testid="stSidebarCollapseButton"] {{
        position: absolute !important;
        right: 0;
        top: .3rem;
        z-index: 6;
    }}
    [data-testid="stSidebar"] .block-container,
    [data-testid="stSidebarUserContent"] {{
        padding-top: .3rem !important;
    }}
    [data-testid="stSidebarCollapseButton"],
    [data-testid="stSidebarCollapsedControl"] {{ top: .25rem; }}
    /* The collapse chevron takes its colour from Streamlit's startup theme,
       which is frozen light -- so it was a dark arrow on a dark panel. */
    [data-testid="stSidebarCollapseButton"] button,
    [data-testid="stSidebarCollapsedControl"] button {{
        background: transparent !important;
        color: var(--db-text-muted) !important;
    }}
    [data-testid="stSidebarCollapseButton"] svg,
    [data-testid="stSidebarCollapsedControl"] svg {{
        color: var(--db-text-muted) !important;
        fill: var(--db-text-muted) !important;
    }}
    /* Material icons are font glyphs in a span that carries its own colour,
       straight from the frozen startup theme -- which is why the collapse
       chevron stayed near-black on a dark panel. Making every icon inherit
       from its (themed) parent fixes the whole class of them at once. */
    [data-testid="stIconMaterial"] {{
        color: inherit !important;
        fill: currentColor !important;
    }}
    [data-testid="stSidebarCollapseButton"] [data-testid="stIconMaterial"],
    [data-testid="stSidebarCollapsedControl"] [data-testid="stIconMaterial"] {{
        color: var(--db-text-muted) !important;
    }}
    [data-testid="stSidebarCollapseButton"] button:hover {{
        background: var(--db-surface-alt) !important;
    }}
    [data-testid="stSidebarCollapseButton"] button:hover svg {{
        color: var(--db-primary) !important;
        fill: var(--db-primary) !important;
    }}

    /* The mark is a bitmap used as an alpha mask, not an <img>: the source
       art is black on white, and painting that into the panel would stamp a
       white box. As a mask its colour comes from background-color, so it can
       read var(--db-text) and follow the theme into dark mode. */
    .db-brand-row {{
        display: flex;
        align-items: center;
        gap: .55rem;
        margin: 0 0 .15rem 0;
    }}
    .db-brand-mark {{
        flex: 0 0 auto;
        width: 35px;
        height: 32px;
        background-color: var(--db-text);
        -webkit-mask-image: url("{logo_uri}");
        mask-image: url("{logo_uri}");
        -webkit-mask-repeat: no-repeat;
        mask-repeat: no-repeat;
        -webkit-mask-position: center;
        mask-position: center;
        -webkit-mask-size: contain;
        mask-size: contain;
    }}
    .db-brand {{
        display: block;
        margin: 0;
        font-family: var(--db-font-heading);
        font-size: 2.05rem;
        font-weight: 700;
        line-height: 1.08;
        letter-spacing: -0.028em;
        color: var(--db-text);
    }}
    .db-brand .db-brand-dot {{ color: var(--db-primary); }}
    .db-brand-sub {{
        display: block;
        margin: 0 0 .1rem 0;
        font-size: .78rem;
        font-weight: 500;
        letter-spacing: .085em;
        text-transform: uppercase;
        color: var(--db-text-faint);
    }}
    .db-rule {{
        height: 1px;
        background: var(--db-border);
        margin: 1.05rem 0;
        border: 0;
    }}

    /* ---- Sidebar navigation -------------------------------------------- */
    /* The section picker is a radio, but it is read as navigation, so it is
       dressed as one: tight rows, a hit area that spans the panel, and a
       tinted row for the current section. */
    /* The vertical block lays its children out with align-items:start, so the
       widget shrink-wraps its text. The rows have to be stretched from the
       element container down for the hit area to span the panel. */
    .st-key-db_nav [data-testid="stElementContainer"],
    .st-key-db_nav [data-testid="stRadio"],
    .st-key-db_nav [data-testid="stRadioGroup"] {{ width: 100%; }}
    .st-key-db_nav [data-testid="stRadioGroup"] {{ gap: .05rem; }}
    .st-key-db_nav [data-testid="stRadioOption"] {{
        width: 100%;
        padding: .3rem .5rem;
        border-radius: 9px;
        transition: background-color .12s ease;
    }}
    .st-key-db_nav [data-testid="stRadioOption"]:hover {{
        background: var(--db-surface-alt);
    }}
    .st-key-db_nav [data-testid="stRadioOption"]:has(input:checked) {{
        background: var(--db-surface-alt);
    }}
    .st-key-db_nav [data-testid="stRadioOption"]:has(input:checked) p {{
        font-weight: 600 !important;
    }}

    /* ---- Sidebar footer ------------------------------------------------- */
    /* Streamlit lays the panel out as a normal document flow, so the credit
       line would otherwise sit directly under the last widget. Stretching the
       block to the panel height and pushing the footer with margin-top:auto
       parks it at the bottom without taking it out of the flow -- it still
       gives way when the content is taller than the viewport. */
    [data-testid="stSidebarUserContent"] > div {{
        display: flex;
        min-height: calc(100vh - 7.3rem);
    }}
    [data-testid="stSidebarUserContent"] > div > [data-testid="stVerticalBlock"] {{
        flex: 1 1 auto;
    }}
    /* Streamlit wraps every keyed container in a layout wrapper, and it is
       the wrapper -- not the container -- that is the flex item, so the auto
       margin has to be aimed one level up. */
    [data-testid="stLayoutWrapper"]:has(> .st-key-db_sidebar_footer) {{
        margin-top: auto;
    }}
    .db-sidebar-footer {{
        border-top: 1px solid var(--db-border);
        padding-top: .7rem;
        margin: .4rem 0 0 0;
        font-size: .74rem;
        letter-spacing: .01em;
        color: var(--db-text-faint);
    }}
    .db-sidebar-footer strong,
    .db-sidebar-footer .db-credit {{
        display: block;
        font-weight: 600;
        color: var(--db-text-muted);
    }}
    .db-sidebar-footer .db-credit {{
        text-decoration: none;
        transition: color .12s ease;
    }}
    .db-sidebar-footer .db-credit:hover {{
        color: var(--db-primary);
        text-decoration: underline;
        text-underline-offset: 2px;
    }}

    /* ---- Hero ---------------------------------------------------------- */
    .db-hero {{
        background: linear-gradient(135deg, var(--db-tint-basics) 0%, var(--db-tint-summary) 100%);
        border: 1px solid var(--db-border);
        border-radius: 14px;
        padding: .85rem 1.35rem;
        margin-bottom: 1.15rem;
    }}
    .db-hero h1 {{
        margin: 0;
        font-size: 1.72rem;
        font-weight: 600;
        color: var(--db-text);
    }}
    /* Streamlit appends an anchor-link button to every heading it renders.
       On a banner heading it is decoration that links nowhere useful, and it
       flickers in on hover. */
    .db-hero h1 a,
    [data-testid="stHeaderActionElements"] {{ display: none !important; }}
    .db-hero p + p {{ margin-top: .3rem; }}
    .db-hero p {{
        margin: 0;
        color: var(--db-text-muted);
        font-size: .94rem;
        line-height: 1.55;
        max-width: 68ch;
    }}

    /* ---- Cards and labels ---------------------------------------------- */
    .db-card {{
        background: var(--db-surface);
        border: 1px solid var(--db-border);
        border-radius: 14px;
        padding: 1rem 1.2rem;
        margin-bottom: .85rem;
    }}
    .db-section-label {{
        display: flex;
        align-items: center;
        gap: .65rem;
        font-family: var(--db-font-heading);
        font-size: 1.18rem;
        font-weight: 600;
        color: var(--db-text);
        margin: .35rem 0 .3rem 0;
    }}
    /* An accent bar rather than a square: at 12px a filled square next to a
       label reads as an unchecked checkbox. */
    .db-accent-bar {{
        width: 3px;
        height: 1.1em;
        border-radius: 2px;
        background: var(--db-primary);
        display: inline-block;
        flex: 0 0 auto;
    }}
    .db-muted {{
        color: var(--db-text-muted);
        font-size: .87rem;
        line-height: 1.5;
        margin: .1rem 0 .55rem 0;
    }}
    .db-tag {{
        display: inline-block;
        padding: .16rem .58rem;
        border-radius: 999px;
        font-size: .72rem;
        font-weight: 600;
        letter-spacing: .02em;
        margin-right: .35rem;
        color: var(--db-text);
    }}

    /* ---- Stat strip ---------------------------------------------------- */
    .db-stat {{
        background: var(--db-surface);
        border: 1px solid var(--db-border);
        border-radius: 12px;
        padding: .7rem .9rem;
        text-align: left;
    }}
    .db-stat-value {{
        font-family: var(--db-font-heading);
        font-size: 1.5rem;
        font-weight: 600;
        line-height: 1.1;
        color: var(--db-text);
    }}
    .db-stat-label {{
        font-size: .72rem;
        letter-spacing: .07em;
        text-transform: uppercase;
        color: var(--db-text-faint);
        margin-top: .15rem;
    }}

    /* ---- Tabs ---------------------------------------------------------- */
    /* Streamlit renders tabs as [role="tablist"] / [data-testid="stTab"] --
       not the BaseWeb data attributes an older version used. */
    [role="tablist"] {{
        background: transparent !important;
        gap: 1.5rem !important;
        border-bottom: 1px solid var(--db-border);
    }}
    [data-testid="stTab"] {{ margin-right: .35rem; }}
    [data-testid="stTab"] {{
        background: transparent !important;
        color: var(--db-text-muted) !important;
        font-weight: 500;
    }}
    [data-testid="stTab"] p {{
        color: inherit !important;
        font-weight: 500;
    }}
    [data-testid="stTab"]:hover, [data-testid="stTab"]:hover p {{
        color: var(--db-text) !important;
    }}
    [data-testid="stTab"][aria-selected="true"],
    [data-testid="stTab"][aria-selected="true"] p {{
        color: var(--db-primary) !important;
    }}
    [data-baseweb="tab-highlight"] {{ background: var(--db-primary) !important; }}
    [data-baseweb="tab-border"] {{ background: var(--db-border) !important; }}
    .db-count {{
        display: inline-block;
        margin-left: .3rem;
        font-size: .74em;
        color: var(--db-text-faint);
    }}

    /* ---- Inputs -------------------------------------------------------- */
    /* The visible box is the *RootElement wrapper, not the <input>. Styling
       only the input leaves a light-coloured frame around a dark field. */
    [data-testid="stTextInputRootElement"],
    [data-testid="stTextAreaRootElement"],
    [data-testid="stNumberInputContainer"],
    [data-baseweb="select"] > div,
    [data-baseweb="input"] {{
        background: var(--db-surface) !important;
        border-color: var(--db-border) !important;
        border-radius: 9px !important;
    }}
    [data-testid="stTextInputField"],
    [data-testid="stTextArea"] textarea,
    [data-testid="stNumberInput"] input,
    [data-baseweb="select"] div {{
        background: transparent !important;
        color: var(--db-text) !important;
    }}
    /* This Streamlit build renders the select without the data-baseweb hook
       the rules above rely on, so the field kept the startup theme's white
       and read as a cream slab inside a dark menu. Anchored on the widget
       testid instead, which is stable. */
    [data-testid="stSelectbox"] > div > div {{
        background: var(--db-surface) !important;
        border-color: var(--db-border) !important;
        border-radius: 9px !important;
    }}
    [data-testid="stSelectbox"] > div > div div,
    [data-testid="stSelectbox"] > div > div input {{
        background: transparent !important;
        color: var(--db-text) !important;
    }}
    [data-testid="stSelectbox"] svg {{
        color: var(--db-text-muted) !important;
        fill: var(--db-text-muted) !important;
    }}
    [data-testid="stTextInputField"]::placeholder,
    [data-testid="stTextArea"] textarea::placeholder {{
        color: var(--db-text-faint) !important;
        opacity: 1;
    }}
    [data-testid="stTextInputRootElement"]:focus-within,
    [data-testid="stTextAreaRootElement"]:focus-within {{
        border-color: var(--db-primary) !important;
        box-shadow: 0 0 0 3px var(--db-primary-soft) !important;
    }}
    [data-testid="stWidgetLabel"] p,
    label p {{
        color: var(--db-text-muted) !important;
        font-size: .84rem !important;
        font-weight: 500;
    }}
    [data-baseweb="popover"] div,
    [data-baseweb="menu"] {{
        background: var(--db-surface) !important;
        color: var(--db-text) !important;
    }}
    [role="option"]:hover {{ background: var(--db-surface-alt) !important; }}

    /* ---- Buttons ------------------------------------------------------- */
    /* Matched by test id, not by ".stButton > button". A button given a
       ``help=`` tooltip is wrapped in a <span>, which breaks the direct-child
       selector -- that is why tooltip buttons stayed white while identical
       buttons without a tooltip picked up the theme. */
    [data-testid^="stBaseButton"] {{
        border-radius: 9px !important;
        border: 1px solid var(--db-border-strong) !important;
        background: var(--db-surface) !important;
        color: var(--db-text) !important;
        font-weight: 550;
        transition: border-color .12s ease, color .12s ease, background .12s ease;
    }}
    [data-testid^="stBaseButton"]:hover:not(:disabled) {{
        border-color: var(--db-primary) !important;
        color: var(--db-primary) !important;
    }}
    [data-testid="stBaseButton-primary"],
    [data-testid="stBaseButton-primaryFormSubmit"] {{
        background: var(--db-primary) !important;
        border-color: var(--db-primary) !important;
        color: var(--db-on-primary) !important;
    }}
    [data-testid="stBaseButton-primary"]:hover:not(:disabled) {{
        background: var(--db-primary-hover) !important;
        border-color: var(--db-primary-hover) !important;
        color: var(--db-on-primary) !important;
    }}
    [data-testid^="stBaseButton"]:disabled {{
        opacity: .5;
        color: var(--db-text-faint) !important;
    }}
    [data-testid^="stBaseButton"] p {{ color: inherit !important; font-weight: 550; }}

    /* ---- Expanders ----------------------------------------------------- */
    [data-testid="stExpander"] {{
        border: 1px solid var(--db-border);
        border-radius: 12px;
        background: var(--db-surface);
        margin-bottom: .6rem;
        overflow: hidden;
    }}
    [data-testid="stExpander"] summary {{
        padding: .7rem .95rem;
        font-weight: 550;
        color: var(--db-text);
        background: var(--db-surface) !important;
    }}
    [data-testid="stExpander"] summary p {{ color: var(--db-text) !important; }}
    [data-testid="stExpander"] [data-testid="stExpanderDetails"] {{
        background: var(--db-surface);
    }}
    [data-testid="stExpander"] summary:hover {{ color: var(--db-primary); }}
    [data-testid="stExpander"] svg {{ fill: var(--db-text-muted); }}

    /* ---- Alerts, metrics, uploader ------------------------------------- */
    [data-testid="stAlert"] {{
        border-radius: 11px;
        border: 1px solid var(--db-border);
        background: var(--db-surface-alt);
        color: var(--db-text);
    }}
    /* The painted element is stAlertContainer, and Streamlit fills it with a
       fixed severity wash -- a yellow at 10% for warnings -- then sets a dark
       mustard text colour on top. Over a dark panel that is mud. The wash is
       replaced with the panel's own surface and the severity moves to a left
       rule, which carries the same meaning and stays legible in both modes. */
    [data-testid="stAlertContainer"] {{
        background: var(--db-surface-alt) !important;
        border-radius: 11px !important;
        border-left: 3px solid var(--db-border-strong) !important;
    }}
    [data-testid="stAlert"] p,
    [data-testid="stAlert"] li,
    [data-testid="stAlert"] code,
    [data-testid="stAlertContainer"] {{ color: var(--db-text) !important; }}
    [data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) {{
        border-left-color: var(--db-warning) !important;
    }}
    [data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {{
        border-left-color: var(--db-danger) !important;
    }}
    [data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) {{
        border-left-color: var(--db-primary) !important;
    }}
    [data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) {{
        border-left-color: var(--db-text-faint) !important;
    }}
    [data-testid="stAlert"] code {{
        background: var(--db-surface) !important;
        border: 1px solid var(--db-border);
        border-radius: 5px;
        padding: 0 .25rem;
    }}
    [data-testid="stMetric"] {{
        background: var(--db-surface);
        border: 1px solid var(--db-border);
        border-radius: 12px;
        padding: .8rem 1rem;
    }}
    [data-testid="stMetricValue"] {{
        color: var(--db-text);
        font-family: var(--db-font-heading);
    }}
    [data-testid="stMetricLabel"] p {{ color: var(--db-text-muted) !important; }}
    [data-testid="stFileUploaderDropzone"] {{
        background: var(--db-surface-alt);
        border: 1px dashed var(--db-border-strong);
        border-radius: 12px;
        color: var(--db-text-muted);
    }}
    [data-testid="stFileUploaderDropzone"] small,
    [data-testid="stFileUploaderDropzone"] span {{ color: var(--db-text-muted) !important; }}
    /* The bar fill, the selected radio dot and the tab underline are painted
       by Streamlit from config.toml's primaryColor, which is fixed at startup.
       Each is re-pointed at the live accent so non-default themes do not show
       a stray violet. Note the track rule is written with two attribute
       selectors so it outranks the fill rule above it. */
    [data-testid="stProgressBarTrack"] > div {{
        background: var(--db-primary) !important;
    }}
    [data-testid="stProgress"] [data-testid="stProgressBarTrack"] {{
        background: var(--db-surface-alt) !important;
    }}
    /* Only the outer circle of the *checked* option is Streamlit's
       primaryColor. The descendant selector has to stop there: the inner dot
       and the option's stMarkdownContainer are also nested divs, so a loose
       "div div div" repainted the dot into invisibility and washed the label
       text with the accent. */
    [data-testid="stRadioOption"]:has(input:checked)
        > div > div > div:first-child:not([data-testid]) {{
        background-color: var(--db-primary) !important;
    }}
    /* The unchecked ring and the dot well come from config.toml's text and
       secondary-background colours, so they are frozen at the light palette
       and show up as pale discs in dark mode. Same re-point as above. */
    [data-testid="stRadioOption"]:not(:has(input:checked))
        > div > div > div:first-child:not([data-testid]) {{
        background-color: var(--db-border-strong) !important;
    }}
    [data-testid="stRadioOption"]
        > div > div > div:first-child:not([data-testid]) > div {{
        background-color: var(--db-surface) !important;
    }}
    [data-testid="stTab"] .react-aria-SelectionIndicator,
    [role="tablist"] .react-aria-SelectionIndicator {{
        background: var(--db-primary) !important;
    }}

    /* Radio and checkbox text */
    [data-testid="stRadio"] label p,
    [data-testid="stCheckbox"] label p {{
        color: var(--db-text) !important;
        font-size: .89rem !important;
        line-height: 1.35 !important;
    }}
    /* Toggles and checkboxes share the stCheckbox testid, and both paint
       their "on" state from Streamlit's startup theme -- so a bronze palette
       still produced a green switch. The checked colour is right for either
       control; the third rule reaches a toggle's knob, which is a div, and
       misses a checkbox's tick, which is an svg. */
    [data-testid="stCheckbox"] label > span > div:first-of-type {{
        background: var(--db-border-strong) !important;
    }}
    [data-testid="stCheckbox"] label > span:has(input:checked) > div:first-of-type {{
        background: var(--db-primary) !important;
    }}
    [data-testid="stCheckbox"] label > span > div:first-of-type > div {{
        background: var(--db-surface) !important;
    }}

    /* Stacked options sit flush against each other by default, which reads as
       one block of text next to a column of dots. */
    [data-testid="stRadioGroup"] {{ gap: .28rem; }}
    [data-testid="stRadioOption"] [data-testid="stMarkdownContainer"] {{
        background: transparent;
    }}

    /* ---- Strength meters ------------------------------------------------ */
    .db-meters {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
        gap: .7rem;
        margin: 0 0 .3rem 0;
    }}
    .db-meter {{
        background: var(--db-surface);
        border: 1px solid var(--db-border);
        border-radius: 12px;
        padding: .62rem .8rem .7rem .8rem;
    }}
    .db-meter-head {{
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        font-size: .74rem;
        font-weight: 600;
        letter-spacing: .075em;
        text-transform: uppercase;
        color: var(--db-text-faint);
    }}
    .db-meter-pct {{
        font-family: var(--db-font-heading);
        font-size: 1.18rem;
        font-weight: 600;
        letter-spacing: -0.01em;
        color: var(--db-text);
        text-transform: none;
    }}
    .db-meter-track {{
        height: 5px;
        border-radius: 3px;
        background: var(--db-surface-alt);
        border: 1px solid var(--db-border);
        margin: .42rem 0 .35rem 0;
        overflow: hidden;
    }}
    .db-meter-track span {{
        display: block;
        height: 100%;
        background: var(--db-primary);
        transition: width .35s ease;
    }}
    .db-meter-detail {{
        font-size: .74rem;
        color: var(--db-text-muted);
    }}

    /* ---- Timeline -------------------------------------------------------- */
    .db-timeline {{
        background: var(--db-surface);
        border: 1px solid var(--db-border);
        border-radius: 12px;
        padding: .75rem .9rem .6rem .9rem;
    }}
    .db-tl-row {{
        display: flex;
        align-items: center;
        gap: .7rem;
        padding: .12rem 0;
    }}
    .db-tl-label {{
        flex: 0 0 210px;
        font-size: .78rem;
        color: var(--db-text);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }}
    .db-tl-track {{
        position: relative;
        flex: 1 1 auto;
        height: 15px;
        border-radius: 4px;
    }}
    .db-tl-bar {{
        position: absolute;
        top: 4px;
        height: 7px;
        /* A three-week project is a real entry, and at this scale its true
           width is two pixels. The minimum keeps it a bar rather than a
           speck; the date beside it carries the precision. */
        min-width: 12px;
        border-radius: 4px;
        background: var(--db-primary);
    }}
    /* Three kinds on one axis need to stay apart without a colour each --
       a second hue would fight the accent. Weight does the work instead. */
    .db-tl-bar.education {{ opacity: .55; }}
    .db-tl-bar.projects {{ opacity: .78; }}
    .db-tl-bar.ongoing {{
        border-top-right-radius: 0;
        border-bottom-right-radius: 0;
    }}
    .db-tl-dates {{
        flex: 0 0 148px;
        text-align: right;
        font-size: .72rem;
        color: var(--db-text-faint);
        white-space: nowrap;
    }}
    .db-tl-axis {{
        margin-top: .2rem;
        border-top: 1px solid var(--db-border);
        padding-top: .28rem;
    }}
    .db-tl-axis .db-tl-track {{ height: 13px; }}
    .db-tl-tick {{
        position: absolute;
        /* Centred on the year it marks. Left-aligned, every label sat half
           its own width to the right of the position it was labelling, which
           is what made the bars look like they disagreed with the axis. */
        transform: translateX(-50%);
        top: 0;
        transform: translateX(-50%);
        font-size: .68rem;
        color: var(--db-text-faint);
    }}
    /* The legend dot belongs beside its label, not above it: Streamlit puts
       every element on its own row, so the dot's container is lifted out of
       the flow and pinned to the left of the button. */
    [class*="st-key-db_tl_"] {{ position: relative; padding-left: 14px; }}
    [class*="st-key-db_tl_"] [data-testid="stElementContainer"]:has(.db-tl-dot) {{
        position: absolute;
        left: 0;
        top: .48rem;
    }}
    [class*="st-key-db_tl_"] .db-tl-dot {{
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: var(--db-primary);
    }}
    [class*="st-key-db_tl_education"] .db-tl-dot {{ opacity: .55; }}
    [class*="st-key-db_tl_projects"] .db-tl-dot {{ opacity: .78; }}

    /* ---- Search results --------------------------------------------------- */
    .db-hit {{
        border-left: 2px solid var(--db-border-strong);
        padding: .12rem 0 .12rem .65rem;
        margin: .35rem 0;
    }}
    .db-hit-where {{
        font-size: .71rem;
        letter-spacing: .04em;
        text-transform: uppercase;
        color: var(--db-text-faint);
    }}
    .db-hit-text {{
        font-size: .87rem;
        color: var(--db-text);
        line-height: 1.45;
    }}
    .db-hit mark {{
        background: var(--db-primary-soft);
        color: var(--db-text);
        border-radius: 3px;
        padding: 0 .1rem;
    }}

    /* ---- First-run guidance ---------------------------------------------- */
    .db-empty {{
        background: var(--db-surface);
        border: 1px dashed var(--db-border-strong);
        border-radius: 14px;
        padding: 1.1rem 1.3rem;
    }}
    .db-empty h3 {{
        margin: 0 0 .3rem 0;
        font-size: 1.05rem;
        font-family: var(--db-font-heading);
        color: var(--db-text);
    }}
    .db-empty p {{
        margin: 0 0 .15rem 0;
        font-size: .87rem;
        color: var(--db-text-muted);
        line-height: 1.5;
    }}
    .db-empty ol {{
        margin: .45rem 0 0 1.1rem;
        padding: 0;
        font-size: .87rem;
        color: var(--db-text-muted);
        line-height: 1.65;
    }}

    /* ---- Quality findings ---------------------------------------------- */
    .db-finding {{
        font-size: .81rem;
        padding: .1rem 0;
        line-height: 1.45;
    }}
    .db-finding.error {{ color: var(--db-danger); }}
    .db-finding.warning {{ color: var(--db-warning); }}
    .db-finding.note {{ color: var(--db-text-faint); }}

    /* ---- Appearance menu, pinned into the top-right toolbar ------------- */
    /* A popover rather than a bare button: theme and light/dark are one
       decision, so they belong behind one control instead of competing for
       space in the sidebar. Fixed-positioned to sit beside Streamlit's own
       menu, which is a closed component and cannot take custom items. */
    .st-key-db_appearance {{
        position: fixed;
        top: .3rem;
        right: 3.2rem;
        z-index: 1000000;
        width: auto;
    }}
    .st-key-db_appearance [data-testid="stPopoverButton"] {{
        border: 1px solid var(--db-border) !important;
        background: var(--db-surface) !important;
        color: var(--db-text-muted) !important;
        border-radius: 9px !important;
        padding: .2rem .7rem;
        font-size: .8rem;
        min-height: 0;
        line-height: 1.6;
    }}
    .st-key-db_appearance [data-testid="stPopoverButton"]:hover {{
        color: var(--db-primary) !important;
        border-color: var(--db-primary) !important;
    }}
    /* The icon ships with the Material font Streamlit already loads, so it
       stays sharp at every zoom level and needs no asset of its own. */
    .st-key-db_appearance [data-testid="stIconMaterial"] {{
        font-size: 1.05rem;
        margin-right: .1rem;
    }}
    [data-testid="stPopoverBody"] {{
        background: var(--db-surface) !important;
        border: 1px solid var(--db-border) !important;
        border-radius: 12px !important;
    }}
    /* Streamlit renders a segmented control as stButtonGroup. Its halves are
       painted from the startup theme, so the unselected one arrived as near
       white with near black text -- unreadable inside a dark menu. The inner
       label div carries its own colour, hence the descendant reset. */
    [data-testid="stButtonGroup"] button {{
        background: var(--db-surface-alt) !important;
        border-color: var(--db-border) !important;
    }}
    [data-testid="stButtonGroup"] button,
    [data-testid="stButtonGroup"] button * {{
        color: var(--db-text-muted) !important;
    }}
    [data-testid="stButtonGroup"] button:hover,
    [data-testid="stButtonGroup"] button:hover * {{ color: var(--db-text) !important; }}
    [data-testid="stButtonGroup"] button[aria-checked="true"] {{
        background: var(--db-primary-soft) !important;
        border-color: var(--db-primary) !important;
    }}
    [data-testid="stButtonGroup"] button[aria-checked="true"],
    [data-testid="stButtonGroup"] button[aria-checked="true"] * {{
        color: var(--db-primary) !important;
    }}
    .db-menu-label {{
        margin: 0 0 .3rem 0;
        font-size: .7rem;
        font-weight: 600;
        letter-spacing: .085em;
        text-transform: uppercase;
        color: var(--db-text-faint);
    }}

    /* ---- Section progress, riding the tab row --------------------------- */
    /* Rendered as a zero-height block immediately before the tabs, then
       lifted onto the tab row. It cannot be a child of the tab strip --
       Streamlit owns that subtree -- so it is layered over the free space to
       the right of the last tab. */
    .st-key-db_tab_progress {{
        position: relative;
        height: 0;
        z-index: 3;
    }}
    /* Section pills: a navigation row, so they sit flush left with a rule
       under them, the way the tab strip they replace did. Scoped to their own
       container because Streamlit gives pills the same stButtonGroup testid as
       the segmented controls in the Appearance menu. */
    .st-key-db_sections {{
        border-bottom: 1px solid var(--db-border);
        padding-bottom: .45rem;
        margin-bottom: .55rem;
    }}
    .st-key-db_sections [data-testid="stButtonGroup"] button {{
        background: transparent !important;
        border: 1px solid transparent !important;
        border-radius: 8px !important;
        padding: .16rem .58rem !important;
    }}
    .st-key-db_sections [data-testid="stButtonGroup"] button,
    .st-key-db_sections [data-testid="stButtonGroup"] button * {{
        color: var(--db-text-muted) !important;
        font-weight: 500 !important;
    }}
    .st-key-db_sections [data-testid="stButtonGroup"] button:hover {{
        background: var(--db-surface-alt) !important;
    }}
    .st-key-db_sections [data-testid="stButtonGroup"] button:hover,
    .st-key-db_sections [data-testid="stButtonGroup"] button:hover * {{
        color: var(--db-text) !important;
    }}
    .st-key-db_sections [data-testid="stButtonGroup"] button[aria-checked="true"] {{
        background: var(--db-primary-soft) !important;
        border-color: var(--db-primary) !important;
    }}
    .st-key-db_sections [data-testid="stButtonGroup"] button[aria-checked="true"],
    .st-key-db_sections [data-testid="stButtonGroup"] button[aria-checked="true"] * {{
        color: var(--db-primary) !important;
        font-weight: 600 !important;
    }}

    .db-tabprogress {{
        position: absolute;
        right: 0;
        top: 1.65rem;
        display: flex;
        align-items: center;
        gap: .55rem;
        pointer-events: none;
    }}
    .db-tabprogress-track {{
        display: flex;
        gap: 3px;
    }}
    .db-tabprogress-seg {{
        width: 16px;
        height: 5px;
        border-radius: 3px;
        background: var(--db-border-strong);
        transition: background-color .18s ease;
    }}
    .db-tabprogress-seg.filled {{ background: var(--db-primary); }}
    /* The section being edited is marked so the strip reads as a position as
       well as a total. */
    .db-tabprogress-seg.active {{
        box-shadow: 0 0 0 2px var(--db-primary-soft);
        background: var(--db-primary);
    }}
    .db-tabprogress-count {{
        font-size: .74rem;
        font-weight: 600;
        letter-spacing: .02em;
        color: var(--db-text-muted);
        white-space: nowrap;
    }}

    /* Tooltips are portalled to the body and painted from the startup theme,
       so they arrived as a near-white card in dark mode. */
    [data-testid="stTooltipContent"] {{
        background: var(--db-surface) !important;
        border: 1px solid var(--db-border) !important;
        border-radius: 9px !important;
        box-shadow: 0 6px 22px rgba(0, 0, 0, .18);
    }}
    [data-testid="stTooltipContent"],
    [data-testid="stTooltipContent"] * {{ color: var(--db-text) !important; }}
    [data-testid="stTooltipIcon"],
    [data-testid="stTooltipIcon"] svg {{
        color: var(--db-text-faint) !important;
        fill: var(--db-text-faint) !important;
    }}

    /* Dim the tiny "Press Enter to apply" hints -- with one widget per bullet
       they otherwise repeat down the whole page. */
    [data-testid="InputInstructions"] {{ display: none; }}

    /* ---- The Resume page ----------------------------------------------- */
    {resume_rules}

    /* ---- Density ------------------------------------------------------- */
    {density_rules}
    </style>
    """


# --------------------------------------------------------------------------
# Public helpers
# --------------------------------------------------------------------------


def apply_theme(
    theme_key: str = DEFAULT_THEME,
    mode: str = DEFAULT_MODE,
    density: str = "comfortable",
) -> dict[str, Any]:
    """Inject the stylesheet for one theme/mode/density. Call once, early."""
    palette = get_palette(theme_key, mode)
    st.markdown(_css(palette, mode, density), unsafe_allow_html=True)
    return palette


def brand(title: str = "Dossierbuild", subtitle: str = "Resume workspace") -> None:
    """The sidebar lockup: mark, wordmark, and the line above them.

    The mark is an empty span rather than an image -- it is painted by the
    stylesheet through a CSS mask so it inherits the theme's text colour. See
    ``dossier.ui.assets`` for why.
    """
    st.markdown(
        f'<span class="db-brand-sub">{subtitle}</span>'
        f'<div class="db-brand-row">'
        f'<span class="db-brand-mark" role="img" aria-label="{title}"></span>'
        f'<span class="db-brand">{title}<span class="db-brand-dot">.</span></span>'
        f"</div>",
        unsafe_allow_html=True,
    )


def sidebar_footer(name: str, url: str = "") -> None:
    """The credit line parked at the bottom of the sidebar.

    ``target="_blank"`` because this is the one link in the workspace that
    leads off it -- losing an unsaved session to a navigation would be a poor
    trade for a profile visit.
    """
    who = (
        f'<a class="db-credit" href="{url}" target="_blank" rel="noopener noreferrer">{name}</a>'
        if url
        else f"<strong>{name}</strong>"
    )
    st.markdown(
        f'<div class="db-sidebar-footer">Built by {who}</div>',
        unsafe_allow_html=True,
    )


def tab_progress(
    done: int,
    total: int,
    filled: list[bool],
    missing: list[str],
    active: int | None = None,
) -> None:
    """A segment per section, filled once that section holds anything.

    One segment per tab rather than a single sliding bar: the tabs are not a
    sequence you walk once, they are eight independent things to fill in, and
    a segmented read says which of them are still empty at a glance.
    """
    segments = "".join(
        f'<span class="db-tabprogress-seg{" filled" if ok else ""}'
        f'{" active" if i == active else ""}"></span>'
        for i, ok in enumerate(filled)
    )
    hint = f"Still empty: {', '.join(missing)}" if missing else "Every section has content"
    st.markdown(
        f'<div class="db-tabprogress" title="{hint}">'
        f'<span class="db-tabprogress-track">{segments}</span>'
        f'<span class="db-tabprogress-count">{done}/{total} sections</span>'
        f"</div>",
        unsafe_allow_html=True,
    )


def rule() -> None:
    st.markdown('<hr class="db-rule">', unsafe_allow_html=True)


def hero(title: str, subtitle: str | None = None) -> None:
    """The page banner. ``subtitle`` is optional -- omit it for a bare title."""
    body = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(
        f'<div class="db-hero"><h1>{title}</h1>{body}</div>',
        unsafe_allow_html=True,
    )


def section_label(text: str, section_key: str = "") -> None:
    st.markdown(
        f'<div class="db-section-label"><span class="db-accent-bar"></span>{text}</div>',
        unsafe_allow_html=True,
    )


def tag(text: str, section_key: str) -> str:
    return (
        f'<span class="db-tag" style="background:var(--db-tint-{section_key})">{text}</span>'
    )


def muted(text: str) -> None:
    st.markdown(f'<p class="db-muted">{text}</p>', unsafe_allow_html=True)


def stat(value: str | int, label: str) -> None:
    st.markdown(
        f'<div class="db-stat"><div class="db-stat-value">{value}</div>'
        f'<div class="db-stat-label">{label}</div></div>',
        unsafe_allow_html=True,
    )


def status(kind: str, text: str) -> None:
    """One line saying where the profile stands: a dot and a sentence.

    Replaces the stack of a disabled button, a caption and a checkbox that all
    said the same thing in three different shapes.
    """
    st.markdown(
        f'<div class="db-status {kind}"><span class="dot"></span>{text}</div>',
        unsafe_allow_html=True,
    )


def keys_hint() -> None:
    st.markdown(
        '<div class="db-keys"><kbd>Ctrl</kbd>+<kbd>S</kbd> save · '
        "<kbd>Ctrl</kbd>+<kbd>Z</kbd> undo · <kbd>/</kbd> search</div>",
        unsafe_allow_html=True,
    )


def shortcuts() -> None:
    """Keyboard shortcuts, driven from a zero-height component.

    Streamlit has no key-event API, so the listener has to be installed on the
    parent document from inside a component iframe. Two details make it
    survive reruns: the previous handler is removed by a reference kept on the
    parent document (its own iframe is gone by then, so it can be removed but
    never called), and every shortcut is resolved by finding the real button
    and clicking it -- which keeps Streamlit's own state machine in charge.
    """
    components.html(
        """
<script>
(function () {
  var doc = window.parent.document;
  if (doc.__dbKeyHandler) {
    doc.removeEventListener('keydown', doc.__dbKeyHandler, true);
  }
  function typing(el) {
    return el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable);
  }
  function clickText(label) {
    var buttons = doc.querySelectorAll('button');
    for (var i = 0; i < buttons.length; i++) {
      if ((buttons[i].innerText || '').trim() === label && !buttons[i].disabled) {
        buttons[i].click();
        return true;
      }
    }
    return false;
  }
  function clickKeyed(key) {
    var el = doc.querySelector('[class*="st-key-' + key + '"] button');
    if (el && !el.disabled) { el.click(); return true; }
    return false;
  }
  var handler = function (e) {
    var k = (e.key || '').toLowerCase();
    var mod = e.ctrlKey || e.metaKey;
    if (mod && k === 's') {
      e.preventDefault();
      clickText('Save changes');
    } else if (mod && k === 'z' && !typing(doc.activeElement)) {
      e.preventDefault();
      clickKeyed('db_undo');
    } else if (k === '/' && !typing(doc.activeElement)) {
      var input = doc.querySelector('[class*="st-key-db_search"] input');
      if (input) { e.preventDefault(); input.focus(); }
    }
  };
  doc.addEventListener('keydown', handler, true);
  doc.__dbKeyHandler = handler;
})();
</script>
""",
        height=0,
    )
