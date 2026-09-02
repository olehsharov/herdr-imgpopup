from imgpopup.input import InputParser


def keys(data):
    return InputParser().feed(data)


def test_plain_keys():
    assert keys(b"q") == [("key", "q")]
    assert keys(b"+-") == [("key", "+"), ("key", "-")]


def test_plain_and_modified_arrows():
    assert keys(b"\x1b[A") == [("key", "up")]
    assert keys(b"\x1b[1;6D") == [("key", "left")]          # ctrl+shift+left
    assert keys(b"\x1b[1;5C\x1b[B") == [("key", "right"), ("key", "down")]


def test_lone_escape_needs_flush():
    p = InputParser()
    assert p.feed(b"\x1b") == []
    assert p.flush() == [("key", "escape")]


def test_sequence_split_across_reads():
    p = InputParser()
    assert p.feed(b"\x1b[1;") == []
    assert p.feed(b"6A") == [("key", "up")]


def test_page_keys_zoom():
    assert keys(b"\x1b[5~") == [("key", "zoom_in")]
    assert keys(b"\x1b[6~") == [("key", "zoom_out")]


def test_kitty_keyboard_protocol_zoom_keys():
    assert keys(b"\x1b[61;6u") == [("key", "zoom_in")]       # ctrl+shift+=
    assert keys(b"\x1b[45;5u") == [("key", "zoom_out")]      # ctrl+-
    assert keys(b"\x1b[113u") == [("key", "q")]


def test_sgr_wheel_with_and_without_modifiers():
    assert keys(b"\x1b[<64;10;5M") == [("wheel", "in", 10, 5)]
    assert keys(b"\x1b[<65;10;5M") == [("wheel", "out", 10, 5)]
    assert keys(b"\x1b[<84;3;4M") == [("wheel", "in", 3, 4)]  # ctrl+shift+wheel up


def test_drag_press_move_release():
    p = InputParser()
    assert p.feed(b"\x1b[<0;10;10M") == []                 # press
    assert p.feed(b"\x1b[<32;13;11M") == [("drag", 3, 1)]  # motion with button held
    assert p.feed(b"\x1b[<32;13;11M") == []                # no movement, no event
    assert p.feed(b"\x1b[<0;13;11m") == []                 # release
    assert p.feed(b"\x1b[<32;20;20M") == []                # motion without press: ignored


def test_unknown_csi_is_dropped_not_crashed():
    assert keys(b"\x1b[?1;2c") == []
