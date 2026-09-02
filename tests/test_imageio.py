import io

import pytest
from PIL import Image

from imgpopup.imageio import load_png


def write(tmp_path, name, size, mode="RGB"):
    p = tmp_path / name
    Image.new(mode, size, (120, 30, 30) if mode == "RGB" else 0).save(p)
    return p


def test_returns_png_bytes_and_dimensions(tmp_path):
    p = write(tmp_path, "a.png", (200, 100))
    data, w, h = load_png(str(p), max_px_w=800)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert (w, h) == (200, 100)


def test_downscales_above_the_cap(tmp_path):
    p = write(tmp_path, "big.jpg", (4000, 2000))
    data, w, h = load_png(str(p), max_px_w=800)
    assert (w, h) == (800, 400)
    assert Image.open(io.BytesIO(data)).size == (800, 400)


def test_does_not_upscale_below_the_cap(tmp_path):
    p = write(tmp_path, "small.png", (50, 50))
    _, w, h = load_png(str(p), max_px_w=800)
    assert (w, h) == (50, 50)


def test_palette_images_survive(tmp_path):
    p = write(tmp_path, "pal.gif", (30, 30), mode="P")
    data, w, h = load_png(str(p), max_px_w=800)
    assert (w, h) == (30, 30)
    assert Image.open(io.BytesIO(data)).mode == "RGBA"


def test_unreadable_file_raises(tmp_path):
    p = tmp_path / "broken.png"
    p.write_bytes(b"not an image")
    with pytest.raises(Exception):
        load_png(str(p), max_px_w=800)
