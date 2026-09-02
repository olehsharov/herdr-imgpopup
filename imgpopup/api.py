"""Thin JSON-RPC client for the Herdr unix socket.

Every Herdr response is either {"result": ...} or {"error": {"code", "message"}}.
A successful response means the request was ACCEPTED - never that a pane painted
or a process survived. Callers must verify effects separately.
"""
import base64
import json
import os
import socket
import time
from typing import Optional, Tuple

DEFAULT_TIMEOUT = 10.0


class HerdrError(Exception):
    """A Herdr API call returned an error body."""


DEFAULT_SOCKET = "~/.config/herdr/herdr.sock"


def _socket_path(sock_path: Optional[str]) -> str:
    """Explicit arg, then the env Herdr injects into its panes, then Herdr's
    default socket location - so `img` works from a bare ssh session that was
    never spawned by Herdr (which is what a kitty open_action produces)."""
    path = sock_path or os.environ.get("HERDR_SOCKET_PATH")
    if not path:
        candidate = os.path.expanduser(DEFAULT_SOCKET)
        if os.path.exists(candidate):
            return candidate
        raise HerdrError("no Herdr socket: HERDR_SOCKET_PATH unset and %s absent"
                         % DEFAULT_SOCKET)
    return path


def call(method: str, params: dict, sock_path: Optional[str] = None) -> dict:
    """One request/response round trip. Raises HerdrError on an error body."""
    request = {"id": "imgpopup:%d" % time.time_ns(), "method": method, "params": params}
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(DEFAULT_TIMEOUT)
        client.connect(_socket_path(sock_path))
        client.sendall((json.dumps(request) + "\n").encode())
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = client.recv(65536)
            if not chunk:
                break
            buf += chunk
    response = json.loads(buf.decode() or "{}")
    if "error" in response:
        err = response["error"]
        raise HerdrError("%s: %s" % (err.get("code", "?"), err.get("message", "")))
    return response.get("result", {})


def pane_rect(pane_id: str, sock_path: Optional[str] = None) -> Tuple[int, int]:
    """The pane's size in cells, as (cols, rows)."""
    layout = call("pane.layout", {"pane_id": pane_id}, sock_path).get("layout", {})
    for pane in layout.get("panes", []):
        if pane["pane_id"] == pane_id:
            return pane["rect"]["width"], pane["rect"]["height"]
    raise HerdrError("pane %s not present in its own layout" % pane_id)


def graphics_set(pane_id: str, png_bytes: bytes, img_w: int, img_h: int,
                 cols: int, rows: int, col: int, row: int,
                 layer_id: str = "img", sock_path: Optional[str] = None,
                 z_index: int = 0) -> None:
    """Place (or replace) a PNG layer. Same layer_id replaces in place."""
    call("pane.graphics.set", {
        "pane_id": pane_id,
        "format": "png",
        "data_base64": base64.standard_b64encode(png_bytes).decode(),
        "image_width": img_w,
        "image_height": img_h,
        "layer_id": layer_id,
        "z_index": z_index,
        "placement": {"grid_cols": cols, "grid_rows": rows,
                      "viewport_col": col, "viewport_row": row},
    }, sock_path)


def graphics_clear(pane_id: str, layer_id: str = "img",
                   sock_path: Optional[str] = None) -> None:
    call("pane.graphics.clear", {"pane_id": pane_id, "layer_id": layer_id}, sock_path)


def pane_alive(pane_id: str, sock_path: Optional[str] = None) -> bool:
    """True if the pane still exists."""
    try:
        pane_rect(pane_id, sock_path)
        return True
    except HerdrError:
        return False
    except OSError:
        return False


def graphics_info(pane_id: str, sock_path: Optional[str] = None) -> dict:
    """Client cell size in px, layer cap, etc. The only call that reports
    graphics health (cell_size_unavailable when the client cannot paint)."""
    return call("pane.graphics.info", {"pane_id": pane_id}, sock_path)
