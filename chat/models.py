import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from .storage import ChatAttachmentStorage


def attachment_path(instance, filename):
    from pathlib import Path
    return f"{uuid.uuid4().hex}{Path(filename).suffix.lower()}"


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chats_first")
    second_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chats_second")
    created_at = models.DateTimeField(auto_now_add=True)
    sync_version = models.PositiveBigIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["first_user", "second_user"], name="chat_unique_pair"),
            models.CheckConstraint(condition=Q(first_user__lt=F("second_user")), name="chat_ordered_pair"),
        ]


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_messages")
    body = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(default=timezone.now)
    deleted_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    sync_version = models.PositiveBigIntegerField(default=0)
    created_version = models.PositiveBigIntegerField(default=0)
    attachment = models.FileField(storage=ChatAttachmentStorage(), upload_to=attachment_path, blank=True)
    attachment_name = models.CharField(max_length=180, blank=True)
    attachment_type = models.CharField(max_length=60, blank=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["conversation", "created_at"], name="chat_message_timeline"),
                   models.Index(fields=["conversation", "sync_version"], name="chat_message_changes")]
