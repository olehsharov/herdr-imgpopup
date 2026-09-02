# lsi - `ls -la` plus a clickable file:// URL for every image.
#
# Why not `ls --hyperlink`: Herdr strips OSC 8 hyperlinks when it renders a
# pane to the client, so kitty never sees them. Kitty DOES detect plain-text
# URLs by prefix, and `file://` is in its default url_prefixes - so a bare
# `file:///abs/path.png` on screen is ctrl+shift+clickable through Herdr.
#
#   source /path/to/lsi.sh      (or add that line to ~/.bashrc)
#   lsi [dir]                    default: .
lsi() {
    local dir="${1:-.}"
    ls -la --color=auto -- "$dir" || return
    local f any=""
    for f in "$dir"/*; do
        case "${f,,}" in
            *.png|*.jpg|*.jpeg|*.webp|*.gif|*.bmp|*.tif|*.tiff)
                [ -f "$f" ] || continue
                [ -n "$any" ] || { printf '\n'; any=1; }
                printf 'file://%s\n' "$(realpath -- "$f")"
                ;;
        esac
    done
}
