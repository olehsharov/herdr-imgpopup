import pytest

from imgpopup.state import ViewerState


def make(img_w=1000, img_h=500, cols=80, rows=41, cell_w=8, cell_h=16):
    return ViewerState(img_w, img_h, cols, rows, cell_w, cell_h)


def test_fit_view_is_the_whole_image_when_aspects_match():
    assert make().view_rect() == (0.0, 0.0, 1000.0, 500.0)


def test_view_aspect_equals_placement_pixel_aspect():
    s = make(1600, 1200, cols=293, rows=100, cell_w=14, cell_h=25)
    cols, rows, _, _ = s.placement()
    _, _, w, h = s.view_rect()
    assert w / h == pytest.approx((cols * 14) / (rows * 25), rel=1e-9)
    assert w <= 1600 and h <= 1200 and (w == 1600 or h == 1200)


def test_placement_uses_real_cell_ratio():
    wide = make(1000, 500, cols=80, rows=41, cell_w=8, cell_h=16).placement()
    tall = make(1000, 500, cols=80, rows=41, cell_w=14, cell_h=25).placement()
    assert wide[:2] == (80, 20)
    assert tall[:2] == (80, 22)                  # 80 * 0.5 * (14/25) = 22.4


def test_placement_is_centred_above_status_row():
    cols, rows, col, row = make().placement()
    assert col == 0 and row == (40 - rows) // 2
    s = make(100, 4000, cols=80, rows=41)
    cols, rows, col, row = s.placement()
    assert row + rows <= 40


def test_zoom_in_shrinks_the_view_and_keeps_centre():
    s = make()
    for _ in range(3):
        s.handle("+")
    x, y, w, h = s.view_rect()
    assert w < 1000 and h < 500
    assert x + w / 2 == pytest.approx(500) and y + h / 2 == pytest.approx(250)


def test_zoom_never_below_fit_and_reports_ignore():
    s = make()
    assert s.handle("-") == "ignore"
    assert s.zoom == 1.0


def test_zoom_caps():
    s = make()
    for _ in range(100):
        s.handle("+")
    assert s.zoom == 32.0
    assert s.handle("+") == "ignore"


def test_zoom_at_keeps_the_point_under_the_pointer_fixed():
    s = make()
    x, y, w, h = s.view_rect()
    px, py = x + 0.8 * w, y + 0.2 * h                  # pointer at 80%,20% of the view
    assert s.zoom_at(2.0, 0.8, 0.2)
    x2, y2, w2, h2 = s.view_rect()
    assert x2 + 0.8 * w2 == pytest.approx(px, abs=1e-6)
    assert y2 + 0.2 * h2 == pytest.approx(py, abs=1e-6)


def test_zoom_at_edge_clamps_inside_image():
    s = make()
    s.zoom_at(4.0, 1.0, 1.0)                           # pointer at bottom-right corner
    x, y, w, h = s.view_rect()
    assert x + w <= 1000 + 1e-9 and y + h <= 500 + 1e-9


def test_arrow_and_hjkl_pan_and_clamp():
    s = make()
    for _ in range(4):
        s.handle("+")
    x0 = s.view_rect()[0]
    assert s.handle("right") == "redraw"
    assert s.view_rect()[0] > x0
    for _ in range(500):
        s.handle("l")
    x, _, w, _ = s.view_rect()
    assert x + w == pytest.approx(1000)
    for _ in range(500):
        s.handle("up")
    assert s.view_rect()[1] == pytest.approx(0)


def test_pan_at_fit_is_ignored():
    s = make()
    assert s.handle("left") == "ignore"
    assert s.handle("j") == "ignore"


def test_drag_moves_the_image_with_the_pointer():
    s = make()
    for _ in range(4):
        s.handle("+")
    x0 = s.view_rect()[0]
    s.drag(+10, 0)                                     # pointer moved right
    assert s.view_rect()[0] < x0                       # view moved left: image follows pointer


def test_view_never_leaves_the_image():
    s = make(333, 777, cols=50, rows=30, cell_w=14, cell_h=25)
    for k in "+++lllljjjjjkkkkhhhh":
        s.handle(k)
        x, y, w, h = s.view_rect()
        assert -1e-9 <= x and x + w <= 333 + 1e-9 and -1e-9 <= y and y + h <= 777 + 1e-9


def test_zero_and_f_reset():
    s = make()
    s.handle("+")
    s.handle("l")
    assert s.handle("0") == "redraw"
    assert s.zoom == 1.0 and s.view_rect() == (0.0, 0.0, 1000.0, 500.0)


def test_quit_keys_and_ignored_keys():
    assert make().handle("q") == "quit"
    assert make().handle("escape") == "quit"
    assert make().handle("z") == "ignore"


def test_load_new_image_resets_view():
    s = make()
    s.handle("+")
    s.load(400, 400)
    assert s.zoom == 1.0 and s.view_rect()[2:] == (400.0, 400.0)
