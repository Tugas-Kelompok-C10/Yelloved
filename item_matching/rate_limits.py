"""Successful photo offers: five per account in a rolling ten-minute window."""
from contextlib import contextmanager
from datetime import timedelta
from math import ceil

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import PhotoOfferQuota

PHOTO_OFFER_LIMIT = 5
PHOTO_OFFER_WINDOW = timedelta(minutes=10)


class PhotoOfferRateLimited(Exception):
    def __init__(self, retry_after):
        self.retry_after = retry_after
        minutes = ceil(retry_after / 60)
        self.message = (
            f'You have reached the limit of {PHOTO_OFFER_LIMIT} photo offers in 10 minutes. '
            f'Please retry in {minutes} minute{"s" if minutes != 1 else ""}. '
            'Your photo and offer details have been kept in this form.'
        )
        super().__init__(self.message)


@contextmanager
def locked_photo_offer_quota(user):
    quota, _ = PhotoOfferQuota.objects.get_or_create(user=user)
    with transaction.atomic():
        # Lock the account before locking a post, consistently across all offers.
        PhotoOfferQuota.objects.filter(pk=quota.pk).update(user_id=F('user_id'))
        yield quota


def check_photo_offer_limit(quota):
    now = timezone.now()
    timestamps = list(quota.events.filter(created_at__gt=now - PHOTO_OFFER_WINDOW)
                      .order_by('created_at').values_list('created_at', flat=True)[:PHOTO_OFFER_LIMIT])
    if len(timestamps) >= PHOTO_OFFER_LIMIT:
        raise PhotoOfferRateLimited(max(1, ceil((timestamps[0] + PHOTO_OFFER_WINDOW - now).total_seconds())))


def record_photo_offer(quota):
    # Called in the same transaction as offer.save(); failures consume no slot.
    now = timezone.now()
    quota.events.filter(created_at__lte=now - PHOTO_OFFER_WINDOW).delete()
    quota.events.create(created_at=now)
