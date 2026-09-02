"""Turn raw tty bytes into viewer events. Pure and stateful (a lone ESC may
arrive on its own; a drag needs the previous pointer position).

Events:
    ("key", name)            name: single char, or up/down/left/right,
                             zoom_in, zoom_out, escape
    ("wheel", "in"|"out", x, y)   1-based cell under the pointer
    ("drag", dx, dy)         pointer moved this many cells with button held
"""
from typing import List, Optional, Tuple

ESC = 0x1B
ARROWS = {"A": "up", "B": "down", "C": "right", "D": "left"}


class InputParser:
    def __init__(self) -> None:
        self.buf = b""
        self.drag_from: Optional[Tuple[int, int]] = None

    def feed(self, data: bytes) -> List[tuple]:
        self.buf += data
        events: List[tuple] = []
        while self.buf:
            event, used = self._parse_one(self.buf)
            if used == 0:
                break                       # incomplete: wait for more bytes
            self.buf = self.buf[used:]
            if event:
                events.append(event)
        return events

    def flush(self) -> List[tuple]:
        """Called when input goes quiet: an ESC with nothing after it is Escape."""
        buf, self.buf = self.buf, b""
        if buf == b"\x1b":
            return [("key", "escape")]
        return []

    # ------------------------------------------------------------------

    def _parse_one(self, b: bytes):
        if b[0] != ESC:
            return ("key", b[:1].decode("utf-8", "ignore")), 1
        if len(b) < 2:
            return None, 0
        if b[1] != ord("["):
            return ("key", "escape"), 1
        for i in range(2, len(b)):
            c = b[i]
            if 0x40 <= c <= 0x7E:
                params = b[2:i].decode("ascii", "ignore")
                return self._csi(params, chr(c)), i + 1
        return None, 0

    def _csi(self, params: str, final: str):
        if final in ARROWS:
            return ("key", ARROWS[final])
        if final == "~":
            n = params.split(";")[0]
            return {"5": ("key", "zoom_in"), "6": ("key", "zoom_out")}.get(n)
        if final == "u":                                    # kitty keyboard protocol
            try:
                cp = int(params.split(";")[0].split(":")[0])
            except ValueError:
                return None
            ch = chr(cp)
            if ch in "+=":
                return ("key", "zoom_in")
            if ch in "-_":
                return ("key", "zoom_out")
            return ("key", ch) if ch.isprintable() else None
        if params.startswith("<") and final in "Mm":        # SGR mouse
            try:
                code, x, y = (int(v) for v in params[1:].split(";"))
            except ValueError:
                return None
            button, wheel, motion = code & 3, code & 64, code & 32
            if wheel:
                return ("wheel", "in" if button == 0 else "out", x, y)
            if motion:
                if self.drag_from is None:
                    return None
                dx, dy = x - self.drag_from[0], y - self.drag_from[1]
                self.drag_from = (x, y)
                return ("drag", dx, dy) if (dx or dy) else None
            if final == "M" and button == 0:
                self.drag_from = (x, y)
            elif final == "m":
                self.drag_from = None
            return None
        return None
