#!/bin/sh
# Runs on the machine running kitty. Fetches the image/video from the Herdr box
# and opens it in macOS Quick Look - a native floating window with pinch-zoom,
# and video playback for free. Alternative to img-remote.sh (Herdr overlay).
HOST="__HOST__"
[ -n "$1" ] || exit 2
dir="${TMPDIR:-/tmp}/imgclick"; mkdir -p "$dir"
dst="$dir/$(basename "$1")"
scp -q -o BatchMode=yes "$HOST:$1" "$dst" || exit 3
if command -v qlmanage >/dev/null 2>&1; then
    qlmanage -p "$dst" >/dev/null 2>&1 &
else
    xdg-open "$dst" 2>/dev/null || open "$dst"
fi
