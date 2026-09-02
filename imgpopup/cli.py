"""`imgpopup show <path>` - the single entry point for every use case.

A link-handler click, a ranger keybinding and an agent's shell command all land
here. Writes the resolved path to the state file, then opens the popup only if
one is not already running.
"""
import argparse
import json
import os
import sys
from typing import Optional, Tuple

from . import api
from .resolve import ResolveError, resolve

PLUGIN_ID = "imgpopup"
ENTRYPOINT = "view"


def state_dir() -> str:
    """Where the CLI and the viewer rendezvous.

    Inside a plugin process Herdr sets HERDR_PLUGIN_STATE_DIR. The CLI often runs
    OUTSIDE one (a shell, a ranger keybinding), so the fallback must reproduce
    Herdr's own layout exactly - a different fallback means the two never see
    each other's files.
    """
    return os.environ.get("HERDR_PLUGIN_STATE_DIR") or os.path.expanduser(
        os.path.join("~/.local/state/herdr/plugins", PLUGIN_ID))


def clicked_from_context(env: dict) -> Tuple[Optional[str], Optional[str]]:
    """Pull (clicked_url, focused_pane_cwd) out of the plugin invocation context."""
    raw = env.get("HERDR_PLUGIN_CONTEXT_JSON")
    if not raw:
        return None, None
    try:
        ctx = json.loads(raw)
    except (ValueError, TypeError):
        return None, None
    if not isinstance(ctx, dict):
        return None, None
    return ctx.get("clicked_url"), ctx.get("focused_pane_cwd")


def _popup_alive() -> bool:
    try:
        with open(os.path.join(state_dir(), "pane"), encoding="utf-8") as handle:
            pane_id = handle.read().strip()
    except OSError:
        return False
    return bool(pane_id) and api.pane_alive(pane_id)


def _pane_cwds() -> list:
    """Working directories of every Herdr pane, focused pane first.

    A click arrives here through a fresh ssh session whose cwd is $HOME, and
    the kitten can only supply a cwd when a shell prompt is visible above the
    click. For a relative path from a Claude Code or ranger pane, Herdr itself
    is the only thing that knows where that pane is.
    """
    try:
        panes = api.call("pane.list", {}).get("panes", [])
    except (api.HerdrError, OSError):
        return []
    panes = sorted(panes, key=lambda p: not p.get("focused"))
    out = []
    for pane in panes:
        for key in ("foreground_cwd", "cwd"):
            d = pane.get(key)
            if d and d not in out:
                out.append(d)
    return out


def _resolve_anywhere(target: str, cwd: Optional[str]):
    """resolve() against the given cwd, then against every Herdr pane cwd."""
    try:
        return resolve(target, cwd or os.getcwd())
    except ResolveError as first:
        if target.startswith(("/", "~", "file://")):
            raise
        for d in _pane_cwds():
            try:
                return resolve(target, d)
            except ResolveError:
                continue
        raise first


def _open_popup() -> None:
    """Open the viewer as an overlay.

    NOT placement "popup": Herdr's popup panes receive no HERDR_PANE_ID and
    plugin.pane.open returns no pane id for them, so a popup cannot name itself
    to pane.graphics.set and can never be painted into. Overlay floats the same
    way and is addressable.
    """
    api.call("plugin.pane.open", {
        "plugin_id": PLUGIN_ID,
        "entrypoint": ENTRYPOINT,
        "placement": "overlay",
        "focus": True,
    })


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(prog="imgpopup")
    sub = parser.add_subparsers(dest="command", required=True)
    show = sub.add_parser("show", help="show an image in the popup")
    show.add_argument("path", nargs="?", help="image path (defaults to the clicked link)")
    args = parser.parse_args(argv)

    clicked, cwd = clicked_from_context(os.environ)
    target = args.path or clicked
    if not target:
        sys.stderr.write("imgpopup: no path given and no clicked link in context\n")
        return 2

    try:
        path = _resolve_anywhere(target, cwd)
    except ResolveError as exc:
        sys.stderr.write("imgpopup: %s\n" % exc)
        return 2

    os.makedirs(state_dir(), exist_ok=True)
    with open(os.path.join(state_dir(), "current"), "w", encoding="utf-8") as handle:
        handle.write(str(path))

    try:
        if not _popup_alive():
            _open_popup()
    except api.HerdrError as exc:
        sys.stderr.write("imgpopup: %s\n" % exc)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
