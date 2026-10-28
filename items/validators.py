import re
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator


def validate_item_image(value):
    """Allow HTTP(S) user photos and a restricted local catalog asset path."""
    if re.fullmatch(r'/static/img/items/catalog/[a-z0-9-]+\.webp', value):
        return
    try:
        URLValidator(schemes=['http', 'https'])(value)
    except ValidationError as exc:
        raise ValidationError('Gunakan URL foto HTTP/HTTPS atau aset katalog lokal yang valid.') from exc


def validate_item_upload(value):
    if value.size > 5 * 1024 * 1024:
        raise ValidationError('Ukuran foto maksimal 5 MB.')
