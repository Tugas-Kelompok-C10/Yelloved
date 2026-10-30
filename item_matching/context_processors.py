from django.urls import reverse

from .summary import tabs_with_stats

SKIPPED_PREFIXES = ('/admin/', '/static/', '/media/')


def activity_summary(request):
    """Navbar Activity summary, independent of the removed notification bell."""
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated or request.path.startswith(SKIPPED_PREFIXES):
        return {}
    dashboard = reverse('item_matching:dashboard')
    tabs = tabs_with_stats(user)
    for tab in tabs:
        tab['url'] = f"{dashboard}?tab={tab['key']}"
    by_key = {tab['key']: tab for tab in tabs}
    action_needed = by_key['incoming']['pending'] + by_key['offers_received']['pending']
    return {
        'matching_pending_count': action_needed,
        'matching_summary': {
            'tabs': tabs,
            'total': sum(tab['total'] for tab in tabs),
            'action_needed': action_needed,
            'waiting': by_key['sent']['pending'] + by_key['offers_sent']['pending'],
        },
    }
