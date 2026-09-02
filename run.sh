#!/bin/sh
# Launcher for the popup pane. The stderr redirect is not optional: pane
# processes are not captured by `herdr plugin log list`, so without it a crash
# takes its own error message off-screen when the pane closes.
cd "$(dirname "$0")" || exit 1
PY=python3
[ -x .venv/bin/python ] && PY=.venv/bin/python
exec "$PY" -m imgpopup.viewer 2>err.log
