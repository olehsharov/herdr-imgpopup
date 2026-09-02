import json

from PIL import Image

from imgpopup import cli


def test_context_supplies_clicked_url_and_cwd():
    env = {"HERDR_PLUGIN_CONTEXT_JSON": json.dumps(
        {"clicked_url": "rim.png", "focused_pane_cwd": "/tmp/pics"})}
    assert cli.clicked_from_context(env) == ("rim.png", "/tmp/pics")


def test_context_absent_returns_none_pair():
    assert cli.clicked_from_context({}) == (None, None)


def test_malformed_context_json_is_tolerated():
    assert cli.clicked_from_context(
        {"HERDR_PLUGIN_CONTEXT_JSON": "{not json"}) == (None, None)


def test_argument_beats_context(tmp_path, monkeypatch):
    img = tmp_path / "a.png"
    Image.new("RGB", (100, 50)).save(img)
    monkeypatch.setenv("HERDR_PLUGIN_CONTEXT_JSON",
                       json.dumps({"clicked_url": "/nope/b.png"}))
    monkeypatch.setenv("HERDR_PLUGIN_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setattr(cli, "_open_popup", lambda: None)
    monkeypatch.setattr(cli, "_popup_alive", lambda: True)
    assert cli.main(["show", str(img)]) == 0
    assert (tmp_path / "state" / "current").read_text().strip() == str(img)


def test_falls_back_to_clicked_url_when_no_argument(tmp_path, monkeypatch):
    img = tmp_path / "clicked.png"
    Image.new("RGB", (10, 10)).save(img)
    monkeypatch.setenv("HERDR_PLUGIN_CONTEXT_JSON", json.dumps(
        {"clicked_url": "clicked.png", "focused_pane_cwd": str(tmp_path)}))
    monkeypatch.setenv("HERDR_PLUGIN_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setattr(cli, "_popup_alive", lambda: True)
    assert cli.main(["show"]) == 0
    assert (tmp_path / "state" / "current").read_text().strip() == str(img)


def test_unresolvable_path_exits_2(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("HERDR_PLUGIN_CONTEXT_JSON", raising=False)
    monkeypatch.setenv("HERDR_PLUGIN_STATE_DIR", str(tmp_path / "state"))
    assert cli.main(["show", str(tmp_path / "ghost.png")]) == 2
    assert "no such file" in capsys.readouterr().err


def test_no_path_and_no_context_exits_2(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("HERDR_PLUGIN_CONTEXT_JSON", raising=False)
    monkeypatch.setenv("HERDR_PLUGIN_STATE_DIR", str(tmp_path / "state"))
    assert cli.main(["show"]) == 2
    assert "no path given" in capsys.readouterr().err


def test_opens_popup_when_none_alive(tmp_path, monkeypatch):
    img = tmp_path / "a.png"
    Image.new("RGB", (100, 50)).save(img)
    monkeypatch.delenv("HERDR_PLUGIN_CONTEXT_JSON", raising=False)
    monkeypatch.setenv("HERDR_PLUGIN_STATE_DIR", str(tmp_path / "state"))
    opened = []
    monkeypatch.setattr(cli, "_popup_alive", lambda: False)
    monkeypatch.setattr(cli, "_open_popup", lambda: opened.append(1))
    assert cli.main(["show", str(img)]) == 0
    assert opened == [1]


def test_does_not_reopen_when_popup_alive(tmp_path, monkeypatch):
    img = tmp_path / "a.png"
    Image.new("RGB", (100, 50)).save(img)
    monkeypatch.delenv("HERDR_PLUGIN_CONTEXT_JSON", raising=False)
    monkeypatch.setenv("HERDR_PLUGIN_STATE_DIR", str(tmp_path / "state"))
    calls = []
    monkeypatch.setattr(cli, "_popup_alive", lambda: True)
    monkeypatch.setattr(cli, "_open_popup", lambda: calls.append(1))
    assert cli.main(["show", str(img)]) == 0
    assert calls == []


def test_relative_path_falls_back_to_herdr_pane_cwds(tmp_path, monkeypatch):
    """A click on `tmp/x.png` in a Claude Code pane: no prompt, ssh cwd is
    $HOME - only Herdr knows that pane's directory."""
    proj = tmp_path / "proj"
    (proj / "tmp").mkdir(parents=True)
    Image.new("RGB", (10, 10)).save(proj / "tmp" / "x.png")
    monkeypatch.chdir(tmp_path)                       # like ssh: not the project
    monkeypatch.delenv("HERDR_PLUGIN_CONTEXT_JSON", raising=False)
    monkeypatch.setenv("HERDR_PLUGIN_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setattr(cli, "_pane_cwds", lambda: ["/nowhere", str(proj)])
    monkeypatch.setattr(cli, "_popup_alive", lambda: True)
    assert cli.main(["show", "tmp/x.png"]) == 0
    assert (tmp_path / "state" / "current").read_text().strip() == str(proj / "tmp" / "x.png")


def test_relative_path_unresolvable_anywhere_exits_2(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HERDR_PLUGIN_CONTEXT_JSON", raising=False)
    monkeypatch.setenv("HERDR_PLUGIN_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setattr(cli, "_pane_cwds", lambda: [str(tmp_path)])
    assert cli.main(["show", "tmp/ghost.png"]) == 2
    assert "no such file" in capsys.readouterr().err


def test_absolute_path_does_not_consult_panes(tmp_path, monkeypatch):
    monkeypatch.setenv("HERDR_PLUGIN_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.delenv("HERDR_PLUGIN_CONTEXT_JSON", raising=False)
    called = []
    monkeypatch.setattr(cli, "_pane_cwds", lambda: called.append(1) or [])
    assert cli.main(["show", str(tmp_path / "ghost.png")]) == 2
    assert called == []


def test_pane_cwds_prefers_focused_and_dedups(monkeypatch):
    panes = [{"pane_id": "a", "focused": False, "cwd": "/h", "foreground_cwd": "/p1"},
             {"pane_id": "b", "focused": True, "cwd": "/p2", "foreground_cwd": "/p2"},
             {"pane_id": "c", "focused": False, "cwd": "/p1", "foreground_cwd": None}]
    monkeypatch.setattr(cli.api, "call", lambda m, p, *a, **k: {"panes": panes})
    assert cli._pane_cwds() == ["/p2", "/p1", "/h"]
