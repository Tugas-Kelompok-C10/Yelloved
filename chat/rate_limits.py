"""Rolling send limit shared by tabs and application workers."""
from contextlib import contextmanager
from datetime import timedelta
from math import ceil

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import Message, MessageSendQuota

MESSAGE_LIMIT = 30
MESSAGE_WINDOW = timedelta(minutes=1)


class MessageRateLimited(Exception):
    def __init__(self, retry_after):
        self.retry_after = retry_after
        self.message = (
            f'You have reached the limit of {MESSAGE_LIMIT} messages in 1 minute. '
            f'Please retry in {retry_after} second{"s" if retry_after != 1 else ""}. '
            'Your unsent message has been kept.'
        )
        super().__init__(self.message)


@contextmanager
def locked_send_quota(user):
    quota, _ = MessageSendQuota.objects.get_or_create(user=user)
    with transaction.atomic():
        # UPDATE locks on both PostgreSQL and SQLite, before counting sends.
        MessageSendQuota.objects.filter(pk=quota.pk).update(user_id=F('user_id'))
        yield


def check_message_limit(user):
    now = timezone.now()
    # Include soft-deleted messages: deleting a sent message cannot reset quota.
    oldest = Message.objects.filter(sender=user, created_at__gt=now - MESSAGE_WINDOW).order_by('created_at')
    timestamps = list(oldest.values_list('created_at', flat=True)[:MESSAGE_LIMIT])
    if len(timestamps) >= MESSAGE_LIMIT:
        raise MessageRateLimited(max(1, ceil((timestamps[0] + MESSAGE_WINDOW - now).total_seconds())))
