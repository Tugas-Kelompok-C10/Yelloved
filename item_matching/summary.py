from django.db.models import Count, Q

from .models import ItemOffer, ItemRequest
from .tabs import TABS


def _counts(qs):
    return qs.aggregate(total=Count('pk'),
                        pending=Count('pk', filter=Q(status='pending')),
                        accepted=Count('pk', filter=Q(status='accepted')))


def tab_stats(user):
    """{tab key: {'total', 'pending', 'accepted'}} for the four dashboard tabs (one query each)."""
    return {
        'incoming': _counts(ItemRequest.objects.filter(item__owner=user)),
        'sent': _counts(ItemRequest.objects.filter(requester=user)),
        'offers_received': _counts(ItemOffer.objects.filter(wanted_post__requester=user)),
        'offers_sent': _counts(ItemOffer.objects.filter(offerer=user)),
    }


def tabs_with_stats(user):
    """The TABS definitions merged with this user's counts."""
    stats = tab_stats(user)
    return [{**tab, **stats[tab['key']]} for tab in TABS]
