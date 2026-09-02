from imgpopup.state import ViewerState


def make(img_w=1000, img_h=500, cols=80, rows=40):
    return ViewerState(img_w, img_h, cols, rows)


def test_starts_at_fit_zoom_one():
    s = make()
    assert s.zoom == 1.0
    cols, rows, _, _ = s.placement()
    assert (cols, rows) == (80, 20)


def test_plus_zooms_in_and_asks_for_redraw():
    s = make()
    assert s.handle("+") == "redraw"
    assert s.zoom > 1.0


def test_minus_zooms_out():
    s = make()
    s.handle("-")
    assert s.zoom < 1.0


def test_q_quits():
    assert make().handle("q") == "quit"


def test_escape_quits():
    assert make().handle("\x1b") == "quit"


def test_unknown_key_is_ignored():
    s = make()
    assert s.handle("z") == "ignore"
    assert s.zoom == 1.0


def test_zero_resets_zoom_and_pan():
    s = make()
    s.handle("+")
    s.handle("l")
    s.handle("j")
    s.handle("0")
    assert s.zoom == 1.0 and s.pan_x == 0 and s.pan_y == 0


def test_pan_is_clamped_at_fit():
    s = make()
    for _ in range(50):
        s.handle("l")
    cols, _, col, _ = s.placement()
    assert col <= max(0, s.pane_cols - cols)


def test_zoomed_in_image_can_pan_negative():
    s = make()
    for _ in range(8):
        s.handle("+")            # image now much wider than the pane
    for _ in range(20):
        s.handle("l")            # scroll right
    _, _, col, _ = s.placement()
    assert col < 0


def test_pan_cannot_push_image_off_pane():
    s = make()
    for _ in range(8):
        s.handle("+")
    for _ in range(999):
        s.handle("l")
    cols, _, col, _ = s.placement()
    assert col >= s.pane_cols - cols


def test_placement_preserves_aspect_across_zoom():
    s = make(1000, 500)
    c1, r1, _, _ = s.placement()
    s.handle("+")
    c2, r2, _, _ = s.placement()
    assert abs((c1 / r1) - (c2 / r2)) < 0.15


def test_load_new_image_resets_view():
    s = make()
    s.handle("+")
    s.handle("l")
    s.load(400, 400)
    assert s.zoom == 1.0 and s.pan_x == 0 and s.pan_y == 0
    assert s.img_w == 400


def test_resize_updates_placement():
    s = make()
    s.resize(40, 20)
    cols, rows, _, _ = s.placement()
    assert cols <= 40 and rows <= 20


def test_dot_switches_to_one_to_one():
    s = make(1000, 500)
    assert s.handle(".") == "redraw"
    assert s.one_to_one is True
