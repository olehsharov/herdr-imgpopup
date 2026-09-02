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


from imgpopup.imageio import encode_tiles, open_image


def test_tiles_cover_the_placement_and_overlap_neighbours_by_one_cell(tmp_path):
    p = noise(tmp_path, "photo.png", (1200, 900))
    img = open_image(str(p))
    tiles = encode_tiles(img, (0, 0, 1200, 900), cols=257, rows=96, col=3, row=1, k=3)
    assert len(tiles) == 9
    covered = set()
    for t in tiles:
        for c in range(t.col, t.col + t.cols):
            for r in range(t.row, t.row + t.rows):
                covered.add((c, r))
    assert covered == {(c, r) for c in range(3, 260) for r in range(1, 97)}
    by = {t.layer: t for t in tiles}
    # a tile with a right neighbour extends one cell into it; the last column does not
    assert by["img-0"].cols == 86 + 1 and by["img-2"].cols == 85
    assert by["img-0"].rows == 32 + 1 and by["img-6"].rows == 32
    # right/bottom neighbours draw on top
    assert by["img-1"].z > by["img-0"].z and by["img-3"].z > by["img-0"].z


def test_every_tile_is_under_budget_and_tiles_beat_one_png(tmp_path):
    p = noise(tmp_path, "photo.png", (1600, 1200))
    img = open_image(str(p))
    tiles = encode_tiles(img, (0, 0, 1600, 1200), 200, 100, 0, 0, k=3, max_bytes=200_000)
    assert all(len(t.png) <= 200_000 for t in tiles)
    single, w, h = load_png(str(p), max_px_w=8000, max_bytes=200_000)
    assert sum(t.width * t.height for t in tiles) > 3 * w * h


def test_zoomed_view_encodes_only_the_crop(tmp_path):
    p = noise(tmp_path, "photo.png", (1000, 1000))
    img = open_image(str(p))
    tiles = encode_tiles(img, (400, 400, 200, 200), 100, 50, 0, 0, k=2)
    assert len(tiles) == 4
    # 200x200 source at k=2 -> each tile ~100 px wide (+1 overlap cell = 2 px), never upscaled
    assert all(t.width <= 103 for t in tiles)


def test_tile_layers_are_stable_names(tmp_path):
    p = write(tmp_path, "a.png", (64, 64))
    tiles = encode_tiles(open_image(str(p)), (0, 0, 64, 64), 20, 10, 0, 0, k=2)
    assert [t.layer for t in tiles] == ["img-0", "img-1", "img-2", "img-3"]


def test_sink_receives_every_tile_as_it_is_encoded(tmp_path):
    p = write(tmp_path, "a.png", (64, 64))
    seen = []
    tiles = encode_tiles(open_image(str(p)), (0, 0, 64, 64), 20, 10, 0, 0, k=2,
                         sink=lambda t: seen.append(t.layer))
    assert sorted(seen) == sorted(t.layer for t in tiles) == ["img-0", "img-1", "img-2", "img-3"]


def test_sink_errors_propagate(tmp_path):
    p = write(tmp_path, "a.png", (64, 64))
    def boom(t):
        raise RuntimeError("socket gone")
    with pytest.raises(RuntimeError):
        encode_tiles(open_image(str(p)), (0, 0, 64, 64), 20, 10, 0, 0, k=2, sink=boom)
