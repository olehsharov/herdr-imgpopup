"""The process that owns the popup pane.

Reads the path to show from $HERDR_PLUGIN_STATE_DIR/current, paints it, then
blocks on the keyboard. The same select() timeout doubles as the poll for that
file changing, so a push from `imgpopup show` swaps the image in place.
"""
import os
import select
import sys
import termios
import tty
from typing import Optional

from . import api
from .geometry import tile_count
from .imageio import encode_tiles, open_image
from .input import InputParser
from .state import ViewerState, ZOOM_STEP

PLUGIN_ID = "imgpopup"
POLL_SECONDS = 0.25
ESC_SETTLE_SECONDS = 0.03
MOUSE_ON = "\x1b[?1002h\x1b[?1006h"
MOUSE_OFF = "\x1b[?1006l\x1b[?1002l"
DEFAULT_CELL = (8, 16)


def state_dir() -> str:
    """Where the CLI and the viewer rendezvous.

    Inside a plugin process Herdr sets HERDR_PLUGIN_STATE_DIR. The CLI often runs
    OUTSIDE one (a shell, a ranger keybinding), so the fallback must reproduce
    Herdr's own layout exactly - a different fallback means the two never see
    each other's files.
    """
    return os.environ.get("HERDR_PLUGIN_STATE_DIR") or os.path.expanduser(
        os.path.join("~/.local/state/herdr/plugins", PLUGIN_ID))


def _current_path() -> str:
    return os.path.join(state_dir(), "current")


def _read_current() -> Optional[str]:
    try:
        with open(_current_path(), encoding="utf-8") as handle:
            return handle.read().strip() or None
    except OSError:
        return None


class Viewer:
    def __init__(self, pane_id: str):
        self.pane_id = pane_id
        self.cols, self.rows = api.pane_rect(pane_id)
        self.cell_w, self.cell_h = DEFAULT_CELL
        self.max_k = 4
        try:
            info = api.graphics_info(pane_id)
            self.cell_w = int(info.get("cell_width_px") or self.cell_w)
            self.cell_h = int(info.get("cell_height_px") or self.cell_h)
            layers = int(info.get("max_layers_per_pane") or 16)
            self.max_k = max(1, int(layers ** 0.5))
        except api.HerdrError:
            pass                                   # draw() will surface it
        self.state = ViewerState(1, 1, self.cols, self.rows, self.cell_w, self.cell_h)
        self.path = None
        self.img = None
        self.error = None
        self.layers = 0

    def status(self, text: str) -> None:
        sys.stdout.write("\x1b[%d;1H\x1b[2K%s" % (self.rows, text[:self.cols - 1]))
        sys.stdout.flush()

    def show(self, path: str) -> None:
        self.path = path
        try:
            self.img = open_image(path)
            self.state.load(self.img.width, self.img.height)
            self.error = None
        except Exception as exc:                      # noqa: BLE001 - shown, not raised
            self.error = "cannot open %s: %s" % (os.path.basename(path), exc)
        self.draw()

    def _clear_layers(self, start: int = 0) -> None:
        for i in range(start, self.layers):
            try:
                api.graphics_clear(self.pane_id, "img-%d" % i)
            except Exception:                          # noqa: BLE001 - best effort
                pass
        self.layers = min(self.layers, start)

    def draw(self) -> None:
        if self.error:
            self.status(self.error + "   q=close")
            return
        st = self.state
        view = st.view_rect()
        cols, rows, col, row = st.placement()
        k = tile_count(st.zoom, max_k=self.max_k)
        def send(t):
            api.graphics_set(self.pane_id, t.png, t.width, t.height,
                             t.cols, t.rows, t.col, t.row, layer_id=t.layer,
                             z_index=t.z)
        try:
            tiles = encode_tiles(self.img, view, cols, rows, col, row, k,
                                 self.cell_w, self.cell_h, sink=send)
            self._clear_layers(len(tiles))
            self.layers = len(tiles)
            px = sum(t.width * t.height for t in tiles)
            kb = sum(len(t.png) for t in tiles) // 1024
            self.status("%s  %dx%d  x%.2f  %dx%d tiles %.1f Mpx %d KB   wheel/+- zoom  drag/arrows pan  0 fit  q close"
                        % (os.path.basename(self.path or "?"), st.img_w, st.img_h,
                           st.zoom, k, k, px / 1e6, kb))
        except api.HerdrError as exc:
            hint = ""
            if "cell_size_unavailable" in str(exc):
                hint = ("  -> set experimental.kitty_graphics = true in the CLIENT's "
                        "config.toml and restart it")
            self.status("cannot paint: %s%s" % (exc, hint))

    def _apply(self, ev: tuple) -> str:
        """One input event -> 'quit' | 'redraw' | 'ignore'."""
        kind = ev[0]
        if kind == "key":
            return self.state.handle(ev[1])
        if self.error:
            return "ignore"
        if kind == "wheel":
            _, direction, x, y = ev
            cols, rows, col, row = self.state.placement()
            fx = min(1.0, max(0.0, (x - 1 - col) / float(cols)))
            fy = min(1.0, max(0.0, (y - 1 - row) / float(rows)))
            factor = ZOOM_STEP if direction == "in" else 1 / ZOOM_STEP
            return "redraw" if self.state.zoom_at(factor, fx, fy) else "ignore"
        if kind == "drag":
            if self.state.zoom == 1.0:
                return "ignore"
            self.state.drag(ev[1], ev[2])
            return "redraw"
        return "ignore"

    def run(self) -> int:
        current = _read_current()
        if not current:
            self.status("nothing to show   q=close")
        else:
            self.show(current)

        fd = sys.stdin.fileno()
        saved = termios.tcgetattr(fd)
        parser = InputParser()
        sys.stdout.write(MOUSE_ON)
        sys.stdout.flush()
        try:
            tty.setraw(fd)
            while True:
                timeout = ESC_SETTLE_SECONDS if parser.buf else POLL_SECONDS
                ready, _, _ = select.select([fd], [], [], timeout)
                if ready:
                    events = parser.feed(os.read(fd, 4096))
                else:
                    events = parser.flush()
                    latest = _read_current()
                    if latest and latest != self.path:
                        self.show(latest)
                redraw = False
                for ev in events:
                    action = self._apply(ev)
                    if action == "quit":
                        return 0
                    redraw = redraw or action == "redraw"
                if redraw:
                    self.draw()
        finally:
            sys.stdout.write(MOUSE_OFF)
            sys.stdout.flush()
            termios.tcsetattr(fd, termios.TCSADRAIN, saved)
            self._clear_layers(0)
            try:
                os.unlink(os.path.join(state_dir(), "pane"))
            except OSError:
                pass


def main() -> int:
    pane_id = os.environ.get("HERDR_PANE_ID")
    if not pane_id:
        sys.stderr.write("HERDR_PANE_ID unset - not running in a Herdr pane\n")
        return 1
    os.makedirs(state_dir(), exist_ok=True)
    with open(os.path.join(state_dir(), "pane"), "w", encoding="utf-8") as handle:
        handle.write(pane_id)
    sys.stdout.write("\x1b[2J\x1b[H")
    sys.stdout.flush()
    return Viewer(pane_id).run()


if __name__ == "__main__":
    raise SystemExit(main())
