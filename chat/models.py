import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chats_first")
    second_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chats_second")
    created_at = models.DateTimeField(auto_now_add=True)

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

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["conversation", "created_at"], name="chat_message_timeline")]
