import pytest

from imgpopup import geometry as g


def test_fit_uses_full_width_when_image_is_wide():
    assert g.fit(1000, 500, pane_cols=80, pane_rows=40) == (80, 20)


def test_fit_falls_back_to_height_when_image_is_tall():
    cols, rows = g.fit(500, 2000, pane_cols=80, pane_rows=40)
    assert (cols, rows) == (20, 40)


def test_fit_never_returns_zero():
    cols, rows = g.fit(4000, 1, pane_cols=10, pane_rows=10)
    assert cols >= 1 and rows >= 1


def test_fit_rejects_degenerate_image():
    with pytest.raises(ValueError):
        g.fit(0, 100, 80, 24)


def test_clamp_zoom_bounds():
    assert g.clamp_zoom(100.0) == 8.0
    assert g.clamp_zoom(0.0001) == 0.1
    assert g.clamp_zoom(1.5) == 1.5


def test_clamp_pan_pins_small_image_inside_pane():
    assert g.clamp_pan(size=20, pane_size=80, offset=-5) == 0
    assert g.clamp_pan(size=20, pane_size=80, offset=999) == 60


def test_clamp_pan_allows_negative_scroll_for_large_image():
    assert g.clamp_pan(size=200, pane_size=80, offset=5) == 0
    assert g.clamp_pan(size=200, pane_size=80, offset=-999) == -120


def test_popup_size_respects_cap():
    w, h = g.popup_size(4000, 100, term_cols=200, term_rows=50)
    assert w.endswith("%") and h.endswith("%")
    assert int(w.rstrip("%")) <= 90 and int(h.rstrip("%")) <= 90


def test_popup_size_is_never_zero_percent():
    w, h = g.popup_size(1, 4000, term_cols=200, term_rows=50)
    assert int(w.rstrip("%")) >= 1 and int(h.rstrip("%")) >= 1


def test_encode_cap_never_upscales():
    assert g.encode_cap(100, 50, popup_px_w=800) == (100, 50)


def test_encode_cap_downscales_preserving_aspect():
    assert g.encode_cap(8000, 4000, popup_px_w=800, factor=4) == (3200, 1600)


def test_split_cells_covers_exactly_with_near_equal_sizes():
    spans = g.split_cells(257, 3)
    assert spans == [(0, 86), (86, 86), (172, 85)]
    assert sum(n for _, n in spans) == 257


def test_split_cells_never_more_parts_than_cells():
    assert g.split_cells(2, 4) == [(0, 1), (1, 1)]
    assert g.split_cells(5, 1) == [(0, 5)]


def test_tile_count_grows_with_zoom_and_caps():
    assert g.tile_count(1.0) == 2
    assert g.tile_count(1.9) == 2
    assert g.tile_count(2.0) == 3
    assert g.tile_count(4.0) == 4
    assert g.tile_count(32.0) == 4
