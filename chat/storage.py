from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class ChatAttachmentStorage(FileSystemStorage):
    """Private files must never be exposed through public MEDIA_URL/WhiteNoise."""
    def __init__(self):
        super().__init__(location=getattr(settings, "CHAT_ATTACHMENT_ROOT", Path(settings.BASE_DIR) / "private_chat_files"))
