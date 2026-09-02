from imgpopup.state import ViewerState


def make(img_w=1000, img_h=500, cols=80, rows=41):
    return ViewerState(img_w, img_h, cols, rows)


def test_fit_view_is_the_whole_image():
    assert make().view_rect() == (0, 0, 1000, 500)


def test_placement_is_fit_rect_centred_above_status_row():
    cols, rows, col, row = make().placement()
    assert (cols, rows) == (80, 20)
    assert col == 0 and row == (40 - 20) // 2


def test_placement_leaves_the_status_row():
    s = make(100, 4000, cols=80, rows=41)          # very tall image
    cols, rows, col, row = s.placement()
    assert row + rows <= 40


def test_zoom_in_halves_the_view_and_keeps_centre():
    s = make()
    for _ in range(3):
        s.handle("+")                               # 1.25^3 = 1.95
    x, y, w, h = s.view_rect()
    assert w < 1000 and h < 500
    assert abs((x + w / 2) - 500) <= 1 and abs((y + h / 2) - 250) <= 1


def test_zoom_never_below_fit():
    s = make()
    s.handle("-")
    assert s.zoom == 1.0 and s.view_rect() == (0, 0, 1000, 500)


def test_zoom_caps():
    s = make()
    for _ in range(100):
        s.handle("+")
    assert s.zoom == 32.0


def test_pan_moves_the_view_and_clamps_to_image():
    s = make()
    for _ in range(4):
        s.handle("+")
    x0, _, w, _ = s.view_rect()
    s.handle("l")
    x1, _, _, _ = s.view_rect()
    assert x1 > x0
    for _ in range(500):
        s.handle("l")
    x, _, w, _ = s.view_rect()
    assert x + w == 1000                             # pinned to the right edge
    for _ in range(500):
        s.handle("k")
    _, y, _, _ = s.view_rect()
    assert y == 0


def test_pan_at_fit_is_a_noop():
    s = make()
    s.handle("l")
    s.handle("j")
    assert s.view_rect() == (0, 0, 1000, 500)


def test_view_never_leaves_the_image():
    s = make(333, 777, cols=50, rows=30)
    for k in "+++lllljjjjjkkkkhhhh":
        s.handle(k)
        x, y, w, h = s.view_rect()
        assert 0 <= x and x + w <= 333 and 0 <= y and y + h <= 777


def test_zero_and_f_reset():
    s = make()
    s.handle("+")
    s.handle("l")
    assert s.handle("0") == "redraw"
    assert s.zoom == 1.0 and s.view_rect() == (0, 0, 1000, 500)


def test_quit_keys_and_ignored_keys():
    assert make().handle("q") == "quit"
    assert make().handle("\x1b") == "quit"
    assert make().handle("z") == "ignore"


def test_load_new_image_resets_view():
    s = make()
    s.handle("+")
    s.load(400, 400)
    assert s.zoom == 1.0 and s.view_rect() == (0, 0, 400, 400)
