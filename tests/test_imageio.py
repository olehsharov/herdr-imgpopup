import io

import numpy as np
import pytest
from PIL import Image

from imgpopup.imageio import MAX_PNG_BYTES, load_png


def write(tmp_path, name, size, mode="RGB"):
    p = tmp_path / name
    Image.new(mode, size, (120, 30, 30) if mode == "RGB" else 0).save(p)
    return p


def noise(tmp_path, name, size):
    """A photo-like image: random pixels do not compress, like a real photo."""
    rng = np.random.default_rng(0)
    arr = rng.integers(0, 255, (size[1], size[0], 3), dtype=np.uint8)
    p = tmp_path / name
    Image.fromarray(arr, "RGB").save(p)
    return p


def test_returns_png_bytes_and_dimensions(tmp_path):
    p = write(tmp_path, "a.png", (200, 100))
    data, w, h = load_png(str(p), max_px_w=800)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert (w, h) == (200, 100)


def test_downscales_above_the_pixel_cap(tmp_path):
    p = write(tmp_path, "big.jpg", (4000, 2000))
    data, w, h = load_png(str(p), max_px_w=800)
    assert (w, h) == (800, 400)
    assert Image.open(io.BytesIO(data)).size == (800, 400)


def test_does_not_upscale_below_the_cap(tmp_path):
    p = write(tmp_path, "small.png", (50, 50))
    _, w, h = load_png(str(p), max_px_w=800)
    assert (w, h) == (50, 50)


def test_opaque_image_encodes_as_rgb(tmp_path):
    p = write(tmp_path, "pal.gif", (30, 30), mode="P")
    data, w, h = load_png(str(p), max_px_w=800)
    assert (w, h) == (30, 30)
    assert Image.open(io.BytesIO(data)).mode == "RGB"


def test_transparent_image_keeps_alpha(tmp_path):
    p = tmp_path / "t.png"
    Image.new("RGBA", (30, 30), (255, 0, 0, 128)).save(p)
    data, _, _ = load_png(str(p), max_px_w=800)
    out = Image.open(io.BytesIO(data))
    assert out.mode == "RGBA"
    assert out.getpixel((0, 0))[3] == 128


def test_photo_is_shrunk_to_fit_the_byte_budget(tmp_path):
    """The bug that left the pane empty: a photo under the pixel cap but over
    Herdr's 1 MiB request limit."""
    p = noise(tmp_path, "photo.png", (1200, 900))
    raw = p.stat().st_size
    assert raw > MAX_PNG_BYTES            # the fixture really is over budget
    data, w, h = load_png(str(p), max_px_w=8000)
    assert len(data) <= MAX_PNG_BYTES
    assert w < 1200 and h < 900
    assert abs((w / h) - (1200 / 900)) < 0.02


def test_byte_budget_is_configurable(tmp_path):
    p = noise(tmp_path, "photo.png", (600, 400))
    data, w, h = load_png(str(p), max_px_w=8000, max_bytes=100_000)
    assert len(data) <= 100_000


def test_unreadable_file_raises(tmp_path):
    p = tmp_path / "broken.png"
    p.write_bytes(b"not an image")
    with pytest.raises(Exception):
        load_png(str(p), max_px_w=800)
