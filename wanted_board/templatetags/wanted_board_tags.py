from decimal import Decimal, InvalidOperation

from django import template
from django.urls import reverse


register = template.Library()


@register.simple_tag(takes_context=True)
def wanted_chat_url(context, post):
    requester_id = getattr(post, "requester_id", None)
    user = context.get("user")
    if requester_id and requester_id != getattr(user, "pk", None):
        return reverse("chat:with_user", args=[requester_id])
    # Demo posters have no real account; owners should not chat with themselves.
    return reverse("chat:inbox")


@register.filter
def rupiah(value):
    """Format a number as whole Indonesian Rupiah using dot separators."""
    if value in (None, ""):
        return ""

    try:
        amount = int(Decimal(str(value)))
    except (InvalidOperation, TypeError, ValueError):
        return value

    return f"Rp {amount:,}".replace(",", ".")
