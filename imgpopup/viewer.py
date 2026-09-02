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
from .imageio import load_png
from .state import ViewerState

PLUGIN_ID = "imgpopup"
LAYER = "img"
POLL_SECONDS = 0.25
CELL_PX_ESTIMATE = 8


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
        self.png = None
        self.error = None

    def status(self, text: str) -> None:
        sys.stdout.write("\x1b[%d;1H\x1b[2K%s" % (self.rows, text[:self.cols - 1]))
        sys.stdout.flush()

    def show(self, path: str) -> None:
        self.path = path
        try:
            max_px = min(4096, max(64, self.cols * CELL_PX_ESTIMATE * 4))
            self.png, width, height = load_png(path, max_px)
            self.state.load(width, height)
            self.error = None
        except Exception as exc:                      # noqa: BLE001 - shown, not raised
            self.error = "cannot open %s: %s" % (os.path.basename(path), exc)
        self.draw()

    def draw(self) -> None:
        if self.error:
            self.status(self.error + "   q=close")
            return
        cols, rows, col, row = self.state.placement()
        try:
            api.graphics_set(self.pane_id, self.png, self.state.img_w,
                             self.state.img_h, cols, rows, col, row, layer_id=LAYER)
            self.status("%s  %dx%d  x%.2f   q close  +/- zoom  hjkl pan  0 fit"
                        % (os.path.basename(self.path or "?"), self.state.img_w,
                           self.state.img_h, self.state.zoom))
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
            try:
                api.graphics_clear(self.pane_id, LAYER)
            except Exception:                          # noqa: BLE001 - teardown
                pass
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
