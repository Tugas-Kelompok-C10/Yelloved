from django import template

from ..models import ItemRequest

register = template.Library()


@register.simple_tag
def item_request_state(item, user):
    """What the signed-in user should see about requests on `item`."""
    if not user.is_authenticated or item.source != 'user':
        return {'mine': None, 'incoming': []}
    if item.owner_id == user.pk:
        pending = ItemRequest.objects.filter(item=item, status=ItemRequest.Status.PENDING)
        return {'mine': None, 'incoming': list(pending.select_related('requester'))}
    latest = ItemRequest.objects.filter(item=item, requester=user).first()  # Meta ordering: newest first
    return {'mine': latest, 'incoming': []}
