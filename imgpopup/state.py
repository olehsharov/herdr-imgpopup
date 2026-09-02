"""What the popup is showing, and how input changes it. No I/O lives here.

The view is a SOURCE RECTANGLE over the original image (zoom + centre) whose
aspect ratio is EXACTLY that of the placement box in client pixels, so the
client never letterboxes and every tile is scaled by the same factor.
"""
from typing import Dict, Tuple

from . import geometry as g

ZOOM_STEP = 1.25
ZOOM_MIN, ZOOM_MAX = 1.0, 32.0
PAN_FRACTION = 0.1            # of the visible width/height per keypress
STATUS_ROWS = 1               # bottom row is the status line

QUIT_KEYS = ("q", "escape", "\x03")
ZOOM_IN_KEYS = ("+", "=", "zoom_in")
ZOOM_OUT_KEYS = ("-", "_", "zoom_out")
RESET_KEYS = ("0", "f")
PAN_KEYS: Dict[str, Tuple[int, int]] = {
    "h": (-1, 0), "left": (-1, 0), "l": (1, 0), "right": (1, 0),
    "k": (0, -1), "up": (0, -1), "j": (0, 1), "down": (0, 1),
}


class ViewerState:
    """Zoom and pan over one image inside a pane of a known cell size."""

    def __init__(self, img_w: int, img_h: int, pane_cols: int, pane_rows: int,
                 cell_w: int = 8, cell_h: int = 16):
        self.img_w = img_w
        self.img_h = img_h
        self.pane_cols = pane_cols
        self.pane_rows = pane_rows
        self.cell_w = cell_w
        self.cell_h = cell_h
        self.zoom = 1.0
        self.cx = img_w / 2.0
        self.cy = img_h / 2.0

    # ---- configuration -----------------------------------------------------

    @property
    def cell_ratio(self) -> float:
        return self.cell_w / self.cell_h

    def load(self, img_w: int, img_h: int) -> None:
        """Show a different image; the view resets."""
        self.img_w = img_w
        self.img_h = img_h
        self.reset()

    def resize(self, pane_cols: int, pane_rows: int) -> None:
        self.pane_cols = pane_cols
        self.pane_rows = pane_rows

    def set_cell_size(self, cell_w: int, cell_h: int) -> None:
        self.cell_w = max(1, cell_w)
        self.cell_h = max(1, cell_h)

    def reset(self) -> None:
        self.zoom = 1.0
        self.cx = self.img_w / 2.0
        self.cy = self.img_h / 2.0

    # ---- geometry ----------------------------------------------------------

    def placement(self) -> Tuple[int, int, int, int]:
        """(cols, rows, col, row): the fit rectangle, centred above the status row."""
        rows_avail = max(1, self.pane_rows - STATUS_ROWS)
        cols, rows = g.fit(self.img_w, self.img_h, self.pane_cols, rows_avail, self.cell_ratio)
        col = max(0, (self.pane_cols - cols) // 2)
        row = max(0, (rows_avail - rows) // 2)
        return cols, rows, col, row

    def aspect(self) -> float:
        """Placement box aspect in client pixels: what the view must match."""
        cols, rows, _, _ = self.placement()
        return (cols * self.cell_w) / (rows * self.cell_h)

    def _base_view(self) -> Tuple[float, float]:
        """Largest rect of the placement aspect that fits inside the image."""
        a = self.aspect()
        if self.img_w / self.img_h >= a:
            h = float(self.img_h)
            return h * a, h
        w = float(self.img_w)
        return w, w / a

    def view_rect(self) -> Tuple[float, float, float, float]:
        """(x, y, w, h) in source pixels, floats: the region currently shown."""
        w0, h0 = self._base_view()
        w, h = w0 / self.zoom, h0 / self.zoom
        self.cx = min(max(self.cx, w / 2.0), self.img_w - w / 2.0)
        self.cy = min(max(self.cy, h / 2.0), self.img_h - h / 2.0)
        return self.cx - w / 2.0, self.cy - h / 2.0, w, h

    # ---- mutations ---------------------------------------------------------

    def zoom_at(self, factor: float, fx: float = 0.5, fy: float = 0.5) -> bool:
        """Zoom keeping the source point at view fraction (fx, fy) fixed.
        Returns False when the zoom did not change (already at a limit)."""
        x, y, w, h = self.view_rect()
        px, py = x + fx * w, y + fy * h
        new = g.clamp_zoom(self.zoom * factor, ZOOM_MIN, ZOOM_MAX)
        if new == self.zoom:
            return False
        self.zoom = new
        w0, h0 = self._base_view()
        w2, h2 = w0 / new, h0 / new
        self.cx = px - (fx - 0.5) * w2
        self.cy = py - (fy - 0.5) * h2
        self.view_rect()
        return True

    def pan(self, dx_frac: float, dy_frac: float) -> None:
        _, _, w, h = self.view_rect()
        self.cx += dx_frac * w
        self.cy += dy_frac * h

    def drag(self, dcols: int, drows: int) -> None:
        """Pointer dragged by (dcols, drows) cells: the image follows it."""
        cols, rows, _, _ = self.placement()
        _, _, w, h = self.view_rect()
        self.cx -= dcols * (w / cols)
        self.cy -= drows * (h / rows)

    def handle(self, key: str) -> str:
        """Apply a named key. Returns 'quit', 'redraw' or 'ignore'."""
        if key in QUIT_KEYS:
            return "quit"
        if key in ZOOM_IN_KEYS:
            return "redraw" if self.zoom_at(ZOOM_STEP) else "ignore"
        if key in ZOOM_OUT_KEYS:
            return "redraw" if self.zoom_at(1 / ZOOM_STEP) else "ignore"
        if key in RESET_KEYS:
            self.reset()
            return "redraw"
        if key in PAN_KEYS:
            if self.zoom == 1.0:
                return "ignore"
            dx, dy = PAN_KEYS[key]
            self.pan(dx * PAN_FRACTION, dy * PAN_FRACTION)
            return "redraw"
        return "ignore"
