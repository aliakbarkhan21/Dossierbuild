"""Jinja2: profile + design -> one self-contained HTML document.

Why HTML at all, rather than a PDF library like ReportLab: a resume is a
*layout* problem -- flowing text, keeping a heading with what it introduces,
two columns that stay level, a rule that spans the measure. Browsers have
spent thirty years on exactly that, and Chromium's print engine is the same
code that lays out the preview. Drawing the same page with ReportLab means
re-implementing line breaking, hyphenation and page-break avoidance by hand,
and then maintaining a second implementation for the on-screen preview that
inevitably disagrees with the first.

The document is self-contained: one file, styles inlined, no local assets. It
can be opened in a browser, mailed, or handed to Chromium unchanged.
"""

from __future__ import annotations

import functools
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from ..core.schema import Profile
from .context import ResumeContext, build_context, trim
from .design import MONO_STACK, Design, mm_to_px

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

# Type sizes are in points because the output is paper. 10.5pt body is the
# size a resume is actually set at: 11pt runs long, 10pt starts to feel like
# fine print in a photocopy.
BASE_PT = 10.5

# The portrait embedded in a gallery thumbnail. 112px across a 9mm frame is
# still sharper than the screen can show.
THUMB_PHOTO_PX = 112


@functools.lru_cache(maxsize=1)
def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(default=True, default_for_string=True),
        # Profile text is user data going into markup, so escaping is on
        # everywhere. StrictUndefined turns a template typo into an error at
        # render time rather than a silently blank line on the printed page.
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _variables(
    design: Design,
    *,
    preview: bool,
    zoom: float,
    breaks: bool,
    fitbar: bool,
    desk_pad: int,
    desk_bg: str,
) -> dict:
    page = design.page_spec
    base_pt = round(BASE_PT * design.scale / 100, 2)
    return {
        "page": page,
        "margin_mm": design.margin_mm,
        "accent": design.accent_hex,
        "fonts": design.pairing,
        "mono": MONO_STACK,
        "base_pt": base_pt,
        "leading": design.leading_value,
        # The space between sections tracks the type size, so scaling the
        # document up does not leave the sections looking crammed together.
        "section_gap": round(base_pt * 1.18, 2),
        "skill_label_col": "24mm",
        "preview": preview,
        "template_key": design.template,
        "page_height_px": round(mm_to_px(page.height_mm), 2),
        "page_width_px": round(mm_to_px(page.width_mm), 2),
        "margin_px": round(mm_to_px(design.margin_mm), 2),
        # One line of body text in CSS pixels, which is what turns "38px of
        # overflow" into "about two lines over" -- the only form of that fact
        # anyone can act on.
        "line_px": round(base_pt * 96 / 72 * design.leading_value, 2),
        "zoom": zoom,
        "breaks": breaks,
        "fitbar": fitbar,
        "desk_pad": desk_pad,
        "desk_bg": desk_bg,
        "design": design,
    }


def render_html(
    profile: Profile,
    design: Design,
    *,
    preview: bool = False,
    zoom: float = 0.0,
    breaks: bool = True,
    fitbar: bool = True,
    desk_pad: int = 16,
    desk_bg: str = "#EDEDF1",
    context: ResumeContext | None = None,
) -> str:
    """The whole document as a string.

    ``preview`` adds the grey desk, the white sheet, the page-break rules and
    the fit readout; without it the markup is exactly what Chromium should
    print. ``zoom`` of 0 means "fit the width available", anything else is a
    literal scale.
    """
    resume = context if context is not None else build_context(profile, design)
    template = _env().get_template(design.template_spec.file)
    return template.render(
        r=resume,
        **_variables(
            design,
            preview=preview,
            zoom=zoom,
            breaks=breaks,
            fitbar=fitbar,
            desk_pad=desk_pad,
            desk_bg=desk_bg,
        ),
    )


def render_thumbnail(profile: Profile, design: Design, template_key: str, zoom: float) -> str:
    """The top of one page in one template, small.

    The gallery shows the user's own material rather than a stock thumbnail:
    a layout only tells you anything once your own name and your own longest
    job title are in it.
    """
    variant = design.model_copy(update={"template": template_key})
    # A small portrait and a capped context: eight of these render on every
    # interaction, and at this size neither is distinguishable from the full
    # thing.
    context = trim(build_context(profile, variant, photo_size=THUMB_PHOTO_PX))
    return render_html(
        profile,
        variant,
        preview=True,
        zoom=zoom,
        breaks=False,
        fitbar=False,
        desk_pad=0,
        desk_bg="transparent",
        context=context,
    )
