import warnings

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError


MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_DIMENSION = 4096


def validate_reference_image(value):
    """Validate uploaded bytes before Django decodes an image for the form."""
    if getattr(value, "_committed", False):
        return  # Editing without a replacement retains the existing stored image.
    if value.size > MAX_IMAGE_BYTES:
        raise ValidationError("Image size must not exceed 5 MB.", code="image_size")

    position = value.tell()
    try:
        value.seek(0)
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(value) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValidationError(
                        "Please upload a JPG, JPEG, PNG, or WEBP image.",
                        code="image_format",
                    )
                if max(image.size) > MAX_IMAGE_DIMENSION:
                    raise ValidationError(
                        "Image dimensions must not exceed 4096 × 4096 pixels.",
                        code="image_dimensions",
                    )
                image.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError,
            Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ValidationError(
            "Please upload a valid image.", code="invalid_image"
        ) from error
    finally:
        value.seek(position)
