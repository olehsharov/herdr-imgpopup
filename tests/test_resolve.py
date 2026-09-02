import pytest

from imgpopup.resolve import ResolveError, resolve


@pytest.fixture
def img(tmp_path):
    p = tmp_path / "rim.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n")
    return p


def test_absolute_path(img):
    assert resolve(str(img)) == img


def test_relative_path_uses_cwd(img):
    assert resolve("rim.png", cwd=str(img.parent)) == img


def test_relative_path_without_cwd_is_rejected(img):
    with pytest.raises(ResolveError):
        resolve("rim.png", cwd=None)


def test_tilde_is_expanded(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "car.jpg").write_bytes(b"x")
    assert resolve("~/car.jpg") == tmp_path / "car.jpg"


def test_surrounding_quotes_are_stripped(img):
    assert resolve('"%s"' % img) == img


def test_file_url_is_accepted(img):
    assert resolve("file://%s" % img) == img


def test_percent_escapes_in_file_url(tmp_path):
    p = tmp_path / "my rim.png"
    p.write_bytes(b"x")
    assert resolve("file://%s/my%%20rim.png" % tmp_path) == p


def test_uppercase_extension_is_accepted(tmp_path):
    p = tmp_path / "RIM.PNG"
    p.write_bytes(b"x")
    assert resolve(str(p)) == p


def test_non_image_extension_is_rejected(tmp_path):
    p = tmp_path / "notes.txt"
    p.write_bytes(b"x")
    with pytest.raises(ResolveError):
        resolve(str(p))


def test_missing_file_is_rejected(tmp_path):
    with pytest.raises(ResolveError):
        resolve(str(tmp_path / "ghost.png"))


def test_directory_is_rejected(tmp_path):
    d = tmp_path / "pics.png"
    d.mkdir()
    with pytest.raises(ResolveError):
        resolve(str(d))


def test_empty_input_is_rejected():
    with pytest.raises(ResolveError):
        resolve("   ")


def test_traversal_is_normalised(img):
    weird = "%s/../%s/rim.png" % (img.parent, img.parent.name)
    assert resolve(weird) == img
