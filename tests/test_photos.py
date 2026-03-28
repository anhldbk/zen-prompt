from unittest.mock import patch
import io
import sys

from PIL import Image as PILImage

from zen_prompt.commands.arts import (
    _fit_image_size,
    _get_textual_image,
    _prepare_terminal_image,
    get_photo_topic,
    get_random_photo_for_topic,
    render_photo,
)


class DummyConsole:
    def __init__(self, width=80):
        self.width = width
        self.printed = []

    def print(self, value):
        self.printed.append(value)


def test_fit_image_size_preserves_ratio():
    fitted_width, fitted_height = _fit_image_size(240, 120, 80, 10)
    assert (fitted_width, fitted_height) == (40, 10)


def test_fit_image_size_respects_width_limit():
    fitted_width, fitted_height = _fit_image_size(300, 100, 15, 10)
    assert (fitted_width, fitted_height) == (15, 2)


def test_render_photo_uses_proportional_dimensions_for_file(tmp_path):
    image_path = tmp_path / "wide.png"
    PILImage.new("RGB", (200, 100), "red").save(image_path)
    console = DummyConsole(width=80)

    with patch(
        "textual_image.renderable.Image",
        side_effect=lambda image, width, height: {
            "image": image,
            "width": width,
            "height": height,
        },
    ):
        render_photo(
            f"file@{image_path}",
            image_max_height=10,
            image_max_width=80,
            console=console,
        )

    assert console.printed
    assert console.printed[0]["width"] == 40
    assert console.printed[0]["height"] == 10


def test_prepare_terminal_image_preserves_rgba_transparency():
    image = PILImage.new("RGBA", (4, 4), (255, 0, 0, 0))

    prepared = _prepare_terminal_image(image)

    assert prepared.mode == "RGBA"
    assert prepared.getpixel((0, 0))[3] == 0


def test_prepare_terminal_image_converts_palette_transparency_to_rgba():
    image = PILImage.new("P", (2, 2))
    image.putpalette(
        [
            255,
            0,
            0,
            0,
            255,
            0,
        ]
        + [0, 0, 0] * 254
    )
    image.info["transparency"] = 0

    prepared = _prepare_terminal_image(image)

    assert prepared.mode == "RGBA"


def test_get_random_photo_for_topic_picks_file_from_topic_dir(tmp_path):
    topic_dir = tmp_path / "monochrome"
    topic_dir.mkdir()
    first = topic_dir / "a.png"
    second = topic_dir / "b.jpg"
    first.write_bytes(b"png")
    second.write_bytes(b"jpg")

    with (
        patch("zen_prompt.commands.arts.PHOTO_DIR", tmp_path),
        patch(
            "zen_prompt.commands.arts.random.choice",
            side_effect=lambda paths: paths[-1],
        ),
    ):
        chosen = get_random_photo_for_topic("monochrome")

    assert chosen == second


def test_get_random_photo_for_topic_rejects_missing_topic(tmp_path):
    with patch("zen_prompt.commands.arts.PHOTO_DIR", tmp_path):
        try:
            get_random_photo_for_topic("missing")
        except ValueError as exc:
            assert str(exc) == "Photo topic not found: missing"
        else:
            raise AssertionError("Expected ValueError for missing photo topic")


def test_get_photo_topic_uses_default_for_image():
    try:
        get_photo_topic("image")
    except ValueError as exc:
        assert str(exc) == "Photo topic is only available for image-based photo modes"
    else:
        raise AssertionError("Expected ValueError for non-topic photo mode")


def test_get_photo_topic_reads_topic_mode():
    assert get_photo_topic("topic@monochrome") == "monochrome"


def test_get_textual_image_uses_dev_tty_when_stdin_is_piped():
    original_stdin = sys.__stdin__

    class FakePipe(io.StringIO):
        def isatty(self):
            return False

    class FakeTty(io.StringIO):
        def isatty(self):
            return True

    fake_pipe = FakePipe()
    fake_tty = FakeTty()

    with (
        patch("builtins.open", return_value=fake_tty) as mock_open,
        patch.dict(
            "sys.modules",
            {"textual_image.renderable": type("Module", (), {"Image": object})()},
        ),
    ):
        sys.__stdin__ = fake_pipe
        try:
            image_cls = _get_textual_image()
        finally:
            sys.__stdin__ = original_stdin

    assert image_cls is object
    mock_open.assert_called_once_with("/dev/tty", "r")
    assert sys.__stdin__ is original_stdin
