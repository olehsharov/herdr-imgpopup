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

## Clicking, for real — via kitty

Herdr's own link handlers do not dispatch (below), but the **outer terminal** has its
own click pipeline that runs regardless of which app owns the pane. On the machine
running kitty (with `HOST` = the ssh target you give `herdr --remote`):

```bash
HOST=ubuntu@your-herdr-box
CFG=~/.config/kitty
RAW=https://raw.githubusercontent.com/olehsharov/herdr-imgpopup/main/kitty
curl -fsSL $RAW/img-remote.sh     -o $CFG/img-remote.sh
curl -fsSL $RAW/open-actions.conf -o $CFG/open-actions.conf
curl -fsSL $RAW/kitty.conf.snippet | sed "s|__CFG__|$CFG|g" >> $CFG/kitty.conf
sed -i '' "s|__HOST__|$HOST|g; s|__CFG__|$CFG|g" $CFG/img-remote.sh $CFG/open-actions.conf
chmod +x $CFG/img-remote.sh
```

Then reload kitty (**ctrl+shift+f5**) and verify each layer in order:

```bash
$CFG/img-remote.sh /path/on/the/box/image.png       # 1. ssh + img   -> overlay appears
kitty +open file:///path/on/the/box/image.png       # 2. open-actions -> overlay appears
```

| what's on screen | how to open it |
|---|---|
| `file:///abs/path/img.png` | **ctrl+shift+click** |
| a bare path `/abs/path/img.png` | **ctrl+shift+i**, then the hint letter |
| `ls` output | use `lsi` (below) and ctrl+shift+click the URL it adds |
| `file:///abs/path/clip.mp4` | **ctrl+shift+click** → mpv in a kitty overlay (untested) |

**`ls` output:** Herdr strips OSC 8 hyperlinks when rendering a pane, so
`ls --hyperlink` never reaches kitty. [`shell/lsi.sh`](shell/lsi.sh) defines `lsi`,
an `ls -la` that appends a plain-text `file://` URL per image — those kitty does detect.
On the Herdr box: `echo 'source ~/.config/herdr/plugins/.../shell/lsi.sh' >> ~/.bashrc`.

Why ctrl+shift: Herdr captures the mouse, so plain/Cmd/Alt clicks go to the pane app;
`ctrl+shift+click` is kitty's own "click the URL even though the app grabbed the mouse".
Why `file://`: kitty detects URLs by prefix; a bare path has none, so it is never a link.
Why a wrapper script: a non-interactive `ssh host img …` does not load your profile, so
`img` is not on PATH there — the wrapper pins `$HOME/.local/bin/img` explicitly.

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
