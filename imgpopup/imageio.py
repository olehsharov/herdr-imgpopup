"""Load an image from disk and hand back PNG bytes small enough to send.

Herdr's API socket rejects any request line over 1 MiB (measured 2026-09-03:
1,048,250 bytes) by silently dropping the connection - the viewer sees a
BrokenPipe and the pane stays empty. Base64 inflates by 4/3 and the JSON
envelope adds a few hundred bytes, so the PNG itself must stay under ~700 KB.
A pixel cap alone is not enough: a photo compresses far worse than a logo.
"""
import io
from typing import Tuple

from PIL import Image

MAX_PNG_BYTES = 700_000
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
