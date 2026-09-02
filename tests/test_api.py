import base64
import json
import os
import socket
import threading

import pytest

from imgpopup import api


class FakeServer:
    """A unix socket that records requests and replies with canned JSON."""

    def __init__(self, tmp_path, reply):
        self.path = str(tmp_path / "sock")
        self.reply = reply
        self.requests = []
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(self.path)
        self.sock.listen(4)
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            with conn:
                buf = b""
                while not buf.endswith(b"\n"):
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    buf += chunk
                if buf:
                    self.requests.append(json.loads(buf))
                conn.sendall((json.dumps(self.reply) + "\n").encode())

    def close(self):
        self.sock.close()
        try:
            os.unlink(self.path)
        except OSError:
            pass


def test_call_sends_method_and_params(tmp_path):
    srv = FakeServer(tmp_path, {"id": "x", "result": {"type": "ok"}})
    try:
        api.call("pane.graphics.clear", {"pane_id": "w1:p1"}, sock_path=srv.path)
        assert srv.requests[0]["method"] == "pane.graphics.clear"
        assert srv.requests[0]["params"]["pane_id"] == "w1:p1"
    finally:
        srv.close()


def test_call_raises_on_error_response(tmp_path):
    srv = FakeServer(tmp_path, {"id": "x", "error": {
        "code": "cell_size_unavailable", "message": "host cell size is unavailable"}})
    try:
        with pytest.raises(api.HerdrError) as exc:
            api.call("pane.graphics.info", {"pane_id": "w1:p1"}, sock_path=srv.path)
        assert "cell_size_unavailable" in str(exc.value)
    finally:
        srv.close()


def test_missing_socket_env_raises_when_default_absent(monkeypatch, tmp_path):
    monkeypatch.delenv("HERDR_SOCKET_PATH", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))          # no ~/.config/herdr/herdr.sock
    with pytest.raises(api.HerdrError):
        api.call("pane.layout", {"pane_id": "w1:p1"})


def test_default_socket_used_when_env_unset(monkeypatch, tmp_path):
    """A kitty open_action arrives via a fresh ssh session with no Herdr env."""
    monkeypatch.delenv("HERDR_SOCKET_PATH", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    sockdir = tmp_path / ".config" / "herdr"
    sockdir.mkdir(parents=True)
    srv = FakeServer(sockdir, {"id": "x", "result": {"type": "ok"}})
    os.rename(srv.path, str(sockdir / "herdr.sock"))
    srv.path = str(sockdir / "herdr.sock")
    try:
        api.call("pane.graphics.clear", {"pane_id": "w1:p1"})
        assert srv.requests[0]["method"] == "pane.graphics.clear"
    finally:
        srv.close()


def test_pane_rect_returns_width_and_height(tmp_path):
    reply = {"id": "x", "result": {"layout": {"panes": [
        {"pane_id": "w1:p1", "rect": {"x": 0, "y": 0, "width": 80, "height": 24}},
        {"pane_id": "w1:p2", "rect": {"x": 80, "y": 0, "width": 40, "height": 24}}]}}}
    srv = FakeServer(tmp_path, reply)
    try:
        assert api.pane_rect("w1:p2", sock_path=srv.path) == (40, 24)
    finally:
        srv.close()


def test_pane_rect_raises_when_pane_absent_from_layout(tmp_path):
    srv = FakeServer(tmp_path, {"id": "x", "result": {"layout": {"panes": []}}})
    try:
        with pytest.raises(api.HerdrError):
            api.pane_rect("w1:p9", sock_path=srv.path)
    finally:
        srv.close()


def test_graphics_set_encodes_base64_and_placement(tmp_path):
    srv = FakeServer(tmp_path, {"id": "x", "result": {"type": "ok"}})
    try:
        api.graphics_set("w1:p1", b"\x89PNG-not-real", 10, 20,
                         cols=30, rows=15, col=2, row=3, sock_path=srv.path)
        params = srv.requests[0]["params"]
        assert params["format"] == "png"
        assert params["image_width"] == 10 and params["image_height"] == 20
        assert params["placement"] == {"grid_cols": 30, "grid_rows": 15,
                                       "viewport_col": 2, "viewport_row": 3}
        assert base64.b64decode(params["data_base64"]) == b"\x89PNG-not-real"
    finally:
        srv.close()


def test_graphics_set_reuses_layer_id(tmp_path):
    srv = FakeServer(tmp_path, {"id": "x", "result": {"type": "ok"}})
    try:
        for _ in range(3):
            api.graphics_set("w1:p1", b"x", 1, 1, 1, 1, 0, 0, sock_path=srv.path)
        assert {r["params"]["layer_id"] for r in srv.requests} == {"img"}
    finally:
        srv.close()


def test_pane_alive_false_when_pane_missing(tmp_path):
    srv = FakeServer(tmp_path, {"id": "x", "error": {
        "code": "pane_not_found", "message": "no such pane"}})
    try:
        assert api.pane_alive("w1:p9", sock_path=srv.path) is False
    finally:
        srv.close()


def test_pane_alive_false_when_socket_is_gone(tmp_path):
    assert api.pane_alive("w1:p1", sock_path=str(tmp_path / "nope.sock")) is False


def test_graphics_set_passes_z_index(tmp_path):
    srv = FakeServer(tmp_path, {"id": "x", "result": {"type": "ok"}})
    try:
        api.graphics_set("w1:p1", b"x", 1, 1, 1, 1, 0, 0, sock_path=srv.path, z_index=7)
        assert srv.requests[0]["params"]["z_index"] == 7
    finally:
        srv.close()
