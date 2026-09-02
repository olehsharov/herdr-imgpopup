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

**From a shell** — click any image path in terminal output. The link handler
matches `png jpg jpeg webp gif bmp tif tiff`.

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
