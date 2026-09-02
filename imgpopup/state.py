"""What the popup is showing, and how keys change it. No I/O lives here.

The view is a SOURCE RECTANGLE over the original image (zoom + centre), not a
stretched placement: every redraw re-encodes only the visible region, so
zooming in yields more pixels, not the same pixels larger.
"""
from typing import Tuple

from . import geometry as g

ZOOM_STEP = 1.25
ZOOM_MIN, ZOOM_MAX = 1.0, 32.0
PAN_FRACTION = 0.1            # of the visible width/height per keypress
STATUS_ROWS = 1               # bottom row is the status line

QUIT_KEYS = ("q", "\x1b", "\x03")
ZOOM_IN_KEYS = ("+", "=")
ZOOM_OUT_KEYS = ("-", "_")


class ViewerState:
    """Zoom and pan over one image inside a pane of a known cell size."""

    def __init__(self, img_w: int, img_h: int, pane_cols: int, pane_rows: int):
        self.img_w = img_w
        self.img_h = img_h
        self.pane_cols = pane_cols
        self.pane_rows = pane_rows
        self.zoom = 1.0
        self.cx = img_w / 2.0
        self.cy = img_h / 2.0

    def load(self, img_w: int, img_h: int) -> None:
        """Show a different image; the view resets."""
        self.img_w = img_w
        self.img_h = img_h
        self.reset()

    def resize(self, pane_cols: int, pane_rows: int) -> None:
        self.pane_cols = pane_cols
        self.pane_rows = pane_rows

    def reset(self) -> None:
        self.zoom = 1.0
        self.cx = self.img_w / 2.0
        self.cy = self.img_h / 2.0

    def view_rect(self) -> Tuple[int, int, int, int]:
        """(x, y, w, h) in source pixels: the region currently shown."""
        w = max(1, round(self.img_w / self.zoom))
        h = max(1, round(self.img_h / self.zoom))
        self.cx = min(max(self.cx, w / 2.0), self.img_w - w / 2.0)
        self.cy = min(max(self.cy, h / 2.0), self.img_h - h / 2.0)
        x = min(max(0, int(round(self.cx - w / 2.0))), self.img_w - w)
        y = min(max(0, int(round(self.cy - h / 2.0))), self.img_h - h)
        return x, y, w, h

    def placement(self) -> Tuple[int, int, int, int]:
        """(cols, rows, col, row): the fit rectangle, centred in the pane."""
        rows_avail = max(1, self.pane_rows - STATUS_ROWS)
        cols, rows = g.fit(self.img_w, self.img_h, self.pane_cols, rows_avail)
        col = max(0, (self.pane_cols - cols) // 2)
        row = max(0, (rows_avail - rows) // 2)
        return cols, rows, col, row

    def handle(self, key: str) -> str:
        """Apply a keystroke. Returns 'quit', 'redraw' or 'ignore'."""
        if key in QUIT_KEYS:
            return "quit"
        if key in ZOOM_IN_KEYS:
            self.zoom = g.clamp_zoom(self.zoom * ZOOM_STEP, ZOOM_MIN, ZOOM_MAX)
        elif key in ZOOM_OUT_KEYS:
            self.zoom = g.clamp_zoom(self.zoom / ZOOM_STEP, ZOOM_MIN, ZOOM_MAX)
        elif key in ("0", "f"):
            self.reset()
        elif key in ("h", "l", "k", "j"):
            _, _, w, h = self.view_rect()
            if key == "h":
                self.cx -= w * PAN_FRACTION
            elif key == "l":
                self.cx += w * PAN_FRACTION
            elif key == "k":
                self.cy -= h * PAN_FRACTION
            else:
                self.cy += h * PAN_FRACTION
        else:
            return "ignore"
        return "redraw"
