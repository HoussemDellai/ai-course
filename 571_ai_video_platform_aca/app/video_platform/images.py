"""Validation and sanitization of user-uploaded reference photos."""

from __future__ import annotations

import warnings
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}
MAX_SIDE = 2048  # longest side after downscaling; Qwen-Image-Edit rescales to ~1 MP anyway
MAX_PIXELS = 50_000_000  # rejects decompression bombs before decoding


class ImageError(ValueError):
    status_code = 422


class ImageTooLarge(ImageError):
    status_code = 413


class UnsupportedImage(ImageError):
    status_code = 415


def sanitize_image(data: bytes, max_bytes: int) -> bytes:
    """Returns the photo as a clean PNG: EXIF orientation applied, metadata (GPS...) stripped,
    alpha flattened on white and the longest side capped at MAX_SIDE."""
    if not data:
        raise ImageError("The image is empty")
    if len(data) > max_bytes:
        raise ImageTooLarge(f"The image is larger than {max_bytes // (1024 * 1024)} MB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as probe:
                fmt = probe.format
                width, height = probe.size
                probe.verify()
            if fmt not in ALLOWED_FORMATS:
                raise UnsupportedImage(f"Unsupported image format {fmt or 'unknown'}: use PNG, JPEG or WebP")
            if width * height > MAX_PIXELS:
                raise ImageError(f"The image is too large ({width}x{height} pixels)")
            with Image.open(BytesIO(data)) as im:
                im.seek(0)  # first frame of animated PNG/WebP
                im = ImageOps.exif_transpose(im)
                if im.mode in ("RGBA", "LA", "P", "PA"):
                    im = im.convert("RGBA")
                    background = Image.new("RGB", im.size, (255, 255, 255))
                    background.paste(im, mask=im.getchannel("A"))
                    im = background
                else:
                    im = im.convert("RGB")
                im.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
                out = BytesIO()
                im.save(out, format="PNG", optimize=True)  # a new RGB image carries no EXIF/ICC/text chunks
                return out.getvalue()
    except ImageError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning) as e:
        raise UnsupportedImage("The file is not a valid PNG, JPEG or WebP image") from e
    except (OSError, SyntaxError, ValueError) as e:
        raise ImageError(f"The image could not be decoded: {e}") from e
