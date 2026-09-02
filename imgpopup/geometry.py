"""Cell arithmetic for placing an image in a pane.

Herdr places images in CELLS, not pixels, so every size here is a cell count.
CELL_RATIO is cell width divided by cell height - about 0.5 for typical
terminal fonts - and converts an image's pixel aspect into a cell aspect.
"""
from typing import Tuple

CELL_RATIO = 0.5


def fit(img_w: int, img_h: int, pane_cols: int, pane_rows: int,
        cell_ratio: float = CELL_RATIO) -> Tuple[int, int]:
    """Largest (cols, rows) preserving aspect ratio that fits the pane."""
    if img_w <= 0 or img_h <= 0:
        raise ValueError("image dimensions must be positive")
    cols = max(1, pane_cols)
    rows = max(1, round(cols * (img_h / img_w) * cell_ratio))
    if rows > pane_rows:
        rows = max(1, pane_rows)
        cols = max(1, round(rows * (img_w / img_h) / cell_ratio))
    return cols, rows


def clamp_zoom(zoom: float, lo: float = 0.1, hi: float = 8.0) -> float:
    return max(lo, min(hi, zoom))


def clamp_pan(size: int, pane_size: int, offset: int) -> int:
    """Keep the image overlapping the pane on one axis.

    Smaller than the pane: offset is pinned to 0..(pane_size - size).
    Larger than the pane: offset ranges (pane_size - size)..0, i.e. scrolling.
    """
    lo = min(0, pane_size - size)
    hi = max(0, pane_size - size)
    return max(lo, min(hi, offset))


def popup_size(img_w: int, img_h: int, term_cols: int, term_rows: int,
               cell_ratio: float = CELL_RATIO, cap: float = 0.9) -> Tuple[str, str]:
    """Popup width/height as percent strings, shaped like the image."""
    if img_w <= 0 or img_h <= 0:
        raise ValueError("image dimensions must be positive")
    cols, rows = fit(img_w, img_h,
                     max(1, int(term_cols * cap)), max(1, int(term_rows * cap)),
                     cell_ratio)
    pct_w = min(int(cap * 100), max(1, round(100 * (cols + 2) / max(1, term_cols))))
    pct_h = min(int(cap * 100), max(1, round(100 * (rows + 2) / max(1, term_rows))))
    return "%d%%" % pct_w, "%d%%" % pct_h


def encode_cap(img_w: int, img_h: int, popup_px_w: int,
               factor: int = 4) -> Tuple[int, int]:
    """Cap the encoded size so a repaint stays small. Never upscales."""
    target = max(1, popup_px_w * factor)
    if img_w <= target:
        return img_w, img_h
    return target, max(1, round(img_h * target / img_w))
