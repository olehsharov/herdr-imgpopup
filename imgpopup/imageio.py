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


def encode_tiles(img: Image.Image, view: Tuple[int, int, int, int],
                 cols: int, rows: int, col: int, row: int, k: int,
                 max_bytes: int = MAX_PNG_BYTES,
                 cell_px: int = CELL_PX_TARGET,
                 sink: Optional[Callable[["Tile"], None]] = None) -> List[Tile]:
    """Split the placement (cols x rows cells at col,row) into k x k
    cell-aligned tiles and encode the matching slice of `view` for each.

    Cell spans and source spans use the same fractions, so tiles meet exactly.
    Each tile except the last column/row is extended by ONE cell to the right
    and bottom and given a higher z than its left/top neighbours: the client
    leaves a ~1 px gap at a placement's edge, and this puts every such gap
    underneath the next tile instead of on screen.
    `sink`, if given, is called with each tile from the worker thread as soon
    as it is encoded - sending from there overlaps the ~1 ms/KB transport to
    the client across tiles (measured: 4 tiles 2.13 s sequential, 0.56 s
    concurrent). Exceptions from `sink` propagate out of this call.
    """
    vx, vy, vw, vh = view
    xs = split_cells(cols, k)
    ys = split_cells(rows, k)
    jobs = []
    for ty, (r0, rn) in enumerate(ys):
        for tx, (c0, cn) in enumerate(xs):
            cn_ext = cn + (1 if tx < len(xs) - 1 else 0)
            rn_ext = rn + (1 if ty < len(ys) - 1 else 0)
            sx0 = vx + vw * c0 / cols
            sx1 = vx + vw * (c0 + cn_ext) / cols
            sy0 = vy + vh * r0 / rows
            sy1 = vy + vh * (r0 + rn_ext) / rows
            box = (int(round(sx0)), int(round(sy0)),
                   max(int(round(sx0)) + 1, int(round(sx1))),
                   max(int(round(sy0)) + 1, int(round(sy1))))
            z = ty * len(xs) + tx
            jobs.append(("img-%d" % z, box, cn_ext, rn_ext, col + c0, row + r0, z))

    def work(job):
        layer, box, cn, rn, c, r, z = job
        tile = img.crop(box)
        max_w = max(MIN_SIDE, cn * cell_px)
        if tile.width > max_w:
            tile = tile.resize((max_w, max(1, round(tile.height * max_w / tile.width))),
                               Image.LANCZOS)
        data, tile = shrink_to_budget(tile, max_bytes)
        out = Tile(layer, data, tile.width, tile.height, cn, rn, c, r, z)
        if sink is not None:
            sink(out)
        return out

    with ThreadPoolExecutor(max_workers=ENCODE_THREADS) as pool:
        return list(pool.map(work, jobs))
