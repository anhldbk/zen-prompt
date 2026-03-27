from __future__ import annotations

import random
from pathlib import Path

ARTS_DIR = Path(__file__).resolve().parent
PHOTO_DIR = ARTS_DIR.parent.parent / "photos"
DEFAULT_PHOTO_TOPIC = "monochrome"
SUPPORTED_PHOTO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
TERMINAL_CELL_HEIGHT_WIDTH_RATIO = 2.0


def _get_topic_dir(photo_topic: str) -> Path:
    return PHOTO_DIR / photo_topic


def _get_topic_image_paths(photo_topic: str) -> list[Path]:
    topic_dir = _get_topic_dir(photo_topic)
    if not topic_dir.is_dir():
        raise ValueError(f"Photo topic not found: {photo_topic}")

    image_paths = sorted(
        path
        for path in topic_dir.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_PHOTO_EXTENSIONS
    )
    if not image_paths:
        raise ValueError(f"No image files found for photo topic: {photo_topic}")

    return image_paths


def get_random_photo_for_topic(photo_topic: str = DEFAULT_PHOTO_TOPIC) -> Path:
    return random.choice(_get_topic_image_paths(photo_topic))


def get_photo_topic(photo: str) -> str:
    if photo.startswith("topic@"):
        return photo[6:]

    raise ValueError("Photo topic is only available for image-based photo modes")


def _fit_image_size(
    image_width: int,
    image_height: int,
    max_width: int,
    max_height: int,
    cell_height_width_ratio: float = TERMINAL_CELL_HEIGHT_WIDTH_RATIO,
) -> tuple[int, int]:
    if image_width <= 0 or image_height <= 0:
        raise ValueError("Image dimensions must be positive")

    if cell_height_width_ratio <= 0:
        raise ValueError("Terminal cell ratio must be positive")

    scale = min(
        (max_width / cell_height_width_ratio) / image_width,
        max_height / image_height,
    )
    scale = max(scale, 0)
    fitted_width = max(1, int(image_width * scale * cell_height_width_ratio))
    fitted_height = max(1, int(image_height * scale))
    fitted_width = min(fitted_width, max_width)
    fitted_height = min(fitted_height, max_height)
    return fitted_width, fitted_height


def validate_photo_mode(photo: str) -> str:
    if photo == "":
        return photo

    if photo.startswith("topic@"):
        photo_topic = photo[6:]
        if not photo_topic:
            raise ValueError("Photo topic cannot be empty")
        _get_topic_image_paths(photo_topic)
        return photo

    if photo.startswith("file@"):
        image_path = Path(photo[5:]).expanduser()
        if not image_path.is_file():
            raise ValueError(f"Photo file not found: {image_path}")
        return f"file@{image_path}"

    raise ValueError("Photo mode must be one of: empty, topic@<name>, file@<path>")


def _prepare_terminal_image(source_image):
    has_transparency = (
        "transparency" in source_image.info
        or source_image.mode in {"RGBA", "LA"}
        or (source_image.mode == "P" and "transparency" in source_image.info)
    )
    if has_transparency:
        return source_image.convert("RGBA")

    if source_image.mode in {"RGB", "L"}:
        return source_image.copy()

    return source_image.convert("RGB")


def get_photo_renderable(
    photo: str,
    image_max_height: int = 10,
    image_max_width: int | None = None,
    console=None,
):
    photo = validate_photo_mode(photo)
    if photo == "":
        return None

    from rich.console import Console
    from PIL import Image as PILImage
    from textual_image.renderable import Image

    console = console or Console()
    max_width = image_max_width or console.width
    image_source = (
        get_random_photo_for_topic(get_photo_topic(photo))
        if photo.startswith("topic@")
        else Path(photo[5:])
    )

    with PILImage.open(image_source) as source_image:
        prepared_image = _prepare_terminal_image(source_image)
        fitted_width, fitted_height = _fit_image_size(
            prepared_image.width,
            prepared_image.height,
            max_width,
            image_max_height,
        )
        return Image(prepared_image, width=fitted_width, height=fitted_height)


def render_photo(
    photo: str,
    image_max_height: int = 10,
    image_max_width: int | None = None,
    console=None,
) -> None:
    renderable = get_photo_renderable(
        photo,
        image_max_height=image_max_height,
        image_max_width=image_max_width,
        console=console,
    )
    if renderable is None:
        return

    from rich.console import Console

    console = console or Console()
    console.print(renderable)
