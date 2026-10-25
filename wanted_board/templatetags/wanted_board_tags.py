from decimal import Decimal, InvalidOperation

from django import template


register = template.Library()


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
