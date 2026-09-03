"""The brand mark, prepared for two very different jobs.

The source file is a black glyph on an opaque white square. Neither job can
use it as-is:

* In the sidebar the mark has to sit on the panel background and follow the
  theme -- near-black on a light palette, near-white on a dark one. Painting a
  white-backed bitmap there would stamp a white box into the panel. So the
  glyph is reduced to an **alpha mask** (ink becomes opacity, paper becomes
  transparent) and handed to CSS ``mask-image``. The colour then comes from
  ``background-color``, which means it can read ``var(--db-text)`` and change
  with the theme for free.

* The browser tab is outside our stylesheet, so nothing there can adapt. A
  bare black glyph vanishes on a dark tab strip. The favicon is therefore
  drawn as a proper product icon: the mark knocked out of a rounded square
  filled with the active accent, which stays legible on light and dark tabs
  alike.

Both are derived from the same file at startup and cached, so there is one
asset to replace if the logo ever changes.
"""

from __future__ import annotations

import base64
import functools
import io
from pathlib import Path

from PIL import Image, ImageDraw

LOGO_PATH = Path(__file__).resolve().parents[2] / "logo.png"

# How much of the favicon's square the glyph is allowed to occupy. Icons read
# better with air around them; filling the square edge to edge looks cramped
# at 16px.
_FAVICON_INSET = 0.22
_FAVICON_SIZE = 256


def _load_mask() -> Image.Image:
    """The glyph as an alpha mask: ink opaque, paper transparent, trimmed.

    The source is flattened onto white first so that a file saved either with
    or without transparency lands in the same place, then inverted -- dark
    pixels become high alpha. Trimming to the ink's bounding box means layout
    can position the mark by its actual edges rather than by whatever margin
    the exported file happened to carry.
    """
    src = Image.open(LOGO_PATH)
    if src.mode in ("RGBA", "LA", "P"):
        src = src.convert("RGBA")
        paper = Image.new("RGBA", src.size, (255, 255, 255, 255))
        src = Image.alpha_composite(paper, src)
    ink = src.convert("L").point(lambda v: 255 - v)
    mask = Image.new("RGBA", ink.size, (0, 0, 0, 0))
    mask.putalpha(ink)
    box = mask.getbbox()
    return mask.crop(box) if box else mask


@functools.lru_cache(maxsize=1)
def logo_data_uri() -> str:
    """The trimmed mask as a data URI, for CSS ``mask-image``.

    Inlined rather than served as a file because Streamlit has no static route
    that CSS can reach reliably across versions, and the asset is small.
    """
    mask = _load_mask()
    buf = io.BytesIO()
    mask.save(buf, format="PNG", optimize=True)
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


@functools.lru_cache(maxsize=8)
def favicon(tile: str = "#2C6A54", ink: str = "#FFFFFF") -> Image.Image:
    """The mark drawn in ``ink`` on a rounded square of ``tile``.

    Two callers with opposite needs: the browser tab wants the accent tile
    with the mark knocked out white, while the desktop icon wants the logo as
    drawn -- black on paper. Both are the same shapes, so they are one
    function with the two colours exposed.

    Returned as a PIL image because that is what ``st.set_page_config`` takes
    directly; keying the cache on the colours means switching theme produces a
    matching tab icon without redrawing on every rerun.
    """
    size = _FAVICON_SIZE
    icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(icon).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=int(size * 0.22), fill=tile
    )

    mask = _load_mask()
    inset = int(size * _FAVICON_INSET)
    box = size - 2 * inset
    scale = min(box / mask.width, box / mask.height)
    glyph = mask.resize(
        (max(1, round(mask.width * scale)), max(1, round(mask.height * scale))),
        Image.LANCZOS,
    )

    # Paint the chosen ink through the glyph's alpha. On the accent tile that
    # is white, so the mark is knocked out rather than printed -- the original
    # black would disappear against a dark accent.
    layer = Image.new("RGBA", glyph.size, ink)
    icon.paste(
        layer,
        ((size - glyph.width) // 2, (size - glyph.height) // 2),
        glyph,
    )
    return icon
