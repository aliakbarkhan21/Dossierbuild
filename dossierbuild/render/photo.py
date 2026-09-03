"""The portrait: stored once, embedded on demand.

Three decisions worth stating, because each has a failure mode behind it.

**Stored as a file, referenced by name.** ``profile.json`` is hand-editable and
copied to a backup on every save; a base64 portrait would put a quarter of a
megabyte of noise through both. The schema holds the file name.

**Normalised on the way in, not on the way out.** A phone camera hands over a
4000x3000 JPEG. Every render would then embed four megabytes, and the PDF
would carry it too. It is cropped square and resized once, at upload, to a
size that still looks sharp at 300dpi in a 30mm frame.

**Embedded as a data URI, never linked.** The rendered HTML is handed to
Chromium as a temporary file and to the user as a download; a ``file://``
reference to ``data/photo.jpg`` would resolve in neither.
"""

from __future__ import annotations

import base64
import functools
import io
from pathlib import Path

from PIL import Image, ImageOps

from ..storage import DATA_DIR

PHOTO_NAME = "photo.jpg"
# 512px across a 30mm frame is a shade over 430dpi -- past the point print
# resolves, and small enough that the embedded copy stays around 40KB.
STORED_PX = 512
JPEG_QUALITY = 88
MAX_UPLOAD_BYTES = 12 * 1024 * 1024


class PhotoError(ValueError):
    """The file was not a usable image, with a sentence saying why."""


def photo_path(filename: str) -> Path | None:
    """Resolve a stored name to a real file, refusing anything outside data/."""
    name = (filename or "").strip()
    if not name:
        return None
    # The name comes out of a JSON file a person can edit, so it is treated as
    # untrusted: a bare file name inside data/, never a path.
    if "/" in name or "\\" in name or name.startswith("."):
        return None
    path = DATA_DIR / name
    return path if path.exists() else None


def save_photo(data: bytes) -> str:
    """Normalise an uploaded image and store it. Returns the file name."""
    if len(data) > MAX_UPLOAD_BYTES:
        raise PhotoError("That image is over 12MB. Try a smaller one.")
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except Exception as exc:  # noqa: BLE001 -- any decode failure reads the same
        raise PhotoError("That file could not be read as an image.") from exc

    # Phone photos carry their orientation in EXIF rather than in the pixels;
    # without this a portrait shot arrives on its side.
    image = ImageOps.exif_transpose(image)
    image = ImageOps.fit(
        image.convert("RGB"), (STORED_PX, STORED_PX), method=Image.LANCZOS, centering=(0.5, 0.35)
    )
    # Centred horizontally but weighted towards the top: on a portrait, the
    # middle of the frame is a chest, and the face is above it.

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / PHOTO_NAME
    image.save(path, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    _data_uri.cache_clear()
    return PHOTO_NAME


def remove_photo(filename: str) -> None:
    path = photo_path(filename)
    if path is not None:
        path.unlink(missing_ok=True)
    _data_uri.cache_clear()


@functools.lru_cache(maxsize=8)
def _data_uri(path: str, mtime: float, size: int) -> str:
    """Cached on the file's modification time, so a replaced photo is picked up."""
    image = Image.open(path)
    if size and size < image.width:
        image = image.resize((size, size), Image.LANCZOS)
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def photo_data_uri(filename: str, size: int = STORED_PX) -> str:
    """The stored portrait as an embeddable URI, or "" if there is none.

    ``size`` exists for the template gallery: eight thumbnails embedding a
    full-size portrait each would add a few megabytes to every rerun, and at
    9mm across nobody can tell.
    """
    path = photo_path(filename)
    if path is None:
        return ""
    try:
        return _data_uri(str(path), path.stat().st_mtime, size)
    except Exception:  # noqa: BLE001 -- a corrupt file should not stop a render
        return ""
