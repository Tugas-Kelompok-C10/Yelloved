from django import template

register = template.Library()


@register.simple_tag
def cart_listing_count(user):
    """Count unique cart listings, never legacy quantities or another user's cart."""
    return user.cart_items.count() if user.is_authenticated else 0
