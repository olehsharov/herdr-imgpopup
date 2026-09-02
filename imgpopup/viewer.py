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
from .state import ViewerState

PLUGIN_ID = "imgpopup"
POLL_SECONDS = 0.25


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
        self.state = ViewerState(1, 1, self.cols, self.rows)
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
        k = tile_count(st.zoom)
        tiles = encode_tiles(self.img, view, cols, rows, col, row, k)
        try:
            for t in tiles:
                api.graphics_set(self.pane_id, t.png, t.width, t.height,
                                 t.cols, t.rows, t.col, t.row, layer_id=t.layer)
            self._clear_layers(len(tiles))
            self.layers = len(tiles)
            px = sum(t.width * t.height for t in tiles)
            kb = sum(len(t.png) for t in tiles) // 1024
            self.status("%s  %dx%d  x%.2f  %dx%d tiles %.1f Mpx %d KB   q close  +/- zoom  hjkl pan  0 fit"
                        % (os.path.basename(self.path or "?"), st.img_w, st.img_h,
                           st.zoom, k, k, px / 1e6, kb))
        except api.HerdrError as exc:
            hint = ""
            if "cell_size_unavailable" in str(exc):
                hint = ("  -> set experimental.kitty_graphics = true in the CLIENT's "
                        "config.toml and restart it")
            self.status("cannot paint: %s%s" % (exc, hint))

    def run(self) -> int:
        current = _read_current()
        if not current:
            self.status("nothing to show   q=close")
        else:
            self.show(current)

        fd = sys.stdin.fileno()
        saved = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while True:
                ready, _, _ = select.select([fd], [], [], POLL_SECONDS)
                if ready:
                    key = os.read(fd, 1).decode("utf-8", "ignore")
                    action = self.state.handle(key)
                    if action == "quit":
                        return 0
                    if action == "redraw":
                        self.draw()
                else:
                    latest = _read_current()
                    if latest and latest != self.path:
                        self.show(latest)
        finally:
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
