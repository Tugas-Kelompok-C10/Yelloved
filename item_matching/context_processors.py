from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from account_profile.models import NotificationPreference

from .models import ItemOffer, ItemRequest
from .summary import tabs_with_stats

RECENT = timedelta(days=7)
DECIDED = ('accepted', 'rejected')
SKIPPED_PREFIXES = ('/admin/', '/static/', '/media/')


def _plural(count, word):
    return f'{count} {word}' if count == 1 else f'{count} {word}s'


def matching_notifications(request):
    """Navbar data: the Item Matching summary popover and the bell's notification list.

    Both are derived from live request/offer state (no separate table to go stale).
    Item requests follow the `order_updates` preference and item offers on wanted posts follow
    `wanted_updates`. The pending counter always shows: it is something the user must act on.
    """
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated or request.path.startswith(SKIPPED_PREFIXES):
        return {}
    dashboard = reverse('item_matching:dashboard')
    tabs = tabs_with_stats(user)
    for tab in tabs:
        tab['url'] = f"{dashboard}?tab={tab['key']}"
    by_key = {tab['key']: tab for tab in tabs}
    pending_requests = by_key['incoming']['pending']
    pending_offers = by_key['offers_received']['pending']
    summary = {
        'tabs': tabs,
        'total': sum(t['total'] for t in tabs),
        'action_needed': pending_requests + pending_offers,
        'waiting': by_key['sent']['pending'] + by_key['offers_sent']['pending'],
    }

    prefs = NotificationPreference.objects.filter(user=user).first()
    order_updates = prefs.order_updates if prefs else True
    wanted_updates = prefs.wanted_updates if prefs else True
    since = timezone.now() - RECENT
    notes = []
    if order_updates:
        if pending_requests:
            notes.append({'text': f'{_plural(pending_requests, "item request")} waiting for your decision',
                          'url': by_key['incoming']['url']})
        for r in ItemRequest.objects.filter(requester=user, status__in=DECIDED, updated_at__gte=since
                                            ).select_related('item')[:3]:
            notes.append({'text': f'Request for “{r.item.title}” was {r.get_status_display().lower()}',
                          'url': by_key['sent']['url']})
    if wanted_updates:
        if pending_offers:
            notes.append({'text': f'{_plural(pending_offers, "item offer")} for your wanted posts',
                          'url': by_key['offers_received']['url']})
        for o in ItemOffer.objects.filter(offerer=user, status__in=DECIDED, updated_at__gte=since
                                          ).select_related('item')[:3]:
            notes.append({'text': f'Offer “{o.item.title}” was {o.get_status_display().lower()}',
                          'url': by_key['offers_sent']['url']})
    return {
        'matching_notifications': notes[:6],
        'matching_pending_count': summary['action_needed'],
        'matching_summary': summary,
    }
