"""The CLI and the viewer must rendezvous in the same directory.

They are separate processes with different environments - the viewer always has
HERDR_PLUGIN_STATE_DIR, the CLI usually does not. A drifting fallback is silent:
the CLI writes, the viewer polls, and nothing ever happens.
"""
import os

from imgpopup import cli, viewer


def test_fallbacks_are_identical(monkeypatch):
    monkeypatch.delenv("HERDR_PLUGIN_STATE_DIR", raising=False)
    assert cli.state_dir() == viewer.state_dir()


def test_fallback_matches_herdr_layout(monkeypatch):
    monkeypatch.delenv("HERDR_PLUGIN_STATE_DIR", raising=False)
    expected = os.path.expanduser("~/.local/state/herdr/plugins/imgpopup")
    assert cli.state_dir() == expected


def test_env_wins_when_present(monkeypatch, tmp_path):
    monkeypatch.setenv("HERDR_PLUGIN_STATE_DIR", str(tmp_path))
    assert cli.state_dir() == str(tmp_path)
    assert viewer.state_dir() == str(tmp_path)
