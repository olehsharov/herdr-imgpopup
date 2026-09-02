#!/bin/sh
# Runs on the machine running kitty. Opens an image that lives on the Herdr box.
#
# Called by open-actions.conf (ctrl+shift+click) and the hints kitten
# (ctrl+shift+i) with the image path as $1. Everything that needs the remote
# side is pinned by absolute path because a non-interactive ssh command does
# NOT load your shell profile - `img` alone is "command not found" there.
HOST="__HOST__"
exec ssh -o BatchMode=yes "$HOST" "\$HOME/.local/bin/img '$1'"
