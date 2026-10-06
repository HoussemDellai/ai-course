from io import BytesIO

import pytest
from PIL import Image

from fakes import make_png
from video_platform.images import MAX_SIDE, ImageError, ImageTooLarge, UnsupportedImage, sanitize_image

MB = 1024 * 1024


def decode(data: bytes) -> Image.Image:
    im = Image.open(BytesIO(data))
    im.load()
    return im


@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "WEBP"])
def test_accepted_formats_become_png(fmt):
    im = decode(sanitize_image(make_png(320, 200, fmt=fmt), 10 * MB))
    assert im.format == "PNG" and im.mode == "RGB" and im.size == (320, 200)


def test_exif_orientation_is_applied_and_metadata_stripped():
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90° clockwise to display
    exif[0x010F] = "SecretCam"
    exif[0x8825] = {2: (48.0, 51.0, 24.0)}  # GPS latitude
    src = BytesIO()
    Image.new("RGB", (300, 100), (10, 200, 30)).save(src, format="JPEG", exif=exif)
    out = sanitize_image(src.getvalue(), 10 * MB)
    im = decode(out)
    assert im.size == (100, 300), "portrait after applying the orientation"
    assert not im.getexif() and b"SecretCam" not in out and "exif" not in im.info


def test_transparency_is_flattened_on_white():
    src = BytesIO()
    Image.new("RGBA", (10, 10), (255, 0, 0, 0)).save(src, format="PNG")
    im = decode(sanitize_image(src.getvalue(), 10 * MB))
    assert im.mode == "RGB" and im.getpixel((5, 5)) == (255, 255, 255)


def test_large_photos_are_downscaled():
    im = decode(sanitize_image(make_png(4000, 3000, fmt="JPEG"), 10 * MB))
    assert max(im.size) == MAX_SIDE and im.size == (MAX_SIDE, 1536)


def test_rejections():
    with pytest.raises(ImageTooLarge) as e:
        sanitize_image(make_png(64, 64), 10)
    assert e.value.status_code == 413
    with pytest.raises(UnsupportedImage) as e:
        sanitize_image(b"definitely not an image", MB)
    assert e.value.status_code == 415
    with pytest.raises(UnsupportedImage, match="GIF"):
        sanitize_image(make_png(10, 10, fmt="GIF"), MB)
    with pytest.raises(ImageError):
        sanitize_image(b"", MB)
    with pytest.raises(ImageError):
        sanitize_image(make_png(64, 64)[:60], MB)  # truncated PNG
