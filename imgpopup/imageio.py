"""Load an image from disk and hand back PNG bytes small enough to send.

Herdr enforces TWO limits on pane.graphics.set, both measured 2026-09-03:
  * the image data itself: a PNG of 524,288 bytes (512 KiB) is accepted,
    524,289 answers image_too_large - this is the binding one;
  * the API request line: over ~1,048,250 bytes and the connection is dropped
    with no reply ("api request line is too large" in the server log).
Base64 inflates 512 KiB to ~700 KB, safely under the line limit, so budgeting
the raw PNG at 512 KiB satisfies both. A pixel cap alone is not enough: a photo
compresses far worse than a logo.
"""
import io
from typing import Tuple

from PIL import Image

MAX_PNG_BYTES = 512 * 1024      # inclusive; 512 KiB + 1 is rejected
MIN_SIDE = 16


def _has_alpha(img: Image.Image) -> bool:
    return img.mode in ("RGBA", "LA", "PA") or (
        img.mode == "P" and "transparency" in img.info)


def _encode(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def load_png(path: str, max_px_w: int,
             max_bytes: int = MAX_PNG_BYTES) -> Tuple[bytes, int, int]:
    """Return (png_bytes, width, height): at most max_px_w wide, at most
    max_bytes long, never upscaled. Opaque images encode as RGB; transparent
    ones keep their alpha."""
    img = Image.open(path)
    img.load()
    img = img.convert("RGBA" if _has_alpha(img) else "RGB")

    if img.width > max_px_w:
        height = max(MIN_SIDE, round(img.height * max_px_w / img.width))
        img = img.resize((max_px_w, height), Image.LANCZOS)

    data = _encode(img)
    while len(data) > max_bytes and min(img.size) > MIN_SIDE:
        # PNG size scales roughly with pixel count, so shrink each side by
        # sqrt(ratio), with a margin so this converges in one or two passes.
        scale = (max_bytes / len(data)) ** 0.5 * 0.9
        size = (max(MIN_SIDE, int(img.width * scale)),
                max(MIN_SIDE, int(img.height * scale)))
        img = img.resize(size, Image.LANCZOS)
        data = _encode(img)
    return data, img.width, img.height
