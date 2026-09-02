"""What the popup is showing, and how keys change it. No I/O lives here."""
from typing import Tuple

from . import geometry as g

ZOOM_STEP = 1.25
PAN_COLS = 2
PAN_ROWS = 1

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
        self.pan_x = 0
        self.pan_y = 0
        self.one_to_one = False

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
        self.pan_x = 0
        self.pan_y = 0
        self.one_to_one = False

    def placement(self) -> Tuple[int, int, int, int]:
        """(cols, rows, viewport_col, viewport_row) for pane.graphics.set."""
        base_cols, base_rows = g.fit(self.img_w, self.img_h,
                                     self.pane_cols, self.pane_rows)
        cols = max(1, int(round(base_cols * self.zoom)))
        rows = max(1, int(round(base_rows * self.zoom)))
        col = g.clamp_pan(cols, self.pane_cols, self.pan_x)
        row = g.clamp_pan(rows, self.pane_rows, self.pan_y)
        self.pan_x, self.pan_y = col, row
        return cols, rows, col, row

    def handle(self, key: str) -> str:
        """Apply a keystroke. Returns 'quit', 'redraw' or 'ignore'."""
        if key in QUIT_KEYS:
            return "quit"
        if key in ZOOM_IN_KEYS:
            self.zoom = g.clamp_zoom(self.zoom * ZOOM_STEP)
        elif key in ZOOM_OUT_KEYS:
            self.zoom = g.clamp_zoom(self.zoom / ZOOM_STEP)
        elif key in ("0", "f"):
            self.reset()
        elif key == ".":
            self.one_to_one = not self.one_to_one
        elif key == "h":
            self.pan_x += PAN_COLS
        elif key == "l":
            self.pan_x -= PAN_COLS
        elif key == "k":
            self.pan_y += PAN_ROWS
        elif key == "j":
            self.pan_y -= PAN_ROWS
        else:
            return "ignore"
        return "redraw"
