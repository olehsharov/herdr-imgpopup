#!/usr/bin/env python3
"""imgclick - a kitten that opens the image path under the mouse pointer.

Runs INSIDE kitty's process (no overlay UI), so it sits above everything that
blocked clicking before: it reads the real screen text (Herdr strips OSC 8
hyperlinks, but not plain text), it knows the exact cell you clicked
(Window.current_mouse_position(), present in kitty's source since long but
undocumented), and it ignores which app grabbed the mouse.

Install (on the machine running kitty):
    cp imgclick.py ~/.config/kitty/
    # kitty.conf:
    mouse_map ctrl+shift+left press   grabbed            discard_event
    mouse_map ctrl+shift+left release grabbed,ungrabbed  kitten imgclick.py ~/.config/kitty/img-remote.sh

The last argument is the program that receives the path (img-remote.sh opens
the Herdr overlay on the remote box; img-native.sh fetches the file and opens
it in macOS Quick Look). With no image under the pointer it falls back to
kitty's normal URL click, so ctrl+shift+click still opens https links.

Bare basenames (as in `ls -la` output) are resolved against the directory
shown in the nearest shell prompt ABOVE the click, e.g.
`ubuntu@host:/mnt/data/pics$` - the only cwd available through Herdr/ssh.

Debug: ~/.config/kitty/imgclick.log
"""
import os
import re
import sys
import time
from typing import Any, List, Optional

IMAGE_EXT = r"(?:png|jpe?g|webp|gif|bmp|tiff?|mp4|mkv|webm|mov|m4v)"
# A candidate token: file:// URL, absolute or ~ path, or a bare name; all must
# end in an image/video extension. Spaces are not allowed inside a token.
TOKEN_RE = re.compile(
    r"(?:file://[^\s'\"<>]+?\." + IMAGE_EXT +
    r"|(?:~|\.{1,2})?/[^\s'\"<>|]*?\." + IMAGE_EXT +
    r"|[\w.@+-]+\." + IMAGE_EXT + r")(?![\w.])",
    re.IGNORECASE,
)
# `user@host:/some/dir$ ` or `user@host:~/dir$ ` - a bash prompt exposing cwd.
PROMPT_RE = re.compile(r"^[\w.-]+@[\w.-]+:(\S+)\s*[$#]")

LOG = os.path.expanduser("~/.config/kitty/imgclick.log")


def log(msg: str) -> None:
    try:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write("%s %s\n" % (time.strftime("%H:%M:%S"), msg))
    except OSError:
        pass


def token_under(line: str, cell_x: int) -> Optional[str]:
    """The image/video token whose span covers column cell_x, if any."""
    for m in TOKEN_RE.finditer(line):
        if m.start() <= cell_x < m.end():
            return m.group(0)
    return None


def prompt_dir_above(lines: List[str], row: int) -> Optional[str]:
    """Directory from the nearest shell prompt at or above `row`."""
    for y in range(min(row, len(lines) - 1), -1, -1):
        m = PROMPT_RE.match(lines[y])
        if m:
            return m.group(1)
    return None


def resolve(token: str, lines: List[str], row: int) -> str:
    """Turn the clicked token into a path the remote `img` can open."""
    if token.lower().startswith("file://"):
        rest = token[len("file://"):]
        # file://host/path -> /path ; file:///path -> /path
        if not rest.startswith("/"):
            rest = rest[rest.find("/"):]
        return rest
    if token.startswith(("/", "~")):
        return token
    if token.startswith("./"):
        token = token[2:]
    base = prompt_dir_above(lines, row)
    return (base.rstrip("/") + "/" + token) if base else token


def find_target(lines: List[str], cell_x: int, cell_y: int) -> Optional[str]:
    """Pure entry point: screen lines + click cell -> path, or None."""
    if not (0 <= cell_y < len(lines)):
        return None
    tok = token_under(lines[cell_y], cell_x)
    return resolve(tok, lines, cell_y) if tok else None


# ---- kitty glue -------------------------------------------------------------

def main(args: List[str]) -> None:
    """no_ui kitten: nothing runs in the terminal; see handle_result."""


def _screen_lines(w: Any) -> List[str]:
    try:
        return [str(w.screen.line(i)) for i in range(w.screen.lines)]
    except Exception as exc:                          # noqa: BLE001
        log("screen.line failed (%s), using as_text" % exc)
        return w.as_text(alternate_screen=True).split("\n")


def handle_result(args: List[str], answer: Any, target_window_id: int, boss: Any) -> None:
    w = boss.window_id_map.get(target_window_id)
    if w is None:
        log("no window %r" % target_window_id)
        return
    mp = w.current_mouse_position()
    if not mp:
        log("no mouse position")
        return
    lines = _screen_lines(w)
    path = find_target(lines, mp["cell_x"], mp["cell_y"])
    log("cell=(%d,%d) line=%r -> %r" % (mp["cell_x"], mp["cell_y"],
                                        lines[mp["cell_y"]][:120] if mp["cell_y"] < len(lines) else "",
                                        path))
    if path is None:
        # Not an image: behave like a normal URL click.
        try:
            w.mouse_click_url()
        except Exception as exc:                      # noqa: BLE001
            log("mouse_click_url failed: %s" % exc)
        return
    program = args[1] if len(args) > 1 else os.path.expanduser("~/.config/kitty/img-remote.sh")
    program = os.path.expanduser(program)
    boss.run_background_process([program, path], cwd=None, allow_remote_control=False)


try:
    from kittens.tui.handler import result_handler   # type: ignore
    handle_result = result_handler(no_ui=True)(handle_result)   # type: ignore
except ImportError:
    pass                                              # not running inside kitty


# ---- self-test (runs anywhere: python3 imgclick.py --selftest) --------------

def _selftest() -> int:
    lines = [
        "ubuntu@renderilla:/mnt/data_2/tryrims/data/samples$ ls -la",
        "-rw-rw-r-- 1 ubuntu ubuntu 2184434 Mar  9 15:43 car.jpg",
        "-rw-rw-r-- 1 ubuntu ubuntu   11206 Mar  9 15:44 car_rim_mask.webp",
        "see file:///mnt/data_2/tryrims/data/samples/rim.png here",
        "  path: /mnt/data_2/x/bmw-328.jpg  and ~/pics/a.PNG  and notes.txt",
        "plain text without anything",
        "file://renderilla/mnt/data_2/tryrims/data/samples/car.jpg",
    ]
    cases = [
        ((49, 1), "/mnt/data_2/tryrims/data/samples/car.jpg"),      # bare name via prompt
        ((55, 2), "/mnt/data_2/tryrims/data/samples/car_rim_mask.webp"),
        ((10, 3), "/mnt/data_2/tryrims/data/samples/rim.png"),      # file:/// URL
        ((3, 3), None),                                            # "see" - not on token
        ((12, 4), "/mnt/data_2/x/bmw-328.jpg"),
        ((40, 4), "~/pics/a.PNG"),
        ((55, 4), None),                                           # notes.txt
        ((5, 5), None),
        ((30, 6), "/mnt/data_2/tryrims/data/samples/car.jpg"),     # file://host/path
        ((0, 99), None),
    ]
    bad = 0
    for (x, y), want in cases:
        got = find_target(lines, x, y)
        ok = got == want
        bad += not ok
        print("%s (%2d,%d) -> %r" % ("ok " if ok else "BAD", x, y, got) + ("" if ok else "  want %r" % want))
    print("%d/%d passed" % (len(cases) - bad, len(cases)))
    return 1 if bad else 0


if __name__ == "__main__" and "--selftest" in sys.argv:
    raise SystemExit(_selftest())
