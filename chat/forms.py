from django import forms
from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError
import warnings


def validate_attachment(upload):
    if upload.size > 5 * 1024 * 1024:
        raise ValidationError("Attachments must not exceed 5 MB.")
    name = upload.name.replace("\\", "/").split("/")[-1]
    suffix = name.rsplit(".", 1)[-1].lower()
    types = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp", "pdf": "application/pdf", "txt": "text/plain"}
    if suffix not in types:
        raise ValidationError("Choose a JPG, PNG, WEBP, PDF, or TXT file.")
    try:
        if suffix in ("jpg", "jpeg", "png", "webp"):
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(upload) as image:
                    if max(image.size) > 4096:
                        raise ValidationError("Image dimensions must not exceed 4096 × 4096 pixels.")
                    expected = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}[suffix]
                    if image.format != expected:
                        raise ValidationError("The image content does not match its file extension.")
                    image.verify()
        elif suffix == "pdf" and not upload.read(5).startswith(b"%PDF-"):
            raise ValidationError("Please choose a valid PDF file.")
        elif suffix == "txt":
            content = upload.read().decode("utf-8")
            if "\x00" in content:
                raise ValidationError("Please choose a UTF-8 text file.")
    except (UnidentifiedImageError, OSError, UnicodeError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ValidationError("The attachment is not a valid supported file.") from error
    finally:
        upload.seek(0)
    upload.chat_content_type = types[suffix]
    upload.chat_display_name = name[:180]
    return upload


class MessageForm(forms.Form):
    body = forms.CharField(max_length=1000, strip=True, required=False)
    client_id = forms.UUIDField()
    attachment = forms.FileField(required=False, validators=[validate_attachment])

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("body") and not cleaned.get("attachment"):
            raise ValidationError("Write a message or attach a file before sending.")
        return cleaned


class MessageEditForm(forms.Form):
    body = forms.CharField(max_length=1000, strip=True)
    revision = forms.DateTimeField()
