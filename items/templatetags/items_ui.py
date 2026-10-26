"""Presentation labels only; stored item choices remain unchanged."""
from django import template

register = template.Library()


@register.filter
def condition_badge(value):
    return {'like_new': 'LIGHTLY USED', 'good': 'WELL USED', 'fair': 'HEAVILY USED',
            'new': 'NEW'}.get(value, 'PRELOVED')


@register.filter
def listing_badge(value):
    return {'sale': 'SELL', 'free': 'FREE', 'swap': 'SWAP'}.get(value, 'PRELOVED')
