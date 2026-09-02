# herdr-imgpopup

View images inside [Herdr](https://herdr.dev) without leaving the terminal.
Click a filename in `ls` output, push one from a coding agent, or call the CLI —
the image opens in a floating overlay you can zoom and pan.

```
┌─ code ──────────────────────────────┐
│ $ ls -la                            │
│ rim.p┌─ rim.png ──────────────┐     │
│ out.p│                        │     │
│      │        [ rim ]         │     │
│      │                        │     │
│      └ q close  +/- zoom  hjkl ┘    │
└─────────────────────────────────────┘
```

## Install

```bash
herdr plugin install olehsharov/herdr-imgpopup
```

That runs `build.sh`, which creates a plugin-local `.venv` with Pillow — nothing
is installed into your system Python.

## Requirements

- **Herdr ≥ 0.8.0**
- A **Kitty-graphics-capable outer terminal**: kitty, Ghostty, WezTerm, or iTerm2 ≥ 3.6
- **This setting, on the machine running the Herdr client** (not the server, if you
  connect with `herdr --remote`):

```toml
# ~/.config/herdr/config.toml
[experimental]
kitty_graphics = true
```

Restart the client after adding it — the flag is read at startup.

This is the single most common reason nothing appears. Without it the client
reports a cell size of zero pixels, Herdr cannot convert a cell placement into a
pixel rectangle, and every image is accepted and then silently not drawn.

## Use

**From a shell**, the primary route:

```bash
img path/to/image.png
```

Create that shortcut once (the plugin root is wherever Herdr installed it):

```bash
printf '#!/bin/sh\nexec "$(herdr plugin list --json | python3 -c "import sys,json;print([p[\'plugin_root\'] for p in json.load(sys.stdin)[\'result\'][\'plugins\'] if p[\'plugin_id\']==\'imgpopup\'][0])")/cli.sh" show "$@"\n' > ~/.local/bin/img
chmod +x ~/.local/bin/img
```

## Clicking ANY image — the `imgclick` kitten

Herdr's link handlers never fire and Herdr strips OSC 8 hyperlinks, so no
path can be made clickable *inside* Herdr. The way out is above it: a kitten that
runs inside kitty's own process. It reads the screen text and the exact cell you
clicked (`Window.current_mouse_position()` — real, just undocumented), so it works in
Claude Code output, `ls -la`, ranger, anything, through Herdr — bare paths included.
Bare `ls` names are resolved against the directory in the shell prompt above the click.

Install on the machine running kitty (`HOST` = the ssh target you give `herdr --remote`):

```bash
HOST=ubuntu@your-herdr-box
CFG=~/.config/kitty
RAW=https://raw.githubusercontent.com/olehsharov/herdr-imgpopup/main/kitty
for f in imgclick.py img-remote.sh img-native.sh open-actions.conf; do curl -fsSL $RAW/$f -o $CFG/$f; done
curl -fsSL $RAW/kitty.conf.snippet | sed "s|__CFG__|$CFG|g" >> $CFG/kitty.conf
sed -i '' "s|__HOST__|$HOST|g; s|__CFG__|$CFG|g" $CFG/img-remote.sh $CFG/img-native.sh $CFG/open-actions.conf
chmod +x $CFG/img-remote.sh $CFG/img-native.sh
```

Reload kitty (**ctrl+shift+f5**), then **ctrl+shift+click** any image path on screen.
Debug log: `~/.config/kitty/imgclick.log` (one line per click: cell, line text, result).

| pointer over | opens |
|---|---|
| `/abs/path/img.png`, `~/x.jpg`, `file:///…`, `file://host/…` | that file |
| `car.jpg` in `ls -la` output | `<dir from the prompt above>/car.jpg` |
| an `https://` link | kitty's normal URL open (fallback) |

Two viewers, pick in the `mouse_map` line: **`img-remote.sh`** → Herdr overlay on the
box (zoom/pan, in-terminal); **`img-native.sh`** → scp + macOS **Quick Look** (native
floating window, pinch zoom, plays video). Keyboard alternative: **ctrl+shift+i** labels
every image path on screen (hints kitten).

Why ctrl+shift: Herdr captures the mouse, so plain/Cmd/Alt clicks go to the pane app;
ctrl+shift is the combination kitty still receives while an app has grabbed the mouse.

> **Herdr's link handlers do not dispatch on 0.8.2.** The plugin registers a
> `[[link_handlers]]` entry, and Herdr accepts it, but nothing dispatches it:
> bare paths are never highlighted, real OSC 8 hyperlinks are highlighted yet
> inert, and no entry appears in the right-click menu. There is no modifier to
> hold — Herdr exposes no URL-click modifier setting at all. The action itself is
> fine (`herdr plugin action invoke show --plugin imgpopup` runs it and receives a
> full context), so this plugin will work unchanged if link dispatch is wired up.
> Until then, use `img` or an editor/agent that calls `cli.sh show`.

**From the CLI**, which is also how an agent pushes you an image:

```bash
~/.config/herdr/plugins/imgpopup/cli.sh show path/to/image.png
```

**From ranger** — clicking may not reach Herdr, because ranger runs on the
alternate screen and captures the mouse itself. Bind a key in `~/.config/ranger/rc.conf`:

```
map <C-i> shell ~/.config/herdr/plugins/imgpopup/cli.sh show %f
```

This is more reliable than clicking anyway: it passes ranger's real path rather
than a basename that has to be guessed against the pane's working directory.

## Keys

| key | action | key | action |
|---|---|---|---|
| `+` `=` | zoom in | `h` `j` `k` `l` | pan |
| `-` `_` | zoom out | `0` `f` | fit |
| `q` `Esc` | close | `.` | 1:1 pixels |

Only one viewer exists at a time. Showing another image swaps it in place,
keeping the overlay where it is.

## Troubleshooting

Nothing appears:

```bash
cat ~/.config/herdr/plugins/imgpopup/err.log     # viewer crashes land here
herdr plugin log list --plugin imgpopup          # action failures land here
```

If the status line says `cell_size_unavailable`, it is the `kitty_graphics`
setting above, on the client machine.

## Notes for anyone extending this

Two Herdr behaviours cost real time to discover and are documented nowhere:

- **Images go through the `pane.graphics.*` API, not Kitty escape sequences.**
  Writing escapes into a pane's tty *is* parsed — Herdr embeds Ghostty's terminal
  core, so it reserves exactly the right number of cells — but nothing is ever
  painted. The cells look right and stay empty.
- **`placement = "popup"` cannot display images.** A popup pane receives no
  `HERDR_PANE_ID`, and `plugin.pane.open` returns no pane id for it, so the
  process inside can never name itself to `pane.graphics.set`. `overlay` floats
  the same way and *is* addressable, which is why this plugin uses it.

`pane.graphics.set` returning `{"type":"ok"}` means the image was accepted, never
that it was drawn. `pane.graphics.info` is the only call that reports health.

## Licence

MIT
