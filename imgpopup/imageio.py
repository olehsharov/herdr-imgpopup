"""Load an image and encode the visible region as PNG tiles small enough to send.

Herdr enforces TWO limits on pane.graphics.set, both measured 2026-09-03:
  * the image data itself: a PNG of 524,288 bytes (512 KiB) is accepted,
    524,289 answers image_too_large - this is the binding one;
  * the API request line: over ~1,048,250 bytes and the connection is dropped
    with no reply ("api request line is too large" in the server log).
The only accepted formats are png / rgb / rgba / bgra, so PNG is the best on
offer and 512 KiB is per LAYER. The way past it is more layers: the visible
region is split into a k x k grid of cell-aligned tiles, each its own PNG
under budget, giving k^2 x the pixels per view.
"""
import io
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from PIL import Image

from .geometry import split_cells

MAX_PNG_BYTES = 512 * 1024      # inclusive; 512 KiB + 1 is rejected
MIN_SIDE = 16
CELL_PX_TARGET = 16             # source pixels per cell worth encoding (retina-ish)
ENCODE_THREADS = 8      # encode AND send overlap per tile; the send is the slow part


@dataclass
class Tile:
    layer: str
    png: bytes
    width: int
    height: int
    cols: int
    rows: int
    col: int
    row: int
    z: int = 0


def _has_alpha(img: Image.Image) -> bool:
    return img.mode in ("RGBA", "LA", "PA") or (
        img.mode == "P" and "transparency" in img.info)


def _encode(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", compress_level=6)
    return buf.getvalue()


def open_image(path: str) -> Image.Image:
    """Decode once. Opaque images become RGB (smaller PNG), others keep alpha."""
    img = Image.open(path)
    img.load()
    return img.convert("RGBA" if _has_alpha(img) else "RGB")


def shrink_to_budget(img: Image.Image, max_bytes: int) -> Tuple[bytes, Image.Image]:
    """Encode; while too big, shrink each side by sqrt(ratio) and retry."""
    data = _encode(img)
    while len(data) > max_bytes and min(img.size) > MIN_SIDE:
        scale = (max_bytes / len(data)) ** 0.5 * 0.9
        size = (max(MIN_SIDE, int(img.width * scale)),
                max(MIN_SIDE, int(img.height * scale)))
        img = img.resize(size, Image.LANCZOS)
        data = _encode(img)
    return data, img


def load_png(path: str, max_px_w: int,
             max_bytes: int = MAX_PNG_BYTES) -> Tuple[bytes, int, int]:
    """Whole image as one PNG: at most max_px_w wide, at most max_bytes."""
    img = open_image(path)
    if img.width > max_px_w:
        height = max(MIN_SIDE, round(img.height * max_px_w / img.width))
        img = img.resize((max_px_w, height), Image.LANCZOS)
    data, img = shrink_to_budget(img, max_bytes)
    return data, img.width, img.height


TILE_PX_TARGET = 300_000        # output pixels per tile before the byte budget bites


def out_px_per_col(view_w: float, cols: int, rows: int, k: int,
                   cell_w: int, cell_h: int, px_per_tile: int = TILE_PX_TARGET) -> float:
    """Output pixels per column, ONE value for every tile: never above the
    source resolution, never above the screen's, and sized so the whole view
    is about k^2 * px_per_tile pixels."""
    source = view_w / cols
    screen = float(cell_w)
    budget = (k * k * px_per_tile * cell_w / (cols * rows * cell_h)) ** 0.5
    return max(0.5, min(source, screen, budget))


def _plan(view, cols, rows, k, cell_w, cell_h, ppc):
    """Cell spans, exact float source boxes and output sizes for k x k tiles.
    Each tile but the last column/row extends one cell into its right/bottom
    neighbour and gets a higher z, hiding the client's ~1 px placement edge."""
    vx, vy, vw, vh = view
    xs = split_cells(cols, k)
    ys = split_cells(rows, k)
    ppr = ppc * cell_h / cell_w
    jobs = []
    for ty, (r0, rn) in enumerate(ys):
        for tx, (c0, cn) in enumerate(xs):
            cn_e = cn + (1 if tx < len(xs) - 1 else 0)
            rn_e = rn + (1 if ty < len(ys) - 1 else 0)
            box = (vx + vw * c0 / cols, vy + vh * r0 / rows,
                   vx + vw * (c0 + cn_e) / cols, vy + vh * (r0 + rn_e) / rows)
            size = (max(1, round(cn_e * ppc)), max(1, round(rn_e * ppr)))
            z = ty * len(xs) + tx
            jobs.append(("img-%d" % z, box, size, cn_e, rn_e, c0, r0, z))
    return jobs


def _clamp_box(box, img_w, img_h):
    x0, y0, x1, y1 = box
    x0, y0 = min(max(0.0, x0), img_w - 1.0), min(max(0.0, y0), img_h - 1.0)
    x1, y1 = min(max(x0 + 1e-3, x1), float(img_w)), min(max(y0 + 1e-3, y1), float(img_h))
    return x0, y0, x1, y1


def encode_tiles(img: Image.Image, view: Tuple[float, float, float, float],
                 cols: int, rows: int, col: int, row: int, k: int,
                 cell_w: int, cell_h: int,
                 max_bytes: int = MAX_PNG_BYTES,
                 px_per_tile: int = TILE_PX_TARGET,
                 sink: Optional[Callable[["Tile"], None]] = None) -> List[Tile]:
    """Encode the visible region as k x k cell-aligned PNG tiles.

    Every tile is resampled from an EXACT float source box with the SAME
    scale, so neighbours are continuous to sub-pixel precision at any zoom.
    If any tile exceeds max_bytes, all tiles are re-encoded at one smaller
    scale (uniformity matters more than the odd second pass).
    `sink` is called from the worker as soon as a tile under budget is
    encoded; a second pass re-sends every tile.
    """
    ppc = out_px_per_col(view[2], cols, rows, k, cell_w, cell_h, px_per_tile)
    for _attempt in range(5):
        jobs = _plan(view, cols, rows, k, cell_w, cell_h, ppc)

        def work(job):
            layer, box, size, cn, rn, c0, r0, z = job
            tile = img.resize(size, Image.LANCZOS, box=_clamp_box(box, img.width, img.height))
            data = _encode(tile)
            out = Tile(layer, data, tile.width, tile.height, cn, rn, col + c0, row + r0, z)
            if sink is not None and len(data) <= max_bytes:
                sink(out)
            return out

        with ThreadPoolExecutor(max_workers=ENCODE_THREADS) as pool:
            tiles = list(pool.map(work, jobs))
        worst = max(len(t.png) for t in tiles)
        if worst <= max_bytes:
            return tiles
        ppc *= (max_bytes / worst) ** 0.5 * 0.9
    raise ValueError("tiles will not fit under %d bytes" % max_bytes)
