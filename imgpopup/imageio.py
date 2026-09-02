"""Load an image from disk and hand back PNG bytes small enough to repaint fast."""
import io
from typing import Tuple

from PIL import Image


def load_png(path: str, max_px_w: int) -> Tuple[bytes, int, int]:
    """Return (png_bytes, width, height), downscaled to max_px_w. Never upscales."""
    img = Image.open(path)
    img = img.convert("RGBA")
    if img.width > max_px_w:
        height = max(1, round(img.height * max_px_w / img.width))
        img = img.resize((max_px_w, height), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue(), img.width, img.height
