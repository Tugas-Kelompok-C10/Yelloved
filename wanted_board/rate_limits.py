"""Database-backed rolling limit for successful Wanted post creations."""
from datetime import timedelta
from math import ceil

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import WantedCreationEvent, WantedCreationQuota, WantedPost

POST_LIMIT = 5
POST_WINDOW = timedelta(minutes=10)


class CreationRateLimited(Exception):
    def __init__(self, retry_after):
        self.retry_after = retry_after
        minutes = ceil(retry_after / 60)
        self.message = (
            "You have reached the limit of 5 wanted posts in 10 minutes. "
            f"Please try again in {minutes} minute{'s' if minutes != 1 else ''}. "
            "Your form details have been kept."
        )
        super().__init__(self.message)


def create_with_quota(user, uid, defaults):
    # Initialize outside the quota transaction: its first statement must be a
    # write, including on SQLite where SELECT FOR UPDATE has no effect.
    quota, _ = WantedCreationQuota.objects.get_or_create(user=user)
    with transaction.atomic():
        # A no-op UPDATE acquires the database write lock before reading the
        # window. Concurrent requests for this user must wait until commit.
        WantedCreationQuota.objects.filter(pk=quota.pk).update(user_id=F("user_id"))
        existing = WantedPost.objects.filter(pk=uid, requester=user).first()
        if existing:
            return existing

        now = timezone.now()
        quota.events.filter(created_at__lte=now - POST_WINDOW).delete()
        events = list(quota.events.order_by("created_at").values_list("created_at", flat=True))
        if len(events) >= POST_LIMIT:
            raise CreationRateLimited(max(1, ceil((events[0] + POST_WINDOW - now).total_seconds())))

        post, created = WantedPost.objects.get_or_create(pk=uid, defaults={**defaults, "requester": user})
        if post.requester_id != user.pk:
            from django.http import Http404
            raise Http404("Wanted post not found")
        if created:
            WantedCreationEvent.objects.create(quota=quota, created_at=now)
        return post
