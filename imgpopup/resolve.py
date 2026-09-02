"""Turn whatever was clicked into an absolute path to an existing image.

The click can arrive as an absolute path, a path relative to the pane's cwd, a
file:// URL, or any of those wrapped in quotes by the shell that printed it.
"""
import os
from pathlib import Path
from typing import Optional
from urllib.parse import unquote

IMAGE_EXTS = frozenset(
    [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"])


class ResolveError(Exception):
    """The clicked text does not name an image file we can open."""


def resolve(clicked: str, cwd: Optional[str] = None) -> Path:
    if not clicked or not clicked.strip():
        raise ResolveError("empty path")

    raw = clicked.strip().strip("'\"")
    if raw.startswith("file://"):
        raw = unquote(raw[len("file://"):])

    path = Path(raw).expanduser()
    if not path.is_absolute():
        if not cwd:
            raise ResolveError("relative path %r with no cwd to resolve against" % raw)
        path = Path(cwd).expanduser() / path

    path = Path(os.path.normpath(str(path)))

    if path.suffix.lower() not in IMAGE_EXTS:
        raise ResolveError("not an image extension: %r" % path.suffix)
    if not path.exists():
        raise ResolveError("no such file: %s" % path)
    if path.is_dir():
        raise ResolveError("is a directory: %s" % path)
    return path
